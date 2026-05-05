"""Build a Titan Validation Packet Stage 2B evidence reinforcement artifact."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from titan_integration.evidence_reinforcement import (
    build_stage2b_packet,
    write_stage2b_packet,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--stage2",
        type=Path,
        default=ROOT
        / "research_packets"
        / "stage2"
        / "NVDA_2026-05-01_stage2_citation_packet.json",
        help="Stage 2 packet JSON path.",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=ROOT
        / "citation_manifests"
        / "nvda_2026-05-01_stage2b_reinforcement.json",
        help="Stage 2B reinforcement manifest JSON path.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=ROOT / "research_packets" / "stage2b",
        help="Output directory for Stage 2B JSON and Markdown packets.",
    )
    args = parser.parse_args()

    packet = build_stage2b_packet(stage2_packet_path=args.stage2, manifest_path=args.manifest)
    json_path, md_path = write_stage2b_packet(packet, args.out_dir)
    print(f"JSON: {json_path}")
    print(f"Markdown: {md_path}")
    print(f"Compliance: {packet.compliance_status}")
    print(f"Status counts: {packet.status_counts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

