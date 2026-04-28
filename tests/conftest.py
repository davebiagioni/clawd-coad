import subprocess
from pathlib import Path

import pytest


def _git(*args: str, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


@pytest.fixture(autouse=True)
def _isolate_git_env(monkeypatch):
    """pre-commit (and some IDEs) set GIT_DIR / GIT_INDEX_FILE in the
    environment, which leak into subprocess git calls and break tests that
    create their own repos. Clear them for every test."""
    for var in ("GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE", "GIT_OBJECT_DIRECTORY"):
        monkeypatch.delenv(var, raising=False)


@pytest.fixture(autouse=True)
def _isolate_user_skills_dir(tmp_path, monkeypatch):
    """Point USER_SKILLS_DIR at an empty tmp dir so tests don't see the
    developer's real ~/.clawd/skills/."""
    from clawd import skills

    monkeypatch.setattr(skills, "USER_SKILLS_DIR", tmp_path / "_user_skills_isolation")


@pytest.fixture(autouse=True)
def _isolate_project_root(tmp_path, monkeypatch):
    """Point _project_root() at an empty tmp dir so tests don't accidentally
    pick up <repo>/.clawd/skills/ from the developer's working tree. Tests
    that need a specific project root override this with their own monkeypatch."""
    from clawd import skills

    monkeypatch.setattr(skills, "_project_root", lambda: tmp_path / "_project_root_isolation")


@pytest.fixture
def jail(tmp_path: Path) -> Path:
    """A directory to use as a tool jail root."""
    j = tmp_path / "jail"
    j.mkdir()
    return j


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """A fresh git repo with one commit and local user.email/name configured."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git("init", "-q", cwd=repo)
    _git("config", "user.email", "test@test", cwd=repo)
    _git("config", "user.name", "test", cwd=repo)
    _git("commit", "-q", "--allow-empty", "-m", "init", cwd=repo)
    return repo


@pytest.fixture
def empty_git_repo(tmp_path: Path) -> Path:
    """A git repo with NO commits but user.email/name set."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git("init", "-q", cwd=repo)
    _git("config", "user.email", "test@test", cwd=repo)
    _git("config", "user.name", "test", cwd=repo)
    return repo
