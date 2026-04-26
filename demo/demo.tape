# clawd demo recording — run from the project root: `vhs demo/demo.tape`
#
# requires:
#   - vhs           (https://github.com/charmbracelet/vhs)
#   - ffmpeg, ttyd  (vhs runtime deps)
#   - a configured .env at the project root (provider, model, api key)
#   - clawd on PATH (`uv tool install --editable .`) — or replace
#     `clawd` below with the full `uv run --project ...` invocation
#
# the recording is fully isolated: it uses a throwaway git repo for
# cwd, a fresh worktree root, and a fresh sqlite checkpoint, so prior
# clawd sessions don't leak conversation history into the demo.
#
# the Sleep after the prompt is sized for a fast hosted model (groq,
# openai — 3–5s). bump it to 20–30s for a local 7B on ollama.

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

# throwaway repo with a tiny file to edit, so /diff has something real
Type "cd $(mktemp -d) && git init -q && printf 'def add(a, b):\n    return a + b\n' > calc.py && git add . && git -c user.email=demo@x -c user.name=demo commit -q -m init && clear"
Enter
Sleep 1s
Show

# --- the demo itself ---
Type "clawd"
Enter
Sleep 3s

Type "add a docstring to add() in calc.py"
Enter
Sleep 10s

Type "/diff"
Enter
Sleep 4s

Type "/exit"
Enter
Sleep 1s
