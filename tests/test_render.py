from rich.syntax import Syntax

from clawd.tui.render import _looks_like_diff, format_tool_call, summarize_output


def test_format_tool_call_read_file():
    out = format_tool_call("read_file", {"path": "clawd/tui.py"})
    assert "read" in out
    assert "clawd/tui.py" in out


def test_format_tool_call_write_file_includes_line_count():
    out = format_tool_call("write_file", {"path": "x.py", "content": "a\nb\nc\n"})
    assert "x.py" in out
    assert "3 lines" in out


def test_format_tool_call_edit_file_shows_line_delta():
    out = format_tool_call("edit_file", {"path": "x.py", "old": "a\nb", "new": "a\nb\nc\nd"})
    assert "x.py" in out
    assert "+2 lines" in out


def test_format_tool_call_edit_file_no_delta_omits_lines():
    out = format_tool_call("edit_file", {"path": "x.py", "old": "a\nb", "new": "x\ny"})
    assert "x.py" in out
    assert "lines" not in out


def test_format_tool_call_bash_truncates_long_command():
    long = "echo " + "a" * 200
    out = format_tool_call("bash", {"command": long})
    assert "shell" in out
    assert "…" in out


def test_format_tool_call_bash_short_command_intact():
    out = format_tool_call("bash", {"command": "ls -la"})
    assert "$ ls -la" in out


def test_format_tool_call_grep_with_glob():
    out = format_tool_call("grep", {"pattern": "TODO", "path": "src", "file_glob": "*.py"})
    assert "TODO" in out
    assert "src" in out
    assert "*.py" in out


def test_format_tool_call_unknown_tool_falls_back():
    out = format_tool_call("custom_thing", {"foo": "bar"})
    assert "custom_thing" in out
    assert "foo" in out


def test_summarize_output_empty():
    out = summarize_output("")
    assert "(no output)" in out


def test_summarize_output_whitespace_only():
    out = summarize_output("   \n\n  ")
    assert "(no output)" in out


def test_summarize_output_short_passes_through():
    out = summarize_output("ok")
    assert "ok" in out


def test_summarize_output_long_truncates_with_count():
    text = "\n".join(f"line {i}" for i in range(20))
    out = summarize_output(text, max_lines=3)
    assert "line 0" in out
    assert "line 19" not in out
    assert "17 more lines" in out


def test_summarize_output_one_extra_line_uses_singular():
    text = "\n".join(f"line {i}" for i in range(5))
    out = summarize_output(text, max_lines=4)
    assert "1 more line" in out
    assert "1 more lines" not in out


def test_summarize_output_diff_returns_syntax():
    diff = "diff --git a/foo b/foo\n--- a/foo\n+++ b/foo\n@@ -1 +1 @@\n-old\n+new"
    out = summarize_output(diff)
    assert isinstance(out, Syntax)


def test_looks_like_diff_positive():
    assert _looks_like_diff("diff --git a/x b/x\n@@ ...")
    assert _looks_like_diff("--- a/x\n+++ b/x\n")


def test_looks_like_diff_negative():
    assert not _looks_like_diff("just some text")
    assert not _looks_like_diff("Error: bad input")
