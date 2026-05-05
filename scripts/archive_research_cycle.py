"""Archive a research cycle into a run-id-specific directory."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--delta", type=Path, default=None)
    parser.add_argument("--summary", type=Path, default=None)
    parser.add_argument("--stage4", type=Path, default=None)
    parser.add_argument(
        "--out-root",
        type=Path,
        default=ROOT / "research_cycles",
    )
    args = parser.parse_args()

    graph = _read_json(args.graph)
    cycle = graph.get("research_cycle", {})
    run_id = cycle.get("research_run_id")
    if not run_id:
        raise SystemExit("Graph does not contain research_cycle.research_run_id")

    out_dir = args.out_root / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    artifacts: list[dict[str, str]] = []

    for node in graph.get("nodes", []):
        source_file = node.get("source_file")
        if source_file and source_file.endswith(".json") and "/research_packets/" in source_file:
            host_path = _container_to_host_path(source_file)
            _copy_artifact(host_path, out_dir, artifacts)

    graph_dir = args.graph.parent
    for name in ["graph.json", "GRAPH_REPORT.md", "graph.html", "README_SHARE.md", "share_manifest.json"]:
        _copy_artifact(graph_dir / name, out_dir / "stage3_graphify", artifacts)
    for zip_path in graph_dir.glob("*interactive_evidence_graph_share_package.zip"):
        _copy_artifact(zip_path, out_dir / "stage3_graphify", artifacts)

    if args.delta:
        _copy_artifact(args.delta, out_dir / "evidence_delta", artifacts)
        md_delta = args.delta.with_suffix(".md")
        _copy_artifact(md_delta, out_dir / "evidence_delta", artifacts)
    if args.summary:
        _copy_artifact(args.summary, out_dir / "tradingagents_baseline", artifacts)
        md_summary = args.summary.with_suffix(".md")
        _copy_artifact(md_summary, out_dir / "tradingagents_baseline", artifacts)
    if args.stage4:
        _copy_artifact(args.stage4, out_dir / "stage4_horizon_validation", artifacts)
        md_stage4 = args.stage4.with_suffix(".md")
        _copy_artifact(md_stage4, out_dir / "stage4_horizon_validation", artifacts)

    manifest = {
        "research_cycle": cycle,
        "source_graph": str(args.graph),
        "artifact_count": len(artifacts),
        "artifacts": artifacts,
    }
    manifest_path = out_dir / "research_cycle_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    readme_path = out_dir / "README.md"
    readme_path.write_text(_readme(manifest), encoding="utf-8")

    print(f"Archive: {out_dir}")
    print(f"Manifest: {manifest_path}")
    print(f"Artifacts: {len(artifacts)}")
    return 0


def _copy_artifact(path: Path, out_dir: Path, artifacts: list[dict[str, str]]) -> None:
    if not path.exists() or not path.is_file():
        return
    out_dir.mkdir(parents=True, exist_ok=True)
    dest = out_dir / path.name
    shutil.copy2(path, dest)
    artifacts.append({"source": str(path), "archive_path": str(dest)})


def _container_to_host_path(path: str) -> Path:
    if path.startswith("/workspace/"):
        return ROOT / path.removeprefix("/workspace/")
    return Path(path)


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _readme(manifest: dict) -> str:
    cycle = manifest["research_cycle"]
    lines = [
        f"# Research Cycle Archive: {cycle.get('research_run_id')}",
        "",
        f"- Ticker: {cycle.get('ticker')}",
        f"- Research generated UTC: {cycle.get('research_generated_at_utc')}",
        f"- Research generated local: {cycle.get('research_generated_at_local')}",
        f"- Requested analysis date: {cycle.get('requested_analysis_date')}",
        f"- Market data as of: {cycle.get('market_data_as_of')}",
        f"- Session context: {cycle.get('session_context')}",
        "",
        "## Artifacts",
        "",
    ]
    lines.extend(f"- `{item['archive_path']}`" for item in manifest["artifacts"])
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
