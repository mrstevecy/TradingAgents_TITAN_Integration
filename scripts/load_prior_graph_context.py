"""Load prior graph-backed research context for a ticker."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from titan_integration.prior_graph_context import (
    build_prior_graph_context,
    write_prior_graph_context,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ticker", default="NVDA")
    parser.add_argument("--as-of-date", default="2026-05-02")
    parser.add_argument(
        "--graph-root",
        type=Path,
        default=ROOT / "research_packets" / "stage3_graphify",
    )
    parser.add_argument(
        "--include-same-date",
        action="store_true",
        help="Include graphs with the same research date as --as-of-date.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=ROOT / "research_packets" / "prior_context",
    )
    args = parser.parse_args()

    packet = build_prior_graph_context(
        ticker=args.ticker,
        as_of_date=args.as_of_date,
        graph_root=args.graph_root,
        include_same_date=args.include_same_date,
    )
    json_path, md_path = write_prior_graph_context(packet, args.out_dir)
    print(f"JSON: {json_path}")
    print(f"Markdown: {md_path}")
    print(f"Context status: {packet.context_status}")
    print(f"Prior graphs: {len(packet.prior_graphs)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
