import os
import re
import subprocess

import pytest

from clawd.worktree import (
    ensure_worktree,
    latest_session_id,
    list_session_ids,
    new_thread_id,
)


def test_creates_worktree_and_branch(git_repo, monkeypatch, tmp_path):
    worktree_root = tmp_path / "worktrees"
    monkeypatch.setattr("clawd.worktree.WORKTREE_ROOT", worktree_root)
    monkeypatch.chdir(git_repo)

    path, branch = ensure_worktree("test")

    assert path == worktree_root / "test"
    assert path.exists()
    assert branch == "clawd/test"
    # Worktree dirs have a .git file (not directory) pointing back to the main repo
    assert (path / ".git").exists()


def test_idempotent_on_resume(git_repo, monkeypatch, tmp_path):
    worktree_root = tmp_path / "worktrees"
    monkeypatch.setattr("clawd.worktree.WORKTREE_ROOT", worktree_root)
    monkeypatch.chdir(git_repo)

    p1, b1 = ensure_worktree("test")
    (p1 / "scratch.txt").write_text("preserved")

    p2, b2 = ensure_worktree("test")
    assert p1 == p2
    assert b1 == b2
    assert (p2 / "scratch.txt").read_text() == "preserved"


def test_autofixes_repo_with_no_commits(empty_git_repo, monkeypatch, tmp_path):
    worktree_root = tmp_path / "worktrees"
    monkeypatch.setattr("clawd.worktree.WORKTREE_ROOT", worktree_root)
    monkeypatch.chdir(empty_git_repo)

    path, _ = ensure_worktree("test")
    assert path.exists()
    log = subprocess.run(
        ["git", "log", "--oneline"],
        cwd=empty_git_repo,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert "clawd init" in log


def test_errors_outside_git_repo(tmp_path, monkeypatch):
    not_a_repo = tmp_path / "plain"
    not_a_repo.mkdir()
    monkeypatch.chdir(not_a_repo)
    with pytest.raises(RuntimeError, match="git repository"):
        ensure_worktree("test")


def test_new_thread_id_is_timestamp_shaped():
    assert re.fullmatch(r"\d{8}-\d{6}", new_thread_id())


def test_list_and_latest_session_ids(tmp_path, monkeypatch):
    worktree_root = tmp_path / "worktrees"
    monkeypatch.setattr("clawd.worktree.WORKTREE_ROOT", worktree_root)

    # Empty / missing root -> empty list, no latest.
    assert list_session_ids() == []
    assert latest_session_id() is None

    worktree_root.mkdir()
    older = worktree_root / "20260101-000000"
    newer = worktree_root / "20260201-000000"
    older.mkdir()
    newer.mkdir()
    # Force ordering by mtime regardless of creation timing.
    os.utime(older, (1_700_000_000, 1_700_000_000))
    os.utime(newer, (1_800_000_000, 1_800_000_000))
    # Stray file (not a dir) should be ignored.
    (worktree_root / "stray.txt").write_text("x")

    assert list_session_ids() == ["20260201-000000", "20260101-000000"]
    assert latest_session_id() == "20260201-000000"
