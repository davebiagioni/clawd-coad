# clawd

A small, hackable open-source coding agent CLI built on LangGraph. Read in an
afternoon, fork it, swap a piece. ~600 LOC target.

## Why this matters when working on the code

- **Clarity > features.** If a change makes the code harder to read for a
  learner, it probably shouldn't land. Prefer deleting code over adding it.
- **Provider neutrality is load-bearing.** Anything in `clawd/llm.py`,
  `clawd/config.py`, or the docs needs to treat OpenAI-compatible (the
  default) and Anthropic on equal footing. Don't default to one vendor or
  hide a provider behind an "advanced" section.
- **Tool-jail is the trust boundary.** Every filesystem-touching tool in
  `clawd/tools/` routes paths through `_jail(jail_root, path)`. Don't add a
  tool that takes a model-supplied path and skips the jail.

## Workflow

- Install / sync: `uv sync` (pyproject.toml has both runtime and dev deps).
- Tests: `uv run pytest`.
- Lint / format: ruff via pre-commit (`pre-commit install` once, then it runs
  on commit). `uv run ruff check` to lint by hand.
- Docs live under `docs/`: `concepts/` for chapter-style explanation,
  `how-to/` for recipes, `reference/` for lookup. Keep individual files
  short; cross-link rather than nest.

## Voice

- Top-level `README.md`: lowercase section headings, terse, philosophical.
- `docs/concepts/*`: sentence-case headings, longer, "we" voice, ends each
  chapter with a small exercise.
- `docs/how-to/*` and `docs/reference/*`: sentence-case headings, recipe
  form (numbered steps for how-tos), no editorializing.

## Out of scope

- Production hardening (auth, multi-user, rate limits).
- Auto-generated API docs — not a library.
- Anything that requires a containerized runtime by default. The optional
  Docker sandbox is documented in chapter 9; it's an alternative, not a
  prerequisite.
