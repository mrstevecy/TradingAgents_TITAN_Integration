"""Report metadata and renderer hygiene helpers."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from enum import Enum
from typing import Any


class ReportMode(str, Enum):
    PRE_TRADE = "pre_trade"
    PAST_TRADE_REVIEW = "past_trade_review"
    BACKTEST = "backtest"


@dataclass(frozen=True)
class ReportDates:
    research_datetime_utc: str
    research_date: str
    market_data_as_of: str | None
    intended_trade_date: str | None
    report_mode: ReportMode
    market_session_status: str = "not_checked"

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["report_mode"] = self.report_mode.value
        return payload


@dataclass(frozen=True)
class ReportContext:
    ticker: str
    company_name: str
    research_date: str
    intended_trade_date: str | None
    market_data_as_of: str | None
    market_bar_status: str
    latest_price: float | None
    latest_price_source: str | None
    latest_price_is_eod: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class FinalDecision:
    rating: str
    actionability: str
    confidence: str
    validated_keys: list[str]
    blocked_keys: list[str]
    required_next_evidence: list[str]
    baseline_posture: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


TECHNICAL_METADATA_RE = re.compile(
    r"\b(?:sma|ema|rsi|macd|vwap|atr|bollinger|bb_|vwma|adx)\b|\$\d+(?:\.\d+)?",
    re.I,
)
NON_ISSUER_TITLE_RE = re.compile(
    r"\b(?:trend analysis|technical analysis|market analysis|fundamental analysis|sentiment|"
    r"multi[-\s]?timeframe|price snapshot|appendix|stage\s*\d+|research packet)\b",
    re.I,
)

SCRATCHPAD_PHRASES = (
    "now i have all the data",
    "i have all the data",
    "excellent! i now have",
    "now i have a comprehensive dataset",
    "comprehensive dataset",
    "let me check",
    "let me search",
    "i will now",
    "i need to",
)


def build_report_dates(
    *,
    market_data_as_of: str | None,
    requested_analysis_date: str | None = None,
    report_mode: ReportMode | str = ReportMode.PRE_TRADE,
    research_datetime_utc: datetime | None = None,
    intended_trade_date: str | None = None,
) -> ReportDates:
    mode = ReportMode(report_mode)
    now = research_datetime_utc or datetime.now(timezone.utc)
    research_date = requested_analysis_date or now.date().isoformat()
    trade_date = intended_trade_date
    if mode == ReportMode.PRE_TRADE:
        trade_date = trade_date or research_date
    return ReportDates(
        research_datetime_utc=now.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        research_date=research_date,
        market_data_as_of=market_data_as_of,
        intended_trade_date=trade_date,
        report_mode=mode,
    )


def sanitize_issuer_display_name(candidate: str | None, fallback_ticker: str) -> str:
    value = " ".join(str(candidate or "").split())
    if not value or TECHNICAL_METADATA_RE.search(value) or NON_ISSUER_TITLE_RE.search(value):
        return fallback_ticker.upper()
    return value


def assert_clean_issuer_display_name(value: str) -> None:
    if TECHNICAL_METADATA_RE.search(value) or NON_ISSUER_TITLE_RE.search(value):
        raise ValueError(f"Issuer display name contains non-issuer metadata: {value}")


def strip_agent_scratchpad(text: str | None) -> str:
    if not text:
        return ""
    lines = []
    for line in str(text).splitlines():
        lower = line.strip().lower()
        if any(phrase in lower for phrase in SCRATCHPAD_PHRASES):
            continue
        lines.append(line)
    return "\n".join(lines)


def classify_price_level(level: float | None, latest_close: float | None, tolerance_pct: float = 0.5) -> str:
    if level is None or latest_close is None:
        return "unclassified"
    if latest_close == 0:
        return "unclassified"
    distance_pct = ((float(level) - float(latest_close)) / float(latest_close)) * 100
    if abs(distance_pct) <= tolerance_pct:
        return "pivot"
    return "resistance" if distance_pct > 0 else "support"


def infer_market_bar_status(
    *,
    research_date: str | None,
    market_data_as_of: str | None,
    latest_volume: float | int | None,
    avg_volume: float | int | None,
) -> tuple[str, bool]:
    if not market_data_as_of:
        return "not_validated", False
    if research_date and market_data_as_of < research_date:
        return "delayed_or_prior_session", True
    if research_date and market_data_as_of > research_date:
        return "vendor_disagreement", False
    if latest_volume is not None and avg_volume:
        try:
            if float(latest_volume) < float(avg_volume) * 0.35:
                return "intraday_partial", False
        except (TypeError, ValueError):
            pass
    return "eod_final", True
