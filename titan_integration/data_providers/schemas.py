"""Shared schemas for the Titan data-provider abstraction.

The first implementation is intentionally small: enough to normalize price
bars, official fundamentals, and source-audit metadata before the Titan wrapper
starts validating TradingAgents output.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class ProviderCapability(str, Enum):
    """Provider capabilities used by the registry."""

    PRICE_BARS = "price_bars"
    FUNDAMENTALS = "fundamentals"
    FILINGS = "filings"
    INTRADAY = "intraday"


class DataProviderError(RuntimeError):
    """Raised when a provider cannot satisfy a normalized data request."""


@dataclass(frozen=True)
class SourceAudit:
    """Audit metadata attached to every normalized provider response."""

    provider: str
    source_url: str
    retrieved_at_utc: str
    license_note: str
    reliability: str
    raw_reference: str | None = None
    warnings: tuple[str, ...] = ()

    @classmethod
    def now(
        cls,
        *,
        provider: str,
        source_url: str,
        license_note: str,
        reliability: str,
        raw_reference: str | None = None,
        warnings: tuple[str, ...] = (),
    ) -> "SourceAudit":
        return cls(
            provider=provider,
            source_url=source_url,
            retrieved_at_utc=datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
            license_note=license_note,
            reliability=reliability,
            raw_reference=raw_reference,
            warnings=warnings,
        )


@dataclass(frozen=True)
class PriceBar:
    """Normalized OHLCV bar."""

    symbol: str
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: int | None
    adjusted_close: float | None = None
    source: SourceAudit | None = None


@dataclass(frozen=True)
class FundamentalsSnapshot:
    """Normalized fundamentals snapshot from official filings where possible."""

    symbol: str
    cik: str | None
    fiscal_period: str | None
    fiscal_year: int | None
    facts: dict[str, Any] = field(default_factory=dict)
    filings: list[dict[str, Any]] = field(default_factory=list)
    source: SourceAudit | None = None

