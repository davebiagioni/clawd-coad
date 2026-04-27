"""Build the prompt_toolkit PromptSession that owns the input line + bottom toolbar."""

import os
import subprocess
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.document import Document
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import FileHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.styles import Style

from ..config import Settings
from .commands import COMMANDS
from .ledger import SessionLedger

_STYLE = Style.from_dict(
    {
        "bottom-toolbar": "fg:#888888 noreverse",
        "prompt": "fg:ansicyan",
    }
)


def _history_path() -> Path:
    base = Path(os.environ.get("XDG_CONFIG_HOME") or "~/.config").expanduser()
    return base / "clawd" / "history"


def _format_tokens(n: int) -> str:
    if n == 0:
        return "—"
    if n < 1000:
        return str(n)
    if n < 1_000_000:
        return f"{n / 1000:.1f}k"
    return f"{n / 1_000_000:.1f}M"


def _list_files(jail_root: Path) -> list[str]:
    """List candidate files for @-completion, relative to jail_root.

    Uses `git ls-files` so .gitignore is honored. Falls back to a directory
    walk when git isn't available or jail_root isn't a repo."""
    try:
        result = subprocess.run(
            ["git", "-C", str(jail_root), "ls-files"],
            capture_output=True,
            text=True,
            check=True,
            timeout=2,
        )
        return [line for line in result.stdout.splitlines() if line]
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        out: list[str] = []
        for p in sorted(jail_root.rglob("*")):
            if not p.is_file():
                continue
            rel = p.relative_to(jail_root)
            if any(part.startswith(".") for part in rel.parts):
                continue
            out.append(str(rel))
        return out


class _Completer(Completer):
    """Slash commands at the start of the line, @file mentions anywhere."""

    def __init__(self, jail_root: Path) -> None:
        self._jail_root = jail_root
        self._files: list[str] | None = None

    def _file_list(self) -> list[str]:
        if self._files is None:
            self._files = _list_files(self._jail_root)
        return self._files

    def get_completions(self, document: Document, complete_event: Any) -> Iterable[Completion]:
        text = document.text_before_cursor

        if text.startswith("/") and " " not in text:
            for name, (_fn, desc) in COMMANDS.items():
                if name.startswith(text):
                    yield Completion(name, start_position=-len(text), display_meta=desc)
            return

        word_start = max(text.rfind(" "), text.rfind("\n")) + 1
        word = text[word_start:]
        if not word.startswith("@"):
            return
        needle = word[1:].lower()
        for path in self._file_list():
            if needle in path.lower():
                yield Completion(
                    "@" + path,
                    start_position=-len(word),
                    display=path,
                )


def _make_toolbar(settings: Settings, branch: str, ledger: SessionLedger, has_callbacks: bool):
    def _toolbar() -> str:
        parts = [settings.provider, settings.model, branch]
        if has_callbacks:
            parts.append("$—" if ledger.pricing is None else f"${ledger.cost_usd:.4f}")
        parts.append(f"{_format_tokens(ledger.total_tokens)} tok")
        return " · ".join(parts)

    return _toolbar


def _key_bindings() -> KeyBindings:
    bindings = KeyBindings()

    @bindings.add("escape", "enter")
    def _(event: Any) -> None:
        event.current_buffer.insert_text("\n")

    return bindings


def make_prompt_session(
    settings: Settings,
    branch: str,
    ledger: SessionLedger,
    has_callbacks: bool,
    jail_root: Path,
) -> PromptSession:
    history_path = _history_path()
    history_path.parent.mkdir(parents=True, exist_ok=True)

    return PromptSession(
        message=HTML("<prompt>&gt; </prompt>"),
        history=FileHistory(str(history_path)),
        completer=_Completer(jail_root),
        complete_while_typing=True,
        bottom_toolbar=_make_toolbar(settings, branch, ledger, has_callbacks),
        style=_STYLE,
        key_bindings=_key_bindings(),
        multiline=False,
        refresh_interval=0.5,
        erase_when_done=True,
    )
