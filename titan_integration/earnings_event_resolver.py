"""Global equity earnings-event resolver.

This resolver exists because a next-earnings page can be stale even when it
looks source-backed. The pipeline must first establish whether the latest
quarter has already been reported, then resolve the next estimated event.
"""

from __future__ import annotations

import json
import html
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote_plus, unquote, urlparse
from urllib.request import Request, urlopen

from .equity_evidence import (
    EvidenceGap,
    EvidenceItem,
    EvidenceStatus,
    EvidenceStore,
    ResolverTrace,
    SourceLevel,
    utc_now_iso,
)
from .equity_public_resolvers import ResolverSource, load_fixture_sources


EARNINGS_EVENT_RESOLVER_CHAIN = (
    "api",
    "official_issuer_site",
    "sec_regulatory",
    "reputable_news_wire",
    "specialist_aggregator",
    "general_web_search",
    "search_query_expansion",
    "extraction_retry",
    "source_conflict_reconciliation",
)


@dataclass(frozen=True)
class EarningsEventResolution:
    ticker: str
    report_date: str
    latest_reported_date: str | None
    latest_reported_fiscal_period: str | None
    latest_reported_source_name: str | None
    latest_reported_source_url: str | None
    next_estimated_date: str | None
    next_estimated_source_name: str | None
    next_estimated_source_url: str | None
    event_state: str
    stale_or_conflicting_dates: list[str] = field(default_factory=list)
    attempts: list[str] = field(default_factory=list)
    attempted_queries: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class _EventCandidate:
    date_value: str
    event_type: str
    source: ResolverSource
    fiscal_period: str | None = None


@dataclass(frozen=True)
class _SearchResult:
    url: str
    title: str
    snippet: str
    rank: int


def resolve_earnings_events(
    ticker: str,
    company: str,
    report_date: str,
    fixture_path: Path | None = None,
    *,
    sources: list[ResolverSource] | None = None,
    allow_network: bool = True,
) -> EarningsEventResolution:
    """Resolve latest reported and next estimated earnings events.

    The function is ticker-generic and fixture-friendly. Production uses
    public-first discovery; tests can pass `sources` directly.
    """
    symbol = ticker.upper()
    source_records = list(sources or [])
    if not source_records:
        source_records.extend(load_fixture_sources(fixture_path))
    queries = _earnings_queries(symbol, company, report_date)
    if allow_network and not source_records:
        source_records.extend(_discover_earnings_sources(symbol, company, report_date, queries))

    report_dt = _parse_iso_date(report_date)
    latest_candidates: list[_EventCandidate] = []
    next_candidates: list[_EventCandidate] = []
    generic_future_candidates: list[_EventCandidate] = []
    attempts = list(EARNINGS_EVENT_RESOLVER_CHAIN)

    for source in source_records:
        found = _extract_candidates(source, report_dt)
        latest_candidates.extend(candidate for candidate in found if candidate.event_type == "latest_reported")
        next_candidates.extend(candidate for candidate in found if candidate.event_type == "next_estimated")
        generic_future_candidates.extend(candidate for candidate in found if candidate.event_type == "generic_future_earnings")

    latest = _select_latest_reported(latest_candidates, report_dt)
    next_event = _select_next_estimated(next_candidates, generic_future_candidates, latest, report_dt)
    stale_dates = _stale_conflicts(generic_future_candidates + next_candidates, latest, next_event, report_dt)

    event_state = "unresolved"
    if latest and next_event:
        event_state = "already_reported_next_estimated"
    elif latest:
        event_state = "already_reported_next_unresolved"
    elif next_event:
        event_state = "upcoming_or_estimated"
    if stale_dates:
        event_state = f"{event_state}_with_stale_conflict" if event_state != "unresolved" else "stale_conflict"

    return EarningsEventResolution(
        ticker=symbol,
        report_date=report_date,
        latest_reported_date=latest.date_value if latest else None,
        latest_reported_fiscal_period=latest.fiscal_period if latest else None,
        latest_reported_source_name=_source_name(latest.source) if latest else None,
        latest_reported_source_url=latest.source.url if latest else None,
        next_estimated_date=next_event.date_value if next_event else None,
        next_estimated_source_name=_source_name(next_event.source) if next_event else None,
        next_estimated_source_url=next_event.source.url if next_event else None,
        event_state=event_state,
        stale_or_conflicting_dates=stale_dates,
        attempts=attempts,
        attempted_queries=queries,
        limitations=[] if latest or next_event else ["Earnings-event resolver exhausted configured source chain without a usable date."],
    )


