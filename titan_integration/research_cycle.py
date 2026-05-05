"""Research-cycle metadata helpers.

These helpers keep research timestamps separate from market-data timestamps so
same-day repeated research runs remain auditable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


LOCAL_TIMEZONE = "Asia/Nicosia"


def utc_now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def build_research_cycle(
    *,
    ticker: str,
    requested_analysis_date: str,
    generated_at_utc: str,
    market_data_as_of: str | None,
    market_data_cutoff_timestamp: str | None = None,
    market_data_granularity: str = "1d",
    user_evidence_latest_timestamp: str | None = None,
    session_context: str | None = None,
) -> dict[str, str | None]:
    local_dt = _to_local(generated_at_utc)
    run_stamp = generated_at_utc.replace("-", "").replace(":", "").replace("Z", "Z")
    return {
        "ticker": ticker.upper(),
        "research_run_id": f"{ticker.upper()}_{run_stamp}",
        "research_generated_at_utc": generated_at_utc,
        "research_generated_at_local": local_dt.isoformat(),
        "research_timezone": LOCAL_TIMEZONE,
        "requested_analysis_date": requested_analysis_date,
        "market_data_as_of": market_data_as_of,
        "market_data_cutoff_timestamp": market_data_cutoff_timestamp,
        "market_data_granularity": market_data_granularity,
        "user_evidence_latest_timestamp": user_evidence_latest_timestamp,
        "session_context": session_context or _session_context(requested_analysis_date, market_data_as_of),
    }


def inherit_research_cycle(
    upstream: dict,
    *,
    fallback_ticker: str,
    fallback_trade_date: str,
    fallback_generated_at_utc: str,
) -> dict[str, str | None]:
    cycle = upstream.get("research_cycle")
    if isinstance(cycle, dict) and cycle.get("research_run_id"):
        return cycle
    market_data_as_of = (
        upstream.get("price_data_audit", {})
        .get("latest_bar", {})
        .get("date")
    )
    return build_research_cycle(
        ticker=fallback_ticker,
        requested_analysis_date=fallback_trade_date,
        generated_at_utc=fallback_generated_at_utc,
        market_data_as_of=market_data_as_of,
    )


def _to_local(generated_at_utc: str) -> datetime:
    value = generated_at_utc.removesuffix("Z")
    utc_dt = datetime.fromisoformat(value).replace(tzinfo=timezone.utc)
    try:
        local_zone = ZoneInfo(LOCAL_TIMEZONE)
    except ZoneInfoNotFoundError:
        local_zone = timezone.utc
    return utc_dt.astimezone(local_zone)


def _session_context(requested_analysis_date: str, market_data_as_of: str | None) -> str:
    if market_data_as_of and market_data_as_of < requested_analysis_date:
        return "Research run after latest available regular-session market data."
    return "Research run aligned with requested analysis date."
