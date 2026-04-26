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
