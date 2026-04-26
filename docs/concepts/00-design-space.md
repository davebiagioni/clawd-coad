# The design space

Before reading any of `clawd`'s code, it helps to know what kind of thing
you're building and what the alternatives look like. "Agentic coding CLI" is
a young enough category that the popular tools disagree on basic questions.

## The minimum viable shape

Every tool in this category has the same core loop:

1. Take a user message.
2. Send it to an LLM, along with a list of *tools* the model can call.
3. If the model asks to call a tool, run the tool and feed the result back.
4. Repeat until the model produces a final answer.

That's it. The model is the brain; the tools are its hands. Everything
else — TUIs, approval flows, sandboxing, observability — is scaffolding
around that loop.

`clawd` implements that loop in 48 lines (`clawd/agent.py`), using
[LangGraph]'s prebuilt `create_react_agent`. It could be even shorter without
the graph framework; we'll talk about why a framework helps in
[chapter 1](01-agent-loop.md).

[LangGraph]: https://langchain-ai.github.io/langgraph/

## Where the popular tools differ

| Tool | Surface | Model lock-in | Sandboxing | Editing model |
|---|---|---|---|---|
| **Claude Code** | TUI + IDE plugin | Claude only | Optional bash sandbox; subagents | Edit/Write tools, model produces patches |
| **Aider** | TUI | Any (LiteLLM) | None by default | Asks model for unified diffs, applies them itself |
| **Cursor** | IDE | Multiple | None | Inline edits via custom protocol |
| **OpenHands** | Web/CLI | Any | Docker container per session | Tools inside the container |
| **clawd** | TUI | OpenAI-compatible or Anthropic | Path-jailed to a git worktree | Edit-style tool, exact-string match |

The interesting axes:

- **Model lock-in.** Claude Code is tightly coupled to Claude — its prompt,
  its tool-calling format, its caching strategy. Aider and OpenHands stay
  provider-neutral and pay for it in features that need provider-specific
  hooks. `clawd` picks a middle path: OpenAI-compatible by default (so any
  local or hosted OSS model works), with a small explicit branch for
  Anthropic when you want to use Claude directly.

- **Sandboxing.** "What happens when the model runs `rm -rf .`?" Claude Code
  prompts the user. OpenHands runs everything in a fresh Docker container.
  Aider runs in your shell and trusts you to review diffs. `clawd` uses a
  **git worktree** — a sibling working copy on a throwaway branch, so the
  model can do whatever it wants and you review with `git diff` before
  merging. Cheap, no Docker required, and version-controlled by construction.

- **Editing model.** This is the *single biggest* design choice and it's
  invisible to users. Aider asks the model for unified diffs and applies
  them — works well with smaller models because diffs are a structured
  output. Claude Code uses an `Edit` tool with `old_string`/`new_string`
  exact-match — robust against malformed diffs but requires the model to
  produce enough surrounding context to make the match unique. `clawd`
  copies Claude Code's approach because exact-match is easier to debug when
  it fails.

## What clawd deliberately omits

So you know what to expect:

- **No subagents.** Claude Code's `Agent` tool spawns sub-conversations
  with their own context. Useful but adds complexity; out of scope here.
- **No MCP.** The Model Context Protocol is a great way to ship tools as
  separate processes. `clawd`'s tools are in-process Python functions
  because that's the minimum needed to learn the loop.
- **No approval flow.** Claude Code prompts before destructive bash
  commands; `clawd` relies on the worktree jail to make destructive
  commands cheap to recover from. Adding an approval prompt would be a
  good exercise.
- **No streaming-tokens UI fanciness.** The TUI prints tool calls and final
  responses; it does not stream tokens character-by-character. You can add
  it; LangGraph supports streaming.

## Why LangGraph?

You don't *need* a graph framework to build this. A bare `while` loop with
the OpenAI SDK works. We use LangGraph for three concrete reasons:

1. **Checkpointing.** `create_react_agent` accepts a `checkpointer` that
   persists every step to SQLite. You get conversation resume, replay, and
   time-travel debugging for free.
2. **Provider abstraction.** `langchain-core`'s `BaseChatModel` interface
   means the same agent code works for OpenAI, Anthropic, Ollama, etc.
   without us writing the adapters.
3. **Callbacks.** The same callback hook used for streaming output to the
   TUI is also used to send traces to Langfuse. One mechanism, two payoffs.

When the tutorial reaches [chapter 1](01-agent-loop.md), we'll show what
the loop looks like *without* LangGraph too, so you can judge the trade.

## What you should be able to do after reading

By the end of these docs you should be able to:

- Read every line of `clawd/` and know why it's there.
- Swap the model provider without changing anything outside `llm.py` and
  `.env`.
- Add a new tool (e.g. a SQL runner, a Linear API client) and have the
  agent use it correctly.
- Replace the worktree sandbox with a different isolation strategy
  (Docker, chroot, none) without touching the agent loop.
- Add streaming token output to the TUI.

If any of those feel unclear after reading the relevant chapter, that's a
docs bug — open an issue.
