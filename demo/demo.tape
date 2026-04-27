# clawd demo recording — run from the project root: `vhs demo/demo.tape`
#
# requires:
#   - vhs           (https://github.com/charmbracelet/vhs)
#   - ffmpeg, ttyd  (vhs runtime deps)
#   - uv            (used to launch clawd and drop pytest into the demo venv)
#   - a configured .env at the project root (provider, model, api key)
#
# clawd itself is launched via `uv run --project "$CLAWD_REPO" clawd`,
# so no host-side `uv tool install` is required — the recording is
# self-contained as long as you run it from the repo root.
#
# the recording is fully isolated: it uses a throwaway git repo for
# cwd, a fresh worktree root, and a fresh sqlite checkpoint, so prior
# clawd sessions don't leak conversation history into the demo.
#
# the Sleep after each user turn is sized for a fast hosted model
# (groq, openai — 3–10s for chat turns, ~30s for the multi-tool bug
# hunt). bump them all if you're running a slow local 7B on ollama.

Output demo/demo.gif

Set Shell    "bash"
Set FontSize 14
Set Width    1200
Set Height   720
Set Padding  20
Set Theme    "Catppuccin Mocha"
Set TypingSpeed 40ms

Hide
# clean prompt — strip whatever PROMPT_COMMAND/PS1 .bashrc set up
Type "unset PROMPT_COMMAND && PS1='$ ' && clear"
Enter
Sleep 300ms

# load provider config from the project .env (groq / openai / anthropic / …)
Type "set -a && . ./.env && set +a"
Enter
Sleep 300ms

# isolate this run: fresh worktree + fresh checkpoint db so no replay
Type "export CLAWD_WORKTREE_ROOT=$(mktemp -d) CLAWD_DB_PATH=$(mktemp -d)/sessions.db"
Enter
Sleep 300ms

# throwaway repo with a buggy `subtract` and a failing test for it
Type "cd $(mktemp -d) && git init -q"
Enter
Sleep 300ms

Type "printf 'def add(a, b):\n    return a + b\n\ndef subtract(a, b):\n    return a + b  # bug\n\ndef multiply(a, b):\n    return a * b\n' > calc.py"
Enter
Sleep 300ms

Type "printf 'from calc import add, subtract, multiply\n\ndef test_add():       assert add(2, 3) == 5\ndef test_subtract():  assert subtract(5, 3) == 2\ndef test_multiply():  assert multiply(4, 3) == 12\n' > test_calc.py"
Enter
Sleep 300ms

Type "git add . && git -c user.email=demo@x -c user.name=demo commit -q -m init"
Enter
Sleep 500ms

# venv + pytest so the agent's `pytest` invocation Just Works. activate
# before launching clawd so the venv's PATH is inherited by the bash tool.
# re-set PS1 — `source .venv/bin/activate` clobbers it with the venv prefix.
Type "uv venv -q && source .venv/bin/activate && uv pip install -q pytest && PS1='$ ' && clear"
Enter
Sleep 2s
Show

# --- the demo itself ---
# show the failure on screen first, so the bug-fix request has visible context
# (and so a smaller hosted model doesn't wander off into unittest-land).
Type "pytest -q"
Enter
Sleep 3s

Type "clawd"
Enter
Sleep 3s

Type "hello"
Enter
Sleep 6s

Type "who are you?"
Enter
Sleep 10s

Type "pytest is failing on test_subtract. find the bug in calc.py and fix it."
Enter
Sleep 45s

Type "/diff"
Enter
Sleep 4s

Type "/exit"
Enter
Sleep 1s
