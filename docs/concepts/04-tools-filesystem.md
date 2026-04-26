# Chapter 4: Tools, part 1 — filesystem

> **Code for this chapter:** `clawd/tools/fs.py` (89 lines),
> `tests/test_jail.py`

A coding agent without filesystem tools is a chatbot. This chapter
covers the four `clawd` ships with — `read_file`, `write_file`,
`edit_file`, `glob_files` — and the `_jail` helper that keeps them from
escaping the worktree.

## The `@tool` decorator: docstrings become schemas

Before reading the code, know that `langchain_core.tools.tool` does one
non-obvious thing: **the function's docstring becomes the tool
description the model sees**. The first line is the summary; the rest is
the full description. Argument types come from the signature. So this:

```python
@tool
def read_file(path: str) -> str:
    """Read a file from disk and return its contents with line numbers."""
```

…becomes a tool schema the model receives that includes the description,
the `path: string` argument, and the return type. Every word of every
docstring in `tools/` is part of `clawd`'s prompt budget every turn. Be
deliberate about what you write.

## `_jail`: the security boundary

```python
def _jail(jail_root: Path, path: str) -> Path:
    p = Path(path).expanduser()
    if not p.is_absolute():
        p = jail_root / p
    p = p.resolve()
    root = jail_root.resolve()
    if not p.is_relative_to(root):
        raise ValueError(f"path {p} escapes worktree {root}")
    return p
```

Every filesystem tool runs every path through `_jail` first. The function
does four things, in order, and the order matters:

1. **`expanduser()`** — turns `~/foo` into the home directory.
2. **Resolve relative paths against `jail_root`** — so `foo.txt` means
   `<jail_root>/foo.txt`, not whatever the process's cwd happens to be.
3. **`.resolve()`** — collapses `..`, follows symlinks. Critical: if you
   skip this, an attacker can use `foo/../../etc/passwd` to escape.
4. **`is_relative_to(root)` check** — the actual jail check. `root` is
   also resolved for symmetry.

`tests/test_jail.py` enumerates the cases:

```python
def test_dotdot_escape_blocked(jail):
    with pytest.raises(ValueError, match="escapes worktree"):
        _jail(jail, "../../etc/passwd")

def test_tilde_expansion_blocked_when_outside(jail):
    with pytest.raises(ValueError, match="escapes worktree"):
        _jail(jail, "~/some-file-that-shouldnt-be-readable")
```

This is one of the most important files in `clawd` to test, because
"the model accidentally wrote to `~/.ssh/authorized_keys`" is a story you
do not want to live.

### What `_jail` does *not* protect against

Be honest about the threat model:

- **Symlinks inside the jail pointing out.** If the worktree contains a
  symlink to `/etc`, `_jail` will resolve through it and (correctly)
  reject the result. But if you `write_file` the symlink target itself,
  it's a real file inside the jail. This is fine in practice because
  worktrees start clean.
- **Race conditions.** Between `_jail` returning and the actual
  read/write happening, the path could be replaced. Theoretical, mostly
  irrelevant on a single-user laptop.
- **The `bash` tool.** `bash` runs arbitrary shell with `cwd=jail_root`,
  so the model can absolutely run `cat /etc/passwd` if it wants to.
  Filesystem-tool jailing is about *editing*; for read-only escape,
  `bash` is the leaky surface. Covered in [chapter 5](05-tools-shell-web.md).

## `read_file`: line numbers included

```python
@tool
def read_file(path: str) -> str:
    """Read a file from disk and return its contents with line numbers."""
    p = _jail(jail_root, path)
    text = p.read_text()
    lines = text.splitlines()
    width = len(str(len(lines))) if lines else 1
    return "\n".join(f"{i + 1:>{width}}\t{line}" for i, line in enumerate(lines))
```

Returning the file with line numbers does two things:

1. **The model can give you `file:line` references** when answering
   ("the bug is at `agent.py:42`"). Without line numbers, it has to
   count, which it does badly.
2. **It eats slightly into the context budget.** A 1000-line file is
   ~5% larger with line numbers prepended. Worth it.

The format is `<line_number>\t<content>`. Tabs not spaces, so the model
can split on `\t` if it needs to recover the original content.

What's *not* here: pagination, byte limits, encoding fallbacks. A 100MB
file will OOM the process. Acceptable for a tutorial; for production
you'd want to cap and offer a `start_line`/`end_line` parameter.

## `write_file`: blunt instrument

