"""Export the approved Stage 5 v2 preview to final HTML, Markdown, and PDF."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from titan_integration.report_preview_v2 import write_preview
from titan_integration.logo_assets import resolve_logo_asset


class MarkdownExtractor(HTMLParser):
    """Small HTML-to-Markdown extractor for an audit-friendly text export."""

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.href_stack: list[str | None] = []
        self.current_href: str | None = None
        self.in_th = False
        self.in_td = False
        self.table_cell: list[str] = []
        self.table_row: list[str] = []
        self.table_rows: list[list[str]] = []
        self.in_table = False
        self.skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)
        if tag in {"style", "script"}:
            self.skip_depth += 1
            return
        if self.skip_depth:
            return
        if tag in {"h1", "h2", "h3", "h4"}:
            level = int(tag[1])
            self.parts.append("\n" + "#" * level + " ")
        elif tag == "p":
            self.parts.append("\n")
        elif tag == "br":
            self.parts.append("\n")
        elif tag == "li":
            self.parts.append("\n- ")
        elif tag == "strong":
            self.parts.append("**")
        elif tag == "em":
            self.parts.append("*")
        elif tag == "a":
            self.href_stack.append(self.current_href)
            self.current_href = attrs_dict.get("href")
        elif tag == "table":
            self.in_table = True
            self.table_rows = []
        elif tag == "tr":
            self.table_row = []
        elif tag in {"td", "th"}:
            self.in_td = tag == "td"
            self.in_th = tag == "th"
            self.table_cell = []

    def handle_endtag(self, tag: str) -> None:
        if tag in {"style", "script"} and self.skip_depth:
            self.skip_depth -= 1
            return
        if self.skip_depth:
            return
        if tag in {"h1", "h2", "h3", "h4", "p", "section", "div"}:
            self.parts.append("\n")
        elif tag in {"strong", "em"}:
            self.parts.append("**" if tag == "strong" else "*")
        elif tag == "a":
            if self.current_href:
                self.parts.append(f" ({self.current_href})")
            self.current_href = self.href_stack.pop() if self.href_stack else None
        elif tag in {"td", "th"}:
            text = _clean_text("".join(self.table_cell))
            self.table_row.append(text)
            self.in_td = False
            self.in_th = False
            self.table_cell = []
        elif tag == "tr":
            if self.table_row:
                self.table_rows.append(self.table_row)
        elif tag == "table":
            self.parts.append("\n" + _markdown_table(self.table_rows) + "\n")
            self.in_table = False
            self.table_rows = []

    def handle_data(self, data: str) -> None:
        if self.skip_depth:
            return
        if self.in_table and (self.in_td or self.in_th):
            self.table_cell.append(data)
        else:
            self.parts.append(data)

    def markdown(self) -> str:
        text = "".join(self.parts)
        text = re.sub(r"[ \t]+\n", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip() + "\n"


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().replace("|", "\\|")


def _markdown_table(rows: list[list[str]]) -> str:
    if not rows:
        return ""
    width = max(len(row) for row in rows)
    normalized = [row + [""] * (width - len(row)) for row in rows]
    header = normalized[0]
    sep = ["---"] * width
    body = normalized[1:]
    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join(sep) + " |",
    ]
    lines.extend("| " + " | ".join(row) + " |" for row in body)
    return "\n".join(lines)


def _html_to_markdown(html_text: str) -> str:
    parser = MarkdownExtractor()
    parser.feed(html_text)
    return parser.markdown()


def _render_pdf_with_playwright(html_path: Path, pdf_path: Path) -> None:
    url = f"file:///{html_path.as_posix()}"
    subprocess.run(
        [
            "npx",
            "--yes",
            "playwright",
            "pdf",
            "--channel",
            "msedge",
            url,
            str(pdf_path),
        ],
        cwd=ROOT,
        check=True,
    )
    if not pdf_path.exists() or pdf_path.stat().st_size == 0:
        raise RuntimeError(f"Playwright did not create a non-empty PDF: {pdf_path}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ticker", default="NVDA")
    parser.add_argument("--baseline-date", default="2026-05-01")
    parser.add_argument("--trade-date", default="2026-05-02")
    parser.add_argument("--run-id", default="NVDA_20260502T150558Z")
    parser.add_argument("--report-name", default=None)
    parser.add_argument("--official-website", default=None, help="Optional issuer official website used for logo discovery.")
    parser.add_argument("--no-logo-discovery", action="store_true", help="Disable official-website logo discovery and use local assets only.")
    args = parser.parse_args()

    ticker = args.ticker.upper()
    logo_resolution = resolve_logo_asset(
        ticker,
        official_website=args.official_website,
        allow_network=not args.no_logo_discovery,
    )
    out_dir = ROOT / "research_packets" / "stage5_final_report" / args.run_id
    stage2d_path = _first_existing(
        ROOT / "research_packets" / "stage2d_stale_claim_refresh" / f"{ticker}_{args.trade_date}_stage2d_stale_claim_refresh_packet.json",
        ROOT / "research_packets" / "stage2d" / f"{ticker}_{args.trade_date}_stage2d_stale_claim_refresh_packet.json",
    )
    baseline_fresh_path = ROOT / "outputs" / "deepseek_fresh_baseline" / f"{ticker}_{args.trade_date}_deepseek_fresh_baseline_summary.json"
    baseline_full_path = _first_existing(
        ROOT / "outputs" / "deepseek_full_baseline" / f"{ticker}_{args.baseline_date}_deepseek_full_baseline_summary.json",
        baseline_fresh_path,
    )
    preview = write_preview(
        baseline_full_path=baseline_full_path,
        baseline_fresh_path=baseline_fresh_path,
        stage1_path=ROOT / "research_packets" / "stage1" / f"{ticker}_{args.trade_date}_stage1_validation_packet.json",
        stage2_path=ROOT / "research_packets" / "stage2" / f"{ticker}_{args.trade_date}_stage2_citation_packet.json",
        stage2b_path=ROOT / "research_packets" / "stage2b" / f"{ticker}_{args.trade_date}_stage2b_reinforcement_packet.json",
        stage2c_path=ROOT / "research_packets" / "stage2c" / f"{ticker}_{args.trade_date}_stage2c_metric_reconciliation_packet.json",
        stage2d_path=stage2d_path,
        stage1b_path=ROOT / "research_packets" / "stage1b_user_technical_features" / f"{ticker}_{args.trade_date}_stage1b_user_technical_features_packet.json",
        delta_path=ROOT / "research_packets" / "evidence_delta" / f"{ticker}_{args.trade_date}_evidence_delta_packet.json",
        stage4_path=ROOT / "research_packets" / "stage4_horizon_validation" / f"{args.run_id}_stage4_horizon_validation_packet.json",
        output_dir=out_dir,
    )

    report_name = args.report_name or f"{args.run_id}_stage5_v2_final_report"
    final_html = out_dir / f"{report_name}.html"
    final_md = out_dir / f"{report_name}.md"
    final_pdf = out_dir / f"{report_name}.pdf"
    final_manifest = out_dir / f"{report_name}_manifest.json"

    shutil.copy2(preview.html_path, final_html)
    html_text = final_html.read_text(encoding="utf-8")
    html_text = html_text.replace(
        "Stage 5 v2 HTML Preview - final PDF paused pending review",
        "Stage 5 v2 Final Institutional Report",
    )
    html_text = html_text.replace(
        "Stage 5 v2 Institutional Preview",
        "Stage 5 v2 Institutional Final Report",
    )
    final_html.write_text(html_text, encoding="utf-8")
    final_md.write_text(_html_to_markdown(html_text), encoding="utf-8")
    _render_pdf_with_playwright(final_html, final_pdf)

    preview_manifest = json.loads(preview.manifest_path.read_text(encoding="utf-8"))
    manifest = {
        **preview_manifest,
        "stage": "Stage 5 v2 Final Report Export",
        "final_markdown_pdf_paused": False,
        "preview_path": str(preview.html_path),
        "final_html_path": str(final_html),
        "final_markdown_path": str(final_md),
        "final_pdf_path": str(final_pdf),
        "pdf_generated_from": "approved_stage5_v2_html",
        "baseline_preservation_rule": "Baseline text is rendered without rewriting; TITAN commentary is additive.",
        "logo_resolution": {
            "ticker": logo_resolution.ticker,
            "status": logo_resolution.status,
            "path": str(logo_resolution.path) if logo_resolution.path else None,
            "source_url": logo_resolution.source_url,
            "official_website": logo_resolution.official_website,
            "note": logo_resolution.note,
        },
    }
    final_manifest.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(f"Final HTML: {final_html}")
    print(f"Final Markdown: {final_md}")
    print(f"Final PDF: {final_pdf}")
    print(f"Final Manifest: {final_manifest}")
    print(f"Logo Resolution: {logo_resolution.status} ({logo_resolution.note})")
    return 0


def _first_existing(*paths: Path) -> Path:
    for path in paths:
        if path.exists():
            return path
    return paths[0]


if __name__ == "__main__":
    raise SystemExit(main())
