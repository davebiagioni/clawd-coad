import httpx
from langchain_core.tools import tool
from markdownify import markdownify as html_to_md

MAX_BYTES = 5 * 1024 * 1024


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
        content_type = r.headers.get("content-type", "").lower()
        encoding = r.encoding or "utf-8"
        chunks: list[bytes] = []
        total = 0
        capped = False
        async for chunk in r.aiter_bytes():
            room = MAX_BYTES - total
            if len(chunk) >= room:
                chunks.append(chunk[:room])
                capped = True
                break
            chunks.append(chunk)
            total += len(chunk)

    raw = b"".join(chunks).decode(encoding, errors="replace")
    text = html_to_md(raw, strip=["script", "style", "noscript"]) if "html" in content_type else raw

    if len(text) > 10000:
        return text[:10000] + f"\n\n[truncated; full length {len(text)} chars]"
    if capped:
        return text + f"\n\n[response capped at {MAX_BYTES} bytes]"
    return text