```python
@tool
def write_file(path: str, content: str) -> str:
    """Write content to a file, creating parent directories if needed.

    Overwrites existing files.
    """
    p = _jail(jail_root, path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    return f"wrote {len(content)} bytes to {p}"
```

`write_file` is the "create from scratch" tool. It's deliberately
unfussy — no diff, no confirmation, no merge. Models default to using
`edit_file` for changes (the prompt nudges them this way), and reach for
`write_file` only for new files.

Why no merge or diff display? Because the user reviews changes with
`git diff` after the fact, not turn-by-turn. The worktree absorbs
mistakes.

## `edit_file`: exact-match, single-occurrence

```python
@tool
def edit_file(path: str, old: str, new: str) -> str:
    """Replace the exact string `old` with `new` in the file at `path`.

    Fails if `old` is not present, or if it appears more than once (in which case
    provide more surrounding context to make the match unique).
    """
    p = _jail(jail_root, path)
    text = p.read_text()
    count = text.count(old)
    if count == 0:
        raise ValueError(f"`old` string not found in {p}")
    if count > 1:
        raise ValueError(
            f"`old` string appears {count} times in {p}; "
            "provide more surrounding context to make it unique"
        )
    p.write_text(text.replace(old, new))
    return f"edited {p}"
```

This is the most consequential tool design choice in the whole project,
so it deserves real space.

### Why exact-match?

The alternatives:

- **Unified diffs** (Aider's approach). The model produces
  `--- old\n+++ new\n@@ ... @@` blocks; you parse and apply them.
  Strengths: well-known format, models from training data are decent at
  it, supports multi-edit. Weaknesses: parsing is a pain, models
  routinely produce diffs with wrong line numbers, error recovery is
  finicky.
- **Search-and-replace by regex.** Powerful, dangerous, hard to debug.
- **Range edit (replace lines N–M)**. Requires the model to count lines
  reliably. They don't.
- **Exact-match string replace** (Claude Code's `Edit`, ours). The model
  produces the literal text that's currently in the file plus the
  literal replacement. Strengths: no parsing, error messages are
  trivial, easy to debug. Weaknesses: token-expensive (you're sending
  the surrounding context twice), and the model has to have *read* the
  exact text first.

Exact-match wins on debuggability. When it fails, the failure mode is
always "the model guessed at the file contents instead of reading them
first," and the fix is always the same: the model reads the file and
retries. Other formats fail in more interesting ways.

### Why single-occurrence?

Without the uniqueness check, the model could ask to replace
`return None` with `return result` in a file with seventeen
`return None`s and silently change all of them. The single-occurrence
constraint forces the model to provide enough surrounding context that
each edit unambiguously points at one location. Errors are loud, not
silent.

The cost: editing the same string in N places requires N tool calls with
N different surrounding contexts. Acceptable.

## `glob_files`: ripgrep, gitignore-aware

```python
@tool
async def glob_files(pattern: str = "*", path: str = ".") -> str:
    """..."""
    proc = await asyncio.create_subprocess_exec(
        "rg", "--files", "--glob", pattern, str(search_root),
        ...
    )
```

Why shell out to `rg` instead of using `pathlib.Path.glob`?

- **Honors `.gitignore` automatically.** Without this, every glob in a
  Python project returns thousands of `.venv/` and `__pycache__/`
  hits and blows up the model's context.
- **Fast.** Native, parallel, written in Rust. For a 100k-file repo,
  the difference is seconds vs minutes.
- **Free.** `rg` is already installed on most dev machines.

The output is capped at 200 lines with a "and N more" suffix. Models
have a way of asking "show me all files" and getting flooded; the cap
turns that into a graceful nudge to narrow the search.

What's missing: a `--type=python` shortcut, structured output, the
ability to also include hidden files. All easy adds.

## What's missing from this chapter

- **Tool error semantics.** When a tool raises, LangGraph passes the
  exception message back to the model as a "tool error" message. The
  model usually retries with a fix. Good error messages matter.
- **Concurrency.** `read_file`, `write_file`, `edit_file` are sync;
  `glob_files` is async. There's no consistency principle here — they
  could all be sync. The async ones are async because they shell out.
- **Multi-edit.** Some agents support "apply N edits to one file in one
  call." Cheaper in tokens, more work in error recovery. Out of scope.

## Exercise

Add a `delete_file` tool. Two-line implementation. Then think about
whether you actually want it — what failure modes does it open? How
does the worktree mitigate them? Would you require confirmation? Where
would the confirmation happen — in the tool, in the TUI, in the
prompt?
