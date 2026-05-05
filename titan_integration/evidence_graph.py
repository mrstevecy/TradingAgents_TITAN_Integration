"""Stage 3 Graphify-compatible evidence graph builder.

This module builds a deterministic evidence graph from Stage 1, Stage 2,
Stage 2B, and their manifests. The source packets are already structured, so
Stage 3 should preserve relationships rather than reinterpret them through an
LLM extraction pass.
"""

from __future__ import annotations

import html
import json
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .research_cycle import inherit_research_cycle, utc_now_iso


@dataclass
class GraphNode:
    id: str
    label: str
    node_type: str
    source_file: str | None = None
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass
class GraphEdge:
    source: str
    target: str
    relation: str
    confidence: str
    confidence_score: float
    source_file: str | None = None
    weight: float = 1.0
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass
class EvidenceGraph:
    ticker: str
    trade_date: str
    generated_at_utc: str
    research_cycle: dict[str, Any]
    stage: str
    compliance_status: str
    nodes: list[GraphNode]
    links: list[GraphEdge]
    communities: dict[str, list[str]]
    audit: dict[str, Any]


def build_evidence_graph(
    *,
    stage1_packet_path: Path,
    stage2_packet_path: Path,
    stage2b_packet_path: Path,
    stage2c_packet_path: Path | None = None,
    stage2d_packet_path: Path | None = None,
    stage4_packet_path: Path | None = None,
    stage5_manifest_path: Path | None = None,
    citation_manifest_path: Path,
    reinforcement_manifest_path: Path,
) -> EvidenceGraph:
    stage1 = _read_json(stage1_packet_path)
    stage2 = _read_json(stage2_packet_path)
    stage2b = _read_json(stage2b_packet_path)
    stage2c = _read_json(stage2c_packet_path) if stage2c_packet_path and stage2c_packet_path.exists() else None
    stage2d = _read_json(stage2d_packet_path) if stage2d_packet_path and stage2d_packet_path.exists() else None
    stage4 = _read_json(stage4_packet_path) if stage4_packet_path and stage4_packet_path.exists() else None
    stage5_manifest = _read_json(stage5_manifest_path) if stage5_manifest_path and stage5_manifest_path.exists() else None
    citation_manifest = _read_json(citation_manifest_path)
    reinforcement_manifest = _read_json(reinforcement_manifest_path)

    builder = _GraphBuilder()
    ticker = stage2b["ticker"]
    trade_date = stage2b["trade_date"]

    packet_ids = {
        "stage1": "packet_stage1",
        "stage2": "packet_stage2",
        "stage2b": "packet_stage2b",
        "stage2c": "packet_stage2c",
        "stage2d": "packet_stage2d",
        "stage4": "packet_stage4",
        "stage5": "packet_stage5_final_report",
        "citation_manifest": "manifest_stage2_citations",
        "reinforcement_manifest": "manifest_stage2b_reinforcement",
    }

    builder.add_node(packet_ids["stage1"], "Stage 1 Pre-Compliance Packet", "packet", stage1_packet_path)
    builder.add_node(packet_ids["stage2"], "Stage 2 Citation Packet", "packet", stage2_packet_path)
    builder.add_node(packet_ids["stage2b"], "Stage 2B Reinforcement Packet", "packet", stage2b_packet_path)
    if stage2c and stage2c_packet_path:
        builder.add_node(
            packet_ids["stage2c"], "Stage 2C Metric Reconciliation Packet", "packet", stage2c_packet_path
        )
    if stage2d and stage2d_packet_path:
        builder.add_node(packet_ids["stage2d"], "Stage 2D Stale Claim Refresh Packet", "packet", stage2d_packet_path)
    if stage4 and stage4_packet_path:
        builder.add_node(packet_ids["stage4"], "Stage 4 Horizon Validation Packet", "packet", stage4_packet_path)
    if stage5_manifest and stage5_manifest_path:
        builder.add_node(
            packet_ids["stage5"],
            "Stage 5 Final Institutional Report",
            "final_report",
            stage5_manifest_path,
            {
                "final_html_path": stage5_manifest.get("final_html_path"),
                "final_markdown_path": stage5_manifest.get("final_markdown_path"),
                "final_pdf_path": stage5_manifest.get("final_pdf_path"),
                "baseline_preservation_rule": stage5_manifest.get("baseline_preservation_rule"),
                "logo_resolution": stage5_manifest.get("logo_resolution", {}),
            },
        )
    builder.add_node(packet_ids["citation_manifest"], "Stage 2 Citation Manifest", "manifest", citation_manifest_path)
    builder.add_node(
        packet_ids["reinforcement_manifest"],
        "Stage 2B Reinforcement Manifest",
        "manifest",
        reinforcement_manifest_path,
    )

    builder.add_edge(packet_ids["stage2"], packet_ids["stage1"], "builds_on", "EXTRACTED", 1.0)
    builder.add_edge(packet_ids["stage2b"], packet_ids["stage2"], "reinforces", "EXTRACTED", 1.0)
    if stage2c:
        builder.add_edge(packet_ids["stage2c"], packet_ids["stage2b"], "reconciles_metrics_from", "EXTRACTED", 1.0)
    if stage2d:
        builder.add_edge(packet_ids["stage2d"], packet_ids["stage2b"], "refreshes_stale_claims_from", "EXTRACTED", 1.0)
    if stage4:
        builder.add_edge(packet_ids["stage4"], packet_ids["stage1"], "validates_horizons_from", "EXTRACTED", 1.0)
        builder.add_edge(packet_ids["stage4"], packet_ids["stage2b"], "uses_reinforced_evidence", "EXTRACTED", 1.0)
        if stage2c:
            builder.add_edge(packet_ids["stage4"], packet_ids["stage2c"], "uses_metric_reconciliation", "EXTRACTED", 1.0)
        if stage2d:
            builder.add_edge(packet_ids["stage4"], packet_ids["stage2d"], "uses_refreshed_claims", "EXTRACTED", 1.0)
    if stage5_manifest:
        builder.add_edge(packet_ids["stage5"], packet_ids["stage4"], "reports_horizon_validation", "EXTRACTED", 1.0)
        builder.add_edge(packet_ids["stage5"], packet_ids["stage1"], "reports_price_and_user_evidence", "EXTRACTED", 1.0)
        builder.add_edge(packet_ids["stage5"], packet_ids["stage2b"], "reports_source_audit", "EXTRACTED", 1.0)
    builder.add_edge(
        packet_ids["stage2"], packet_ids["citation_manifest"], "uses_manifest", "EXTRACTED", 1.0
    )
    builder.add_edge(
        packet_ids["stage2b"],
        packet_ids["reinforcement_manifest"],
        "uses_manifest",
        "EXTRACTED",
        1.0,
    )

    sources = {source["source_id"]: source for source in stage2b.get("citation_sources", [])}
    for source_id, source in sources.items():
        builder.add_node(
            _source_node_id(source_id),
            source_id,
            "source",
            stage2b_packet_path,
            {
                "title": source.get("title"),
                "publisher": source.get("publisher"),
                "url": source.get("url"),
                "published_date": source.get("published_date"),
                "reliability_tier": source.get("reliability_tier"),
                "source_type": source.get("source_type"),
                "evidence_summary": source.get("evidence_summary"),
                "limitations": source.get("limitations", []),
            },
        )
        tier_id = _status_node_id("source_tier", source.get("reliability_tier", "unknown"))
        builder.add_node(tier_id, source.get("reliability_tier", "unknown"), "source_tier")
        builder.add_edge(_source_node_id(source_id), tier_id, "has_reliability_tier", "EXTRACTED", 1.0)

    claims_by_text = {claim["claim"]: claim for claim in stage2.get("linked_claims", [])}
    for index, claim in enumerate(stage2b.get("reinforced_claims", []), start=1):
        claim_id = f"claim_{index:02d}"
        previous = claims_by_text.get(claim["claim"], {})
        builder.add_node(
            claim_id,
            claim["claim"],
            "claim",
            stage2b_packet_path,
            {
                "stage1_status": previous.get("stage1_status"),
                "stage2_status": previous.get("stage2_status"),
                "reinforced_status": claim.get("reinforced_status"),
                "evidence_class": claim.get("evidence_class"),
                "rationale": claim.get("rationale"),
                "task_id": claim.get("task_id"),
            },
        )
        builder.add_edge(packet_ids["stage2b"], claim_id, "contains_claim", "EXTRACTED", 1.0)

        status_id = _status_node_id("claim_status", claim.get("reinforced_status", "Unknown"))
        builder.add_node(status_id, claim.get("reinforced_status", "Unknown"), "claim_status")
        builder.add_edge(claim_id, status_id, "has_reinforced_status", "EXTRACTED", 1.0)

        evidence_class_id = _status_node_id("evidence_class", claim.get("evidence_class", "unknown"))
        builder.add_node(evidence_class_id, claim.get("evidence_class", "unknown"), "evidence_class")
        builder.add_edge(claim_id, evidence_class_id, "has_evidence_class", "EXTRACTED", 1.0)

        for source_id in claim.get("source_ids", []):
            if source_id not in sources:
                continue
            relation, score = _claim_source_relation(
                claim.get("reinforced_status"), claim.get("evidence_class"), source_id
            )
            builder.add_edge(claim_id, _source_node_id(source_id), relation, "EXTRACTED", score)

        for gap_index, gap in enumerate(claim.get("residual_gaps", []), start=1):
            gap_id = f"{claim_id}_gap_{gap_index:02d}"
            builder.add_node(gap_id, gap, "residual_gap", stage2b_packet_path)
            builder.add_edge(claim_id, gap_id, "has_residual_gap", "EXTRACTED", 1.0)

        task_id = claim.get("task_id")
        if task_id:
            task_node_id = _task_node_id(task_id)
            builder.add_edge(task_node_id, claim_id, "reinforces_claim", "EXTRACTED", 1.0)

    _add_user_technical_features(builder, stage1, stage1_packet_path, packet_ids["stage1"], sources)

    for task in stage2b.get("reinforcement_tasks", []):
        task_node_id = _task_node_id(task["task_id"])
        builder.add_node(
            task_node_id,
            task["task_id"],
            "reinforcement_task",
            stage2b_packet_path,
            {
                "original_stage2_status": task.get("original_stage2_status"),
                "reinforced_status": task.get("reinforced_status"),
                "missing_evidence": task.get("missing_evidence", []),
                "retrieval_actions": task.get("retrieval_actions", []),
                "rationale": task.get("rationale"),
            },
        )
        builder.add_edge(packet_ids["reinforcement_manifest"], task_node_id, "defines_task", "EXTRACTED", 1.0)
        for source_id in task.get("added_source_ids", []):
            if source_id in sources:
                builder.add_edge(task_node_id, _source_node_id(source_id), "retrieved_source", "EXTRACTED", 1.0)

    if stage2c and stage2c_packet_path:
        _add_metric_reconciliation(builder, stage2c, stage2c_packet_path, packet_ids["stage2c"])
    if stage2d and stage2d_packet_path:
        _add_stale_claim_refresh(builder, stage2d, stage2d_packet_path, packet_ids["stage2d"])
    if stage4 and stage4_packet_path:
        _add_horizon_validation_overlay(builder, stage4, stage4_packet_path, packet_ids)
    if stage5_manifest and stage5_manifest_path:
        _add_final_report_overlay(builder, stage5_manifest, stage5_manifest_path, packet_ids)

    _add_manifest_coverage(builder, citation_manifest, reinforcement_manifest, packet_ids)

    nodes = list(builder.nodes.values())
    links = builder.links
    communities = _communities(nodes)
    audit = _audit(nodes, links, stage1, stage2, stage2b, stage2c, stage2d, stage4, stage5_manifest)

    generated_at_utc = utc_now_iso()
    return EvidenceGraph(
        ticker=ticker,
        trade_date=trade_date,
        generated_at_utc=generated_at_utc,
        research_cycle=inherit_research_cycle(
            stage1,
            fallback_ticker=ticker,
            fallback_trade_date=trade_date,
            fallback_generated_at_utc=generated_at_utc,
        ),
        stage="Titan Validation Packet Stage 3F - Evidence Graph with Horizon and Report Overlay",
        compliance_status="Not Titan-Compliant",
        nodes=nodes,
        links=links,
        communities=communities,
        audit=audit,
    )


