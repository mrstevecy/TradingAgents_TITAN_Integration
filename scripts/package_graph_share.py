"""Create a single shareable ZIP package for an interactive graph."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from titan_integration.share_package import build_graph_share_package


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--graph-dir",
        type=Path,
        default=ROOT / "research_packets" / "stage3_graphify" / "NVDA_2026-05-01",
    )
    parser.add_argument("--package-path", type=Path, default=None)
    args = parser.parse_args()

    package_path, manifest_path = build_graph_share_package(
        graph_dir=args.graph_dir, package_path=args.package_path
    )
    print(f"Package: {package_path}")
    print(f"Manifest: {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