def promote_earnings_event_resolution(store: EvidenceStore, resolution: EarningsEventResolution) -> None:
    """Promote resolved event state into the typed evidence store."""
    retrieved_at = utc_now_iso()

    def add(
        key: str,
        value: Any,
        *,
        source_name: str | None,
        source_url: str | None,
        status: EvidenceStatus = EvidenceStatus.RETRIEVED,
        source_level: SourceLevel = SourceLevel.AGGREGATOR_OR_MARKET_DATA,
        as_of_date: str | None = None,
        limitations: list[str] | None = None,
    ) -> None:
        store.add_item(
            EvidenceItem(
                key=key,
                value=value,
                status=status,
                source_name=source_name or "Titan EarningsEventResolver",
                source_url=source_url,
                source_level=source_level,
                as_of_date=as_of_date or resolution.report_date,
                retrieved_at=retrieved_at,
                limitations=limitations or [],
                retrieval_method="earnings_event_resolver",
                confidence="high" if status == EvidenceStatus.RETRIEVED else "medium",
                direct_or_proxy="direct",
            )
        )
        store.record_attempt("earnings_event_resolver", key, status, f"Event state={resolution.event_state}.")

    if resolution.latest_reported_date:
        add(
            "earnings.latest_reported.date",
            resolution.latest_reported_date,
            source_name=resolution.latest_reported_source_name,
            source_url=resolution.latest_reported_source_url,
            source_level=SourceLevel.COMPANY_IR_OR_TRANSCRIPT,
            as_of_date=resolution.latest_reported_date,
        )
        if resolution.latest_reported_fiscal_period:
            add(
                "earnings.latest_reported.fiscal_period",
                resolution.latest_reported_fiscal_period,
                source_name=resolution.latest_reported_source_name,
                source_url=resolution.latest_reported_source_url,
                source_level=SourceLevel.COMPANY_IR_OR_TRANSCRIPT,
                as_of_date=resolution.latest_reported_date,
            )
        add(
            "fundamentals.latest_earnings_release",
            {
                "date": resolution.latest_reported_date,
                "fiscal_period": resolution.latest_reported_fiscal_period,
                "source": resolution.latest_reported_source_name,
                "url": resolution.latest_reported_source_url,
            },
            source_name=resolution.latest_reported_source_name,
            source_url=resolution.latest_reported_source_url,
            source_level=SourceLevel.COMPANY_IR_OR_TRANSCRIPT,
            as_of_date=resolution.latest_reported_date,
        )

    add(
        "earnings.event_state",
        {
            "state": resolution.event_state,
            "latest_reported_date": resolution.latest_reported_date,
            "next_estimated_date": resolution.next_estimated_date,
            "stale_or_conflicting_dates": resolution.stale_or_conflicting_dates,
        },
        source_name="Titan EarningsEventResolver",
        source_url=None,
        source_level=SourceLevel.COMPANY_IR_OR_TRANSCRIPT,
        status=EvidenceStatus.RETRIEVED if resolution.latest_reported_date or resolution.next_estimated_date else EvidenceStatus.PARTIAL,
        limitations=resolution.limitations,
    )

    if resolution.next_estimated_date:
        add(
            "catalyst.next_earnings_date.value",
            resolution.next_estimated_date,
            source_name=resolution.next_estimated_source_name,
            source_url=resolution.next_estimated_source_url,
            source_level=SourceLevel.AGGREGATOR_OR_MARKET_DATA,
            as_of_date=resolution.next_estimated_date,
        )
        add(
            "catalyst.next_earnings_date",
            {
                "date": resolution.next_estimated_date,
                "state": resolution.event_state,
                "source": resolution.next_estimated_source_name,
                "url": resolution.next_estimated_source_url,
            },
            source_name=resolution.next_estimated_source_name,
            source_url=resolution.next_estimated_source_url,
            source_level=SourceLevel.AGGREGATOR_OR_MARKET_DATA,
            as_of_date=resolution.next_estimated_date,
        )
        add(
            "catalyst.next_earnings_date.sources",
            [resolution.next_estimated_source_name],
            source_name=resolution.next_estimated_source_name,
            source_url=resolution.next_estimated_source_url,
            source_level=SourceLevel.AGGREGATOR_OR_MARKET_DATA,
            as_of_date=resolution.next_estimated_date,
        )

    if resolution.stale_or_conflicting_dates:
        detail = {
            "stale_or_conflicting_dates": resolution.stale_or_conflicting_dates,
            "latest_reported_date": resolution.latest_reported_date,
            "next_estimated_date": resolution.next_estimated_date,
            "rule": "Do not describe stale dates as upcoming earnings when a newer latest-reported/next-estimated event state is resolved.",
        }
        add(
            "catalyst.stale_earnings_date_conflict",
            detail,
            source_name="Titan EarningsEventResolver",
            source_url=None,
            source_level=SourceLevel.COMPANY_IR_OR_TRANSCRIPT,
            status=EvidenceStatus.STALE,
            limitations=["Potential stale earnings catalyst detected and quarantined from final-truth usage."],
        )
        store.add_gap(
            EvidenceGap(
                key="catalyst.stale_earnings_date_conflict",
                label="Stale or conflicting earnings catalyst date",
                status=EvidenceStatus.STALE,
                source_classes_attempted=list(EARNINGS_EVENT_RESOLVER_CHAIN),
                validation_result=f"Conflicting stale dates detected: {', '.join(resolution.stale_or_conflicting_dates)}.",
                thesis_impact="Agents must not treat stale earnings dates as upcoming catalysts.",
                next_best_evidence="Use issuer IR latest release and at least one reputable next-date provider.",
                constrained_conclusion="Discuss stale dates only as invalidated catalyst evidence.",
                blocking=False,
            )
        )

    store.record_trace(
        ResolverTrace(
            evidence_key="earnings.event_state",
            attempted_queries=resolution.attempted_queries,
            attempted_sources=list(resolution.attempts),
            successful_sources=[name for name in (resolution.latest_reported_source_name, resolution.next_estimated_source_name) if name],
            selected_source=resolution.latest_reported_source_name or resolution.next_estimated_source_name,
            selected_value={
                "latest_reported_date": resolution.latest_reported_date,
                "next_estimated_date": resolution.next_estimated_date,
                "stale_or_conflicting_dates": resolution.stale_or_conflicting_dates,
            },
            confidence="high" if resolution.latest_reported_date or resolution.next_estimated_date else "low",
            direct_or_proxy="direct",
            extraction_method="earnings_event_state_resolver",
            validation_status=resolution.event_state,
            failure_reason="; ".join(resolution.limitations) if resolution.limitations else None,
        )
    )