def write_evidence_graph(graph: EvidenceGraph, out_dir: Path) -> tuple[Path, Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        **asdict(graph),
        "graph_policy": {
            "edge_confidence": "EXTRACTED edges are direct from structured packets/manifests.",
            "inference_policy": "No LLM semantic inference was used in Stage 3 deterministic graph build.",
            "titan_status": "Pre-compliance evidence graph only.",
        },
    }
    graph_json = out_dir / "graph.json"
    graph_report = out_dir / "GRAPH_REPORT.md"
    graph_html = out_dir / "graph.html"
    graph_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    graph_report.write_text(_report(payload), encoding="utf-8")
    graph_html.write_text(_html(payload), encoding="utf-8")
    return graph_json, graph_report, graph_html


class _GraphBuilder:
    def __init__(self) -> None:
        self.nodes: dict[str, GraphNode] = {}
        self.links: list[GraphEdge] = []
        self._edge_keys: set[tuple[str, str, str]] = set()

    def add_node(
        self,
        node_id: str,
        label: str,
        node_type: str,
        source_file: Path | str | None = None,
        attributes: dict[str, Any] | None = None,
    ) -> None:
        if node_id in self.nodes:
            if attributes:
                self.nodes[node_id].attributes.update(attributes)
            return
        self.nodes[node_id] = GraphNode(
            id=node_id,
            label=label,
            node_type=node_type,
            source_file=str(source_file) if source_file else None,
            attributes=attributes or {},
        )

    def add_edge(
        self,
        source: str,
        target: str,
        relation: str,
        confidence: str,
        confidence_score: float,
        source_file: Path | str | None = None,
        attributes: dict[str, Any] | None = None,
    ) -> None:
        key = (source, target, relation)
        if key in self._edge_keys:
            return
        self._edge_keys.add(key)
        self.links.append(
            GraphEdge(
                source=source,
                target=target,
                relation=relation,
                confidence=confidence,
                confidence_score=confidence_score,
                source_file=str(source_file) if source_file else None,
                attributes=attributes or {},
            )
        )


def _add_metric_reconciliation(
    builder: _GraphBuilder, stage2c: dict[str, Any], stage2c_packet_path: Path, packet_id: str
) -> None:
    for index, metric in enumerate(stage2c.get("reconciled_metrics", []), start=1):
        metric_id = f"metric_{index:02d}_{_slug(metric['metric'])}"
        builder.add_node(
            metric_id,
            metric["metric"],
            "computed_metric",
            stage2c_packet_path,
            {
                "formula": metric.get("formula"),
                "computed_value": metric.get("computed_value"),
                "reported_values": metric.get("reported_values", {}),
                "reconciliation_status": metric.get("reconciliation_status"),
                "specific_claim_status": metric.get("specific_claim_status"),
                "usable_range": metric.get("usable_range", {}),
                "conclusion": metric.get("conclusion"),
                "limitations": metric.get("limitations", []),
            },
        )
        builder.add_edge(packet_id, metric_id, "contains_computed_metric", "EXTRACTED", 1.0)
        status_id = _status_node_id("metric_status", metric.get("reconciliation_status", "Unknown"))
        builder.add_node(status_id, metric.get("reconciliation_status", "Unknown"), "metric_status")
        builder.add_edge(metric_id, status_id, "has_reconciliation_status", "EXTRACTED", 1.0)

        formula_id = f"{metric_id}_formula"
        builder.add_node(formula_id, metric.get("formula", "formula"), "formula", stage2c_packet_path)
        builder.add_edge(metric_id, formula_id, "uses_formula", "EXTRACTED", 1.0)

        for input_index, metric_input in enumerate(metric.get("inputs", []), start=1):
            input_id = f"{metric_id}_input_{input_index:02d}_{_slug(metric_input['name'])}"
            builder.add_node(
                input_id,
                metric_input["name"],
                "metric_input",
                stage2c_packet_path,
                metric_input,
            )
            builder.add_edge(metric_id, input_id, "uses_input", "EXTRACTED", 1.0)
            source_id = metric_input.get("source_id")
            if source_id:
                builder.add_edge(input_id, _source_node_id(source_id), "sourced_from", "EXTRACTED", 1.0)


