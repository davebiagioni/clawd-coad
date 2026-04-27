# Chapter 9: Sandboxing with Docker

> **Code for this chapter:** `Dockerfile` (~17 lines),
> `scripts/clawd-sandbox` (~40 lines), `.dockerignore`

Chapter 5 ended with an honest admission: the `bash` tool runs as the
user, with the user's permissions. Chapter 6 said the same about
worktrees: a malicious agent can `rm -rf ~` from inside the worktree.
The defense both chapters offered was *blast-radius reduction*, not
access control — the agent can do anything you can do.

That's fine if you trust the model and you're working in a project
you'd accept full access to. It's not fine if you don't, or you're
poking at a CLI you cloned from GitHub ten minutes ago.

This chapter is the second UX: same `clawd`, run inside a container,
isolated from your home directory, your SSH keys, your shell history,
and everything else outside the project you point it at.

## Two UXes, one codebase

The two modes are intentionally not in tension:

- **Trust mode.** `clawd` from your terminal. Fast, no Docker
  required, full host access. The mode you've been reading about so
  far.
- **Sandbox mode.** `scripts/clawd-sandbox` from your terminal. Same
  binary inside a container, with only the project dir bind-mounted
  in.

The agent code doesn't know which mode it's in. The container is just
a different process boundary around the exact same Python.

## What isolation actually buys you

Worth being concrete, because "Docker" is often used as a synonym for
"safe" without saying what's actually being prevented.

| Concern                                  | Trust mode    | Sandbox mode |
|------------------------------------------|---------------|--------------|
| Agent reads `~/.ssh/id_rsa`              | possible      | blocked      |
| Agent reads `~/.aws/credentials`         | possible      | blocked      |
| Agent reads your shell history           | possible      | blocked      |
| Agent `rm -rf ~`                         | possible      | blocked      |
| Agent kills/signals host processes       | possible      | blocked      |
| Agent edits files outside `$PWD`         | possible      | blocked      |
| Agent edits files inside `$PWD`          | yes (intended)| yes (intended)|
| Agent does anything with API keys you put in `.env` | yes | yes |
| Agent makes outbound network calls       | yes           | yes (see gaps) |

The big wins are credential isolation and filesystem isolation. The
agent in a container literally cannot see `~/.ssh`, regardless of how
clever the prompt that drove it there was. That's a categorical
difference from any amount of bash command filtering.

The non-wins are also worth naming. The agent can still:

- Burn through whatever API budget the keys in `.env` allow.
- Make any outbound HTTPS call it wants, including exfiltrating the
  contents of `$PWD`. The egress gap is intentional for v1; see the
  end of the chapter.
