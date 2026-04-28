from pathlib import Path

from langchain_core.tools import BaseTool

from .dispatch import make_dispatch_tool
from .fs import make_fs_tools
from .shell import make_shell_tools
from .web import web_fetch


def make_tools(jail_root: Path) -> list[BaseTool]:
    return [
        *make_fs_tools(jail_root),
        *make_shell_tools(jail_root),
        web_fetch,
        make_dispatch_tool(jail_root),
    ]
