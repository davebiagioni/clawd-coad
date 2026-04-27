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
# (groq, openai — 3–10s for chat turns, ~45s for the multi-tool bug
# hunt). bump them all if you're running a slow local 7B on ollama.

Output demo/demo.gif

Set Shell    "bash"
Set FontSize 14
Set Width    1200
Set Height   720
Set Padding  20
Set Theme    { "name": "Clawd", "background": "#0d0d0d", "foreground": "#ece6dc", "cursor": "#d97757", "selection": "#3a2a22", "black": "#1a1a1a", "red": "#e06c4a", "green": "#a3b86c", "yellow": "#e5b769", "blue": "#7aa2c7", "magenta": "#c89bcc", "cyan": "#7ec4b8", "white": "#ece6dc", "brightBlack": "#5c5c5c", "brightRed": "#ff8a5c", "brightGreen": "#c1d684", "brightYellow": "#ffd180", "brightBlue": "#9ec0e0", "brightMagenta": "#dfb4e3", "brightCyan": "#a0dccf", "brightWhite": "#ffffff" }
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
Type "clawd"
Enter
Sleep 3s

Type "who are you?"
Enter
Sleep 3s

Type "run pytest. any bugs?" 
Enter
Sleep 7s

Type "fix the bug and run pytest again"
Enter
Sleep 7s

Type "thanks clawd, you're the best"
Enter
Sleep 3s

Type "/exit"
Enter
Sleep 1s
