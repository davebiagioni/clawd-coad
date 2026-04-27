# Chapter 6: Worktrees & isolation

> **Code for this chapter:** `clawd/worktree.py` (55 lines),
> `tests/test_worktree.py`

A coding agent that can edit files and run shell commands needs *some*
isolation story. The options are roughly:

- **None.** Trust the user to review every edit live. Aider's default.
  Works fine for solo dev work; terrifying for an agent that runs many
  turns unattended.
- **Filesystem jail.** Path-restrict every file operation to a
  directory. `clawd` does this for *editing* (chapter 4) but `bash`
  bypasses it.
- **Container.** Docker per session. OpenHands. Strong isolation, real
  cost (Docker on the user's laptop, container start-up time, an extra
  layer of indirection for everything).
- **VM / firecracker.** Replit-style. Strongest isolation, biggest
  ops surface.
- **Git worktree.** A throwaway sibling working copy on a throwaway
  branch. Edits land in a branch the user reviews and merges (or
  discards). Cheap, recoverable, no extra dependencies.

`clawd` picks the worktree because it's the laptop-friendly option that
gives you "git diff before merging" for free.

## What a worktree actually is

A git **worktree** is a second working directory backed by the same git
repository. Run `git worktree add ../foo somebranch` and you get a full
checkout of `somebranch` in `../foo`, sharing all the git internals with
the original repo. Commits made in either directory are visible to both.

For our purposes:

- The user runs `clawd` from their main repo.
- `clawd` creates a worktree at `~/.clawd/worktrees/<thread_id>` on a
  branch `clawd/<thread_id>`, branched off the user's current `HEAD`.
- All agent edits happen in that worktree.
- The user reviews with `git -C <worktree> diff`, then merges with
  `git merge clawd/<thread_id>` from their main repo.

The agent doesn't know about any of this — it just sees a directory it
can edit. The git layering is transparent.

## `clawd/worktree.py`

```python
import subprocess
from pathlib import Path

WORKTREE_ROOT = Path("~/.clawd/worktrees").expanduser()


def _git(*args: str, cwd: Path | None = None) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} failed: {result.stderr.strip() or result.stdout.strip()}"
        )
    return result.stdout.strip()


def ensure_worktree(thread_id: str) -> tuple[Path, str]:
    """Create (or resume) a git worktree for this thread.

    Returns (path, branch). The worktree lives at ~/.clawd/worktrees/<thread_id>
    on a branch named clawd/<thread_id>, branched off whatever HEAD is when the
    worktree is first created.
    """
    try:
        _git("rev-parse", "--git-dir")
    except RuntimeError as e:
        raise RuntimeError(
            "clawd requires a git repository. cd into one or run `git init` first."
        ) from e

    try:
        _git("rev-parse", "HEAD")
    except RuntimeError:
        _git("commit", "--allow-empty", "-m", "clawd init")

    branch = f"clawd/{thread_id}"
    path = WORKTREE_ROOT / thread_id

    _git("worktree", "prune")

    if path.exists():
        return path, branch

    path.parent.mkdir(parents=True, exist_ok=True)

    if _git("branch", "--list", branch):
        _git("worktree", "add", str(path), branch)
    else:
        _git("worktree", "add", "-b", branch, str(path), "HEAD")

    return path, branch
```

55 lines, three behaviors worth pulling out:

### 1. The "no commits yet" edge case

```python
try:
    _git("rev-parse", "HEAD")
except RuntimeError:
    _git("commit", "--allow-empty", "-m", "clawd init")
```

`git worktree add` requires a commit to branch from — a fresh `git
init`'d repo with no commits will refuse. Rather than make the user
remember this, we make an empty commit. Cost: one ugly commit in the
user's history (with the message `clawd init`). Benefit: `clawd` works
in any git repo, even a brand-new one.

This is the kind of thing every coding agent has to handle and it's
weirdly absent from most of them.

### 2. Resume vs fresh

```python
if path.exists():
    return path, branch
...
if _git("branch", "--list", branch):
    _git("worktree", "add", str(path), branch)
else:
    _git("worktree", "add", "-b", branch, str(path), "HEAD")
```

Three cases, in priority order:

1. **Worktree directory exists** → reuse it. The agent picks up where
   it left off, including uncommitted changes.
2. **Branch exists but no worktree** → recreate the worktree on the
   existing branch. Happens after a `worktree prune` (e.g., the
   directory was deleted manually).
3. **Neither exists** → create both, branched from current HEAD.

Together with LangGraph's checkpointer (which persists the
*conversation*), this gives a complete resume story: `clawd -r <id>`
(or `clawd -c` for the most recent) gets you back the same
conversation and the same files-on-disk. Run `clawd` with no flags
and you get a fresh session with a timestamp-shaped id.

### 3. `worktree prune`

```python
_git("worktree", "prune")
```

`prune` removes git's bookkeeping for worktree directories that have
been deleted on disk. Without it, `git worktree add` to a previously-used
path fails with "already registered." Cheap to run on every session
start; fixes the "I deleted the directory and now it won't recreate"
class of bug.

## Why this beats the alternatives

For a *laptop* coding agent, the worktree is hard to beat:

- **No new dependency.** Git is already there.
- **No daemon, no container runtime.** Just a directory.
- **Native review.** `git diff`, `git log`, `git checkout` — the user
  already knows these.
- **Native rollback.** `git reset --hard` discards everything. `git
  branch -D clawd/foo` makes it never have happened.
- **Native merge.** `git merge clawd/foo` integrates the work, with
  conflict resolution if something changed in the main branch
  meanwhile.
- **Composable with everything.** Branches push to remotes, get rebased,
  become PRs. The agent's output is just code, in a branch, like any
  other code in any other branch.

What it gives up:

- **No `bash` containment.** The model can `rm -rf ~` from inside the
  worktree. This is a *trust* concern, not a *blast radius* concern —
  the worktree itself is recoverable, the user's home directory isn't.
  See chapter 5 for the threat model.
- **Shared object database.** A worktree shares `.git/objects` with
  the main repo. A truly malicious agent could `git push` the user's
  unrelated branches somewhere. Not a realistic threat for current
  models, but worth knowing.

## Tests

`tests/test_worktree.py` covers:

- Fresh repo, no prior worktree → creates branch + directory.
- Existing worktree path → returns same `(path, branch)`.
- Existing branch but no worktree → reattaches.
- Empty repo (no commits) → makes the empty commit and proceeds.
- No git repo at all → raises with a helpful message.

The fixtures in `tests/conftest.py` are worth noting — `git_repo` and
`empty_git_repo` give you isolated repos per test, with `_isolate_git_env`
unsetting `GIT_DIR` etc. so leaked envvars from pre-commit don't taint
the subprocess git calls.

## What's missing

- **Cleanup.** Worktrees accumulate forever in `~/.clawd/worktrees/`.
  No automatic GC. A `clawd worktrees clean --older-than 7d` command
  would be a nice add.
- **Multiple agents per repo.** They share the branch namespace
  (`clawd/<thread_id>`). Two agents with the same `thread_id` would
  collide. Trivially fixed by including a hostname or random suffix.
- **Branch base selection.** Always branched from `HEAD`. Sometimes
  you want to branch from `main` regardless of where the user's HEAD
  is — easy config.

## Exercise

Add a `clawd merge` CLI command that runs `git merge clawd/<thread_id>
--no-ff` from the user's main repo. Should it auto-delete the worktree
on success? What happens on conflict? Should it prompt the user, or
leave them in the standard `git mergetool` flow?

This is mostly UX design — the git plumbing is one shell command. The
interesting part is deciding what's friendly vs. what's surprising.
