import pytest

from clawd.tools.fs import make_fs_tools


def _tools(jail):
    return {t.name: t for t in make_fs_tools(jail)}


def test_factory_returns_expected_tools(jail):
    tools = _tools(jail)
    assert set(tools) == {"read_file", "write_file", "edit_file", "glob_files"}


def test_write_then_read_roundtrip(jail):
    tools = _tools(jail)
    tools["write_file"].invoke({"path": "x.txt", "content": "hello"})
    out = tools["read_file"].invoke({"path": "x.txt"})
    # Output is line-numbered: "1\thello"
    assert "hello" in out
    assert out.startswith("1\t")


def test_write_creates_parents(jail):
    tools = _tools(jail)
    tools["write_file"].invoke({"path": "deep/nested/x.txt", "content": "hi"})
    assert (jail / "deep/nested/x.txt").read_text() == "hi"


def test_write_blocked_outside_jail(jail):
    tools = _tools(jail)
    with pytest.raises(ValueError, match="escapes worktree"):
        tools["write_file"].invoke({"path": "/tmp/escape.txt", "content": "x"})


def test_edit_unique_match(jail):
    (jail / "x.txt").write_text("foo bar baz")
    tools = _tools(jail)
    tools["edit_file"].invoke({"path": "x.txt", "old": "bar", "new": "BAR"})
    assert (jail / "x.txt").read_text() == "foo BAR baz"


def test_edit_non_unique_errors(jail):
    (jail / "x.txt").write_text("foo foo")
    tools = _tools(jail)
    with pytest.raises(ValueError, match="appears 2 times"):
        tools["edit_file"].invoke({"path": "x.txt", "old": "foo", "new": "BAR"})


def test_edit_missing_errors(jail):
    (jail / "x.txt").write_text("hello")
    tools = _tools(jail)
    with pytest.raises(ValueError, match="not found"):
        tools["edit_file"].invoke({"path": "x.txt", "old": "missing", "new": "X"})


async def test_glob_finds_files(jail):
    (jail / "a.py").write_text("")
    (jail / "b.py").write_text("")
    (jail / "c.txt").write_text("")
    tools = _tools(jail)
    out = await tools["glob_files"].ainvoke({"pattern": "*.py"})
    assert "a.py" in out
    assert "b.py" in out
    assert "c.txt" not in out


async def test_glob_no_matches(jail):
    tools = _tools(jail)
    out = await tools["glob_files"].ainvoke({"pattern": "*.nonexistent"})
    assert out == "no matches"
