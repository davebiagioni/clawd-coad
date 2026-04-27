"""TUI entry point: banner, main loop, command dispatch, error handling."""

import asyncio
import traceback

import httpx
from prompt_toolkit.patch_stdout import patch_stdout
from rich.console import Console

from ..agent import make_session
from ..config import settings
from . import theme as t
from .commands import COMMANDS, EXIT_WORDS, Context
from .input import make_prompt_session
from .ledger import LedgerCallback, SessionLedger
from .render import replay_history, run_turn

console = Console()


def _is_connection_error(exc: BaseException) -> bool:
    while exc is not None:
        if isinstance(exc, httpx.ConnectError):
            return True
        exc = exc.__cause__
    return False


def _api_status_error(exc: BaseException) -> BaseException | None:
    """Return the first exception in the cause chain that looks like a provider
    HTTP-status error (openai.APIStatusError, anthropic.APIStatusError, …).
    Duck-typed on `status_code` so we don't need to import either SDK here."""
    while exc is not None:
        if getattr(exc, "status_code", None) is not None:
            return exc
        exc = exc.__cause__
    return None


def _banner(jail_root, branch: str) -> None:
    console.print(
        f"\n[bold]clawd[/]  [{t.TOOL}]{settings.provider}[/]  "
        f"[{t.ACCENT}]{settings.model}[/]  [{t.WARN}]{branch}[/]"
    )
    console.print(f"[{t.DIM}]worktree: {jail_root}[/]")
    console.print(
        f"[{t.DIM}]/help for commands  ·  alt-enter for newline  ·  ctrl-r searches history[/]\n"
    )


async def _main(thread_id: str) -> None:
    async with make_session(thread_id) as session:
        ledger = SessionLedger()
        await ledger.refresh_pricing(settings.model)
        config = {
            "configurable": {"thread_id": thread_id},
            "callbacks": list(session.callbacks) + [LedgerCallback(ledger)],
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
        if session.callbacks and ledger.pricing is None:
            console.print(
                f"[{t.DIM}]no langfuse pricing for {settings.model} — run /cost to set it[/]"
            )
        await replay_history(session.agent, config, console)

        ps = make_prompt_session(settings, session.branch, ledger, bool(session.callbacks))
        ctx = Context(session=session, config=config, console=console, ledger=ledger)

        while True:
            try:
                with patch_stdout():
                    prompt = (await ps.prompt_async()).strip()
            except (EOFError, KeyboardInterrupt):
                console.print()
                break

            if not prompt:
                continue
            if prompt.lower() in EXIT_WORDS:
                break

            if prompt.startswith("/"):
                parts = prompt.split()
                entry = COMMANDS.get(parts[0].lower())
                if entry is None:
                    console.print(f"[{t.ERROR}]unknown command:[/] {parts[0]} (try /help)")
                    continue
                try:
                    await entry[0](ctx, parts[1:])
                except Exception as e:
                    console.print(f"[{t.ERROR}]error:[/] {e}")
                continue

            try:
                await run_turn(session.agent, config, prompt, console)
            except KeyboardInterrupt:
                console.print(f"\n[{t.ERROR}]interrupted[/]")
            except Exception as e:
                if _is_connection_error(e):
                    target = (
                        settings.base_url if settings.provider == "openai" else "the Anthropic API"
                    )
                    console.print(
                        f"[{t.ERROR}]couldn't reach {target}[/] — is the model server running?"
                    )
                elif (api_err := _api_status_error(e)) is not None:
                    console.print(f"[{t.ERROR}]API error {api_err.status_code}:[/] {api_err}")
                else:
                    console.print(f"[{t.ERROR}]error:[/] {e}")
                    console.print(f"[{t.DIM}]{traceback.format_exc()}[/]")

        console.print(f"[{t.DIM}]bye[/]")


def run(thread_id: str) -> None:
    asyncio.run(_main(thread_id))
