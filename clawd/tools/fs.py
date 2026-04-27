import asyncio
from pathlib import Path

from langchain_core.tools import BaseTool, tool


def _jail(jail_root: Path, path: str) -> Path:
    p = Path(path).expanduser()
    if not p.is_absolute():
        p = jail_root / p
    p = p.resolve()
    root = jail_root.resolve()
    if not p.is_relative_to(root):
        raise ValueError(f"path {p} escapes worktree {root}")
    return p


def make_fs_tools(jail_root: Path) -> list[BaseTool]:
    @tool
    def read_file(path: str) -> str:
        """Read a file from disk and return its contents with line numbers."""
        p = _jail(jail_root, path)
        text = p.read_text()
        lines = text.splitlines()
        width = len(str(len(lines))) if lines else 1
        return "\n".join(f"{i + 1:>{width}}\t{line}" for i, line in enumerate(lines))

    @tool
    def write_file(path: str, content: str) -> str:
        """Write content to a file, creating parent directories if needed.

        Overwrites existing files.
        """
        p = _jail(jail_root, path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
        return f"wrote {len(content)} bytes to {p}"

    @tool
    def edit_file(path: str, old: str, new: str) -> str:
        """Replace the exact string `old` with `new` in the file at `path`.

        Returns an error message (instead of raising) if `old` is not present, or
        if it appears more than once — in which case retry with more surrounding
        context to make the match unique.
        """
        p = _jail(jail_root, path)
        text = p.read_text()
        count = text.count(old)
        if count == 0:
            return f"error: `old` string not found in {p}"
        if count > 1:
            return (
                f"error: `old` string appears {count} times in {p}; "
                "retry with more surrounding context to make it unique"
            )
        p.write_text(text.replace(old, new))
        return f"edited {p}"

    @tool
    async def glob_files(pattern: str = "*", path: str = ".") -> str:
        """Find files matching a glob pattern. Honors .gitignore, so virtualenvs, build
        artifacts, and node_modules are skipped automatically.

        Examples: '*.py', '**/*.md', 'tests/test_*.py'
        """
        search_root = _jail(jail_root, path)
        proc = await asyncio.create_subprocess_exec(
            "rg",
            "--files",
            "--glob",
            pattern,
            str(search_root),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode not in (0, 1):
            return f"ripgrep error: {stderr.decode(errors='replace')}"

        out = stdout.decode(errors="replace").strip()
        if not out:
            return "no matches"
        lines = out.splitlines()
        if len(lines) > 200:
            return "\n".join(lines[:200]) + f"\n... and {len(lines) - 200} more"
        return out

    return [read_file, write_file, edit_file, glob_files]
