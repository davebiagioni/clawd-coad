"""Plain Rich rendering: user messages, raw tool calls, full tool output, streaming."""

from typing import Any

from langchain_core.messages import HumanMessage
from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.syntax import Syntax

from . import theme as t


def format_tool_call(name: str, args: dict[str, Any]) -> str:
    return f"[{t.TOOL}]→ {name}({args})[/]"


def _looks_like_diff(text: str) -> bool:
    head = text[:300]
    return "diff --git" in head or ("--- " in head and "+++ " in head)


def render_output(text: str) -> Any:
    text = text.rstrip()
    if not text:
        return f"[{t.DIM}](no output)[/]"
    if _looks_like_diff(text):
        return Syntax(text, "diff", theme="ansi_dark", background_color="default")
    return f"[{t.DIM}]{text}[/]"


def _print_user(console: Console, content: str) -> None:
    console.print()
    console.print(f"[bold {t.USER}]> {content}[/]")


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
            console.print(render_output(str(msg.content)))


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
            console.print(render_output(str(getattr(output, "content", output) or "")))

    stop_live()
