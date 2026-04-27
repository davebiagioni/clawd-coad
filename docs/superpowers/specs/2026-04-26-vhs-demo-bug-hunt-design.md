# VHS demo: bug-hunt arc

Status: design approved 2026-04-26

## Why

The current `demo/demo.tape` is functional but minimal: it boots clawd, asks
for a docstring on `add()`, shows `/diff`, exits. It demonstrates that the
agent edits files, but doesn't show the rest of what makes clawd interesting
(reading, shelling out, multi-tool reasoning), and the opening turns don't
land with any personality.

The new demo replaces the single-turn task with a five-turn story: a friendly
greeting, a self-introduction, then a bug-hunt where the agent runs failing
tests, locates the bug, fixes it, and re-runs to green. Same isolation shell,
new content.

## Story arc

```
hello
  → friendly response
who are you?
  → agent self-introduces (whatever the model says — not gated on identity)
the tests are failing. find the bug and fix it.
  → pytest (failure) → read calc.py → edit subtract → pytest (green)
/diff
  → show the one-line fix
/exit
```

Five user turns, ~75–90s total runtime on a fast hosted model.

## Setup (hidden)

Same isolation pattern as the current tape: a throwaway `mktemp -d` repo,
fresh `CLAWD_WORKTREE_ROOT`, fresh `CLAWD_DB_PATH`, sourced `.env`. Two
content changes:

1. `uv tool install pytest -q` — idempotent, ensures `pytest` is on PATH so
   the agent's natural `pytest` invocation works without uv-specific phrasing
   in the user prompts.
2. Two files instead of one:

   ```python
   # calc.py
   def add(a, b):
       return a + b

   def subtract(a, b):
       return a + b  # bug: should be a - b

   def multiply(a, b):
       return a * b
   ```

   ```python
   # test_calc.py
   from calc import add, subtract, multiply

   def test_add():       assert add(2, 3) == 5
   def test_subtract():  assert subtract(5, 3) == 2
   def test_multiply():  assert multiply(4, 3) == 12
   ```

The `subtract` bug returns `a + b` instead of `a - b`. Subtle enough to
require reading the file (the function name and the operator disagree), and
the punchline reads cleanly in the final `/diff`.

## Visible script

| turn | input | sleep after |
|------|-------|-------------|
| boot | `clawd` | 3s |
| 1 | `hello` | 6s |
| 2 | `who are you?` | 10s |
| 3 | `the tests are failing. find the bug and fix it.` | 30s |
| 4 | `/diff` | 4s |
| 5 | `/exit` | 1s |

Sleeps are sized for a fast hosted model (groq, openai). The existing tape
comment about bumping sleeps for slow local models still applies and will be
preserved verbatim.

The 30s sleep on turn 3 covers ~4 tool calls (pytest, read, edit, pytest).
First real recording will tell us if it needs adjustment.

## What stays unchanged

- Tape framing: `Output demo/demo.gif`, theme, dimensions, font, typing speed.
- Shell setup: PROMPT_COMMAND/PS1 reset, `.env` sourcing, tempdir env vars.
- Repo init: `git init`, initial commit.
- Closing beats: `/diff` then `/exit`.
- Header comment block (with the slow-model sleep advice).

## Risks

- **Identity drift on turn 2.** Whatever the model says is fine — the demo
  isn't gated on the model self-identifying as clawd. Accepted per design
  conversation.
- **Tool-call count variance on turn 3.** A chatty model may re-read or
  double-check; a terse one may skip the second pytest. 30s is a reasonable
  default; tune after first recording.
- **`uv tool install` first-run cost.** First time it runs on a machine, it
  downloads pytest. The hidden phase doesn't time-budget this; if it stalls,
  the visible demo just starts a few seconds later. Not a blocker.

## Out of scope

- Changing the demo's recording harness (vhs flags, output format, theme).
- Adding new slash commands or agent tools to make the demo work.
- Localization / multiple demo variants (one canonical demo is enough).
