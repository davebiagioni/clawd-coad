from rich.syntax import Syntax

from clawd.tui.render import _looks_like_diff, format_tool_call, render_output


def test_format_tool_call_includes_name_and_args():
    out = format_tool_call("read_file", {"path": "clawd/tui.py"})
    assert "read_file" in out
    assert "clawd/tui.py" in out


def test_format_tool_call_unknown_tool_renders_args():
    out = format_tool_call("custom_thing", {"foo": "bar"})
    assert "custom_thing" in out
    assert "foo" in out
    assert "bar" in out


def test_render_output_empty():
    out = render_output("")
    assert "(no output)" in out


def test_render_output_whitespace_only():
    out = render_output("   \n\n  ")
    assert "(no output)" in out


def test_render_output_short_passes_through():
    out = render_output("ok")
    assert "ok" in out


def test_render_output_long_passes_through_in_full():
    text = "\n".join(f"line {i}" for i in range(200))
    out = render_output(text)
    assert "line 0" in out
    assert "line 199" in out


def test_render_output_diff_returns_syntax():
    diff = "diff --git a/foo b/foo\n--- a/foo\n+++ b/foo\n@@ -1 +1 @@\n-old\n+new"
    out = render_output(diff)
    assert isinstance(out, Syntax)


def test_looks_like_diff_positive():
    assert _looks_like_diff("diff --git a/x b/x\n@@ ...")
    assert _looks_like_diff("--- a/x\n+++ b/x\n")


def test_looks_like_diff_negative():
    assert not _looks_like_diff("just some text")
    assert not _looks_like_diff("Error: bad input")
