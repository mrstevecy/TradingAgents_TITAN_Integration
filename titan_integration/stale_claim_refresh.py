"""Refresh stale graph claims using prior source evidence.

This layer consumes an evidence delta packet and a prior evidence graph. When a
previously supported claim is absent from the fresh graph, the layer attempts to
re-attach and timestamp the prior source evidence instead of leaving the item as
an ambiguous stale gap.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .research_cycle import inherit_research_cycle, utc_now_iso


@dataclass(frozen=True)
class RefreshedSource:
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
    refresh_status: str
    refresh_detail: str
    limitations: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class RefreshedClaim:
    claim: str
    prior_status: str
    refresh_status: str
    evidence_class: str
    rationale: str
    source_ids: list[str]
    residual_gaps: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class StaleClaimRefreshPacket:
    ticker: str
    trade_date: str
    generated_at_utc: str
    research_cycle: dict[str, Any]
    stage: str
    compliance_status: str
    delta_packet_path: str
    prior_graph_path: str
    refreshed_claims: list[RefreshedClaim]
    refreshed_sources: list[RefreshedSource]
    status_counts: dict[str, int]
    next_required_evidence: list[str]


def build_stale_claim_refresh_packet(
    *,
    delta_packet_path: Path,
    prior_graph_path: Path,
    check_urls: bool = True,
) -> StaleClaimRefreshPacket:
    delta = _read_json(delta_packet_path)
    prior_graph = _read_json(prior_graph_path)
    source_nodes = _source_nodes(prior_graph)

    stale_items = [
        item
        for item in delta.get("delta_items", [])
        if item.get("delta_status") == "Stale" and item.get("prior_status") == "Supported"
    ]
    refreshed_claims: list[RefreshedClaim] = []
    refreshed_sources_by_id: dict[str, RefreshedSource] = {}
    for item in stale_items:
        source_ids = [source_id for source_id in item.get("source_refs", []) if source_id in source_nodes]
        refreshed_sources: list[RefreshedSource] = []
        for source_id in source_ids:
            source = source_nodes[source_id]
            refreshed = _refresh_source(source_id, source, check_urls=check_urls)
            refreshed_sources_by_id[source_id] = refreshed
            refreshed_sources.append(refreshed)
        status = "Supported" if refreshed_sources and all(src.refresh_status != "Unavailable" for src in refreshed_sources) else "Conditional"
        refreshed_claims.append(
            RefreshedClaim(
                claim=item["label"],
                prior_status=item["prior_status"],
                refresh_status=status,
                evidence_class="refreshed_prior_source" if status == "Supported" else "partial_refreshed_source",
                rationale=_claim_rationale(item["label"], refreshed_sources, status),
                source_ids=source_ids,
                residual_gaps=[] if status == "Supported" else ["Refresh source was unavailable or incomplete."],
            )
        )

    generated_at_utc = utc_now_iso()
    return StaleClaimRefreshPacket(
        ticker=delta["ticker"],
        trade_date=delta["fresh_research_date"],
        generated_at_utc=generated_at_utc,
        research_cycle=inherit_research_cycle(
            {"research_cycle": delta.get("fresh_research_cycle", {})},
            fallback_ticker=delta["ticker"],
            fallback_trade_date=delta["fresh_research_date"],
            fallback_generated_at_utc=generated_at_utc,
        ),
        stage="Stage 2D - Stale Claim Refresh",
        compliance_status="Not Titan-Compliant",
        delta_packet_path=str(delta_packet_path),
        prior_graph_path=str(prior_graph_path),
        refreshed_claims=refreshed_claims,
        refreshed_sources=list(refreshed_sources_by_id.values()),
        status_counts=_status_counts(refreshed_claims),
        next_required_evidence=[
            "Feed refreshed claims into Stage 3 graph generation.",
            "Rerun evidence delta to confirm stale items are removed or preserved as conditional.",
            "Use refreshed sources as current evidence only within their stated limitations.",
        ],
    )


def write_stale_claim_refresh_packet(packet: StaleClaimRefreshPacket, out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{packet.ticker}_{packet.trade_date}_stage2d_stale_claim_refresh_packet"
    json_path = out_dir / f"{stem}.json"
    md_path = out_dir / f"{stem}.md"
    payload = asdict(packet)
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(_to_markdown(payload), encoding="utf-8")
    return json_path, md_path


def _source_nodes(graph: dict[str, Any]) -> dict[str, dict[str, Any]]:
    sources: dict[str, dict[str, Any]] = {}
    for node in graph.get("nodes", []):
        if node.get("node_type") != "source":
            continue
        source_id = node.get("label")
        if source_id:
            sources[source_id] = node.get("attributes", {})
    return sources


def _refresh_source(source_id: str, source: dict[str, Any], *, check_urls: bool) -> RefreshedSource:
    retrieved = utc_now_iso()
    url = source.get("url") or ""
    refresh_status = "Not Checked"
    detail = "URL check disabled."
    if check_urls and url.startswith(("http://", "https://")):
        refresh_status, detail = _check_url(url)
    elif check_urls:
        refresh_status = "Unavailable"
        detail = "Source URL was not HTTP(S)."
    return RefreshedSource(
        source_id=source_id,
        title=source.get("title") or source_id,
        publisher=source.get("publisher") or "Unknown",
        url=url,
        published_date=source.get("published_date"),
        retrieved_at_utc=retrieved,
        reliability_tier=source.get("reliability_tier") or "unknown",
        source_type=source.get("source_type") or "unknown",
        evidence_summary=source.get("evidence_summary") or "",
        supported_claims=source.get("supported_claims") or [],
        refresh_status=refresh_status,
        refresh_detail=detail,
        limitations=source.get("limitations") or [],
    )


def _check_url(url: str) -> tuple[str, str]:
    request = Request(url, headers={"User-Agent": "TitanTradingResearch/0.1"})
    try:
        with urlopen(request, timeout=15) as response:
            return "Available", f"HTTP {response.status}"
    except HTTPError as exc:
        if exc.code in {401, 403, 405, 429}:
            return "Reachability Restricted", f"HTTP {exc.code}"
        return "Unavailable", f"HTTP {exc.code}"
    except URLError as exc:
        return "Unavailable", str(exc.reason)
    except TimeoutError:
        return "Unavailable", "Timed out"


def _claim_rationale(label: str, sources: list[RefreshedSource], status: str) -> str:
    if not sources:
        return f"{label} was stale and no prior source nodes were available for refresh."
    source_text = ", ".join(f"{source.source_id} ({source.refresh_status})" for source in sources)
    if status == "Supported":
        return f"{label} was stale in the fresh graph but prior supported source evidence was refreshed: {source_text}."
    return f"{label} remains conditional after refresh attempt: {source_text}."


def _status_counts(claims: list[RefreshedClaim]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for claim in claims:
        counts[claim.refresh_status] = counts.get(claim.refresh_status, 0) + 1
    return dict(sorted(counts.items()))


def _to_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# Stage 2D Stale Claim Refresh: {payload['ticker']} {payload['trade_date']}",
        "",
        f"Generated UTC: {payload['generated_at_utc']}",
        f"Compliance Status: {payload['compliance_status']}",
        "",
        "## Refreshed Claims",
        "",
        "| Status | Claim | Sources | Rationale |",
        "|---|---|---|---|",
    ]
    for claim in payload["refreshed_claims"]:
        lines.append(
            f"| {claim['refresh_status']} | {claim['claim']} | {', '.join(claim['source_ids']) or 'None'} | {claim['rationale']} |"
        )
    lines.extend(["", "## Refreshed Sources", "", "| Source | Publisher | Refresh | URL |", "|---|---|---|---|"])
    for source in payload["refreshed_sources"]:
        lines.append(
            f"| {source['source_id']} | {source['publisher']} | {source['refresh_status']} | {source['url']} |"
        )
    lines.extend(["", "## Status Counts", "", "```json", json.dumps(payload["status_counts"], indent=2), "```"])
    lines.extend(["", "## Next Required Evidence", ""])
    lines.extend(f"- {item}" for item in payload["next_required_evidence"])
    return "\n".join(lines) + "\n"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))
