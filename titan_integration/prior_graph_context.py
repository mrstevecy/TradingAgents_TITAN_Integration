"""Prior graph context loader for repeated ticker research.

This module discovers existing graph-backed research for the same ticker and
summarizes what can be reused, what must be refreshed, and what remains blocked.
It is the continuity layer that prevents repeated research from starting from
scratch when timestamped evidence already exists.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class PriorGraphSummary:
    ticker: str
    research_date: str
    graph_path: str
    generated_at_utc: str | None
    node_count: int
    edge_count: int
    claim_status_counts: dict[str, int]
    computed_metric_count: int
    residual_gap_count: int
    reusable_claims: list[dict[str, Any]]
    blocked_items: list[str]


@dataclass(frozen=True)
class PriorGraphContextPacket:
    ticker: str
    as_of_date: str
    generated_at_utc: str
    stage: str
    context_status: str
    graph_root: str
    prior_graphs: list[PriorGraphSummary]
    latest_prior_graph: PriorGraphSummary | None
    continuity_instructions: list[str]
    refresh_requirements: list[str]
    next_required_evidence: list[str]


def build_prior_graph_context(
    *, ticker: str, as_of_date: str, graph_root: Path, include_same_date: bool = False
) -> PriorGraphContextPacket:
    ticker = ticker.upper()
    prior_graphs = _discover_graphs(
        ticker=ticker,
        as_of_date=as_of_date,
        graph_root=graph_root,
        include_same_date=include_same_date,
    )
    latest = prior_graphs[-1] if prior_graphs else None
    status = "Prior Graph Context Available" if latest else "No Prior Graph Context Found"
    return PriorGraphContextPacket(
        ticker=ticker,
        as_of_date=as_of_date,
        generated_at_utc=datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        stage="Stage 0 - Prior Graph Context Loader",
        context_status=status,
        graph_root=str(graph_root),
        prior_graphs=prior_graphs,
        latest_prior_graph=latest,
        continuity_instructions=_continuity_instructions(bool(latest)),
        refresh_requirements=_refresh_requirements(latest),
        next_required_evidence=[
            "Load latest prior graph before new TradingAgents or Titan analysis.",
            "Run fresh data, news, macro, valuation, and technical evidence retrieval for the new timestamp.",
            "Compare new evidence against prior claims, statuses, residual gaps, and computed metrics.",
            "Generate an evidence delta packet before final report generation.",
        ],
    )


def write_prior_graph_context(packet: PriorGraphContextPacket, out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{packet.ticker}_{packet.as_of_date}_prior_graph_context"
    json_path = out_dir / f"{stem}.json"
    md_path = out_dir / f"{stem}.md"
    payload = asdict(packet)
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(_to_markdown(payload), encoding="utf-8")
    return json_path, md_path


def _discover_graphs(
    *, ticker: str, as_of_date: str, graph_root: Path, include_same_date: bool
) -> list[PriorGraphSummary]:
    results: list[PriorGraphSummary] = []
    if not graph_root.exists():
        return results
    for graph_path in graph_root.glob(f"{ticker}_*/graph.json"):
        research_date = graph_path.parent.name.replace(f"{ticker}_", "", 1)
        if include_same_date:
            is_prior = research_date <= as_of_date
        else:
            is_prior = research_date < as_of_date
        if not is_prior:
            continue
        graph = json.loads(graph_path.read_text(encoding="utf-8"))
        results.append(_summarize_graph(graph_path, graph, ticker, research_date))
    return sorted(results, key=lambda item: item.research_date)


def _summarize_graph(
    graph_path: Path, graph: dict[str, Any], ticker: str, research_date: str
) -> PriorGraphSummary:
    audit = graph.get("audit", {})
    nodes = graph.get("nodes", [])
    links = graph.get("links", [])
    reusable_claims = []
    blocked_items = []
    for node in nodes:
        if node.get("node_type") != "claim":
            continue
        attrs = node.get("attributes", {})
        status = attrs.get("reinforced_status")
        claim_summary = {
            "claim": node.get("label"),
            "status": status,
            "evidence_class": attrs.get("evidence_class"),
            "rationale": attrs.get("rationale"),
        }
        if status == "Supported":
            reusable_claims.append(claim_summary)
        elif status in {"Contradictory", "Conditional", "Not Validated"}:
            blocked_items.append(f"{node.get('label')}: {status}")

    for node in nodes:
        if node.get("node_type") == "computed_metric":
            attrs = node.get("attributes", {})
            status = attrs.get("reconciliation_status", "Unknown")
            if status != "Reconciled":
                blocked_items.append(f"{node.get('label')}: {status}")

    return PriorGraphSummary(
        ticker=ticker,
        research_date=research_date,
        graph_path=str(graph_path),
        generated_at_utc=graph.get("generated_at_utc"),
        node_count=len(nodes),
        edge_count=len(links),
        claim_status_counts=audit.get("claim_status_counts", {}),
        computed_metric_count=audit.get("computed_metric_count", 0),
        residual_gap_count=audit.get("residual_gap_count", 0),
        reusable_claims=reusable_claims,
        blocked_items=blocked_items,
    )


def _continuity_instructions(has_prior: bool) -> list[str]:
    if not has_prior:
        return [
            "No prior graph was found; proceed with a full fresh research run.",
            "After research completes, generate Stage 1 through Stage 3 artifacts for future continuity.",
        ]
    return [
        "Treat prior supported claims as historical context, not automatically current evidence.",
        "Reload prior residual gaps and blocked items before forming the new research plan.",
        "Refresh all time-sensitive evidence: price, volume, technicals, news, macro, earnings, estimates, and catalysts.",
        "Compare new evidence against prior graph nodes and record changes in an evidence delta packet.",
        "Do not reuse prior horizon classifications without fresh Titan horizon validation.",
    ]


def _refresh_requirements(latest: PriorGraphSummary | None) -> list[str]:
    if latest is None:
        return ["Full evidence collection required; no graph-backed prior context is available."]
    requirements = [
        "Refresh report-timestamp price and technical structure.",
        "Refresh newsflow and macro context since the prior research date.",
        "Refresh forward estimates and recompute valuation ratios.",
        "Recheck all prior residual gaps.",
    ]
    requirements.extend(f"Resolve prior blocked item: {item}" for item in latest.blocked_items)
    return requirements


def _to_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# Prior Graph Context: {payload['ticker']} as of {payload['as_of_date']}",
        "",
        f"Generated UTC: {payload['generated_at_utc']}",
        f"Context Status: {payload['context_status']}",
        "",
        "## Prior Graphs",
        "",
    ]
    if not payload["prior_graphs"]:
        lines.append("- None found.")
    else:
        for graph in payload["prior_graphs"]:
            lines.extend(
                [
                    f"### {graph['research_date']}",
                    "",
                    f"- Graph: `{graph['graph_path']}`",
                    f"- Nodes: {graph['node_count']}",
                    f"- Edges: {graph['edge_count']}",
                    f"- Claim statuses: `{json.dumps(graph['claim_status_counts'])}`",
                    f"- Computed metrics: {graph['computed_metric_count']}",
                    f"- Residual gaps: {graph['residual_gap_count']}",
                    "",
                    "Reusable supported claims:",
                    "",
                ]
            )
            lines.extend(
                f"- {claim['claim']} ({claim['evidence_class']})"
                for claim in graph["reusable_claims"][:10]
            )
            if not graph["reusable_claims"]:
                lines.append("- None.")
            lines.extend(["", "Blocked / refresh items:", ""])
            lines.extend(f"- {item}" for item in graph["blocked_items"][:12])
            if not graph["blocked_items"]:
                lines.append("- None.")
            lines.append("")

    lines.extend(["## Continuity Instructions", ""])
    lines.extend(f"- {item}" for item in payload["continuity_instructions"])
    lines.extend(["", "## Refresh Requirements", ""])
    lines.extend(f"- {item}" for item in payload["refresh_requirements"])
    lines.extend(["", "## Next Required Evidence", ""])
    lines.extend(f"- {item}" for item in payload["next_required_evidence"])
    return "\n".join(lines) + "\n"
