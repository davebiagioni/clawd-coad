"""Plain Rich rendering: user messages, raw tool calls, full tool output, streaming."""

from typing import Any

from langchain_core.messages import HumanMessage
from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.spinner import Spinner
from rich.syntax import Syntax
from rich.text import Text

from . import theme as t


class _Display:
    """Rich Live region that switches between transient status indicators
    (cleared on stop) and persistent streaming markdown (kept on screen)."""

    def __init__(self, console: Console) -> None:
        self.console = console
        self._live: Live | None = None
        self._buffer = ""
        self._streaming = False

    def status(self, msg: str) -> None:
        self._stop()
        spinner = Spinner("simpleDots", text=Text(msg, style=t.DIM), style=t.DIM)
        self._live = Live(spinner, console=self.console, refresh_per_second=8, transient=True)
        self._live.start()

    def token(self, tok: str) -> None:
        if not self._streaming:
            self._stop()
            self._live = Live(Markdown(""), console=self.console, refresh_per_second=20)
            self._live.start()
            self._streaming = True
        self._buffer += tok
        self._live.update(Markdown(self._buffer))

    def stop(self) -> None:
        self._stop()

    def _stop(self) -> None:
        if self._live is not None:
            self._live.stop()
            self._live = None
        self._buffer = ""
        self._streaming = False


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
    display = _Display(console)
    display.status("thinking")

    async for event in agent.astream_events(
        {"messages": [HumanMessage(content=prompt)]}, config=config, version="v2"
    ):
        kind = event["event"]
        if kind == "on_chat_model_stream":
            tok = event["data"]["chunk"].content
            if isinstance(tok, str) and tok:
                display.token(tok)
        elif kind == "on_tool_start":
            name = event.get("name", "tool")
            display.stop()
            console.print(format_tool_call(name, event["data"].get("input", {})))
            display.status(f"running {name}")
        elif kind == "on_tool_end":
            display.stop()
            output = event["data"].get("output")
            console.print(render_output(str(getattr(output, "content", output) or "")))
            display.status("thinking")

    display.stop()
