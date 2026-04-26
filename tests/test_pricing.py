from types import SimpleNamespace

import pytest

from clawd import pricing


def _set_keys(monkeypatch, public, secret, host=None):
    monkeypatch.setattr(pricing.langfuse_settings, "public_key", public)
    monkeypatch.setattr(pricing.langfuse_settings, "secret_key", secret)
    monkeypatch.setattr(pricing.langfuse_settings, "host", host)


class FakeModelsResource:
    def __init__(self, pages):
        self._pages = pages
        self.list_calls = []
        self.create_calls = []

    async def list(self, *, page, limit):
        self.list_calls.append((page, limit))
        items = self._pages[page - 1]
        return SimpleNamespace(
            data=[SimpleNamespace(**m) for m in items],
            meta=SimpleNamespace(total_pages=len(self._pages)),
        )

    async def create(self, **kwargs):
        self.create_calls.append(kwargs)
        return SimpleNamespace(**kwargs)


def _install_fake_client(monkeypatch, fake_models):
    """Patch _api_client to return a fake AsyncLangfuseAPI exposing `fake_models`."""
    fake_client = SimpleNamespace(models=fake_models)
    monkeypatch.setattr(pricing, "_api_client", lambda: fake_client)
    return fake_client


def test_api_client_returns_none_without_keys(monkeypatch):
    _set_keys(monkeypatch, None, None)
    assert pricing._api_client() is None


def test_api_client_constructs_when_configured(monkeypatch):
    _set_keys(monkeypatch, "pk-test", "sk-test", host="http://localhost:3000")
    client = pricing._api_client()
    assert client is not None  # just confirms it constructs without error


def test_api_client_strips_trailing_slash_on_host(monkeypatch):
    """The Langfuse SDK builds paths as `api/public/...`; trailing slash on host doubles it."""
    _set_keys(monkeypatch, "pk-test", "sk-test", host="http://localhost:3000/")
    captured = {}

    class FakeAPI:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    import langfuse.api.client as api_mod

    monkeypatch.setattr(api_mod, "AsyncLangfuseAPI", FakeAPI)
    pricing._api_client()
    assert captured["base_url"] == "http://localhost:3000"


@pytest.mark.asyncio
async def test_find_pricing_returns_none_when_disabled(monkeypatch):
    _set_keys(monkeypatch, None, None)
    assert await pricing.find_pricing("any-model") is None


@pytest.mark.asyncio
async def test_find_pricing_matches_by_regex(monkeypatch):
    _set_keys(monkeypatch, "pk", "sk")
    fake = FakeModelsResource(
        pages=[
            [
                {"match_pattern": "(?i)^gpt-4o$", "input_price": 1e-6, "output_price": 2e-6},
                {"match_pattern": "(?i)^qwen2\\.5-coder:7b$", "input_price": 0, "output_price": 0},
            ]
        ]
    )
    _install_fake_client(monkeypatch, fake)

    match = await pricing.find_pricing("qwen2.5-coder:7b")

    assert match is not None
    assert match.match_pattern == "(?i)^qwen2\\.5-coder:7b$"


@pytest.mark.asyncio
async def test_find_pricing_returns_none_when_no_match(monkeypatch):
    _set_keys(monkeypatch, "pk", "sk")
    fake = FakeModelsResource(pages=[[{"match_pattern": "(?i)^gpt-4o$"}]])
    _install_fake_client(monkeypatch, fake)

    assert await pricing.find_pricing("qwen2.5-coder:7b") is None


@pytest.mark.asyncio
async def test_find_pricing_paginates(monkeypatch):
    _set_keys(monkeypatch, "pk", "sk")
    fake = FakeModelsResource(
        pages=[
            [{"match_pattern": "(?i)^gpt-4o$"}],
            [{"match_pattern": "(?i)^claude-sonnet-4$"}],
            [{"match_pattern": "(?i)^qwen2\\.5-coder:7b$"}],
        ]
    )
    _install_fake_client(monkeypatch, fake)

    match = await pricing.find_pricing("qwen2.5-coder:7b")

    assert match is not None
    assert [c[0] for c in fake.list_calls] == [1, 2, 3]


@pytest.mark.asyncio
async def test_find_pricing_skips_invalid_regex(monkeypatch):
    """A bogus stored pattern shouldn't blow up the whole query."""
    _set_keys(monkeypatch, "pk", "sk")
    fake = FakeModelsResource(
        pages=[
            [
                {"match_pattern": "[unclosed-bracket"},
                {"match_pattern": "(?i)^qwen2\\.5-coder:7b$"},
            ]
        ]
    )
    _install_fake_client(monkeypatch, fake)

    match = await pricing.find_pricing("qwen2.5-coder:7b")
    assert match is not None


@pytest.mark.asyncio
async def test_register_pricing_raises_when_disabled(monkeypatch):
    _set_keys(monkeypatch, None, None)
    with pytest.raises(RuntimeError):
        await pricing.register_pricing("any-model", 0, 0)


@pytest.mark.asyncio
async def test_register_pricing_converts_per_million_to_per_token(monkeypatch):
    _set_keys(monkeypatch, "pk", "sk")
    fake = FakeModelsResource(pages=[[]])
    _install_fake_client(monkeypatch, fake)

    await pricing.register_pricing("qwen2.5-coder:7b", 0.15, 0.6)

    assert len(fake.create_calls) == 1
    call = fake.create_calls[0]
    assert call["model_name"] == "qwen2.5-coder:7b"
    assert call["unit"] == "TOKENS"
    assert call["input_price"] == pytest.approx(0.15 / 1_000_000)
    assert call["output_price"] == pytest.approx(0.6 / 1_000_000)


@pytest.mark.asyncio
async def test_register_pricing_escapes_special_chars_in_pattern(monkeypatch):
    """Model names like `qwen2.5-coder:7b` contain regex metachars (the `.`)."""
    _set_keys(monkeypatch, "pk", "sk")
    fake = FakeModelsResource(pages=[[]])
    _install_fake_client(monkeypatch, fake)

    await pricing.register_pricing("qwen2.5-coder:7b", 0, 0)

    pattern = fake.create_calls[0]["match_pattern"]
    assert pattern == r"(?i)^qwen2\.5\-coder:7b$"

    import re

    assert re.match(pattern, "qwen2.5-coder:7b")
    assert not re.match(pattern, "qwen2X5-coder:7b")  # `.` was escaped, not wildcard
