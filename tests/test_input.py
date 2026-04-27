import subprocess
from pathlib import Path

from prompt_toolkit.document import Document

from clawd.tui.input import _Completer, _list_files


def _completions(comp: _Completer, text: str) -> list[tuple[str, int]]:
    out = []
    for c in comp.get_completions(Document(text, len(text)), None):
        out.append((c.text, c.start_position))
    return out


def test_slash_command_completion(jail: Path):
    comp = _Completer(jail)
    results = _completions(comp, "/he")
    assert ("/help", -3) in results


def test_slash_command_completion_lists_all_with_just_slash(jail: Path):
    comp = _Completer(jail)
    results = _completions(comp, "/")
    names = {text for text, _ in results}
    assert "/help" in names
    assert "/clear" in names


def test_slash_after_space_does_not_complete_command(jail: Path):
    comp = _Completer(jail)
    assert _completions(comp, "/help ") == []


def test_at_mention_completes_repo_files(git_repo: Path):
    (git_repo / "src").mkdir()
    (git_repo / "src" / "main.py").write_text("x")
    (git_repo / "README.md").write_text("hi")
    subprocess.run(["git", "-C", str(git_repo), "add", "."], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(git_repo), "commit", "-q", "-m", "files"],
        check=True,
        capture_output=True,
    )

    comp = _Completer(git_repo)
    results = _completions(comp, "look at @main")
    assert results == [("@src/main.py", -5)]


def test_at_mention_substring_match_case_insensitive(git_repo: Path):
    (git_repo / "src").mkdir()
    (git_repo / "src" / "Main.py").write_text("x")
    subprocess.run(["git", "-C", str(git_repo), "add", "."], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(git_repo), "commit", "-q", "-m", "f"], check=True, capture_output=True
    )

    comp = _Completer(git_repo)
    assert ("@src/Main.py", -5) in _completions(comp, "@MAIN")


def test_at_mention_only_completes_current_word(jail: Path):
    (jail / "a.py").write_text("x")
    comp = _Completer(jail)
    assert _completions(comp, "hello world") == []


def test_list_files_outside_git_walks_directory(jail: Path):
    (jail / "a.py").write_text("x")
    (jail / "sub").mkdir()
    (jail / "sub" / "b.py").write_text("x")
    (jail / ".hidden").write_text("x")
    files = _list_files(jail)
    assert "a.py" in files
    assert "sub/b.py" in files
    assert ".hidden" not in files


def test_list_files_in_git_repo_respects_gitignore(git_repo: Path):
    (git_repo / ".gitignore").write_text("ignored.py\n")
    (git_repo / "tracked.py").write_text("x")
    (git_repo / "ignored.py").write_text("x")
    subprocess.run(
        ["git", "-C", str(git_repo), "add", ".gitignore", "tracked.py"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(git_repo), "commit", "-q", "-m", "f"], check=True, capture_output=True
    )

    files = _list_files(git_repo)
    assert "tracked.py" in files
    assert "ignored.py" not in files
