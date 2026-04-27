# How to run clawd in a sandbox

You want to run clawd against an unfamiliar project, or one whose code you
don't fully trust the agent to roam through. Sandbox mode runs clawd inside
a container with only the project bind-mounted; `~/.ssh`, your shell history,
and the rest of `$HOME` are invisible to the agent.

For the design behind this — what's actually isolated, what isn't, and why
it's a separate UX rather than the default — see
[chapter 9: sandboxing with Docker](../concepts/09-sandbox.md).

## Prerequisites

- A Docker-compatible runtime running locally. Any of these work:
  Docker Desktop (Mac, Windows), Rancher Desktop (Mac, Windows, Linux),
  Colima (Mac), OrbStack (Mac), or plain Docker Engine (Linux). The
  wrapper just shells out to `docker`.
- A clone of `clawd-coad` somewhere on disk.
- The target project you want clawd to work on, in its own directory.

## Steps

### 1. Configure `.env` in the target project

```bash
cd ~/your-project
cp /path/to/clawd-coad/.env.example .env
$EDITOR .env
```

The `.env` lives in your **target project**, not in the clawd repo —
that's the directory the wrapper reads from. The wrapper rewrites
`localhost` and `127.0.0.1` inside `.env` to `host.docker.internal`
so a host-side Ollama / vLLM / Langfuse remains reachable from inside
the container.

Drop a `.env` even if you're using the Ollama default. The baked-in
default `CLAWD_BASE_URL=http://localhost:11434/v1` (in `clawd/config.py`)
goes straight into the container otherwise, where `localhost` means the
container itself.

### 2. Run the wrapper from the target project

```bash
cd ~/your-project
/path/to/clawd-coad/scripts/clawd-sandbox
```

First run builds the image (one-time, a minute or two depending on
network). Subsequent runs reuse the cached image and start instantly.
Pass `--build` to force a rebuild after editing the `Dockerfile` or
`pyproject.toml`.

You'll see the same Rich TUI as trust mode. Inside the container the
target project is bind-mounted at `/workspace`.

### 3. Drive the agent

Type prompts as usual. The TUI is identical — agent, tools, slash commands
all work the same. To verify isolation is real, ask:

> list the contents of `~/.ssh`

The bash tool reports the directory missing. Your real `~/.ssh` lives
on the host, which the container can't see.

### 4. Review changes on the host

Worktrees land at `./.clawd-worktrees/<thread_id>/` inside the **target
project** (not in `~/.clawd/` like trust mode — that path doesn't exist
in a fresh container). Review from any normal shell on the host:

```bash
git -C .clawd-worktrees/<thread_id> diff
git -C .clawd-worktrees/<thread_id> log --oneline
```

`.clawd-worktrees/` is in clawd-coad's own `.gitignore`. Add it to your
target project's `.gitignore` too if you want it hidden from `git status`.

## Common issues

- **`docker: command not found`.** Install one of the runtimes from
  prerequisites and confirm `docker` is on your `PATH`.
- **`Cannot connect to the Docker daemon`.** The runtime isn't running,
  or the CLI is pointed at the wrong context. Start the runtime, or run
  `docker context ls` and `docker context use <name>` to point at the one
  that's running.
- **Connection refused to `host.docker.internal:11434`.** Your local
  service binds to loopback only. Ollama on Linux defaults to this; set
  `OLLAMA_HOST=0.0.0.0` and restart it. Same fix for any other host-side
  service the wrapper rewrites.
- **Container can't reach Ollama and there's no `.env`.** See step 1 —
  even with defaults, the wrapper only rewrites `localhost` inside `.env`.
- **`OSError: Readme file does not exist: README.md` during build.** Stale
  Dockerfile from before [PR #8](https://github.com/davebiagioni/clawd-coad/pull/8).
  `git pull` and rerun.

## Related

- [Chapter 9: sandboxing with Docker](../concepts/09-sandbox.md) — design
  rationale, what isolation actually buys, what's still missing (egress
  filtering, etc.).
- [Configuration](../reference/configuration.md) — every `CLAWD_*` env var.
- `Dockerfile` and `scripts/clawd-sandbox` — the source of truth.
