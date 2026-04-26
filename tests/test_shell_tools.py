from clawd.tools.shell import make_shell_tools


def _tools(jail):
    return {t.name: t for t in make_shell_tools(jail)}


def test_factory_returns_expected_tools(jail):
    tools = _tools(jail)
    assert set(tools) == {"bash", "grep"}


async def test_bash_runs_in_jail_cwd(jail):
    tools = _tools(jail)
    out = await tools["bash"].ainvoke({"command": "pwd"})
    assert str(jail.resolve()) in out
    assert "exit code: 0" in out


async def test_bash_stderr_captured(jail):
    tools = _tools(jail)
    out = await tools["bash"].ainvoke({"command": "echo oops 1>&2"})
    assert "oops" in out
    assert "stderr:" in out


async def test_bash_timeout(jail):
    tools = _tools(jail)
    out = await tools["bash"].ainvoke({"command": "sleep 5", "timeout": 1})
    assert "timed out" in out


async def test_grep_finds_match(jail):
    (jail / "x.txt").write_text("hello world")
    tools = _tools(jail)
    out = await tools["grep"].ainvoke({"pattern": "hello"})
    assert "hello world" in out


async def test_grep_no_matches(jail):
    (jail / "x.txt").write_text("hello world")
    tools = _tools(jail)
    out = await tools["grep"].ainvoke({"pattern": "definitely-not-there"})
    assert out == "no matches"


async def test_grep_file_glob_filter(jail):
    (jail / "a.py").write_text("target")
    (jail / "b.txt").write_text("target")
    tools = _tools(jail)
    out = await tools["grep"].ainvoke({"pattern": "target", "file_glob": "*.py"})
    assert "a.py" in out
    assert "b.txt" not in out
