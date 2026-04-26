import httpx
from langchain_core.tools import tool
from markdownify import markdownify as html_to_md


@tool
async def web_fetch(url: str) -> str:
    """Fetch a URL and return its content. HTML is converted to markdown for readability.

    Follows redirects, 15-second timeout. Output is truncated to ~10k chars.
    """
    async with httpx.AsyncClient(follow_redirects=True, timeout=15.0) as client:
        r = await client.get(url, headers={"User-Agent": "clawd/0.0.1"})
        r.raise_for_status()

    content_type = r.headers.get("content-type", "").lower()
    if "html" in content_type:
        text = html_to_md(r.text, strip=["script", "style", "noscript"])
    else:
        text = r.text

    if len(text) > 10000:
        text = text[:10000] + f"\n\n[truncated; full length {len(text)} chars]"
    return text
