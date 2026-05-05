"""Optional paid/account-backed provider placeholders.

These adapters are intentionally inactive. They document where Alpha Vantage
and Alpaca should be integrated once keys, entitlements, and usage rules are
approved.
"""

from __future__ import annotations

from .base import DataProvider
from .schemas import DataProviderError, ProviderCapability


class AlpacaBasicProvider(DataProvider):
    name = "alpaca_basic"
    capabilities = (ProviderCapability.PRICE_BARS, ProviderCapability.INTRADAY)

    def __init__(self, key_id: str | None = None, secret_key: str | None = None) -> None:
        self.key_id = key_id
        self.secret_key = secret_key

    def get_price_bars(self, *args, **kwargs):
        raise DataProviderError(
            "Alpaca Basic adapter is reserved for a later step after API keys "
            "and data-entitlement rules are configured."
        )


class AlphaVantageProvider(DataProvider):
    name = "alpha_vantage"
    capabilities = (
        ProviderCapability.PRICE_BARS,
        ProviderCapability.FUNDAMENTALS,
        ProviderCapability.INTRADAY,
    )

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key

    def get_price_bars(self, *args, **kwargs):
        raise DataProviderError(
            "Alpha Vantage adapter is optional and inactive because the free "
            "tier is limited to 25 requests/day."
        )

