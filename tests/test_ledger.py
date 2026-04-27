from dataclasses import dataclass
from unittest.mock import AsyncMock

import pytest
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, LLMResult

from clawd.tui.ledger import LedgerCallback, SessionLedger


@dataclass
class _FakePricing:
    input_price: float
    output_price: float
    match_pattern: str = "fake"


def _result(input_t: int, output_t: int) -> LLMResult:
    msg = AIMessage(
        content="x",
        usage_metadata={
            "input_tokens": input_t,
            "output_tokens": output_t,
            "total_tokens": input_t + output_t,
        },
    )
    return LLMResult(generations=[[ChatGeneration(message=msg)]])


def test_add_usage_accumulates_without_pricing():
    ledger = SessionLedger()
    ledger.add_usage(10, 5)
    ledger.add_usage(3, 7)
    assert ledger.input_tokens == 13
    assert ledger.output_tokens == 12
    assert ledger.total_tokens == 25
    assert ledger.cost_usd == 0.0


def test_add_usage_computes_cost_with_pricing():
    ledger = SessionLedger(pricing=_FakePricing(input_price=2e-6, output_price=8e-6))
    ledger.add_usage(1_000_000, 500_000)
    # 1M @ $2/M + 0.5M @ $8/M = $2 + $4 = $6
    assert ledger.cost_usd == pytest.approx(6.0)


def test_callback_extracts_usage():
    ledger = SessionLedger()
    cb = LedgerCallback(ledger)
    cb.on_llm_end(_result(42, 17))
    assert ledger.input_tokens == 42
    assert ledger.output_tokens == 17


def test_callback_skips_messages_without_usage():
    ledger = SessionLedger()
    cb = LedgerCallback(ledger)
    msg = AIMessage(content="no usage info here")
    result = LLMResult(generations=[[ChatGeneration(message=msg)]])
    cb.on_llm_end(result)
    assert ledger.total_tokens == 0


def test_callback_records_first_usage_block_only():
    """Multiple generations in one LLMResult — record once, not duplicated."""
    ledger = SessionLedger()
    cb = LedgerCallback(ledger)
    msg1 = AIMessage(
        content="a",
        usage_metadata={"input_tokens": 5, "output_tokens": 3, "total_tokens": 8},
    )
    msg2 = AIMessage(
        content="b",
        usage_metadata={"input_tokens": 99, "output_tokens": 99, "total_tokens": 198},
    )
    result = LLMResult(generations=[[ChatGeneration(message=msg1), ChatGeneration(message=msg2)]])
    cb.on_llm_end(result)
    assert ledger.input_tokens == 5
    assert ledger.output_tokens == 3


@pytest.mark.asyncio
async def test_refresh_pricing_caches_lookup(monkeypatch):
    fake = _FakePricing(input_price=1e-6, output_price=2e-6)
    mock_find = AsyncMock(return_value=fake)
    monkeypatch.setattr("clawd.tui.ledger.pricing_mod.find_pricing", mock_find)

    ledger = SessionLedger()
    await ledger.refresh_pricing("some-model")
    assert ledger.pricing is fake
    mock_find.assert_awaited_once_with("some-model")


@pytest.mark.asyncio
async def test_refresh_pricing_swallows_errors(monkeypatch):
    mock_find = AsyncMock(side_effect=RuntimeError("network down"))
    monkeypatch.setattr("clawd.tui.ledger.pricing_mod.find_pricing", mock_find)

    ledger = SessionLedger(pricing=None)
    await ledger.refresh_pricing("some-model")
    assert ledger.pricing is None
