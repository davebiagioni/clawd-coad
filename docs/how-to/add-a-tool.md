# How to add a new tool

You want to give the agent a new capability — say, querying a database,
hitting an internal API, or running a domain-specific linter. Tools are
LangChain `BaseTool` objects assembled in `clawd/tools/__init__.py`; this
guide walks through the steps.

For the full design behind tools, see
[chapter 5: tools, part 1: filesystem](../concepts/04-tools-filesystem.md)
and [chapter 6: shell & web](../concepts/05-tools-shell-web.md).

## The tool contract

Every tool clawd exposes:

1. Is a `BaseTool` (the easiest way: decorate a function with `@tool` from
   `langchain_core.tools`).
2. Has a clear docstring — the LLM reads it as the tool description, so
   write it for the model, not just for humans.
3. Has typed parameters with sensible defaults where they make sense.
4. Returns a string the model can read.
5. If it touches the filesystem, it goes through `_jail()` from
   `clawd/tools/fs.py` so paths can't escape the worktree.

## Steps

### 1. Pick a home

- Filesystem-shaped → `clawd/tools/fs.py`.
- Subprocess / shell-shaped → `clawd/tools/shell.py`.
- Network-shaped → `clawd/tools/web.py`.
- Genuinely new (e.g. `git.py`, `db.py`) → a new module under `clawd/tools/`.

### 2. Write the tool

The simplest shape — a free function with `@tool`:

```python
# clawd/tools/web.py (existing example, simplified)
from langchain_core.tools import tool

@tool
async def web_fetch(url: str) -> str:
    """Fetch a URL and return its content. HTML is converted to markdown..."""
    ...
```

If your tool needs the worktree path (for jailing or as a working directory),
wrap it in a factory that closes over `jail_root`:

```python
# clawd/tools/fs.py pattern
from pathlib import Path
from langchain_core.tools import BaseTool, tool

def make_my_tools(jail_root: Path) -> list[BaseTool]:
    @tool
    def my_tool(arg: str) -> str:
        """Short, model-facing description.

        Longer notes about behavior, error modes, examples. The model sees this.
        """
        # use jail_root here
        return "result"

    return [my_tool]
```

Anything that takes a path argument from the model **must** route it through
`_jail(jail_root, path)` first — that's the worktree-escape check.

### 3. Wire it into `make_tools`

Open `clawd/tools/__init__.py` and add your tool to the list returned by
`make_tools`:

```python
from .my_module import make_my_tools  # or `my_tool` if it's a free function

def make_tools(jail_root: Path) -> list[BaseTool]:
    return [
        *make_fs_tools(jail_root),
        *make_shell_tools(jail_root),
        web_fetch,
        *make_my_tools(jail_root),  # or just: my_tool
    ]
```

That's it for plumbing — `clawd/agent.py` calls `make_tools` and passes the
result straight to `create_react_agent`.

### 4. (Optional) Mention it in the system prompt

If the tool has a sharp edge worth flagging (an invariant the docstring
can't carry), add a bullet under "Tool usage" in `BASE` in
`clawd/prompt.py`. Don't dump every tool — the model already gets each
tool's description. Only add prompt text for cross-tool guidance, like
"use X before Y."

### 5. Test it

The `jail` fixture in `tests/conftest.py` gives you a tmp directory to use
as the worktree root. Mirror an existing test:

```python
# tests/test_my_tool.py
from clawd.tools.my_module import make_my_tools

def test_my_tool(jail):
    [my_tool] = make_my_tools(jail)
    assert my_tool.invoke({"arg": "hello"}) == "result"
```

```bash
uv run pytest tests/test_my_tool.py -q
```

### 6. Try it in the REPL

```bash
uv run clawd
> use my_tool with the argument "hello"
```

You should see `→ my_tool({'arg': 'hello'})` in the output, followed by
your tool's return value. If you have Langfuse configured the call also
shows up in the trace alongside the existing tools.

## Common issues

- **`ValueError: path X escapes worktree Y`** — a path resolved outside the
  worktree. Either route it through `_jail()` to validate, or document
  that the tool only takes relative paths.
- **Model never calls the tool.** The docstring is the tool description —
  if it's vague, the model won't know when to use it. Make the first
  sentence a tight verb-led description ("Run a SQL query against ...").
- **Tool returns a non-string and the model errors.** Tool outputs must be
  strings (or things that stringify cleanly). Format big results yourself
  rather than returning a dict.
- **Tool runs but blocks the event loop.** A synchronous subprocess or
  `requests` call inside an async agent will stall the TUI. Use
  `asyncio.create_subprocess_exec` / `httpx.AsyncClient` (see `shell.py`
  and `web.py` for patterns).
- **Long output floods the context.** Cap it. `glob_files` truncates at
  200 lines; `web_fetch` truncates at ~10k chars. Pick a similar cap.

## Related

- [Configuration](../reference/configuration.md) — env vars (your tool can
  read its own from `os.environ` if it needs an API key).
- [Slash commands](../reference/slash-commands.md).
- `clawd/tools/fs.py` — reference patterns for jailed filesystem tools and
  the `_jail` helper.
- `clawd/tools/shell.py` — subprocess tool with timeouts.
- `clawd/tools/web.py` — standalone async tool with output capping.
