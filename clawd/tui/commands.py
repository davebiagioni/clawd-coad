"""Slash-command handlers. Each takes a Context + args."""

import asyncio
from dataclasses import dataclass
from typing import Any

from rich.console import Console
from rich.syntax import Syntax

from ..agent import Session
from ..config import settings
from ..pricing import find_pricing, register_pricing
from ..worktree import list_session_ids
from . import theme as t
from .ledger import SessionLedger


@dataclass
class Context:
    session: Session
    config: dict[str, Any]
    console: Console
    ledger: SessionLedger


async def cmd_help(ctx: Context, args: list[str]) -> None:
    ctx.console.print("[bold]commands:[/]")
    for name, (_fn, desc) in COMMANDS.items():
        ctx.console.print(f"  [{t.ACCENT}]{name:<8}[/] {desc}")
    ctx.console.print(f"  [{t.ACCENT}]{'/exit':<8}[/] quit (also: /quit, /q, ctrl+d)")


async def cmd_clear(ctx: Context, args: list[str]) -> None:
    thread_id = ctx.config["configurable"]["thread_id"]
    await ctx.session.agent.checkpointer.adelete_thread(thread_id)
    ctx.ledger.reset()
    ctx.console.print(f"[{t.DIM}]conversation cleared[/]")


async def cmd_diff(ctx: Context, args: list[str]) -> None:
    proc = await asyncio.create_subprocess_exec(
        "git",
        "-C",
        str(ctx.session.jail_root),
        "diff",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await proc.communicate()
    out = stdout.decode(errors="replace")
    if not out.strip():
        ctx.console.print(f"[{t.DIM}]no changes[/]")
        return
    ctx.console.print(Syntax(out, "diff", theme="ansi_dark", background_color="default"))


async def cmd_cost(ctx: Context, args: list[str]) -> None:
    if not ctx.session.callbacks:
        ctx.console.print(
            f"[{t.DIM}]langfuse not configured (set LANGFUSE_PUBLIC_KEY/SECRET_KEY)[/]"
        )
        return

    if not args:
        match = await find_pricing(settings.model)
        if match is None:
            ctx.console.print(
                f"model: [{t.ACCENT}]{settings.model}[/] · [{t.WARN}]not registered[/]"
            )
            ctx.console.print(
                f"[{t.DIM}]register with: /cost set <input_per_1m> <output_per_1m>[/]"
            )
            ctx.console.print(f"[{t.DIM}]example (free):     /cost set 0 0[/]")
            ctx.console.print(f"[{t.DIM}]example (paid):     /cost set 0.15 0.6[/]")
            return
        in_per_1m = (match.input_price or 0) * 1_000_000
        out_per_1m = (match.output_price or 0) * 1_000_000
        ctx.console.print(f"model: [{t.ACCENT}]{settings.model}[/] · [{t.SUCCESS}]registered[/]")
        ctx.console.print(f"  pattern: {match.match_pattern}")
        ctx.console.print(f"  input: ${in_per_1m:g}/1M  output: ${out_per_1m:g}/1M")
        ctx.console.print(f"  session so far: [{t.SUCCESS}]${ctx.ledger.cost_usd:.4f}[/]")
        return

    if args[0] == "set" and len(args) == 3:
        try:
            in_per_1m = float(args[1])
            out_per_1m = float(args[2])
        except ValueError:
            ctx.console.print(f"[{t.ERROR}]usage:[/] /cost set <input_per_1m> <output_per_1m>")
            return
        await register_pricing(settings.model, in_per_1m, out_per_1m)
        await ctx.ledger.refresh_pricing(settings.model)
        ctx.console.print(f"registered [{t.ACCENT}]{settings.model}[/]")
        ctx.console.print(f"  input: ${in_per_1m:g}/1M  output: ${out_per_1m:g}/1M")
        return

    ctx.console.print(f"[{t.ERROR}]usage:[/] /cost  |  /cost set <input_per_1m> <output_per_1m>")


async def cmd_sessions(ctx: Context, args: list[str]) -> None:
    ids = list_session_ids()
    if not ids:
        ctx.console.print(f"[{t.DIM}]no sessions yet[/]")
        return
    current = ctx.config["configurable"]["thread_id"]
    for sid in ids:
        if sid == current:
            ctx.console.print(f"  [{t.ACCENT}]* {sid}[/]")
        else:
            ctx.console.print(f"    {sid}")
    ctx.console.print(
        f"[{t.DIM}]resume with `clawd -r <id>` (or `clawd -c` for the most recent)[/]"
    )


COMMANDS: dict[str, tuple[Any, str]] = {
    "/help": (cmd_help, "show this list"),
    "/clear": (cmd_clear, "reset this conversation"),
    "/diff": (cmd_diff, "show git diff of the worktree"),
    "/cost": (cmd_cost, "show or register langfuse pricing for this model"),
    "/sessions": (cmd_sessions, "list saved sessions"),
}

EXIT_WORDS: set[str] = {"/exit", "/quit", "/q", "exit", "quit"}