def _earnings_queries(ticker: str, company: str, report_date: str) -> list[str]:
    issuer = company or ticker
    return [
        f"{ticker} latest earnings release investor relations {report_date}",
        f"{issuer} latest quarterly results earnings release",
        f"{ticker} next earnings date estimated",
        f"{ticker} fiscal quarter earnings call transcript latest reported",
        f"{ticker} earnings calendar next estimated date",
    ]


def _discover_earnings_sources(ticker: str, company: str, report_date: str, queries: list[str]) -> list[ResolverSource]:
    sources: list[ResolverSource] = []
    for query in queries[:4]:
        for result in _search_results(query)[:6]:
            text = _fetch_public_text(result.url)
            retrieval_method = "earnings_event_resolver"
            limitations = ["Discovered through earnings-event resolver source chain; source permissions still apply."]
            if not text:
                text = _clean_search_text(f"{result.title}. {result.snippet}")
                retrieval_method = "earnings_event_search_snippet"
                limitations.append("Target fetch failed or returned empty content; using search result title/snippet as lower-confidence discovery text.")
            if not text:
                continue
            sources.append(
                ResolverSource(
                    source_id=f"earnings_search_{len(sources)+1}",
                    title=result.title or f"{ticker} earnings event discovery",
                    publisher=_publisher(result.url),
                    url=result.url,
                    text=text,
                    source_type="earnings_event",
                    retrieval_method=retrieval_method,
                    as_of_date=report_date,
                    confidence="medium" if retrieval_method == "earnings_event_resolver" else "low",
                    direct_or_proxy="direct",
                    source_level=_source_level_for_url(result.url),
                    limitations=limitations,
                )
            )
    return sources


