# Chapter 1: The agent loop

> **Code for this chapter:** `clawd/agent.py` (48 lines)

The "agent" in an agentic coding CLI is the loop that:

1. Sends the conversation to the LLM with a list of tools available.
2. If the LLM wants to call a tool, runs it and appends the result.
3. Repeats until the LLM stops calling tools.

This is sometimes called a **ReAct loop** (for "Reason + Act"). It's the
heart of the program. Everything else — the TUI, the prompt, the worktree —
is plumbing around it.

## The loop, written by hand

Before we look at `clawd/agent.py`, here's what the loop looks like with no
framework, just the OpenAI SDK:

```python
from openai import OpenAI

client = OpenAI()
messages = [{"role": "system", "content": SYSTEM_PROMPT}]
tools = [READ_FILE_SCHEMA, EDIT_FILE_SCHEMA, BASH_SCHEMA]
tool_impls = {"read_file": read_file, "edit_file": edit_file, "bash": bash}

while True:
    user_input = input("> ")
    messages.append({"role": "user", "content": user_input})

    while True:  # inner loop: keep calling tools until the model stops
        resp = client.chat.completions.create(
            model="gpt-4o", messages=messages, tools=tools,
        )
        msg = resp.choices[0].message
        messages.append(msg)

        if not msg.tool_calls:
            print(msg.content)
            break

        for call in msg.tool_calls:
            args = json.loads(call.function.arguments)
            result = tool_impls[call.function.name](**args)
            messages.append({
                "role": "tool",
                "tool_call_id": call.id,
                "content": result,
            })
```

That's the entire concept. ~25 lines, no framework. If you want to *really*
understand the loop, type that in and run it against a local model.

## Why we don't use that

The hand-rolled version works, but it's missing things you'll want as soon
as the agent does anything non-trivial:

- **Persistence.** Close the terminal, lose the conversation. We want
  conversations to survive across sessions, and we want to be able to
  *replay* them for debugging.
- **Provider portability.** That code is bound to OpenAI's SDK. Swapping
  to Anthropic requires rewriting the whole loop, because tool-call message
  shapes differ.
- **Streaming hooks.** The TUI needs to render tool calls as they happen,
  not wait for the whole turn to finish. Adding that to the hand-rolled
  loop means restructuring it around an async generator.
- **Observability.** We want every LLM call and tool call to show up in
  [Langfuse](https://langfuse.com) (or any OpenTelemetry-compatible
  backend) without scattering instrumentation through the loop.

You can build all of that yourself. We chose to use [LangGraph] because it
gives us all four out of the box, and the API surface we touch is small —
basically one function call.

[LangGraph]: https://langchain-ai.github.io/langgraph/

## Reading `clawd/agent.py`

Here's the file in full, then we'll walk through it.

```python
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from langchain_core.callbacks import BaseCallbackHandler
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.prebuilt import create_react_agent

from .config import settings
from .llm import make_llm
from .prompt import build_system_prompt
from .tools import make_tools
from .tracing import flush as flush_tracing
from .tracing import make_langfuse_handler
from .worktree import ensure_worktree


@dataclass
class Session:
    agent: Any
    jail_root: Path
    branch: str
    callbacks: list[BaseCallbackHandler] = field(default_factory=list)


@asynccontextmanager
async def make_session(thread_id: str = "default") -> AsyncIterator[Session]:
    jail_root, branch = ensure_worktree(thread_id)

    db_path = Path(settings.db_path).expanduser()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    handler = make_langfuse_handler()
    callbacks = [handler] if handler else []

    async with AsyncSqliteSaver.from_conn_string(str(db_path)) as saver:
        agent = create_react_agent(
            make_llm(),
            tools=make_tools(jail_root),
            checkpointer=saver,
            prompt=build_system_prompt(jail_root, branch),
        )
        try:
            yield Session(agent=agent, jail_root=jail_root, branch=branch, callbacks=callbacks)
        finally:
            flush_tracing()
```

