"""Provider registry and default free-data routing."""

from __future__ import annotations

from .base import DataProvider
from .schemas import DataProviderError, ProviderCapability


class ProviderRegistry:
    """Routes normalized data requests to registered providers."""

    def __init__(self) -> None:
        self._providers: dict[str, DataProvider] = {}

    def register(self, provider: DataProvider) -> None:
        self._providers[provider.name] = provider

    def get(self, name: str) -> DataProvider:
        try:
            return self._providers[name]
        except KeyError as exc:
            raise DataProviderError(f"Provider is not registered: {name}") from exc

    def names(self) -> list[str]:
        return sorted(self._providers)

    def providers_for(self, capability: ProviderCapability) -> list[DataProvider]:
        return [
            provider
            for provider in self._providers.values()
            if capability in provider.capabilities
        ]

    def first_for(self, capability: ProviderCapability) -> DataProvider:
        providers = self.providers_for(capability)
        if not providers:
            raise DataProviderError(f"No provider registered for {capability.value}")
        return providers[0]


def create_default_registry() -> ProviderRegistry:
    """Create the accepted free-source stack.

    Active primary order:
    - yfinance for prototype OHLCV.
    - Stooq as EOD fallback.
    - SEC EDGAR for official filings/fundamentals.

    Alpaca and Alpha Vantage remain optional adapters until keys and usage rules
    are explicitly configured.
    """

    from .sec_edgar_provider import SecEdgarProvider
    from .stooq_provider import StooqProvider
    from .yfinance_provider import YFinanceProvider

    registry = ProviderRegistry()
    registry.register(YFinanceProvider())
    registry.register(StooqProvider())
    registry.register(SecEdgarProvider())
    return registry