def _extract_candidates(source: ResolverSource, report_dt: date | None) -> list[_EventCandidate]:
    text = _clean(f"{source.title} {source.publisher} {source.url or ''} {source.text}")
    fiscal_period = _extract_fiscal_period(text)
    candidates: list[_EventCandidate] = []
    for date_value in _date_strings(text, report_dt):
        dt = _parse_iso_date(date_value)
        if not dt:
            continue
        window = _window_around(text, date_value.lower(), radius=180)
        if _looks_like_metadata_date(window):
            continue
        if _looks_like_reported_release(window, text, source):
            candidates.append(_EventCandidate(date_value, "latest_reported", source, fiscal_period))
        elif _looks_like_next_estimated(window):
            candidates.append(_EventCandidate(date_value, "next_estimated", source, fiscal_period))
        elif report_dt and dt > report_dt and _looks_like_earnings_context(window):
            candidates.append(_EventCandidate(date_value, "generic_future_earnings", source, fiscal_period))
    return candidates


def _select_latest_reported(candidates: list[_EventCandidate], report_dt: date | None) -> _EventCandidate | None:
    eligible = [candidate for candidate in candidates if not report_dt or (_parse_iso_date(candidate.date_value) or date.min) <= report_dt]
    if not eligible:
        return None
    return sorted(eligible, key=lambda item: (_parse_iso_date(item.date_value) or date.min, int(item.source.source_level)), reverse=True)[0]


def _select_next_estimated(
    next_candidates: list[_EventCandidate],
    generic_candidates: list[_EventCandidate],
    latest: _EventCandidate | None,
    report_dt: date | None,
) -> _EventCandidate | None:
    latest_dt = _parse_iso_date(latest.date_value) if latest else None
    pool = list(next_candidates) + list(generic_candidates)
    eligible: list[_EventCandidate] = []
    for candidate in pool:
        dt = _parse_iso_date(candidate.date_value)
        if not dt or (report_dt and dt <= report_dt):
            continue
        if latest_dt and (dt - latest_dt).days <= 45 and candidate.source.source_level < SourceLevel.COMPANY_IR_OR_TRANSCRIPT:
            continue
        eligible.append(candidate)
    if not eligible:
        return None
    next_marked = [candidate for candidate in eligible if candidate.event_type == "next_estimated"]
    selected_pool = next_marked or eligible
    return sorted(selected_pool, key=lambda item: (_parse_iso_date(item.date_value) or date.max, -int(item.source.source_level)))[0]


def _stale_conflicts(
    candidates: list[_EventCandidate],
    latest: _EventCandidate | None,
    selected_next: _EventCandidate | None,
    report_dt: date | None,
) -> list[str]:
    latest_dt = _parse_iso_date(latest.date_value) if latest else None
    selected = selected_next.date_value if selected_next else None
    stale: list[str] = []
    for candidate in candidates:
        dt = _parse_iso_date(candidate.date_value)
        if not dt:
            continue
        if selected and candidate.date_value == selected:
            continue
        is_near_recent_release = bool(latest_dt and 0 < (dt - latest_dt).days <= 21)
        is_after_report = bool(report_dt and dt > report_dt)
        if is_after_report and is_near_recent_release and candidate.source.source_level < SourceLevel.COMPANY_IR_OR_TRANSCRIPT:
            if candidate.date_value not in stale:
                stale.append(candidate.date_value)
    return stale