def _add_stale_claim_refresh(
    builder: _GraphBuilder, stage2d: dict[str, Any], stage2d_packet_path: Path, packet_id: str
) -> None:
    sources = {source["source_id"]: source for source in stage2d.get("refreshed_sources", [])}
    for source_id, source in sources.items():
        builder.add_node(
            _source_node_id(source_id),
            source_id,
            "source",
            stage2d_packet_path,
            {
                "title": source.get("title"),
                "publisher": source.get("publisher"),
                "url": source.get("url"),
                "published_date": source.get("published_date"),
                "reliability_tier": source.get("reliability_tier"),
                "source_type": source.get("source_type"),
                "evidence_summary": source.get("evidence_summary"),
                "supported_claims": source.get("supported_claims", []),
                "refresh_status": source.get("refresh_status"),
                "refresh_detail": source.get("refresh_detail"),
                "limitations": source.get("limitations", []),
            },
        )
        builder.add_edge(packet_id, _source_node_id(source_id), "refreshes_source", "EXTRACTED", 1.0)

    existing_claim_ids = {
        node.label: node_id
        for node_id, node in builder.nodes.items()
        if node.node_type == "claim"
    }
    start_index = len(existing_claim_ids) + 1
    for offset, claim in enumerate(stage2d.get("refreshed_claims", []), start=0):
        claim_id = existing_claim_ids.get(claim["claim"]) or f"claim_{start_index + offset:02d}_refreshed"
        builder.add_node(
            claim_id,
            claim["claim"],
            "claim",
            stage2d_packet_path,
            {
                "stage2d_refresh_status": claim.get("refresh_status"),
                "reinforced_status": claim.get("refresh_status"),
                "evidence_class": claim.get("evidence_class"),
                "rationale": claim.get("rationale"),
                "refresh_layer": "Stage 2D",
            },
        )
        builder.add_edge(packet_id, claim_id, "contains_refreshed_claim", "EXTRACTED", 1.0)
        status_id = _status_node_id("claim_status", claim.get("refresh_status", "Unknown"))
        builder.add_node(status_id, claim.get("refresh_status", "Unknown"), "claim_status")
        builder.add_edge(claim_id, status_id, "has_reinforced_status", "EXTRACTED", 1.0)
        evidence_class_id = _status_node_id("evidence_class", claim.get("evidence_class", "unknown"))
        builder.add_node(evidence_class_id, claim.get("evidence_class", "unknown"), "evidence_class")
        builder.add_edge(claim_id, evidence_class_id, "has_evidence_class", "EXTRACTED", 1.0)
        for source_id in claim.get("source_ids", []):
            if source_id in sources:
                builder.add_edge(claim_id, _source_node_id(source_id), "refreshed_by_source", "EXTRACTED", 1.0)
        for gap_index, gap in enumerate(claim.get("residual_gaps", []), start=1):
            gap_id = f"{claim_id}_stage2d_gap_{gap_index:02d}"
            builder.add_node(gap_id, gap, "residual_gap", stage2d_packet_path)
            builder.add_edge(claim_id, gap_id, "has_residual_gap", "EXTRACTED", 1.0)


def _add_horizon_validation_overlay(
    builder: _GraphBuilder,
    stage4: dict[str, Any],
    stage4_packet_path: Path,
    packet_ids: dict[str, str],
) -> None:
    for index, decision in enumerate(stage4.get("horizon_decisions", []), start=1):
        horizon = decision.get("horizon", f"horizon_{index:02d}")
        horizon_id = f"horizon_decision_{index:02d}_{_slug(horizon)}"
        builder.add_node(
            horizon_id,
            horizon,
            "horizon_decision",
            stage4_packet_path,
            {
                "classification": decision.get("classification"),
                "evidence_status": decision.get("evidence_status"),
                "rationale": decision.get("rationale"),
                "supported_evidence": decision.get("supported_evidence", []),
                "blocking_factors": decision.get("blocking_factors", []),
                "required_next_evidence": decision.get("required_next_evidence", []),
            },
        )
        builder.add_edge(packet_ids["stage4"], horizon_id, "contains_horizon_decision", "EXTRACTED", 1.0)
        status_id = _status_node_id("horizon_status", decision.get("classification", "Unknown"))
        builder.add_node(status_id, decision.get("classification", "Unknown"), "horizon_status")
        builder.add_edge(horizon_id, status_id, "has_horizon_classification", "EXTRACTED", 1.0)

        for evidence_index, evidence in enumerate(decision.get("supported_evidence", []), start=1):
            evidence_id = f"{horizon_id}_evidence_{evidence_index:02d}"
            builder.add_node(evidence_id, evidence, "horizon_evidence_statement", stage4_packet_path)
            builder.add_edge(horizon_id, evidence_id, "supported_by_horizon_evidence", "EXTRACTED", 1.0)
            _link_horizon_evidence_to_underlying_nodes(builder, evidence_id, evidence)

        for block_index, factor in enumerate(decision.get("blocking_factors", []), start=1):
            block_id = f"{horizon_id}_block_{block_index:02d}"
            builder.add_node(block_id, factor, "horizon_blocking_factor", stage4_packet_path)
            builder.add_edge(horizon_id, block_id, "has_horizon_blocking_factor", "EXTRACTED", 1.0)
            _link_horizon_evidence_to_underlying_nodes(builder, block_id, factor)

        for next_index, item in enumerate(decision.get("required_next_evidence", []), start=1):
            next_id = f"{horizon_id}_next_{next_index:02d}"
            builder.add_node(next_id, item, "horizon_required_next_evidence", stage4_packet_path)
            builder.add_edge(horizon_id, next_id, "requires_next_evidence", "EXTRACTED", 1.0)

    self_audit = stage4.get("titan_self_audit", {})
    if self_audit:
        audit_id = "stage4_titan_self_audit"
        builder.add_node(audit_id, "Stage 4 Titan Self-Audit", "self_audit", stage4_packet_path, self_audit)
        builder.add_edge(packet_ids["stage4"], audit_id, "contains_self_audit", "EXTRACTED", 1.0)


def _link_horizon_evidence_to_underlying_nodes(builder: _GraphBuilder, source_node_id: str, text: str) -> None:
    low = str(text or "").lower()
    if any(token in low for token in ("user technical", "15m", "5m", "1h", "4h", "1d", "1w", "vwap", "rsi", "adx")):
        for node_id, node in builder.nodes.items():
            if node.node_type in {"user_technical_feature", "user_technical_mtf_read"}:
                builder.add_edge(source_node_id, node_id, "references_user_technical_evidence", "EXTRACTED", 0.86)
    if any(token in low for token in ("valuation", "forward p/e", "eps", "assumption-based")):
        for node_id, node in builder.nodes.items():
            if node.node_type in {"computed_metric", "metric_status", "metric_input"}:
                builder.add_edge(source_node_id, node_id, "references_metric_reconciliation", "EXTRACTED", 0.9)
    if any(token in low for token in ("sec", "fundamental", "financial statement", "balance-sheet")):
        builder.add_edge(source_node_id, _source_node_id("stage1_sec_edgar"), "references_sec_evidence", "EXTRACTED", 0.88)
    if any(token in low for token in ("price", "50-day", "200-day", "distribution", "moving average", "daily")):
        builder.add_edge(source_node_id, _source_node_id("stage1_yfinance"), "references_price_evidence", "EXTRACTED", 0.82)
    if any(token in low for token in ("proxy", "ecosystem", "ai infrastructure", "macro", "geopolitical")):
        for node_id, node in builder.nodes.items():
            if node.node_type == "claim":
                label = node.label.lower()
                if any(token in label for token in ("proxy", "ecosystem", "macro", "ai", "infrastructure", "geopolitical")):
                    builder.add_edge(source_node_id, node_id, "references_context_claim", "EXTRACTED", 0.72)