### `Session`

A small bag of everything the TUI needs from a started agent:

- `agent` — the LangGraph runnable; you call `.astream(...)` on it.
- `jail_root` — the worktree path the agent is sandboxed to. The TUI
  displays this so the user knows where edits are landing.
- `branch` — the throwaway git branch backing the worktree.
- `callbacks` — Langfuse tracing handler, if configured. Passed to every
  `.astream(...)` call so traces include the right metadata.

The `Any` type on `agent` is deliberate — LangGraph's runnable types are
elaborate and don't add value at this boundary.

### `make_session` — the four ingredients

The `create_react_agent` call is where everything comes together. It needs
four things:

```python
agent = create_react_agent(
    make_llm(),                                  # 1. the model
    tools=make_tools(jail_root),                 # 2. the tools
    checkpointer=saver,                          # 3. persistence
    prompt=build_system_prompt(jail_root, branch),  # 4. the system prompt
)
```

Each of those gets its own chapter:

1. **The model** — `make_llm()` returns a `BaseChatModel`. Covered in
   [chapter 2](02-talking-to-a-model.md).
2. **The tools** — `make_tools(jail_root)` returns a list of `BaseTool`s,
   each scoped to the jail. Covered in [chapter 4](04-tools-filesystem.md)
   and [chapter 5](05-tools-shell-web.md).
3. **The checkpointer** — `AsyncSqliteSaver` writes every step to a
   SQLite file. We'll explain what "every step" means below.
4. **The prompt** — covered in [chapter 3](03-system-prompt.md).

That's the whole agent.

### Why an async context manager?

`make_session` is `@asynccontextmanager`, which means usage looks like:

```python
async with make_session(thread_id) as session:
    async for chunk in session.agent.astream(...):
        ...
```

Two reasons it's shaped this way:

- **Resource cleanup.** `AsyncSqliteSaver.from_conn_string(...)` is itself
  an async context manager — it opens and closes the SQLite connection.
  Wrapping it in our own context manager lets the TUI not care.
- **Trace flushing.** Langfuse buffers spans and flushes in the
  background; if the program exits before the buffer drains, you lose the
  last trace. The `finally: flush_tracing()` makes sure that doesn't
  happen even if the TUI crashes.

### Why a checkpointer?

The checkpointer is the most under-appreciated piece. Every time the agent
takes a step (an LLM call, a tool call, a tool result), LangGraph writes
the new state to the checkpointer's storage, keyed by `thread_id`. This
buys you:

- **Resume across restarts.** Reopen the TUI with the same `thread_id`
  and the conversation picks up where it left off.
- **Multiple parallel conversations.** Each `thread_id` is independent.
  The TUI doesn't currently expose this, but it's two lines of code to add
  a "new chat" command.
- **Replay.** You can read the SQLite file directly to see exactly what
  happened in any past conversation — useful when a model does something
  surprising and you want to know why.

`SqliteSaver` is the simplest backend; LangGraph also ships Postgres and
Redis variants if you want shared state across machines.

## What's missing from this chapter

We didn't cover:

- **How `astream` actually drives the loop.** That's a LangGraph internals
  question, covered briefly in [chapter 8](08-tui.md) when we wire up the
  TUI.
- **The system prompt.** [Chapter 3](03-system-prompt.md).
- **What "every step" means in checkpointer storage.** If you're curious
  now, open `~/.clawd/sessions.db` with `sqlite3` and `SELECT * FROM
  checkpoints LIMIT 5`.

## Exercise

Rewrite `make_session` without LangGraph, using the OpenAI SDK directly.
Keep the four ingredients (model, tools, persistence, prompt) but
implement them yourself. Use `shelve` or a JSON file for persistence — the
goal is to feel where the framework was helping.

When you're done, compare line counts and decide whether the framework
earns its keep for *your* use case. There is no wrong answer.