def _looks_like_reported_release(window: str, text: str, source: ResolverSource) -> bool:
    searchable_window = window.replace("-", " ").replace("_", " ")
    release_words = (
        "earnings release",
        "press release",
        "quarterly results",
        "results were released",
        "reported results",
        "earnings press release",
        "financial results are available",
        "third-quarter financial results",
        "first-quarter financial results",
        "second-quarter financial results",
        "fourth-quarter financial results",
        "q1 earnings report",
        "q2 earnings report",
        "q3 earnings report",
        "q4 earnings report",
        "announced earnings per share",
        "announced that fiscal year",
    )
    source_hint = source.source_level >= SourceLevel.COMPANY_IR_OR_TRANSCRIPT or "investor" in (source.url or "").lower()
    return any(word in searchable_window for word in release_words) and (
        source_hint or any(word in searchable_window for word in ("released", "reported", "announced"))
    )


def _looks_like_next_estimated(window: str) -> bool:
    if any(word in window for word in ("fiscal quarter ending", "period ending", "quarter ending", "quarter end")):
        return False
    if any(word in window for word in ("next earnings", "earnings date", "earnings calendar", "report earnings")):
        return True
    return any(word in window for word in ("estimated", "expected", "estimate")) and _looks_like_earnings_context(window)


def _looks_like_earnings_context(window: str) -> bool:
    return "earnings" in window or "quarterly results" in window or "conference call" in window


def _looks_like_metadata_date(window: str) -> bool:
    return any(
        phrase in window
        for phrase in (
            "date modified",
            "datepublished",
            "datemodified",
            "published on",
            "published:",
            "last updated",
            "updated may",
            "price quote as of",
            "delayed data",
            "closing price",
            "ex-dividend",
            "dividend date",
        )
    )


def _extract_fiscal_period(text: str) -> str | None:
    patterns = (
        r"\b(?:fy|fiscal year)\s*[- ]?(20\d{2}|\d{2})\s*[- ]?(q[1-4]|first quarter|second quarter|third quarter|fourth quarter)\b",
        r"\b(q[1-4])\s*(?:fy|fiscal year)\s*[- ]?(20\d{2}|\d{2})\b",
    )
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            return " ".join(part.upper() for part in match.groups())
    return None


def _fiscal_sort_key(value: str | None) -> tuple[int, int]:
    if not value:
        return (0, 0)
    text = value.lower()
    year_match = re.search(r"(20\d{2}|\b\d{2}\b)", text)
    year = int(year_match.group(1)) if year_match else 0
    if 0 < year < 100:
        year += 2000
    quarter = 0
    quarter_words = {
        "q1": 1,
        "first quarter": 1,
        "q2": 2,
        "second quarter": 2,
        "q3": 3,
        "third quarter": 3,
        "q4": 4,
        "fourth quarter": 4,
    }
    for label, index in quarter_words.items():
        if label in text:
            quarter = index
            break
    return (year, quarter)


def _date_strings(text: str, report_dt: date | None = None) -> list[str]:
    out: list[str] = []
    patterns = (
        r"\b20\d{2}[-/]\d{1,2}[-/]\d{1,2}\b",
        r"\b\d{1,2}/\d{1,2}/\d{2,4}\b",
        r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{1,2},?\s+20\d{2}\b",
        r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{1,2}\b",
    )
    for pattern in patterns:
        for match in re.finditer(pattern, text, re.I):
            normalized = _normalize_date(match.group(0), report_dt)
            if normalized and normalized not in out:
                out.append(normalized)
    return out


