"""Build Titan Validation Packet Stage 3 Graphify-compatible evidence graph."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from titan_integration.evidence_graph import build_evidence_graph, write_evidence_graph


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--stage1",
        type=Path,
        default=ROOT
        / "research_packets"
        / "stage1"
        / "NVDA_2026-05-01_stage1_validation_packet.json",
    )
    parser.add_argument(
        "--stage2",
        type=Path,
        default=ROOT
        / "research_packets"
        / "stage2"
        / "NVDA_2026-05-01_stage2_citation_packet.json",
    )
    parser.add_argument(
        "--stage2b",
        type=Path,
        default=ROOT
        / "research_packets"
        / "stage2b"
        / "NVDA_2026-05-01_stage2b_reinforcement_packet.json",
    )
    parser.add_argument(
        "--stage2c",
        type=Path,
        default=ROOT
        / "research_packets"
        / "stage2c"
        / "NVDA_2026-05-01_stage2c_metric_reconciliation_packet.json",
    )
    parser.add_argument(
        "--stage2d",
        type=Path,
        default=ROOT
        / "research_packets"
        / "stage2d_stale_claim_refresh"
        / "NVDA_2026-05-02_stage2d_stale_claim_refresh_packet.json",
    )
    parser.add_argument(
        "--stage4",
        type=Path,
        default=ROOT
        / "research_packets"
        / "stage4_horizon_validation"
        / "NVDA_20260502T150558Z_stage4_horizon_validation_packet.json",
    )
    parser.add_argument(
        "--stage5-manifest",
        type=Path,
        default=ROOT
        / "research_packets"
        / "stage5_final_report"
        / "NVDA_20260502T150558Z"
        / "NVDA_20260502T150558Z_stage5_v2_final_report_manifest.json",
    )
    parser.add_argument(
        "--citation-manifest",
        type=Path,
        default=ROOT / "citation_manifests" / "nvda_2026-05-01_stage2_sources.json",
    )
    parser.add_argument(
        "--reinforcement-manifest",
        type=Path,
        default=ROOT / "citation_manifests" / "nvda_2026-05-01_stage2b_reinforcement.json",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=ROOT / "research_packets" / "stage3_graphify" / "NVDA_2026-05-01",
    )
    args = parser.parse_args()

    graph = build_evidence_graph(
        stage1_packet_path=args.stage1,
        stage2_packet_path=args.stage2,
        stage2b_packet_path=args.stage2b,
        stage2c_packet_path=args.stage2c,
        stage2d_packet_path=args.stage2d,
        stage4_packet_path=args.stage4,
        stage5_manifest_path=args.stage5_manifest,
        citation_manifest_path=args.citation_manifest,
        reinforcement_manifest_path=args.reinforcement_manifest,
    )
    graph_json, graph_report, graph_html = write_evidence_graph(graph, args.out_dir)
    print(f"Graph JSON: {graph_json}")
    print(f"Graph report: {graph_report}")
    print(f"Graph HTML: {graph_html}")
    print(f"Nodes: {len(graph.nodes)}")
    print(f"Edges: {len(graph.links)}")
    print(f"Compliance: {graph.compliance_status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
