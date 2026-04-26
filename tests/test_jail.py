import pytest

from clawd.tools.fs import _jail


def test_relative_path_resolved_inside_jail(jail):
    assert _jail(jail, "foo.txt") == (jail / "foo.txt").resolve()


def test_nested_relative_path(jail):
    assert _jail(jail, "a/b/c.txt") == (jail / "a/b/c.txt").resolve()


def test_absolute_path_inside_jail_ok(jail):
    target = jail / "sub" / "f.txt"
    assert _jail(jail, str(target)) == target.resolve()


def test_absolute_outside_jail_blocked(jail):
    with pytest.raises(ValueError, match="escapes worktree"):
        _jail(jail, "/etc/passwd")


def test_dotdot_escape_blocked(jail):
    with pytest.raises(ValueError, match="escapes worktree"):
        _jail(jail, "../../etc/passwd")


def test_tilde_expansion_blocked_when_outside(jail):
    with pytest.raises(ValueError, match="escapes worktree"):
        _jail(jail, "~/some-file-that-shouldnt-be-readable")
