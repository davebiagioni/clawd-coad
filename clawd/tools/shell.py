import asyncio
from pathlib import Path

from langchain_core.tools import BaseTool, tool

from .fs import _jail


def make_shell_tools(jail_root: Path) -> list[BaseTool]:
    @tool
    async def bash(command: str, timeout: int = 30) -> str:
        """Run a shell command and return stdout, stderr, and exit code.

        Default timeout is 30 seconds. The command runs with the worktree as its
        working directory. Use this for any shell operation: ls, git, running tests, etc.
        """
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(jail_root),
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except TimeoutError:
            proc.kill()
            await proc.wait()
            return f"command timed out after {timeout}s"

        parts = []
        if stdout:
            parts.append(f"stdout:\n{stdout.decode(errors='replace')}")
        if stderr:
            parts.append(f"stderr:\n{stderr.decode(errors='replace')}")
        parts.append(f"exit code: {proc.returncode}")
        return "\n".join(parts)

    @tool
    async def grep(pattern: str, path: str = ".", file_glob: str | None = None) -> str:
        """Search for a regex pattern in files using ripgrep.

        Returns matching lines as `file:line:content`. Honors .gitignore.
        Optional `file_glob` (e.g. '*.py') restricts which files are searched.
        """
        search_root = _jail(jail_root, path)
        args = ["rg", "--line-number", "--max-count", "50", "--max-columns", "300"]
        if file_glob:
            args.extend(["--glob", file_glob])
        args.extend([pattern, str(search_root)])

        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode == 1:
            return "no matches"
        if proc.returncode != 0:
            return f"ripgrep error: {stderr.decode(errors='replace')}"

        out = stdout.decode(errors="replace")
        lines = out.splitlines()
        if len(lines) > 200:
            out = "\n".join(lines[:200]) + f"\n... and {len(lines) - 200} more matches"
        return out

    return [bash, grep]
