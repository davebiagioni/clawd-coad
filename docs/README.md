# Build your own Claude Code

`clawd` is a ~600-line, OSS-friendly clone of the kind of agentic coding CLI
that tools like [Claude Code], [Aider], [Cursor], and [OpenHands] popularized.
It is small enough to read in an afternoon, and these docs walk through *why*
each piece exists — not just what the code does.

[Claude Code]: https://docs.claude.com/en/docs/claude-code/overview
[Aider]: https://aider.chat
[Cursor]: https://cursor.com
[OpenHands]: https://github.com/All-Hands-AI/OpenHands

## Who this is for

People who have *used* a coding agent and want to understand how one works
under the hood — enough to fork it, swap the model, add a tool, or build
something different in the same shape.

You should be comfortable with Python and have a rough mental model of "an
LLM that can call functions." You do **not** need to know LangGraph, Langfuse,
or any specific provider's SDK; we explain those as they show up.

## How to read these docs

Each chapter pairs prose with a specific file or two in `clawd/`,
explaining the design choices, the tradeoffs, and where the same problem
could have been solved differently. Read in order or jump around — each
chapter stands alone.

1. [The design space](concepts/00-design-space.md) — what coding agents
   actually are, and how the popular ones differ
2. [The agent loop](concepts/01-agent-loop.md) — `clawd/agent.py`
3. [Talking to a model](concepts/02-talking-to-a-model.md) — `clawd/llm.py`,
   `clawd/config.py`
4. [The system prompt](concepts/03-system-prompt.md) — `clawd/prompt.py`
5. [Tools, part 1: filesystem](concepts/04-tools-filesystem.md) —
   `clawd/tools/fs.py`
6. [Tools, part 2: shell & web](concepts/05-tools-shell-web.md) —
   `clawd/tools/shell.py`, `clawd/tools/web.py`
7. [Worktrees & isolation](concepts/06-worktrees.md) —
   `clawd/worktree.py`
8. [Observability](concepts/07-observability.md) — `clawd/tracing.py`,
   `clawd/pricing.py`
9. [The TUI](concepts/08-tui.md) — `clawd/tui.py`
10. [Sandboxing with Docker](concepts/09-sandbox.md) — `Dockerfile`,
    `scripts/clawd-sandbox`

## Provider neutrality

`clawd` defaults to a local OpenAI-compatible endpoint (Ollama with
`qwen2.5-coder:7b`) so you can run the whole tutorial offline, on your
laptop, with no API bill. The same code works against OpenAI, Anthropic,
OpenRouter, Together, Groq, vLLM, llama.cpp — anything that speaks the
OpenAI chat completions protocol — plus Anthropic's direct API as a separate
branch in `clawd/llm.py`. Wherever a chapter talks about a provider-specific
quirk, it'll say so.
