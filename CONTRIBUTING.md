# Contributing

`clawd` is a learning project, primarily for reading and tinkering. PRs are
welcome but the bar is *clarity*: if a change makes the codebase harder to
read for someone learning how a coding agent works, it probably shouldn't
land.

## Dev setup

```bash
uv sync                    # install runtime + dev deps
pre-commit install         # ruff + pytest hooks on commit
```

`uv` is required; we use `[dependency-groups]` rather than the `[project]
optional-dependencies` shape, which `pip` doesn't read.

## The check loop

```bash
uv run pytest              # full test suite
uv run pytest tests/test_foo.py -q   # single file
uv run ruff check          # lint
uv run ruff format         # autoformat
```

Pre-commit runs ruff and the pytest hook on every commit; you don't need to
remember to run them by hand once `pre-commit install` is done.

## What changes are welcome

- **Yes:** clarity improvements, dead-code removal, better names, sharper
  docstrings, new how-to / reference docs that close a real gap, tests for
  things that don't have them yet, bug fixes with a regression test.
- **Yes, with discussion first** (open an issue): new tools, new providers
  (anything OpenAI-compatible should already work; anything else is a real
  branch), changes to the worktree-jail invariant, anything that grows the
  LOC count materially.
- **Probably not:** features that aren't useful for *learning* how a coding
  agent works, abstractions added "for future flexibility", configuration
  knobs nobody asked for.

## Provider neutrality

Anywhere a chapter or doc mentions providers, OpenAI-compatible (the default,
local Ollama out of the box) and Anthropic should be presented on equal
footing. Don't make one the canonical example with the other relegated to a
footnote.

## Tests

There's a `jail` fixture in `tests/conftest.py` that gives you a tmp dir to
use as a tool jail root; mirror an existing test in `tests/test_fs_tools.py`
or `tests/test_shell_tools.py` for new tools. Async tests work via
`pytest-asyncio` (`asyncio_mode = "auto"` is set in `pyproject.toml`).

## Filing issues

Keep them small: what you tried, what happened, what you expected. Logs from
`/cost`-enabled Langfuse traces help if the bug is in the agent loop.
