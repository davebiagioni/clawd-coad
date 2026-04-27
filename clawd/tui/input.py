"""Build the prompt_toolkit PromptSession that owns the input line + bottom toolbar."""

import os
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


class _SlashCompleter(Completer):
    def get_completions(self, document: Document, complete_event: Any) -> Iterable[Completion]:
        text = document.text_before_cursor
        if not text.startswith("/"):
            return
        for name, (_fn, desc) in COMMANDS.items():
            if name.startswith(text):
                yield Completion(name, start_position=-len(text), display_meta=desc)


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
    settings: Settings, branch: str, ledger: SessionLedger, has_callbacks: bool
) -> PromptSession:
    history_path = _history_path()
    history_path.parent.mkdir(parents=True, exist_ok=True)

    return PromptSession(
        message=HTML("<prompt>&gt; </prompt>"),
        history=FileHistory(str(history_path)),
        completer=_SlashCompleter(),
        complete_while_typing=False,
        bottom_toolbar=_make_toolbar(settings, branch, ledger, has_callbacks),
        style=_STYLE,
        key_bindings=_key_bindings(),
        multiline=False,
        refresh_interval=0.5,
        erase_when_done=True,
    )
