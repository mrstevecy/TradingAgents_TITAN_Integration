"""Build Titan Validation Packet Stage 2C computable metric reconciliation."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from titan_integration.metric_reconciliation import build_stage2c_packet, write_stage2c_packet


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
        "--stage2b",
        type=Path,
        default=ROOT
        / "research_packets"
        / "stage2b"
        / "NVDA_2026-05-01_stage2b_reinforcement_packet.json",
    )
    parser.add_argument(
        "--baseline-summary",
        type=Path,
        default=ROOT
        / "outputs"
        / "deepseek_full_baseline"
        / "NVDA_2026-05-01_deepseek_full_baseline_summary.json",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=ROOT / "research_packets" / "stage2c",
    )
    args = parser.parse_args()

    packet = build_stage2c_packet(
        stage1_packet_path=args.stage1,
        stage2b_packet_path=args.stage2b,
        baseline_summary_path=args.baseline_summary,
    )
    json_path, md_path = write_stage2c_packet(packet, args.out_dir)
    print(f"JSON: {json_path}")
    print(f"Markdown: {md_path}")
    print(f"Compliance: {packet.compliance_status}")
    print(f"Status counts: {packet.status_counts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
