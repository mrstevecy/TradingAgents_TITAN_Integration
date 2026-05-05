"""yfinance adapter for broad prototype price coverage."""

from __future__ import annotations

from datetime import date
from typing import Any

from .base import DataProvider
from .schemas import DataProviderError, PriceBar, ProviderCapability, SourceAudit


class YFinanceProvider(DataProvider):
    name = "yfinance"
    capabilities = (ProviderCapability.PRICE_BARS,)

    def get_price_bars(
        self,
        symbol: str,
        start: date | str,
        end: date | str,
        interval: str = "1d",
    ) -> list[PriceBar]:
        try:
            import yfinance as yf
        except ImportError as exc:
            raise DataProviderError(
                "yfinance is not installed in the current Python environment"
            ) from exc

        data = yf.download(
            symbol,
            start=str(start),
            end=str(end),
            interval=interval,
            progress=False,
            auto_adjust=False,
            threads=False,
        )
        if data.empty:
            raise DataProviderError(f"yfinance returned no data for {symbol}")

        if hasattr(data.columns, "levels"):
            data.columns = data.columns.get_level_values(0)

        audit = SourceAudit.now(
            provider=self.name,
            source_url="https://finance.yahoo.com/",
            license_note=(
                "Unofficial Yahoo Finance access through yfinance; suitable for "
                "research prototypes, not sole institutional source."
            ),
            reliability="prototype",
            raw_reference=f"yf.download({symbol}, {start}, {end}, {interval})",
        )

        bars: list[PriceBar] = []
        for index, row in data.iterrows():
            bars.append(
                PriceBar(
                    symbol=symbol.upper(),
                    date=str(index.date()),
                    open=_float(row, "Open"),
                    high=_float(row, "High"),
                    low=_float(row, "Low"),
                    close=_float(row, "Close"),
                    volume=_int_or_none(row, "Volume"),
                    adjusted_close=_float_or_none(row, "Adj Close"),
                    source=audit,
                )
            )
        return bars


def _float(row: Any, key: str) -> float:
    value = row.get(key)
    if value is None:
        raise DataProviderError(f"Missing required yfinance field: {key}")
    return float(value)


def _float_or_none(row: Any, key: str) -> float | None:
    value = row.get(key)
    if value is None:
        return None
    return float(value)


def _int_or_none(row: Any, key: str) -> int | None:
    value = row.get(key)
    if value is None:
        return None
    return int(value)

