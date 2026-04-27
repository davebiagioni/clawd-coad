"""Per-session token & cost accumulator + LangChain callback that feeds it."""

from dataclasses import dataclass
from typing import Any

from langchain_core.callbacks import BaseCallbackHandler

from .. import pricing as pricing_mod


@dataclass
class SessionLedger:
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    pricing: Any = None

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def add_usage(self, input_t: int, output_t: int) -> None:
        self.input_tokens += input_t
        self.output_tokens += output_t
        if self.pricing is not None:
            self.cost_usd += input_t * (self.pricing.input_price or 0) + output_t * (
                self.pricing.output_price or 0
            )

    async def refresh_pricing(self, model_name: str) -> None:
        try:
            self.pricing = await pricing_mod.find_pricing(model_name)
        except Exception:
            self.pricing = None


class LedgerCallback(BaseCallbackHandler):
    def __init__(self, ledger: SessionLedger) -> None:
        self.ledger = ledger

    def on_llm_end(self, response: Any, **kwargs: Any) -> None:
        for gen_list in response.generations:
            for gen in gen_list:
                msg = getattr(gen, "message", None)
                if msg is None:
                    continue
                usage = getattr(msg, "usage_metadata", None) or {}
                input_t = int(usage.get("input_tokens", 0) or 0)
                output_t = int(usage.get("output_tokens", 0) or 0)
                if input_t or output_t:
                    self.ledger.add_usage(input_t, output_t)
                    return