def _normalize_date(value: str, report_dt: date | None = None) -> str | None:
    text = value.strip().replace("/", "-")
    for fmt in ("%Y-%m-%d", "%Y-%m-%d", "%m-%d-%Y", "%m-%d-%y", "%B %d, %Y", "%b %d, %Y", "%B %d %Y", "%b %d %Y"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    if report_dt:
        for fmt in ("%B %d", "%b %d"):
            try:
                parsed = datetime.strptime(text, fmt).date()
                return date(report_dt.year, parsed.month, parsed.day).isoformat()
            except ValueError:
                continue
    try:
        return datetime.fromisoformat(text[:10]).date().isoformat()
    except ValueError:
        return None


def _parse_iso_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value)[:10]).date()
    except ValueError:
        return None


def _window_around(text: str, needle: str, radius: int = 160) -> str:
    idx = text.find(needle)
    if idx < 0:
        return text[: radius * 2]
    return text[max(0, idx - radius) : idx + len(needle) + radius]


def _search_urls(query: str) -> list[str]:
    return [item.url for item in _search_results(query)]


def _search_results(query: str) -> list[_SearchResult]:
    raw_html = _fetch_public_html(f"https://duckduckgo.com/html/?q={quote_plus(query)}", limit=300_000)
    results: list[_SearchResult] = []
    seen: set[str] = set()
    anchor_pattern = re.compile(r'<a[^>]*class="[^"]*result__a[^"]*"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', re.I | re.S)
    for match in anchor_pattern.finditer(raw_html):
        href = match.group(1)
        if "uddg=" in href:
            parsed = parse_qs(urlparse(html.unescape(href)).query).get("uddg")
            if parsed:
                href = unquote(parsed[0])
        if not href.startswith("http"):
            continue
        if any(blocked in href for blocked in ("duckduckgo.com", "javascript:", "mailto:")):
            continue
        if href in seen:
            continue
        seen.add(href)
        window = raw_html[match.end() : match.end() + 1400]
        title = _clean_search_text(match.group(2))
        snippet_match = re.search(r'class="[^"]*result__snippet[^"]*"[^>]*>(.*?)</a>|class="[^"]*result__snippet[^"]*"[^>]*>(.*?)</div>', window, re.I | re.S)
        snippet = _clean_search_text(next((part for part in (snippet_match.groups() if snippet_match else ()) if part), "") if snippet_match else "")
        results.append(_SearchResult(href, title, snippet, len(results) + 1))
    return results


def _fetch_public_text(url: str, limit: int = 700_000) -> str:
    request = Request(url, headers={"User-Agent": "TitanIntegration/0.1 earnings-event-resolver"})
    try:
        with urlopen(request, timeout=6) as response:
            data = response.read(limit).decode("utf-8", errors="ignore")
    except Exception:
        return ""
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", data))


def _fetch_public_html(url: str, limit: int = 700_000) -> str:
    request = Request(url, headers={"User-Agent": "Mozilla/5.0 TitanIntegration/0.1 earnings-event-resolver"})
    try:
        with urlopen(request, timeout=6) as response:
            return response.read(limit).decode("utf-8", errors="ignore")
    except Exception:
        return ""


def _publisher(url: str) -> str:
    return re.sub(r"^www\.", "", urlparse(url).netloc.lower()) or "public_web"


def _source_level_for_url(url: str) -> SourceLevel:
    host = _publisher(url)
    path = urlparse(url).path.lower()
    if "sec.gov" in host:
        return SourceLevel.SEC_OR_REGULATORY
    if "investor" in host or "/investor" in path or "ir." in host:
        return SourceLevel.COMPANY_IR_OR_TRANSCRIPT
    if any(name in host for name in ("reuters", "bloomberg", "cnbc", "wsj", "barrons", "prnewswire")):
        return SourceLevel.MAJOR_WIRE_OR_REPUTABLE_NEWS
    return SourceLevel.AGGREGATOR_OR_MARKET_DATA


def _source_name(source: ResolverSource) -> str:
    return source.publisher or source.title or source.source_id


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").lower()


def _clean_search_text(text: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", text or ""))).strip()
