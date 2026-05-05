"""Stage 5 evidence-gated final report exporter."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .report_quality import FINAL_REPORT_STAGE, section_titles


@dataclass(frozen=True)
class ReportArtifacts:
    markdown_path: Path
    pdf_path: Path
    manifest_path: Path


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _money(value: Any) -> str:
    if value is None:
        return "N/A"
    try:
        return f"${float(value):,.2f}"
    except (TypeError, ValueError):
        return str(value)


def _num(value: Any, digits: int = 2) -> str:
    if value is None:
        return "N/A"
    try:
        return f"{float(value):,.{digits}f}"
    except (TypeError, ValueError):
        return str(value)


def _pct(value: Any, digits: int = 2) -> str:
    if value is None:
        return "N/A"
    try:
        return f"{float(value):,.{digits}f}%"
    except (TypeError, ValueError):
        return str(value)


def _md_table(headers: list[str], rows: list[list[Any]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        cleaned = [str(cell).replace("\n", " ").replace("|", "/") for cell in row]
        lines.append("| " + " | ".join(cleaned) + " |")
    return "\n".join(lines)


def _first_metric(stage2c: dict[str, Any]) -> dict[str, Any]:
    metrics = stage2c.get("reconciled_metrics") or []
    return metrics[0] if metrics else {}


def _claim_by_label(stage1: dict[str, Any], label: str) -> dict[str, Any] | None:
    for claim in stage1.get("claim_evidence_map", []):
        if claim.get("claim") == label:
            return claim
    return None


def _extract_graph_counts(graph_report_text: str) -> dict[str, str]:
    counts: dict[str, str] = {}
    for key in ["Nodes", "Edges", "Sources", "Residual gaps"]:
        match = re.search(rf"- {re.escape(key)}: ([^\n]+)", graph_report_text)
        if match:
            counts[key] = match.group(1).strip()
    return counts


def _clean_markdown_for_pdf(text: str) -> str:
    return (
        text.replace("->", "to")
        .replace("—", "-")
        .replace("–", "-")
        .replace("’", "'")
        .replace("“", '"')
        .replace("”", '"')
        .replace("**", "")
        .replace("`", "")
    )


def build_final_markdown(
    *,
    baseline: dict[str, Any],
    stage1: dict[str, Any],
    stage1b: dict[str, Any],
    stage2c: dict[str, Any],
    stage2d: dict[str, Any],
    graph_report_text: str,
    delta: dict[str, Any],
    stage4: dict[str, Any],
) -> str:
    ticker = stage1.get("ticker", "UNKNOWN")
    cycle = stage4.get("research_cycle") or stage1.get("research_cycle") or {}
    price = stage1.get("price_data_audit", {})
    latest_bar = price.get("latest_bar", {})
    metrics = price.get("computed_metrics", {})
    sec = stage1.get("sec_fundamentals_audit", {})
    user_summary = stage1.get("user_supplied_evidence_audit", {}).get("summary", {})
    mft = stage1b.get("multi_timeframe_read", {})
    metric = _first_metric(stage2c)
    usable_range = metric.get("usable_range", {})
    reported_values = metric.get("reported_values", {})
    issuer_guidance_eps = reported_values.get("computed_using_issuer_guidance_derived_annualized_eps")
    graph_counts = _extract_graph_counts(graph_report_text)

    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    report_title = f"{ticker} Titan Evidence-Gated Final Research Report"

    metadata_rows = [
        ["Ticker", ticker],
        ["Report Stage", FINAL_REPORT_STAGE],
        ["Generated UTC", generated_at],
        ["Research Run ID", cycle.get("research_run_id", "N/A")],
        ["Research Generated Local", cycle.get("research_generated_at_local", "N/A")],
        ["Requested Analysis Date", cycle.get("requested_analysis_date", stage1.get("trade_date", "N/A"))],
        ["Market Data As Of", cycle.get("market_data_as_of", "N/A")],
        ["Market Data Granularity", cycle.get("market_data_granularity", "N/A")],
        ["User Evidence Latest Timestamp", cycle.get("user_evidence_latest_timestamp", user_summary.get("latest_user_evidence_timestamp", "N/A"))],
        ["Session Context", cycle.get("session_context", "N/A")],
        ["Compliance Status", stage4.get("compliance_status", "N/A")],
    ]

    decision_rows = [
        ["Baseline Decision", "TradingAgents baseline", baseline.get("processed_decision", "N/A")],
        ["Fresh TradingAgents Decision", "2026-05-02 DeepSeek fresh run", stage1.get("tradingagents_final_stance", "N/A")],
        ["Stance Delta", "Evidence delta / Stage 4", stage4.get("stance_delta", "N/A")],
        ["Validated Trading Horizon", "Stage 4", stage4.get("validated_trading_horizon", "N/A")],
        ["Final Report Posture", "Stage 5 synthesis", "Defensive / Underweight bias; conditional monitoring only until unresolved valuation and live-market evidence are addressed."],
    ]

    technical_rows = [
        ["Latest Close", _money(latest_bar.get("close")), "yfinance daily bar"],
        ["Latest Volume", _num(latest_bar.get("volume"), 0), "yfinance daily bar"],
        ["10 EMA", _money(metrics.get("ema_10")), "Short-term trend"],
        ["50 SMA", _money(metrics.get("sma_50")), "Medium-term support"],
        ["200 SMA", _money(metrics.get("sma_200")), "Long-term structure"],
        ["20 VWMA", _money(metrics.get("vwma_20")), "Volume-weighted trend"],
        ["20D Avg Volume", _num(metrics.get("avg_20_volume"), 0), "Liquidity context"],
        ["Recent Swing Move", _pct(metrics.get("recent_swing_move_pct")), "Recent swing magnitude"],
    ]

    user_rows = []
    for item in stage1b.get("feature_summaries", []):
        user_rows.append(
            [
                item.get("detected_timeframe", "N/A"),
                item.get("latest_timestamp", "N/A"),
                _money(item.get("latest_close")),
                item.get("vwap_position", "N/A"),
                item.get("rsi_regime", "N/A"),
                item.get("adx_regime", "N/A"),
                item.get("volume_regime", "N/A"),
            ]
        )

    valuation_rows = [
        ["TradingAgents reported Forward P/E", _num(reported_values.get("tradingagents_reported_forward_pe")), metric.get("specific_claim_status", "Blocked"), "Specific point estimate remains blocked because the fresh run did not expose the EPS input."],
        ["StockAnalysis reported Forward P/E", _num(reported_values.get("stockanalysis_reported_forward_pe")), "Scenario input", "Secondary market-data point used inside the range."],
        ["MarketBeat annualized EPS scenario", _num(reported_values.get("computed_using_marketbeat_annualized_quarterly_eps")), "Computed scenario", "Quarterly EPS estimate annualized against report-timestamp price."],
        ["Issuer guidance-derived EPS scenario", _num(issuer_guidance_eps), "Computed scenario", "Scenario calculation from company guidance, not official EPS guidance."],
        ["Usable Forward P/E Range", f"{_num(usable_range.get('low'))}x to {_num(usable_range.get('high'))}x", metric.get("reconciliation_status", "N/A"), usable_range.get("business_interpretation", "N/A")],
    ]

    horizon_rows = []
    for item in stage4.get("horizon_decisions", []):
        horizon_rows.append(
            [
                item.get("horizon", "N/A"),
                item.get("classification", "N/A"),
                item.get("evidence_status", "N/A"),
                item.get("rationale", "N/A"),
            ]
        )

    source_rows = []
    for source in stage1.get("source_reliability_table", []):
        source_rows.append(
            [
                source.get("provider", "N/A"),
                source.get("role", "N/A"),
                source.get("reliability", "N/A"),
                source.get("status", "N/A"),
            ]
        )
    for source in stage2d.get("refreshed_sources", []):
        source_rows.append(
            [
                source.get("source_id", "N/A"),
                source.get("publisher", "N/A"),
                source.get("reliability_tier", "N/A"),
                source.get("refresh_status", "N/A"),
            ]
        )

    delta_rows = []
    for key, value in (delta.get("delta_counts") or {}).items():
        delta_rows.append([key, value])
    for item in delta.get("blocked_items", []):
        delta_rows.append(["Blocked Item", f"{item.get('label')}: {item.get('required_action')}"])

    self_audit = stage4.get("titan_self_audit", {})
    self_audit_rows = [
        ["Full Titan Validation Claimed", self_audit.get("full_validation_claimed", False), "Must remain false while blockers exist."],
        ["Timeframe Mixing Check", self_audit.get("timeframe_mixing_check", "N/A"), "Long-term thesis cannot validate shorter-horizon execution."],
        ["Blocked Evidence Preserved", self_audit.get("blocked_evidence_preserved", "N/A"), "Blocked valuation remains visible."],
        ["Assumption-Based Range Present", self_audit.get("assumption_based_range_present", "N/A"), "Range used only with explicit caveats."],
        ["Stale Claim Count", self_audit.get("stale_claim_count", "N/A"), "Stage 2D refreshed stale catalyst/timing claims."],
    ]

    lines: list[str] = [
        f"# {report_title}",
        "",
        "**Report Type:** Institutional evidence-gated final report",
        "",
        "> Research-only decision support. This report is not financial advice, investment advice, tax advice, legal advice, or brokerage advice.",
        "",
        "## Report Metadata",
        _md_table(["Field", "Value"], metadata_rows),
        "",
        "## Executive Decision Summary",
        "The evidence-gated conclusion preserves the baseline decision while routing every material conclusion through the source audit, evidence graph, valuation reconciliation, delta packet, and Stage 4 horizon validation.",
        "",
        _md_table(["Item", "Evidence Layer", "Conclusion"], decision_rows),
        "",
        "## Technical Analysis",
        f"{ticker} technical context is evaluated from the current packet's provider-backed price data and user-supplied timeframe evidence. Short-, medium-, and long-term trend conclusions must remain tied to the listed moving averages, VWAP context, volume evidence, and market-data timestamp for this run.",
        "",
        _md_table(["Metric", "Value", "Interpretation"], technical_rows),
        "",
        "## User-Supplied Multi-Timeframe Technical Evidence",
        f"Stage 1A detected {user_summary.get('file_count', 0)} user-supplied file(s), all deduplicated by hash. Stage 1B extracted VWAP, volume, RSI, ATR, ADX, moving-average, band, and divergence features. Multi-timeframe read: {mft.get('summary_read', 'N/A')}",
        "",
        _md_table(["TF", "Latest Timestamp", "Close", "VWAP", "RSI", "ADX", "Volume"], user_rows),
        "",
        "## Fundamental Analysis",
        "Official SEC EDGAR evidence is available for core financial-statement facts. This supports the existence of issuer-backed fundamentals, but final long-term validation still requires a fuller source-mapped moat, secular thesis, normalized return, and cycle-aware valuation packet.",
        "",
        _md_table(
            ["Field", "Value"],
            [
                ["SEC Status", sec.get("status", "N/A")],
                ["CIK", sec.get("cik", "N/A")],
                ["Available Fact Keys", ", ".join(sec.get("fact_keys", []))],
                ["Latest Filing", (sec.get("recent_filings") or [{}])[0].get("form", "N/A")],
                ["Latest Filing Date", (sec.get("recent_filings") or [{}])[0].get("filing_date", "N/A")],
            ],
        ),
        "",
        "## Valuation Section",
        metric.get("conclusion", "No valuation reconciliation was available."),
        "",
        _md_table(["Metric", "Value", "Status", "Business Reason"], valuation_rows),
        "",
        "## News, Catalysts, Macro, and Narrative Context",
        "Stage 2D removes stale catalyst and earnings-timing ambiguity by refreshing prior supported sources. Macro, industry, and ecosystem proxy claims may support context in the graph, but proxy evidence must remain labeled as indirect context rather than direct issuer revenue validation.",
        "",
        _md_table(
            ["Claim", "Refresh Status", "Source IDs", "Rationale"],
            [
                [
                    claim.get("claim", "N/A"),
                    claim.get("refresh_status", "N/A"),
                    ", ".join(claim.get("source_ids", [])),
                    claim.get("rationale", "N/A"),
                ]
                for claim in stage2d.get("refreshed_claims", [])
            ],
        ),
        "",
        "## Evidence Graph and Source Audit",
        f"The Stage 3 evidence graph is deterministic and did not use LLM semantic extraction. Graph summary: nodes={graph_counts.get('Nodes', 'N/A')}, edges={graph_counts.get('Edges', 'N/A')}, sources={graph_counts.get('Sources', 'N/A')}, residual gaps={graph_counts.get('Residual gaps', 'N/A')}.",
        "",
        _md_table(["Provider / Source", "Role / Publisher", "Reliability", "Status"], source_rows),
        "",
        _md_table(["Delta Status", "Count / Detail"], delta_rows),
        "",
        "## Validated Trading Horizon",
        "Each horizon is evaluated independently. Intraday is not fully validated because live tape, spread/depth, session liquidity, and opening-range evidence are absent in this weekend/after-close packet.",
        "",
        _md_table(["Horizon", "Classification", "Evidence Status", "Rationale"], horizon_rows),
        "",
        "## Self-Audit and Internal Checks",
        "This final report is evidence-gated but does not claim full Titan compliance. Remaining blockers and conditional items are intentionally preserved so business users can see why a classification was assigned.",
        "",
        _md_table(["Check", "Result", "Interpretation"], self_audit_rows),
        "",
        "## Required Next Evidence",
    ]
    for item in stage4.get("next_required_evidence", []):
        lines.append(f"- {item}")

    lines.extend(
        [
            "",
            "## Section Contract",
            "This report was generated under the Stage 5 final-report quality gate. Required sections:",
        ]
    )
    for title in section_titles():
        lines.append(f"- {title}")

    lines.extend(
        [
            "",
            "## Source Artifact Paths",
            "- Exact source artifact paths are recorded in the generated Stage 5 manifest.",
            f"- Stage 4 packet run ID: `{stage4.get('research_cycle', {}).get('research_run_id', 'unknown_run')}`",
        ]
    )

    return "\n".join(lines) + "\n"


def write_pdf_from_markdown(markdown_text: str, output_path: Path) -> None:
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import LETTER
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import inch
        from reportlab.platypus import (
            PageBreak,
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
        )
    except ImportError as exc:  # pragma: no cover - runtime environment check
        raise RuntimeError("reportlab is required to generate PDFs. Install it with `python -m pip install reportlab`.") from exc

    output_path.parent.mkdir(parents=True, exist_ok=True)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="ReportTitle", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=20, leading=24, textColor=colors.HexColor("#172033"), spaceAfter=14))
    styles.add(ParagraphStyle(name="SectionHeading", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=13, leading=16, textColor=colors.HexColor("#1F4E79"), spaceBefore=10, spaceAfter=7))
    styles.add(ParagraphStyle(name="BodyTight", parent=styles["BodyText"], fontName="Helvetica", fontSize=8.2, leading=10.5, spaceAfter=5))
    styles.add(ParagraphStyle(name="Small", parent=styles["BodyText"], fontName="Helvetica", fontSize=7, leading=8.5))

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=LETTER,
        rightMargin=0.45 * inch,
        leftMargin=0.45 * inch,
        topMargin=0.45 * inch,
        bottomMargin=0.45 * inch,
        title="Titan Evidence-Gated Final Research Report",
    )

    story: list[Any] = []
    lines = _clean_markdown_for_pdf(markdown_text).splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            story.append(Spacer(1, 4))
            i += 1
            continue
        if line.startswith("# "):
            story.append(Paragraph(line[2:], styles["ReportTitle"]))
            i += 1
            continue
        if line.startswith("## "):
            if story:
                story.append(Spacer(1, 4))
            story.append(Paragraph(line[3:], styles["SectionHeading"]))
            i += 1
            continue
        if line.startswith("| "):
            table_lines = []
            while i < len(lines) and lines[i].strip().startswith("| "):
                table_lines.append(lines[i].strip())
                i += 1
            rows = []
            for tline in table_lines:
                cells = [c.strip() for c in tline.strip("|").split("|")]
                if all(set(c) <= {"-"} for c in cells):
                    continue
                rows.append([Paragraph(c, styles["Small"]) for c in cells])
            if rows:
                col_count = max(len(row) for row in rows)
                width = 7.6 * inch
                col_widths = [width / col_count] * col_count
                table = Table(rows, colWidths=col_widths, repeatRows=1)
                table.setStyle(
                    TableStyle(
                        [
                            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EAF1F8")),
                            ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#172033")),
                            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#C8D3DF")),
                            ("VALIGN", (0, 0), (-1, -1), "TOP"),
                            ("LEFTPADDING", (0, 0), (-1, -1), 3),
                            ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                            ("TOPPADDING", (0, 0), (-1, -1), 3),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                        ]
                    )
                )
                story.append(table)
                story.append(Spacer(1, 7))
            continue
        if line.startswith("- "):
            story.append(Paragraph(f"&#8226; {line[2:]}", styles["BodyTight"]))
            i += 1
            continue
        if line.startswith(">"):
            story.append(Paragraph(line.lstrip("> "), styles["BodyTight"]))
            i += 1
            continue
        story.append(Paragraph(line, styles["BodyTight"]))
        i += 1

    def footer(canvas: Any, doc_obj: Any) -> None:
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.HexColor("#5D6673"))
        canvas.drawString(0.45 * inch, 0.25 * inch, "Titan Stage 5 evidence-gated research output - research only, not financial advice")
        canvas.drawRightString(8.05 * inch, 0.25 * inch, f"Page {doc_obj.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)


def export_final_report(
    *,
    baseline_path: Path,
    stage1_path: Path,
    stage1b_path: Path,
    stage2c_path: Path,
    stage2d_path: Path,
    graph_report_path: Path,
    delta_path: Path,
    stage4_path: Path,
    output_dir: Path,
    report_name: str | None = None,
) -> ReportArtifacts:
    baseline = _load_json(baseline_path)
    stage1 = _load_json(stage1_path)
    stage1b = _load_json(stage1b_path)
    stage2c = _load_json(stage2c_path)
    stage2d = _load_json(stage2d_path)
    graph_report_text = _read_text(graph_report_path)
    delta = _load_json(delta_path)
    stage4 = _load_json(stage4_path)

    ticker = stage1.get("ticker", "UNKNOWN")
    run_id = (stage4.get("research_cycle") or {}).get("research_run_id", "unknown_run")
    stem = report_name or f"{run_id}_stage5_final_report"
    output_dir.mkdir(parents=True, exist_ok=True)

    markdown = build_final_markdown(
        baseline=baseline,
        stage1=stage1,
        stage1b=stage1b,
        stage2c=stage2c,
        stage2d=stage2d,
        graph_report_text=graph_report_text,
        delta=delta,
        stage4=stage4,
    )

    markdown_path = output_dir / f"{stem}.md"
    pdf_path = output_dir / f"{stem}.pdf"
    manifest_path = output_dir / f"{stem}_manifest.json"

    markdown_path.write_text(markdown, encoding="utf-8")
    write_pdf_from_markdown(markdown, pdf_path)

    manifest = {
        "stage": FINAL_REPORT_STAGE,
        "ticker": ticker,
        "research_run_id": run_id,
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "markdown_path": str(markdown_path),
        "pdf_path": str(pdf_path),
        "source_paths": {
            "baseline": str(baseline_path),
            "stage1": str(stage1_path),
            "stage1b": str(stage1b_path),
            "stage2c": str(stage2c_path),
            "stage2d": str(stage2d_path),
            "graph_report": str(graph_report_path),
            "delta": str(delta_path),
            "stage4": str(stage4_path),
        },
        "quality_gate_sections": list(section_titles()),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return ReportArtifacts(markdown_path=markdown_path, pdf_path=pdf_path, manifest_path=manifest_path)
