from clawd import skills
from clawd.prompt import build_system_prompt


def test_includes_jail_root_and_branch(tmp_path):
    p = build_system_prompt(tmp_path, "clawd/feature-x")
    assert str(tmp_path) in p
    assert "clawd/feature-x" in p


def test_includes_baseline_identity(tmp_path):
    p = build_system_prompt(tmp_path, "clawd/test")
    assert "clawd" in p.lower()
    assert "tool" in p.lower()


def test_no_claude_md_no_project_context_section(tmp_path):
    p = build_system_prompt(tmp_path, "clawd/test")
    assert "Project context" not in p


def test_appends_claude_md_when_present(tmp_path):
    (tmp_path / "CLAUDE.md").write_text("Use tabs not spaces.")
    p = build_system_prompt(tmp_path, "clawd/test")
    assert "Project context" in p
    assert "Use tabs not spaces." in p


def test_no_skills_section_when_none_installed(tmp_path):
    p = build_system_prompt(tmp_path, "clawd/test")
    assert "Skills available" not in p


def test_skills_section_lists_name_and_description(tmp_path, monkeypatch):
    monkeypatch.setattr(skills, "_project_root", lambda: tmp_path)
    skills_dir = tmp_path / ".clawd/skills"
    skills_dir.mkdir(parents=True)
    (skills_dir / "tdd.md").write_text(
        "---\nname: tdd\ndescription: Use when writing features\n---\nbody"
    )

    p = build_system_prompt(tmp_path, "clawd/test")

    assert "Skills available" in p
    assert "load_skill" in p
    assert "tdd" in p
    assert "Use when writing features" in p
