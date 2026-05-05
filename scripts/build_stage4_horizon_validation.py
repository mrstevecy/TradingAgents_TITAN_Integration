"""Build Titan Validation Packet Stage 4 horizon validation."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from titan_integration.horizon_validation import (
    build_horizon_validation_packet,
    write_horizon_validation_packet,
)


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
        default=ROOT / "research_packets" / "stage3_graphify" / "NVDA_2026-05-02" / "graph.json",
    )
    parser.add_argument(
        "--delta",
        type=Path,
        default=ROOT / "research_packets" / "evidence_delta" / "NVDA_2026-05-02_evidence_delta_packet.json",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=ROOT / "research_packets" / "stage4_horizon_validation",
    )
    args = parser.parse_args()

    packet = build_horizon_validation_packet(
        prior_graph_path=args.prior_graph,
        fresh_graph_path=args.fresh_graph,
        delta_packet_path=args.delta,
    )
    json_path, md_path = write_horizon_validation_packet(packet, args.out_dir)
    print(f"JSON: {json_path}")
    print(f"Markdown: {md_path}")
    print(f"Compliance: {packet.compliance_status}")
    print(f"Validated Trading Horizon: {packet.validated_trading_horizon}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