def _add_final_report_overlay(
    builder: _GraphBuilder,
    stage5_manifest: dict[str, Any],
    stage5_manifest_path: Path,
    packet_ids: dict[str, str],
) -> None:
    report_id = packet_ids["stage5"]
    sections = [
        ("final_trade_decision", "Final Trade Decision", ["packet_stage4"]),
        ("market_report", "Market Report", ["packet_stage1", _source_node_id("stage1_yfinance")]),
        ("news_report", "News Report", ["packet_stage2b", "packet_stage2d"]),
        ("fundamentals_report", "Fundamentals Report", ["packet_stage1", _source_node_id("stage1_sec_edgar")]),
        ("sentiment_report", "Sentiment Report", ["packet_stage2b"]),
        ("investment_plan", "Investment Plan", ["packet_stage4"]),
        ("trader_investment_plan", "Trader Investment Plan", ["packet_stage4"]),
        ("titan_addendum_c", "TITAN Addendum C: User-Supplied Multi-Timeframe Technical Evidence", ["user_technical_mtf_read"]),
        ("titan_addendum_f", "TITAN Addendum F: Valuation and Metric Reconciliation", ["packet_stage2c"]),
        ("titan_addendum_g", "TITAN Addendum G: Validated Trading Horizon", ["packet_stage4"]),
        ("titan_addendum_h", "TITAN Addendum H: Evidence Graph and Source Audit", ["packet_stage2b"]),
        ("titan_addendum_j", "TITAN Addendum J: Citations and References", ["packet_stage2b"]),
    ]
    for key, label, targets in sections:
        section_id = f"report_section_{key}"
        builder.add_node(
            section_id,
            label,
            "report_section",
            stage5_manifest_path,
            {"section_key": key, "report_path": stage5_manifest.get("final_html_path")},
        )
        builder.add_edge(report_id, section_id, "contains_report_section", "EXTRACTED", 1.0)
        for target in targets:
            if target in builder.nodes:
                builder.add_edge(section_id, target, "traceable_to_evidence_layer", "EXTRACTED", 0.9)

    for node_id, node in list(builder.nodes.items()):
        if node.node_type == "horizon_decision":
            builder.add_edge("report_section_titan_addendum_g", node_id, "reports_horizon_decision", "EXTRACTED", 1.0)
        elif node.node_type == "source":
            builder.add_edge("report_section_titan_addendum_j", node_id, "lists_citation_source", "EXTRACTED", 0.85)
        elif node.node_type == "computed_metric":
            builder.add_edge("report_section_titan_addendum_f", node_id, "reports_metric_reconciliation", "EXTRACTED", 1.0)

    legal_id = "report_legal_notice_research_only"
    builder.add_node(
        legal_id,
        "Research-only / Not Financial Advice Notice",
        "legal_notice",
        stage5_manifest_path,
        {
            "notice": "Informational decision-support report only; not financial, investment, legal, tax, accounting, or brokerage advice.",
        },
    )
    builder.add_edge(report_id, legal_id, "contains_legal_notice", "EXTRACTED", 1.0)

    logo = stage5_manifest.get("logo_resolution", {}) or {}
    logo_id = "report_logo_attribution"
    builder.add_node(
        logo_id,
        "Issuer Logo Attribution Notice",
        "logo_attribution",
        stage5_manifest_path,
        {
            "ticker": logo.get("ticker"),
            "status": logo.get("status"),
            "path": logo.get("path"),
            "source_url": logo.get("source_url"),
            "official_website": logo.get("official_website"),
            "notice": "Logo used solely for issuer identification; no affiliation, sponsorship, approval, or endorsement implied.",
        },
    )
    builder.add_edge(report_id, logo_id, "contains_logo_attribution", "EXTRACTED", 1.0)


def _add_user_technical_features(
    builder: _GraphBuilder,
    stage1: dict[str, Any],
    stage1_packet_path: Path,
    packet_id: str,
    sources: dict[str, dict[str, Any]],
) -> None:
    feature_audit = stage1.get("user_technical_feature_audit", {})
    feature_summaries = feature_audit.get("feature_summaries", [])
    if not feature_summaries:
        return
    source_id = "stage1b_user_technical_features"
    source_node = _source_node_id(source_id)
    for index, feature in enumerate(feature_summaries, start=1):
        timeframe = feature.get("detected_timeframe", f"tf_{index:02d}")
        node_id = f"user_technical_{index:02d}_{_slug(timeframe)}"
        builder.add_node(
            node_id,
            f"{timeframe} User Technical Features",
            "user_technical_feature",
            stage1_packet_path,
            {
                "file_name": feature.get("file_name"),
                "latest_timestamp": feature.get("latest_timestamp"),
                "latest_close": feature.get("latest_close"),
                "latest_rolling_vwap": feature.get("latest_rolling_vwap"),
                "vwap_position": feature.get("vwap_position"),
                "volume_regime": feature.get("volume_regime"),
                "rsi_regime": feature.get("rsi_regime"),
                "latest_rsi": feature.get("latest_rsi"),
                "adx_regime": feature.get("adx_regime"),
                "latest_adx": feature.get("latest_adx"),
                "latest_atr": feature.get("latest_atr"),
                "atr_pct_of_close": feature.get("atr_pct_of_close"),
                "ma_position": feature.get("ma_position"),
                "band_position": feature.get("band_position"),
                "recent_bullish_divergence_count": feature.get("recent_bullish_divergence_count"),
                "recent_bearish_divergence_count": feature.get("recent_bearish_divergence_count"),
                "technical_read": feature.get("technical_read"),
                "columns_used": feature.get("columns_used", []),
            },
        )
        builder.add_edge(packet_id, node_id, "contains_user_technical_feature", "EXTRACTED", 1.0)
        if source_id in sources:
            builder.add_edge(node_id, source_node, "derived_from_source", "EXTRACTED", 1.0)

    mtf = feature_audit.get("multi_timeframe_read", {})
    mtf_id = "user_technical_mtf_read"
    builder.add_node(
        mtf_id,
        "User Technical Multi-Timeframe Read",
        "user_technical_mtf_read",
        stage1_packet_path,
        mtf,
    )
    builder.add_edge(packet_id, mtf_id, "contains_user_technical_mtf_read", "EXTRACTED", 1.0)
    if source_id in sources:
        builder.add_edge(mtf_id, source_node, "derived_from_source", "EXTRACTED", 1.0)


def _add_manifest_coverage(
    builder: _GraphBuilder,
    citation_manifest: dict[str, Any],
    reinforcement_manifest: dict[str, Any],
    packet_ids: dict[str, str],
) -> None:
    for index, rule in enumerate(citation_manifest.get("claim_links", []), start=1):
        rule_id = f"citation_rule_{index:02d}"
        builder.add_node(
            rule_id,
            ", ".join(rule.get("match_contains", [])) or rule_id,
            "citation_rule",
            attributes={
                "stage2_status": rule.get("stage2_status"),
                "evidence_class": rule.get("evidence_class"),
                "rationale": rule.get("rationale"),
            },
        )
        builder.add_edge(packet_ids["citation_manifest"], rule_id, "defines_rule", "EXTRACTED", 1.0)

    for source in reinforcement_manifest.get("added_sources", []):
        builder.add_edge(
            packet_ids["reinforcement_manifest"],
            _source_node_id(source["source_id"]),
            "adds_source",
            "EXTRACTED",
            1.0,
        )


def _claim_source_relation(
    status: str | None, evidence_class: str | None, source_id: str
) -> tuple[str, float]:
    if status == "Contradictory":
        if source_id.startswith("stockanalysis_"):
            return "contradicted_by_source", 1.0
        return "valuation_context_source", 0.75
    if evidence_class and "proxy" in evidence_class:
        return "supported_by_proxy_source", 0.85
    return "supported_by_source", 1.0


def _communities(nodes: list[GraphNode]) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = defaultdict(list)
    for node in nodes:
        grouped[node.node_type].append(node.id)
    return dict(sorted(grouped.items()))


def _audit(
    nodes: list[GraphNode],
    links: list[GraphEdge],
    stage1: dict[str, Any],
    stage2: dict[str, Any],
    stage2b: dict[str, Any],
    stage2c: dict[str, Any] | None,
    stage2d: dict[str, Any] | None,
    stage4: dict[str, Any] | None,
    stage5_manifest: dict[str, Any] | None,
) -> dict[str, Any]:
    node_counts = Counter(node.node_type for node in nodes)
    edge_counts = Counter(edge.relation for edge in links)
    status_counts = Counter(
        node.attributes.get("reinforced_status")
        for node in nodes
        if node.node_type == "claim" and node.attributes.get("reinforced_status")
    )
    return {
        "node_counts": dict(sorted(node_counts.items())),
        "edge_counts": dict(sorted(edge_counts.items())),
        "claim_status_counts": dict(sorted(status_counts.items())),
        "source_count": node_counts.get("source", 0),
        "stage1_compliance_status": stage1.get("compliance_status"),
        "stage2_compliance_status": stage2.get("compliance_status"),
        "stage2b_compliance_status": stage2b.get("compliance_status"),
        "stage2c_compliance_status": stage2c.get("compliance_status") if stage2c else "Not generated",
        "stage2d_compliance_status": stage2d.get("compliance_status") if stage2d else "Not generated",
        "stage4_compliance_status": stage4.get("compliance_status") if stage4 else "Not generated",
        "stage5_report_status": stage5_manifest.get("stage") if stage5_manifest else "Not generated",
        "refreshed_claim_count": len(stage2d.get("refreshed_claims", [])) if stage2d else 0,
        "horizon_decision_count": len(stage4.get("horizon_decisions", [])) if stage4 else 0,
        "report_section_count": node_counts.get("report_section", 0),
        "residual_gap_count": node_counts.get("residual_gap", 0),
        "computed_metric_count": node_counts.get("computed_metric", 0),
        "llm_semantic_extraction_used": False,
        "deterministic_build": True,
    }


