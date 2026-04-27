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
# the visible command is just `clawd` — we put $CLAWD_REPO/.venv/bin on
# PATH in the hidden setup so the recording matches what a local user
# sees after `uv tool install clawd` (or running from a synced repo).
#
# the recording is fully isolated: throwaway git repo for cwd, fresh
# worktree root, fresh sqlite checkpoint, so prior clawd sessions
# don't leak conversation history into the demo.
#
# Sleep after each user turn is sized for a fast hosted model
# (groq, openai). bump them all if you're on a slow local 7B.

Output demo/demo.gif

Set Shell    "bash"
Set FontSize 14
Set Width    1200
Set Height   720
Set Padding  20
Set Theme    "Catppuccin Mocha"
Set TypingSpeed 40ms

Hide
Type "unset PROMPT_COMMAND && PS1='$ ' && clear"
Enter
Sleep 300ms

Type "export CLAWD_REPO=$PWD"
Enter
Sleep 300ms

Type "set -a && . ./.env && set +a"
Enter
Sleep 300ms

# silence langfuse for the recording — empty values override the .env-loaded
# keys, so clawd skips the callback handler and the "no pricing" warning.
Type "export LANGFUSE_PUBLIC_KEY= LANGFUSE_SECRET_KEY="
Enter
Sleep 300ms

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
Sleep 5s
Type `export PATH="$CLAWD_REPO/.venv/bin:$PATH"`
Enter
Sleep 300ms
Type "clear"
Enter
Sleep 500ms
Show

# --- the demo itself ---
# show the failure on screen first, so the bug-fix request has visible context
# (and so a smaller hosted model doesn't wander off into unittest-land).
Type "pytest -q"
Enter
Sleep 3s

Type "clawd"
Enter
Sleep 4s

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
