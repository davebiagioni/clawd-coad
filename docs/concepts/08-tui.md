# Chapter 8: The TUI

> **Code for this chapter:** `clawd/tui.py` (235 lines), `clawd/cli.py`
> (5 lines)

The TUI is where the user actually meets the agent. Everything in
chapters 1–7 is invisible plumbing; this is what they see. It also
turns out to be the largest file in the project (~235 lines), because
"render an LLM streaming token-by-token while also showing tool calls
and supporting slash commands" is more code than "wire up an agent."

## Rich, not Textual

`clawd` uses [Rich] for the TUI, not [Textual]. The decision shows up
in `pyproject.toml` (we depend on `rich`, not `textual`). Why:

- **Rich is line-oriented.** The terminal scrolls, like a chat. Each
  turn appends to the bottom. This matches how coding agents are used
  (long-running, scroll-back-able sessions) and matches what users
  already know from `claude`/`aider`/the shell itself.
- **Textual is screen-oriented.** Full-screen TUI apps with panels,
  focus, mouse events. Beautiful for an editor, overkill for a chat.
- **Rich works inside other terminals.** Tmux, VS Code's integrated
  terminal, SSH sessions — Rich is just ANSI escape codes. Textual
  needs a real terminal-like environment.

If you want to swap to Textual later, the agent code (chapters 1–7)
doesn't change. `tui.py` is the only file that knows about presentation.

[Rich]: https://rich.readthedocs.io
[Textual]: https://textual.textualize.io

## `clawd/cli.py`: the entry point

```python
from .tui import run


def main() -> None:
    run()
```

That's the whole CLI. `pyproject.toml` registers `clawd = "clawd.cli:main"`
as a console script, so `pip install -e .` gives you a `clawd` command
that calls `tui.run()`.

No argument parsing — yet. The first thing this would grow is a
`--thread-id` flag (currently hardcoded to `"default"`); see "what's
missing."

## The shape of `tui.py`

The file has three layers:

1. **`_main()`** — the REPL loop. Read input, dispatch.
2. **`_run_turn()`** — invoke the agent for one user message; render
   the streaming output.
3. **Slash commands** — `/help`, `/clear`, `/diff`, `/cost`. A small
   dict-based dispatcher.

Plus helpers: `_banner`, `_replay_history`, `_pricing_nudge`.

We'll walk through the interesting parts.

## Streaming with `astream_events`

```python
async def _run_turn(agent, config, prompt: str) -> None:
    buffer = ""
    live: Live | None = None

    def stop_live() -> None:
        ...

    async for event in agent.astream_events(
        {"messages": [HumanMessage(content=prompt)]},
        config=config,
        version="v2",
    ):
        kind = event["event"]

        if kind == "on_chat_model_stream":
            chunk = event["data"]["chunk"]
            token = chunk.content if isinstance(chunk.content, str) else ""
            ...
            live.update(Markdown(buffer))

        elif kind == "on_tool_start":
            stop_live()
            console.print(f"[yellow]→ {name}({tool_input})[/]")

        elif kind == "on_tool_end":
            ...
            console.print(f"[dim]{text}[/]")
```

`astream_events` is LangGraph's "give me every event that happens
during this run" API. Three event types we care about:

- **`on_chat_model_stream`** — a token from the model. Append to a
  buffer, re-render the buffer as markdown via Rich's `Live`.
- **`on_tool_start`** — the model decided to call a tool. Stop the
  live render, print the tool name + arguments inline.
- **`on_tool_end`** — tool returned. Print a dimmed, truncated preview.

The `Live` object is Rich's "redraw this region in place" widget —
it lets us render incomplete markdown as it streams (think "\`\`\`python"
mid-stream, before the closing fence arrives). When a tool call
interrupts the stream, we stop the live region so the tool call
appears below it instead of clobbering it.

What's *not* here:

- **No real markdown until end-of-turn.** Markdown that's mid-stream
  (a half-open code block, an incomplete table) renders weirdly. We
  let Rich's Markdown component cope; it does a decent job. A more
  polished agent might buffer until paragraph boundaries.
- **No syntax highlighting in mid-stream code blocks.** Same reason —
  highlighting needs the close fence.
- **No reasoning/thinking display.** Anthropic's extended thinking and
  OpenAI's reasoning models emit `on_chat_model_stream` events too,
  but the content is in a separate field this code ignores. Adding
  thinking display is ~10 lines.

## Slash commands

```python
COMMANDS = {
    "/help": (_cmd_help, "show this list"),
    "/clear": (_cmd_clear, "reset this conversation"),
    "/diff": (_cmd_diff, "show git diff of the worktree"),
    "/cost": (_cmd_cost, "show or register langfuse pricing for this model"),
}
```

A simple dispatch table. Each command is `(handler_function,
description)`. The dispatcher in `_main` parses `prompt.split()`,
looks up the first token, calls the handler with `(session, config,
args)`.

