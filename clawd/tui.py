import asyncio
import traceback

from langchain_core.messages import HumanMessage
from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.syntax import Syntax

from .agent import Session, make_session
from .config import settings
from .pricing import find_pricing, register_pricing

console = Console()


def _banner(jail_root, branch) -> None:
    console.print()
    console.print(
        f"[bold]clawd[/bold] · {settings.provider} · {settings.model} · [cyan]{branch}[/cyan]"
    )
    console.print(f"[dim]worktree: {jail_root}[/dim]")
    console.print("[dim]type /help for commands[/dim]")
    console.print()


async def _pricing_nudge(session: Session) -> None:
    if not session.callbacks:
        return
    try:
        match = await find_pricing(settings.model)
    except Exception:
        return
    if match is None:
        console.print(f"[dim]no langfuse pricing for {settings.model} — run /cost to set it[/dim]")


async def _replay_history(agent, config) -> None:
    state = await agent.aget_state(config)
    messages = state.values.get("messages", []) if state and state.values else []
    for msg in messages:
        if msg.type == "human":
            console.print(f"[bold cyan]> {msg.content}[/]")
        elif msg.type == "ai":
            if msg.content:
                console.print(Markdown(msg.content))
            for tc in getattr(msg, "tool_calls", []) or []:
                console.print(f"[yellow]→ {tc['name']}({tc['args']})[/]")
        elif msg.type == "tool":
            text = str(msg.content)
            if len(text) > 400:
                text = text[:400] + "\n..."
            console.print(f"[dim]{text}[/]")


async def _run_turn(agent, config, prompt: str) -> None:
    buffer = ""
    live: Live | None = None

    def stop_live() -> None:
        nonlocal live, buffer
        if live is not None:
            live.stop()
            live = None
            buffer = ""

    async for event in agent.astream_events(
        {"messages": [HumanMessage(content=prompt)]},
        config=config,
        version="v2",
    ):
        kind = event["event"]

        if kind == "on_chat_model_stream":
            chunk = event["data"]["chunk"]
            token = chunk.content if isinstance(chunk.content, str) else ""
            if not token:
                continue
            if live is None:
                live = Live(Markdown(""), console=console, refresh_per_second=20)
                live.start()
            buffer += token
            live.update(Markdown(buffer))

        elif kind == "on_tool_start":
            stop_live()
            name = event.get("name", "tool")
            tool_input = event["data"].get("input", {})
            console.print(f"[yellow]→ {name}({tool_input})[/]")

        elif kind == "on_tool_end":
            output = event["data"].get("output")
            text = str(getattr(output, "content", output) or "")
            if len(text) > 400:
                text = text[:400] + "\n..."
            console.print(f"[dim]{text}[/]")

    stop_live()


async def _cmd_help(session: Session, config: dict, args: list[str]) -> None:
    console.print("[bold]commands:[/]")
    for name, (_fn, desc) in COMMANDS.items():
        console.print(f"  [cyan]{name:<8}[/] {desc}")
    console.print(f"  [cyan]{'/exit':<8}[/] quit (also: /quit, /q, ctrl+d, ctrl+c)")


async def _cmd_clear(session: Session, config: dict, args: list[str]) -> None:
    thread_id = config["configurable"]["thread_id"]
    await session.agent.checkpointer.adelete_thread(thread_id)
    console.print("[dim]conversation cleared[/]")


async def _cmd_diff(session: Session, config: dict, args: list[str]) -> None:
    proc = await asyncio.create_subprocess_exec(
        "git",
        "-C",
        str(session.jail_root),
        "diff",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await proc.communicate()
    out = stdout.decode(errors="replace")
    if not out.strip():
        console.print("[dim]no changes[/]")
        return
    console.print(Syntax(out, "diff", theme="ansi_dark", background_color="default"))


async def _cmd_cost(session: Session, config: dict, args: list[str]) -> None:
    if not session.callbacks:
        console.print("[dim]langfuse not configured (set LANGFUSE_PUBLIC_KEY/SECRET_KEY)[/]")
        return

    if not args:
        match = await find_pricing(settings.model)
        if match is None:
            console.print(f"model: [cyan]{settings.model}[/] · [yellow]not registered[/]")
            console.print("[dim]register with: /cost set <input_per_1m> <output_per_1m>[/]")
            console.print("[dim]example (free):     /cost set 0 0[/]")
            console.print("[dim]example (paid):     /cost set 0.15 0.6[/]")
            return
        in_per_1m = (match.input_price or 0) * 1_000_000
        out_per_1m = (match.output_price or 0) * 1_000_000
        console.print(f"model: [cyan]{settings.model}[/] · [green]registered[/]")
        console.print(f"  pattern: {match.match_pattern}")
        console.print(f"  input: ${in_per_1m:g}/1M  output: ${out_per_1m:g}/1M")
        return

    if args[0] == "set" and len(args) == 3:
        try:
            in_per_1m = float(args[1])
            out_per_1m = float(args[2])
        except ValueError:
            console.print("[red]usage:[/] /cost set <input_per_1m> <output_per_1m>")
            return
        await register_pricing(settings.model, in_per_1m, out_per_1m)
        console.print(f"registered [cyan]{settings.model}[/]")
        console.print(f"  input: ${in_per_1m:g}/1M  output: ${out_per_1m:g}/1M")
        return

    console.print("[red]usage:[/] /cost  |  /cost set <input_per_1m> <output_per_1m>")


COMMANDS = {
    "/help": (_cmd_help, "show this list"),
    "/clear": (_cmd_clear, "reset this conversation"),
    "/diff": (_cmd_diff, "show git diff of the worktree"),
    "/cost": (_cmd_cost, "show or register langfuse pricing for this model"),
}

EXIT_WORDS = {"/exit", "/quit", "/q", "exit", "quit"}


async def _main() -> None:
    thread_id = "default"
    async with make_session(thread_id) as session:
        config = {
            "configurable": {"thread_id": thread_id},
            "callbacks": session.callbacks,
            "metadata": {
                "langfuse_session_id": thread_id,
                "langfuse_tags": [
                    f"provider:{settings.provider}",
                    f"model:{settings.model}",
                    f"branch:{session.branch}",
                ],
            },
            "run_name": "clawd-turn",
        }
        _banner(session.jail_root, session.branch)
        await _pricing_nudge(session)
        await _replay_history(session.agent, config)

        while True:
            try:
                prompt = console.input("[bold cyan]> [/]").strip()
            except (EOFError, KeyboardInterrupt):
                console.print()
                break

            if not prompt:
                continue
            if prompt.lower() in EXIT_WORDS:
                break

            if prompt.startswith("/"):
                parts = prompt.split()
                cmd = parts[0].lower()
                args = parts[1:]
                entry = COMMANDS.get(cmd)
                if entry is None:
                    console.print(f"[red]unknown command:[/] {cmd} (try /help)")
                    continue
                try:
                    await entry[0](session, config, args)
                except Exception as e:
                    console.print(f"[red]error:[/] {e}")
                continue

            try:
                await _run_turn(session.agent, config, prompt)
            except KeyboardInterrupt:
                console.print("\n[red]interrupted[/]")
            except Exception as e:
                console.print(f"[red]error:[/] {e}")
                console.print(f"[dim]{traceback.format_exc()}[/]")

        console.print("[dim]bye[/]")


def run() -> None:
    asyncio.run(_main())
