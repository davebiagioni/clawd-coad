# Chapter 7: Observability

> **Code for this chapter:** `clawd/tracing.py` (26 lines),
> `clawd/pricing.py` (66 lines), `tests/test_tracing.py`

The agent loop is, by nature, *opaque*. The model decided to call
`read_file`, then `grep`, then `edit_file`, then write a final answer —
and you have no idea why. When something goes wrong (the model
hallucinated a function, looped on a tool error, blew the budget),
understanding it after the fact requires *traces*: a structured record
of every LLM call, every tool call, every input, every output, every
token count.

This chapter covers `clawd`'s tracing setup (Langfuse, optional) and
the small pricing module that makes those traces report cost in
dollars.

## Why traces, not just logs

Logs are text-shaped: lines, files, levels. Traces are tree-shaped: a
parent span contains child spans, each with attributes (model name,
input tokens, latency, etc.) and links to siblings.

For an agent, the tree shape is everything. One user turn produces:

```
turn (8.2s, 12.1k input tokens, 412 output tokens, $0.0034)
├── llm call #1 (1.1s, 8.4k in, 87 out)
├── tool: read_file(path="agent.py") (3ms)
├── llm call #2 (0.9s, 9.1k in, 134 out)
├── tool: edit_file(path="agent.py", ...) (4ms)
├── llm call #3 (1.2s, 9.8k in, 98 out)
├── tool: bash(command="pytest tests/test_agent.py") (4.1s)
└── llm call #4 (0.8s, 10.4k in, 93 out)
```

A flat log can't represent that without inventing one. A tracing
backend (Langfuse, OpenTelemetry collectors, [Phoenix], Honeycomb,
Datadog APM) understands the tree natively.

[Phoenix]: https://github.com/Arize-ai/phoenix

## Langfuse: the LLM-shaped option

`clawd` uses [Langfuse] for one reason: it's purpose-built for LLM
applications. Generic APM tools (Datadog, Honeycomb) understand spans
but not "this span had a `gpt-4o` model call with 8.4k input tokens at
$0.05/1M." Langfuse does, and it shows you token counts, costs,
prompts, and responses without you instrumenting them yourself.

Other valid options for the same job:

- **OpenTelemetry + a backend that knows about LLMs** (Phoenix is a
  good one; Honeycomb has decent LLM support now).
- **OpenLLMetry**, which is OTel with LLM-specific conventions.
- **Self-rolled.** Print every step to JSONL and grep later. Surprisingly
  workable for solo dev work.

We chose Langfuse because it's free for self-hosting (single-binary
Docker), the langchain integration is one line, and the UI for
inspecting agent runs is the best of what we tried in 2026.

[Langfuse]: https://langfuse.com

## `clawd/tracing.py`

```python
from langchain_core.callbacks import BaseCallbackHandler

from .config import langfuse_settings


def make_langfuse_handler() -> BaseCallbackHandler | None:
    if not (langfuse_settings.public_key and langfuse_settings.secret_key):
        return None

    from langfuse import Langfuse
    from langfuse.langchain import CallbackHandler

    Langfuse(
        public_key=langfuse_settings.public_key,
        secret_key=langfuse_settings.secret_key,
        host=langfuse_settings.host,
    )
    return CallbackHandler()


def flush() -> None:
    if not (langfuse_settings.public_key and langfuse_settings.secret_key):
        return
    from langfuse import get_client

    get_client().flush()
```

The whole file. Three things to notice:

### 1. Optional by default

```python
if not (langfuse_settings.public_key and langfuse_settings.secret_key):
    return None
```

If you haven't set `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` in
the environment, tracing is disabled. The agent doesn't fail; it just
doesn't trace. The TUI passes the (None) handler through and the
LangGraph callback system silently no-ops.

This is the right default for a tutorial project — most readers will
not have a Langfuse instance handy. Setting it up should be opt-in.

### 2. `BaseCallbackHandler`: one mechanism, many uses

```python
return CallbackHandler()
```

`langchain_core.callbacks.BaseCallbackHandler` is the single hook
LangGraph (and LangChain) exposes for *anything that wants to observe
the loop*: tracing, streaming UI updates, cost tracking, custom
logging. Same interface, different implementations.

In `clawd`, this matters because:

- The TUI uses LangGraph's `astream_events` to render output (chapter 8),
  which is built on the same callback machinery.