def _report(payload: dict[str, Any]) -> str:
    audit = payload["audit"]
    cycle = payload.get("research_cycle", {})
    god_nodes = _top_degree_nodes(payload)
    surprising = _surprising_connections(payload)
    questions = _suggested_questions(payload)

    lines = [
        f"# Graphify Evidence Graph Report: {payload['ticker']}",
        "",
        f"Generated UTC: {payload['generated_at_utc']}",
        f"Research Run ID: {cycle.get('research_run_id')}",
        f"Research Generated Local: {cycle.get('research_generated_at_local')}",
        f"Requested Analysis Date: {cycle.get('requested_analysis_date')}",
        f"Market Data As Of: {cycle.get('market_data_as_of')}",
        f"Session Context: {cycle.get('session_context')}",
        f"Compliance Status: {payload['compliance_status']}",
        "",
        "## Audit Summary",
        "",
        f"- Nodes: {len(payload['nodes'])}",
        f"- Edges: {len(payload['links'])}",
        f"- Sources: {audit['source_count']}",
        f"- Residual gaps: {audit['residual_gap_count']}",
        f"- Deterministic build: {audit['deterministic_build']}",
        f"- LLM semantic extraction used: {audit['llm_semantic_extraction_used']}",
        "",
        "## Claim Status Counts",
        "",
        _code_json(audit["claim_status_counts"]),
        "",
        "## God Nodes",
        "",
    ]
    lines.extend(f"- {label}: degree {degree}" for label, degree in god_nodes)
    lines.extend(["", "## Surprising Connections", ""])
    lines.extend(f"- {item}" for item in surprising)
    lines.extend(["", "## Suggested Questions", ""])
    lines.extend(f"- {question}" for question in questions)
    lines.extend(
        [
            "",
            "## Residual Governance Notes",
            "",
            "- This graph includes the Stage 3 evidence layer plus Stage 4 horizon and Stage 5 report traceability overlays where provided.",
            "- Forward valuation is explicitly contradicted and must be recalculated or replaced before final reporting.",
            "- Proxy evidence must stay graph-labeled as indirect evidence.",
            "- Final business use remains evidence-gated; report sections are traceability nodes, not independent evidence.",
        ]
    )
    return "\n".join(lines) + "\n"


