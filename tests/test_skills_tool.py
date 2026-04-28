from clawd.tools.skills import make_skills_tool


def _write(jail, name, description, body):
    d = jail / ".clawd/skills"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{name}.md").write_text(f"---\nname: {name}\ndescription: {description}\n---\n{body}")


def test_returns_none_when_no_skills(jail):
    assert make_skills_tool(jail) is None


def test_returns_tool_when_skills_present(jail):
    _write(jail, "tdd", "use it", "body")

    tool = make_skills_tool(jail)

    assert tool is not None
    assert tool.name == "load_skill"


def test_load_skill_returns_body(jail):
    _write(jail, "tdd", "use it", "# Test-Driven\nWrite the test first.")
    tool = make_skills_tool(jail)

    body = tool.invoke({"name": "tdd"})

    assert "Write the test first." in body


def test_load_skill_unknown_name(jail):
    _write(jail, "tdd", "use it", "body")
    tool = make_skills_tool(jail)

    msg = tool.invoke({"name": "doesnt-exist"})

    assert "unknown skill" in msg
    assert "tdd" in msg  # available list


def test_load_skill_re_discovers_at_call_time(jail):
    """Adding a skill after the tool is built should still work (no caching)."""
    _write(jail, "first", "x", "first body")
    tool = make_skills_tool(jail)
    _write(jail, "second", "x", "second body")

    body = tool.invoke({"name": "second"})

    assert "second body" in body


def test_skills_tool_registered_in_make_tools_when_present(jail):
    from clawd.tools import make_tools

    _write(jail, "x", "x", "x")
    names = {t.name for t in make_tools(jail)}

    assert "load_skill" in names


def test_skills_tool_absent_in_make_tools_when_no_skills(jail):
    from clawd.tools import make_tools

    names = {t.name for t in make_tools(jail)}

    assert "load_skill" not in names
