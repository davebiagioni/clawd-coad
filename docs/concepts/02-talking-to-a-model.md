# Chapter 2: Talking to a model

> **Code for this chapter:** `clawd/llm.py` (23 lines), `clawd/config.py`
> (33 lines), `.env.example`

The agent loop from [chapter 1](01-agent-loop.md) needs a model to call. In
2026 there are many ways to get one:

- **Hosted closed-source.** OpenAI, Anthropic, Google.
- **Hosted open-source.** OpenRouter, Together, Groq, Fireworks, Cerebras.
- **Local open-source.** Ollama, llama.cpp, vLLM, LM Studio.
- **Self-hosted closed-source.** Azure OpenAI, AWS Bedrock.

`clawd` is designed so the same code works against any of them. This
chapter explains how, and what the limits of "any of them" actually are.

## The OpenAI chat completions protocol won

When OpenAI shipped `chat/completions` with function calling in 2023, every
inference provider that came after it copied the wire format. Today, the
phrase **"OpenAI-compatible endpoint"** means the server speaks:

- `POST /v1/chat/completions` with the same request schema.
- Tool calls in the same `tool_calls`/`tool` message shape.
- Streaming via Server-Sent Events with the same delta format.

Ollama, vLLM, llama.cpp's server, OpenRouter, Together, Groq, Fireworks —
all of them. You point the OpenAI SDK at a different `base_url`, set an
API key (often a dummy string for local servers), and the same client code
works.

Anthropic is the major exception. Their Messages API has a different shape
(content blocks, separate `tool_use`/`tool_result` types, no
`tool_call_id`). Worth it for them because they ship features the OpenAI
protocol doesn't have a slot for (extended thinking, prompt caching with
explicit cache breakpoints, fine-grained streaming events). Not worth
re-implementing in your own code, which is why we use a library.

## `clawd/llm.py`

```python
from langchain_core.language_models import BaseChatModel

from .config import settings


def make_llm() -> BaseChatModel:
    if settings.provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model=settings.model,
            api_key=settings.api_key,
            temperature=0,
        )

    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=settings.model,
        base_url=settings.base_url,
        api_key=settings.api_key,
        temperature=0,
    )
```

Two branches, twenty-three lines. The interesting parts:

- **Return type is `BaseChatModel`**, not a provider-specific class. The
  agent in chapter 1 only ever sees this interface. Add a third provider
  (Google, Bedrock) by adding a third branch — nothing downstream changes.
- **Imports inside the branches.** `langchain_anthropic` is only imported
  if you actually use Anthropic. Keeps cold start fast and lets users who
  don't have an Anthropic key avoid installing extra dependencies in
  practice (the library is in `pyproject.toml` because we ship both, but
  the import-on-demand pattern scales if you add five more providers).
- **`temperature=0`.** Coding agents almost always want deterministic
  output. The model still picks tools and writes code; you just don't want
  it picking *differently* on retries.

What's deliberately *not* here:

- No fallback chain ("try Anthropic, fall back to OpenAI"). If your
  provider is down, that's a real signal worth surfacing, not papering
  over.
- No retry logic. The provider SDKs already retry on transient failures.
- No model selection logic. Picking a model is a config concern, not a
  runtime concern.

## `clawd/config.py`

```python
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CLAWD_",
        env_file=".env",
        extra="ignore",
    )

    provider: Literal["openai", "anthropic"] = "openai"
    model: str = "qwen2.5-coder:7b"
    api_key: str = "ollama"
    base_url: str = "http://localhost:11434/v1"
    db_path: str = "~/.clawd/sessions.db"
```

Five fields, all overridable from the environment with the `CLAWD_` prefix.
The defaults are deliberate:

- **`provider="openai"`** — but pointed at Ollama. Out of the box, no API
  bill, no account signup, no internet required. You'll see this default
  in every chapter.
- **`model="qwen2.5-coder:7b"`** — small enough to run on a laptop, good
  enough at tool-calling to drive the loop. Your mileage will vary; see
  "Picking a model" below.
