import langfuse
import langfuse.langchain
import pytest

from clawd import tracing
from clawd.agent import Session


def _set_keys(monkeypatch, public, secret, host=None):
    monkeypatch.setattr(tracing.langfuse_settings, "public_key", public)
    monkeypatch.setattr(tracing.langfuse_settings, "secret_key", secret)
    monkeypatch.setattr(tracing.langfuse_settings, "host", host)


@pytest.mark.parametrize(
    "public,secret",
    [(None, None), ("pk-test", None), (None, "sk-test"), ("", "")],
)
def test_make_handler_returns_none_without_both_keys(monkeypatch, public, secret):
    _set_keys(monkeypatch, public, secret)
    assert tracing.make_langfuse_handler() is None


def test_make_handler_constructs_with_expected_kwargs(monkeypatch):
    _set_keys(monkeypatch, "pk-test", "sk-test", host="http://localhost:3000")

    captured = {}

    class FakeLangfuse:
        def __init__(self, **kwargs):
            captured["init_kwargs"] = kwargs

    class FakeHandler:
        pass

    monkeypatch.setattr(langfuse, "Langfuse", FakeLangfuse)
    monkeypatch.setattr(langfuse.langchain, "CallbackHandler", FakeHandler)

    handler = tracing.make_langfuse_handler()

    assert isinstance(handler, FakeHandler)
    assert captured["init_kwargs"] == {
        "public_key": "pk-test",
        "secret_key": "sk-test",
        "host": "http://localhost:3000",
    }


def test_make_handler_passes_none_host_through(monkeypatch):
    """User can omit LANGFUSE_HOST and rely on the SDK's default (cloud)."""
    _set_keys(monkeypatch, "pk-test", "sk-test", host=None)

    captured = {}
    monkeypatch.setattr(
        langfuse, "Langfuse", lambda **kw: captured.setdefault("kw", kw) or object()
    )
    monkeypatch.setattr(langfuse.langchain, "CallbackHandler", lambda: object())

    tracing.make_langfuse_handler()

    assert captured["kw"]["host"] is None


def test_flush_is_noop_without_keys(monkeypatch):
    _set_keys(monkeypatch, None, None)

    def boom():
        raise AssertionError("get_client should not be called when disabled")

    monkeypatch.setattr(langfuse, "get_client", boom)

    tracing.flush()  # must not raise


def test_flush_calls_client_flush_when_configured(monkeypatch):
    _set_keys(monkeypatch, "pk-test", "sk-test")

    flushed = []

    class FakeClient:
        def flush(self):
            flushed.append(True)

    monkeypatch.setattr(langfuse, "get_client", lambda: FakeClient())

    tracing.flush()

    assert flushed == [True]


def test_session_callbacks_default_is_empty():
    s = Session(agent=object(), jail_root=None, branch="x")
    assert s.callbacks == []


def test_session_two_instances_have_independent_callbacks():
    """Guard against the classic mutable-default-argument bug."""
    a = Session(agent=object(), jail_root=None, branch="a")
    b = Session(agent=object(), jail_root=None, branch="b")
    a.callbacks.append("sentinel")
    assert b.callbacks == []
