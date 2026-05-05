"""Stage 2 citation retrieval and evidence linking.

Stage 2 consumes a Stage 1 validation packet plus a curated citation manifest.
It upgrades or preserves Stage 1 claim statuses based on external source
evidence. This is still not a final Titan report; it is an evidence-linking
layer that prepares claims for later Graphify and horizon validation.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from .evidence_ledger import EvidenceLedger
from .research_cycle import inherit_research_cycle, utc_now_iso


@dataclass(frozen=True)
class CitationSource:
    source_id: str
    title: str
    publisher: str
    url: str
    published_date: str | None
    retrieved_at_utc: str
    reliability_tier: str
    source_type: str
    evidence_summary: str
    supported_claims: list[str]
    limitations: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class LinkedClaim:
    claim: str
    stage1_status: str
    stage2_status: str
    evidence_class: str
    rationale: str
    source_ids: list[str] = field(default_factory=list)
    unresolved_requirements: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Stage2Packet:
    ticker: str
    trade_date: str
    generated_at_utc: str
    research_cycle: dict[str, Any]
    stage: str
    compliance_status: str
    upstream_stage1_status: str
    citation_manifest_path: str
    linked_claims: list[LinkedClaim]
    citation_sources: list[CitationSource]
    source_reliability_table: list[dict[str, Any]]
    remaining_evidence_gaps: list[str]
    graphify_readiness: dict[str, Any]
    next_required_evidence: list[str]


def build_stage2_packet(*, stage1_packet_path: Path, manifest_path: Path) -> Stage2Packet:
    stage1 = json.loads(stage1_packet_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    sources = [CitationSource(**item) for item in manifest["sources"]]
    sources.extend(_stage1_sources(stage1))
    sources_by_id = {source.source_id: source for source in sources}
    ledger = EvidenceLedger.from_citation_sources(
        research_date=stage1["trade_date"],
        sources=sources,
        asset=stage1["ticker"],
    )

    linked_claims: list[LinkedClaim] = []
    stage1_claims = stage1.get("claim_evidence_map", [])
    for claim in stage1_claims:
        linked_claims.append(_link_claim(claim, manifest, sources_by_id, ledger))

    generated_at_utc = utc_now_iso()
    return Stage2Packet(
        ticker=stage1["ticker"],
        trade_date=stage1["trade_date"],
        generated_at_utc=generated_at_utc,
        research_cycle=inherit_research_cycle(
            stage1,
            fallback_ticker=stage1["ticker"],
            fallback_trade_date=stage1["trade_date"],
            fallback_generated_at_utc=generated_at_utc,
        ),
        stage="Titan Validation Packet Stage 2 - Citation Evidence Linking",
        compliance_status="Not Titan-Compliant",
        upstream_stage1_status=stage1.get("preliminary_validation_status", {}).get(
            "overall", "Unknown"
        ),
        citation_manifest_path=str(manifest_path),
        linked_claims=linked_claims,
        citation_sources=sources,
        source_reliability_table=_source_reliability_table(sources),
        remaining_evidence_gaps=_remaining_gaps(linked_claims),
        graphify_readiness={
            "ready_for_graphify": True,
            "recommended_input": "Stage 1 packet + Stage 2 packet + citation manifest",
            "edge_policy": (
                "Use EXTRACTED for claim-source links, INFERRED only for cross-source "
                "relationships, and AMBIGUOUS for unresolved or partial support."
            ),
        },
        next_required_evidence=_next_required_evidence(),
    )


def write_stage2_packet(packet: Stage2Packet, out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{packet.ticker}_{packet.trade_date}_stage2_citation_packet"
    json_path = out_dir / f"{stem}.json"
    md_path = out_dir / f"{stem}.md"

    payload = asdict(packet)
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(_to_markdown(payload), encoding="utf-8")
    return json_path, md_path


def _link_claim(
    claim: dict[str, Any],
    manifest: dict[str, Any],
    sources_by_id: dict[str, CitationSource],
    ledger: EvidenceLedger,
) -> LinkedClaim:
    claim_text = claim["claim"]
    rule = _match_rule(claim_text, manifest.get("claim_links", []))
    if not rule:
        source_ids = _stage1_source_ids(claim.get("source_refs", []))
        validation = ledger.validate_claim(
            claim=claim_text,
            source_ids=source_ids,
            requested_status=claim["status"],
            evidence_class="stage1_provider_evidence",
            rationale=(
                "No Stage 2 external citation rule was required; this claim is carried "
                "forward from Stage 1 provider-backed validation."
            )
            if source_ids
            else "No Stage 2 citation rule matched this claim.",
            unresolved_requirements=[],
        )
        return LinkedClaim(
            claim=claim_text,
            stage1_status=claim["status"],
            stage2_status=validation.status,
            evidence_class=validation.evidence_class,
            rationale=validation.rationale,
            source_ids=validation.source_ids,
            unresolved_requirements=validation.unresolved_requirements,
        )

    source_ids = rule.get("source_ids", [])
    validation = ledger.validate_claim(
        claim=claim_text,
        source_ids=source_ids,
        requested_status=rule["stage2_status"],
        evidence_class=rule["evidence_class"],
        rationale=rule["rationale"],
        unresolved_requirements=rule.get("unresolved_requirements", []),
    )

    return LinkedClaim(
        claim=claim_text,
        stage1_status=claim["status"],
        stage2_status=validation.status,
        evidence_class=validation.evidence_class,
        rationale=validation.rationale,
        source_ids=validation.source_ids,
        unresolved_requirements=validation.unresolved_requirements,
    )


def _match_rule(claim_text: str, rules: list[dict[str, Any]]) -> dict[str, Any] | None:
    normalized = claim_text.lower()
    for rule in rules:
        patterns = [item.lower() for item in rule.get("match_contains", [])]
        if any(pattern in normalized for pattern in patterns):
            return rule
    return None


def _source_is_future_dated(source: CitationSource, trade_date: str) -> bool:
    published = _parse_date(source.published_date)
    as_of = _parse_date(trade_date)
    if not published or not as_of:
        return False
    return published > as_of


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _source_reliability_table(sources: list[CitationSource]) -> list[dict[str, Any]]:
    return [
        {
            "source_id": source.source_id,
            "publisher": source.publisher,
            "source_type": source.source_type,
            "reliability_tier": source.reliability_tier,
            "published_date": source.published_date,
            "url": source.url,
        }
        for source in sources
    ]


def _stage1_sources(stage1: dict[str, Any]) -> list[CitationSource]:
    now = utc_now_iso()
    sources: list[CitationSource] = [
        CitationSource(
            source_id="stage1_tradingagents_summary",
            title="Clean TradingAgents DeepSeek Baseline Summary",
            publisher="Local TradingAgents Integration",
            url=stage1.get("run_metadata", {}).get("input_summary_path", "local"),
            published_date=stage1.get("trade_date"),
            retrieved_at_utc=stage1.get("generated_at_utc", now),
            reliability_tier="internal_generated",
            source_type="agent_output",
            evidence_summary="Stage 1 input summary containing the processed TradingAgents stance and generated analyst outputs.",
            supported_claims=["TradingAgents final stance"],
            limitations=["Agent-generated output; not a source of market facts without validation."],
        )
    ]

    price_source = stage1.get("price_data_audit", {}).get("source")
    if price_source:
        sources.append(
            CitationSource(
                source_id="stage1_yfinance",
                title="Stage 1 normalized yfinance price evidence",
                publisher="Yahoo Finance via yfinance",
                url=price_source.get("source_url", "https://finance.yahoo.com/"),
                published_date=None,
                retrieved_at_utc=price_source.get("retrieved_at_utc", now),
                reliability_tier="prototype_market_data",
                source_type="price_data",
                evidence_summary="Stage 1 normalized OHLCV and computed technical evidence.",
                supported_claims=[
                    "TradingAgents reference price is aligned with normalized market data",
                    "reference close",
                    "volume",
                    "moving averages",
                ],
                limitations=["Unofficial Yahoo Finance access; not sole institutional source."],
            )
        )

    sec_source = stage1.get("sec_fundamentals_audit", {}).get("source")
    if sec_source:
        sources.append(
            CitationSource(
                source_id="stage1_sec_edgar",
                title="Stage 1 SEC EDGAR companyfacts and filings evidence",
                publisher="SEC EDGAR",
                url=sec_source.get("source_url", "https://data.sec.gov/"),
                published_date=None,
                retrieved_at_utc=sec_source.get("retrieved_at_utc", now),
                reliability_tier="official_regulatory",
                source_type="fundamentals_filings",
                evidence_summary="Stage 1 SEC CIK, companyfacts, and recent filings evidence.",
                supported_claims=["core financial statement facts", "recent filings"],
                limitations=["SEC concept mapping still requires Titan normalization."],
            )
        )
    user_audit = stage1.get("user_supplied_evidence_audit", {})
    if user_audit and user_audit.get("summary", {}).get("file_count", 0) > 0:
        sources.append(
            CitationSource(
                source_id="stage1_user_supplied_evidence",
                title="Stage 1A user-supplied evidence packet",
                publisher="Local user input folder",
                url="local://inputs",
                published_date=stage1.get("trade_date"),
                retrieved_at_utc=user_audit.get("generated_at_utc", now),
                reliability_tier="user_supplied",
                source_type="supplemental_market_data",
                evidence_summary=(
                    f"Stage 1A detected {user_audit.get('summary', {}).get('file_count', 0)} "
                    "local user-supplied file(s) and summarized timestamp ranges, "
                    "timeframes, hashes, and selected analysis windows."
                ),
                supported_claims=["user-supplied multi-timeframe evidence"],
                limitations=[
                    "User-supplied evidence supplements external provider data and must not silently override provider evidence.",
                    "Conflicts require explicit Titan review.",
                ],
            )
        )
    feature_audit = stage1.get("user_technical_feature_audit", {})
    if feature_audit and feature_audit.get("feature_summaries"):
        sources.append(
            CitationSource(
                source_id="stage1b_user_technical_features",
                title="Stage 1B user-derived technical feature packet",
                publisher="Local user input folder",
                url="local://inputs",
                published_date=stage1.get("trade_date"),
                retrieved_at_utc=feature_audit.get("generated_at_utc", now),
                reliability_tier="user_derived",
                source_type="derived_technical_features",
                evidence_summary=(
                    "Stage 1B extracted VWAP, volume regime, RSI, ATR, ADX, moving-average, "
                    "band-position, and divergence features from user-supplied CSV files."
                ),
                supported_claims=[
                    "user-derived multi-timeframe technical features",
                    "user-derived VWAP positioning",
                    "user-derived momentum and trend-strength features",
                ],
                limitations=[
                    "Derived from user-supplied local exports; supplemental only.",
                    "Does not replace live tape, spread/depth, or opening-range evidence for intraday validation.",
                    "Conflicts with external provider data require explicit Titan review.",
                ],
            )
        )
    return sources


def _stage1_source_ids(source_refs: list[str]) -> list[str]:
    source_ids: list[str] = []
    joined = " ".join(source_refs).lower()
    if "tradingagents" in joined:
        source_ids.append("stage1_tradingagents_summary")
    if "yfinance" in joined:
        source_ids.append("stage1_yfinance")
    if "sec" in joined or "edgar" in joined:
        source_ids.append("stage1_sec_edgar")
    if "user_supplied" in joined or "user-supplied" in joined:
        source_ids.append("stage1_user_supplied_evidence")
    if "user_technical" in joined or "technical_features" in joined:
        source_ids.append("stage1b_user_technical_features")
    return source_ids


def _remaining_gaps(linked_claims: list[LinkedClaim]) -> list[str]:
    gaps = [
        "Titan Primary Corpus evidence gates have not yet been applied.",
        "Validated Trading Horizon classification has not yet been performed.",
        "Graphify evidence graph has not yet been generated.",
        "Final source-integrity self-audit has not yet been run.",
    ]
    for claim in linked_claims:
        for requirement in claim.unresolved_requirements:
            if requirement not in gaps:
                gaps.append(requirement)
    return gaps


def _next_required_evidence() -> list[str]:
    return [
        "Run Graphify over Stage 1 packet, Stage 2 packet, and citation manifest.",
        "Add source retrieval automation for future tickers instead of curated manifests only.",
        "Add estimates-provider support before validating forward P/E, PEG, and NTM growth claims.",
        "Apply Titan horizon rules independently after cited evidence is available.",
        "Run self-audit before any institutional PDF report is generated.",
    ]


def _to_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# Titan Validation Packet Stage 2: {payload['ticker']} {payload['trade_date']}",
        "",
        f"Generated UTC: {payload['generated_at_utc']}",
        f"Research Run ID: {payload.get('research_cycle', {}).get('research_run_id')}",
        f"Market Data As Of: {payload.get('research_cycle', {}).get('market_data_as_of')}",
        f"Compliance Status: {payload['compliance_status']}",
        f"Upstream Stage 1 Status: {payload['upstream_stage1_status']}",
        "",
        "## Linked Claims",
        "",
        "| Stage 2 | Stage 1 | Evidence Class | Claim | Sources |",
        "|---|---|---|---|---|",
    ]
    for claim in payload["linked_claims"]:
        lines.append(
            "| {stage2_status} | {stage1_status} | {evidence_class} | {claim} | {sources} |".format(
                stage2_status=claim["stage2_status"],
                stage1_status=claim["stage1_status"],
                evidence_class=claim["evidence_class"],
                claim=claim["claim"],
                sources=", ".join(claim["source_ids"]) or "None",
            )
        )

    lines.extend(["", "## Claim Rationales", ""])
    for claim in payload["linked_claims"]:
        lines.extend(
            [
                f"### {claim['stage2_status']}: {claim['claim']}",
                "",
                f"Rationale: {claim['rationale']}",
                "",
                f"Unresolved: {', '.join(claim['unresolved_requirements']) or 'None'}",
                "",
            ]
        )

    lines.extend(
        [
            "## Citation Sources",
            "",
            "| Source ID | Publisher | Tier | Type | Date | URL |",
            "|---|---|---|---|---|---|",
        ]
    )
    for source in payload["citation_sources"]:
        lines.append(
            f"| {source['source_id']} | {source['publisher']} | {source['reliability_tier']} | "
            f"{source['source_type']} | {source['published_date']} | {source['url']} |"
        )

    lines.extend(["", "## Source Summaries", ""])
    for source in payload["citation_sources"]:
        lines.extend(
            [
                f"### {source['source_id']}: {source['title']}",
                "",
                source["evidence_summary"],
                "",
                f"Limitations: {', '.join(source['limitations']) or 'None'}",
                "",
            ]
        )

    lines.extend(["## Remaining Evidence Gaps", ""])
    lines.extend(f"- {gap}" for gap in payload["remaining_evidence_gaps"])
    lines.extend(["", "## Graphify Readiness", "", _code_json(payload["graphify_readiness"])])
    lines.extend(["", "## Next Required Evidence", ""])
    lines.extend(f"- {item}" for item in payload["next_required_evidence"])
    return "\n".join(lines) + "\n"


def _code_json(value: Any) -> str:
    return "```json\n" + json.dumps(value, indent=2, ensure_ascii=False) + "\n```"
