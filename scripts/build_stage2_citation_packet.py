"""Build a Titan Validation Packet Stage 2 citation evidence artifact."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from titan_integration.citation_retrieval import build_stage2_packet, write_stage2_packet


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--stage1",
        type=Path,
        default=ROOT
        / "research_packets"
        / "stage1"
        / "NVDA_2026-05-01_stage1_validation_packet.json",
        help="Stage 1 packet JSON path.",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=ROOT
        / "citation_manifests"
        / "nvda_2026-05-01_stage2_sources.json",
        help="Citation manifest JSON path.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=ROOT / "research_packets" / "stage2",
        help="Output directory for Stage 2 JSON and Markdown packets.",
    )
    args = parser.parse_args()

    packet = build_stage2_packet(stage1_packet_path=args.stage1, manifest_path=args.manifest)
    json_path, md_path = write_stage2_packet(packet, args.out_dir)
    print(f"JSON: {json_path}")
    print(f"Markdown: {md_path}")
    print(f"Compliance: {packet.compliance_status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

