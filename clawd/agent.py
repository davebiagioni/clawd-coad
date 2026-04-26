from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from langchain_core.callbacks import BaseCallbackHandler
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.prebuilt import create_react_agent

from .config import settings
from .llm import make_llm
from .prompt import build_system_prompt
from .tools import make_tools
from .tracing import flush as flush_tracing
from .tracing import make_langfuse_handler
from .worktree import ensure_worktree


@dataclass
class Session:
    agent: Any
    jail_root: Path
    branch: str
    callbacks: list[BaseCallbackHandler] = field(default_factory=list)


@asynccontextmanager
async def make_session(thread_id: str = "default") -> AsyncIterator[Session]:
    jail_root, branch = ensure_worktree(thread_id)

    db_path = Path(settings.db_path).expanduser()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    handler = make_langfuse_handler()
    callbacks = [handler] if handler else []

    async with AsyncSqliteSaver.from_conn_string(str(db_path)) as saver:
        agent = create_react_agent(
            make_llm(),
            tools=make_tools(jail_root),
            checkpointer=saver,
            prompt=build_system_prompt(jail_root, branch),
        )
        try:
            yield Session(agent=agent, jail_root=jail_root, branch=branch, callbacks=callbacks)
        finally:
            flush_tracing()
