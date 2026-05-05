"""Provider interfaces for normalized Titan data access."""

from __future__ import annotations

from abc import ABC
from datetime import date

from .schemas import FundamentalsSnapshot, PriceBar, ProviderCapability


class DataProvider(ABC):
    """Base class for provider adapters.

    Methods intentionally raise ``NotImplementedError`` unless a provider
    explicitly supports that capability. The registry uses ``capabilities`` to
    route requests.
    """

    name: str
    capabilities: tuple[ProviderCapability, ...]

    def get_price_bars(
        self,
        symbol: str,
        start: date | str,
        end: date | str,
        interval: str = "1d",
    ) -> list[PriceBar]:
        raise NotImplementedError(f"{self.name} does not support price bars")

    def get_fundamentals(self, symbol: str) -> FundamentalsSnapshot:
        raise NotImplementedError(f"{self.name} does not support fundamentals")

    def get_filings(self, symbol: str, limit: int = 10) -> list[dict]:
        raise NotImplementedError(f"{self.name} does not support filings")