def _html(payload: dict[str, Any]) -> str:
    data = json.dumps(payload, ensure_ascii=False)
    cycle = payload.get("research_cycle", {})
    title = f"{payload['ticker']} Evidence Graph"
    subtitle = (
        f"Research Run: {cycle.get('research_generated_at_local') or payload.get('generated_at_utc')} "
        f"| Market Data As Of: {cycle.get('market_data_as_of') or payload.get('trade_date')}"
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{html.escape(title)}</title>
  <style>
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Arial, sans-serif;
      background: #f7f8fa;
      color: #111827;
      overflow: hidden;
    }}
    header {{
      height: 66px;
      padding: 14px 22px;
      background: #111827;
      color: white;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 18px;
    }}
    header strong {{ font-size: 16px; }}
    header .meta {{ color: #cbd5e1; font-size: 12px; margin-top: 4px; }}
    main {{
      display: grid;
      grid-template-columns: 300px minmax(520px, 1fr) 360px;
      height: calc(100vh - 66px);
      min-height: 620px;
    }}
    aside, .inspector {{
      background: white;
      overflow: auto;
      border-color: #d1d5db;
    }}
    aside {{
      border-right: 1px solid #d1d5db;
      padding: 14px;
    }}
    .inspector {{
      border-left: 1px solid #d1d5db;
      padding: 14px;
    }}
    .canvas-wrap {{
      position: relative;
      background:
        linear-gradient(90deg, rgba(17,24,39,0.035) 1px, transparent 1px),
        linear-gradient(rgba(17,24,39,0.035) 1px, transparent 1px);
      background-size: 28px 28px;
      overflow: hidden;
    }}
    svg {{ width: 100%; height: 100%; display: block; cursor: grab; }}
    svg:active {{ cursor: grabbing; }}
    input, select, button {{
      width: 100%;
      padding: 8px;
      border: 1px solid #cbd5e1;
      background: white;
      color: #111827;
      font-size: 13px;
    }}
    button {{ cursor: pointer; }}
    button:hover {{ background: #f3f4f6; }}
    label {{ display: block; font-size: 12px; color: #374151; margin: 12px 0 5px; }}
    .row {{ display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }}
    .pill {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      margin: 3px 5px 3px 0;
      padding: 3px 7px;
      border: 1px solid #d1d5db;
      border-radius: 999px;
      font-size: 11px;
      background: #f9fafb;
    }}
    .pill.filter-pill {{ cursor: pointer; }}
    .pill.filter-pill:hover {{ background: #eef2ff; border-color: #94a3b8; }}
    .pill.filter-pill.active {{ background: #e0f2fe; border-color: #0284c7; font-weight: 700; }}
    .swatch {{ width: 10px; height: 10px; border-radius: 50%; display: inline-block; }}
    .muted {{ color: #6b7280; font-size: 12px; }}
    .stat-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin: 12px 0; }}
    .stat {{ background: #f3f4f6; padding: 8px; border: 1px solid #e5e7eb; }}
    .stat.clickable {{ cursor: pointer; }}
    .stat.clickable:hover {{ background: #e0f2fe; border-color: #0284c7; }}
    .stat b {{ display: block; font-size: 16px; }}
    .stat span {{ color: #6b7280; font-size: 11px; }}
    .edge-line {{ stroke: #94a3b8; stroke-opacity: 0.52; stroke-width: 1.4; }}
    .edge-line.active {{ stroke: #111827; stroke-opacity: 0.95; stroke-width: 2.4; }}
    .edge-line.dimmed {{ stroke-opacity: 0.08; }}
    .edge-label {{ fill: #475569; font-size: 10px; paint-order: stroke; stroke: white; stroke-width: 3px; }}
    .node-circle {{ stroke: white; stroke-width: 1.8; cursor: pointer; }}
    .node-circle.dimmed {{ opacity: 0.15; }}
    .node-circle.active {{ stroke: #111827; stroke-width: 3; }}
    .node-label {{
      font-size: 11px;
      fill: #111827;
      paint-order: stroke;
      stroke: white;
      stroke-width: 4px;
      pointer-events: none;
    }}
    .node-label.dimmed {{ opacity: 0.18; }}
    .list-item {{
      padding: 7px;
      margin: 5px 0;
      border: 1px solid #e5e7eb;
      border-left: 4px solid #94a3b8;
      background: #fff;
      cursor: pointer;
      font-size: 12px;
    }}
    .list-item:hover {{ background: #f8fafc; }}
    .list-item.active {{ border-color: #111827; background: #eef2ff; }}
    pre {{
      white-space: pre-wrap;
      word-break: break-word;
      background: #f8fafc;
      border: 1px solid #e5e7eb;
      padding: 9px;
      font-size: 11px;
      max-height: 220px;
      overflow: auto;
    }}
    .section-title {{ margin: 16px 0 8px; font-size: 13px; font-weight: 700; }}
    .toolbar {{
      position: absolute;
      right: 14px;
      top: 14px;
      display: flex;
      gap: 8px;
      width: auto;
      z-index: 5;
    }}
    .toolbar button {{ width: auto; min-width: 74px; background: rgba(255,255,255,0.94); }}
  </style>
</head>
<body>
  <header>
    <div>
      <strong>{html.escape(title)}</strong>
      <div class="meta">{html.escape(subtitle)}</div>
      <div class="meta">Interactive Stage 3 evidence graph - click a node to inspect relationships</div>
    </div>
    <div class="meta" id="headerStats"></div>
  </header>
  <main>
    <aside>
      <label for="search">Search nodes / sources / edges</label>
      <input id="search" placeholder="Forward P/E, source, residual gap">
      <label for="nodeType">Node Type</label>
      <select id="nodeType"></select>
      <div class="row">
        <button id="reset">Reset</button>
        <button id="fit">Fit</button>
      </div>
      <div class="muted" style="margin-top:8px">Node-type dropdown, legend pills, and dashboard cards filter the graph visually. Filters show the selected node type plus one-hop context so relationships remain readable.</div>
      <div class="stat-grid" id="stats"></div>
      <div class="section-title">Legend</div>
      <div id="legend"></div>
      <div class="section-title">Visible Nodes</div>
      <div id="nodeList"></div>
    </aside>
    <section class="canvas-wrap">
      <div class="toolbar">
        <button id="labels">Labels</button>
        <button id="edges">Edges</button>
        <button id="physics">Physics</button>
      </div>
      <svg id="graphSvg" role="img" aria-label="Interactive evidence graph">
        <defs>
          <marker id="arrow" markerWidth="10" markerHeight="8" refX="9" refY="4" orient="auto">
            <path d="M0,0 L10,4 L0,8 z" fill="#94a3b8"></path>
          </marker>
          <marker id="arrowActive" markerWidth="10" markerHeight="8" refX="9" refY="4" orient="auto">
            <path d="M0,0 L10,4 L0,8 z" fill="#111827"></path>
          </marker>
        </defs>
        <g id="viewport">
          <g id="edgeLayer"></g>
          <g id="edgeLabelLayer"></g>
          <g id="nodeLayer"></g>
          <g id="nodeLabelLayer"></g>
        </g>
      </svg>
    </section>
    <section class="inspector">
      <div class="section-title">Inspector</div>
      <div id="inspector" class="muted">Select a node to inspect attributes, inbound/outbound edges, and connected sources.</div>
    </section>
  </main>
  <script>
    const graph = {data};
    const colors = {{
      packet: '#334155',
      manifest: '#64748b',
      source: '#059669',
      source_tier: '#0f766e',
      claim: '#7c3aed',
      claim_status: '#a855f7',
      evidence_class: '#2563eb',
      residual_gap: '#dc2626',
      reinforcement_task: '#ea580c',
      citation_rule: '#ca8a04',
      computed_metric: '#0891b2',
      metric_status: '#0e7490',
      formula: '#475569',
      metric_input: '#0284c7',
      user_technical_feature: '#16a34a',
      user_technical_mtf_read: '#15803d',
      final_report: '#1f2937',
      report_section: '#475569',
      horizon_decision: '#7c2d12',
      horizon_status: '#c2410c',
      horizon_evidence_statement: '#0369a1',
      horizon_blocking_factor: '#be123c',
      horizon_required_next_evidence: '#b45309',
      self_audit: '#4b5563',
      legal_notice: '#92400e',
      logo_attribution: '#0f766e'
    }};
    const radiusByType = {{
      claim: 11,
      source: 8,
      computed_metric: 12,
      residual_gap: 7,
      packet: 12,
      manifest: 10,
      reinforcement_task: 9,
      metric_input: 7,
      formula: 7,
      user_technical_feature: 9,
      user_technical_mtf_read: 11,
      final_report: 13,
      report_section: 9,
      horizon_decision: 12,
      legal_notice: 9,
      logo_attribution: 9
    }};
    const svg = document.getElementById('graphSvg');
    const viewport = document.getElementById('viewport');
    const edgeLayer = document.getElementById('edgeLayer');
    const edgeLabelLayer = document.getElementById('edgeLabelLayer');
    const nodeLayer = document.getElementById('nodeLayer');
    const nodeLabelLayer = document.getElementById('nodeLabelLayer');
    const inspector = document.getElementById('inspector');
    const nodeList = document.getElementById('nodeList');
    const nodeType = document.getElementById('nodeType');
    const search = document.getElementById('search');
    const nodes = graph.nodes.map((node, index) => ({{
      ...node,
      x: 250 + Math.cos(index * 2.399) * (90 + index * 2.7),
      y: 250 + Math.sin(index * 2.399) * (90 + index * 2.7),
      vx: 0,
      vy: 0
    }}));
    const byId = Object.fromEntries(nodes.map(n => [n.id, n]));
    const links = graph.links
      .filter(edge => byId[edge.source] && byId[edge.target])
      .map(edge => ({{
        ...edge,
        sourceNode: byId[edge.source],
        targetNode: byId[edge.target]
      }}));
    let selectedId = null;
    let showLabels = true;
    let showEdgeLabels = false;
    let physics = true;
    let tickCount = 0;
    const settleTicks = 180;
    let scale = 1;
    let panX = 0;
    let panY = 0;
    const typeValues = [...new Set(nodes.map(n => n.node_type))].sort();
    nodeType.innerHTML = '<option value="">All node types</option>' + typeValues.map(t => `<option>${{escapeHtml(t)}}</option>`).join('');
    document.getElementById('headerStats').textContent =
      `${{nodes.length}} nodes · ${{links.length}} edges · ${{graph.audit.source_count}} sources · ${{graph.audit.residual_gap_count}} residual gaps`;
    document.getElementById('stats').innerHTML = [
      ['Nodes', nodes.length, ''],
      ['Edges', links.length, '__edges__'],
      ['Sources', graph.audit.source_count, 'source'],
      ['Metrics', graph.audit.computed_metric_count || 0, 'computed_metric'],
      ['Residual Gaps', graph.audit.residual_gap_count, 'residual_gap'],
      ['Claims', Object.values(graph.audit.claim_status_counts || {{}}).reduce((a,b) => a + b, 0), 'claim']
    ].map(([label, value, type]) => `<div class="stat clickable" data-type="${{escapeHtml(type)}}"><b>${{value}}</b><span>${{label}}</span></div>`).join('');
    document.getElementById('legend').innerHTML = typeValues.map(type =>
      `<span class="pill filter-pill" data-type="${{escapeHtml(type)}}"><span class="swatch" style="background:${{color(type)}}"></span>${{escapeHtml(type)}}</span>`
    ).join('');

    let edgeEls = [];
    let edgeLabelEls = [];
    let nodeEls = [];
    let labelEls = [];

    function color(type) {{
      return colors[type] || '#475569';
    }}
    function radius(node) {{
      return radiusByType[node.node_type] || 6;
    }}
    function escapeHtml(value) {{
      return String(value ?? '').replace(/[&<>"']/g, ch => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}})[ch]);
    }}
    function nodeMatchesFilter(node) {{
      const q = search.value.trim().toLowerCase();
      const type = nodeType.value;
      const matchesType = !type || node.node_type === type;
      const matchesSearch = !q || JSON.stringify(node).toLowerCase().includes(q) ||
        links.some(edge => (edge.source === node.id || edge.target === node.id) && JSON.stringify(edge).toLowerCase().includes(q));
      return matchesType && matchesSearch;
    }}
    function coreVisibleNodes() {{
      return new Set(nodes.filter(nodeMatchesFilter).map(node => node.id));
    }}
    function visibleNodes() {{
      const core = coreVisibleNodes();
      if (!nodeType.value && !search.value.trim()) return core;
      const expanded = new Set(core);
      links.forEach(edge => {{
        if (core.has(edge.source)) expanded.add(edge.target);
        if (core.has(edge.target)) expanded.add(edge.source);
      }});
      return expanded;
    }}
    function visibleEdge(edge, visible, core) {{
      if (!visible.has(edge.source) || !visible.has(edge.target)) return false;
      if (!nodeType.value && !search.value.trim()) return true;
      return core.has(edge.source) || core.has(edge.target);
    }}
    function connectedIds(nodeId) {{
      const ids = new Set([nodeId]);
      links.forEach(edge => {{
        if (edge.source === nodeId) ids.add(edge.target);
        if (edge.target === nodeId) ids.add(edge.source);
      }});
      return ids;
    }}
    function activeLink(edge) {{
      return selectedId && (edge.source === selectedId || edge.target === selectedId);
    }}
    function draw() {{
      edgeLayer.innerHTML = '';
      edgeLabelLayer.innerHTML = '';
      nodeLayer.innerHTML = '';
      nodeLabelLayer.innerHTML = '';
      edgeEls = [];
      edgeLabelEls = [];
      nodeEls = [];
      labelEls = [];
      const visible = visibleNodes();
      const core = coreVisibleNodes();
      links.forEach((edge, index) => {{
        if (!visibleEdge(edge, visible, core)) return;
        const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
        line.dataset.index = index;
        line.classList.add('edge-line');
        line.setAttribute('marker-end', 'url(#arrow)');
        edgeLayer.appendChild(line);
        edgeEls.push(line);
        const label = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        label.dataset.index = index;
        label.classList.add('edge-label');
        label.textContent = edge.relation;
        label.style.display = showEdgeLabels ? 'block' : 'none';
        edgeLabelLayer.appendChild(label);
        edgeLabelEls.push(label);
      }});
      nodes.forEach(node => {{
        if (!visible.has(node.id)) return;
        const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
        circle.dataset.id = node.id;
        circle.classList.add('node-circle');
        if (!core.has(node.id)) circle.classList.add('dimmed');
        circle.setAttribute('r', radius(node));
        circle.setAttribute('fill', color(node.node_type));
        circle.addEventListener('click', event => {{
          event.stopPropagation();
          selectNode(node.id);
        }});
        circle.addEventListener('pointerdown', event => startDrag(event, node));
        nodeLayer.appendChild(circle);
        nodeEls.push(circle);
        const label = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        label.dataset.id = node.id;
        label.classList.add('node-label');
        if (!core.has(node.id)) label.classList.add('dimmed');
        label.textContent = shortLabel(node.label);
        label.style.display = showLabels ? 'block' : 'none';
        nodeLabelLayer.appendChild(label);
        labelEls.push(label);
      }});
      renderNodeList(visible);
      updatePositions();
      updateFocus();
    }}
    function updatePositions() {{
      edgeEls.forEach(el => {{
        const edge = links[Number(el.dataset.index)];
        el.setAttribute('x1', edge.sourceNode.x);
        el.setAttribute('y1', edge.sourceNode.y);
        el.setAttribute('x2', edge.targetNode.x);
        el.setAttribute('y2', edge.targetNode.y);
      }});
      edgeLabelEls.forEach(el => {{
        const edge = links[Number(el.dataset.index)];
        el.setAttribute('x', (edge.sourceNode.x + edge.targetNode.x) / 2);
        el.setAttribute('y', (edge.sourceNode.y + edge.targetNode.y) / 2);
      }});
      nodeEls.forEach(el => {{
        const node = byId[el.dataset.id];
        el.setAttribute('cx', node.x);
        el.setAttribute('cy', node.y);
      }});
      labelEls.forEach(el => {{
        const node = byId[el.dataset.id];
        el.setAttribute('x', node.x + radius(node) + 4);
        el.setAttribute('y', node.y + 4);
      }});
      viewport.setAttribute('transform', `translate(${{panX}} ${{panY}}) scale(${{scale}})`);
    }}
    function tick() {{
      if (physics) {{
        tickCount += 1;
        const center = graphCenter();
        nodes.forEach(node => {{
          node.vx += (center.x - node.x) * 0.0008;
          node.vy += (center.y - node.y) * 0.0008;
        }});
        for (let i = 0; i < nodes.length; i++) {{
          for (let j = i + 1; j < nodes.length; j++) {{
            const a = nodes[i], b = nodes[j];
            let dx = b.x - a.x, dy = b.y - a.y;
            let dist2 = dx * dx + dy * dy || 0.01;
            const force = Math.min(600 / dist2, 0.08);
            a.vx -= dx * force; a.vy -= dy * force;
            b.vx += dx * force; b.vy += dy * force;
          }}
        }}
        links.forEach(edge => {{
          const a = edge.sourceNode, b = edge.targetNode;
          const dx = b.x - a.x, dy = b.y - a.y;
          const dist = Math.sqrt(dx * dx + dy * dy) || 1;
          const desired = 105 + Math.min(edge.relation.length * 2, 70);
          const force = (dist - desired) * 0.0035;
          const fx = dx / dist * force, fy = dy / dist * force;
          a.vx += fx; a.vy += fy; b.vx -= fx; b.vy -= fy;
        }});
        nodes.forEach(node => {{
          if (node.fixed) return;
          node.vx *= 0.82; node.vy *= 0.82;
          node.x += node.vx; node.y += node.vy;
        }});
        if (tickCount >= settleTicks) {{
          physics = false;
          nodes.forEach(node => {{
            node.vx = 0;
            node.vy = 0;
          }});
        }}
      }}
      updatePositions();
      requestAnimationFrame(tick);
    }}
    function graphCenter() {{
      const rect = svg.getBoundingClientRect();
      return {{ x: (rect.width / 2 - panX) / scale, y: (rect.height / 2 - panY) / scale }};
    }}
    function shortLabel(label) {{
      return String(label).length > 34 ? String(label).slice(0, 31) + '...' : label;
    }}
    function selectNode(nodeId) {{
      selectedId = selectedId === nodeId ? null : nodeId;
      if (selectedId && byId[selectedId]) {{
        byId[selectedId].fixed = true;
        byId[selectedId].vx = 0;
        byId[selectedId].vy = 0;
      }}
      inspect();
      updateFocus();
      updateNodeListActive();
    }}
    function updateFocus() {{
      const connected = selectedId ? connectedIds(selectedId) : null;
      const core = coreVisibleNodes();
      nodeEls.forEach(el => {{
        const active = selectedId && el.dataset.id === selectedId;
        const dim = (connected && !connected.has(el.dataset.id)) || !core.has(el.dataset.id);
        el.classList.toggle('active', Boolean(active));
        el.classList.toggle('dimmed', Boolean(dim));
      }});
      labelEls.forEach(el => {{
        const dim = (connected && !connected.has(el.dataset.id)) || !core.has(el.dataset.id);
        el.classList.toggle('dimmed', Boolean(dim));
      }});
      edgeEls.forEach(el => {{
        const edge = links[Number(el.dataset.index)];
        const active = activeLink(edge);
        el.classList.toggle('active', Boolean(active));
        el.classList.toggle('dimmed', Boolean(selectedId && !active));
        el.setAttribute('marker-end', active ? 'url(#arrowActive)' : 'url(#arrow)');
      }});
      edgeLabelEls.forEach(el => {{
        const edge = links[Number(el.dataset.index)];
        el.style.display = (showEdgeLabels || activeLink(edge)) ? 'block' : 'none';
      }});
    }}
    function inspect() {{
      if (!selectedId) {{
        inspector.innerHTML = '<span class="muted">Select a node to inspect attributes, inbound/outbound edges, and connected sources.</span>';
        return;
      }}
      const node = byId[selectedId];
      const related = links.filter(edge => edge.source === selectedId || edge.target === selectedId);
      const linksHtml = urlLinks(node);
      inspector.innerHTML = `
        <div class="pill"><span class="swatch" style="background:${{color(node.node_type)}}"></span>${{escapeHtml(node.node_type)}}</div>
        <h2 style="font-size:17px;margin:10px 0 6px">${{escapeHtml(node.label)}}</h2>
        <div class="muted">${{escapeHtml(node.id)}}</div>
        ${{linksHtml ? `<div class="section-title">Source Links</div>${{linksHtml}}` : ''}}
        <div class="section-title">Attributes</div>
        <pre>${{escapeHtml(JSON.stringify(node.attributes || {{}}, null, 2))}}</pre>
        <div class="section-title">Relationships (${{related.length}})</div>
        ${{related.map(edge => {{
          const outward = edge.source === selectedId;
          const other = byId[outward ? edge.target : edge.source];
          return `<div class="list-item" style="border-left-color:${{color(other.node_type)}}"
            onclick="window.selectEvidenceNode('${{other.id}}')">
            <b>${{outward ? 'out' : 'in'}}: ${{escapeHtml(edge.relation)}}</b>
            <div>${{escapeHtml(other.label)}}</div>
            <div class="muted">${{escapeHtml(edge.confidence)}} · score ${{edge.confidence_score}}</div>
          </div>`;
        }}).join('') || '<div class="muted">No graph relationships found.</div>'}}
      `;
    }}
    function urlLinks(node) {{
      const attrs = node.attributes || {{}};
      const candidates = [];
      if (attrs.url && /^https?:\\/\\//i.test(attrs.url)) {{
        candidates.push({{ label: attrs.title || attrs.publisher || attrs.url, url: attrs.url }});
      }}
      if (node.source_file && /^https?:\\/\\//i.test(node.source_file)) {{
        candidates.push({{ label: 'source file', url: node.source_file }});
      }}
      return candidates.map(item =>
        `<div class="list-item" style="border-left-color:${{color(node.node_type)}}">` +
        `<a href="${{escapeHtml(item.url)}}" target="_blank" rel="noopener noreferrer">${{escapeHtml(item.label)}}</a>` +
        `<div class="muted">${{escapeHtml(item.url)}}</div></div>`
      ).join('');
    }}
    window.selectEvidenceNode = selectNode;
    function renderNodeList(visible) {{
      const candidates = nodes.filter(node => visible.has(node.id)).slice(0, 90);
      nodeList.innerHTML = candidates.map(node => `
        <div class="list-item ${{node.id === selectedId ? 'active' : ''}}" style="border-left-color:${{color(node.node_type)}}"
          onclick="window.selectEvidenceNode('${{node.id}}')">
          <b>${{escapeHtml(shortLabel(node.label))}}</b>
          <div class="muted">${{escapeHtml(node.node_type)}}</div>
        </div>
      `).join('');
    }}
    function updateNodeListActive() {{
      const visible = visibleNodes();
      renderNodeList(visible);
    }}
    function fitGraph(targetNodes = null) {{
      const rect = svg.getBoundingClientRect();
      const selectedNodes = targetNodes ? nodes.filter(n => targetNodes.has(n.id)) : nodes;
      const fitNodes = selectedNodes.length ? selectedNodes : nodes;
      const xs = fitNodes.map(n => n.x), ys = fitNodes.map(n => n.y);
      const minX = Math.min(...xs), maxX = Math.max(...xs), minY = Math.min(...ys), maxY = Math.max(...ys);
      const width = Math.max(maxX - minX, 1), height = Math.max(maxY - minY, 1);
      scale = Math.min(rect.width / (width + 180), rect.height / (height + 180), 1.25);
      panX = rect.width / 2 - (minX + width / 2) * scale;
      panY = rect.height / 2 - (minY + height / 2) * scale;
      updatePositions();
    }}
    function drawAndFit() {{
      selectedId = null;
      draw();
      fitGraph(visibleNodes());
      inspect();
      updateLegendState();
    }}
    function setNodeTypeFilter(type) {{
      if (type === '__edges__') {{
        showEdgeLabels = true;
        updateFocus();
        return;
      }}
      if (!type) search.value = '';
      nodeType.value = type || '';
      drawAndFit();
    }}
    function updateLegendState() {{
      document.querySelectorAll('.filter-pill').forEach(el => {{
        el.classList.toggle('active', el.dataset.type === nodeType.value);
      }});
    }}
    function resetGraph() {{
      selectedId = null;
      search.value = '';
      nodeType.value = '';
      scale = 1;
      panX = 0;
      panY = 0;
      tickCount = 0;
      physics = true;
      nodes.forEach(node => {{
        node.fixed = false;
        node.vx = 0;
        node.vy = 0;
      }});
      inspect();
      draw();
      updateLegendState();
      fitGraph();
    }}
    function startDrag(event, node) {{
      event.preventDefault();
      node.fixed = true;
      const start = point(event);
      const ox = node.x, oy = node.y;
      function move(moveEvent) {{
        const p = point(moveEvent);
        node.x = ox + (p.x - start.x) / scale;
        node.y = oy + (p.y - start.y) / scale;
        node.vx = 0; node.vy = 0;
        updatePositions();
      }}
      function up() {{
        window.removeEventListener('pointermove', move);
        window.removeEventListener('pointerup', up);
      }}
      window.addEventListener('pointermove', move);
      window.addEventListener('pointerup', up);
    }}
    function point(event) {{
      const rect = svg.getBoundingClientRect();
      return {{ x: event.clientX - rect.left, y: event.clientY - rect.top }};
    }}
    let panStart = null;
    svg.addEventListener('pointerdown', event => {{
      if (event.target.classList.contains('node-circle')) return;
      panStart = {{ x: event.clientX, y: event.clientY, panX, panY }};
    }});
    window.addEventListener('pointermove', event => {{
      if (!panStart) return;
      panX = panStart.panX + event.clientX - panStart.x;
      panY = panStart.panY + event.clientY - panStart.y;
      updatePositions();
    }});
    window.addEventListener('pointerup', () => panStart = null);
    svg.addEventListener('wheel', event => {{
      event.preventDefault();
      const before = point(event);
      const oldScale = scale;
      scale = Math.max(0.25, Math.min(3, scale * (event.deltaY < 0 ? 1.08 : 0.92)));
      panX = before.x - (before.x - panX) * (scale / oldScale);
      panY = before.y - (before.y - panY) * (scale / oldScale);
      updatePositions();
    }}, {{ passive: false }});
    svg.addEventListener('click', event => {{
      if (event.target === svg) selectNode(null);
    }});
    search.addEventListener('input', drawAndFit);
    nodeType.addEventListener('change', drawAndFit);
    document.querySelectorAll('.filter-pill').forEach(el => {{
      el.addEventListener('click', () => setNodeTypeFilter(el.dataset.type));
    }});
    document.querySelectorAll('.stat.clickable').forEach(el => {{
      el.addEventListener('click', () => setNodeTypeFilter(el.dataset.type));
    }});
    document.getElementById('reset').addEventListener('click', resetGraph);
    document.getElementById('fit').addEventListener('click', fitGraph);
    document.getElementById('labels').addEventListener('click', () => {{
      showLabels = !showLabels;
      labelEls.forEach(el => el.style.display = showLabels ? 'block' : 'none');
    }});
    document.getElementById('edges').addEventListener('click', () => {{
      showEdgeLabels = !showEdgeLabels;
      updateFocus();
    }});
    document.getElementById('physics').addEventListener('click', () => {{
      physics = !physics;
      if (physics) {{
        tickCount = 0;
        nodes.forEach(node => {{
          if (!node.fixed) {{
            node.vx = 0;
            node.vy = 0;
          }}
        }});
      }}
    }});
    draw();
    setTimeout(fitGraph, 650);
    requestAnimationFrame(tick);
  </script>
</body>
</html>
"""


def _top_degree_nodes(payload: dict[str, Any]) -> list[tuple[str, int]]:
    degree: Counter[str] = Counter()
    labels = {node["id"]: node["label"] for node in payload["nodes"]}
    for edge in payload["links"]:
        degree[edge["source"]] += 1
        degree[edge["target"]] += 1
    return [(labels.get(node_id, node_id), count) for node_id, count in degree.most_common(8)]


def _surprising_connections(payload: dict[str, Any]) -> list[str]:
    connections: list[str] = []
    labels = {node["id"]: node["label"] for node in payload["nodes"]}
    for edge in payload["links"]:
        if edge["relation"] in {"contradicted_by_source", "supported_by_proxy_source", "has_residual_gap"}:
            connections.append(
                f"{labels.get(edge['source'], edge['source'])} --{edge['relation']}--> {labels.get(edge['target'], edge['target'])}"
            )
    return connections[:10] or ["No cross-boundary relationships were identified beyond direct support links."]


def _suggested_questions(payload: dict[str, Any]) -> list[str]:
    return [
        "Which claims are supported by primary or official sources versus secondary market data?",
        "Which residual gaps block Titan-compliant horizon validation?",
        "How does the forward valuation contradiction affect the final trade stance?",
        "Which proxy evidence should be treated as indirect rather than issuer-specific validation?",
        "Which evidence nodes should feed the next Validated Trading Horizon gate?",
    ]


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _source_node_id(source_id: str) -> str:
    return f"source_{_slug(source_id)}"


def _task_node_id(task_id: str) -> str:
    return f"task_{_slug(task_id)}"


def _status_node_id(prefix: str, value: str) -> str:
    return f"{prefix}_{_slug(value)}"


def _slug(value: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "_" for ch in value).strip("_")


def _code_json(value: Any) -> str:
    return "```json\n" + json.dumps(value, indent=2, ensure_ascii=False) + "\n```"
