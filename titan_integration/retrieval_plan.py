"""Institutional evidence retrieval plans.

Retrieval plans define what the system must try to find before an external
fact can be treated as missing. They are intentionally ticker-agnostic and
asset-class aware, so the same rules apply across future research runs.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class EvidenceRetrievalTask:
    evidence_id: str
    label: str
    asset_classes: list[str]
    primary_source_classes: list[str]
    secondary_source_classes: list[str]
    fallback_source_classes: list[str]
    required_before_final_claims: list[str]
    blocking_when_missing: bool
    search_terms: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


EQUITY_RETRIEVAL_PLAN: list[EvidenceRetrievalTask] = [
    EvidenceRetrievalTask(
        evidence_id="latest_company_guidance",
        label="Latest company guidance and filing-backed outlook",
        asset_classes=["Equity", "Equity-Option"],
        primary_source_classes=[
            "SEC EDGAR 8-K/10-Q/10-K exhibits",
            "issuer investor-relations earnings release",
            "issuer investor-relations presentation",
            "issuer earnings-call transcript",
        ],
        secondary_source_classes=[
            "reputable transcript provider",
            "reputable financial-data aggregator with source date",
        ],
        fallback_source_classes=["reputable financial news summarizing issuer guidance"],
        required_before_final_claims=[
            "forward revenue",
            "gross margin",
            "EPS guidance",
            "valuation synthesis",
            "fundamental rating",
        ],
        blocking_when_missing=True,
        search_terms=[
            "{ticker} investor relations latest earnings release guidance",
            "{ticker} SEC 8-K earnings release outlook",
            "{ticker} latest earnings call transcript guidance",
        ],
    ),
    EvidenceRetrievalTask(
        evidence_id="price_volume_context",
        label="Price, volume, and liquidity context",
        asset_classes=["Equity", "ETF", "Index", "Equity-Option", "ETF-Option", "Index-Option"],
        primary_source_classes=["exchange market data", "provider OHLCV bars"],
        secondary_source_classes=["Yahoo/yfinance", "Stooq", "reputable market-data aggregator"],
        fallback_source_classes=["broker/platform export supplied by user"],
        required_before_final_claims=[
            "trend",
            "support/resistance",
            "volume confirmation",
            "entry/exit levels",
        ],
        blocking_when_missing=True,
        search_terms=[
            "{ticker} historical price volume",
            "{ticker} OHLCV latest close volume",
        ],
    ),
    EvidenceRetrievalTask(
        evidence_id="valuation_basis",
        label="Valuation basis and estimate inputs",
        asset_classes=["Equity", "Equity-Option"],
        primary_source_classes=[
            "issuer guidance",
            "SEC filings",
            "consensus estimate provider with source date",
        ],
        secondary_source_classes=[
            "StockAnalysis",
            "MarketBeat",
            "Yahoo Finance analysis/earnings pages",
            "TIKR-style aggregator where available",
        ],
        fallback_source_classes=["reputable financial media citing consensus estimates"],
        required_before_final_claims=[
            "forward P/E",
            "PEG",
            "EV/EBITDA",
            "upside/downside to price target",
        ],
        blocking_when_missing=True,
        search_terms=[
            "{ticker} forward PE consensus EPS",
            "{ticker} analyst price target consensus",
            "{ticker} estimates FY1 FY2 EPS revenue",
        ],
    ),
    EvidenceRetrievalTask(
        evidence_id="catalyst_calendar",
        label="Catalyst calendar and event timing",
        asset_classes=["Equity", "ETF", "Index", "Equity-Option", "ETF-Option", "Index-Option"],
        primary_source_classes=["issuer IR calendar", "SEC filing", "exchange calendar"],
        secondary_source_classes=["earnings-date provider", "reputable financial-data calendar"],
        fallback_source_classes=["reputable financial news with publication date"],
        required_before_final_claims=[
            "earnings date",
            "event-risk window",
            "holding period",
            "horizon classification",
        ],
        blocking_when_missing=False,
        search_terms=[
            "{ticker} next earnings date investor relations",
            "{ticker} earnings calendar source date",
            "{ticker} upcoming catalysts",
        ],
    ),
    EvidenceRetrievalTask(
        evidence_id="sentiment_positioning",
        label="Sentiment, analyst consensus, and positioning",
        asset_classes=["Equity", "ETF", "Index", "Equity-Option", "ETF-Option", "Index-Option"],
        primary_source_classes=["FINRA short interest", "exchange short interest", "issuer filings"],
        secondary_source_classes=[
            "analyst consensus aggregator with source date",
            "options data provider",
            "put-call/open-interest provider",
        ],
        fallback_source_classes=["reputable financial news citing analyst or positioning data"],
        required_before_final_claims=[
            "crowded-long",
            "short squeeze",
            "professional bearish conviction",
            "analyst consensus",
        ],
        blocking_when_missing=True,
        search_terms=[
            "{ticker} short interest days to cover FINRA",
            "{ticker} analyst consensus price target source date",
            "{ticker} options open interest put call ratio",
        ],
    ),
    EvidenceRetrievalTask(
        evidence_id="macro_news_context",
        label="Macro, policy, industry, and news context",
        asset_classes=["Equity", "ETF", "Index", "Crypto", "FX", "Futures", "Commodity", "CFD"],
        primary_source_classes=["official agency", "central bank", "company primary statement"],
        secondary_source_classes=["reputable financial media", "reputable industry press"],
        fallback_source_classes=["source-dated aggregator article linking back to primary reporting"],
        required_before_final_claims=[
            "macro regime",
            "policy catalyst",
            "supply/demand claim",
            "industry cycle claim",
        ],
        blocking_when_missing=False,
        search_terms=[
            "{ticker} macro policy catalyst source dated",
            "{ticker} industry supply demand latest source",
        ],
    ),
]


def retrieval_plan_for(asset_class: str) -> list[EvidenceRetrievalTask]:
    normalized = asset_class.strip().lower()
    return [
        task
        for task in EQUITY_RETRIEVAL_PLAN
        if any(item.lower() == normalized for item in task.asset_classes)
    ]


def default_retrieval_plan_payload(asset_class: str) -> dict[str, Any]:
    tasks = retrieval_plan_for(asset_class)
    return {
        "asset_class": asset_class,
        "policy": (
            "A missing evidence outcome is valid only after the listed primary, secondary, "
            "and fallback source classes have been attempted and documented."
        ),
        "tasks": [task.to_dict() for task in tasks],
    }
