"""Build a Titan Validation Packet Stage 1 artifact."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from titan_integration.validation_packet import build_stage1_packet, write_packet


def main() -> int:
    _load_env_file(ROOT / "TradingAgents" / ".env")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--summary",
        type=Path,
        default=ROOT
        / "outputs"
        / "deepseek_full_baseline"
        / "NVDA_2026-05-01_deepseek_full_baseline_summary.json",
        help="TradingAgents summary JSON path.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=ROOT / "research_packets" / "stage1",
        help="Output directory for JSON and Markdown packets.",
    )
    parser.add_argument(
        "--input-root",
        type=Path,
        default=ROOT / "inputs",
        help="Root directory for Stage 1A user-supplied evidence.",
    )
    args = parser.parse_args()

    packet = build_stage1_packet(
        tradingagents_summary_path=args.summary,
        input_root=args.input_root,
    )
    json_path, md_path = write_packet(packet, args.out_dir)
    print(f"JSON: {json_path}")
    print(f"Markdown: {md_path}")
    print(f"Status: {packet.preliminary_validation_status['overall']}")
    return 0


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key.strip(), value)


if __name__ == "__main__":
    raise SystemExit(main())