- **`api_key="ollama"`** — Ollama doesn't check it but the OpenAI SDK
  requires *something* in the header. "ollama" is the convention.
- **`base_url="http://localhost:11434/v1"`** — Ollama's OpenAI-compatible
  endpoint.

`pydantic-settings` does the .env loading and type coercion. The
`Literal["openai", "anthropic"]` type means a typo in `CLAWD_PROVIDER`
fails fast at startup instead of mysteriously later.

## Recipes: switching providers

### OpenAI

```bash
CLAWD_PROVIDER=openai
CLAWD_BASE_URL=https://api.openai.com/v1
CLAWD_MODEL=gpt-4o-mini
CLAWD_API_KEY=sk-...
```

### Anthropic

```bash
CLAWD_PROVIDER=anthropic
CLAWD_MODEL=claude-haiku-4-5-20251001     # cheap, great for tinkering
# CLAWD_MODEL=claude-sonnet-4-6           # the coding workhorse
CLAWD_API_KEY=sk-ant-...
```

Note: `CLAWD_BASE_URL` is ignored when `provider=anthropic` — the SDK uses
its own default.

### OpenRouter (any model on the menu)

```bash
CLAWD_PROVIDER=openai
CLAWD_BASE_URL=https://openrouter.ai/api/v1
CLAWD_MODEL=meta-llama/llama-3.3-70b-instruct
CLAWD_API_KEY=sk-or-...
```

### vLLM (your own GPU)

```bash
CLAWD_PROVIDER=openai
CLAWD_BASE_URL=http://your-server:8000/v1
CLAWD_MODEL=Qwen/Qwen2.5-Coder-32B-Instruct
CLAWD_API_KEY=anything
```

## Picking a model

The single most-asked question in this category is "which model should I
use?" The honest answer in 2026 is *it depends on your machine and
budget*, but here are the constraints that actually matter for an agentic
coding CLI:

- **Tool calling has to work.** Many open-source models can produce JSON
  but mangle the tool-call structure. If the agent never calls any tools
  and just chats at you, that's the symptom. Models known to be solid:
  Qwen2.5-Coder family, Llama 3.3, the GPT-4o family, Claude Haiku/Sonnet.
- **Context window.** Coding sessions accumulate context fast. Anything
  under 32k will start truncating mid-task. 128k+ is comfortable.
- **Latency.** A 7B local model on Ollama might take 5s per turn; a
  hosted Groq endpoint might take 200ms. The loop runs many turns, so
  this compounds.
- **Cost per session.** A typical 10-minute coding session might burn
  100k–500k tokens between input and output. Multiply by your provider's
  rate.

The local default (`qwen2.5-coder:7b`) is good enough to follow this
tutorial. For real work you'll want something stronger — pick whatever
fits your situation.

## What's missing from this chapter

- **Streaming.** `make_llm()` returns a model that *can* stream, but
  nothing in `clawd` enables it yet. Adding streaming means using
  `astream` instead of `ainvoke` in the agent loop and rendering deltas
  in the TUI. Good exercise for chapter 9.
- **Prompt caching.** Anthropic and OpenAI both offer prompt caching, but
  the APIs are different, and `langchain-*` exposes them differently.
  Worth a separate chapter when this tutorial gets there.
- **Vision / multimodal.** `clawd` is text-only. Adding image input is a
  config change plus a TUI change.

## Exercise

Run `clawd` against three different providers (e.g. local Ollama, hosted
OSS via OpenRouter, and one frontier model) on the same simple task —
"add a docstring to every function in `clawd/agent.py`". Compare:

- Did each model use the right tools?
- Did it produce equivalent output?
- How long did it take?
- How much did it cost (where applicable)?

You'll develop intuition for how much of the agent's quality comes from
the model versus the scaffolding. (Answer: more from the model than you
expect, and more from the scaffolding than the model vendors will admit.)
