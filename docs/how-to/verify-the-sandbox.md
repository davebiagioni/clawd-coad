# How to verify the sandbox actually isolates

You've installed Docker, run `scripts/clawd-sandbox`, and clawd starts.
This recipe walks through a handful of probes that confirm the
container is doing its job: only the project is visible, host secrets
aren't reachable, the jail still holds inside the container, and edits
land where you expect them.

For setup, see [run clawd in a sandbox](run-the-sandbox.md). For the
design intent, see [chapter 9: sandboxing with Docker](../concepts/09-sandbox.md).

## Steps

### 1. Build / refresh the image

```bash
cd /path/to/clawd-coad
docker build -t clawd:latest .
```

The image is ~370 MB. Confirm it exists:

```bash
docker image ls clawd:latest
```

### 2. Smoke-test the entrypoint

```bash
docker run --rm clawd:latest --help
```

You should see the `clawd` argparse usage. If the container exits with
"detected dubious ownership" or other git errors, your image is
missing the `safe.directory` line — rebuild from a current `Dockerfile`.

### 3. Start a sandboxed session

From your target project (not `clawd-coad` itself):

```bash
cd ~/some-test-project
/path/to/clawd-coad/scripts/clawd-sandbox
```

The TUI should come up exactly as it does outside the sandbox.

### 4. Confirm the host filesystem is hidden

In the TUI, ask:

> list the contents of `~/.ssh`

Expected: the bash tool reports the directory missing or empty. The
container has its own `/root` (or `/home/...`), not yours.

Also try:

> read the file at `/Users/<your-username>/...` (or `/home/<your-username>/...`)

Expected: jail rejection (`escapes worktree`) — the model-supplied
path isn't reachable from `/workspace`.

### 5. Confirm the jail holds inside the container

> run `pwd` and then `cat /etc/shadow`

Expected: `pwd` returns `/workspace/.clawd-worktrees/<id>`. `/etc/shadow`
is readable inside the container *as root*, but it's the container's
shadow file, not your host's — confirming that "what the agent sees" is
the container's filesystem, not yours.

### 6. Confirm edits land in the bind mount

In the TUI:

> create a file `sandbox-probe.md` with the contents "ok"

Then on the host:

```bash
ls .clawd-worktrees/*/sandbox-probe.md
```

The file appears on the host, in the worktree directory inside your
project. Same `git diff` workflow as trust mode.

### 7. Tear down

`Ctrl-D` or `/exit` quits the TUI; `--rm` on the docker run means the
container disappears. The bind-mounted files persist (that's the point).

## Common issues

- **`fatal: detected dubious ownership in repository at '/workspace'`.**
  Rebuild the image (`docker build --no-cache -t clawd:latest .`). The
  current `Dockerfile` whitelists `/workspace` via `safe.directory`; an
  older cached image won't have that line.
- **`the input device is not a TTY`.** The wrapper uses `docker run -it`,
  which needs a real terminal. Run it from your interactive shell, not
  through a pipe or non-TTY runner.
- **Container starts but can't reach Ollama.** With the default Ollama
  config the wrapper injects
  `CLAWD_BASE_URL=http://host.docker.internal:11434/v1` for you. If
  Ollama itself binds loopback only (Linux default), restart it with
  `OLLAMA_HOST=0.0.0.0`. For non-default providers, see step 1 of
  [run clawd in a sandbox](run-the-sandbox.md).
- **`docker: command not found`.** Install Docker Desktop, OrbStack,
  Rancher Desktop, or Docker Engine.

## Related

- [Run clawd in a sandbox](run-the-sandbox.md) — the everyday recipe.
- [Chapter 9: sandboxing with Docker](../concepts/09-sandbox.md) — what
  the sandbox is actually buying you and what it isn't.
