"""Stooq CSV adapter used as a free historical EOD fallback."""

from __future__ import annotations

import csv
import os
from datetime import date
from io import StringIO
from urllib.error import URLError
from urllib.request import Request, urlopen

from .base import DataProvider
from .schemas import DataProviderError, PriceBar, ProviderCapability, SourceAudit


class StooqProvider(DataProvider):
    name = "stooq"
    capabilities = (ProviderCapability.PRICE_BARS,)

    def get_price_bars(
        self,
        symbol: str,
        start: date | str,
        end: date | str,
        interval: str = "1d",
    ) -> list[PriceBar]:
        if interval != "1d":
            raise DataProviderError("Stooq fallback currently supports daily EOD bars only")

        normalized = _stooq_symbol(symbol)
        api_key = os.getenv("STOOQ_API_KEY")
        url = f"https://stooq.com/q/d/l/?s={normalized}&d1={_yyyymmdd(start)}&d2={_yyyymmdd(end)}&i=d"
        if api_key:
            request_url = f"{url}&apikey={api_key}"
            audit_url = f"{url}&apikey=REDACTED"
        else:
            request_url = url
            audit_url = url
        request = Request(request_url, headers={"User-Agent": "TitanIntegration/0.1"})
        try:
            with urlopen(request, timeout=30) as response:
                payload = response.read().decode("utf-8")
        except URLError as exc:
            raise DataProviderError(f"Stooq request failed for {symbol}: {exc}") from exc

        if "Get your apikey" in payload or "apikey" in payload[:500].lower():
            raise DataProviderError(
                "Stooq CSV endpoint requires STOOQ_API_KEY. Get the key manually "
                "from https://stooq.com/q/d/?s=nvda.us&get_apikey and set it in "
                "the environment before using Stooq as fallback."
            )

        rows = list(csv.DictReader(StringIO(payload)))
        if not rows or "Date" not in rows[0]:
            raise DataProviderError(f"Stooq returned no data for {symbol}")

        audit = SourceAudit.now(
            provider=self.name,
            source_url=audit_url,
            license_note="Free Stooq CSV endpoint; use as EOD fallback and cross-check source.",
            reliability="fallback",
            raw_reference=audit_url,
        )

        bars: list[PriceBar] = []
        for row in rows:
            bars.append(
                PriceBar(
                    symbol=symbol.upper(),
                    date=row["Date"],
                    open=float(row["Open"]),
                    high=float(row["High"]),
                    low=float(row["Low"]),
                    close=float(row["Close"]),
                    volume=int(row["Volume"]) if row.get("Volume") else None,
                    adjusted_close=None,
                    source=audit,
                )
            )
        return bars


def _stooq_symbol(symbol: str) -> str:
    raw = symbol.strip().lower()
    if "." in raw:
        return raw
    return f"{raw}.us"


def _yyyymmdd(value: date | str) -> str:
    if isinstance(value, date):
        return value.strftime("%Y%m%d")
    return value.replace("-", "")
