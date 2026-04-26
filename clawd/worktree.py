import os
import subprocess
from pathlib import Path

WORKTREE_ROOT = Path(os.environ.get("CLAWD_WORKTREE_ROOT", "~/.clawd/worktrees")).expanduser()


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
