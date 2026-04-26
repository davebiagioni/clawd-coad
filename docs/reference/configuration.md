# Configuration

Every clawd setting comes from environment variables, loaded by
`pydantic-settings` from `.env` and the process environment. The schemas
live in `clawd/config.py`. Two prefixes: `CLAWD_*` for the agent itself and
`LANGFUSE_*` for tracing.

Copy `.env.example` to `.env` and edit. Anything not set falls back to the
defaults below.

## CLAWD_PROVIDER

- **Default:** `openai`
- **Allowed:** `openai` | `anthropic`
- **Description:** Which client `clawd/llm.py` builds. `openai` uses
  `langchain-openai`'s `ChatOpenAI` (any OpenAI-compatible endpoint).
  `anthropic` uses `langchain-anthropic`'s `ChatAnthropic` against the
  Anthropic API directly.
- **Example:** `CLAWD_PROVIDER=anthropic`

## CLAWD_MODEL

- **Default:** `qwen2.5-coder:7b`
- **Description:** Model name passed straight to the chat client. Format
  depends on the provider — Ollama uses `name:tag`, OpenRouter uses
  `vendor/model`, Anthropic uses dated IDs like `claude-haiku-4-5-20251001`.
- **Example:** `CLAWD_MODEL=claude-sonnet-4-6`

## CLAWD_BASE_URL

- **Default:** `http://localhost:11434/v1`
- **Used when:** `CLAWD_PROVIDER=openai`. Ignored for `anthropic`.
- **Description:** The OpenAI-compatible endpoint. The default points at a
  local Ollama. Other examples:
  - OpenAI: `https://api.openai.com/v1`
  - OpenRouter: `https://openrouter.ai/api/v1`
  - Together: `https://api.together.xyz/v1`
  - Groq: `https://api.groq.com/openai/v1`
  - vLLM / llama.cpp: whatever you've configured locally
- **Example:** `CLAWD_BASE_URL=https://openrouter.ai/api/v1`

## CLAWD_API_KEY

- **Default:** `ollama` (a placeholder; Ollama ignores the key)
- **Description:** API key for the chosen provider. For local Ollama any
  non-empty string works; for cloud providers, a real key.
- **Example:** `CLAWD_API_KEY=sk-or-...`

## CLAWD_DB_PATH

- **Default:** `~/.clawd/sessions.db`
- **Description:** Path to the sqlite file `AsyncSqliteSaver` uses to
  checkpoint conversations. `~` is expanded; the parent directory is
  created on first run. Delete the file to wipe all sessions.
- **Example:** `CLAWD_DB_PATH=/tmp/clawd-test.db`

## LANGFUSE_PUBLIC_KEY

- **Default:** unset
- **Description:** Public key for [Langfuse](https://langfuse.com) tracing.
  Tracing is enabled only if both `LANGFUSE_PUBLIC_KEY` and
  `LANGFUSE_SECRET_KEY` are set.
- **Example:** `LANGFUSE_PUBLIC_KEY=pk-lf-...`

## LANGFUSE_SECRET_KEY

- **Default:** unset
- **Description:** Secret key for Langfuse. See above.
- **Example:** `LANGFUSE_SECRET_KEY=sk-lf-...`

## LANGFUSE_HOST

- **Default:** unset (the Langfuse SDK falls back to
  `https://cloud.langfuse.com`)
- **Description:** Langfuse server URL. Set this for self-hosted Langfuse.
- **Example:** `LANGFUSE_HOST=http://localhost:3000`

## What's not configurable (yet)

These are baked into the source today; if you want them tunable, that's a
small patch:

- The system prompt — `clawd/prompt.py`.
- Default thread ID — `"default"` in `clawd/tui.py`.
- Worktree root — `~/.clawd/worktrees` in `clawd/worktree.py`.
- LLM temperature — `0` in `clawd/llm.py`.
- `bash` tool's default timeout (30s); `web_fetch`'s 5 MB download cap and
  10k-char output truncation.
