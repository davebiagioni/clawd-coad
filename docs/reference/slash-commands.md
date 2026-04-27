# Slash commands

Anything typed at the `>` prompt that starts with `/` is a slash command,
not a turn. Defined in the `COMMANDS` table in `clawd/tui.py`. Anything
else is sent to the agent as a normal user message.

## /help

Print the list of available commands.

## /clear

Reset the current conversation. Calls `checkpointer.adelete_thread(thread_id)`
on the sqlite saver — the next prompt starts a fresh history. The worktree
and its branch are not touched.

## /diff

Show the unstaged diff of the worktree. Equivalent to
`git -C <worktree> diff`. Empty output prints `no changes`.

## /sessions

List the saved sessions on disk (one entry per worktree directory in
`~/.clawd/worktrees/`), most recent first. The current session is marked
with a `*`. Resume one by quitting and running `clawd -r <id>` (or
`clawd -c` for the most recent).

## /cost

Inspect or set Langfuse pricing for the current model.

- `/cost` — print whether the current `CLAWD_MODEL` has a pricing entry
  registered in Langfuse, and if so its input/output rates per 1M tokens.
- `/cost set <input_per_1m> <output_per_1m>` — register pricing in USD
  per 1M tokens. Use `0 0` for free models (so traces still show usage).

Requires `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` to be set;
otherwise prints a nudge and returns.

## Exiting

Not a slash command, but worth noting: `/exit`, `/quit`, `/q`, plain
`exit`/`quit`, Ctrl+D, and Ctrl+C all leave the REPL. Ctrl+C *during* a
turn interrupts the in-flight request and drops you back at the prompt.
