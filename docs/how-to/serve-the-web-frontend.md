# Serve the web frontend

`clawd serve` runs the same agent loop behind a tiny FastAPI app, with a
single-page web UI on top. Optional — installed as a `[web]` extra. Useful
when you want streaming markdown, copyable code blocks, and KaTeX-rendered
math instead of a terminal.

The backend is `clawd/web/server.py` (~140 lines); the frontend is
vanilla JS in `clawd/web/static/` (~500 lines of HTML/CSS/JS). Same
agent, same tools, same worktree as the TUI — only the surface changes.

## Prerequisites

- A working clawd setup (a model configured, a project to work on). If
  you've never run the TUI, start with the [quickstart](../../README.md#quickstart).
- The `[web]` extra installed (next step).

## Steps

### 1. Install the web extra

```bash
uv pip install -e '.[web]'
```

This adds `fastapi`, `uvicorn`, and `sse-starlette`. Without it,
`clawd serve` exits with a one-line hint instead of starting.

### 2. Start the server

```bash
cd ~/your-project
clawd serve
# clawd web — http://127.0.0.1:8765  (thread <id>)
```

Same session flags as the TUI: `--continue` resumes the most recent
session, `--resume <id>` resumes a named one, no flag starts a fresh
thread. `--host` and `--port` override the defaults (`127.0.0.1:8765`).

### 3. Open the page

Visit <http://127.0.0.1:8765>. The header shows the same provider,
model, and worktree branch the TUI banner shows, plus a running token
and cost tally. The textarea sends on submit; tokens stream in over
[Server-Sent Events][sse], and tool calls and outputs render inline as
the agent runs them.

If you opened a `--continue` or `--resume` session, the prior
conversation is replayed via `GET /api/history` before the composer
becomes interactive.

[sse]: https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events

## What renders

- **Markdown** via [marked], sanitized with [DOMPurify].
- **LaTeX** via [KaTeX]'s auto-render extension. Standard delimiters:
  `$...$` and `\(...\)` inline, `$$...$$` and `\[...\]` display. Useful
  when a model explains an algorithm with actual math instead of ASCII
  pseudocode — try `derive the closed-form solution for ridge regression`
  and watch the equations come out typeset.
- **Tool calls** as `name({...args})` lines; **tool outputs** in a
  monospace block, with a small visual cue when the output looks like
  `git diff` output.

[marked]: https://marked.js.org
[DOMPurify]: https://github.com/cure53/DOMPurify
[KaTeX]: https://katex.org

## The HTTP shape

Three endpoints, if you want to swap the frontend (or drive it from a
script):

- `GET /api/info` — provider, model, branch, jail root, running token /
  cost totals.
- `GET /api/history` — the checkpointed conversation as a list of
  `{kind, ...}` records (`user`, `assistant`, `tool_call`, `tool_output`).
- `POST /api/chat` — body `{"text": "..."}`, returns an SSE stream with
  events `token`, `tool_start`, `tool_end`, `done`. These mirror the
  LangGraph `astream_events` types the TUI consumes (chapter 8).

## What's not here

The web frontend is deliberately tiny and trust-mode-only:

- **No auth, localhost-only by default.** Don't expose `--host 0.0.0.0`
  on a network you don't trust — anyone who reaches the port can drive
  the agent against your worktree.
- **One thread per server.** The `thread_id` is fixed at startup. Want
  a second conversation? Start a second `clawd serve` on another port.
- **Slash commands are TUI-only.** No `/diff`, `/clear`, `/cost` in the
  browser yet. Run `git -C <worktree> diff` from a shell, or flip back
  to the TUI for those.

## Related

- [Chapter 8: the TUI](../concepts/08-tui.md) — the parallel surface,
  and the `astream_events` shape both frontends consume.
- [Chapter 7: observability](../concepts/07-observability.md) — the
  ledger and pricing the header tally pulls from.
- `clawd/web/server.py`, `clawd/web/static/` — the source of truth.
