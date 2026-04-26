<div align="center">

```
   ▄████████  ▄█          ▄████████  ▄█     █▄  ████████▄
  ███    ███ ███         ███    ███ ███     ███ ███   ▀███
  ███    █▀  ███         ███    ███ ███     ███ ███    ███
  ███        ███         ███    ███ ███     ███ ███    ███
  ███        ███       ▀███████████ ███     ███ ███    ███
  ███    █▄  ███         ███    ███ ███     ███ ███    ███
  ███    ███ ███▌    ▄   ███    ███ ███ ▄█▄ ███ ███   ▄███
  ████████▀  █████▄▄██   ███    █▀   ▀███▀███▀  ████████▀
```

### a tiny, hackable, open-source coding agent CLI

[![CI](https://github.com/davebiagioni/clawd-coad/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/davebiagioni/clawd-coad/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.11%2B-3776AB?style=flat-square&logo=python&logoColor=white)
![LangGraph](https://img.shields.io/badge/langgraph-built--on-1C3A5E?style=flat-square)
![Providers](https://img.shields.io/badge/providers-OpenAI--compatible%20%7C%20Anthropic-FF6F61?style=flat-square)
![Local-first](https://img.shields.io/badge/local--first-Ollama%20default-25A162?style=flat-square)
![Status](https://img.shields.io/badge/status-learning%20project-FFB400?style=flat-square)
![LOC](https://img.shields.io/badge/code-~600%20LOC-9B59B6?style=flat-square)

![clawd in action](demo/demo.gif)

</div>

---

## what is this

**clawd** is a ~600-line coding agent in the spirit of Claude Code, Aider,
and Cursor — small enough to read in an afternoon, hackable enough to
actually learn from. Local models out of the box (Ollama default, no API
bill); swap to OpenAI / Anthropic / OpenRouter / vLLM by editing a
`.env` line.

Built for **fun and learning**, not production.

```
                                   ╭──────────╮
   you ──── prompt ────▶ TUI ────▶ │  agent   │ ────▶ tools (fs/shell/web)
                         ▲         ╰────┬─────╯              │
                         │              │                    │
                         │              ▼                    ▼
                         │        ┌──────────┐         ┌──────────────┐
                         │        │   LLM    │         │ git worktree │
                         │        │ (any)    │         │ (the jail)   │
                         │        └──────────┘         └──────────────┘
                         │              │
                         └──── stream ──┘
```

## quickstart

```bash
# 1. clone & install
git clone https://github.com/davebiagioni/clawd-coad.git && cd clawd-coad
uv sync
```

**2. pick a model — local *or* hosted, both equally supported:**

```bash
# 2a. local with ollama (no API key, no bill)
ollama pull qwen2.5-coder:7b
ollama serve  # in another terminal
# (no .env needed — these are the defaults)
```

```bash
# 2b. hosted with groq (free tier, fast, OpenAI-compatible)
cat > .env <<EOF
CLAWD_BASE_URL=https://api.groq.com/openai/v1
CLAWD_MODEL=llama-3.3-70b-versatile
CLAWD_API_KEY=gsk-...   # https://console.groq.com/keys
EOF
```

See [providers, picked from a hat](#providers-picked-from-a-hat) below for
OpenAI / Anthropic / OpenRouter / vLLM snippets — same shape.

```bash
# 3. cd into ANY git repo you want clawd to work on
cd ~/your-project

# 4. go
uv run --project ~/path/to/clawd-coad clawd
```

That's it. Type at the prompt, watch it work, review with `/diff`.

## what a session looks like

```
clawd · openai · qwen2.5-coder:7b · clawd/default
worktree: /Users/you/.clawd/worktrees/default
type /help for commands

> add a docstring to every function in clawd/agent.py

→ read_file({'path': 'clawd/agent.py'})
→ edit_file({'path': 'clawd/agent.py', 'old': 'def make_session(...', ...})
done — added docstrings to make_session and the Session dataclass.

> /diff
diff --git a/clawd/agent.py b/clawd/agent.py
+    """Build an agent session bound to a per-thread git worktree."""
...
```

## features

| | |
|---|---|
| **agent loop**       | LangGraph `create_react_agent`, SQLite checkpointing, conversation resume |
| **provider-neutral** | any OpenAI-compatible endpoint (Ollama / vLLM / OpenRouter / Together / Groq / OpenAI) **plus** direct Anthropic API |
| **tools**            | `read_file`, `write_file`, `edit_file`, `glob_files`, `grep`, `bash`, `web_fetch` |
| **isolation**        | git worktree per session — agent edits land on a throwaway branch you `git diff` and `git merge` |
| **observability**    | optional [Langfuse](https://langfuse.com) tracing with cost-in-dollars and per-run tags |
| **TUI**              | streaming markdown via [Rich](https://rich.readthedocs.io), slash commands (`/help` `/clear` `/diff` `/cost`) |

## providers, picked from a hat

```bash
# local (default — no bill, no signup)
CLAWD_BASE_URL=http://localhost:11434/v1
CLAWD_MODEL=qwen2.5-coder:7b
CLAWD_API_KEY=ollama

# OpenAI
CLAWD_BASE_URL=https://api.openai.com/v1
CLAWD_MODEL=gpt-4o-mini
CLAWD_API_KEY=sk-...

# Anthropic
CLAWD_PROVIDER=anthropic
CLAWD_MODEL=claude-haiku-4-5-20251001
CLAWD_API_KEY=sk-ant-...

# OpenRouter (anything on the menu)
CLAWD_BASE_URL=https://openrouter.ai/api/v1
CLAWD_MODEL=meta-llama/llama-3.3-70b-instruct
CLAWD_API_KEY=sk-or-...
```

## learn how it works

`clawd` ships with a full set of docs that walk through every line of
the codebase — the design tradeoffs, what was deliberately left out,
and how to swap pieces.

→ **[start here: docs/README.md](docs/README.md)**

Nine short chapters, ordered to match how the code is laid out:

1. The design space — what coding agents are, how the popular ones differ
2. The agent loop — `clawd/agent.py`
3. Talking to a model — `clawd/llm.py`, `clawd/config.py`
4. The system prompt — `clawd/prompt.py`
5. Tools, part 1: filesystem — `clawd/tools/fs.py`
6. Tools, part 2: shell & web — `clawd/tools/shell.py`, `clawd/tools/web.py`
7. Worktrees & isolation — `clawd/worktree.py`
8. Observability — `clawd/tracing.py`, `clawd/pricing.py`
9. The TUI — `clawd/tui.py`

## philosophy

```
small over featureful
explicit over magical
provider-neutral over vendor-friendly
worktree over container
read the code, change the code
```

## status

Learning project, in active tinkering. APIs will move. Your worktrees
are safe; nothing else is. PRs welcome but the primary goal is *clarity*
— if a change makes the code harder to read for a learner, it probably
shouldn't land.

