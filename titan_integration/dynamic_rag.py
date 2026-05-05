"""Resolver-driven dynamic RAG repair for equity evidence stores.

This module is intentionally deterministic and fixture-friendly. Production
uses public-first URL discovery where available; tests can provide source
fixtures through the same promotion interface so no regression depends on live
websites being reachable.
"""

from __future__ import annotations

from dataclasses import dataclass
import html
import hashlib
from pathlib import Path
from typing import Any
import re
from urllib.parse import parse_qs, quote_plus, unquote, urlparse
from urllib.request import Request, urlopen

from .equity_evidence import (
    EvidenceStatus,
    EvidenceStore,
    MANDATORY_EQUITY_KEYS,
    ResolverTrace,
    reconcile_evidence_status,
)
from .equity_public_resolvers import (
    ResolverSource,
    collect_public_equity_sources,
    load_fixture_sources,
    promote_pre_agent_sources,
)
from .earnings_event_resolver import promote_earnings_event_resolution, resolve_earnings_events


RESOLVER_CHAIN = (
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

SOURCE_CLASS_BY_KEY: dict[str, tuple[str, ...]] = {
    "fundamentals.latest_earnings_release": ("official_issuer_site", "sec_regulatory", "reputable_news_wire"),
    "earnings.latest_reported.date": ("official_issuer_site", "reputable_news_wire", "specialist_aggregator"),
    "earnings.event_state": ("official_issuer_site", "reputable_news_wire", "specialist_aggregator"),
    "fundamentals.latest_financial_filing": ("sec_regulatory", "official_issuer_site"),
    "fundamentals.latest_earnings_8k": ("sec_regulatory", "official_issuer_site"),
    "fundamentals.earnings_transcript": ("official_issuer_site", "specialist_aggregator", "reputable_news_wire"),
    "earnings.actual_vs_consensus": ("specialist_aggregator", "reputable_news_wire"),
    "guidance.management": ("official_issuer_site", "sec_regulatory", "reputable_news_wire"),
    "business.rpo_or_backlog": ("official_issuer_site", "sec_regulatory"),
    "capex.guidance": ("official_issuer_site", "sec_regulatory", "reputable_news_wire"),
    "cashflow.fcf_inputs": ("sec_regulatory", "official_issuer_site", "specialist_aggregator"),
    "cashflow.latest.ocf": ("sec_regulatory", "official_issuer_site", "specialist_aggregator"),
    "consensus.analyst": ("specialist_aggregator",),
    "positioning.short_interest": ("sec_regulatory", "specialist_aggregator"),
    "short_interest.shares_short": ("sec_regulatory", "specialist_aggregator"),
    "ownership.form4_90d": ("sec_regulatory", "specialist_aggregator"),
    "options.put_call": ("specialist_aggregator",),
    "catalyst.next_earnings_date": ("official_issuer_site", "specialist_aggregator"),
    "valuation.forward_pe_basis": ("specialist_aggregator",),
    "market.snapshot.primary": ("api", "specialist_aggregator"),
}

SOURCE_CLASS_DOMAIN_HINTS: dict[str, tuple[str, ...]] = {
    "official_issuer_site": ("investor", "ir.", "/investor", "/investors", "earnings", "results"),
    "sec_regulatory": ("sec.gov", "edgar"),
    "reputable_news_wire": ("reuters", "bloomberg", "cnbc", "wsj", "barrons", "prnewswire", "businesswire"),
    "specialist_aggregator": ("stockanalysis.com", "marketbeat.com", "nasdaq.com", "finance.yahoo.com", "tipranks.com", "fintel.io", "barchart.com"),
    "api": ("yahoo", "yfinance", "nasdaq.com", "stockanalysis.com"),
}


CRITICAL_REPAIR_KEYS = {
    "market.latest_price",
    "market.ohlcv_6m",
    "market.snapshot.primary",
    "fundamentals.latest_earnings_release",
    "earnings.latest_reported.date",
    "earnings.event_state",
    "fundamentals.latest_financial_filing",
    "fundamentals.latest_earnings_8k",
    "fundamentals.earnings_transcript",
    "earnings.actual_vs_consensus",
    "guidance.management",
    "business.rpo_or_backlog",
    "capex.guidance",
    "cashflow.fcf_inputs",
    "cashflow.latest.ocf",
    "consensus.analyst",
    "positioning.short_interest",
    "short_interest.shares_short",
    "ownership.form4_90d",
    "options.put_call",
    "catalyst.next_earnings_date",
    "valuation.forward_pe_basis",
}


@dataclass(frozen=True)
class DynamicRagResult:
    store: EvidenceStore
    repaired_keys: list[str]
    unresolved_keys: list[str]
    traces: list[ResolverTrace]
    institutional_mode_allowed: bool


@dataclass(frozen=True)
class QuerySpec:
    query: str
    source_class: str
    priority: int


@dataclass(frozen=True)
class SearchCandidate:
    url: str
    query: str
    source_class: str
    rank: int
    score: float
    title: str = ""
    snippet: str = ""


@dataclass(frozen=True)
class SearchResult:
    url: str
    title: str
    snippet: str
    rank: int


def build_queries(
    ticker: str,
    company: str,
    evidence_key: str,
    report_date: str,
    fiscal_period: str | None = None,
) -> list[str]:
    """Build evidence-key-specific retrieval queries."""
    symbol = ticker.upper()
    issuer = company or symbol
    period = fiscal_period or "latest quarter"
    templates: dict[str, list[str]] = {
        "fundamentals.latest_earnings_release": [
            f"{issuer} investor relations {period} earnings release",
            f"site:investor.{issuer.split()[0].lower()}.com {issuer} {period} earnings release",
            f"{symbol} {period} earnings release revenue EPS {report_date}",
        ],
        "earnings.actual_vs_consensus": [
            f"{symbol} {period} actual revenue EPS consensus estimate",
            f"{issuer} {period} revenue EPS beat consensus",
            f"{symbol} MarketBeat earnings actual consensus {report_date}",
        ],
        "guidance.management": [
            f"{issuer} earnings call transcript guidance outlook {period}",
            f"{issuer} investor relations guidance capex outlook {report_date}",
            f"{symbol} management guidance transcript {report_date}",
        ],
        "capex.guidance": [
            f"{issuer} earnings call transcript capital expenditures guidance {period}",
            f"{issuer} capital spending capex outlook AI infrastructure {report_date}",
            f"{symbol} management commentary capex guidance fiscal year calendar year",
            f"{issuer} investor relations capex forecast data center investment",
        ],
        "business.rpo_or_backlog": [
            f"{issuer} remaining performance obligation RPO {period} earnings release",
            f"{issuer} 10-Q remaining performance obligations {report_date}",
            f"{issuer} contracted not recognized revenue backlog latest quarter",
        ],
        "cashflow.fcf_inputs": [
            f"{issuer} cash flow statement operating cash flow capital expenditures {period}",
            f"{symbol} 10-Q net cash provided by operations additions to property and equipment",
        ],
        "cashflow.latest.ocf": [
            f"{issuer} operating cash flow {period} 10-Q",
            f"{symbol} net cash provided by operations latest quarter",
        ],
        "valuation.forward_pe_basis": [
            f"{symbol} FY1 EPS estimate FY2 EPS estimate forward PE",
            f"{symbol} analyst EPS estimates next fiscal year stockanalysis marketbeat",
        ],
        "consensus.analyst": [
            f"{symbol} analyst consensus buy hold sell average price target",
            f"{symbol} MarketBeat TipRanks StockAnalysis analyst consensus",
        ],
        "positioning.short_interest": [
            f"{symbol} short interest percent float days to cover",
            f"{symbol} MarketBeat Nasdaq FINRA short interest",
        ],
        "short_interest.shares_short": [
            f"{symbol} shares short percent float days to cover",
            f"{symbol} short interest shares short MarketBeat Nasdaq",
            f"{symbol} FINRA short interest shares short settlement date",
        ],
        "ownership.form4_90d": [
            f"{symbol} SEC Form 4 insider transactions latest",
            f"{issuer} EDGAR Form 4 insider ownership latest filing",
            f"{symbol} insider activity Form 4 last 90 days",
        ],
        "options.put_call": [
            f"{symbol} put call ratio options open interest volume",
            f"{symbol} Barchart Fintel put call ratio",
        ],
        "catalyst.next_earnings_date": [
            f"{symbol} next earnings date investor relations",
            f"{issuer} earnings calendar next earnings date",
        ],
        "earnings.latest_reported.date": [
            f"{symbol} latest earnings release investor relations {report_date}",
            f"{issuer} latest quarterly results earnings press release",
            f"{symbol} latest reported fiscal quarter earnings call",
        ],
        "earnings.event_state": [
            f"{symbol} latest reported earnings and next estimated earnings date",
            f"{issuer} investor relations earnings release next earnings date",
        ],
        "market.snapshot.primary": [
            f"{symbol} stock quote open high low volume timestamp",
            f"{symbol} Nasdaq Yahoo Finance StockAnalysis current quote",
        ],
    }
    return templates.get(evidence_key, [f"{symbol} {issuer} {evidence_key.replace('.', ' ')} {report_date}"])


def build_query_plan(
    ticker: str,
    company: str,
    evidence_key: str,
    report_date: str,
    fiscal_period: str | None = None,
) -> list[QuerySpec]:
    """Create a multi-query, source-aware retrieval plan for one evidence key."""
    base_queries = build_queries(ticker, company, evidence_key, report_date, fiscal_period)
    source_classes = SOURCE_CLASS_BY_KEY.get(evidence_key, ("official_issuer_site", "sec_regulatory", "reputable_news_wire", "specialist_aggregator", "general_web_search"))
    plan: list[QuerySpec] = []
    seen: set[tuple[str, str]] = set()
    priority = 0
    for source_class in source_classes:
        for query in base_queries:
            for expanded in _expand_query_for_source_class(query, ticker, company, source_class, report_date):
                key = (source_class, expanded.lower())
                if key in seen:
                    continue
                seen.add(key)
                plan.append(QuerySpec(expanded, source_class, priority))
                priority += 1
    if not any(spec.source_class == "general_web_search" for spec in plan):
        for query in base_queries[:2]:
            key = ("general_web_search", query.lower())
            if key not in seen:
                plan.append(QuerySpec(query, "general_web_search", priority))
                priority += 1
    return plan


def pre_render_repair_loop(
    store: EvidenceStore,
    *,
    company: str,
    fixture_path: Path | None = None,
    allow_network: bool = True,
) -> DynamicRagResult:
    """Run the hybrid resolver chain before Stage 5 decides report mode."""
    repaired_before = set(_usable_keys(store))
    unresolved = _repair_targets(store)
    fixture_sources = load_fixture_sources(fixture_path) if fixture_path else []
    public_sources = collect_public_equity_sources(store.ticker, store.report_date, None) if allow_network else []
    traces: list[ResolverTrace] = []

    for key in unresolved:
        plan = build_query_plan(store.ticker, company, key, store.report_date)
        queries = [item.query for item in plan]
        attempted_sources = list(RESOLVER_CHAIN)
        sources = list(fixture_sources) + list(public_sources)
        if allow_network:
            sources.extend(_discover_general_web_sources(key, plan, store.report_date))
        before_status = store.status(key)
        if sources:
            promote_pre_agent_sources(store, _sources_for_key(key, sources))
        reconcile_evidence_status(store)
        after = store.get(key)
        success = after is not None and after.status in {EvidenceStatus.RETRIEVED, EvidenceStatus.COMPUTED}
        trace = ResolverTrace(
            evidence_key=key,
            attempted_queries=queries,
            attempted_sources=attempted_sources,
            successful_sources=_successful_source_names(key, store),
            selected_source=after.source_name if success and after else None,
            selected_value=after.value if success and after else None,
            confidence=after.confidence or "medium" if success and after else "low",
            direct_or_proxy=after.direct_or_proxy if success and after else "none",
            extraction_method="fixture_or_public_source_promotion",
            validation_status=store.status(key).value,
            failure_reason=None if success else _failure_reason(store, key, before_status),
        )
        store.record_trace(trace)
        store.record_attempt(
            "dynamic_rag_repair_loop",
            key,
            store.status(key),
            f"Resolver chain exhausted={not success}; queries={queries[:3]}",
        )
        traces.append(trace)

    earnings_resolution = resolve_earnings_events(
        store.ticker,
        company,
        store.report_date,
        fixture_path,
        sources=list(fixture_sources) + list(public_sources),
        allow_network=allow_network,
    )
    promote_earnings_event_resolution(store, earnings_resolution)

    final_store = reconcile_evidence_status(store)
    repaired_after = set(_usable_keys(final_store))
    repaired_keys = sorted(repaired_after - repaired_before)
    unresolved_keys = sorted(_repair_targets(final_store))
    return DynamicRagResult(
        store=final_store,
        repaired_keys=repaired_keys,
        unresolved_keys=unresolved_keys,
        traces=traces,
        institutional_mode_allowed=not _critical_failures(final_store),
    )


def _repair_targets(store: EvidenceStore) -> list[str]:
    targets: list[str] = []
    for key in sorted(CRITICAL_REPAIR_KEYS | set(MANDATORY_EQUITY_KEYS)):
        status = store.status(key)
        if status in {
            EvidenceStatus.MISSING,
            EvidenceStatus.RETRIEVED_INVALID,
            EvidenceStatus.BLOCKED,
            EvidenceStatus.CONTESTED,
            EvidenceStatus.EXTRACTION_FAILED,
            EvidenceStatus.SOURCE_CONFLICT,
        }:
            targets.append(key)
    return targets


def _critical_failures(store: EvidenceStore) -> list[str]:
    failures: list[str] = []
    for key, spec in MANDATORY_EQUITY_KEYS.items():
        if spec.get("blocking") and store.status(key) not in {EvidenceStatus.RETRIEVED, EvidenceStatus.COMPUTED}:
            failures.append(key)
    for key in ("earnings.actual_vs_consensus", "cashflow.fcf_inputs", "valuation.forward_pe_basis"):
        if store.status(key) not in {EvidenceStatus.RETRIEVED, EvidenceStatus.COMPUTED}:
            failures.append(key)
    return sorted(set(failures))


def _usable_keys(store: EvidenceStore) -> list[str]:
    return [key for key, item in store.items.items() if item.status in {EvidenceStatus.RETRIEVED, EvidenceStatus.COMPUTED}]


def _sources_for_key(key: str, sources: list[ResolverSource]) -> list[ResolverSource]:
    query_terms = set(key.replace(".", " ").split())
    selected = []
    for source in sources:
        text = f"{source.title} {source.publisher} {source.source_type} {source.text}".lower()
        if any(term in text for term in query_terms):
            selected.append(source)
    return selected or sources


def _successful_source_names(key: str, store: EvidenceStore) -> list[str]:
    item = store.get(key)
    return [item.source_name] if item and item.status in {EvidenceStatus.RETRIEVED, EvidenceStatus.COMPUTED} else []


def _failure_reason(store: EvidenceStore, key: str, before_status: EvidenceStatus) -> str:
    gap = store.gaps.get(key)
    if gap:
        return gap.validation_result
    item = store.get(key)
    if item and item.status == EvidenceStatus.RETRIEVED_INVALID:
        return "; ".join(item.limitations or []) or "Retrieved evidence failed validation."
    return f"Resolver chain did not upgrade status from {before_status.value}."


def _discover_general_web_sources(key: str, queries: list[str] | list[QuerySpec], report_date: str) -> list[ResolverSource]:
    """Source-aware public web discovery fallback for dynamic RAG repair.

    This implements a production-RAG style recall/rank loop: expand queries by
    evidence key, search multiple source classes, dedupe URLs, rerank candidates,
    fetch the highest scoring pages, and preserve URL citations in evidence.
    """
    out: list[ResolverSource] = []
    plan = _coerce_query_plan(key, queries)
    candidates = _rank_search_candidates(key, plan)
    for candidate in candidates[:10]:
        text = _fetch_public_text(candidate.url)
        retrieval_method = "dynamic_web_rag"
        limitations = [
            f"Discovered by query='{candidate.query}'.",
            f"source_class={candidate.source_class}; retrieval_score={candidate.score:.4f}.",
            "Source permissions and numeric plausibility validation still apply before promotion.",
        ]
        if not text:
            text = _search_result_text(candidate)
            retrieval_method = "dynamic_web_rag_snippet"
            limitations.append("Target fetch failed or returned empty content; using search result title/snippet as lower-confidence discovery text.")
        if not text:
            continue
        out.append(
            ResolverSource(
                source_id=f"search_{_stable_id(candidate.url)}",
                title=candidate.title or f"Search result for {key}",
                publisher=_publisher(candidate.url),
                url=candidate.url,
                text=text,
                source_type=key,
                retrieval_method=retrieval_method,
                as_of_date=report_date,
                confidence=_confidence_for_candidate(candidate),
                direct_or_proxy="direct",
                source_level=_source_level_for_discovered_url(candidate.url),
                limitations=limitations,
            )
        )
    return out


def _coerce_query_plan(key: str, queries: list[str] | list[QuerySpec]) -> list[QuerySpec]:
    if not queries:
        return []
    if isinstance(queries[0], QuerySpec):
        return list(queries)  # type: ignore[list-item]
    return [QuerySpec(str(query), "general_web_search", index) for index, query in enumerate(queries)]


def _expand_query_for_source_class(query: str, ticker: str, company: str, source_class: str, report_date: str) -> list[str]:
    symbol = ticker.upper()
    issuer = company or symbol
    base = [query]
    if source_class == "official_issuer_site":
        base.extend(
            [
                f"{issuer} investor relations {query}",
                f"{symbol} official investor relations {query}",
                f"{issuer} earnings release transcript investor relations {report_date}",
            ]
        )
    elif source_class == "sec_regulatory":
        base.extend(
            [
                f"site:sec.gov {symbol} 10-Q 10-K 8-K {query}",
                f"{symbol} SEC EDGAR {query}",
            ]
        )
    elif source_class == "reputable_news_wire":
        base.extend(
            [
                f"{symbol} Reuters Bloomberg CNBC {query}",
                f"{issuer} press release BusinessWire PRNewswire {query}",
            ]
        )
    elif source_class == "specialist_aggregator":
        base.extend(
            [
                f"{symbol} StockAnalysis MarketBeat Nasdaq {query}",
                f"{symbol} Yahoo Finance TipRanks Fintel Barchart {query}",
            ]
        )
    return [re.sub(r"\s+", " ", item).strip() for item in base if item.strip()]


def _rank_search_candidates(key: str, plan: list[QuerySpec]) -> list[SearchCandidate]:
    by_url: dict[str, SearchCandidate] = {}
    key_terms = set(re.findall(r"[a-z0-9]+", key.replace(".", " ").lower()))
    for spec in plan[:16]:
        results = _search_results(spec.query)
        for result in results[:6]:
            url = result.url
            if not _url_allowed_for_source_class(url, spec.source_class):
                continue
            score = _candidate_score(url, spec, result.rank, key_terms, f"{result.title} {result.snippet}")
            existing = by_url.get(url)
            candidate = SearchCandidate(
                url=url,
                query=spec.query,
                source_class=spec.source_class,
                rank=result.rank,
                score=score,
                title=result.title,
                snippet=result.snippet,
            )
            if existing is None or candidate.score > existing.score:
                by_url[url] = candidate
    return sorted(by_url.values(), key=lambda item: item.score, reverse=True)


def _candidate_score(url: str, spec: QuerySpec, rank: int, key_terms: set[str], search_text: str = "") -> float:
    host_path = f"{_publisher(url)} {urlparse(url).path} {search_text}".lower()
    source_bonus = _source_class_score(url, spec.source_class)
    term_bonus = sum(0.08 for term in key_terms if term and term in host_path)
    priority_bonus = max(0.0, 1.0 - (spec.priority * 0.025))
    rrf = 1.0 / (60 + rank)
    return source_bonus + term_bonus + priority_bonus + rrf


def _source_class_score(url: str, source_class: str) -> float:
    text = f"{_publisher(url)} {urlparse(url).path}".lower()
    hints = SOURCE_CLASS_DOMAIN_HINTS.get(source_class, ())
    if source_class == "general_web_search":
        return 0.35
    return 0.75 if any(hint in text for hint in hints) else 0.15


def _url_allowed_for_source_class(url: str, source_class: str) -> bool:
    if source_class == "general_web_search":
        return True
    text = f"{_publisher(url)} {urlparse(url).path}".lower()
    hints = SOURCE_CLASS_DOMAIN_HINTS.get(source_class, ())
    return any(hint in text for hint in hints)


def _confidence_for_candidate(candidate: SearchCandidate) -> str:
    if candidate.source_class in {"official_issuer_site", "sec_regulatory"} and candidate.score >= 1.5:
        return "high"
    if candidate.score >= 1.0:
        return "medium"
    return "low"


def _stable_id(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:12]


def _search_urls(query: str) -> list[str]:
    return [item.url for item in _search_results(query)]


def _search_results(query: str) -> list[SearchResult]:
    url = f"https://duckduckgo.com/html/?q={quote_plus(query)}"
    raw_html = _fetch_public_html(url, limit=300_000)
    results: list[SearchResult] = []
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
        results.append(SearchResult(href, title, snippet, len(results) + 1))
    return results


def _search_result_text(candidate: SearchCandidate) -> str:
    return _clean_search_text(f"{candidate.title}. {candidate.snippet}")


def _clean_search_text(text: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", text or ""))).strip()


def _fetch_public_text(url: str, limit: int = 700_000) -> str:
    request = Request(url, headers={"User-Agent": "TitanIntegration/0.1 dynamic-rag"})
    try:
        with urlopen(request, timeout=5) as response:
            data = response.read(limit).decode("utf-8", errors="ignore")
    except Exception:
        return ""
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", data))


def _fetch_public_html(url: str, limit: int = 700_000) -> str:
    request = Request(url, headers={"User-Agent": "Mozilla/5.0 TitanIntegration/0.1 dynamic-rag"})
    try:
        with urlopen(request, timeout=6) as response:
            return response.read(limit).decode("utf-8", errors="ignore")
    except Exception:
        return ""


def _publisher(url: str) -> str:
    return re.sub(r"^www\.", "", urlparse(url).netloc.lower()) or "public_web"


def _source_level_for_discovered_url(url: str):
    from .equity_evidence import SourceLevel

    host = _publisher(url)
    if "sec.gov" in host:
        return SourceLevel.SEC_OR_REGULATORY
    path = urlparse(url).path.lower()
    if "investor" in host or "/investor" in path or host.startswith("ir."):
        return SourceLevel.COMPANY_IR_OR_TRANSCRIPT
    if any(name in host for name in ("reuters", "bloomberg", "cnbc", "wsj", "barrons")):
        return SourceLevel.MAJOR_WIRE_OR_REPUTABLE_NEWS
    return SourceLevel.AGGREGATOR_OR_MARKET_DATA
