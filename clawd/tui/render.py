"""Rich-side rendering: tool-call rows, output summaries, replay, and the streaming turn loop."""

from collections.abc import Callable
from typing import Any

from langchain_core.messages import HumanMessage
from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.syntax import Syntax

from . import theme as t


def _summary_edit(a: dict[str, Any]) -> str:
    path = a.get("path", "")
    delta = len(a.get("new", "").splitlines()) - len(a.get("old", "").splitlines())
    if delta == 0:
        return path
    return f"{path} · {'+' if delta > 0 else ''}{delta} lines"


def _summary_bash(a: dict[str, Any]) -> str:
    cmd = a.get("command", "")
    return f"$ {cmd[:77] + '…' if len(cmd) > 80 else cmd}"


TOOL_RENDERERS: dict[str, tuple[str, Callable[[dict[str, Any]], str]]] = {
    "read_file": ("read", lambda a: a.get("path", "")),
    "write_file": (
        "write",
        lambda a: f"{a.get('path', '')} · {len(a.get('content', '').splitlines())} lines",
    ),
    "edit_file": ("edit", _summary_edit),
    "glob_files": ("glob", lambda a: f"{a.get('pattern', '*')} in {a.get('path', '.')}"),
    "bash": ("shell", _summary_bash),
    "grep": (
        "grep",
        lambda a: (
            f"{a.get('pattern', '')} in {a.get('path', '.')}"
            + (f" ({a['file_glob']})" if a.get("file_glob") else "")
        ),
    ),
    "web_fetch": ("fetch", lambda a: a.get("url", "")),
}


def format_tool_call(name: str, args: dict[str, Any]) -> str:
    head = f"  [{t.TOOL}]{t.TOOL_GLYPH}[/] [{t.TEXT}]"
    if name in TOOL_RENDERERS:
        verb, summarize = TOOL_RENDERERS[name]
        return f"{head}{verb}[/] [{t.ACCENT}]{summarize(args)}[/]"
    return f"{head}{name}[/] [{t.DIM}]{args}[/]"


def _looks_like_diff(text: str) -> bool:
    head = text[:300]
    return "diff --git" in head or ("--- " in head and "+++ " in head)


def summarize_output(text: str, max_lines: int = 4) -> Any:
    if not text.strip():
        return f"  [{t.DIM}](no output)[/]"
    if _looks_like_diff(text):
        return Syntax(text, "diff", theme="ansi_dark", background_color="default")
    lines = text.splitlines()
    if len(lines) > max_lines:
        more = len(lines) - max_lines
        body = "\n".join(lines[:max_lines])
        return f"  [{t.DIM}]{body}\n  … {more} more line{'' if more == 1 else 's'}[/]"
    return f"  [{t.DIM}]{text}[/]"


def _print_user(console: Console, content: str) -> None:
    console.print()
    console.print(f"[{t.USER}]{t.USER_BAR}[/] [bold]{content}[/]")


async def replay_history(agent: Any, config: dict[str, Any], console: Console) -> None:
    state = await agent.aget_state(config)
    messages = state.values.get("messages", []) if state and state.values else []
    for msg in messages:
        if msg.type == "human":
            _print_user(console, str(msg.content))
        elif msg.type == "ai":
            if msg.content:
                console.print(Markdown(msg.content))
            for tc in getattr(msg, "tool_calls", []) or []:
                console.print(format_tool_call(tc["name"], tc.get("args", {})))
        elif msg.type == "tool":
            console.print(summarize_output(str(msg.content)))


async def run_turn(agent: Any, config: dict[str, Any], prompt: str, console: Console) -> None:
    _print_user(console, prompt)
    buffer = ""
    live: Live | None = None

    def stop_live() -> None:
        nonlocal live, buffer
        if live is not None:
            live.stop()
            live = None
            buffer = ""

    async for event in agent.astream_events(
        {"messages": [HumanMessage(content=prompt)]}, config=config, version="v2"
    ):
        kind = event["event"]
        if kind == "on_chat_model_stream":
            tok = event["data"]["chunk"].content
            if not isinstance(tok, str) or not tok:
                continue
            if live is None:
                live = Live(Markdown(""), console=console, refresh_per_second=20)
                live.start()
            buffer += tok
            live.update(Markdown(buffer))
        elif kind == "on_tool_start":
            stop_live()
            console.print(
                format_tool_call(event.get("name", "tool"), event["data"].get("input", {}))
            )
        elif kind == "on_tool_end":
            output = event["data"].get("output")
            console.print(summarize_output(str(getattr(output, "content", output) or "")))

    stop_live()
