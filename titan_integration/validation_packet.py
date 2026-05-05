"""Titan Validation Packet Stage 1.

This module creates a pre-compliance evidence packet from a clean
TradingAgents run plus normalized data-provider outputs.

Stage 1 is deliberately conservative:
- it does not produce a final Titan report,
- it does not override TradingAgents,
- it does not claim Titan compliance,
- it marks claims as Conditional or Not Validated when source evidence is absent.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from statistics import mean
from typing import Any

from .data_providers import DataProviderError, create_default_registry
from .data_providers.schemas import FundamentalsSnapshot, PriceBar
from .equity_evidence import EvidenceStore, run_equity_data_scan
from .research_cycle import build_research_cycle, utc_now_iso
from .user_evidence import build_user_evidence_packet
from .user_technical_features import build_user_technical_feature_packet


@dataclass(frozen=True)
class EvidenceItem:
    claim: str
    status: str
    evidence: str
    source_refs: list[str] = field(default_factory=list)
    reason: str = ""


@dataclass(frozen=True)
class MandatoryEvidenceItem:
    evidence_id: str
    label: str
    asset_classes: list[str]
    status: str
    source_classes_required: list[str]
    source_classes_attempted: list[str]
    validation_result: str
    freshness: str
    gap_severity: str
    thesis_impact: str
    next_best_evidence: str
    constrained_conclusion: str


@dataclass(frozen=True)
class ValidationPacket:
    ticker: str
    trade_date: str
    generated_at_utc: str
    research_cycle: dict[str, Any]
    stage: str
    compliance_status: str
    run_metadata: dict[str, Any]
    tradingagents_final_stance: str
    price_data_audit: dict[str, Any]
    user_supplied_evidence_audit: dict[str, Any]
    user_technical_feature_audit: dict[str, Any]
    sec_fundamentals_audit: dict[str, Any]
    mandatory_equity_data_scan: dict[str, Any]
    mandatory_evidence_audit: list[MandatoryEvidenceItem]
    source_reliability_table: list[dict[str, Any]]
    claim_evidence_map: list[EvidenceItem]
    titan_evidence_gaps: list[str]
    preliminary_validation_status: dict[str, Any]
    next_required_evidence: list[str]


def build_stage1_packet(
    *,
    tradingagents_summary_path: Path,
    ticker: str | None = None,
    trade_date: str | None = None,
    input_root: Path | None = None,
) -> ValidationPacket:
    summary = json.loads(tradingagents_summary_path.read_text(encoding="utf-8"))
    ticker = (ticker or summary["ticker"]).upper()
    trade_date = trade_date or summary["trade_date"]

    registry = create_default_registry()
    price_bars, price_warning = _safe_price_bars(registry, ticker, trade_date)
    fundamentals, fundamentals_warning = _safe_fundamentals(registry, ticker)
    user_evidence = build_user_evidence_packet(
        ticker=ticker,
        trade_date=trade_date,
        input_root=input_root or Path.cwd() / "inputs",
    )
    user_features = build_user_technical_feature_packet(
        ticker=ticker,
        trade_date=trade_date,
        input_root=input_root or Path.cwd() / "inputs",
        stage1a_packet=user_evidence,
    )

    metrics = _price_metrics(price_bars, trade_date) if price_bars else {}
    final_stance = summary.get("processed_decision") or _extract_stance(
        summary.get("final_trade_decision", "")
    )

    claim_map = _build_claim_map(summary, metrics, fundamentals)
    if price_warning:
        claim_map.append(
            EvidenceItem(
                claim="Normalized price evidence is available for validation.",
                status="Not Validated",
                evidence=price_warning,
                reason="Price provider request failed or returned no usable data.",
            )
        )
    if fundamentals_warning:
        claim_map.append(
            EvidenceItem(
                claim="Official SEC fundamentals evidence is available for validation.",
                status="Not Validated",
                evidence=fundamentals_warning,
                reason="SEC provider request failed or returned no usable data.",
            )
        )
    if user_evidence.files:
        claim_map.append(
            EvidenceItem(
                claim="User-supplied multi-timeframe evidence is available for supplemental validation.",
                status="Supported",
                evidence=(
                    f"{len(user_evidence.files)} file(s), new={user_evidence.summary.get('new_file_count')}, "
                    f"already_ingested={user_evidence.summary.get('already_ingested_count')}, timeframes="
                    f"{', '.join(user_evidence.summary.get('timeframes_detected', []))}, "
                    f"latest_user_timestamp={user_evidence.summary.get('latest_user_evidence_timestamp')}"
                ),
                source_refs=["user_supplied_evidence"],
                reason=(
                    "Stage 1A detected local user-provided files and summarized them. "
                    "These supplement, but do not replace, external provider evidence."
                ),
            )
        )
    for claim in user_features.generated_claims:
        claim_map.append(
            EvidenceItem(
                claim=claim["claim"],
                status=claim["status"],
                evidence=claim["evidence"],
                source_refs=claim.get("source_refs", []),
                reason=claim["reason"],
            )
        )

    price_audit = _price_audit(price_bars, metrics, price_warning)
    sec_audit = _sec_audit(fundamentals, fundamentals_warning)

    source_table = _source_reliability(price_bars, fundamentals, price_warning)
    equity_scan = _merge_baseline_scan_fallbacks(run_equity_data_scan(ticker, trade_date), summary)
    mandatory_audit = _mandatory_evidence_audit(summary, price_bars, fundamentals)
    gaps = _titan_gaps(summary, price_bars, fundamentals, mandatory_audit)
    preliminary = _preliminary_status(claim_map, gaps, mandatory_audit)

    generated_at_utc = utc_now_iso()
    return ValidationPacket(
        ticker=ticker,
        trade_date=trade_date,
        generated_at_utc=generated_at_utc,
        research_cycle=build_research_cycle(
            ticker=ticker,
            requested_analysis_date=trade_date,
            generated_at_utc=generated_at_utc,
            market_data_as_of=price_audit.get("latest_bar", {}).get("date"),
            market_data_granularity="1d",
            user_evidence_latest_timestamp=user_evidence.summary.get("latest_user_evidence_timestamp"),
        ),
        stage="Titan Validation Packet Stage 1 - Pre-Compliance",
        compliance_status="Not Titan-Compliant",
        run_metadata={
            "input_summary_path": str(tradingagents_summary_path),
            "llm_provider": summary.get("provider"),
            "quick_think_llm": summary.get("quick_think_llm"),
            "deep_think_llm": summary.get("deep_think_llm"),
            "selected_analysts": summary.get("selected_analysts", []),
        },
        tradingagents_final_stance=final_stance,
        price_data_audit=price_audit,
        user_supplied_evidence_audit=asdict(user_evidence),
        user_technical_feature_audit=asdict(user_features),
        sec_fundamentals_audit=sec_audit,
        mandatory_equity_data_scan=equity_scan.to_dict(),
        mandatory_evidence_audit=mandatory_audit,
        source_reliability_table=source_table,
        claim_evidence_map=claim_map,
        titan_evidence_gaps=gaps,
        preliminary_validation_status=preliminary,
        next_required_evidence=_next_required_evidence(mandatory_audit),
    )


def _merge_baseline_scan_fallbacks(scan: EvidenceStore, summary: dict[str, Any]) -> EvidenceStore:
    """Use already-captured provider evidence when a local adapter is unavailable.

    Stage 1 should prefer a fresh live provider scan, but a missing optional
    Python dependency such as yfinance must not erase valid provider evidence
    captured by the baseline run in the same research cycle.
    """
    payload = summary.get("mandatory_equity_data_scan")
    if not isinstance(payload, dict):
        return scan
    try:
        baseline = EvidenceStore.from_dict(payload)
    except Exception:
        return scan
    for key in ("market.latest_price", "market.ohlcv_6m", "technical.sma_50", "technical.sma_200", "technical.ema_10", "technical.rsi_14", "technical.volume_ma_20"):
        if scan.is_usable(key):
            continue
        item = baseline.get(key)
        if item and baseline.is_usable(key):
            scan.add_item(item)
    return scan


def write_packet(packet: ValidationPacket, out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{packet.ticker}_{packet.trade_date}_stage1_validation_packet"
    json_path = out_dir / f"{stem}.json"
    md_path = out_dir / f"{stem}.md"

    payload = asdict(packet)
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(_to_markdown(payload), encoding="utf-8")
    return json_path, md_path


def _safe_price_bars(registry, ticker: str, trade_date: str) -> tuple[list[PriceBar], str | None]:
    start = (datetime.fromisoformat(trade_date) - timedelta(days=370)).date().isoformat()
    end = (datetime.fromisoformat(trade_date) + timedelta(days=1)).date().isoformat()
    try:
        return registry.get("yfinance").get_price_bars(ticker, start, end), None
    except DataProviderError as exc:
        return [], str(exc)


def _safe_fundamentals(registry, ticker: str) -> tuple[FundamentalsSnapshot | None, str | None]:
    try:
        return registry.get("sec_edgar").get_fundamentals(ticker), None
    except DataProviderError as exc:
        return None, str(exc)


def _price_metrics(bars: list[PriceBar], trade_date: str) -> dict[str, Any]:
    sorted_bars = sorted(bars, key=lambda item: item.date)
    latest = max((bar for bar in sorted_bars if bar.date <= trade_date), key=lambda item: item.date)

    closes = [bar.close for bar in sorted_bars if bar.date <= latest.date]
    volumes = [bar.volume or 0 for bar in sorted_bars if bar.date <= latest.date]
    last_20 = [bar for bar in sorted_bars if bar.date <= latest.date][-20:]
    avg_20_volume = mean([bar.volume or 0 for bar in last_20]) if last_20 else None

    eligible = [bar for bar in sorted_bars if bar.date <= latest.date]
    recent_20 = eligible[-20:]
    distribution_bar = _latest_high_volume_down_bar(recent_20, avg_20_volume)
    swing_window = eligible[-45:]
    swing_low = min(swing_window, key=lambda item: item.close) if swing_window else None
    swing_high = max(swing_window, key=lambda item: item.high) if swing_window else None
    week_52_window = eligible[-260:]
    week_52_high = max(week_52_window, key=lambda item: item.high) if week_52_window else None
    week_52_low = min(week_52_window, key=lambda item: item.low) if week_52_window else None
    distance_from_52w_low_pct = (
        ((latest.close - week_52_low.low) / week_52_low.low) * 100
        if latest and week_52_low and week_52_low.low
        else None
    )
    distance_from_52w_high_pct = (
        ((latest.close - week_52_high.high) / week_52_high.high) * 100
        if latest and week_52_high and week_52_high.high
        else None
    )

    return {
        "latest_bar": asdict(latest),
        "sma_50": _sma(closes, 50),
        "sma_200": _sma(closes, 200),
        "ema_10": _ema(closes, 10),
        "vwma_20": _vwma(sorted_bars, 20),
        "avg_20_volume": avg_20_volume,
        "recent_distribution_bar": asdict(distribution_bar) if distribution_bar else None,
        "recent_swing_high_bar": asdict(swing_high) if swing_high else None,
        "recent_swing_low_bar": asdict(swing_low) if swing_low else None,
        "week_52_high_bar": asdict(week_52_high) if week_52_high else None,
        "week_52_low_bar": asdict(week_52_low) if week_52_low else None,
        "distance_from_52w_low_pct": distance_from_52w_low_pct,
        "distance_from_52w_high_pct": distance_from_52w_high_pct,
        "reported_reference_bar": asdict(latest),
        "recent_swing_move_pct": (
            ((swing_high.high - swing_low.close) / swing_low.close) * 100 if swing_high and swing_low else None
        ),
    }


def _sma(values: list[float], window: int) -> float | None:
    if len(values) < window:
        return None
    return sum(values[-window:]) / window


def _ema(values: list[float], window: int) -> float | None:
    if len(values) < window:
        return None
    multiplier = 2 / (window + 1)
    ema = sum(values[:window]) / window
    for value in values[window:]:
        ema = (value - ema) * multiplier + ema
    return ema


def _vwma(bars: list[PriceBar], window: int) -> float | None:
    recent = bars[-window:]
    volume_sum = sum((bar.volume or 0) for bar in recent)
    if not recent or volume_sum == 0:
        return None
    return sum(bar.close * (bar.volume or 0) for bar in recent) / volume_sum


def _latest_high_volume_down_bar(bars: list[PriceBar], avg_volume: float | None) -> PriceBar | None:
    if not avg_volume:
        return None
    candidates = [
        bar
        for bar in bars
        if bar.close < bar.open and (bar.volume or 0) > avg_volume * 1.2
    ]
    return candidates[-1] if candidates else None


def _build_claim_map(
    summary: dict[str, Any],
    metrics: dict[str, Any],
    fundamentals: FundamentalsSnapshot | None,
) -> list[EvidenceItem]:
    items: list[EvidenceItem] = []
    final_text = summary.get("final_trade_decision", "")
    final_stance = summary.get("processed_decision") or _extract_stance(final_text)

    items.append(
        EvidenceItem(
            claim=f"TradingAgents final stance is {final_stance}.",
            status="Supported",
            evidence=f"Processed decision: {summary.get('processed_decision')}",
            source_refs=["TradingAgents summary"],
            reason=(
                "The claim label is generated from the processed decision for this run; "
                "Stage 1 does not assume a fixed stance across repeated ticker research."
            ),
        )
    )

    latest = metrics.get("latest_bar")
    reported_reference = metrics.get("reported_reference_bar")
    if reported_reference:
        items.append(
            EvidenceItem(
                claim="TradingAgents reference price is aligned with normalized market data.",
                status="Supported",
                evidence=(
                    f"yfinance reference bar {reported_reference['date']} "
                    f"close={reported_reference['close']:.2f}; latest fetched bar "
                    f"{latest['date']} close={latest['close']:.2f}" if latest else ""
                ),
                source_refs=["yfinance"],
                reason=(
                    "Stage 1 anchors the run to the normalized market-data bar available "
                    "for the requested trade date rather than hard-coding a prior run's "
                    "price level."
                ),
            )
        )

    distribution_bar = metrics.get("recent_distribution_bar")
    avg_20_volume = metrics.get("avg_20_volume")
    if distribution_bar and avg_20_volume:
        is_down = distribution_bar["close"] < distribution_bar["open"]
        high_volume = distribution_bar["volume"] > avg_20_volume * 1.2
        items.append(
            EvidenceItem(
                claim="A recent high-volume down day/distribution warning was detected.",
                status="Supported" if is_down and high_volume else "Conditional",
                evidence=(
                    f"{distribution_bar['date']} open={distribution_bar['open']:.2f}, "
                    f"close={distribution_bar['close']:.2f}, volume={distribution_bar['volume']:,}, "
                    f"20-day avg volume={avg_20_volume:,.0f}"
                ),
                source_refs=["yfinance"],
                reason="Price closed below open and volume exceeded the recent 20-day average threshold."
                if is_down and high_volume
                else "The direction/volume criteria were not fully satisfied.",
            )
        )

    latest_close = latest["close"] if latest else None
    if latest_close and metrics.get("ema_10") and metrics.get("sma_50") and metrics.get("sma_200"):
        items.append(
            EvidenceItem(
                claim="Price is below short-term trend but above 50-day and 200-day averages.",
                status="Supported"
                if latest_close < metrics["ema_10"]
                and latest_close > metrics["sma_50"]
                and latest_close > metrics["sma_200"]
                else "Conditional",
                evidence=(
                    f"close={latest_close:.2f}, ema_10={metrics['ema_10']:.2f}, "
                    f"sma_50={metrics['sma_50']:.2f}, sma_200={metrics['sma_200']:.2f}"
                ),
                source_refs=["yfinance"],
                reason="Computed from normalized OHLCV bars, independent of TradingAgents text.",
            )
        )

    if fundamentals:
        items.append(
            EvidenceItem(
                claim="Official SEC evidence exists for core financial statement facts.",
                status="Supported",
                evidence=f"SEC CIK={fundamentals.cik}; facts={', '.join(sorted(fundamentals.facts))}",
                source_refs=["SEC EDGAR companyfacts", "SEC submissions"],
                reason="SEC EDGAR returned CIK mapping, companyfacts, and recent filings.",
            )
        )

    guidance_status, guidance_reason = _latest_guidance_status(summary, fundamentals)
    items.append(
        EvidenceItem(
            claim="Latest company guidance must be retrieved and validated before fundamental, valuation, catalyst, or final decision synthesis.",
            status=guidance_status,
            evidence=(
                "Stage 1 scanned available TradingAgents output and SEC provider evidence for explicit issuer guidance or outlook-table language."
            ),
            source_refs=["TradingAgents generated text", "SEC EDGAR companyfacts" if fundamentals else "SEC EDGAR companyfacts unavailable"],
            reason=guidance_reason,
        )
    )

    catalyst_status, catalyst_reason = _catalyst_calendar_status(summary)
    items.append(
        EvidenceItem(
            claim="Confirmed catalyst calendar and next earnings date must be retrieved and validated before event-risk or horizon synthesis.",
            status=catalyst_status,
            evidence="Stage 1 scanned available TradingAgents output for an explicit, date-specific catalyst or earnings calendar.",
            source_refs=["TradingAgents generated text"],
            reason=catalyst_reason,
        )
    )

    positioning_status, positioning_reason = _sentiment_positioning_status(summary)
    items.append(
        EvidenceItem(
            claim="Sentiment and positioning data must be retrieved and validated before crowding, squeeze, or professional-bearish-conviction claims are used.",
            status=positioning_status,
            evidence="Stage 1 scanned available TradingAgents output for explicit short-interest, days-to-cover, or options-positioning evidence.",
            source_refs=["TradingAgents generated text"],
            reason=positioning_reason,
        )
    )

    for claim in _unverified_narrative_claims(final_text, summary):
        items.append(claim)

    return items


def _unverified_narrative_claims(final_text: str, summary: dict[str, Any]) -> list[EvidenceItem]:
    combined = "\n".join(
        str(summary.get(key, ""))
        for key in ("final_trade_decision", "news_report", "sentiment_report", "fundamentals_report")
    )
    checks = [
        ("Pentagon AI contract claim", r"Pentagon|classified AI|defense AI"),
        ("Forward valuation claim", r"forward P/E|PEG|forward EPS"),
        (
            "Ecosystem proxy claims",
            r"ecosystem|supplier|customer|supply chain|sector read[- ]?through|industry read[- ]?through|proxy evidence|peer evidence|memory cycle|infrastructure cycle",
        ),
        ("Macro/geopolitical claims", r"Iran|Fed|oil reserves|geopolitical"),
        ("Next earnings timing claim", r"late May|next earnings"),
    ]
    items: list[EvidenceItem] = []
    for label, pattern in checks:
        if re.search(pattern, combined, flags=re.IGNORECASE):
            items.append(
                EvidenceItem(
                    claim=label,
                    status="Not Validated",
                    evidence="Claim appears in TradingAgents output but Stage 1 has not yet attached independent source verification.",
                    source_refs=["TradingAgents generated text"],
                    reason=(
                        "Stage 1 validates provider-backed price/SEC evidence only. "
                        "News, macro, forward estimates, and third-party claims require a citation layer."
                    ),
                )
            )
    return items


def _latest_guidance_status(
    summary: dict[str, Any],
    fundamentals: FundamentalsSnapshot | None,
) -> tuple[str, str]:
    text_blob = json.dumps(summary, ensure_ascii=False).lower()
    guidance_negative = _has_negative_guidance_language(text_blob)
    guidance_positive = _has_positive_guidance_language(text_blob)
    if guidance_negative:
        return (
            "Not Validated",
            (
                "Available generated text indicates guidance was missing or not retrieved. "
                "This must escalate to issuer IR, SEC-hosted earnings-release exhibits, and transcripts before synthesis."
            ),
        )
    if fundamentals and guidance_positive:
        return (
            "Conditional",
            (
                "Generated text contains explicit guidance or outlook language and SEC provider evidence exists, "
                "but Stage 1 still requires Stage 2 citation linking to issuer or regulatory guidance sources before final use."
            ),
        )
    return (
        "Not Validated",
        (
            "No explicit latest issuer guidance was validated in Stage 1. "
            "Downstream citation retrieval must persistently search primary company and regulatory sources before any final thesis relies on estimates."
        ),
    )


def _catalyst_calendar_status(summary: dict[str, Any]) -> tuple[str, str]:
    text_blob = json.dumps(summary, ensure_ascii=False).lower()
    if _has_exact_earnings_or_catalyst_date(text_blob):
        return (
            "Conditional",
            (
                "Generated text contains a date-specific catalyst or earnings reference, "
                "but Stage 2 must attach issuer IR, SEC, earnings-calendar, or reputable news evidence before final synthesis."
            ),
        )
    return (
        "Not Validated",
        (
            "No exact catalyst or next-earnings date was validated in Stage 1. "
            "Approximate phrases such as late June are insufficient for event-risk and horizon logic."
        ),
    )


def _sentiment_positioning_status(summary: dict[str, Any]) -> tuple[str, str]:
    text_blob = json.dumps(summary, ensure_ascii=False).lower()
    if _has_negative_positioning_language(text_blob):
        return (
            "Not Validated",
            (
                "Generated text indicates positioning data was inferred, missing, or not retrieved. "
                "Crowding, squeeze, and professional-bearish-conviction claims must remain blocked until source-backed data is retrieved."
            ),
        )
    if _has_numeric_positioning_data(text_blob):
        return (
            "Conditional",
            (
                "Generated text contains numeric positioning language, but Stage 2 must attach FINRA/equivalent short-interest, "
                "options, or analyst-consensus evidence before final synthesis."
            ),
        )
    return (
        "Not Validated",
        (
            "No validated positioning evidence was found in Stage 1. "
            "The pipeline must retrieve short interest, days to cover, options positioning, or analyst consensus before using positioning claims."
        ),
    )


def _has_negative_guidance_language(text_blob: str) -> bool:
    return any(
        phrase in text_blob
        for phrase in (
            "no forward guidance",
            "without forward guidance",
            "guidance not retrieved",
            "guidance missing",
            "not retrieved",
        )
    )


def _has_exact_earnings_or_catalyst_date(text_blob: str) -> bool:
    if not any(token in text_blob for token in ("earnings", "catalyst", "reports", "calendar")):
        return False
    month_day = re.search(
        r"\b(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+\d{1,2}(?:,\s*\d{4})?\b",
        text_blob,
        flags=re.IGNORECASE,
    )
    iso_date = re.search(r"\b20\d{2}-\d{2}-\d{2}\b", text_blob)
    numeric_date = re.search(r"\b\d{1,2}/\d{1,2}/20\d{2}\b", text_blob)
    return bool(month_day or iso_date or numeric_date)


def _has_negative_positioning_language(text_blob: str) -> bool:
    return any(
        phrase in text_blob
        for phrase in (
            "short interest / days-to-cover data — not retrieved",
            "short interest / days-to-cover data - not retrieved",
            "short interest not retrieved",
            "not explicitly debated",
            "inferred from sentiment",
            "could not assess squeeze risk",
            "cannot assess squeeze risk",
        )
    )


def _has_numeric_positioning_data(text_blob: str) -> bool:
    if not any(token in text_blob for token in ("short interest", "short float", "days to cover", "days-to-cover", "put/call", "put-call")):
        return False
    has_percent = re.search(r"\b\d+(?:\.\d+)?\s*%", text_blob) is not None
    has_days_to_cover = re.search(r"\bdays[- ]to[- ]cover\b.{0,80}\b\d+(?:\.\d+)?\b", text_blob) is not None
    has_shares_short = re.search(r"\b\d+(?:\.\d+)?\s*(?:m|million)\s+shares\s+(?:sold\s+)?short\b", text_blob) is not None
    return bool(has_percent or has_days_to_cover or has_shares_short)


def _has_positive_guidance_language(text_blob: str) -> bool:
    return any(
        phrase in text_blob
        for phrase in (
            "q3 guidance",
            "q4 guidance",
            "guidance table",
            "outlook table",
            "revenue guidance",
            "eps guidance",
            "gross margin guidance",
        )
    )


def _price_audit(bars: list[PriceBar], metrics: dict[str, Any], warning: str | None) -> dict[str, Any]:
    if warning:
        return {"status": "Not Validated", "warning": warning}
    source = asdict(bars[-1].source) if bars and bars[-1].source else None
    return {
        "status": "Available",
        "provider": "yfinance",
        "bar_count": len(bars),
        "date_range": {"start": bars[0].date if bars else None, "end": bars[-1].date if bars else None},
        "latest_bar": metrics.get("latest_bar"),
        "computed_metrics": {
            "ema_10": metrics.get("ema_10"),
            "sma_50": metrics.get("sma_50"),
            "sma_200": metrics.get("sma_200"),
            "vwma_20": metrics.get("vwma_20"),
            "avg_20_volume": metrics.get("avg_20_volume"),
            "recent_swing_move_pct": metrics.get("recent_swing_move_pct"),
            "week_52_high_bar": metrics.get("week_52_high_bar"),
            "week_52_low_bar": metrics.get("week_52_low_bar"),
            "distance_from_52w_low_pct": metrics.get("distance_from_52w_low_pct"),
            "distance_from_52w_high_pct": metrics.get("distance_from_52w_high_pct"),
        },
        "source": source,
    }


def _sec_audit(fundamentals: FundamentalsSnapshot | None, warning: str | None) -> dict[str, Any]:
    if warning:
        return {"status": "Not Validated", "warning": warning}
    if not fundamentals:
        return {"status": "Not Validated", "warning": "No SEC fundamentals snapshot returned"}
    return {
        "status": "Available",
        "provider": "sec_edgar",
        "cik": fundamentals.cik,
        "fact_keys": sorted(fundamentals.facts.keys()),
        "recent_filings": fundamentals.filings[:10],
        "source": asdict(fundamentals.source) if fundamentals.source else None,
    }


def _source_reliability(
    bars: list[PriceBar],
    fundamentals: FundamentalsSnapshot | None,
    price_warning: str | None,
) -> list[dict[str, Any]]:
    table = [
        {
            "provider": "yfinance",
            "role": "Prototype OHLCV / technical evidence",
            "reliability": "prototype",
            "status": "Available" if bars else "Not Validated",
            "notes": price_warning or "Unofficial Yahoo Finance access; do not use as sole institutional source.",
        },
        {
            "provider": "sec_edgar",
            "role": "Official filings and XBRL company facts",
            "reliability": "official",
            "status": "Available" if fundamentals else "Not Validated",
            "notes": "Official SEC source; concept mapping still requires Titan normalization.",
        },
        {
            "provider": "user_supplied_inputs",
            "role": "Supplemental local evidence, including TradingView CSV exports",
            "reliability": "user_supplied",
            "status": "Evaluated in Stage 1A",
            "notes": "User evidence is integrated as supplemental evidence and does not override provider data without explicit conflict review.",
        },
        {
            "provider": "stooq",
            "role": "EOD fallback price data",
            "reliability": "fallback",
            "status": "Configured but inactive",
            "notes": "Requires STOOQ_API_KEY before fallback can be used.",
        },
    ]
    return table


def _mandatory_evidence_audit(
    summary: dict[str, Any],
    bars: list[PriceBar],
    fundamentals: FundamentalsSnapshot | None,
) -> list[MandatoryEvidenceItem]:
    text_blob = json.dumps(summary, ensure_ascii=False).lower()
    asset_class = "Equity"
    price_supported = bool(bars)
    sec_supported = fundamentals is not None
    guidance_supported = sec_supported and not _has_negative_guidance_language(text_blob) and _has_positive_guidance_language(text_blob)
    earnings_date_supported = any(
        token in text_blob for token in ("earnings date", "reports earnings", "earnings on")
    )
    earnings_date_supported = earnings_date_supported and _has_exact_earnings_or_catalyst_date(text_blob)
    short_interest_supported = _has_numeric_positioning_data(text_blob) and not _has_negative_positioning_language(text_blob)
    valuation_basis_supported = any(
        token in text_blob for token in ("fy1", "fy2", "ntm", "forward p/e", "forward pe")
    )
    future_source_dates = _future_source_date_mentions(summary, summary.get("trade_date", ""))

    return [
        _mandatory_item(
            evidence_id="temporal_source_integrity",
            label="Research-date temporal source integrity",
            asset_class=asset_class,
            supported=not future_source_dates,
            source_classes_required=[
                "source publication dates",
                "retrieval timestamps",
                "market-data as-of dates",
                "research trade-date boundary",
            ],
            source_classes_attempted=["TradingAgents baseline text temporal scan"],
            gap_severity="Critical",
            thesis_impact=(
                "Future-dated articles, analyst notes, market closes, or inferred debate dates can create look-ahead bias "
                "and corrupt the research thesis."
            ),
            next_best_evidence=(
                "Remove or relabel future-dated evidence as post-run review evidence; replace it with sources available on or before the research date."
            ),
            constrained_conclusion=(
                "Use a constrained conclusion only; do not treat future-dated source claims as validated as-of evidence."
            ),
        ),
        _mandatory_item(
            evidence_id="latest_company_guidance",
            label="Latest company guidance and filing-backed outlook",
            asset_class=asset_class,
            supported=guidance_supported,
            source_classes_required=[
                "SEC EDGAR 8-K/10-Q/10-K",
                "issuer investor relations",
                "earnings release",
                "earnings call transcript",
            ],
            source_classes_attempted=["SEC EDGAR companyfacts"] if sec_supported else ["SEC EDGAR companyfacts failed or unavailable"],
            gap_severity="Critical",
            thesis_impact="Forward revenue, margin, EPS, valuation, and catalyst conclusions may be guidance-blind.",
            next_best_evidence="Retrieve the latest issuer earnings release, 8-K outlook table, and transcript guidance commentary.",
            constrained_conclusion="Use a constrained conclusion only; do not accept high-conviction fundamental or valuation conclusions until latest guidance is validated or explicitly blocked.",
        ),
        _mandatory_item(
            evidence_id="market_price_volume",
            label="Normalized market price, volume, and technical context",
            asset_class=asset_class,
            supported=price_supported,
            source_classes_required=["exchange/provider market data", "Yahoo/yfinance", "user-supplied technical evidence"],
            source_classes_attempted=["yfinance daily OHLCV", "user-supplied evidence scan"],
            gap_severity="Critical",
            thesis_impact="Technical levels, moving averages, volatility, and execution triggers may be stale or unsupported.",
            next_best_evidence="Retrieve recent OHLCV from a reliable market-data provider and reconcile with user-supplied timeframe files where present.",
            constrained_conclusion="Do not publish technical triggers as final without timestamped market data.",
        ),
        _mandatory_item(
            evidence_id="valuation_basis",
            label="Forward valuation basis by FY1, FY2, and NTM",
            asset_class=asset_class,
            supported=valuation_basis_supported,
            source_classes_required=["issuer guidance", "reputable estimates provider", "StockAnalysis/MarketBeat/Yahoo-style aggregator"],
            source_classes_attempted=["TradingAgents baseline text scan", "Stage 2/2C required external estimates escalation"],
            gap_severity="Critical",
            thesis_impact="Forward multiples may be mislabelled across fiscal years or treated as exact when inputs are unsupported.",
            next_best_evidence="Retrieve FY1, FY2, and NTM EPS or EBITDA estimates with source date and reconcile each multiple formula.",
            constrained_conclusion="Use only assumption-based valuation ranges until exact point-estimate inputs are externally sourced.",
        ),
        _mandatory_item(
            evidence_id="catalyst_calendar",
            label="Confirmed catalyst calendar and next earnings date",
            asset_class=asset_class,
            supported=earnings_date_supported,
            source_classes_required=["issuer IR calendar", "SEC filings", "earnings-date provider", "reputable financial news"],
            source_classes_attempted=["TradingAgents baseline text scan", "Stage 2 citation escalation required"],
            gap_severity="High",
            thesis_impact="Time horizon, event risk, and pre/post-catalyst trade plans may be incomplete.",
            next_best_evidence="Retrieve the next earnings date and material catalyst calendar from issuer IR or reputable earnings-date sources.",
            constrained_conclusion="Use broad horizon caveats and avoid binary event trade plans until catalyst dates are validated.",
        ),
        _mandatory_item(
            evidence_id="sentiment_positioning",
            label="Sentiment and positioning validation",
            asset_class=asset_class,
            supported=short_interest_supported,
            source_classes_required=["FINRA/equivalent short interest", "options/put-call provider", "analyst consensus aggregator"],
            source_classes_attempted=["TradingAgents baseline text scan", "Stage 2 citation escalation required"],
            gap_severity="High",
            thesis_impact="Crowding, squeeze, professional-bearish-conviction, and 'who is left to buy' claims may be unsupported.",
            next_best_evidence="Retrieve short float, days to cover, options positioning, and analyst consensus with source dates.",
            constrained_conclusion="Block crowding and squeeze claims until positioning data is validated; retain only caveated sentiment observations.",
        ),
    ]


def _mandatory_item(
    *,
    evidence_id: str,
    label: str,
    asset_class: str,
    supported: bool,
    source_classes_required: list[str],
    source_classes_attempted: list[str],
    gap_severity: str,
    thesis_impact: str,
    next_best_evidence: str,
    constrained_conclusion: str,
) -> MandatoryEvidenceItem:
    return MandatoryEvidenceItem(
        evidence_id=evidence_id,
        label=label,
        asset_classes=[asset_class],
        status="Supported" if supported else "Not Validated",
        source_classes_required=source_classes_required,
        source_classes_attempted=source_classes_attempted,
        validation_result=(
            "Required evidence class appears in available packet inputs."
            if supported
            else "Required evidence class is not validated in available packet inputs; persistent source-aware escalation is required before final synthesis."
        ),
        freshness="Timestamped by packet source where available" if supported else "Freshness not established",
        gap_severity="None" if supported else gap_severity,
        thesis_impact="No mandatory gap identified for this item." if supported else thesis_impact,
        next_best_evidence="Continue normal cross-checking in downstream stages." if supported else next_best_evidence,
        constrained_conclusion="May be used with source caveats." if supported else constrained_conclusion,
    )


def _future_source_date_mentions(summary: dict[str, Any], trade_date: str) -> list[str]:
    as_of = _parse_date(trade_date)
    if not as_of:
        return []
    text = json.dumps(summary, ensure_ascii=False)
    future_mentions: list[str] = []
    source_context = re.compile(
        r"(source|article|published|retrieved|market close|close|analyst|note|reuters|bloomberg|barron|yahoo finance|goldman|morgan stanley|fed|kashkari|powell|speech|speeches|debate|search).{0,140}",
        flags=re.IGNORECASE,
    )
    contexts = [match.group(0) for match in source_context.finditer(text)]
    if not contexts:
        contexts = [text]
    for context in contexts:
        if _is_future_event_context_with_asof_valid_source(context, as_of):
            continue
        for raw_date in _date_mentions(context, as_of.year):
            parsed = _parse_date(raw_date)
            if parsed and parsed > as_of:
                future_mentions.append(raw_date)
    return list(dict.fromkeys(future_mentions))


def _is_future_event_context_with_asof_valid_source(context: str, as_of: date) -> bool:
    lowered = context.lower()
    if not any(
        token in lowered
        for token in (
            "next earnings",
            "earnings date",
            "earnings calendar",
            "issuer ir calendar",
            "ir calendar",
            "event calendar",
            "catalyst calendar",
            "scheduled",
        )
    ):
        return False
    source_boundary_terms = ("retrieved", "published", "source", "issuer ir calendar", "ir calendar", "as of")
    source_dates: list[date] = []
    for match in re.finditer(r"(retrieved|published|source|issuer ir calendar|ir calendar|as of).{0,40}", context, flags=re.IGNORECASE):
        source_dates.extend(
            parsed
            for raw in _date_mentions(match.group(0), as_of.year)
            if (parsed := _parse_date(raw)) is not None
        )
    return bool(source_dates) and all(item <= as_of for item in source_dates)


def _date_mentions(text: str, default_year: int) -> list[str]:
    months = {
        "jan": "01",
        "january": "01",
        "feb": "02",
        "february": "02",
        "mar": "03",
        "march": "03",
        "apr": "04",
        "april": "04",
        "may": "05",
        "jun": "06",
        "june": "06",
        "jul": "07",
        "july": "07",
        "aug": "08",
        "august": "08",
        "sep": "09",
        "september": "09",
        "oct": "10",
        "october": "10",
        "nov": "11",
        "november": "11",
        "dec": "12",
        "december": "12",
    }
    found = re.findall(r"\b20\d{2}-\d{2}-\d{2}\b", text)
    ranged_day_month = re.findall(
        r"\b(\d{1,2})\s*[-–]\s*(\d{1,2})\s+(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)(?:\s+(20\d{2}))?\b",
        text,
        flags=re.IGNORECASE,
    )
    for _start_day, end_day, month, year in ranged_day_month:
        found.append(f"{year or default_year}-{months[month.lower()]}-{int(end_day):02d}")
    month_day = re.findall(
        r"\b(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+(\d{1,2})(?:,\s*(20\d{2}))?\b",
        text,
        flags=re.IGNORECASE,
    )
    for month, day, year in month_day:
        found.append(f"{year or default_year}-{months[month.lower()]}-{int(day):02d}")
    day_month = re.findall(
        r"\b(\d{1,2})\s+(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)(?:\s+(20\d{2}))?\b",
        text,
        flags=re.IGNORECASE,
    )
    for day, month, year in day_month:
        found.append(f"{year or default_year}-{months[month.lower()]}-{int(day):02d}")
    return found


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _titan_gaps(
    summary: dict[str, Any],
    bars: list[PriceBar],
    fundamentals: FundamentalsSnapshot | None,
    mandatory_audit: list[MandatoryEvidenceItem],
) -> list[str]:
    gaps = [
        "Primary Corpus rules have not yet been applied.",
        "Secondary Corpus presentation-quality rules have not yet been applied.",
        "Activation Trigger Framework gating has not yet been applied.",
        "Validated Trading Horizon has not yet been classified.",
        "News, macro, geopolitical, and catalyst claims lack independent citation mapping.",
        "Forward estimates and valuation claims are not yet sourced from a verified estimates provider.",
        "Risk/reward levels are not yet reconciled against Titan horizon-specific evidence blocks.",
        "No final report-level self-audit has been run.",
    ]
    if not bars:
        gaps.append("Normalized price evidence is missing.")
    if not fundamentals:
        gaps.append("Official SEC fundamentals evidence is missing.")
    for item in mandatory_audit:
        if item.status != "Supported":
            gaps.append(
                f"Mandatory evidence gap ({item.gap_severity}): {item.label} - {item.thesis_impact}"
            )
    return gaps


def _preliminary_status(
    items: list[EvidenceItem],
    gaps: list[str],
    mandatory_audit: list[MandatoryEvidenceItem],
) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for item in items:
        counts[item.status] = counts.get(item.status, 0) + 1
    mandatory_counts: dict[str, int] = {}
    for item in mandatory_audit:
        mandatory_counts[item.status] = mandatory_counts.get(item.status, 0) + 1
    return {
        "overall": "Conditional - Pre-Compliance Only",
        "reason": (
            "Some price/SEC evidence is available, but Titan corpus validation, "
            "citation mapping, horizon classification, and self-audit are incomplete."
        ),
        "claim_status_counts": counts,
        "mandatory_evidence_status_counts": mandatory_counts,
        "blocking_gap_count": len(gaps),
    }


def _next_required_evidence(mandatory_audit: list[MandatoryEvidenceItem] | None = None) -> list[str]:
    required = [
        "Apply Primary Corpus rules for evidence gating.",
        "Apply Secondary Corpus report-structure and presentation standards.",
        "Add cited news/macro/catalyst source retrieval.",
        "Normalize SEC financial concepts into Titan fundamentals fields.",
        "Add forward-estimate and valuation source provider or mark those fields Not Validated.",
        "Run horizon classification independently for intraday, swing, positional, and long-term.",
        "Generate source-integrity table and final self-audit before any PDF report.",
    ]
    for item in mandatory_audit or []:
        if item.status != "Supported":
            required.append(f"{item.label}: {item.next_best_evidence}")
    return list(dict.fromkeys(required))


def _within(value: float, target: float, tolerance: float) -> str:
    return "Supported" if abs(value - target) <= tolerance else "Contradictory"


def _extract_stance(text: str) -> str:
    match = re.search(r"\b(BUY|SELL|HOLD|WAIT|SHORT|LONG)\b", text, flags=re.IGNORECASE)
    return match.group(1).title() if match else "Unknown"


def _to_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# Titan Validation Packet Stage 1: {payload['ticker']} {payload['trade_date']}",
        "",
        f"Generated UTC: {payload['generated_at_utc']}",
        f"Research Run ID: {payload.get('research_cycle', {}).get('research_run_id')}",
        f"Research Generated Local: {payload.get('research_cycle', {}).get('research_generated_at_local')}",
        f"Requested Analysis Date: {payload.get('research_cycle', {}).get('requested_analysis_date')}",
        f"Market Data As Of: {payload.get('research_cycle', {}).get('market_data_as_of')}",
        f"Compliance Status: {payload['compliance_status']}",
        f"TradingAgents Final Stance: {payload['tradingagents_final_stance']}",
        "",
        "## Run Metadata",
        "",
        f"- Provider: {payload['run_metadata'].get('llm_provider')}",
        f"- Quick model: {payload['run_metadata'].get('quick_think_llm')}",
        f"- Deep model: {payload['run_metadata'].get('deep_think_llm')}",
        f"- Analysts: {', '.join(payload['run_metadata'].get('selected_analysts', []))}",
        "",
        "## Price Data Audit",
        "",
        _code_json(payload["price_data_audit"]),
        "",
        "## SEC Fundamentals Audit",
        "",
        _code_json(payload["sec_fundamentals_audit"]),
        "",
        "## Mandatory Equity Data Scan",
        "",
        _code_json(payload.get("mandatory_equity_data_scan", {})),
        "",
        "## User-Supplied Evidence Audit",
        "",
        _code_json(payload["user_supplied_evidence_audit"]),
        "",
        "## User Technical Feature Audit",
        "",
        _code_json(payload["user_technical_feature_audit"]),
        "",
        "## Mandatory Evidence Audit",
        "",
        "| Evidence | Status | Severity | Attempted Source Classes | Thesis Impact | Next Evidence | Constrained Conclusion |",
        "|---|---|---|---|---|---|---|",
    ]
    for item in payload.get("mandatory_evidence_audit", []):
        lines.append(
            f"| {item['label']} | {item['status']} | {item['gap_severity']} | "
            f"{'; '.join(item.get('source_classes_attempted', []))} | "
            f"{item['thesis_impact']} | {item['next_best_evidence']} | "
            f"{item['constrained_conclusion']} |"
        )

    lines.extend([
        "",
        "## Source Reliability Table",
        "",
        "| Provider | Role | Reliability | Status | Notes |",
        "|---|---|---|---|---|",
    ])
    for row in payload["source_reliability_table"]:
        lines.append(
            f"| {row['provider']} | {row['role']} | {row['reliability']} | {row['status']} | {row['notes']} |"
        )

    lines.extend(["", "## Claim / Evidence Map", ""])
    for item in payload["claim_evidence_map"]:
        lines.extend(
            [
                f"### {item['status']}: {item['claim']}",
                "",
                f"Evidence: {item['evidence']}",
                "",
                f"Reason: {item['reason']}",
                "",
                f"Sources: {', '.join(item.get('source_refs', [])) or 'None'}",
                "",
            ]
        )

    lines.extend(["## Titan Evidence Gaps", ""])
    lines.extend(f"- {gap}" for gap in payload["titan_evidence_gaps"])
    lines.extend(["", "## Preliminary Validation Status", "", _code_json(payload["preliminary_validation_status"])])
    lines.extend(["", "## Next Required Evidence", ""])
    lines.extend(f"- {item}" for item in payload["next_required_evidence"])
    return "\n".join(lines) + "\n"


def _code_json(value: Any) -> str:
    return "```json\n" + json.dumps(value, indent=2, ensure_ascii=False) + "\n```"
