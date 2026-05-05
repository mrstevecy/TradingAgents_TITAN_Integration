"""Share package builder for graph artifacts."""

from __future__ import annotations

import json
import zipfile
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True)
class SharePackageManifest:
    package_name: str
    generated_at_utc: str
    source_dir: str
    files: list[str]
    instructions: list[str]


def build_graph_share_package(*, graph_dir: Path, package_path: Path | None = None) -> tuple[Path, Path]:
    required = ["graph.html", "graph.json", "GRAPH_REPORT.md"]
    missing = [name for name in required if not (graph_dir / name).exists()]
    if missing:
        raise FileNotFoundError(f"Missing required graph artifact(s): {', '.join(missing)}")

    if package_path is None:
        package_path = graph_dir / f"{graph_dir.name}_interactive_evidence_graph_share_package.zip"

    manifest = SharePackageManifest(
        package_name=package_path.name,
        generated_at_utc=datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        source_dir=str(graph_dir),
        files=required + ["README_SHARE.md"],
        instructions=[
            "Extract the ZIP to any local folder.",
            "Open graph.html in a modern browser.",
            "No Python, Graphify, project checkout, or local server is required.",
            "Internet access is needed only for opening external citation links.",
            "If corporate security blocks local HTML JavaScript, host the extracted folder on a trusted internal static site.",
        ],
    )
    readme = _readme(manifest)
    manifest_path = graph_dir / "share_manifest.json"
    readme_path = graph_dir / "README_SHARE.md"
    manifest_path.write_text(json.dumps(asdict(manifest), indent=2), encoding="utf-8")
    readme_path.write_text(readme, encoding="utf-8")

    with zipfile.ZipFile(package_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in required:
            archive.write(graph_dir / name, arcname=name)
        archive.write(readme_path, arcname="README_SHARE.md")
        archive.write(manifest_path, arcname="share_manifest.json")
    return package_path, manifest_path


def _readme(manifest: SharePackageManifest) -> str:
    lines = [
        "# Interactive Evidence Graph Share Package",
        "",
        f"Generated UTC: {manifest.generated_at_utc}",
        "",
        "## How to Open",
        "",
    ]
    lines.extend(f"{index}. {item}" for index, item in enumerate(manifest.instructions, start=1))
    lines.extend(["", "## Included Files", ""])
    lines.extend(f"- `{name}`" for name in manifest.files)
    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- `graph.html` is self-contained for visual inspection.",
            "- `graph.json` and `GRAPH_REPORT.md` are included for audit and traceability.",
            "- External citation links open from source nodes in the inspector.",
        ]
    )
    return "\n".join(lines) + "\n"
