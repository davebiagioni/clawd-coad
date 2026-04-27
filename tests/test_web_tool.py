from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest

from clawd.tools import web


class _FakeResponse:
    def __init__(self, chunks: list[bytes], content_type: str = "text/plain"):
        self._chunks = chunks
        self.headers = {"content-type": content_type}
        self.encoding = "utf-8"

    def raise_for_status(self) -> None:
        pass

    async def aiter_bytes(self) -> AsyncIterator[bytes]:
        for c in self._chunks:
            yield c


class _FakeClient:
    def __init__(self, response: _FakeResponse):
        self._response = response

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    @asynccontextmanager
    async def stream(self, method, url, headers=None):
        yield self._response


def _patch_httpx(monkeypatch, response: _FakeResponse) -> None:
    monkeypatch.setattr(web.httpx, "AsyncClient", lambda **kw: _FakeClient(response))


@pytest.mark.asyncio
async def test_returns_small_response_unchanged(monkeypatch):
    _patch_httpx(monkeypatch, _FakeResponse([b"hello world"]))
    out = await web.web_fetch.ainvoke({"url": "http://x"})
    assert out == "hello world"


@pytest.mark.asyncio
async def test_caps_oversized_response(monkeypatch):
    monkeypatch.setattr(web, "MAX_BYTES", 100)
    chunks = [b"a" * 60, b"b" * 60, b"c" * 60]
    _patch_httpx(monkeypatch, _FakeResponse(chunks))

    out = await web.web_fetch.ainvoke({"url": "http://x"})

    assert "[response capped at 100 bytes]" in out
    body = out.split("\n\n[response capped")[0]
    assert len(body) == 100
    assert set(body) == {"a", "b"}


@pytest.mark.asyncio
async def test_html_converted_to_markdown(monkeypatch):
    html = b"<html><body><h1>Hi</h1><p>there</p></body></html>"
    _patch_httpx(monkeypatch, _FakeResponse([html], content_type="text/html"))
    out = await web.web_fetch.ainvoke({"url": "http://x"})
    assert "Hi" in out
    assert "there" in out
    assert "<h1>" not in out


@pytest.mark.asyncio
async def test_html_strips_script_and_style_content(monkeypatch):
    # Google's "please enable JS" interstitial is the canonical example: tens of
    # KB of inline JS in a text/html response. Tag-stripping alone leaks the
    # script bodies into the model context and burns tokens.
    html = (
        b"<html><head><style>body{color:red}</style></head>"
        b"<body><script>console.log('SECRET_JS')</script>"
        b"<noscript>NOSCRIPT_TEXT</noscript>"
        b"<p>visible</p></body></html>"
    )
    _patch_httpx(monkeypatch, _FakeResponse([html], content_type="text/html"))
    out = await web.web_fetch.ainvoke({"url": "http://x"})
    assert "visible" in out
    assert "SECRET_JS" not in out
    assert "color:red" not in out
    assert "NOSCRIPT_TEXT" not in out
