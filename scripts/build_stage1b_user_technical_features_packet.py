"""Build Stage 1B user technical feature packet."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from titan_integration.user_technical_features import (
    build_user_technical_feature_packet,
    write_user_technical_feature_packet,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ticker", default="NVDA")
    parser.add_argument("--trade-date", default="2026-05-02")
    parser.add_argument("--input-root", type=Path, default=ROOT / "inputs")
    parser.add_argument(
        "--registry",
        type=Path,
        default=ROOT / "normalized_data" / "user_evidence_registry.json",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=ROOT / "research_packets" / "stage1b_user_technical_features",
    )
    args = parser.parse_args()

    packet = build_user_technical_feature_packet(
        ticker=args.ticker,
        trade_date=args.trade_date,
        input_root=args.input_root,
        registry_path=args.registry,
    )
    json_path, md_path = write_user_technical_feature_packet(packet, args.out_dir)
    print(f"JSON: {json_path}")
    print(f"Markdown: {md_path}")
    print(f"Status: {packet.status}")
    print(f"Feature summaries: {len(packet.feature_summaries)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
