"""Build a Stage 5 evidence-gated final Markdown and PDF report."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from titan_integration.report_exporter import export_final_report


def default_paths(repo_root: Path, ticker: str, trade_date: str, baseline_date: str, run_id: str) -> dict[str, Path]:
    return {
        "baseline_path": repo_root / "outputs" / "deepseek_full_baseline" / f"{ticker}_{baseline_date}_deepseek_full_baseline_summary.json",
        "stage1_path": repo_root / "research_packets" / "stage1" / f"{ticker}_{trade_date}_stage1_validation_packet.json",
        "stage1b_path": repo_root / "research_packets" / "stage1b_user_technical_features" / f"{ticker}_{trade_date}_stage1b_user_technical_features_packet.json",
        "stage2c_path": repo_root / "research_packets" / "stage2c" / f"{ticker}_{trade_date}_stage2c_metric_reconciliation_packet.json",
        "stage2d_path": repo_root / "research_packets" / "stage2d_stale_claim_refresh" / f"{ticker}_{trade_date}_stage2d_stale_claim_refresh_packet.json",
        "graph_report_path": repo_root / "research_packets" / "stage3_graphify" / f"{ticker}_{trade_date}" / "GRAPH_REPORT.md",
        "delta_path": repo_root / "research_packets" / "evidence_delta" / f"{ticker}_{trade_date}_evidence_delta_packet.json",
        "stage4_path": repo_root / "research_packets" / "stage4_horizon_validation" / f"{run_id}_stage4_horizon_validation_packet.json",
        "output_dir": repo_root / "research_packets" / "stage5_final_report" / run_id,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ticker", default="NVDA")
    parser.add_argument("--trade-date", default="2026-05-02")
    parser.add_argument("--baseline-date", default="2026-05-01")
    parser.add_argument("--run-id", default="NVDA_20260502T123138Z")
    parser.add_argument("--report-name", default=None)
    parser.add_argument("--repo-root", default=Path.cwd(), type=Path)
    parser.add_argument("--baseline-path", type=Path)
    parser.add_argument("--stage1-path", type=Path)
    parser.add_argument("--stage1b-path", type=Path)
    parser.add_argument("--stage2c-path", type=Path)
    parser.add_argument("--stage2d-path", type=Path)
    parser.add_argument("--graph-report-path", type=Path)
    parser.add_argument("--delta-path", type=Path)
    parser.add_argument("--stage4-path", type=Path)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    paths = default_paths(repo_root, args.ticker, args.trade_date, args.baseline_date, args.run_id)
    for key in list(paths):
        override = getattr(args, key, None)
        if override is not None:
            paths[key] = override

    missing = [str(path) for key, path in paths.items() if key != "output_dir" and not path.exists()]
    if missing:
        raise FileNotFoundError("Missing Stage 5 input artifact(s):\n" + "\n".join(missing))

    artifacts = export_final_report(
        baseline_path=paths["baseline_path"],
        stage1_path=paths["stage1_path"],
        stage1b_path=paths["stage1b_path"],
        stage2c_path=paths["stage2c_path"],
        stage2d_path=paths["stage2d_path"],
        graph_report_path=paths["graph_report_path"],
        delta_path=paths["delta_path"],
        stage4_path=paths["stage4_path"],
        output_dir=paths["output_dir"],
        report_name=args.report_name,
    )
    print(f"Markdown: {artifacts.markdown_path}")
    print(f"PDF: {artifacts.pdf_path}")
    print(f"Manifest: {artifacts.manifest_path}")


if __name__ == "__main__":
    main()
