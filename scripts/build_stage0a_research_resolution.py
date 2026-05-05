"""Build Stage 0A universal research request resolution packet."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from titan_integration.universal_research import (
    request_from_mapping,
    resolve_research_request,
    write_resolution_packet,
)
from titan_integration.input_discovery import resolve_latest_input_folder


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, help="JSON file containing the universal research request.")
    parser.add_argument("--asset", default="NVIDIA Corporation")
    parser.add_argument("--ticker", default="NVDA")
    parser.add_argument("--full-name", default="NVIDIA Corporation")
    parser.add_argument("--instrument-type", default="Equity")
    parser.add_argument("--asset-class", default="Equity")
    parser.add_argument("--primary-strategy", default="Long/Short/Hold")
    parser.add_argument("--trading-horizon", default="Intraday/Swing/Positional/Long-Term")
    parser.add_argument("--execution-platform", default="TradingView")
    parser.add_argument("--analysis-date", default="2026-05-02")
    parser.add_argument("--input-root", type=Path, default=ROOT / "inputs")
    parser.add_argument("--input-folder", type=Path, default=None)
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=ROOT / "research_packets" / "stage0a_research_resolution",
    )
    args = parser.parse_args()

    if args.request:
        payload = json.loads(args.request.read_text(encoding="utf-8"))
    else:
        input_resolution = resolve_latest_input_folder(
            input_root=args.input_root,
            ticker=args.ticker,
            analysis_date=args.analysis_date,
            requested_input_folder=args.input_folder,
        )
        payload = {
            "asset": args.asset,
            "ticker": args.ticker,
            "full_name": args.full_name,
            "instrument_type": args.instrument_type,
            "asset_class": args.asset_class,
            "primary_strategy": args.primary_strategy,
            "trading_horizon": args.trading_horizon,
            "execution_platform": args.execution_platform,
            "analysis_date": args.analysis_date,
            "input_folder": input_resolution.selected_input_folder,
            "input_folder_resolution": input_resolution.to_dict(),
        }

    packet = resolve_research_request(request_from_mapping(payload))
    json_path, md_path = write_resolution_packet(packet, args.out_dir)
    print(f"JSON: {json_path}")
    print(f"Markdown: {md_path}")
    print(f"Registry Status: {packet.registry_status}")
    print(f"Active Research Profile: {packet.active_research_profile}")
    print(f"Next Action: {packet.next_action}")
    resolution = packet.request.get("input_folder_resolution")
    if resolution:
        print(f"Selected Input Folder: {resolution.get('selected_input_folder')}")
        if resolution.get("warning"):
            print(f"Input Folder Warning: {resolution.get('warning')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
