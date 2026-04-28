import os
import sys
import time
from datetime import datetime
from pathlib import Path

from langchain_core.tools import BaseTool, tool
from langgraph.prebuilt import create_react_agent

from ..llm import make_llm
from .fs import make_fs_tools
from .shell import make_shell_tools
from .web import web_fetch


def _debug() -> bool:
    return os.environ.get("CLAWD_DEBUG_DISPATCH") == "1"


def _log(line: str) -> None:
    print(line, file=sys.stderr, flush=True)


def _short(task: str, n: int = 50) -> str:
    return repr(task if len(task) <= n else task[:n] + "...")


SUBAGENT_PROMPT = """\
You are a subagent of clawd, dispatched to complete one focused task and \
return a final answer to the parent agent.

# Working environment
You operate inside the same git worktree at {jail_root}. All filesystem and \
shell operations are jailed there. You cannot dispatch your own subagents.

# Output style
Return the smallest answer the parent needs — a result, a finding, or a \
short summary. Do not narrate your tool use.
"""


def make_dispatch_tool(jail_root: Path) -> BaseTool:
    sub_tools = [
        *make_fs_tools(jail_root),
        *make_shell_tools(jail_root),
        web_fetch,
    ]

    @tool
    async def dispatch(task: str) -> str:
        """Run a focused task in an isolated subagent and return its final answer.

        Use this to parallelize independent subtasks: issue several `dispatch` calls
        in one turn and they run concurrently. Good for fan-out work like "search for
        X in subsystem A while reading file B".

        The subagent shares the same worktree and has the same filesystem / shell /
        web tools, but cannot dispatch its own subagents (no recursion).
        """
        agent = create_react_agent(
            make_llm(),
            tools=sub_tools,
            prompt=SUBAGENT_PROMPT.format(jail_root=jail_root),
        )

        debug = _debug()
        if debug:
            start = time.perf_counter()
            ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            _log(f"[dispatch {ts}] start {_short(task)}")

        try:
            result = await agent.ainvoke({"messages": [("user", task)]})
        except Exception as e:
            if debug:
                elapsed = time.perf_counter() - start
                _log(
                    f"[dispatch {datetime.now().strftime('%H:%M:%S.%f')[:-3]}] error "
                    f"{_short(task)} ({elapsed:.2f}s)"
                )
            # A subagent crash (malformed tool call rejected by the provider, network
            # blip, etc.) must surface to the parent as a tool result, not propagate
            # up and kill the parent's turn.
            return f"subagent failed: {type(e).__name__}: {e}"

        if debug:
            elapsed = time.perf_counter() - start
            _log(
                f"[dispatch {datetime.now().strftime('%H:%M:%S.%f')[:-3]}] end   "
                f"{_short(task)} ({elapsed:.2f}s)"
            )

        return result["messages"][-1].content

    return dispatch
