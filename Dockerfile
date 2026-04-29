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

# The bind-mounted /workspace is owned by the host user, but the container runs
# as root. Without this, every git invocation inside the container fails with
# "fatal: detected dubious ownership". Safe in the sandbox: /workspace is the
# only repo we ever touch.
RUN git config --system --add safe.directory /workspace \
    && git config --system --add safe.directory '/workspace/.clawd-worktrees/*'

ENTRYPOINT ["/app/.venv/bin/clawd"]
