from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Protocol

from earnings_export.options_models import OptionChainSnapshot, ProviderCapability


@dataclass(frozen=True)
class ProviderResult:
    snapshot: OptionChainSnapshot | None
    capability: ProviderCapability

    @classmethod
    def unavailable(cls, provider: str, code: str, message: str | None = None) -> ProviderResult:
        return cls(
            snapshot=None,
            capability=ProviderCapability(
                provider=provider,
                available=False,
                code=code,
                message=message,
            ),
        )


class OptionsDataProvider(Protocol):
    name: str

    def fetch_current_chain(self, symbol: str) -> ProviderResult:
        raise NotImplementedError

    def fetch_historical_chain(self, symbol: str, as_of: date) -> ProviderResult:
        raise NotImplementedError