- The Langfuse handler is just another callback that subscribes to the
  same events.

Adding a third observer (say, a JSONL logger) is a one-class change.

### 3. Explicit flush

```python
def flush() -> None:
    ...
    get_client().flush()
```

Langfuse buffers spans and ships them to the backend on a background
thread. If your process exits before the buffer drains, you lose the
tail. `agent.py` calls `flush_tracing()` in its `finally:` block to
guarantee the last trace makes it out.

This is the kind of thing you only learn by losing data once.

## `clawd/pricing.py`: making traces show dollars

Langfuse can compute cost-per-trace if it knows the per-token price for
your model. Their cloud pricing list covers OpenAI/Anthropic/Google
out of the box, but local models (`qwen2.5-coder:7b`, your custom vLLM
deployment) it doesn't know about.

`clawd/pricing.py` exists so users can register a model's price from the
TUI (`/cost set 0.15 0.6` → input $0.15/1M, output $0.6/1M) without
clicking through the Langfuse UI:

```python
async def find_pricing(model_name: str) -> Any | None:
    """Return the Langfuse model entry whose match_pattern matches `model_name`, else None."""
    client = _api_client()
    if client is None:
        return None

    page = 1
    while True:
        result = await client.models.list(page=page, limit=100)
        for m in result.data:
            try:
                if re.match(m.match_pattern, model_name):
                    return m
            except re.error:
                continue
        if page >= result.meta.total_pages:
            return None
        page += 1


async def register_pricing(model_name, input_per_1m, output_per_1m):
    """Register `model_name` in Langfuse with USD-per-1M-token pricing (TOKENS unit)."""
    ...
    return await client.models.create(
        model_name=model_name,
        match_pattern=f"(?i)^{re.escape(model_name)}$",
        unit="TOKENS",
        input_price=input_per_1m / 1_000_000,
        output_price=output_per_1m / 1_000_000,
    )
```

Two concrete things worth knowing:

- **`match_pattern` is a regex.** Langfuse picks the first matching
  entry, walking newest-to-oldest by start time. So if you register
  the exact name, you get a guaranteed-unique match; if you register a
  loose pattern (e.g. `qwen2.5-.*`), it'll catch all variants.
- **Local models register at $0.** `/cost set 0 0` is the right move
  for local Ollama/vLLM deployments, so traces show the right token
  counts but no fake cost.

The TUI's `/cost` command exposes both functions; chapter 8 covers it.

## Trace metadata: `langfuse_session_id`, tags

In `tui.py`, every turn passes config that includes Langfuse-specific
metadata:

```python
config = {
    "configurable": {"thread_id": thread_id},
    "callbacks": session.callbacks,
    "metadata": {
        "langfuse_session_id": thread_id,
        "langfuse_tags": [
            f"provider:{settings.provider}",
            f"model:{settings.model}",
            f"branch:{session.branch}",
        ],
    },
    "run_name": "clawd-turn",
}
```

This buys you, in the Langfuse UI:

- **Sessions.** All turns from the same `thread_id` group together.
- **Tags.** Filter by provider, model, branch — useful when comparing
  "qwen2.5-coder:7b vs gpt-4o-mini on the same task."
- **Run name.** Every span tree shows up labeled `clawd-turn`, so you
  can find your traces in a busy project.

These are Langfuse-specific keys (`langfuse_session_id`,
`langfuse_tags`) that the langchain integration recognizes. Other
backends use different keys; the pattern (annotate every run with
metadata you'll want to filter on later) is universal.

## What's missing

- **Local-only mode.** A JSONL logger callback would let you trace
  without standing up Langfuse. Two-class change; would be a nice
  addition.
- **Trace sampling.** Right now every turn traces. For high-volume use
  you'd want sampling.
- **Eval pipeline.** Langfuse supports running automatic evals over
  past traces (e.g. "did the agent's final answer satisfy the
  request?"). Not wired up; would be a useful next chapter.
- **Latency budgets.** No alerting when turns get slow. Outside scope
  but a real production concern.

## Exercise

Stand up Langfuse locally (`docker compose up`) and run `clawd`
against three different models on the same task. Compare in the
Langfuse UI:

- Total turns
- Total tokens
- Total latency
- Total cost (after running `/cost set` for each)
- Tool-call patterns

This is roughly the same exercise as chapter 2's, but now with data.
You'll learn more about your models from one weekend of Langfuse traces
than from any benchmark.
