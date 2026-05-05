"""Build Stage 5 v2 HTML preview only."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from titan_integration.report_preview_v2 import write_preview


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ticker", default="NVDA")
    parser.add_argument("--baseline-date", default="2026-05-01")
    parser.add_argument("--trade-date", default="2026-05-02")
    parser.add_argument("--run-id", default="NVDA_20260502T123138Z")
    parser.add_argument("--out-dir", type=Path)
    args = parser.parse_args()

    ticker = args.ticker.upper()
    out_dir = args.out_dir or ROOT / "research_packets" / "stage5_final_report" / args.run_id
    artifacts = write_preview(
        baseline_full_path=ROOT / "outputs" / "deepseek_full_baseline" / f"{ticker}_{args.baseline_date}_deepseek_full_baseline_summary.json",
        baseline_fresh_path=ROOT / "outputs" / "deepseek_fresh_baseline" / f"{ticker}_{args.trade_date}_deepseek_fresh_baseline_summary.json",
        stage1_path=ROOT / "research_packets" / "stage1" / f"{ticker}_{args.trade_date}_stage1_validation_packet.json",
        stage2_path=ROOT / "research_packets" / "stage2" / f"{ticker}_{args.trade_date}_stage2_citation_packet.json",
        stage2b_path=ROOT / "research_packets" / "stage2b" / f"{ticker}_{args.trade_date}_stage2b_reinforcement_packet.json",
        stage2c_path=ROOT / "research_packets" / "stage2c" / f"{ticker}_{args.trade_date}_stage2c_metric_reconciliation_packet.json",
        stage2d_path=ROOT / "research_packets" / "stage2d_stale_claim_refresh" / f"{ticker}_{args.trade_date}_stage2d_stale_claim_refresh_packet.json",
        stage1b_path=ROOT / "research_packets" / "stage1b_user_technical_features" / f"{ticker}_{args.trade_date}_stage1b_user_technical_features_packet.json",
        delta_path=ROOT / "research_packets" / "evidence_delta" / f"{ticker}_{args.trade_date}_evidence_delta_packet.json",
        stage4_path=ROOT / "research_packets" / "stage4_horizon_validation" / f"{args.run_id}_stage4_horizon_validation_packet.json",
        output_dir=out_dir,
    )
    print(f"HTML Preview: {artifacts.html_path}")
    print(f"Manifest: {artifacts.manifest_path}")
    print("Final Markdown/PDF generation paused pending user approval.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
