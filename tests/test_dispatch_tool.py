import asyncio

import pytest
from langchain_core.messages import AIMessage

from clawd.tools import dispatch as dispatch_module
from clawd.tools.dispatch import make_dispatch_tool


class _FakeAgent:
    """Captures the prompt + tools it was built with and returns a canned reply."""

    def __init__(self, *, tools, prompt, reply: str = "ok"):
        self.tools = tools
        self.prompt = prompt
        self.reply = reply
        self.received: list[str] = []

    async def ainvoke(self, payload):
        # payload is {"messages": [("user", task)]}
        self.received.append(payload["messages"][0][1])
        return {"messages": [AIMessage(content=self.reply)]}


def _patch_agent(monkeypatch, *, reply: str = "ok"):
    """Replace create_react_agent + make_llm so no real LLM is called."""
    built: list[_FakeAgent] = []

    def fake_create_react_agent(llm, tools, prompt):
        agent = _FakeAgent(tools=tools, prompt=prompt, reply=reply)
        built.append(agent)
        return agent

    monkeypatch.setattr(dispatch_module, "create_react_agent", fake_create_react_agent)
    monkeypatch.setattr(dispatch_module, "make_llm", lambda: object())
    return built


def test_dispatch_tool_has_expected_name(jail):
    tool = make_dispatch_tool(jail)
    assert tool.name == "dispatch"


def test_dispatch_returns_subagents_final_message(jail, monkeypatch):
    _patch_agent(monkeypatch, reply="found 3 matches")
    tool = make_dispatch_tool(jail)

    result = asyncio.run(tool.ainvoke({"task": "count matches of FOO"}))

    assert result == "found 3 matches"


def test_dispatch_passes_task_to_subagent(jail, monkeypatch):
    built = _patch_agent(monkeypatch)
    tool = make_dispatch_tool(jail)

    asyncio.run(tool.ainvoke({"task": "summarize agent.py"}))

    assert built[0].received == ["summarize agent.py"]


def test_subagent_does_not_get_dispatch_tool(jail, monkeypatch):
    """No recursion: a subagent must not be able to dispatch its own subagents."""
    built = _patch_agent(monkeypatch)
    tool = make_dispatch_tool(jail)

    asyncio.run(tool.ainvoke({"task": "noop"}))

    tool_names = {t.name for t in built[0].tools}
    assert "dispatch" not in tool_names
    # sanity: it still has the normal tools
    assert {"read_file", "bash", "web_fetch"}.issubset(tool_names)


def test_subagent_prompt_mentions_jail_root(jail, monkeypatch):
    built = _patch_agent(monkeypatch)
    tool = make_dispatch_tool(jail)

    asyncio.run(tool.ainvoke({"task": "noop"}))

    assert str(jail) in built[0].prompt


def test_parallel_dispatch_runs_concurrently(jail, monkeypatch):
    """Two dispatch calls awaited via asyncio.gather should overlap, not serialize."""
    started = 0
    max_concurrent = 0

    class _SlowAgent:
        def __init__(self, *_, **__):
            pass

        async def ainvoke(self, _payload):
            nonlocal started, max_concurrent
            started += 1
            max_concurrent = max(max_concurrent, started)
            await asyncio.sleep(0.05)
            started -= 1
            return {"messages": [AIMessage(content="done")]}

    monkeypatch.setattr(dispatch_module, "create_react_agent", lambda *a, **kw: _SlowAgent())
    monkeypatch.setattr(dispatch_module, "make_llm", lambda: object())

    tool = make_dispatch_tool(jail)

    async def run_two():
        return await asyncio.gather(
            tool.ainvoke({"task": "a"}),
            tool.ainvoke({"task": "b"}),
        )

    results = asyncio.run(run_two())
    assert results == ["done", "done"]
    assert max_concurrent == 2


@pytest.mark.parametrize("registered", [True])
def test_dispatch_is_registered_with_main_tools(jail, registered):
    from clawd.tools import make_tools

    names = {t.name for t in make_tools(jail)}
    assert ("dispatch" in names) is registered
