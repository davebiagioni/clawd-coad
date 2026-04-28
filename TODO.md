# todo

## parallel subagents

let the agent dispatch independent tasks to sub-instances and merge results.

- new tool `dispatch(task: str, tools?: list[str]) -> str` in `clawd/tools/dispatch.py`
- builds a fresh `create_react_agent` with the same llm + jail_root, no checkpointer, a stripped system prompt ("you are a subagent, return a final answer")
- parent calls multiple `dispatch` in one turn → langgraph runs the tool calls concurrently → `asyncio.gather` falls out for free
- open questions: read-only subagent? own branch off the worktree? recursion depth cap? tool allowlist per-call?
- prompt.py: add a short "use dispatch for independent subtasks" section
- size: ~40–60 lines + a test

## claude-like skills

discoverable, on-demand instruction bundles the agent loads by name.

- skills = markdown files with yaml frontmatter (`name`, `description`, optional `when_to_use`)
- discovery roots: `~/.clawd/skills/` and `<jail_root>/.clawd/skills/`
- new module `clawd/skills.py`: parse frontmatter, return `{name: (description, path)}`
- two new tools in `clawd/tools/skills.py`: `list_skills()` and `load_skill(name)`
- `prompt.py`: inject the name+description list at session start so the model knows what's available
- size: ~50–80 lines + tests for discovery + a sample skill in `docs/`

## verify docker sandboxing

audit, not feature work. the goal is a checked claim, not new code.

- read `Dockerfile` + `scripts/clawd-sandbox` end to end, confirm:
  - host fs outside `$PWD` not visible (only `-v $PWD:/workspace`)
  - host network rewriting (`localhost` → `host.docker.internal`) is sound
  - no host secrets leak in via build context
  - jail still holds inside the container (paths under `/workspace`)
- write `docs/how-to/verify-the-sandbox.md`: reproducible probe commands the reader can run (`bash` tool tries to read `/etc/shadow`, `~`, `/host`, etc.) and expected outcomes
- optional: `tests/test_sandbox.py` that skips unless `docker` is on PATH
- size: docs-heavy, near-zero code

## `!` shell prefix in the TUI

let the user run a shell command directly from the prompt without going through the model.

- detect a `!` prefix on submitted input in `clawd/tui/app.py` (or wherever input is handled)
- if present, run the rest of the line via the existing `bash` tool / a thin wrapper so the worktree jail still applies
- render output inline in the same panel style as a model-driven `bash` call
- no LLM roundtrip; nothing is appended to the conversation history (or — open question — append as a synthetic user message so the model sees the result on the next turn?)
- mirrors claude code's `!` and shells like `:!cmd` — familiar muscle memory
- size: ~20–40 lines, mostly UI

## local tracing of llm completions + tool use

no-cloud alternative to langfuse — same shape, file-backed.

- new `LocalTraceHandler(BaseCallbackHandler)` in `clawd/tracing.py` (or split into `tracing/local.py` + `tracing/langfuse.py`)
- writes one jsonl line per llm call (model, prompt, response, usage, latency) and per tool call (name, args, result, duration) to `~/.clawd/traces/<thread_id>.jsonl`
- enabled by default; opt out with `CLAWD_TRACE=0`. langfuse handler stacks on top when configured
- viewer: `clawd traces` subcommand (or `/traces` slash command) — tails the file, pretty-prints, supports `--session ID`
- pricing.py already knows how to cost a usage dict — reuse it for a `total $` summary
- size: ~80–120 lines + a test
