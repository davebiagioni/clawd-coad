from pathlib import Path

import pytest

from clawd import skills
from clawd.skills import Skill, discover_skills


def _write_skill(dir: Path, filename: str, frontmatter: str, body: str = "") -> Path:
    dir.mkdir(parents=True, exist_ok=True)
    p = dir / filename
    p.write_text(f"---\n{frontmatter}---\n{body}")
    return p


def _set_project_root(monkeypatch, root: Path) -> None:
    monkeypatch.setattr(skills, "_project_root", lambda: root)


def test_no_skills_dir_returns_empty():
    assert discover_skills() == {}


def test_parses_project_skill(jail, monkeypatch):
    _set_project_root(monkeypatch, jail)
    _write_skill(
        jail / ".clawd/skills",
        "tdd.md",
        "name: tdd\ndescription: Use TDD when adding features\n",
        "# Test-Driven Development\nWrite the test first.",
    )

    found = discover_skills()

    assert set(found) == {"tdd"}
    skill = found["tdd"]
    assert skill.name == "tdd"
    assert skill.description == "Use TDD when adding features"
    assert "Write the test first." in skill.body


def test_skipped_when_frontmatter_missing(jail, monkeypatch):
    _set_project_root(monkeypatch, jail)
    p = jail / ".clawd/skills" / "no-front.md"
    p.parent.mkdir(parents=True)
    p.write_text("just a body, no frontmatter\n")

    assert discover_skills() == {}


def test_skipped_when_name_missing(jail, monkeypatch):
    _set_project_root(monkeypatch, jail)
    _write_skill(
        jail / ".clawd/skills",
        "broken.md",
        "description: no name field\n",
    )
    assert discover_skills() == {}


def test_skipped_when_yaml_invalid(jail, monkeypatch):
    _set_project_root(monkeypatch, jail)
    p = jail / ".clawd/skills" / "broken.md"
    p.parent.mkdir(parents=True)
    p.write_text("---\nname: [unterminated\n---\nbody\n")

    assert discover_skills() == {}


def test_user_skills_picked_up(tmp_path, monkeypatch):
    user_dir = tmp_path / "user_skills"
    monkeypatch.setattr(skills, "USER_SKILLS_DIR", user_dir)
    _write_skill(user_dir, "global.md", "name: global\ndescription: user-wide skill\n", "body")

    found = discover_skills()

    assert set(found) == {"global"}


def test_project_skill_overrides_user_skill(jail, tmp_path, monkeypatch):
    _set_project_root(monkeypatch, jail)
    user_dir = tmp_path / "user_skills"
    monkeypatch.setattr(skills, "USER_SKILLS_DIR", user_dir)
    _write_skill(user_dir, "x.md", "name: x\ndescription: from user\n", "user body")
    _write_skill(
        jail / ".clawd/skills", "x.md", "name: x\ndescription: from project\n", "proj body"
    )

    found = discover_skills()

    assert found["x"].description == "from project"
    assert found["x"].body.strip() == "proj body"


def test_skill_dataclass_is_frozen():
    import dataclasses

    s = Skill(name="x", description="d", body="b", path=Path("/tmp/x.md"))
    with pytest.raises(dataclasses.FrozenInstanceError):
        s.name = "y"  # type: ignore[misc]
