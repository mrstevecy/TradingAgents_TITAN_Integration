"""Global equity evidence store, scan contracts, and validation gates.

This module is deliberately code-first: agents may describe evidence, but the
final equity workflow can only upgrade critical claims when the evidence store
contains source-ranked, timestamped facts or an explicit documented gap.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .data_providers import DataProviderError, create_default_registry


class EvidenceStatus(str, Enum):
    RETRIEVED = "retrieved"
    RETRIEVED_INVALID = "retrieved_invalid"
    PARTIAL = "partial"
    MISSING = "missing"
    STALE = "stale"
    BLOCKED = "blocked"
    CONTESTED = "contested"
    COMPUTED = "computed"
    PROXY_ONLY = "proxy_only"
    REJECTED = "rejected"
    EXTRACTION_FAILED = "extraction_failed"
    PAYWALLED_AFTER_RETRIES = "paywalled_after_retries"
    SOURCE_CONFLICT = "source_conflict"


class SourceLevel(int, Enum):
    SEC_OR_REGULATORY = 5
    COMPANY_IR_OR_TRANSCRIPT = 4
    MAJOR_WIRE_OR_REPUTABLE_NEWS = 3
    AGGREGATOR_OR_MARKET_DATA = 2
    COMMENTARY_OR_SOCIAL = 1


@dataclass(frozen=True)
class EvidenceItem:
    key: str
    value: Any
    status: EvidenceStatus
    source_name: str
    source_url: str | None
    source_level: SourceLevel
    as_of_date: str | None
    retrieved_at: str
    fiscal_period: str | None = None
    limitations: list[str] = field(default_factory=list)
    superseded_by: str | None = None
    retrieval_method: str | None = None
    confidence: str | None = None
    direct_or_proxy: str = "direct"


@dataclass(frozen=True)
class EvidenceGap:
    key: str
    label: str
    status: EvidenceStatus
    source_classes_attempted: list[str]
    validation_result: str
    thesis_impact: str
    next_best_evidence: str
    constrained_conclusion: str
    blocking: bool = False


@dataclass(frozen=True)
class ResolverTrace:
    evidence_key: str
    attempted_queries: list[str]
    attempted_sources: list[str]
    successful_sources: list[str]
    selected_source: str | None
    selected_value: Any
    confidence: str
    direct_or_proxy: str
    extraction_method: str
    validation_status: str
    failure_reason: str | None = None


@dataclass
class EvidenceStore:
    ticker: str
    report_date: str
    generated_at: str
    items: dict[str, EvidenceItem] = field(default_factory=dict)
    gaps: dict[str, EvidenceGap] = field(default_factory=dict)
    resolver_attempts: list[dict[str, Any]] = field(default_factory=list)
    resolver_traces: list[ResolverTrace] = field(default_factory=list)

    def add_item(self, item: EvidenceItem) -> None:
        invalid_reasons = _evidence_invalid_reasons(item.key, item)
        if invalid_reasons and item.status in {EvidenceStatus.RETRIEVED, EvidenceStatus.COMPUTED, EvidenceStatus.PARTIAL}:
            item = replace(
                item,
                status=EvidenceStatus.RETRIEVED_INVALID,
                limitations=list(dict.fromkeys(list(item.limitations or []) + invalid_reasons)),
            )
        existing = self.items.get(item.key)
        if existing is not None and item.key.endswith(".sources"):
            self.items[item.key] = _merge_source_list_item(existing, item)
            self.gaps.pop(item.key, None)
            return
        if existing is not None and not _should_replace_evidence_item(existing, item):
            self.record_attempt(
                "evidence_store_priority",
                item.key,
                item.status,
                f"Retained stronger existing evidence from {existing.source_name}; skipped weaker incoming evidence from {item.source_name}.",
            )
            return
        self.items[item.key] = item
        self.gaps.pop(item.key, None)

    def add_gap(self, gap: EvidenceGap) -> None:
        self.gaps[gap.key] = gap

    def get(self, key: str) -> EvidenceItem | None:
        return self.items.get(key)

    def status(self, key: str) -> EvidenceStatus:
        if key in self.items:
            return self.items[key].status
        if key in self.gaps:
            return self.gaps[key].status
        return EvidenceStatus.MISSING

    def value(self, key: str, default: Any = None) -> Any:
        item = self.items.get(key)
        return item.value if item else default

    def is_usable(self, key: str) -> bool:
        return self.status(key) in {EvidenceStatus.RETRIEVED, EvidenceStatus.COMPUTED}

    def record_attempt(self, resolver: str, key: str, status: EvidenceStatus, detail: str) -> None:
        self.resolver_attempts.append(
            {
                "resolver": resolver,
                "key": key,
                "status": status.value,
                "detail": detail,
                "attempted_at": utc_now_iso(),
            }
        )

    def record_trace(self, trace: ResolverTrace) -> None:
        self.resolver_traces.append(trace)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ticker": self.ticker,
            "report_date": self.report_date,
            "generated_at": self.generated_at,
            "items": {key: _enum_safe(asdict(item)) for key, item in self.items.items()},
            "gaps": {key: _enum_safe(asdict(gap)) for key, gap in self.gaps.items()},
            "resolver_attempts": list(self.resolver_attempts),
            "resolver_traces": [_enum_safe(asdict(trace)) for trace in self.resolver_traces],
            "status_counts": self.status_counts(),
            "blocking_gaps": [asdict(gap) for gap in self.gaps.values() if gap.blocking],
        }

    def status_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for item in self.items.values():
            counts[item.status.value] = counts.get(item.status.value, 0) + 1
        for gap in self.gaps.values():
            counts[gap.status.value] = counts.get(gap.status.value, 0) + 1
        return counts

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "EvidenceStore":
        store = cls(
            ticker=payload["ticker"],
            report_date=payload["report_date"],
            generated_at=payload.get("generated_at", utc_now_iso()),
        )
        for key, item in payload.get("items", {}).items():
            store.items[key] = EvidenceItem(
                **{
                    **item,
                    "status": EvidenceStatus(item["status"]),
                    "source_level": SourceLevel(item["source_level"]),
                    "direct_or_proxy": item.get("direct_or_proxy", "direct"),
                }
            )
        for key, gap in payload.get("gaps", {}).items():
            store.gaps[key] = EvidenceGap(
                **{
                    **gap,
                    "status": EvidenceStatus(gap["status"]),
                }
            )
        store.resolver_attempts = list(payload.get("resolver_attempts", []))
        store.resolver_traces = [ResolverTrace(**trace) for trace in payload.get("resolver_traces", [])]
        return store

    def agent_context(self) -> str:
        lines = [
            f"MANDATORY EQUITY EVIDENCE STORE for {self.ticker} as of {self.report_date}",
            "Agents must use these facts before inherited narrative claims.",
        ]
        for key in sorted(self.items):
            item = self.items[key]
            source_url = f"; url={item.source_url}" if item.source_url else ""
            lines.append(
                f"- {key}: {item.value} [{item.status.value}; {item.source_name}; "
                f"as_of={item.as_of_date}; source_type={item.direct_or_proxy}; confidence={item.confidence or 'n/a'}{source_url}]"
            )
        link_rows = []
        for item in sorted(self.items.values(), key=lambda row: row.key):
            if item.source_url and item.status in {EvidenceStatus.RETRIEVED, EvidenceStatus.COMPUTED, EvidenceStatus.PARTIAL}:
                link_rows.append(f"- {item.key}: {item.source_name} -> {item.source_url}")
        if link_rows:
            lines.append("SOURCE LINKS AVAILABLE TO AGENTS:")
            lines.extend(link_rows[:40])
        if self.resolver_traces:
            lines.append("DYNAMIC RAG RESOLVER TRACE SUMMARY:")
            for trace in self.resolver_traces[-12:]:
                selected = trace.selected_source or "unresolved"
                queries = " | ".join(trace.attempted_queries[:3])
                lines.append(f"- {trace.evidence_key}: {trace.validation_status}; selected={selected}; queries={queries}")
        for key in sorted(self.gaps):
            gap = self.gaps[key]
            lines.append(
                f"- GAP {key}: {gap.status.value}; attempted={', '.join(gap.source_classes_attempted)}; "
                f"impact={gap.thesis_impact}"
            )
        return "\n".join(lines)

    def do_not_claim_context(self) -> str:
        blocked = [gap for gap in self.gaps.values() if gap.blocking or gap.status != EvidenceStatus.RETRIEVED]
        if not blocked:
            return "No blocked equity evidence claims are currently registered."
        lines = ["DO-NOT-CLAIM LIST: Agents may discuss these only as gaps, rejected claims, or uncertainty."]
        for gap in sorted(blocked, key=lambda item: item.key):
            lines.append(f"- {gap.key}: {gap.constrained_conclusion}")
        return "\n".join(lines)


SOURCE_PERMISSIONS: dict[str, tuple[str, ...]] = {
    "guidance.management": ("investor", "issuer ir", "sec.gov", "reuters", "bloomberg", "cnbc", "transcript", "earnings release", "issuer_ir"),
    "capex.guidance": ("investor", "issuer ir", "sec.gov", "10-q", "10-k", "8-k", "reuters", "bloomberg", "cnbc", "transcript", "earnings release", "issuer_ir", "motley", "fool.com", "marketbeat"),
    "business.rpo_or_backlog": ("investor", "issuer ir", "sec.gov", "10-q", "10-k", "earnings release", "issuer_ir"),
    "options.put_call": ("barchart", "fintel", "options"),
    "consensus.analyst": ("marketbeat", "tipranks", "stockanalysis", "factset", "lseg"),
    "positioning.short_interest": ("finra", "nasdaq", "marketbeat", "benzinga", "fintel"),
    "short_interest.shares_short": ("finra", "nasdaq", "marketbeat", "benzinga", "fintel"),
    "earnings.actual_vs_consensus": ("marketbeat", "ibd", "factset", "lseg", "stockanalysis", "reuters"),
    "fundamentals.latest_earnings_release": ("investor", "sec.gov", "8-k", "earnings release", "issuer_ir", "earnings_event_resolver", "reuters"),
    "cashflow.fcf_inputs": ("investor", "issuer ir", "sec.gov", "10-q", "10-k", "cash flow", "cashflow", "issuer_ir", "yfinance", "computed_financial", "titan financialcalculator"),
    "cashflow.latest.ocf": ("investor", "issuer ir", "sec.gov", "10-q", "10-k", "cash flow", "cashflow", "issuer_ir", "yfinance"),
    "cashflow.latest.capex": ("investor", "issuer ir", "sec.gov", "10-q", "10-k", "cash flow", "cashflow", "issuer_ir", "yfinance", "stockanalysis"),
    "valuation.forward_pe_basis": ("marketbeat", "tipranks", "stockanalysis", "factset", "lseg", "yahoo", "yfinance", "computed_valuation", "titan forward p/e resolver", "upstream_tool_promotion"),
    "ownership.form4_90d": ("sec.gov", "form 4", "insider"),
    "ownership.13f_latest": ("sec.gov", "13f", "institutional ownership", "fintel", "nasdaq", "whalewisdom"),
}


def _should_replace_evidence_item(existing: EvidenceItem, incoming: EvidenceItem) -> bool:
    """Avoid last-writer-wins evidence loss.

    Resolver and upstream-agent capture now run through several passes. A later
    web scrape must not displace a stronger typed provider/issuer fact with an
    invalid numeric artifact or proxy value. Newer market bars and richer
    computed valuation/cash-flow objects can still replace weaker earlier items.
    """
    if existing.key == "market.latest_price":
        existing_date = _value_date(existing.value)
        incoming_date = _value_date(incoming.value)
        if existing_date and incoming_date and incoming_date != existing_date:
            return incoming_date > existing_date
    incoming_rank = _evidence_item_rank(incoming)
    existing_rank = _evidence_item_rank(existing)
    if incoming_rank != existing_rank:
        return incoming_rank > existing_rank
    incoming_detail = _value_completeness(incoming.key, incoming.value)
    existing_detail = _value_completeness(existing.key, existing.value)
    if incoming_detail != existing_detail:
        return incoming_detail > existing_detail
    return True


def _merge_source_list_item(existing: EvidenceItem, incoming: EvidenceItem) -> EvidenceItem:
    merged: list[Any] = []
    for value in list(existing.value if isinstance(existing.value, list) else [existing.value]) + list(
        incoming.value if isinstance(incoming.value, list) else [incoming.value]
    ):
        if value not in (None, "") and value not in merged:
            merged.append(value)
    winner = incoming if _evidence_item_rank(incoming) >= _evidence_item_rank(existing) else existing
    return replace(winner, value=merged, limitations=list(dict.fromkeys((existing.limitations or []) + (incoming.limitations or []))))


def _evidence_item_rank(item: EvidenceItem) -> tuple[int, int, int, int]:
    status_rank = {
        EvidenceStatus.RETRIEVED: 60,
        EvidenceStatus.COMPUTED: 58,
        EvidenceStatus.PARTIAL: 35,
        EvidenceStatus.PROXY_ONLY: 25,
        EvidenceStatus.SOURCE_CONFLICT: 20,
        EvidenceStatus.CONTESTED: 15,
        EvidenceStatus.MISSING: 10,
        EvidenceStatus.STALE: 8,
        EvidenceStatus.BLOCKED: 5,
        EvidenceStatus.EXTRACTION_FAILED: 3,
        EvidenceStatus.PAYWALLED_AFTER_RETRIES: 3,
        EvidenceStatus.RETRIEVED_INVALID: 0,
        EvidenceStatus.REJECTED: 0,
    }.get(item.status, 0)
    if _numeric_invalid_reason(item.key, item.value):
        status_rank = min(status_rank, 1)
    if item.direct_or_proxy == "proxy":
        status_rank = min(status_rank, 30)
    source_rank = int(item.source_level)
    confidence_rank = {"high": 3, "medium": 2, "low": 1}.get(str(item.confidence or "").lower(), 0)
    permitted_rank = 1 if _source_allowed_for_key(item.key, item) else 0
    method_rank = {
        "sec_api": 5,
        "issuer_ir": 5,
        "upstream_tool_capture": 4,
        "earnings_event_resolver": 5,
        "computed_financial": 4,
        "computed_valuation": 4,
        "computed_indicator": 4,
        "public_url": 2,
    }.get(str(item.retrieval_method or "").lower(), 1)
    return (status_rank, permitted_rank, source_rank, method_rank, confidence_rank)


def _value_completeness(key: str, value: Any) -> int:
    if isinstance(value, list):
        return len([item for item in value if item not in (None, "")])
    if not isinstance(value, dict):
        return 1 if value not in (None, "") else 0
    required_by_key = {
        "cashflow.fcf_inputs": ("ocf", "capex", "fcf"),
        "valuation.forward_pe_basis": ("price", "fy1_eps", "fy1_pe"),
        "positioning.short_interest": ("shares_short", "percent_float", "days_to_cover"),
        "market.latest_price": ("close", "date", "volume"),
    }
    required = required_by_key.get(key, ())
    if required:
        return sum(1 for field in required if value.get(field) not in (None, "", []))
    return sum(1 for field_value in value.values() if field_value not in (None, "", []))


def _value_date(value: Any) -> str | None:
    if isinstance(value, dict):
        candidate = value.get("date") or value.get("as_of_date")
        if isinstance(candidate, str) and re.match(r"20\d{2}-\d{2}-\d{2}", candidate):
            return candidate[:10]
    return None


def reconcile_evidence_status(store: EvidenceStore) -> EvidenceStore:
    """Apply final source and numeric validation before report rendering."""
    _derive_recent_form4_from_latest_ownership(store)
    for key, item in list(store.items.items()):
        reasons = _evidence_invalid_reasons(key, item)
        if not reasons:
            continue
        merged_limitations = list(item.limitations or [])
        for reason in reasons:
            if reason not in merged_limitations:
                merged_limitations.append(reason)
        store.items[key] = replace(
            item,
            status=EvidenceStatus.RETRIEVED_INVALID,
            limitations=merged_limitations,
        )
        store.add_gap(
            EvidenceGap(
                key=key,
                label=f"Invalid retrieved evidence for {key}",
                status=EvidenceStatus.RETRIEVED_INVALID,
                source_classes_attempted=[item.source_name or "unknown"],
                validation_result="Retrieved evidence failed final source/numeric validation.",
                thesis_impact=f"{key} cannot support final synthesis until corrected.",
                next_best_evidence="Retrieve a permitted source with plausible units and complete required fields.",
                constrained_conclusion="Discuss this only as an unresolved evidence defect.",
                blocking=bool(MANDATORY_EQUITY_KEYS.get(key, {}).get("blocking", False)),
            )
        )
    return store


def _derive_recent_form4_from_latest_ownership(store: EvidenceStore) -> None:
    if store.is_usable("ownership.form4_90d"):
        return
    latest = store.get("ownership.latest_filing")
    if not latest or not isinstance(latest.value, dict):
        return
    if str(latest.value.get("form", "")).upper() not in {"3", "4", "5"}:
        return
    candidate_date = latest.value.get("filing_date") or latest.value.get("report_date")
    if not _within_days(store.report_date, candidate_date, 90):
        return
    store.add_item(
        EvidenceItem(
            key="ownership.form4_90d",
            value=latest.value,
            status=EvidenceStatus.RETRIEVED,
            source_name="SEC EDGAR Form 4",
            source_url=latest.source_url,
            source_level=SourceLevel.SEC_OR_REGULATORY,
            as_of_date=candidate_date,
            retrieved_at=utc_now_iso(),
            retrieval_method="sec_api",
            confidence="high",
            direct_or_proxy="direct",
            limitations=["Derived from the latest SEC ownership filing during final evidence reconciliation."],
        )
    )


def _evidence_invalid_reasons(key: str, item: EvidenceItem) -> list[str]:
    reasons: list[str] = []
    if not _source_allowed_for_key(key, item):
        reasons.append(f"Source {item.source_name!r} is not permitted for {key}.")
    numeric_reason = _numeric_invalid_reason(key, item.value)
    if numeric_reason:
        reasons.append(numeric_reason)
    if key == "positioning.short_interest":
        value = item.value if isinstance(item.value, dict) else {}
        text = json.dumps(value, ensure_ascii=False).lower()
        if not all(token in text for token in ("short",)):
            reasons.append("Short-interest object lacks explicit short-interest fields.")
    return reasons


def _source_allowed_for_key(key: str, item: EvidenceItem) -> bool:
    allowed = SOURCE_PERMISSIONS.get(key)
    if not allowed:
        return True
    source_text = f"{item.source_name or ''} {item.source_url or ''} {item.retrieval_method or ''} {json.dumps(item.value, ensure_ascii=False)}".lower()
    if item.direct_or_proxy == "direct" and item.source_level >= SourceLevel.COMPANY_IR_OR_TRANSCRIPT and any(
        token in allowed for token in ("investor", "issuer ir", "issuer_ir", "sec.gov")
    ):
        return True
    return any(token in source_text for token in allowed)


def _numeric_invalid_reason(key: str, value: Any) -> str | None:
    number = _extract_numeric_value(value)
    if number is None:
        return None
    low_large_scale = {
        "earnings.revenue.actual",
        "cashflow.latest.ocf",
        "cashflow.latest.capex",
        "business.rpo_or_backlog",
    }
    if key in low_large_scale and abs(number) < 1_000:
        return f"Numeric value {number} for {key} is unitless or implausibly small."
    if key == "business.rpo_or_backlog" and abs(number) < 1_000_000:
        return f"RPO/backlog value {number} is implausibly small or likely an identifier/artifact."
    if key == "cashflow.fcf_inputs" and isinstance(value, dict):
        ocf = value.get("ocf")
        capex = value.get("capex")
        if isinstance(ocf, (int, float)) and abs(float(ocf)) < 1_000:
            return f"FCF input OCF value {ocf} is unitless or implausibly small."
        if isinstance(capex, (int, float)) and abs(float(capex)) < 1_000:
            return f"FCF input CapEx value {capex} is unitless or implausibly small."
    if key == "short_interest.shares_short" and number < 100_000:
        return f"Short-interest shares value {number} is implausibly small or unitless."
    return None


def _extract_numeric_value(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, dict):
        for preferred in ("actual", "value", "shares_short", "ocf", "capex", "rpo", "amount"):
            if preferred in value and isinstance(value[preferred], (int, float)):
                return float(value[preferred])
    return None


MANDATORY_EQUITY_KEYS: dict[str, dict[str, Any]] = {
    "market.latest_price": {
        "label": "Latest price / close and timestamp",
        "attempts": ["market data provider"],
        "blocking": True,
        "impact": "Technical triggers and valuation denominators may be stale.",
    },
    "market.ohlcv_6m": {
        "label": "6+ months OHLCV",
        "attempts": ["market data provider"],
        "blocking": True,
        "impact": "Technical trend and volatility context may be incomplete.",
    },
    "fundamentals.latest_earnings_release": {
        "label": "Latest earnings press release or 8-K",
        "attempts": ["issuer IR", "SEC EDGAR 8-K/10-Q/10-K"],
        "blocking": True,
        "impact": "Fundamental, news, debate, Research Manager, and PM conclusions may be based on stale data.",
    },
    "fundamentals.latest_filing": {
        "label": "Latest 10-Q or 10-K",
        "attempts": ["SEC EDGAR"],
        "blocking": True,
        "impact": "Financial statement calculations may be unsupported.",
    },
    "fundamentals.latest_financial_filing": {
        "label": "Latest financial filing (10-Q or 10-K)",
        "attempts": ["SEC EDGAR 10-Q/10-K", "issuer IR SEC filings page"],
        "blocking": True,
        "impact": "Financial statement calculations may be unsupported.",
    },
    "fundamentals.latest_earnings_8k": {
        "label": "Latest earnings 8-K",
        "attempts": ["SEC EDGAR 8-K", "issuer IR earnings release"],
        "blocking": False,
        "impact": "Latest quarter validation may lack an 8-K exhibit trail.",
    },
    "fundamentals.earnings_transcript": {
        "label": "Earnings call transcript",
        "attempts": ["issuer IR transcript", "reputable transcript provider"],
        "blocking": True,
        "impact": "Fundamental confidence cannot exceed LOW when transcript exists but is unavailable.",
    },
    "earnings.actual_vs_consensus": {
        "label": "Revenue/EPS/key metric actual vs consensus",
        "attempts": ["earnings release", "reputable estimates aggregator"],
        "blocking": True,
        "impact": "Earnings beat/miss and stock reaction may be misclassified.",
    },
    "guidance.management": {
        "label": "Management forward guidance",
        "attempts": ["earnings call transcript", "issuer IR", "SEC exhibits"],
        "blocking": True,
        "impact": "Valuation, CapEx, FCF, and catalyst conclusions may be guidance-blind.",
    },
    "capex.guidance": {
        "label": "Forward CapEx guidance",
        "attempts": ["earnings call transcript", "issuer IR", "SEC exhibits"],
        "blocking": False,
        "impact": "Forward CapEx peak, decline, elevation, and run-rate claims must be caveated unless management guidance is available.",
    },
    "consensus.analyst": {
        "label": "Analyst consensus from at least two aggregators",
        "attempts": ["TipRanks-style consensus", "StockAnalysis/MarketBeat/Yahoo-style aggregators"],
        "blocking": False,
        "impact": "Single-firm analyst notes may be mistaken for consensus.",
    },
    "positioning.short_interest": {
        "label": "Short interest, percent float, and days to cover",
        "attempts": ["FINRA/equivalent", "Nasdaq/equivalent", "MarketBeat/StockAnalysis/Fintel-style aggregators"],
        "blocking": False,
        "impact": "Crowding, squeeze, and professional-bearish-positioning claims are unsupported.",
    },
    "catalyst.next_earnings_date": {
        "label": "Next earnings date",
        "attempts": ["issuer IR calendar", "SEC/company reference", "earnings-date aggregators"],
        "blocking": False,
        "impact": "Event-risk timing and horizon classification may be incomplete.",
    },
    "cashflow.fcf_inputs": {
        "label": "OCF and CapEx inputs",
        "attempts": ["SEC cash-flow statement", "issuer release"],
        "blocking": True,
        "impact": "Free cash flow may be inconsistent across sections.",
    },
    "ownership.form4_90d": {
        "label": "Form 4 insider filings, last 90 days",
        "attempts": ["SEC EDGAR ownership forms"],
        "blocking": False,
        "impact": "Insider behavior cannot be used as a thesis support.",
    },
    "ownership.13f_latest": {
        "label": "Latest 13F institutional ownership context",
        "attempts": ["SEC EDGAR 13F", "institutional ownership aggregators"],
        "blocking": False,
        "impact": "Institutional positioning cannot be used as a thesis support.",
    },
    "options.put_call": {
        "label": "Options put/call ratio and significant strikes",
        "attempts": ["options data providers", "exchange/provider option chain"],
        "blocking": False,
        "impact": "Options sentiment and event-risk conclusions may be incomplete.",
    },
}


def run_equity_data_scan(ticker: str, report_date: str) -> EvidenceStore:
    store = EvidenceStore(ticker=ticker.upper(), report_date=report_date, generated_at=utc_now_iso())
    registry = create_default_registry()
    bars = []

    try:
        start_year = int(report_date[:4]) - 1
        bars = registry.get("yfinance").get_price_bars(ticker, f"{start_year}{report_date[4:]}", report_date)
        if bars:
            latest = sorted(bars, key=lambda item: item.date)[-1]
            store.add_item(
                EvidenceItem(
                    key="market.latest_price",
                    value={"close": latest.close, "date": latest.date, "volume": latest.volume},
                    status=EvidenceStatus.RETRIEVED,
                    source_name="yfinance",
                    source_url="https://finance.yahoo.com/",
                    source_level=SourceLevel.AGGREGATOR_OR_MARKET_DATA,
                    as_of_date=latest.date,
                    retrieved_at=latest.source.retrieved_at_utc if latest.source else utc_now_iso(),
                )
            )
            store.add_item(
                EvidenceItem(
                    key="market.ohlcv_6m",
                    value={"bar_count": len(bars), "first_date": bars[0].date, "last_date": latest.date},
                    status=EvidenceStatus.RETRIEVED if len(bars) >= 120 else EvidenceStatus.PARTIAL,
                    source_name="yfinance",
                    source_url="https://finance.yahoo.com/",
                    source_level=SourceLevel.AGGREGATOR_OR_MARKET_DATA,
                    as_of_date=latest.date,
                    retrieved_at=latest.source.retrieved_at_utc if latest.source else utc_now_iso(),
                    limitations=[] if len(bars) >= 120 else ["Fewer than 120 daily bars were retrieved."],
                    retrieval_method="market_data_provider",
                    confidence="medium",
                    direct_or_proxy="direct",
                )
            )
            from .equity_public_resolvers import promote_technical_indicators

            promote_technical_indicators(store, bars)
        else:
            _add_missing(store, "market.latest_price")
            _add_missing(store, "market.ohlcv_6m")
    except Exception as exc:
        _add_missing(store, "market.latest_price", detail=str(exc))
        _add_missing(store, "market.ohlcv_6m", detail=str(exc))

    try:
        fundamentals = registry.get("sec_edgar").get_fundamentals(ticker)
        if fundamentals:
            from .equity_public_resolvers import promote_financial_filing

            promote_financial_filing(
                store,
                fundamentals.filings or [],
                fundamentals.source.source_url if fundamentals.source else "https://www.sec.gov/edgar",
            )
            _promote_sec_cashflow_facts(store, fundamentals.facts or {}, fundamentals.source.source_url if fundamentals.source else "https://www.sec.gov/edgar")
        else:
            _add_missing(store, "fundamentals.latest_filing")
    except (DataProviderError, Exception) as exc:
        _add_missing(store, "fundamentals.latest_filing", detail=str(exc))

    try:
        from .equity_public_resolvers import collect_public_equity_sources, promote_pre_agent_sources

        fixture_path = Path(__file__).resolve().parents[1] / "research_packets" / "pre_agent_evidence" / f"{ticker.upper()}_{report_date}_pre_agent_sources.json"
        sources = collect_public_equity_sources(ticker, report_date, fixture_path if fixture_path.exists() else None)
        promote_pre_agent_sources(store, sources)
    except Exception as exc:
        store.record_attempt("pre_agent_public_resolvers", "equity.mandatory_public_sources", EvidenceStatus.PARTIAL, str(exc))

    try:
        from .earnings_event_resolver import promote_earnings_event_resolution, resolve_earnings_events

        earnings_fixture = Path(__file__).resolve().parents[1] / "research_packets" / "pre_agent_evidence" / f"{ticker.upper()}_{report_date}_earnings_events.json"
        resolution = resolve_earnings_events(
            ticker,
            "",
            report_date,
            earnings_fixture if earnings_fixture.exists() else None,
            allow_network=True,
        )
        promote_earnings_event_resolution(store, resolution)
    except Exception as exc:
        store.record_attempt("earnings_event_resolver", "earnings.event_state", EvidenceStatus.PARTIAL, str(exc))

    for key in MANDATORY_EQUITY_KEYS:
        if key not in store.items and key not in store.gaps:
            _add_missing(store, key)

    record_equity_discovery_attempts(store)

    return store


def record_equity_discovery_attempts(store: EvidenceStore) -> None:
    """Record hybrid public-first fallback discovery plans for unresolved facts.

    Direct adapters run first. For anything still unresolved, this records the
    exact public-source classes and search categories the retrieval layer must
    exhaust before the fact can be treated as unavailable.
    """
    for key, gap in list(store.gaps.items()):
        source_classes = "; ".join(gap.source_classes_attempted)
        query = f"{store.ticker} {gap.label} {store.report_date}"
        store.record_attempt(
            "hybrid_public_first_discovery",
            key,
            EvidenceStatus.MISSING,
            f"Fallback web discovery queued after direct adapters: query='{query}'; source classes={source_classes}.",
        )


def _promote_sec_cashflow_facts(store: EvidenceStore, facts: dict[str, Any], source_url: str | None) -> None:
    ocf = _sec_fact_value(
        facts,
        (
            "NetCashProvidedByUsedInOperatingActivities",
            "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
        ),
    )
    capex = _sec_fact_value(
        facts,
        (
            "PaymentsToAcquirePropertyPlantAndEquipment",
            "PaymentsToAcquireProductiveAssets",
            "PaymentsToAcquireBusinessesAndPropertyPlantAndEquipment",
        ),
    )
    if ocf is not None:
        store.add_item(
            EvidenceItem(
                key="cashflow.latest.ocf",
                value=ocf["value"],
                status=EvidenceStatus.RETRIEVED,
                source_name="SEC EDGAR companyfacts",
                source_url=source_url,
                source_level=SourceLevel.SEC_OR_REGULATORY,
                as_of_date=ocf.get("end") or ocf.get("filed"),
                retrieved_at=utc_now_iso(),
                limitations=[f"SEC concept: {ocf['concept']}; unit: {ocf.get('unit') or 'unknown'}."],
                retrieval_method="sec_companyfacts",
                confidence="high",
                direct_or_proxy="direct",
            )
        )
    if capex is not None:
        store.add_item(
            EvidenceItem(
                key="cashflow.latest.capex",
                value=abs(float(capex["value"])),
                status=EvidenceStatus.RETRIEVED,
                source_name="SEC EDGAR companyfacts",
                source_url=source_url,
                source_level=SourceLevel.SEC_OR_REGULATORY,
                as_of_date=capex.get("end") or capex.get("filed"),
                retrieved_at=utc_now_iso(),
                limitations=[f"SEC concept: {capex['concept']}; stored as cash outflow absolute value."],
                retrieval_method="sec_companyfacts",
                confidence="high",
                direct_or_proxy="direct",
            )
        )


def _sec_fact_value(facts: dict[str, Any], concepts: tuple[str, ...]) -> dict[str, Any] | None:
    for concept in concepts:
        item = facts.get(concept)
        if not isinstance(item, dict):
            continue
        value = item.get("value")
        if isinstance(value, (int, float)):
            return {**item, "concept": concept}
    return None


def save_evidence_store(store: EvidenceStore, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(store.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")


def load_evidence_store(path: Path) -> EvidenceStore:
    return EvidenceStore.from_dict(json.loads(path.read_text(encoding="utf-8")))


def promoted_store_from_stage_packets(
    *,
    ticker: str,
    report_date: str,
    stage2: dict[str, Any] | None = None,
    stage2b: dict[str, Any] | None = None,
    base_store: EvidenceStore | None = None,
) -> EvidenceStore:
    store = base_store or EvidenceStore(ticker=ticker.upper(), report_date=report_date, generated_at=utc_now_iso())
    sources = []
    if stage2:
        sources.extend(stage2.get("citation_sources", []) or [])
    if stage2b:
        sources.extend(stage2b.get("citation_sources", []) or [])
    for source in _dedupe_source_dicts(sources):
        promote_source_record_to_store(store, source)
    if stage2b:
        promote_reinforced_claims_to_store(store, stage2b.get("reinforced_claims", []) or [])
    return store


def promote_source_record_to_store(store: EvidenceStore, source: dict[str, Any]) -> None:
    text = _source_text(source)
    source_name = source.get("publisher") or source.get("title") or source.get("source_id") or "source"
    source_url = source.get("url")
    as_of = source.get("published_date")
    retrieved = source.get("retrieved_at_utc") or utc_now_iso()
    source_level = _source_level_from_record(source)

    def add(key: str, value: Any, status: EvidenceStatus = EvidenceStatus.RETRIEVED) -> None:
        store.add_item(
            EvidenceItem(
                key=key,
                value=value,
                status=status,
                source_name=source_name,
                source_url=source_url,
                source_level=source_level,
                as_of_date=as_of,
                retrieved_at=retrieved,
                limitations=list(source.get("limitations", []) or []),
            )
        )

    if _has_any(text, ("earnings release", "8-k", "results release", "quarterly results")):
        add("fundamentals.latest_earnings_release", {"source_id": source.get("source_id"), "summary": source.get("evidence_summary")})
    if _has_any(text, ("transcript", "earnings call", "q&a", "management commentary")):
        add("fundamentals.earnings_transcript", {"source_id": source.get("source_id"), "summary": source.get("evidence_summary")})
    if _has_any(text, ("guidance", "outlook", "forward guidance")):
        add("guidance.management", {"source_id": source.get("source_id"), "summary": source.get("evidence_summary")})
    if _indicates_capex_guidance(text):
        add(
            "capex.guidance",
            {
                "source_id": source.get("source_id"),
                "summary": source.get("evidence_summary"),
                "guidance_type": "management_or_transcript_capex_context",
            },
        )
    rpo = _extract_money_near_keywords(text, ("remaining performance obligation", "remaining performance obligations", "rpo", "backlog"))
    if rpo is not None and _has_any(text, ("remaining performance obligation", "remaining performance obligations", "rpo", "backlog")):
        add("business.rpo_or_backlog", rpo)
    if _has_any(text, ("actual vs consensus", "beat consensus", "missed consensus", "eps consensus", "revenue consensus", "versus consensus", "vs consensus")):
        eps_pair = _extract_eps_actual_consensus(text)
        if eps_pair.get("eps_actual") is not None:
            add("earnings.eps.actual", eps_pair["eps_actual"])
        if eps_pair.get("eps_consensus") is not None:
            add("earnings.eps.consensus", eps_pair["eps_consensus"])
        add("earnings.actual_vs_consensus", {"source_id": source.get("source_id"), "summary": source.get("evidence_summary"), **eps_pair})
    if _has_any(text, ("analyst consensus", "buy rating", "hold rating", "sell rating", "price target", "average target")):
        _append_source_list(store, "consensus.analyst.sources", source_name, source)
        if len(store.value("consensus.analyst.sources", []) or []) >= 2:
            add("consensus.analyst", {"sources": store.value("consensus.analyst.sources", [])})
    if _has_any(text, ("short interest", "days to cover", "short percent", "% of float", "percent of float")):
        _append_source_list(store, "short_interest.sources", source_name, source)
        fields = _extract_short_interest_fields(text)
        value = {"source_id": source.get("source_id"), "summary": source.get("evidence_summary"), **fields}
        add("positioning.short_interest", value)
        if fields.get("shares_short") is not None:
            add("short_interest.shares_short", fields["shares_short"])
        if fields.get("days_to_cover") is not None:
            add("short_interest.days_to_cover", fields["days_to_cover"])
        if fields.get("percent_float") is not None:
            add("short_interest.percent_float", fields["percent_float"])
    if _has_any(text, ("next earnings", "earnings date", "reports earnings")):
        _append_source_list(store, "catalyst.next_earnings_date.sources", source_name, source)
        add("catalyst.next_earnings_date", {"source_id": source.get("source_id"), "summary": source.get("evidence_summary")})
    if _has_any(text, ("operating cash flow", "free cash flow", "capital expenditure", "capex", "capital expenditures")):
        add("cashflow.fcf_inputs", {"source_id": source.get("source_id"), "summary": source.get("evidence_summary")}, EvidenceStatus.PARTIAL)
    if _has_any(text, ("fy1 eps", "fy2 eps", "ntm eps", "forward eps", "forward p/e", "forward pe")):
        add("valuation.forward_pe_basis", {"source_id": source.get("source_id"), "summary": source.get("evidence_summary")}, EvidenceStatus.PARTIAL)


def promote_reinforced_claims_to_store(store: EvidenceStore, claims: list[dict[str, Any]]) -> None:
    for claim in claims:
        status = str(claim.get("reinforced_status", "")).lower()
        if status != "supported":
            continue
        text = f"{claim.get('claim', '')} {claim.get('evidence_class', '')} {claim.get('rationale', '')}".lower()
        source_ids = claim.get("source_ids", []) or []
        value = {"claim": claim.get("claim"), "source_ids": source_ids, "rationale": claim.get("rationale")}
        source_name = ", ".join(source_ids) or "Stage 2B reinforcement"
        key: str | None = None
        if _has_any(text, ("guidance", "outlook")):
            key = "guidance.management"
            if "capex" in text or "capital expenditure" in text:
                store.add_item(
                    EvidenceItem(
                        key="capex.guidance",
                        value=value,
                        status=EvidenceStatus.RETRIEVED,
                        source_name=source_name,
                        source_url=None,
                        source_level=SourceLevel.AGGREGATOR_OR_MARKET_DATA,
                        as_of_date=store.report_date,
                        retrieved_at=utc_now_iso(),
                    )
                )
        elif _has_any(text, ("short interest", "days to cover", "short percent", "percent of float")):
            key = "positioning.short_interest"
        elif _has_any(text, ("analyst consensus", "price target", "buy rating")):
            key = "consensus.analyst"
        elif _has_any(text, ("next earnings", "earnings date", "catalyst")):
            key = "catalyst.next_earnings_date"
        elif _has_any(text, ("actual vs consensus", "beat consensus", "miss consensus")):
            key = "earnings.actual_vs_consensus"
        elif _has_any(text, ("transcript", "earnings call")):
            key = "fundamentals.earnings_transcript"
        elif _has_any(text, ("capex", "free cash flow", "operating cash flow")):
            key = "cashflow.fcf_inputs"
        if key:
            store.add_item(
                EvidenceItem(
                    key=key,
                    value=value,
                    status=EvidenceStatus.RETRIEVED,
                    source_name=source_name,
                    source_url=None,
                    source_level=SourceLevel.AGGREGATOR_OR_MARKET_DATA,
                    as_of_date=store.report_date,
                    retrieved_at=utc_now_iso(),
                )
            )


def _dedupe_source_dicts(sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for source in sources:
        source_id = str(source.get("source_id") or source.get("url") or source.get("title") or len(deduped))
        if source_id in seen:
            continue
        seen.add(source_id)
        deduped.append(source)
    return deduped


def _source_text(source: dict[str, Any]) -> str:
    fields = [
        source.get("title"),
        source.get("publisher"),
        source.get("source_type"),
        source.get("evidence_summary"),
        " ".join(source.get("supported_claims", []) or []),
    ]
    if _should_deep_fetch_source(source):
        fields.append(_fetch_source_page_text(str(source.get("url") or "")))
    return " ".join(str(item or "") for item in fields).lower()


def _should_deep_fetch_source(source: dict[str, Any]) -> bool:
    text = f"{source.get('publisher', '')} {source.get('source_type', '')} {source.get('url', '')}".lower()
    return bool(source.get("url")) and any(
        token in text
        for token in (
            "investor",
            "ir.",
            "sec.gov",
            "earnings",
            "press-release",
            "press_release",
            "transcript",
            "10-q",
            "10-k",
        )
    )


def _fetch_source_page_text(url: str) -> str:
    if not url:
        return ""
    request = Request(url, headers={"User-Agent": "TitanIntegration/0.1 evidence-source-reader"})
    try:
        with urlopen(request, timeout=12) as response:
            raw = response.read(1_500_000).decode("utf-8", errors="ignore")
    except (HTTPError, URLError, TimeoutError, OSError):
        return ""
    return re.sub(r"<[^>]+>", " ", raw)


def _source_level_from_record(source: dict[str, Any]) -> SourceLevel:
    text = f"{source.get('reliability_tier', '')} {source.get('publisher', '')} {source.get('source_type', '')}".lower()
    if "sec" in text or "regulatory" in text or "edgar" in text:
        return SourceLevel.SEC_OR_REGULATORY
    if "issuer" in text or "company" in text or "transcript" in text or "ir" in text:
        return SourceLevel.COMPANY_IR_OR_TRANSCRIPT
    if "wire" in text or "news" in text or "reuters" in text or "bloomberg" in text:
        return SourceLevel.MAJOR_WIRE_OR_REPUTABLE_NEWS
    return SourceLevel.AGGREGATOR_OR_MARKET_DATA


def _append_source_list(store: EvidenceStore, key: str, value: str, source: dict[str, Any]) -> None:
    current = list(store.value(key, []) or [])
    if value not in current:
        current.append(value)
    store.add_item(
        EvidenceItem(
            key=key,
            value=current,
            status=EvidenceStatus.RETRIEVED if current else EvidenceStatus.MISSING,
            source_name=value,
            source_url=source.get("url"),
            source_level=_source_level_from_record(source),
            as_of_date=source.get("published_date"),
            retrieved_at=source.get("retrieved_at_utc") or utc_now_iso(),
        )
    )


def _has_any(text: str, needles: tuple[str, ...]) -> bool:
    return any(needle in text for needle in needles)


def _extract_first_number(text: str) -> float | None:
    match = re.search(r"(\d+(?:\.\d+)?)", text)
    return float(match.group(1)) if match else None


def _extract_eps_actual_consensus(text: str) -> dict[str, float | None]:
    patterns = (
        r"eps\s+of\s+\$?([0-9]+(?:\.[0-9]+)?)\s+(?:versus|vs\.?)\s+consensus\s+(?:of\s+)?\$?([0-9]+(?:\.[0-9]+)?)",
        r"eps\s+\$?([0-9]+(?:\.[0-9]+)?)\s+(?:versus|vs\.?)\s+consensus\s+\$?([0-9]+(?:\.[0-9]+)?)",
        r"\$?([0-9]+(?:\.[0-9]+)?)\s+eps\s+(?:versus|vs\.?)\s+\$?([0-9]+(?:\.[0-9]+)?)\s+consensus",
    )
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            return {"eps_actual": float(match.group(1)), "eps_consensus": float(match.group(2))}
    return {"eps_actual": None, "eps_consensus": None}


def _extract_short_interest_fields(text: str) -> dict[str, float]:
    fields: dict[str, float] = {}
    shares_patterns = (
        r"([0-9][0-9,]*(?:\.[0-9]+)?)\s*(million|billion|m|b)?\s+shares?\s+short",
        r"short\s+interest[^.\n]{0,80}?([0-9][0-9,]*(?:\.[0-9]+)?)\s*(million|billion|m|b)?\s+shares?",
        r"shares?\s+short[^.\n]{0,80}?([0-9][0-9,]*(?:\.[0-9]+)?)\s*(million|billion|m|b)?",
    )
    shares = _extract_number_with_optional_unit(text, shares_patterns)
    if shares is not None:
        fields["shares_short"] = shares
    pct = _extract_number_with_optional_unit(
        text,
        (
            r"([0-9]+(?:\.[0-9]+)?)\s*%\s*(?:of\s+)?(?:shares\s+)?float",
            r"([0-9]+(?:\.[0-9]+)?)\s*percent\s+(?:of\s+)?(?:shares\s+)?float",
            r"([0-9]+(?:\.[0-9]+)?)\s*%\s+of\s+shares",
            r"([0-9]+(?:\.[0-9]+)?)\s*percent\s+of\s+shares",
        ),
    )
    if pct is not None:
        fields["percent_float"] = pct
    days = _extract_number_with_optional_unit(
        text,
        (
            r"([0-9]+(?:\.[0-9]+)?)\s+days?\s+to\s+cover",
            r"short[-\s]?interest\s+ratio[^.\n]{0,40}?([0-9]+(?:\.[0-9]+)?)\s+days?",
        ),
    )
    if days is not None:
        fields["days_to_cover"] = days
    return fields


def _extract_money_near_keywords(text: str, needles: tuple[str, ...]) -> float | None:
    rpo_specific = re.search(
        r"(?:remaining\s+performance\s+obligations?|rpo|backlog)[^.\n]{0,140}?(?:to|was|were|of|at)?\s*\$?\s*([0-9][0-9,]*(?:\.[0-9]+)?)\s*(billion|million|b|m)",
        text,
        re.I,
    )
    if rpo_specific:
        return _scale_number(float(rpo_specific.group(1).replace(",", "")), rpo_specific.group(2))
    rpo_reverse = re.search(
        r"\$?\s*([0-9][0-9,]*(?:\.[0-9]+)?)\s*(billion|million|b|m)[^.\n]{0,120}?(?:remaining\s+performance\s+obligations?|rpo|backlog)",
        text,
        re.I,
    )
    if rpo_reverse:
        return _scale_number(float(rpo_reverse.group(1).replace(",", "")), rpo_reverse.group(2))
    for needle in needles:
        idx = text.find(needle)
        if idx < 0:
            continue
        window = text[max(0, idx - 80) : idx + 220]
        value = _extract_number_with_optional_unit(
            window,
            (r"\$?\s*([0-9][0-9,]*(?:\.[0-9]+)?)\s*(billion|million|b|m)?",),
        )
        if value is not None:
            return value
    return None


def _scale_number(value: float, unit: str | None) -> float:
    unit = (unit or "").lower()
    if unit in {"billion", "b"}:
        return value * 1_000_000_000
    if unit in {"million", "m"}:
        return value * 1_000_000
    return value


def _extract_number_with_optional_unit(text: str, patterns: tuple[str, ...]) -> float | None:
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if not match:
            continue
        raw = match.group(1).replace(",", "")
        value = float(raw)
        unit = ""
        if len(match.groups()) > 1 and match.group(2):
            unit = match.group(2).lower()
        if unit in {"billion", "b"}:
            return value * 1_000_000_000
        if unit in {"million", "m"}:
            return value * 1_000_000
        return value
    return None


def _indicates_capex_guidance(text: str) -> bool:
    has_capex = _has_any(
        text,
        (
            "capex",
            "capital expenditure",
            "capital expenditures",
            "capital spending",
            "ai capex",
            "ai infrastructure",
            "data center investment",
        ),
    )
    has_forward_context = _has_any(
        text,
        (
            "guidance",
            "outlook",
            "expect",
            "expects",
            "expected",
            "will increase",
            "will decline",
            "remain elevated",
            "spending growth",
            "next quarter",
            "fiscal",
            "calendar year",
        ),
    )
    return has_capex and has_forward_context


def _within_days(anchor: str | None, candidate: str | None, days: int) -> bool:
    anchor_dt = _parse_iso_date(anchor)
    candidate_dt = _parse_iso_date(candidate)
    if not anchor_dt or not candidate_dt:
        return False
    delta = (anchor_dt - candidate_dt).days
    return 0 <= delta <= days


def _parse_iso_date(value: str | None):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value)[:10]).date()
    except ValueError:
        return None


def _add_missing(store: EvidenceStore, key: str, detail: str | None = None) -> None:
    spec = MANDATORY_EQUITY_KEYS[key]
    store.add_gap(
        EvidenceGap(
            key=key,
            label=spec["label"],
            status=EvidenceStatus.MISSING,
            source_classes_attempted=list(spec["attempts"]),
            validation_result=detail or "Required evidence item was not retrieved by the mandatory scan.",
            thesis_impact=spec["impact"],
            next_best_evidence=f"Retry via {', '.join(spec['attempts'])}.",
            constrained_conclusion="Use constrained conclusions and block dependent claims until this evidence is retrieved.",
            blocking=bool(spec["blocking"]),
        )
    )


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _enum_safe(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {key: _enum_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_enum_safe(item) for item in value]
    return value


@dataclass(frozen=True)
class EarningsMetricResult:
    metric: str
    actual: float | str
    consensus: float | str | None
    beat_miss: str
    source_key: str


@dataclass(frozen=True)
class EarningsEvent:
    quarter_quality: str
    metric_results: list[EarningsMetricResult]
    stock_reaction: str | None
    reaction_cause: str | None
    reaction_cause_source: str | None


def classify_earnings_event(evidence: EvidenceStore) -> EarningsEvent:
    results: list[EarningsMetricResult] = []
    for metric in ("revenue", "eps", "key_segment"):
        actual_key = f"earnings.{metric}.actual"
        consensus_key = f"earnings.{metric}.consensus"
        actual = evidence.get(actual_key)
        if not actual:
            continue
        consensus = evidence.value(consensus_key)
        actual_value = actual.value
        beat_miss = "unknown"
        if isinstance(actual_value, (int, float)) and isinstance(consensus, (int, float)):
            if actual_value > consensus:
                beat_miss = "beat"
            elif actual_value < consensus:
                beat_miss = "miss"
            else:
                beat_miss = "inline"
        results.append(
            EarningsMetricResult(
                metric=metric,
                actual=actual_value,
                consensus=consensus,
                beat_miss=beat_miss,
                source_key=actual_key,
            )
        )
    known = [item.beat_miss for item in results if item.beat_miss != "unknown"]
    if known and all(item == "beat" for item in known):
        quality = "beat"
    elif known and all(item == "miss" for item in known):
        quality = "miss"
    elif known:
        quality = "mixed"
    else:
        quality = "unknown"
    return EarningsEvent(
        quarter_quality=quality,
        metric_results=results,
        stock_reaction=evidence.value("earnings.stock_reaction"),
        reaction_cause=evidence.value("earnings.reaction_cause"),
        reaction_cause_source="earnings.reaction_cause" if evidence.get("earnings.reaction_cause") else None,
    )


def validate_earnings_language(text: str, event: EarningsEvent) -> None:
    bad_language = re.search(
        r"\b(disappointment|disappointing|missed expectations|miss|fell short|below expectations|decelerated versus consensus)\b",
        text,
        flags=re.IGNORECASE,
    )
    if bad_language and event.quarter_quality == "beat":
        raise EquityValidationError(
            "Earnings language contradicts actual-vs-consensus classifier: quarter_quality=beat."
        )
    if bad_language and not event.metric_results:
        raise EquityValidationError("Earnings disappointment/miss language requires classifier metric evidence.")


@dataclass(frozen=True)
class CapexProfile:
    quarterly_actuals: dict[str, float]
    next_quarter_guidance: float | tuple[float, float] | None
    full_year_or_calendar_guidance: float | tuple[float, float] | None
    guidance_source: str | None
    annualized_fallback_used: bool


def resolve_capex(evidence: EvidenceStore) -> CapexProfile:
    quarterly = evidence.value("capex.quarterly_actuals", {}) or {}
    guidance = evidence.value("capex.full_year_guidance") or evidence.value("capex.calendar_year_guidance")
    next_q = evidence.value("capex.next_quarter_guidance")
    if guidance is not None or next_q is not None:
        evidence.record_attempt("capex_resolver", "capex.guidance", EvidenceStatus.RETRIEVED, "Management guidance available.")
        return CapexProfile(quarterly, next_q, guidance, "capex.full_year_guidance", False)
    fallback = None
    if quarterly:
        fallback = list(quarterly.values())[-1] * 4
    evidence.record_attempt("capex_resolver", "capex.guidance", EvidenceStatus.PARTIAL, "Annualized fallback used.")
    return CapexProfile(quarterly, None, fallback, None, True)


def compute_free_cash_flow(ocf: float, capex: float) -> float:
    return ocf - capex


@dataclass(frozen=True)
class FCFReconciliation:
    period: str
    ocf: float | None
    capex: float | None
    reconciled_fcf: float | None
    agent_values: list[float]
    status: EvidenceStatus
    source_key: str | None


def reconcile_fcf(agent_values: list[float], evidence: EvidenceStore, period: str = "latest") -> FCFReconciliation:
    ocf = evidence.value(f"cashflow.{period}.ocf")
    capex = evidence.value(f"cashflow.{period}.capex")
    if ocf is None or capex is None:
        return FCFReconciliation(period, ocf, capex, None, agent_values, EvidenceStatus.MISSING, None)
    reconciled = compute_free_cash_flow(float(ocf), float(capex))
    status = EvidenceStatus.COMPUTED
    if any(abs(value - reconciled) > 0.05 for value in agent_values):
        status = EvidenceStatus.CONTESTED
    return FCFReconciliation(period, float(ocf), float(capex), reconciled, agent_values, status, f"cashflow.{period}")


@dataclass(frozen=True)
class ForwardPEResolution:
    fy1_eps: float | None
    fy2_eps: float | None
    ntm_eps: float | None
    fy1_pe: float | None
    fy2_pe: float | None
    ntm_pe: float | None
    sources: list[str]
    status: EvidenceStatus


def resolve_forward_pe(ticker: str, price: float, evidence: EvidenceStore | None = None) -> ForwardPEResolution:
    fy1 = evidence.value("valuation.fy1_eps") if evidence else None
    fy2 = evidence.value("valuation.fy2_eps") if evidence else None
    ntm = evidence.value("valuation.ntm_eps") if evidence else None
    sources = []
    if evidence:
        sources = [
            key
            for key in ("valuation.fy1_eps", "valuation.fy2_eps", "valuation.ntm_eps")
            if evidence.get(key)
        ]
        evidence.record_attempt(
            "forward_pe_resolver",
            "valuation.forward_pe",
            EvidenceStatus.RETRIEVED if sources else EvidenceStatus.MISSING,
            f"Resolved EPS sources: {', '.join(sources) or 'none'}",
        )
    return ForwardPEResolution(
        fy1_eps=fy1,
        fy2_eps=fy2,
        ntm_eps=ntm,
        fy1_pe=price / fy1 if fy1 else None,
        fy2_pe=price / fy2 if fy2 else None,
        ntm_pe=price / ntm if ntm else None,
        sources=sources,
        status=EvidenceStatus.RETRIEVED if sources else EvidenceStatus.MISSING,
    )


@dataclass(frozen=True)
class AnalystConsensus:
    sources: list[str]
    analyst_count: int | None
    buy_count: int | None
    hold_count: int | None
    sell_count: int | None
    average_price_target: float | None
    high_price_target: float | None
    low_price_target: float | None
    as_of_date: str | None
    status: EvidenceStatus


def retrieve_analyst_consensus_from_store(evidence: EvidenceStore, min_sources: int = 2) -> AnalystConsensus:
    sources = evidence.value("consensus.analyst.sources", []) or []
    status = EvidenceStatus.RETRIEVED if len(sources) >= min_sources else EvidenceStatus.PARTIAL
    return AnalystConsensus(
        sources=sources,
        analyst_count=evidence.value("consensus.analyst.count"),
        buy_count=evidence.value("consensus.analyst.buy"),
        hold_count=evidence.value("consensus.analyst.hold"),
        sell_count=evidence.value("consensus.analyst.sell"),
        average_price_target=evidence.value("consensus.analyst.avg_pt"),
        high_price_target=evidence.value("consensus.analyst.high_pt"),
        low_price_target=evidence.value("consensus.analyst.low_pt"),
        as_of_date=evidence.value("consensus.analyst.as_of"),
        status=status,
    )


@dataclass(frozen=True)
class CatalystDate:
    event_name: str
    date: str | None
    time: str | None
    timezone: str | None
    sources: list[str]
    confidence: str
    days_until_event: int | None


def resolve_next_earnings_date_from_store(evidence: EvidenceStore, min_sources: int = 3) -> CatalystDate:
    sources = evidence.value("catalyst.next_earnings_date.sources", []) or []
    date_value = evidence.value("catalyst.next_earnings_date.value")
    confidence = "confirmed" if date_value and len(sources) >= min_sources else "probable" if date_value else "unconfirmed"
    return CatalystDate(
        event_name="Next earnings",
        date=date_value,
        time=evidence.value("catalyst.next_earnings_date.time"),
        timezone=evidence.value("catalyst.next_earnings_date.timezone"),
        sources=sources,
        confidence=confidence,
        days_until_event=None,
    )


@dataclass(frozen=True)
class ShortInterest:
    shares_short: float | None
    percent_float_short: float | None
    days_to_cover: float | None
    source: str | None
    as_of_date: str | None
    status: EvidenceStatus


def retrieve_short_interest_from_store(evidence: EvidenceStore) -> ShortInterest:
    return ShortInterest(
        shares_short=evidence.value("short_interest.shares_short"),
        percent_float_short=evidence.value("short_interest.percent_float"),
        days_to_cover=evidence.value("short_interest.days_to_cover"),
        source="short_interest" if evidence.get("short_interest.percent_float") else None,
        as_of_date=evidence.value("short_interest.as_of"),
        status=EvidenceStatus.RETRIEVED if evidence.get("short_interest.percent_float") else EvidenceStatus.MISSING,
    )


POSITIONING_CLAIM_RE = re.compile(
    r"\b(crowded short|crowded long|short squeeze|squeeze risk|professional bears absent|bearish positioning|low squeeze risk)\b",
    flags=re.IGNORECASE,
)


def validate_short_interest_dependency(text: str, short_interest: ShortInterest) -> None:
    if POSITIONING_CLAIM_RE.search(text) and short_interest.status != EvidenceStatus.RETRIEVED:
        raise EquityValidationError("Positioning conclusion requires retrieved short-interest evidence.")


@dataclass(frozen=True)
class PeerComparisonRow:
    company: str
    segment: str
    segment_revenue: float | None
    growth_pct: float | None
    consensus: float | None
    beat_miss: str
    market_share: float | None
    scale_context: str | None


def validate_peer_comparison(rows: list[PeerComparisonRow]) -> None:
    if not rows:
        raise EquityValidationError("Peer comparison requires rows.")
    for row in rows:
        if row.segment_revenue is None or row.scale_context is None:
            raise EquityValidationError("Peer comparison cannot use only percentage growth rates.")


@dataclass(frozen=True)
class DebateRound:
    round_name: str
    bull: str
    bear: str
    evidence_keys: list[str]


@dataclass(frozen=True)
class DebateResult:
    rounds: list[DebateRound]

    @property
    def round_count(self) -> int:
        return len(self.rounds)


class DebateValidationError(RuntimeError):
    pass


DEBATE_ROUND_REQUIREMENTS: tuple[tuple[str, tuple[str, ...], tuple[str, ...]], ...] = (
    ("Opening Thesis", ("opening", "thesis"), ("data", "evidence", "source", "claim")),
    ("Data Challenge", ("data", "challenge"), ("source", "citation", "metric", "stale", "fabricat")),
    ("Narrative Counter", ("narrative", "counter"), ("logic", "category", "analogy", "thesis")),
    ("Invalidation Stress-Test", ("invalidation", "stress"), ("destroy", "invalidate", "specific", "data point", "event")),
    ("Convergence & Residual Disagreement", ("convergence", "residual"), ("agree", "disagree", "residual", "diverge")),
)


def validate_debate(result: DebateResult, min_rounds: int = 5) -> None:
    if result.round_count < min_rounds:
        raise DebateValidationError("Bull/Bear debate must have at least five rounds.")
    for index, item in enumerate(result.rounds[:min_rounds], start=1):
        if not item.bull or not item.bear:
            raise DebateValidationError("Every debate round must include Bull and Bear contributions.")
        if not item.evidence_keys:
            raise DebateValidationError("Every debate round must cite evidence keys.")
        expected_label, name_terms, content_terms = DEBATE_ROUND_REQUIREMENTS[index - 1]
        name_text = item.round_name.lower()
        combined = f"{item.round_name} {item.bull} {item.bear}".lower()
        if not any(term in name_text for term in name_terms):
            raise DebateValidationError(f"Debate round {index} must be {expected_label}.")
        if not any(term in combined for term in content_terms):
            raise DebateValidationError(f"Debate round {index} lacks required {expected_label} content.")


@dataclass(frozen=True)
class RejectedClaim:
    agent_name: str
    severity: str
    exact_claim: str
    reason: str
    correction_rule: str
    recurrence: bool = False
    pattern: str | None = None


@dataclass(frozen=True)
class FinalReportSafetyResult:
    accepted_claims: list[str]
    rejected_claims: list[RejectedClaim]
    unresolved_gaps: list[str]
    sanitized_sections: dict[str, str]
    self_audit_passed: bool


CLAIM_GUARD_RULES: tuple[dict[str, Any], ...] = (
    {
        "pattern": re.compile(r"\b(disappointing earnings|earnings disappointment|fell short|missed expectations|below expectations|azure disappointed|segment disappointed)\b", re.I),
        "dependency": "earnings.actual_vs_consensus",
        "severity": "CRITICAL",
        "reason": "Earnings disappointment or miss language requires actual-vs-consensus evidence and cannot be inferred from stock reaction.",
        "rule": "Never label earnings or a segment as disappointing unless actual and consensus figures are both retrieved and the classifier shows a miss.",
    },
    {
        "pattern": re.compile(
            r"\b("
            r"annuali[sz](?:ed|ation)\s+capex|"
            r"capex\s+annuali[sz](?:ed|ation)|"
            r"capex\s+run[- ]?rate|"
            r"quarterly\s+capex\s*[x×]\s*4|"
            r"(?:fy20\d{2}|fy\d{2}|next\s+year|future|forward|management)\s+capex|"
            r"capex\s+(?:guidance|peak|peaking|timeline|inflection|overhang)|"
            r"peak\s+capex|"
            r"capex\s+remains\s+elevated|"
            r"spending\s+(?:cliff|will\s+peak|is\s+peaking)"
            r")\b",
            re.I,
        ),
        "dependency": "capex.guidance",
        "severity": "HIGH",
        "reason": "Forward CapEx guidance, peak, decline, or run-rate language requires management guidance before it can be stated as final fact.",
        "rule": "Preserve actual CapEx/OCF/FCF analysis, but label forward CapEx peak/decline/elevation language as an unvalidated scenario unless management guidance is retrieved.",
        "disposition": "annotate",
    },
    {
        "pattern": re.compile(r"\b(strong buy|analyst consensus|consensus rating|average price target|street consensus)\b", re.I),
        "dependency": "consensus.analyst",
        "severity": "HIGH",
        "reason": "Consensus language requires at least two aggregator sources and cannot be inferred from a single analyst action.",
        "rule": "Never treat a single analyst note as consensus; require at least two consensus aggregators.",
    },
    {
        "pattern": re.compile(r"\b(short squeeze|squeeze risk|crowded long|crowded short|bearish positioning|professional bears|short interest)\b", re.I),
        "dependency": "positioning.short_interest",
        "severity": "HIGH",
        "reason": "Positioning and squeeze claims require retrieved short-interest evidence.",
        "rule": "Do not write sentiment or positioning conclusions from short interest unless short interest, percent float, and/or days to cover are sourced.",
    },
    {
        "pattern": re.compile(r"\b(rpo|remaining performance obligation|remaining performance obligations|contracted backlog|backlog)\b", re.I),
        "dependency": "business.rpo_or_backlog",
        "severity": "HIGH",
        "reason": "RPO/backlog claims require issuer IR, SEC filing, transcript, or another permitted direct source.",
        "rule": "Do not use RPO/backlog as cloud or subscription-demand support unless the typed evidence store contains a permitted source and plausible units.",
    },
    {
        "pattern": re.compile(r"\b(forward p/e|forward pe|ntm p/e|fy1 p/e|fy2 p/e)\b", re.I),
        "dependency": "valuation.forward_pe_basis",
        "severity": "MEDIUM",
        "reason": "Forward P/E claims require explicit price and FY1/FY2/NTM EPS basis.",
        "rule": "State forward P/E only when the price and EPS denominator are both sourced or computed from sourced inputs.",
    },
    {
        "pattern": re.compile(
            r"\b("
            r"free[- ]cash[- ]flow|"
            r"fcf|"
            r"cash[- ]flow\s+deterioration|"
            r"cash\s+flow\s+deterioration|"
            r"ocf\s+.*capex|"
            r"capex\s+.*ocf|"
            r"capital\s+efficiency"
            r")\b",
            re.I,
        ),
        "dependency": "cashflow.fcf_inputs",
        "severity": "HIGH",
        "reason": "FCF claims require same-period operating cash flow and CapEx inputs.",
        "rule": "Never reconcile FCF from mixed periods; use same-period OCF minus CapEx.",
    },
)


def build_final_report_safety_result(sections: dict[str, str], evidence: EvidenceStore) -> FinalReportSafetyResult:
    rejected: list[RejectedClaim] = []
    sanitized: dict[str, str] = {}
    accepted: list[str] = []
    unresolved = [gap.key for gap in evidence.gaps.values()]
    for section_name, text in sections.items():
        sanitized[section_name] = _sanitize_section_text(section_name, text, evidence, rejected)
    for key, item in evidence.items.items():
        if item.status in {EvidenceStatus.RETRIEVED, EvidenceStatus.COMPUTED}:
            accepted.append(key)
    return FinalReportSafetyResult(
        accepted_claims=sorted(accepted),
        rejected_claims=rejected,
        unresolved_gaps=sorted(unresolved),
        sanitized_sections=sanitized,
        self_audit_passed=not rejected and not any(gap.blocking for gap in evidence.gaps.values()),
    )


def _sanitize_section_text(
    section_name: str,
    text: str,
    evidence: EvidenceStore,
    rejected: list[RejectedClaim],
) -> str:
    if not text:
        return ""
    blocks = re.split(r"(\n\s*\n)", text)
    cleaned: list[str] = []
    for block in blocks:
        if not block.strip() or re.fullmatch(r"\n\s*\n", block):
            cleaned.append(block)
            continue
        rejection = _rejection_for_block(section_name, block, evidence)
        if rejection:
            if _should_annotate_instead_of_reject(rejection):
                cleaned.append(block.rstrip() + "\n\n" + _inline_evidence_note(rejection) + "\n")
                continue
            rejected.append(rejection)
            continue
        cleaned.append(block)
    return "".join(cleaned)


def _rejection_for_block(section_name: str, block: str, evidence: EvidenceStore) -> RejectedClaim | None:
    stale_event = _stale_earnings_event_for_block(section_name, block, evidence)
    if stale_event:
        return stale_event
    for rule in CLAIM_GUARD_RULES:
        if not rule["pattern"].search(block):
            continue
        dependency = rule["dependency"]
        if evidence.is_usable(dependency):
            continue
        return RejectedClaim(
            agent_name=_agent_from_section(section_name),
            severity=rule["severity"],
            exact_claim=_compact_claim(block),
            reason=rule["reason"],
            correction_rule=rule["rule"],
            pattern=dependency,
        )
    return None


def _should_annotate_instead_of_reject(rejection: RejectedClaim) -> bool:
    return rejection.pattern in {
        "capex.guidance",
        "valuation.forward_pe_basis",
        "cashflow.fcf_inputs",
        "business.rpo_or_backlog",
        "positioning.short_interest",
        "consensus.analyst",
        "catalyst.stale_earnings_date_conflict",
    }


def _inline_evidence_note(rejection: RejectedClaim) -> str:
    return (
        f"> Evidence note ({rejection.pattern}): {rejection.reason} "
        "Status: not promoted as final truth; preserve as scenario/claim requiring human review. "
        f"Rule: {rejection.correction_rule}"
    )


def _stale_earnings_event_for_block(section_name: str, block: str, evidence: EvidenceStore) -> RejectedClaim | None:
    item = evidence.get("catalyst.stale_earnings_date_conflict")
    if not item or not isinstance(item.value, dict):
        return None
    stale_dates = item.value.get("stale_or_conflicting_dates") or []
    if not stale_dates:
        return None
    block_text = block.lower()
    for stale_date in stale_dates:
        variants = _date_text_variants(str(stale_date))
        if any(variant and variant.lower() in block_text for variant in variants):
            return RejectedClaim(
                agent_name=_agent_from_section(section_name),
                severity="HIGH",
                exact_claim=_compact_claim(block),
                reason=(
                    f"Earnings catalyst date {stale_date} conflicts with the resolved earnings-event state: "
                    f"latest reported={item.value.get('latest_reported_date')}, next estimated={item.value.get('next_estimated_date')}."
                ),
                correction_rule=(
                    "Do not describe stale earnings dates as upcoming catalysts; use issuer/latest-release state "
                    "and the resolved next estimated earnings date."
                ),
                pattern="catalyst.stale_earnings_date_conflict",
            )
    return None


def _date_text_variants(value: str) -> list[str]:
    variants = [value]
    try:
        parsed = datetime.fromisoformat(value[:10])
    except ValueError:
        return variants
    variants.extend(
        [
            parsed.strftime("%B %d, %Y").replace(" 0", " "),
            parsed.strftime("%b %d, %Y").replace(" 0", " "),
            parsed.strftime("%B %d").replace(" 0", " "),
            parsed.strftime("%b %d").replace(" 0", " "),
            parsed.strftime("%m/%d/%Y"),
        ]
    )
    variants.append(f"{parsed.month}/{parsed.day}/{parsed.year}")
    return list(dict.fromkeys(variant for variant in variants if variant))


def _agent_from_section(section_name: str) -> str:
    return {
        "final_trade_decision": "Portfolio Manager",
        "market_report": "Market Analyst",
        "news_report": "News Analyst",
        "fundamentals_report": "Fundamentals Analyst",
        "sentiment_report": "Sentiment Analyst",
        "investment_plan": "Research Manager",
        "trader_investment_plan": "Trader",
    }.get(section_name, section_name)


def _compact_claim(text: str, limit: int = 260) -> str:
    compact = re.sub(r"\s+", " ", re.sub(r"[*_`#>|]+", " ", text)).strip()
    return compact if len(compact) <= limit else compact[: limit - 3] + "..."


@dataclass(frozen=True)
class ContaminationReport:
    agent_name: str
    accepted_facts: list[str]
    rejected_facts: list[str]
    contested_facts: list[str]
    stale_facts: list[str]
    missing_facts: list[str]


def run_contamination_check(agent_name: str, required_facts: list[str], evidence: EvidenceStore) -> ContaminationReport:
    accepted: list[str] = []
    rejected: list[str] = []
    contested: list[str] = []
    stale: list[str] = []
    missing: list[str] = []
    for key in required_facts:
        status = evidence.status(key)
        if status in {EvidenceStatus.RETRIEVED, EvidenceStatus.COMPUTED}:
            accepted.append(key)
        elif status == EvidenceStatus.CONTESTED:
            contested.append(key)
        elif status == EvidenceStatus.STALE:
            stale.append(key)
        elif status == EvidenceStatus.MISSING:
            missing.append(key)
        else:
            rejected.append(key)
    return ContaminationReport(agent_name, accepted, rejected, contested, stale, missing)


def validate_no_contaminated_truth_use(text: str, report: ContaminationReport) -> None:
    lowered = text.lower()
    for key in report.rejected_facts + report.contested_facts + report.stale_facts + report.missing_facts:
        terms = [part.replace("_", " ") for part in key.split(".")]
        if any(term in lowered for term in terms) and not any(
            token in lowered for token in ("missing", "contested", "uncertain", "blocked", "stale")
        ):
            raise EquityValidationError(f"Agent used non-accepted fact as truth: {key}")


@dataclass(frozen=True)
class ResearchManagerAdjudication:
    factor: str
    bull_claim: str
    bear_claim: str
    evidence_decider: str
    verdict: str
    excluded_claims: list[str]


def validate_research_manager_adjudication(rows: list[ResearchManagerAdjudication]) -> None:
    if not rows:
        raise EquityValidationError("Research Manager cannot issue a rating without factor-by-factor adjudication.")


@dataclass(frozen=True)
class PMSanityCheck:
    analyst_consensus_ok: bool
    management_guidance_ok: bool
    short_interest_ok: bool
    evidence_status_ok: bool
    debate_status_ok: bool
    limitations: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(
            [
                self.analyst_consensus_ok,
                self.management_guidance_ok,
                self.short_interest_ok,
                self.evidence_status_ok,
                self.debate_status_ok,
            ]
        )


def run_pm_sanity_checks(evidence: EvidenceStore, debate_result: DebateResult | None = None) -> PMSanityCheck:
    consensus = retrieve_analyst_consensus_from_store(evidence)
    short_interest = retrieve_short_interest_from_store(evidence)
    limitations: list[str] = []
    if consensus.status != EvidenceStatus.RETRIEVED:
        limitations.append("Analyst consensus has fewer than two sources.")
    if not evidence.is_usable("guidance.management"):
        limitations.append("Management guidance is missing or unresolved.")
    if short_interest.status != EvidenceStatus.RETRIEVED:
        limitations.append("Short interest is missing.")
    debate_ok = True
    if debate_result is not None:
        try:
            validate_debate(debate_result)
        except DebateValidationError as exc:
            debate_ok = False
            limitations.append(str(exc))
    return PMSanityCheck(
        analyst_consensus_ok=consensus.status == EvidenceStatus.RETRIEVED,
        management_guidance_ok=evidence.is_usable("guidance.management"),
        short_interest_ok=short_interest.status == EvidenceStatus.RETRIEVED,
        evidence_status_ok=not any(gap.blocking for gap in evidence.gaps.values()),
        debate_status_ok=debate_ok,
        limitations=limitations,
    )


def validate_pm_can_issue_verdict(check: PMSanityCheck) -> None:
    if not check.passed:
        raise EquityValidationError("Portfolio Manager sanity checks failed: " + "; ".join(check.limitations))


class EquityValidationError(RuntimeError):
    pass
