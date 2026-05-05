"""Public-first equity evidence resolvers and source promotion."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

from .equity_evidence import EvidenceItem, EvidenceStatus, EvidenceStore, SourceLevel, utc_now_iso


@dataclass(frozen=True)
class ResolverSource:
    source_id: str
    title: str
    publisher: str
    url: str | None
    text: str
    source_type: str
    retrieval_method: str
    as_of_date: str | None
    confidence: str
    direct_or_proxy: str
    source_level: SourceLevel
    limitations: list[str] = field(default_factory=list)


def load_fixture_sources(path: Path | None) -> list[ResolverSource]:
    if not path or not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    records = payload.get("sources", payload if isinstance(payload, list) else [])
    return [_source_from_dict(item) for item in records]


def collect_public_equity_sources(ticker: str, report_date: str, fixture_path: Path | None = None) -> list[ResolverSource]:
    sources = load_fixture_sources(fixture_path)
    if fixture_path and sources:
        return sources
    for url, source_type in _candidate_public_urls(ticker):
        text = _fetch_text(url)
        if not text:
            continue
        sources.append(
            ResolverSource(
                source_id=f"public_{len(sources)+1}",
                title=f"{ticker.upper()} {source_type}",
                publisher=_publisher_from_url(url),
                url=url,
                text=text,
                source_type=source_type,
                retrieval_method="public_url",
                as_of_date=report_date,
                confidence="medium",
                direct_or_proxy=_direct_or_proxy_for_source(url, source_type),
                source_level=_source_level_for_url(url, source_type),
                limitations=["Public page parser is best-effort; fixture-backed tests cover deterministic extraction."],
            )
        )
    return sources


def promote_pre_agent_sources(store: EvidenceStore, sources: list[ResolverSource]) -> None:
    for source in sources:
        _promote_source(store, source)
    _compute_derived_items(store)


def _promote_source(store: EvidenceStore, source: ResolverSource) -> None:
    text = _clean(source.text)

    def add(key: str, value: Any, status: EvidenceStatus = EvidenceStatus.RETRIEVED, source_level: SourceLevel | None = None) -> None:
        store.add_item(
            EvidenceItem(
                key=key,
                value=value,
                status=status,
                source_name=source.publisher or source.title,
                source_url=source.url,
                source_level=source_level or source.source_level,
                as_of_date=source.as_of_date,
                retrieved_at=utc_now_iso(),
                limitations=list(source.limitations),
                retrieval_method=source.retrieval_method,
                confidence=source.confidence,
                direct_or_proxy=source.direct_or_proxy,
            )
        )
        store.record_attempt(source.retrieval_method, key, status, f"Promoted from {source.publisher}: {source.title}")

    if _is_earnings_release_source(source, text):
        add("fundamentals.latest_earnings_release", _summary(source))
    if source.direct_or_proxy == "direct" and _has(text, "form 8-k", "8-k", "earnings 8-k"):
        add("fundamentals.latest_earnings_8k", _summary(source), EvidenceStatus.PARTIAL, SourceLevel.SEC_OR_REGULATORY)
    if _source_looks_like_transcript(source) and _has(text, "transcript", "earnings call"):
        add("fundamentals.earnings_transcript", _summary(source))
    if _source_allows_guidance_claims(source) and _has(text, "guidance", "outlook"):
        add("guidance.management", _extract_guidance(text) or _summary(source))
    if _source_allows_fundamental_claims(source) and _has(
        text,
        "capex",
        "capital expenditure",
        "capital expenditures",
        "capital spending",
        "ai infrastructure",
        "data center investment",
    ):
        capex = _extract_money_near(text, ("capex", "capital expenditure", "capital expenditures", "capital spending", "ai infrastructure", "data center investment"))
        if capex is not None:
            if _source_allows_guidance_claims(source) and _has(text, "guidance", "expects", "outlook", "forecast", "planned", "expects to spend"):
                add("capex.full_year_guidance", capex, EvidenceStatus.RETRIEVED)
                add("capex.guidance", {"value": capex, "source_id": source.source_id}, EvidenceStatus.RETRIEVED)
            else:
                add("cashflow.latest.capex", capex, EvidenceStatus.PARTIAL)
        elif _source_allows_guidance_claims(source) and _indicates_capex_guidance(text):
            add(
                "capex.guidance",
                {
                    "source_id": source.source_id,
                    "guidance_type": "qualitative_or_partial",
                    "summary": _summary(source),
                },
                EvidenceStatus.RETRIEVED,
            )
    _promote_actual_vs_consensus(add, text, source)
    _promote_cloud_saas_metrics(add, text, source)
    _promote_cashflow(add, text, source)
    _promote_consensus(store, add, text, source)
    _promote_short_interest(add, text, source)
    _promote_options(add, text, source)
    _promote_earnings_date(add, text, source)
    _promote_ownership(add, text, source)


def promote_financial_filing(store: EvidenceStore, filings: list[dict[str, Any]], source_url: str | None = None) -> None:
    financial = _latest_form(filings, {"10-Q", "10-K"})
    earnings_8k = _latest_form(filings, {"8-K"})
    ownership = _latest_form(filings, {"3", "4", "5", "13D", "13G", "13F-HR", "13F"})
    if financial:
        store.add_item(EvidenceItem("fundamentals.latest_financial_filing", financial, EvidenceStatus.RETRIEVED, "SEC EDGAR", source_url, SourceLevel.SEC_OR_REGULATORY, financial.get("filing_date") or financial.get("report_date"), utc_now_iso(), retrieval_method="sec_api", confidence="high", direct_or_proxy="direct"))
        store.add_item(EvidenceItem("fundamentals.latest_filing", financial, EvidenceStatus.RETRIEVED, "SEC EDGAR", source_url, SourceLevel.SEC_OR_REGULATORY, financial.get("filing_date") or financial.get("report_date"), utc_now_iso(), retrieval_method="sec_api", confidence="high", direct_or_proxy="direct"))
    if earnings_8k:
        store.add_item(EvidenceItem("fundamentals.latest_earnings_8k", earnings_8k, EvidenceStatus.RETRIEVED, "SEC EDGAR", source_url, SourceLevel.SEC_OR_REGULATORY, earnings_8k.get("filing_date") or earnings_8k.get("report_date"), utc_now_iso(), retrieval_method="sec_api", confidence="high", direct_or_proxy="direct"))
    if ownership:
        store.add_item(EvidenceItem("ownership.latest_filing", ownership, EvidenceStatus.RETRIEVED, "SEC EDGAR", source_url, SourceLevel.SEC_OR_REGULATORY, ownership.get("filing_date") or ownership.get("report_date"), utc_now_iso(), retrieval_method="sec_api", confidence="high", direct_or_proxy="direct"))
        if str(ownership.get("form", "")).upper() in {"3", "4", "5"} and _within_days(store.report_date, ownership.get("filing_date") or ownership.get("report_date"), 90):
            store.add_item(EvidenceItem("ownership.form4_90d", ownership, EvidenceStatus.RETRIEVED, "SEC EDGAR Form 4", source_url, SourceLevel.SEC_OR_REGULATORY, ownership.get("filing_date") or ownership.get("report_date"), utc_now_iso(), retrieval_method="sec_api", confidence="high", direct_or_proxy="direct"))


def promote_technical_indicators(store: EvidenceStore, bars: list[Any]) -> None:
    if not bars:
        return
    closes = [float(item.close) for item in bars if getattr(item, "close", None) is not None]
    volumes = [getattr(item, "volume", None) for item in bars]
    latest = bars[-1]
    for key, window in (("technical.sma_50", 50), ("technical.sma_200", 200), ("technical.ema_10", 10)):
        if len(closes) >= window:
            value = sum(closes[-window:]) / window
            store.add_item(EvidenceItem(key, round(value, 4), EvidenceStatus.COMPUTED, "yfinance OHLCV", "https://finance.yahoo.com/", SourceLevel.AGGREGATOR_OR_MARKET_DATA, latest.date, utc_now_iso(), limitations=[f"Computed from last {window} daily closes."], retrieval_method="computed_indicator", confidence="medium", direct_or_proxy="direct"))
    if len(closes) >= 15:
        rsi = _rsi(closes[-15:])
        store.add_item(EvidenceItem("technical.rsi_14", round(rsi, 4), EvidenceStatus.COMPUTED, "yfinance OHLCV", "https://finance.yahoo.com/", SourceLevel.AGGREGATOR_OR_MARKET_DATA, latest.date, utc_now_iso(), limitations=["Computed with simple 14-period RSI approximation."], retrieval_method="computed_indicator", confidence="medium", direct_or_proxy="direct"))
    if volumes and any(v is not None for v in volumes[-20:]):
        vol_values = [int(v) for v in volumes[-20:] if v is not None]
        if vol_values:
            store.add_item(EvidenceItem("technical.volume_ma_20", round(sum(vol_values) / len(vol_values), 2), EvidenceStatus.COMPUTED, "yfinance OHLCV", "https://finance.yahoo.com/", SourceLevel.AGGREGATOR_OR_MARKET_DATA, latest.date, utc_now_iso(), retrieval_method="computed_indicator", confidence="medium", direct_or_proxy="direct"))


def _compute_derived_items(store: EvidenceStore) -> None:
    from .equity_evidence import _evidence_invalid_reasons

    ocf_item = store.get("cashflow.latest.ocf")
    capex_item = store.get("cashflow.latest.capex")
    ocf = store.value("cashflow.latest.ocf")
    capex = store.value("cashflow.latest.capex")
    ocf_valid = ocf_item is not None and store.is_usable("cashflow.latest.ocf") and not _evidence_invalid_reasons("cashflow.latest.ocf", ocf_item)
    capex_valid = capex_item is not None and store.is_usable("cashflow.latest.capex") and not _evidence_invalid_reasons("cashflow.latest.capex", capex_item)
    if ocf_valid and capex_valid and isinstance(ocf, (int, float)) and isinstance(capex, (int, float)):
        fcf = float(ocf) - float(capex)
        conversion = fcf / float(ocf) if float(ocf) else None
        store.add_item(EvidenceItem("cashflow.latest.fcf", round(fcf, 4), EvidenceStatus.COMPUTED, "Titan FinancialCalculator", None, SourceLevel.SEC_OR_REGULATORY, store.report_date, utc_now_iso(), limitations=["Computed centrally as same-period OCF minus CapEx."], retrieval_method="computed_financial", confidence="high", direct_or_proxy="direct"))
        store.add_item(EvidenceItem("cashflow.fcf_inputs", {"ocf": ocf, "capex": capex, "fcf": round(fcf, 4)}, EvidenceStatus.RETRIEVED, "Titan FinancialCalculator", None, SourceLevel.SEC_OR_REGULATORY, store.report_date, utc_now_iso(), retrieval_method="computed_financial", confidence="high", direct_or_proxy="direct"))
        store.add_item(EvidenceItem("cashflow.fcf_conversion", round(conversion, 6) if conversion is not None else None, EvidenceStatus.COMPUTED, "Titan FinancialCalculator", None, SourceLevel.SEC_OR_REGULATORY, store.report_date, utc_now_iso(), limitations=["Computed as same-period FCF divided by OCF."], retrieval_method="computed_financial", confidence="high", direct_or_proxy="direct"))
        store.add_item(EvidenceItem("capex.actual.same_period", capex, EvidenceStatus.RETRIEVED, "Titan FinancialCalculator", None, SourceLevel.SEC_OR_REGULATORY, store.report_date, utc_now_iso(), limitations=["Actual CapEx input from same-period cash-flow evidence; distinct from forward CapEx guidance."], retrieval_method="computed_financial", confidence="high", direct_or_proxy="direct"))
    fy1 = store.value("valuation.fy1_eps")
    fy2 = store.value("valuation.fy2_eps")
    price = store.value("market.latest_price", {}) or {}
    close = price.get("close") if isinstance(price, dict) else None
    if close and (fy1 or fy2):
        value = {"price": close}
        if fy1:
            value["fy1_eps"] = fy1
            value["fy1_pe"] = round(float(close) / float(fy1), 4)
        if fy2:
            value["fy2_eps"] = fy2
            value["fy2_pe"] = round(float(close) / float(fy2), 4)
        store.add_item(EvidenceItem("valuation.forward_pe_basis", value, EvidenceStatus.RETRIEVED, "Titan Forward P/E Resolver", None, SourceLevel.AGGREGATOR_OR_MARKET_DATA, store.report_date, utc_now_iso(), retrieval_method="computed_valuation", confidence="medium", direct_or_proxy="direct"))
    consensus_sources = store.value("consensus.analyst.sources", []) or []
    if len(consensus_sources) >= 2:
        store.add_item(EvidenceItem("consensus.analyst", {"sources": consensus_sources}, EvidenceStatus.RETRIEVED, "Titan Analyst Consensus Aggregator", None, SourceLevel.AGGREGATOR_OR_MARKET_DATA, store.report_date, utc_now_iso(), retrieval_method="aggregated_consensus", confidence="medium", direct_or_proxy="direct"))


def _promote_actual_vs_consensus(add, text: str, source: ResolverSource) -> None:
    eps_actual = _extract_after(text, (r"eps(?:\s+of|\s+was)?\s*\$?([0-9]+(?:\.[0-9]+)?)",))
    eps_consensus = _extract_after(text, (r"(?:eps|earnings per share)[^.\n]{0,80}(?:consensus|estimate)[^0-9]{0,20}\$?([0-9]+(?:\.[0-9]+)?)",))
    revenue_actual = _extract_money_near(text, ("revenue",))
    revenue_consensus = _extract_after(text, (r"revenue[^.\n]{0,80}(?:consensus|estimate)[^0-9]{0,20}\$?([0-9]+(?:\.[0-9]+)?)\s*(billion|million|b|m)?",))
    if revenue_consensus is not None and revenue_consensus < 1000:
        revenue_consensus = revenue_consensus * 1_000_000_000
    if eps_actual is not None:
        add("earnings.eps.actual", eps_actual)
    if eps_consensus is not None:
        add("earnings.eps.consensus", eps_consensus)
    if revenue_actual is not None:
        add("earnings.revenue.actual", revenue_actual)
    if revenue_consensus is not None:
        add("earnings.revenue.consensus", revenue_consensus)
    if (eps_actual is not None and eps_consensus is not None) or (revenue_actual is not None and revenue_consensus is not None):
        add("earnings.actual_vs_consensus", {"source_id": source.source_id, "eps_actual": eps_actual, "eps_consensus": eps_consensus, "revenue_actual": revenue_actual, "revenue_consensus": revenue_consensus})


def _promote_cloud_saas_metrics(add, text: str, source: ResolverSource) -> None:
    arr = _extract_money_near(text, ("annual revenue run rate", "arr", "run rate"))
    rpo = _extract_money_near(text, ("remaining performance obligation", "rpo", "backlog"))
    seats = _extract_after(text, (r"([0-9]+(?:\.[0-9]+)?)\s*(million|billion|m|b)?\s+(?:paid\s+)?(?:seats|users|subscribers|customers)",))
    azure = _extract_after(text, (r"azure[^0-9]{0,40}([0-9]+(?:\.[0-9]+)?)\s*%",))
    if arr is not None:
        add("business.arr_or_revenue_run_rate", arr)
    if rpo is not None:
        add("business.rpo_or_backlog", rpo)
    if seats is not None:
        add("business.paid_seats_or_users", seats)
    if azure is not None:
        add("earnings.key_segment.actual", azure)


def _promote_cashflow(add, text: str, source: ResolverSource) -> None:
    ocf = _extract_money_near(text, ("operating cash flow", "net cash from operations", "net cash provided by operations"))
    capex = _extract_money_near(text, ("additions to property and equipment", "capital expenditures", "capex"))
    if ocf is not None:
        add("cashflow.latest.ocf", ocf)
    if capex is not None:
        add("cashflow.latest.capex", capex)


def _promote_consensus(store: EvidenceStore, add, text: str, source: ResolverSource) -> None:
    if not _has(text, "price target", "buy", "hold", "sell"):
        return
    buy = _extract_after(text, (r"([0-9]+)\s+buy",))
    hold = _extract_after(text, (r"([0-9]+)\s+hold",))
    sell = _extract_after(text, (r"([0-9]+)\s+sell",))
    avg_pt = _extract_after(text, (r"(?:average|avg)[^.\n]{0,30}(?:price target|pt)[^0-9]{0,20}\$?([0-9]+(?:\.[0-9]+)?)",))
    current = list(store.value("consensus.analyst.sources", []) or [])
    if source.publisher not in current:
        current.append(source.publisher)
    add("consensus.analyst.sources", current)
    if buy is not None:
        add("consensus.analyst.buy", int(buy))
    if hold is not None:
        add("consensus.analyst.hold", int(hold))
    if sell is not None:
        add("consensus.analyst.sell", int(sell))
    if avg_pt is not None:
        add("consensus.analyst.avg_pt", avg_pt)


def _promote_short_interest(add, text: str, source: ResolverSource) -> None:
    if not _has(text, "short interest", "days to cover", "percent of float", "% of float"):
        return
    fields = _extract_short_interest_fields(text)
    shares = fields.get("shares_short")
    pct = fields.get("percent_float")
    days = fields.get("days_to_cover")
    if shares is not None:
        add("short_interest.shares_short", shares)
    if pct is not None:
        add("short_interest.percent_float", pct)
    if days is not None:
        add("short_interest.days_to_cover", days)
    add("positioning.short_interest", {"source_id": source.source_id, "shares_short": shares, "percent_float": pct, "days_to_cover": days})


def _promote_options(add, text: str, source: ResolverSource) -> None:
    if not _has(text, "put/call", "put call", "put-call"):
        return
    ratio = _extract_after(text, (r"(?:put/call|put call|put-call)[^0-9]{0,40}([0-9]+(?:\.[0-9]+)?)",))
    add("options.put_call", {"ratio": ratio, "source_id": source.source_id}, EvidenceStatus.RETRIEVED if ratio is not None else EvidenceStatus.PARTIAL)


def _promote_earnings_date(add, text: str, source: ResolverSource) -> None:
    if not _has(text, "next earnings", "earnings date", "reports earnings"):
        return
    date_value = _next_earnings_date_near_label(text, source.as_of_date)
    add("catalyst.next_earnings_date.sources", [source.publisher])
    add("catalyst.next_earnings_date", {"date": date_value, "source_id": source.source_id}, EvidenceStatus.RETRIEVED if date_value else EvidenceStatus.PARTIAL)
    if date_value:
        add("catalyst.next_earnings_date.value", date_value)


def _promote_ownership(add, text: str, source: ResolverSource) -> None:
    source_hint = f"{source.source_type} {source.title} {source.publisher} {source.url or ''}".lower()
    if any(token in source_hint for token in ("short_interest", "short-interest", "options", "put-call")):
        return
    if _has(text, "form 4", "insider transaction", "insider activity"):
        add("ownership.form4_90d", _summary(source), EvidenceStatus.PARTIAL if source.direct_or_proxy == "proxy" else EvidenceStatus.RETRIEVED)
    if _has(text, "13f", "institutional ownership"):
        add("ownership.13f_latest", _summary(source), EvidenceStatus.PARTIAL if source.direct_or_proxy == "proxy" else EvidenceStatus.RETRIEVED)


def _candidate_public_urls(ticker: str) -> list[tuple[str, str]]:
    symbol = ticker.upper()
    lower = ticker.lower()
    return [
        (f"https://stockanalysis.com/stocks/{lower}/", "market_snapshot"),
        (f"https://stockanalysis.com/stocks/{lower}/financials/cash-flow-statement/", "cashflow"),
        (f"https://stockanalysis.com/stocks/{lower}/forecast/", "analyst_consensus"),
        (f"https://www.marketbeat.com/stocks/NASDAQ/{symbol}/earnings/", "actual_vs_consensus"),
        (f"https://www.marketbeat.com/stocks/NASDAQ/{symbol}/forecast/", "analyst_consensus"),
        (f"https://www.marketbeat.com/stocks/NASDAQ/{symbol}/short-interest/", "short_interest"),
        (f"https://www.nasdaq.com/market-activity/stocks/{lower}/short-interest", "short_interest"),
        (f"https://finance.yahoo.com/quote/{symbol}/insider-transactions/", "ownership_proxy"),
        (f"https://www.barchart.com/stocks/quotes/{symbol}/put-call-ratios", "options_proxy"),
        (f"https://fintel.io/sopt/us/{lower}", "options_proxy"),
    ]


def _is_earnings_release_source(source: ResolverSource, text: str) -> bool:
    source_hint = f"{source.source_type} {source.title} {source.url or ''}".lower()
    if any(blocked in source_hint for blocked in ("short_interest", "short-interest", "options", "put-call", "ownership", "insider")):
        return False
    has_release_words = _has(text, "earnings release", "quarterly results", "results release")
    source_path_supports_release = any(word in source_hint for word in ("earnings", "results", "investor", "8-k", "10-q", "10-k"))
    return source.direct_or_proxy == "direct" and has_release_words and source_path_supports_release


def _source_allows_fundamental_claims(source: ResolverSource) -> bool:
    source_hint = f"{source.source_type} {source.title} {source.publisher} {source.url or ''}".lower()
    blocked = ("short_interest", "short-interest", "options", "put-call", "ownership", "insider", "forecast", "price-target")
    if any(token in source_hint for token in blocked):
        return False
    return source.direct_or_proxy == "direct" and (
        source.source_level >= SourceLevel.MAJOR_WIRE_OR_REPUTABLE_NEWS
        or any(token in source_hint for token in ("earnings", "results", "transcript", "investor", "10-q", "10-k", "8-k", "sec"))
    )


def _source_allows_guidance_claims(source: ResolverSource) -> bool:
    source_hint = f"{source.source_type} {source.title} {source.publisher} {source.url or ''}".lower()
    blocked = ("short_interest", "short-interest", "options", "put-call", "ownership", "insider", "cash-flow-statement", "financials/cash-flow")
    if any(token in source_hint for token in blocked):
        return False
    return source.direct_or_proxy == "direct" and (
        source.source_level >= SourceLevel.MAJOR_WIRE_OR_REPUTABLE_NEWS
        or any(token in source_hint for token in ("guidance", "outlook", "transcript", "earnings", "results", "investor", "10-q", "10-k", "8-k"))
    ) and source.source_level != SourceLevel.AGGREGATOR_OR_MARKET_DATA


def _source_looks_like_transcript(source: ResolverSource) -> bool:
    source_hint = f"{source.source_type} {source.title} {source.publisher} {source.url or ''}".lower()
    if any(token in source_hint for token in ("short_interest", "short-interest", "options", "put-call", "ownership", "insider")):
        return False
    return source.direct_or_proxy == "direct" and (
        "transcript" in source_hint
        or "earnings-call" in source_hint
        or "earnings_call" in source_hint
        or source.source_level == SourceLevel.COMPANY_IR_OR_TRANSCRIPT
    )


def _next_earnings_date_near_label(text: str, as_of_date: str | None) -> str | None:
    report_dt = _parse_date(as_of_date)
    label_pattern = re.compile(r"(next earnings|earnings date|reports earnings)", re.I)
    date_pattern = re.compile(
        r"(20\d{2}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}/\d{1,2}/\d{2,4}|(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{1,2},?\s+20\d{2})",
        re.I,
    )
    candidates: list[tuple[datetime, str]] = []
    for label in label_pattern.finditer(text):
        window = text[max(0, label.start() - 120) : label.end() + 220]
        for match in date_pattern.finditer(window):
            normalized = _normalize_date(match.group(1))
            parsed = _parse_date(normalized)
            if not normalized or not parsed:
                continue
            if report_dt and parsed.date() <= report_dt.date():
                continue
            candidates.append((parsed, normalized))
    if not candidates:
        return None
    return sorted(candidates, key=lambda item: item[0])[0][1]


def _normalize_date(value: str) -> str | None:
    text = value.strip().replace("/", "-")
    for fmt in ("%Y-%m-%d", "%m-%d-%Y", "%m-%d-%y", "%B %d, %Y", "%b %d, %Y", "%B %d %Y", "%b %d %Y"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _fetch_text(url: str) -> str:
    request = Request(url, headers={"User-Agent": "TitanIntegration/0.1 evidence-resolver"})
    try:
        with urlopen(request, timeout=5) as response:
            data = response.read(1_000_000).decode("utf-8", errors="ignore")
    except (URLError, TimeoutError, OSError):
        return ""
    return re.sub(r"<[^>]+>", " ", data)


def _source_from_dict(item: dict[str, Any]) -> ResolverSource:
    return ResolverSource(
        source_id=str(item.get("source_id") or item.get("id") or "fixture_source"),
        title=str(item.get("title") or item.get("source_type") or "Fixture source"),
        publisher=str(item.get("publisher") or item.get("source_name") or "Fixture"),
        url=item.get("url"),
        text=str(item.get("text") or item.get("evidence_summary") or ""),
        source_type=str(item.get("source_type") or "fixture"),
        retrieval_method=str(item.get("retrieval_method") or "fixture"),
        as_of_date=item.get("as_of_date") or item.get("published_date"),
        confidence=str(item.get("confidence") or "high"),
        direct_or_proxy=str(item.get("direct_or_proxy") or "direct"),
        source_level=SourceLevel(item.get("source_level", SourceLevel.AGGREGATOR_OR_MARKET_DATA.value)),
        limitations=list(item.get("limitations", []) or []),
    )


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").lower()


def _has(text: str, *needles: str) -> bool:
    return any(needle in text for needle in needles)


def _summary(source: ResolverSource) -> dict[str, Any]:
    return {"source_id": source.source_id, "title": source.title, "publisher": source.publisher, "url": source.url}


def _extract_after(text: str, patterns: tuple[str, ...]) -> float | None:
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if not match:
            continue
        value = float(match.group(1))
        unit = match.group(2).lower() if len(match.groups()) > 1 and match.group(2) else ""
        if unit in {"billion", "b"}:
            return value * 1_000_000_000
        if unit in {"million", "m"}:
            return value * 1_000_000
        return value
    return None


def _extract_money_near(text: str, needles: tuple[str, ...]) -> float | None:
    if any(needle in needles for needle in ("remaining performance obligation", "rpo", "backlog")):
        specific = re.search(
            r"(?:remaining\s+performance\s+obligations?|rpo|backlog)[^.\n]{0,140}?(?:to|was|were|of|at)?\s*\$?\s*([0-9][0-9,]*(?:\.[0-9]+)?)\s*(billion|million|b|m)",
            text,
            re.I,
        )
        if specific:
            return _scale_number(float(specific.group(1).replace(",", "")), specific.group(2))
        reverse = re.search(
            r"\$?\s*([0-9][0-9,]*(?:\.[0-9]+)?)\s*(billion|million|b|m)[^.\n]{0,120}?(?:remaining\s+performance\s+obligations?|rpo|backlog)",
            text,
            re.I,
        )
        if reverse:
            return _scale_number(float(reverse.group(1).replace(",", "")), reverse.group(2))
    for needle in needles:
        idx = text.find(needle)
        if idx < 0:
            continue
        window = text[idx : idx + 180]
        match = re.search(r"\$?\s*([0-9]+(?:\.[0-9]+)?)\s*(billion|million|b|m)?", window, re.I)
        if not match:
            continue
        value = float(match.group(1))
        unit = (match.group(2) or "").lower()
        if unit in {"billion", "b"}:
            return value * 1_000_000_000
        if unit in {"million", "m"}:
            return value * 1_000_000
        return value
    return None


def _scale_number(value: float, unit: str | None) -> float:
    unit = (unit or "").lower()
    if unit in {"billion", "b"}:
        return value * 1_000_000_000
    if unit in {"million", "m"}:
        return value * 1_000_000
    return value


def _extract_guidance(text: str) -> dict[str, Any] | None:
    revenue = _extract_money_near(text, ("revenue guidance", "q4 revenue", "revenue outlook"))
    azure = _extract_after(text, (r"azure[^.\n]{0,80}(?:guidance|outlook|expected)[^0-9]{0,20}([0-9]+(?:\.[0-9]+)?)\s*%",))
    if revenue is None and azure is None:
        return None
    return {"revenue": revenue, "key_segment_growth_pct": azure}


def _extract_short_interest_fields(text: str) -> dict[str, float]:
    fields: dict[str, float] = {}
    shares = _extract_number_with_optional_unit(
        text,
        (
            r"([0-9][0-9,]*(?:\.[0-9]+)?)\s*(million|billion|m|b)?\s+shares?\s+short",
            r"short\s+interest[^.\n]{0,80}?([0-9][0-9,]*(?:\.[0-9]+)?)\s*(million|billion|m|b)?\s+shares?",
            r"shares?\s+short[^.\n]{0,80}?([0-9][0-9,]*(?:\.[0-9]+)?)\s*(million|billion|m|b)?",
        ),
    )
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


def _extract_number_with_optional_unit(text: str, patterns: tuple[str, ...]) -> float | None:
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if not match:
            continue
        value = float(match.group(1).replace(",", ""))
        unit = match.group(2).lower() if len(match.groups()) > 1 and match.group(2) else ""
        if unit in {"billion", "b"}:
            return value * 1_000_000_000
        if unit in {"million", "m"}:
            return value * 1_000_000
        return value
    return None


def _indicates_capex_guidance(text: str) -> bool:
    return _has(
        text,
        "capex",
        "capital expenditure",
        "capital expenditures",
        "capital spending",
        "ai infrastructure",
        "data center investment",
    ) and _has(
        text,
        "guidance",
        "outlook",
        "expect",
        "expects",
        "will increase",
        "will decline",
        "remain elevated",
        "fiscal",
        "calendar year",
    )


def _within_days(anchor: str | None, candidate: str | None, days: int) -> bool:
    anchor_dt = _parse_date(anchor)
    candidate_dt = _parse_date(candidate)
    if not anchor_dt or not candidate_dt:
        return False
    delta = (anchor_dt.date() - candidate_dt.date()).days
    return 0 <= delta <= days


def _publisher_from_url(url: str) -> str:
    host = re.sub(r"^https?://(?:www\.)?", "", url).split("/", 1)[0]
    return host


def _direct_or_proxy_for_source(url: str, source_type: str) -> str:
    text = f"{url} {source_type}".lower()
    if "sec.gov" in text or "investor" in text or "transcript" in text or "earnings" in text:
        return "direct"
    if "ownership" in text or "options" in text:
        return "proxy"
    return "direct"


def _source_level_for_url(url: str, source_type: str) -> SourceLevel:
    text = f"{url} {source_type}".lower()
    if "sec.gov" in text:
        return SourceLevel.SEC_OR_REGULATORY
    if "investor" in text or "transcript" in text:
        return SourceLevel.COMPANY_IR_OR_TRANSCRIPT
    if "reuters" in text:
        return SourceLevel.MAJOR_WIRE_OR_REPUTABLE_NEWS
    return SourceLevel.AGGREGATOR_OR_MARKET_DATA


def _latest_form(filings: list[dict[str, Any]], accepted: set[str]) -> dict[str, Any] | None:
    matches = [item for item in filings if str(item.get("form", "")).upper() in accepted]
    return sorted(matches, key=lambda item: item.get("filing_date") or "")[-1] if matches else None


def _rsi(closes: list[float]) -> float:
    gains = []
    losses = []
    for prev, curr in zip(closes, closes[1:]):
        delta = curr - prev
        gains.append(max(delta, 0.0))
        losses.append(abs(min(delta, 0.0)))
    avg_gain = sum(gains) / len(gains) if gains else 0.0
    avg_loss = sum(losses) / len(losses) if losses else 0.0
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))
