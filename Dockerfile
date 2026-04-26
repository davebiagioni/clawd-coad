FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends git ripgrep \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

COPY clawd ./clawd
RUN uv sync --frozen --no-dev

WORKDIR /workspace
ENV CLAWD_WORKTREE_ROOT=/workspace/.clawd-worktrees \
    PATH=/app/.venv/bin:$PATH

ENTRYPOINT ["/app/.venv/bin/clawd"]
