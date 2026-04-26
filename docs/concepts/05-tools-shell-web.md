# Chapter 5: Tools, part 2 — shell & web

> **Code for this chapter:** `clawd/tools/shell.py` (69 lines),
> `clawd/tools/web.py` (41 lines)

The filesystem tools from [chapter 4](04-tools-filesystem.md) cover
*editing* the codebase. Shell and web cover the other things a coding
agent needs to *do*: run tests, run the program, search the web,
look up an API.

## `bash`: the everything tool

```python
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
```

A coding agent without `bash` can read and edit but cannot *verify*. It
cannot run the tests. It cannot run the program. It cannot check whether
its diff applied. Adding `bash` is what turns a code-suggester into a
code-runner.

The implementation choices:

- **`create_subprocess_shell`** (not `_exec`). The model gets a real
  shell with pipes, redirection, globbing. Cost: shell injection is now
  the model's responsibility, not yours. Acceptable because the worktree
  is the sandbox.
- **`cwd=str(jail_root)`.** Pins the working directory. The model can
  still `cd /etc` *inside* the command, but every fresh `bash` call
  starts in the worktree. Important: the model has no shell state
  between calls. Each invocation is a fresh process.
- **Timeout default 30s.** Stops runaway commands (`sleep infinity`,
  infinite loops, hung network calls). The model can override by passing
  a larger value for known-long commands.
- **Output format**. Three sections: stdout, stderr, exit code. The
  exit code line is mandatory because models otherwise miss non-zero
  exits buried in stderr.

What's *not* here:

- **No command filtering.** No allowlist, no denylist. The model can run
  `rm -rf .` if it wants — and we want that to be possible, because the
  worktree means recovery is `git checkout .` away. Filtering would
  give a false sense of safety; trust the sandbox instead.
- **No streaming output.** Commands buffer fully before returning. A
  long test run that prints progress is invisible until it finishes. A
  reasonable extension: stream output back through LangGraph's
  callback channel.
- **No interactive support.** `bash` cannot answer prompts ("Are you
  sure? [y/n]"). Models adapted to this learn to pass `--yes`/`-y`
  flags or pipe `yes` in.

### The security model, said out loud

Read-write protection inside the jail comes from `_jail` (chapter 4).
But `bash` can do anything outside the jail too — it's a real shell. So
why isn't this a problem?

Two reasons:

1. **The user's shell is already this dangerous.** Anyone who runs
   `claude`/`clawd`/`aider` is implicitly trusting it with the
   permissions of their user account. Adding command filtering doesn't
   change the trust boundary; it just makes the agent feel safer than
   it is.
2. **The worktree is recoverable.** All edits land in a branch the
   user controls. They can `git diff` before merging, `git reset
   --hard` to undo, or never merge at all. The sandbox is *blast-radius
   reduction*, not access control.

For higher-trust use cases (servers, CI, untrusted-prompt scenarios),
you'd want a Docker container or a real VM. The worktree is the
laptop-friendly version of that idea.

## `grep`: ripgrep again

```python
@tool
async def grep(pattern: str, path: str = ".", file_glob: str | None = None) -> str:
    """Search for a regex pattern in files using ripgrep.

    Returns matching lines as `file:line:content`. Honors .gitignore.
    Optional `file_glob` (e.g. '*.py') restricts which files are searched.
    """
    ...
    args = ["rg", "--line-number", "--max-count", "50", "--max-columns", "300"]
    if file_glob:
        args.extend(["--glob", file_glob])
    args.extend([pattern, str(search_root)])
```

`grep` exists separately from `bash` even though `bash` could invoke
ripgrep itself. Two reasons:

1. **Discoverability.** A dedicated tool with a tight schema teaches
   the model "use me to search content" without it having to know
   ripgrep's flags.
2. **Output shaping.** `--max-count 50` per file and `--max-columns
   300` per line keep the output bounded. A model that runs
   `bash("grep -r foo .")` against a large codebase gets a context
   explosion; `grep("foo")` gets a curated 50-per-file digest.

The output format is `file:line:content` — the same convention as
`grep -n`, deliberate so the model can pipe it through other tools or
use the results as `read_file`/`edit_file` inputs.

200-line cap with "and N more matches" suffix, same pattern as
`glob_files`.

## Why a separate `grep` from `glob_files`?

They're both ripgrep wrappers. Why not one tool?

Different mental models:

- `glob_files` answers "what files exist that match this pattern?"
  (`*.py`, `tests/test_*.py`)
- `grep` answers "what lines contain this content?"
  (`def make_session`, `TODO`)

Models that have a tool per intent pick correctly. Models that have one
overloaded "search" tool with mode flags get confused about when to
pass which flag. The cost is a few extra lines of schema; the benefit is
correct tool selection.

## `web_fetch`: the only network tool

```python
@tool
async def web_fetch(url: str) -> str:
    """Fetch a URL and return its content. HTML is converted to markdown for readability.

    Follows redirects, 15-second timeout. Raw response is capped at 5 MB to bound memory;
    final output is truncated to ~10k chars.
    """
    async with (
        httpx.AsyncClient(follow_redirects=True, timeout=15.0) as client,
        client.stream("GET", url, headers={"User-Agent": "clawd/0.0.1"}) as r,
    ):
        r.raise_for_status()
        ...
```

`web_fetch` is the "look it up online" tool. The model needs API docs?
Library docs? An RFC? It fetches them.

Design choices that matter:

- **Streaming download with byte cap.** `MAX_BYTES = 5 * 1024 * 1024`.
  We could `await r.aread()` and get the whole body in one line, but
  then a misbehaving server that returns a 2GB response would OOM the
  process. Streaming with `aiter_bytes` and breaking at the cap is the
  defense.
- **HTML → markdown.** `markdownify` turns the soup of `<div>`s into
  something a model can actually read. Strips `script`, `style`,
  `noscript`. Plain-text or JSON URLs pass through unchanged.
- **10k char output cap.** Even after markdown conversion, articles
  blow context. The cap is generous enough for most docs pages, with
  a clear "[truncated]" suffix.
- **15s timeout.** Slow servers shouldn't stall the agent.
- **`follow_redirects=True`.** Most doc URLs redirect. Without this,
  the agent gets confused 301s and gives up.

What's *not* here:

- **No JS rendering.** Pages that need JavaScript to load (lots of
  modern docs sites) come back empty or with skeleton HTML. Workarounds
  involve headless Chrome (Playwright/Puppeteer); not in scope.
- **No search.** The model has to know the URL. Adding a `web_search`
  tool that hits Bing/Brave/Tavily is a common extension; it's a config
  + dependency call.
- **No POST.** Read-only by design. The agent can't accidentally
  trigger destructive HTTP calls.
- **No auth.** Public URLs only. Adding API-key support per-host is a
  reasonable extension.

## What's missing from this chapter

- **Streaming output for long-running commands.** Test suites that take
  minutes are invisible until they finish.
- **Tool composition.** Real agents often want "run command, parse
  output, decide next step." `bash` returns text; the model parses with
  its own intelligence. Works fine but is token-expensive.
- **Cost accounting.** A `bash` call that returns 10MB of test output
  is a context disaster. Capping it (truncate stdout/stderr to 50k
  chars) is a reasonable next step.

## Exercise

Add a `web_search` tool that returns the top 5 results for a query.
Pick a backend (DuckDuckGo via [ddgs], Brave Search API, Tavily — all
free tiers exist). Keep the output to title, URL, snippet per result.
Then watch what happens to your model's behavior: does it search before
fetching, or does it still try to guess URLs?

[ddgs]: https://github.com/deedy5/ddgs
