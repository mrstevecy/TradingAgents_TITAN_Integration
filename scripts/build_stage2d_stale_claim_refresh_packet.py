"""Build Stage 2D stale claim refresh packet."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from titan_integration.stale_claim_refresh import (
    build_stale_claim_refresh_packet,
    write_stale_claim_refresh_packet,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--delta",
        type=Path,
        default=ROOT / "research_packets" / "evidence_delta" / "NVDA_2026-05-02_evidence_delta_packet.json",
    )
    parser.add_argument(
        "--prior-graph",
        type=Path,
        default=ROOT / "research_packets" / "stage3_graphify" / "NVDA_2026-05-01" / "graph.json",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=ROOT / "research_packets" / "stage2d_stale_claim_refresh",
    )
    parser.add_argument("--no-url-check", action="store_true")
    args = parser.parse_args()

    packet = build_stale_claim_refresh_packet(
        delta_packet_path=args.delta,
        prior_graph_path=args.prior_graph,
        check_urls=not args.no_url_check,
    )
    json_path, md_path = write_stale_claim_refresh_packet(packet, args.out_dir)
    print(f"JSON: {json_path}")
    print(f"Markdown: {md_path}")
    print(f"Compliance: {packet.compliance_status}")
    print(f"Status counts: {packet.status_counts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
