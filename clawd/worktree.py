import os
import subprocess
from datetime import datetime
from pathlib import Path

WORKTREE_ROOT = Path(os.environ.get("CLAWD_WORKTREE_ROOT", "~/.clawd/worktrees")).expanduser()


def new_thread_id() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def list_session_ids() -> list[str]:
    """Existing session ids on disk, most recently modified first."""
    if not WORKTREE_ROOT.exists():
        return []
    dirs = [p for p in WORKTREE_ROOT.iterdir() if p.is_dir()]
    dirs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return [p.name for p in dirs]


def latest_session_id() -> str | None:
    ids = list_session_ids()
    return ids[0] if ids else None


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
        if "dubious ownership" in str(e):
            raise RuntimeError(
                "git refuses to operate on this repo because its on-disk owner doesn't "
                "match the current user. This usually means you're running clawd inside "
                "a container against a host-mounted repo. Add the path to git's safe list:\n"
                "    git config --global --add safe.directory <path>\n"
                "or rebuild the container image (the Dockerfile already does this for "
                "/workspace; if you've changed the mount point, update it there)."
            ) from e
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