- Modify your project files (that's the whole point). If you care
  about those, commit before invoking.

## The Dockerfile

```dockerfile
FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends git ripgrep \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

COPY clawd ./clawd
COPY README.md ./
RUN uv sync --frozen --no-dev

WORKDIR /workspace
ENV CLAWD_WORKTREE_ROOT=/workspace/.clawd-worktrees \
    PATH=/app/.venv/bin:$PATH

ENTRYPOINT ["/app/.venv/bin/clawd"]
```

Five things worth pointing out:

### 1. The base image

`ghcr.io/astral-sh/uv:python3.11-bookworm-slim` is the official `uv`
image. We use `uv` for local dev, so the container uses it too — no
divergent dependency story between host and container.

### 2. `git` and `ripgrep`

The `bash` and `grep` tools shell out to ripgrep (chapter 4–5). Git is
for the worktree machinery (chapter 6). Both have to be in the image
or the agent's tools silently break.

### 3. Two `uv sync` calls

```dockerfile
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

COPY clawd ./clawd
COPY README.md ./
RUN uv sync --frozen --no-dev
```

The first sync installs *only* the dependencies (`--no-install-project`
skips the local package), which gives Docker a stable layer cached on
the lockfile. The second sync installs the project itself, off a layer
that changes every time you edit `clawd/`. Net effect: rebuilding after
a code change takes seconds, not minutes.

### 4. `CLAWD_WORKTREE_ROOT=/workspace/.clawd-worktrees`

This is the only code change the sandbox required. In trust mode
worktrees live at `~/.clawd/worktrees/<thread_id>`. In a container
that path resolves to `/root/.clawd/...` — *inside* the container,
which evaporates on exit. So we override the worktree root to live
inside `/workspace`, which is bind-mounted from the host.

Two upsides fall out of that:

- **Worktrees survive.** Re-running `clawd-sandbox` against the same
  project picks up where you left off.
- **You can review on the host.** The worktree is just a directory
  under your project root; `git -C .clawd-worktrees/<id> diff` works
  from your normal shell.

`.clawd-worktrees/` is in `.gitignore` so the worktree directory
doesn't show up as untracked noise in the host repo.

### 5. `ENTRYPOINT` is the binary, not `uv run`

We invoke `/app/.venv/bin/clawd` directly rather than `uv run clawd`.
Saves a few hundred milliseconds at startup and means TTY stdin/stdout
flow through cleanly to Rich.

## The wrapper

```bash
#!/usr/bin/env bash
set -eo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE="clawd:latest"

ARGS=()
FORCE_BUILD=0
for arg in "$@"; do
    if [[ "$arg" == "--build" ]]; then
        FORCE_BUILD=1
    else
        ARGS+=("$arg")
    fi
done

if [[ $FORCE_BUILD -eq 1 ]] || ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
    docker build -t "$IMAGE" "$REPO_ROOT"
fi

DOCKER_ENV=()
if [[ -f .env ]]; then
    TMP_ENV=$(mktemp)
    trap 'rm -f "$TMP_ENV"' EXIT
    sed -E 's#//(127\.0\.0\.1|localhost)#//host.docker.internal#g' .env > "$TMP_ENV"
    DOCKER_ENV=(--env-file "$TMP_ENV")
fi

exec docker run --rm -it \
    --add-host=host.docker.internal:host-gateway \
    -v "$PWD:/workspace" \
    -w /workspace \
    "${DOCKER_ENV[@]}" \
    "$IMAGE" "${ARGS[@]}"
```

The wrapper exists to remove three small papercuts:

### Build-if-missing

Users shouldn't have to remember `docker build` before `docker run`.
The wrapper checks for the image and builds it once; subsequent runs
are instant. `--build` forces a rebuild after you change the
Dockerfile or bump dependencies.

### Localhost rewriting

The most common provider for `clawd` is a *local* OpenAI-compatible
server — Ollama, llama.cpp, vLLM. Their endpoints look like
`http://localhost:11434/v1`. From inside a container, `localhost` is
the container itself, not the host, so an unmodified `.env` would
have the agent talking to nothing.

The wrapper rewrites `//localhost` and `//127.0.0.1` in `.env` to
`//host.docker.internal` on the way through. The `//` prefix is just
to avoid mangling random strings that happen to contain the word
"localhost". Same trick covers Langfuse running in a host Docker
Compose stack.

### `--add-host=host.docker.internal:host-gateway`

`host.docker.internal` resolves natively on Docker Desktop (Mac,
Windows). On Linux it doesn't, unless you ask for it — which is what
`--add-host=...:host-gateway` does (Docker 20.10+). One flag, same
behavior on all three platforms.

## Alternatives we didn't pick

### Per-tool sandboxing (OpenHands-style)

Run `clawd` on the host, but spin up a long-lived container per
session and route only `bash` calls into it. More surgical — only the
untrusted code is jailed.

We rejected it because it doesn't help the threat the user actually
articulated. If you don't trust the agent enough to read your
`~/.ssh`, you also don't trust the *host process driving the agent*
to read your `~/.ssh`. Per-tool sandboxing leaves that host process
fully privileged. It also adds a lot of plumbing: container
lifecycle, an exec protocol for tool calls, file-state sync between
host and container.

For this codebase, putting the whole CLI in a container is both
simpler *and* a stronger answer to the same question.

### `devcontainer.json`

VS Code devcontainers would give you the same isolation with a nicer
"reopen in container" affordance, at the cost of pulling in a much
larger spec and assuming a particular editor. The Dockerfile + bash
wrapper is a couple of files anyone can read and modify. We can add a
devcontainer pointer later if there's demand.

## What's missing

- **Egress is wide open.** A container running with default
  networking can reach anywhere your host can. A real "untrusted
  agent" sandbox needs an outbound proxy or iptables rules
  allowlisting just the LLM endpoint. Punted for v1 because the
  credential and filesystem wins are most of the value, and proper
  egress filtering is a rabbit hole. See the exercise.
- **Ollama on Linux needs `OLLAMA_HOST=0.0.0.0`.** Ollama binds to
  loopback by default, which `host.docker.internal:host-gateway`
  can't reach. Documented, not auto-fixed.
- **No published image.** Every user runs `docker build` once.
  Pushing to GHCR is a five-line GitHub Actions job we haven't done
  yet.
- **No worktree GC inside `/workspace`.** Same gap as the host
  worktree dir from chapter 6.
- **`.git` is shared between host and container.** Running host
  `clawd` and `clawd-sandbox` against the same repo at the same time
  would collide on git's worktree bookkeeping. Don't do that.
- **API keys are still trusted.** Anything the agent can do with the
  keys you put in `.env`, the agent in the sandbox can also do. Use a
  cheap/scoped key for sandbox runs you don't trust.

## Exercise

Add an egress allowlist. The shape: a `tinyproxy` (or
`mitmproxy --mode reverse`) sidecar in a tiny `compose.yml`, set
`HTTPS_PROXY=http://proxy:8888` inside the `clawd` container, and
configure the proxy to permit only the host of `CLAWD_BASE_URL`.

The interesting parts aren't the proxy config — they're the questions
that fall out of it. Where do you read `CLAWD_BASE_URL` from? (The
host .env, before docker-compose comes up.) What do you do when the
model wants to `pip install` something? (Probably allow PyPI;
probably make that explicit.) What about `git push`? (Do you trust
the agent to push code, or only to write it?)

A good answer to those questions is most of what serious agent
sandboxing actually is.