The four commands are deliberate:

- **`/help`** — discoverability. Lists itself.
- **`/clear`** — drop the conversation history without exiting. Calls
  `agent.checkpointer.adelete_thread(thread_id)`. The next message
  starts a fresh context.
- **`/diff`** — show what the agent has changed in the worktree.
  Shells out to `git -C <worktree> diff`, renders with Rich's
  syntax-highlighted `Syntax("diff", ...)`. This is the bridge between
  "the agent edited stuff" and "the user reviews it."
- **`/cost`** — show or register Langfuse pricing for the current
  model. Critical for local models that Langfuse doesn't know about
  (chapter 7).

What's *not* here:

- **`/model`** — switch model mid-session. Would need to recreate the
  agent.
- **`/undo`** — revert the worktree to a previous state. Would be
  `git reset --hard <prev>`; mostly a UX question.
- **`/save`** — explicitly checkpoint the worktree (a `git commit`).
  Currently the user does this manually if they want to merge.
- **`/agent`** — spawn a subagent for a sub-task. Out of scope.

## Resume: `_replay_history`

```python
async def _replay_history(agent, config) -> None:
    state = await agent.aget_state(config)
    messages = state.values.get("messages", []) if state and state.values else []
    for msg in messages:
        if msg.type == "human":
            console.print(f"[bold cyan]> {msg.content}[/]")
        elif msg.type == "ai":
            ...
        elif msg.type == "tool":
            ...
```

When you start `clawd` with an existing `thread_id`, the LangGraph
checkpointer has the full conversation. `_replay_history` reads it and
re-renders, so the user sees what happened last session before the new
prompt prompt appears.

Three things worth noting:

- **`agent.aget_state(config)`** is LangGraph's "give me the latest
  saved state for this thread" API. Pure read; no side effects.
- **Three message types.** Human, AI (with optional tool calls), tool
  (the tool result). They render differently — humans in cyan, AI in
  markdown, tools in dim text.
- **Tool outputs truncated to 400 chars on replay.** Old conversations
  with big tool outputs would scroll forever. Truncation hits a
  reasonable middle.

This is the kind of feature that's invisible if you've never used a
checkpointed agent and revelatory once you have. Closing the terminal
no longer means losing context.

## The pricing nudge

```python
async def _pricing_nudge(session: Session) -> None:
    if not session.callbacks:
        return
    try:
        match = await find_pricing(settings.model)
    except Exception:
        return
    if match is None:
        console.print(f"[dim]no langfuse pricing for {settings.model} — run /cost to set it[/dim]")
```

A one-line nudge at session start: if Langfuse is configured *and* the
current model isn't registered there, print a hint about `/cost`. Tries
to be informative without being annoying — the message is dim, fires
once, and silently no-ops if Langfuse isn't on.

The kind of friction-removing detail that makes a tutorial project
feel like a real tool.

## Error handling

Two levels:

```python
try:
    await _run_turn(session.agent, config, prompt)
except KeyboardInterrupt:
    console.print("\n[red]interrupted[/]")
except Exception as e:
    console.print(f"[red]error:[/] {e}")
    console.print(f"[dim]{traceback.format_exc()}[/]")
```

A turn that errors prints the error and continues — *not* exits. The
user can fix whatever (bad prompt, model down, tool bug) and try
again. Ctrl+C interrupts a turn cleanly.

Slash command errors are similarly contained:

```python
try:
    await entry[0](session, config, args)
except Exception as e:
    console.print(f"[red]error:[/] {e}")
```

The whole REPL only exits on EOF (Ctrl+D), explicit `/exit`, or
fall-through Ctrl+C at the prompt. Robust enough for laptop use.

## What's missing

- **Argument parsing.** No `--thread-id`, no `--model`, no `--config`.
  All come from environment.
- **Tab completion** for slash commands and file paths.
- **History.** Up-arrow to recall past prompts. (Rich's `console.input`
  doesn't get GNU readline by default; you'd need `prompt_toolkit`.)
- **Colorblind-friendly themes.** The yellow tool-call lines are
  fixed.
- **Token-by-token visualization of tool input.** Right now tool calls
  appear all-at-once when complete; for slow models you might want to
  see them stream too.
- **Web/IDE surfaces.** A terminal is one delivery channel. Same agent
  could power a `langgraph.serve` HTTP backend with a different
  frontend; nothing in `agent.py`/`tools/` would change.

## Exercise

Add a `/model` command that lets the user switch the model
mid-session. Two design questions to think about before coding:

1. Does the current conversation carry over to the new model, or does
   `/model` imply `/clear`?
2. What about pricing? Should `/model gpt-4o` automatically check if
   pricing is registered and prompt if not?

The implementation is "tear down the agent, make a new one with a new
`make_llm()` result, swap it into `Session`." The interesting part is
the UX.
