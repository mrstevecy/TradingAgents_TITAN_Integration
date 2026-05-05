"""Build an evidence delta packet between prior and fresh graph-backed research."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from titan_integration.evidence_delta import build_evidence_delta_packet, write_evidence_delta_packet


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--prior-graph",
        type=Path,
        default=ROOT / "research_packets" / "stage3_graphify" / "NVDA_2026-05-01" / "graph.json",
    )
    parser.add_argument(
        "--fresh-graph",
        type=Path,
        default=ROOT / "research_packets" / "stage3_graphify" / "NVDA_2026-05-01" / "graph.json",
    )
    parser.add_argument("--fresh-research-date", default=None)
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=ROOT / "research_packets" / "evidence_delta",
    )
    args = parser.parse_args()

    packet = build_evidence_delta_packet(
        prior_graph_path=args.prior_graph,
        fresh_graph_path=args.fresh_graph,
        fresh_research_date=args.fresh_research_date,
    )
    json_path, md_path = write_evidence_delta_packet(packet, args.out_dir)
    print(f"JSON: {json_path}")
    print(f"Markdown: {md_path}")
    print(f"Compliance: {packet.compliance_status}")
    print(f"Delta counts: {packet.delta_counts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
