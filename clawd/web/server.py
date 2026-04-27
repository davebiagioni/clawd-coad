"""Tiny FastAPI frontend for clawd. Streams the same agent events the TUI consumes."""

import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from langchain_core.messages import HumanMessage
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from ..agent import make_session
from ..config import settings
from ..tui.ledger import LedgerCallback, SessionLedger

STATIC_DIR = Path(__file__).parent / "static"


class Prompt(BaseModel):
    text: str


def _history(messages: list[Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for msg in messages:
        if msg.type == "human":
            out.append({"kind": "user", "text": str(msg.content)})
        elif msg.type == "ai":
            if msg.content:
                out.append({"kind": "assistant", "text": str(msg.content)})
            for tc in getattr(msg, "tool_calls", []) or []:
                out.append({"kind": "tool_call", "name": tc["name"], "args": tc.get("args", {})})
        elif msg.type == "tool":
            out.append({"kind": "tool_output", "text": str(msg.content)})
    return out


def make_app(thread_id: str) -> FastAPI:
    state: dict[str, Any] = {}

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        async with make_session(thread_id) as session:
            ledger = SessionLedger()
            await ledger.refresh_pricing(settings.model)
            state["session"] = session
            state["ledger"] = ledger
            state["config"] = {
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
            yield

    app = FastAPI(lifespan=lifespan)

    @app.get("/api/info")
    async def info() -> dict[str, Any]:
        session = state["session"]
        ledger: SessionLedger = state["ledger"]
        return {
            "thread_id": thread_id,
            "provider": settings.provider,
            "model": settings.model,
            "branch": session.branch,
            "jail_root": str(session.jail_root),
            "tokens": ledger.total_tokens,
            "cost_usd": ledger.cost_usd,
        }

    @app.get("/api/history")
    async def history() -> list[dict[str, Any]]:
        agent = state["session"].agent
        snap = await agent.aget_state(state["config"])
        msgs = snap.values.get("messages", []) if snap and snap.values else []
        return _history(msgs)

    @app.post("/api/chat")
    async def chat(prompt: Prompt) -> EventSourceResponse:
        agent = state["session"].agent
        config = state["config"]

        async def gen():
            async for event in agent.astream_events(
                {"messages": [HumanMessage(content=prompt.text)]},
                config=config,
                version="v2",
            ):
                kind = event["event"]
                if kind == "on_chat_model_stream":
                    tok = event["data"]["chunk"].content
                    if isinstance(tok, str) and tok:
                        yield {"event": "token", "data": json.dumps({"text": tok})}
                elif kind == "on_tool_start":
                    yield {
                        "event": "tool_start",
                        "data": json.dumps(
                            {
                                "name": event.get("name", "tool"),
                                "args": event["data"].get("input", {}),
                            }
                        ),
                    }
                elif kind == "on_tool_end":
                    output = event["data"].get("output")
                    text = str(getattr(output, "content", output) or "")
                    yield {"event": "tool_end", "data": json.dumps({"output": text})}
            yield {"event": "done", "data": "{}"}

        return EventSourceResponse(gen())

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/")
    async def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    return app


def serve(thread_id: str, host: str = "127.0.0.1", port: int = 8765) -> None:
    import uvicorn

    print(f"clawd web — http://{host}:{port}  (thread {thread_id})")
    uvicorn.run(make_app(thread_id), host=host, port=port, log_level="warning")
