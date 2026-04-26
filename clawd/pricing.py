import re
from typing import Any

from .config import langfuse_settings


def _api_client() -> Any | None:
    if not (langfuse_settings.public_key and langfuse_settings.secret_key):
        return None

    from langfuse.api.client import AsyncLangfuseAPI

    base = (langfuse_settings.host or "https://cloud.langfuse.com").rstrip("/")
    return AsyncLangfuseAPI(
        base_url=base,
        username=langfuse_settings.public_key,
        password=langfuse_settings.secret_key,
    )


async def find_pricing(model_name: str) -> Any | None:
    """Return the Langfuse model entry whose match_pattern matches `model_name`, else None.

    Returns None if Langfuse is not configured. Iterates pages until a match is found
    or the list is exhausted.
    """
    client = _api_client()
    if client is None:
        return None

    page = 1
    while True:
        result = await client.models.list(page=page, limit=100)
        for m in result.data:
            try:
                if re.match(m.match_pattern, model_name):
                    return m
            except re.error:
                continue
        if page >= result.meta.total_pages:
            return None
        page += 1


async def register_pricing(
    model_name: str,
    input_per_1m: float,
    output_per_1m: float,
) -> Any:
    """Register `model_name` in Langfuse with USD-per-1M-token pricing (TOKENS unit).

    Raises RuntimeError if Langfuse is not configured. Creates a fresh entry; if one
    already exists with the same name, Langfuse keeps the newest by start time.
    """
    client = _api_client()
    if client is None:
        raise RuntimeError("Langfuse is not configured")

    return await client.models.create(
        model_name=model_name,
        match_pattern=f"(?i)^{re.escape(model_name)}$",
        unit="TOKENS",
        input_price=input_per_1m / 1_000_000,
        output_price=output_per_1m / 1_000_000,
    )
