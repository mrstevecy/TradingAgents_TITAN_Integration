"""Evidence delta packet builder.

The delta layer compares prior graph-backed research with a fresh graph. It is
used before horizon validation so the system can identify what changed, what
stayed grounded, what became stale, and what remains blocked.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .research_cycle import utc_now_iso


@dataclass(frozen=True)
class DeltaItem:
    item_type: str
    label: str
    prior_status: str | None
    fresh_status: str | None
    delta_status: str
    rationale: str
    required_action: str
    source_refs: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class EvidenceDeltaPacket:
    ticker: str
    prior_research_date: str
    fresh_research_date: str
    generated_at_utc: str
    prior_research_cycle: dict[str, Any]
    fresh_research_cycle: dict[str, Any]
    stage: str
    compliance_status: str
    prior_graph_path: str
    fresh_graph_path: str
    delta_items: list[DeltaItem]
    delta_counts: dict[str, int]
    blocked_items: list[DeltaItem]
    reusable_items: list[DeltaItem]
    refresh_requirements: list[str]
    next_required_evidence: list[str]


def build_evidence_delta_packet(
    *,
    prior_graph_path: Path,
    fresh_graph_path: Path,
    fresh_research_date: str | None = None,
) -> EvidenceDeltaPacket:
    prior_graph = _read_json(prior_graph_path)
    fresh_graph = _read_json(fresh_graph_path)
    ticker = fresh_graph["ticker"]
    prior_date = prior_graph["trade_date"]
    fresh_date = fresh_research_date or fresh_graph["trade_date"]
    same_graph = prior_graph_path.resolve() == fresh_graph_path.resolve()

    prior_items = _index_graph_items(prior_graph)
    fresh_items = _index_graph_items(fresh_graph)
    labels = sorted(set(prior_items) | set(fresh_items))
    delta_items = [
        _compare_item(
            label,
            prior_items.get(label),
            fresh_items.get(label),
            prior_date,
            fresh_date,
            same_graph,
        )
        for label in labels
    ]

    blocked_items = [
        item
        for item in delta_items
        if item.delta_status in {"Blocked", "Still Blocked"}
    ]
    reusable_items = [
        item for item in delta_items if item.delta_status in {"Unchanged Supported", "Strengthened"}
    ]

    return EvidenceDeltaPacket(
        ticker=ticker,
        prior_research_date=prior_date,
        fresh_research_date=fresh_date,
        generated_at_utc=utc_now_iso(),
        prior_research_cycle=prior_graph.get("research_cycle", {}),
        fresh_research_cycle=fresh_graph.get("research_cycle", {}),
        stage="Evidence Delta Packet",
        compliance_status="Not Titan-Compliant",
        prior_graph_path=str(prior_graph_path),
        fresh_graph_path=str(fresh_graph_path),
        delta_items=delta_items,
        delta_counts=_counts(delta_items),
        blocked_items=blocked_items,
        reusable_items=reusable_items,
        refresh_requirements=_refresh_requirements(delta_items, prior_date, fresh_date),
        next_required_evidence=[
            "Run fresh source retrieval before treating same-date deltas as current evidence.",
            "Resolve or preserve blocked valuation items before final Titan report language.",
            "Feed delta packet into Stage 4 Titan horizon validation.",
            "Persist the next fresh graph after validation so future runs inherit updated context.",
        ],
    )


def write_evidence_delta_packet(packet: EvidenceDeltaPacket, out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{packet.ticker}_{packet.fresh_research_date}_evidence_delta_packet"
    json_path = out_dir / f"{stem}.json"
    md_path = out_dir / f"{stem}.md"
    payload = asdict(packet)
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(_to_markdown(payload), encoding="utf-8")
    return json_path, md_path


def _index_graph_items(graph: dict[str, Any]) -> dict[str, dict[str, Any]]:
    items: dict[str, dict[str, Any]] = {}
    for node in graph.get("nodes", []):
        node_type = node.get("node_type")
        attrs = node.get("attributes", {})
        if node_type == "claim":
            label = node["label"]
            status = attrs.get("reinforced_status")
            stance = _extract_stance_label(label)
            if stance:
                label = "TradingAgents final stance"
                status = stance
            items[label] = {
                "item_type": "claim",
                "status": status,
                "evidence_class": attrs.get("evidence_class"),
                "rationale": attrs.get("rationale"),
                "source_refs": _source_refs_for_node(graph, node["id"]),
            }
        elif node_type == "computed_metric":
            items[node["label"]] = {
                "item_type": "computed_metric",
                "status": attrs.get("reconciliation_status"),
                "evidence_class": "computed_metric",
                "rationale": attrs.get("conclusion"),
                "source_refs": _source_refs_for_metric(graph, node["id"]),
            }
    return items


def _compare_item(
    label: str,
    prior: dict[str, Any] | None,
    fresh: dict[str, Any] | None,
    prior_date: str,
    fresh_date: str,
    same_graph: bool,
) -> DeltaItem:
    if prior is None and fresh is not None:
        return DeltaItem(
            item_type=fresh["item_type"],
            label=label,
            prior_status=None,
            fresh_status=fresh["status"],
            delta_status="Newly Discovered",
            rationale="Item exists in the fresh graph but not in the prior graph.",
            required_action="Validate the new item through the relevant Titan evidence gate.",
            source_refs=fresh.get("source_refs", []),
        )
    if prior is not None and fresh is None:
        return DeltaItem(
            item_type=prior["item_type"],
            label=label,
            prior_status=prior["status"],
            fresh_status=None,
            delta_status="Stale",
            rationale="Item existed in the prior graph but is absent from the fresh graph.",
            required_action="Determine whether the item is obsolete, missing from retrieval, or intentionally removed.",
            source_refs=prior.get("source_refs", []),
        )

    assert prior is not None and fresh is not None
    if prior["status"] == fresh["status"]:
        blocked_statuses = {
            "Contradictory",
            "Conditional",
            "Not Validated",
            "Computed - Source Conflict Preserved",
            "Not Computable - Missing Explicit Input",
            "Blocked",
        }
        if fresh["status"] in blocked_statuses:
            status = "Still Blocked"
            action = "Resolve the blocked evidence requirement before final Titan use."
        elif prior_date == fresh_date or same_graph:
            status = "Needs Fresh Evidence"
            action = "Run fresh timestamped evidence retrieval before treating this as current."
        else:
            status = "Unchanged Supported"
            action = "Carry forward as historical context and refresh time-sensitive data as needed."
        return DeltaItem(
            item_type=fresh["item_type"],
            label=label,
            prior_status=prior["status"],
            fresh_status=fresh["status"],
            delta_status=status,
            rationale="Prior and fresh graph statuses match.",
            required_action=action,
            source_refs=fresh.get("source_refs", []),
        )

    if prior["status"] in {"Conditional", "Not Validated", "Contradictory"} and fresh["status"] == "Supported":
        status = "Strengthened"
        action = "Use strengthened item only after confirming the fresh source timestamp and evidence class."
    elif fresh["status"] in {"Contradictory", "Not Validated"}:
        status = "Blocked"
        action = "Block final Titan language until the contradiction or validation failure is resolved."
    else:
        status = "Updated"
        action = "Review status transition and route to the relevant Titan validation gate."

    return DeltaItem(
        item_type=fresh["item_type"],
        label=label,
        prior_status=prior["status"],
        fresh_status=fresh["status"],
        delta_status=status,
        rationale=f"Status changed from {prior['status']} to {fresh['status']}.",
        required_action=action,
        source_refs=fresh.get("source_refs", []),
    )


def _extract_stance_label(label: str) -> str | None:
    match = re.match(r"TradingAgents final stance is (.+)\.$", label)
    return match.group(1) if match else None


def _source_refs_for_node(graph: dict[str, Any], node_id: str) -> list[str]:
    refs: list[str] = []
    source_labels = {node["id"]: node["label"] for node in graph.get("nodes", []) if node.get("node_type") == "source"}
    for edge in graph.get("links", []):
        if edge.get("source") == node_id and edge.get("target") in source_labels:
            refs.append(source_labels[edge["target"]])
    return refs


def _source_refs_for_metric(graph: dict[str, Any], metric_id: str) -> list[str]:
    input_ids = {
        edge["target"]
        for edge in graph.get("links", [])
        if edge.get("source") == metric_id and edge.get("relation") == "uses_input"
    }
    source_labels = {node["id"]: node["label"] for node in graph.get("nodes", []) if node.get("node_type") == "source"}
    refs: list[str] = []
    for edge in graph.get("links", []):
        if edge.get("source") in input_ids and edge.get("target") in source_labels:
            refs.append(source_labels[edge["target"]])
    return refs


def _counts(items: list[DeltaItem]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        counts[item.delta_status] = counts.get(item.delta_status, 0) + 1
    return dict(sorted(counts.items()))


def _refresh_requirements(items: list[DeltaItem], prior_date: str, fresh_date: str) -> list[str]:
    requirements: list[str] = []
    if prior_date == fresh_date:
        requirements.append(
            "Prior and fresh graph dates are identical; this is a structural delta test, not a fresh market update."
        )
    for item in items:
        if item.delta_status in {"Still Blocked", "Blocked", "Needs Fresh Evidence", "Stale"}:
            requirements.append(f"{item.label}: {item.required_action}")
    return list(dict.fromkeys(requirements))


def _to_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# Evidence Delta Packet: {payload['ticker']} {payload['fresh_research_date']}",
        "",
        f"Generated UTC: {payload['generated_at_utc']}",
        f"Prior Research Run ID: {payload.get('prior_research_cycle', {}).get('research_run_id')}",
        f"Fresh Research Run ID: {payload.get('fresh_research_cycle', {}).get('research_run_id')}",
        f"Fresh Research Generated Local: {payload.get('fresh_research_cycle', {}).get('research_generated_at_local')}",
        f"Fresh Market Data As Of: {payload.get('fresh_research_cycle', {}).get('market_data_as_of')}",
        f"Compliance Status: {payload['compliance_status']}",
        f"Prior Graph: `{payload['prior_graph_path']}`",
        f"Fresh Graph: `{payload['fresh_graph_path']}`",
        "",
        "## Delta Counts",
        "",
        _code_json(payload["delta_counts"]),
        "",
        "## Delta Items",
        "",
        "| Delta | Type | Prior | Fresh | Item | Required Action |",
        "|---|---|---|---|---|---|",
    ]
    for item in payload["delta_items"]:
        lines.append(
            f"| {item['delta_status']} | {item['item_type']} | {item['prior_status']} | "
            f"{item['fresh_status']} | {item['label']} | {item['required_action']} |"
        )

    lines.extend(["", "## Blocked Items", ""])
    if payload["blocked_items"]:
        for item in payload["blocked_items"]:
            lines.append(f"- {item['label']}: {item['fresh_status']} -> {item['required_action']}")
    else:
        lines.append("- None.")

    lines.extend(["", "## Reusable Items", ""])
    if payload["reusable_items"]:
        for item in payload["reusable_items"]:
            lines.append(f"- {item['label']}: {item['fresh_status']}")
    else:
        lines.append("- None.")

    lines.extend(["", "## Refresh Requirements", ""])
    lines.extend(f"- {item}" for item in payload["refresh_requirements"])
    lines.extend(["", "## Next Required Evidence", ""])
    lines.extend(f"- {item}" for item in payload["next_required_evidence"])
    return "\n".join(lines) + "\n"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _code_json(value: Any) -> str:
    return "```json\n" + json.dumps(value, indent=2, ensure_ascii=False) + "\n```"
