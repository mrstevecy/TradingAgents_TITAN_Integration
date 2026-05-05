"""Stage 5 v2 HTML preview renderer."""

from __future__ import annotations

import html
import json
import re
import base64
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .reader_status import reader_status
from .logo_assets import LOGO_DIR
from .equity_evidence import (
    EvidenceItem,
    EvidenceStatus,
    EvidenceStore,
    SourceLevel,
    build_final_report_safety_result,
    promoted_store_from_stage_packets,
    reconcile_evidence_status,
    utc_now_iso,
)
from .dynamic_rag import pre_render_repair_loop
from .upstream_tool_promotion import load_upstream_tool_records, promote_upstream_tool_records
from .error_learning import ErrorLearningStore, make_error_record
from .report_metadata import (
    ReportMode,
    FinalDecision,
    ReportContext,
    assert_clean_issuer_display_name,
    build_report_dates,
    classify_price_level,
    infer_market_bar_status,
    sanitize_issuer_display_name,
    strip_agent_scratchpad,
)


@dataclass(frozen=True)
class PreviewArtifacts:
    html_path: Path
    manifest_path: Path


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


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


def _integer(value: Any) -> str:
    if value is None:
        return "N/A"
    try:
        return f"{float(value):,.0f}"
    except (TypeError, ValueError):
        return str(value)


def _e(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def _badge(status: str | None) -> str:
    item = reader_status(status)
    return f'<span class="badge {item.tone}" title="{_e(item.summary)}">{_e(item.label)}</span>'


def _signal_tone(value: Any) -> tuple[str, str]:
    text = str(value or "")
    low = text.lower()
    if any(word in low for word in ("bearish", "below vwap", "below volume", "negative", "weak/range")):
        return "", "signal-red"
    if any(
        word in low
        for word in (
            "bullish",
            "above vwap",
            "above volume",
            "very strong",
            "strong trend",
            "strong growth",
            "exceptional",
        )
    ):
        return "", "signal-green"
    if any(word in low for word in ("neutral", "near", "mixed", "watch", "developing", "elevated")):
        return "", "signal-amber"
    return "", "signal-neutral"


def _signal_cell(value: Any) -> SafeHtml:
    _icon, css = _signal_tone(value)
    return SafeHtml(f'<span class="signal {css}"><span class="signal-dot" aria-hidden="true"></span>{_e(value)}</span>')


def _signal_metric_cell(label: Any, details: str) -> SafeHtml:
    _icon, css = _signal_tone(label)
    return SafeHtml(
        '<span class="signal {css}"><span class="signal-dot" aria-hidden="true"></span>'
        '<span class="signal-stack"><span class="signal-label">{label}</span>'
        '<span class="signal-detail">{details}</span></span></span>'.format(
            css=css,
            label=_e(label),
            details=_e(details),
        )
    )


def _vwap_cell(item: dict[str, Any]) -> SafeHtml:
    close = _as_float(item.get("latest_close"))
    vwap = _as_float(item.get("latest_rolling_vwap"))
    details = f"VWAP {_money(vwap)}"
    if close is not None and vwap is not None and vwap != 0:
        diff = close - vwap
        details += f"; close diff {_money(diff)} ({_pct((diff / vwap) * 100)})"
    return _signal_metric_cell(item.get("vwap_position", ""), details)


def _rsi_cell(item: dict[str, Any]) -> SafeHtml:
    return _signal_metric_cell(
        item.get("rsi_regime", ""),
        f"RSI {_num(item.get('latest_rsi'))}",
    )


def _adx_cell(item: dict[str, Any]) -> SafeHtml:
    return _signal_metric_cell(
        item.get("adx_regime", ""),
        f"ADX {_num(item.get('latest_adx'))}",
    )


def _volume_cell(item: dict[str, Any]) -> SafeHtml:
    volume = _as_float(item.get("latest_volume"))
    volume_ma = _as_float(item.get("latest_volume_ma"))
    details = f"Vol {_integer(volume)}"
    if volume_ma is not None:
        details += f"; MA {_integer(volume_ma)}"
    if volume is not None and volume_ma not in (None, 0):
        details += f"; ratio {_num(volume / volume_ma)}x"
    return _signal_metric_cell(item.get("volume_regime", ""), details)


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _source_link(source: dict[str, Any]) -> str:
    url = source.get("url")
    title = source.get("title") or source.get("source_id") or source.get("publisher")
    if url:
        return f'<a href="{_e(url)}" target="_blank" rel="noopener">{_e(title)}</a>'
    return _e(title)


def _timeframe_sort_key(value: Any) -> tuple[int, str]:
    order = {
        "1m": 1,
        "3m": 2,
        "5m": 3,
        "15m": 4,
        "30m": 5,
        "1h": 6,
        "2h": 7,
        "4h": 8,
        "1d": 9,
        "1w": 10,
        "1mo": 11,
        "1mth": 11,
    }
    text = str(value or "").strip().lower()
    return order.get(text, 999), text


def _paragraphs(markdown_text: str | None, limit: int = 3) -> str:
    if not markdown_text:
        return ""
    text = re.sub(r"^#+\s+", "", markdown_text.strip(), flags=re.MULTILINE)
    blocks = [block.strip() for block in re.split(r"\n\s*\n", text) if block.strip()]
    rendered = []
    for block in blocks[:limit]:
        if block.startswith("|"):
            continue
        block = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", _e(block))
        block = block.replace("\n", "<br>")
        rendered.append(f"<p>{block}</p>")
    return "\n".join(rendered)


def _normalize_report_dates(markdown_text: str | None, research_date: str, market_date: str | None = None) -> str:
    """Correct reader-facing current-date lines while preserving source lookback dates."""
    if not markdown_text:
        return ""
    text = str(markdown_text)
    pretty_research = _pretty_date(research_date)
    pretty_market = _pretty_date(market_date) if market_date else None
    text = re.sub(r"\*\*Current\s+Date:\*\*\s*May\s+1,\s+2026", f"**Research Date:** {pretty_research}", text, flags=re.IGNORECASE)
    text = re.sub(r"Current\s+Date:\s*May\s+1,\s+2026", f"Research Date: {pretty_research}", text, flags=re.IGNORECASE)
    text = re.sub(r"\*\*Current\s+Date:\*\*\s*20\d{2}-\d{2}-\d{2}", f"**Research Date:** {research_date}", text, flags=re.IGNORECASE)
    text = re.sub(r"Current\s+Date:\s*20\d{2}-\d{2}-\d{2}", f"Research Date: {research_date}", text, flags=re.IGNORECASE)
    if pretty_market and "Market Data As-Of:" not in text[:800]:
        text = text.replace(
            "---",
            f"---\n\n> **Titan timestamp note:** Research date is {pretty_research}. Latest regular-session market data used by this packet is as of {pretty_market}.\n\n---",
            1,
        )
    return text


def _pretty_date(value: str | None) -> str:
    if not value:
        return "N/A"
    try:
        return datetime.fromisoformat(value[:10]).strftime("%B %-d, %Y")
    except ValueError:
        try:
            return datetime.fromisoformat(value[:10]).strftime("%B %#d, %Y")
        except ValueError:
            return str(value)


def _inline_md(text: str) -> str:
    escaped = _e(text)
    escaped = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r'<a href="\2" target="_blank" rel="noopener">\1</a>', escaped)
    escaped = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"(?<!\*)\*(?!\*)(.*?)(?<!\*)\*(?!\*)", r"<em>\1</em>", escaped)
    return escaped


def _heading_icon(title: str, level: int) -> str:
    low = title.lower()
    if "news" in low or "report" in low and level == 1:
        return "📰"
    if "macro" in low or "market context" in low:
        return "🌐"
    if "technical" in low or "indicator" in low or "market" in low:
        return "📈"
    if "fundamental" in low or "metrics" in low or "cash flow" in low:
        return "📊"
    if "bull" in low and "bear" in low:
        return "⚖️"
    if "risk" in low:
        return "🔴"
    if "strength" in low:
        return "🟢"
    if "actionable" in low or "trader" in low:
        return "💡"
    if "valuation" in low:
        return "🧮"
    if "sentiment" in low or "media" in low:
        return "🔎"
    if "decision" in low or "verdict" in low or "proposal" in low:
        return "🎯"
    return "●" if level >= 3 else "▣"


def _md_table(lines: list[str]) -> str:
    rows = []
    for line in lines:
        raw = line.strip().strip("|")
        cells = [cell.strip() for cell in raw.split("|")]
        if all(re.fullmatch(r":?-{3,}:?", cell.replace(" ", "")) for cell in cells):
            continue
        rows.append(cells)
    if not rows:
        return ""
    headers = rows[0]
    body = rows[1:]
    thead = "".join(f"<th>{_inline_md(cell)}</th>" for cell in headers)
    trs = []
    for row in body:
        cells = row + [""] * (len(headers) - len(row))
        trs.append("<tr>" + "".join(f"<td>{_inline_md(cell)}</td>" for cell in cells[: len(headers)]) + "</tr>")
    return f'<div class="table-wrap baseline-table"><table><thead><tr>{thead}</tr></thead><tbody>{"".join(trs)}</tbody></table></div>'


def _md_to_html(markdown_text: str | None) -> str:
    """Small markdown renderer for the TradingAgents report subset."""
    if not markdown_text:
        return ""
    lines = str(markdown_text).splitlines()
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        stripped = line.strip()
        if not stripped:
            i += 1
            continue
        if stripped == "---":
            out.append("<hr>")
            i += 1
            continue
        if stripped.startswith(">"):
            quote_lines = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                quote_lines.append(lines[i].strip().lstrip(">").strip())
                i += 1
            out.append(f'<div class="titan-note">{_inline_md(" ".join(quote_lines))}</div>')
            continue
        if stripped.startswith("|"):
            table_lines = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                table_lines.append(lines[i])
                i += 1
            out.append(_md_table(table_lines))
            continue
        match = re.match(r"^(#{1,4})\s+(.*)$", stripped)
        if match:
            level = min(len(match.group(1)) + 1, 5)
            title = match.group(2).strip()
            out.append(f'<h{level} class="md-heading">{_inline_md(title)}</h{level}>')
            i += 1
            continue
        if re.match(r"^[-*]\s+", stripped):
            items = []
            while i < len(lines) and re.match(r"^[-*]\s+", lines[i].strip()):
                items.append(re.sub(r"^[-*]\s+", "", lines[i].strip()))
                i += 1
            out.append("<ul>" + "".join(f"<li>{_inline_md(item)}</li>" for item in items) + "</ul>")
            continue
        if re.match(r"^\d+\.\s+", stripped):
            items = []
            while i < len(lines) and re.match(r"^\d+\.\s+", lines[i].strip()):
                items.append(re.sub(r"^\d+\.\s+", "", lines[i].strip()))
                i += 1
            out.append("<ol>" + "".join(f"<li>{_inline_md(item)}</li>" for item in items) + "</ol>")
            continue
        paragraph = [stripped]
        i += 1
        while i < len(lines):
            nxt = lines[i].strip()
            if not nxt or nxt.startswith(("#", "|", ">", "---")) or re.match(r"^[-*]\s+|^\d+\.\s+", nxt):
                break
            paragraph.append(nxt)
            i += 1
        text = " ".join(paragraph)
        out.append(f"<p>{_inline_md(text)}</p>")
    return "\n".join(out)


def _baseline_block(title: str, subtitle: str, markdown_text: str | None, *, icon: str, note: str | None = None) -> str:
    note_html = f'<div class="titan-note">{_inline_md(note)}</div>' if note else ""
    return f"""
  <section class="section baseline-section">
    <div class="section-kicker">{_e(subtitle)}</div>
    <h2>{_e(title)}</h2>
    <div class="baseline-content">
      {_md_to_html(markdown_text)}
    </div>
    {note_html}
  </section>
"""


def _baseline_section_dict(baseline: dict[str, Any]) -> dict[str, str]:
    return {
        "final_trade_decision": strip_agent_scratchpad(baseline.get("final_trade_decision") or ""),
        "market_report": strip_agent_scratchpad(baseline.get("market_report") or ""),
        "news_report": strip_agent_scratchpad(baseline.get("news_report") or ""),
        "fundamentals_report": strip_agent_scratchpad(baseline.get("fundamentals_report") or ""),
        "sentiment_report": strip_agent_scratchpad(baseline.get("sentiment_report") or ""),
        "investment_plan": strip_agent_scratchpad(baseline.get("investment_plan") or ""),
        "trader_investment_plan": strip_agent_scratchpad(baseline.get("trader_investment_plan") or ""),
    }


def _constrain_rejected_decision_sections(
    sections: dict[str, str],
    safety: Any,
    baseline_decision: str,
) -> dict[str, str]:
    constrained = dict(sections)
    section_agents = {
        "final_trade_decision": "Portfolio Manager",
        "investment_plan": "Research Manager",
        "trader_investment_plan": "Trader",
    }
    gaps = ", ".join(safety.unresolved_gaps or ["none recorded"])
    for section, agent in section_agents.items():
        agent_rejections = [claim for claim in safety.rejected_claims if claim.agent_name == agent]
        if not agent_rejections:
            continue
        dependencies = sorted({claim.pattern or claim.reason for claim in agent_rejections})
        constrained[section] = (
            "### Evidence-Gated Constrained Decision\n\n"
            f"The upstream {agent} output is not promoted as executable decision text because code-level "
            f"validation rejected {len(agent_rejections)} claim(s) tied to: {', '.join(dependencies)}.\n\n"
            f"Raw baseline posture observed: **{baseline_decision or 'N/A'}**. "
            "Defensible reader-facing conclusion: treat the result as a constrained research view, "
            "not an actionable Buy/Sell/Exit instruction, until the unresolved evidence gaps are resolved.\n\n"
            f"Unresolved evidence gaps: {gaps}.\n\n"
            "See Appendix A for the exact rejected claims, failure reasons, and correction rules."
        )
    return constrained


def _build_report_context(
    *,
    ticker: str,
    company_name: str,
    report_dates: Any,
    bar: dict[str, Any],
    metrics: dict[str, Any],
    price_audit: dict[str, Any],
) -> ReportContext:
    status, is_eod = infer_market_bar_status(
        research_date=report_dates.research_date,
        market_data_as_of=report_dates.market_data_as_of,
        latest_volume=bar.get("volume"),
        avg_volume=metrics.get("avg_20_volume"),
    )
    source = price_audit.get("source") or {}
    return ReportContext(
        ticker=ticker,
        company_name=company_name,
        research_date=report_dates.research_date,
        intended_trade_date=report_dates.intended_trade_date,
        market_data_as_of=report_dates.market_data_as_of,
        market_bar_status=status,
        latest_price=_as_float(bar.get("close")),
        latest_price_source=source.get("provider") or price_audit.get("provider"),
        latest_price_is_eod=is_eod,
    )


def _build_final_decision(
    *,
    baseline_decision: str,
    safety: Any,
    evidence_store: EvidenceStore,
) -> FinalDecision:
    validated = sorted(k for k, item in evidence_store.items.items() if item.status.value in {"retrieved", "computed"})
    rejected_dependencies = sorted(
        {
            claim.pattern
            for claim in safety.rejected_claims
            if claim.pattern and claim.pattern != "catalyst.stale_earnings_date_conflict"
        }
    )
    blocking_gaps = {
        gap.key
        for gap in evidence_store.gaps.values()
        if gap.blocking and gap.status.value not in {"retrieved", "computed"}
    }
    blocked = sorted(blocking_gaps | set(rejected_dependencies))
    if blocked:
        rating = "DATA-INCOMPLETE / MONITOR ONLY"
        actionability = "No executable Buy/Sell/Exit action while critical evidence blockers remain."
        confidence = "Low"
    else:
        rating = f"EVIDENCE-GATED {baseline_decision.upper()}" if baseline_decision else "EVIDENCE-GATED MONITOR"
        actionability = "Candidate action requires normal portfolio suitability review."
        confidence = "Medium"
    return FinalDecision(
        rating=rating,
        actionability=actionability,
        confidence=confidence,
        validated_keys=validated,
        blocked_keys=blocked,
        required_next_evidence=_next_evidence_for_blocked(blocked),
        baseline_posture=baseline_decision or None,
    )


def _next_evidence_for_blocked(blocked: list[str]) -> list[str]:
    guidance = {
        "capex.guidance": "Issuer IR/transcript/SEC-backed CapEx outlook with timing and units.",
        "earnings.actual_vs_consensus": "Actual revenue/EPS versus consensus from at least one permitted estimates source.",
        "fundamentals.latest_earnings_release": "Issuer earnings release or 8-K exhibit for the latest quarter.",
        "cashflow.fcf_inputs": "Same-period OCF and CapEx values with units and source tags.",
        "cashflow.latest.ocf": "Latest operating cash flow from SEC 10-Q/10-K cash-flow statement or issuer-reported cash-flow table.",
        "business.rpo_or_backlog": "Issuer IR, SEC filing, or transcript-backed RPO/backlog value; required only for subscription/contract-heavy thesis claims.",
        "catalyst.stale_earnings_date_conflict": "Remove stale baseline catalyst dates from reader-facing sections after canonical earnings-event resolution.",
        "valuation.forward_pe_basis": "Price plus FY1/FY2/NTM EPS denominator from permitted estimates source.",
        "positioning.short_interest": "Shares short, percent float, and days-to-cover from permitted short-interest source.",
    }
    return [guidance.get(key, f"Permitted, unit-valid source for {key}.") for key in blocked]


def _final_decision_markdown(decision: FinalDecision) -> str:
    rows = [
        ["Final reader-facing rating", decision.rating],
        ["Actionability", decision.actionability],
        ["Confidence", decision.confidence],
        ["Screened baseline posture", decision.baseline_posture or "N/A"],
        ["Blocked evidence keys", ", ".join(decision.blocked_keys) or "None"],
        ["Next evidence required", "; ".join(decision.required_next_evidence) or "None"],
    ]
    return "### Canonical Final Decision\n\n" + _markdown_table(["Field", "Value"], rows)


def _markdown_table(headers: list[str], rows: list[list[Any]]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(str(cell) for cell in row) + " |")
    return "\n".join(lines)


def _technical_analysis_markdown(context: ReportContext, metrics: dict[str, Any], stage1b: dict[str, Any], stage4: dict[str, Any]) -> str:
    close = context.latest_price
    rows = [
        ["Latest price", _money(close), context.market_data_as_of or "N/A", context.market_bar_status],
        ["10 EMA", _money(metrics.get("ema_10")), classify_price_level(metrics.get("ema_10"), close), "Computed from normalized OHLCV."],
        ["50 SMA", _money(metrics.get("sma_50")), classify_price_level(metrics.get("sma_50"), close), "Medium-term trend level."],
        ["200 SMA", _money(metrics.get("sma_200")), classify_price_level(metrics.get("sma_200"), close), "Long-term trend level."],
        ["VWMA 20", _money(metrics.get("vwma_20")), classify_price_level(metrics.get("vwma_20"), close), "Volume-weighted moving average."],
    ]
    horizon = stage4.get("validated_trading_horizon", "N/A")
    return (
        "### Technical Analysis\n\n"
        f"Canonical market context: {context.ticker} latest validated price is {_money(close)} as of {context.market_data_as_of or 'N/A'} "
        f"with market bar status `{context.market_bar_status}`. Horizon validation: {horizon}.\n\n"
        + _markdown_table(["Level", "Value", "Relation to Price", "Evidence Note"], rows)
        + "\n\nAll support/resistance labels are generated from numeric price-vs-level relation, not baseline prose."
    )


def _market_analysis_markdown(context: ReportContext, stage2d: dict[str, Any], evidence_store: EvidenceStore) -> str:
    refreshed = [claim for claim in stage2d.get("refreshed_claims", []) if str(claim.get("refresh_status", "")).lower() == "supported"]
    rows = [[claim.get("claim", ""), claim.get("refresh_status", ""), claim.get("rationale", "")] for claim in refreshed[:6]]
    event_state = evidence_store.value("earnings.event_state", {}) or {}
    if isinstance(event_state, dict) and (event_state.get("latest_reported_date") or event_state.get("next_estimated_date")):
        rows.insert(
            0,
            [
                "Earnings event state",
                evidence_store.status("earnings.event_state").value,
                (
                    f"Latest reported: {event_state.get('latest_reported_date') or 'unresolved'}; "
                    f"next estimated: {event_state.get('next_estimated_date') or 'unresolved'}; "
                    f"state: {event_state.get('state') or 'unresolved'}."
                ),
            ],
        )
    stale = evidence_store.value("catalyst.stale_earnings_date_conflict", {}) or {}
    if isinstance(stale, dict) and stale.get("stale_or_conflicting_dates"):
        rows.insert(
            1 if rows else 0,
            [
                "Stale earnings catalyst guard",
                "stale",
                (
                    f"Quarantined date(s): {', '.join(stale.get('stale_or_conflicting_dates') or [])}. "
                    "These cannot be treated as upcoming catalysts unless independently revalidated."
                ),
            ],
        )
    if not rows:
        rows = [["No refreshed catalyst claim promoted", "Constrained", "Use only canonical report context until catalyst evidence refresh succeeds."]]
    return (
        "### Market Analysis\n\n"
        f"Market narrative is anchored to research date {context.research_date} and market data as of {context.market_data_as_of or 'N/A'}. "
        "Stale baseline dates are treated as historical diagnostics and do not control this section.\n\n"
        + _markdown_table(["Market/Catalyst Item", "Status", "Rationale"], rows)
    )


def _fundamental_analysis_markdown(evidence_store: EvidenceStore, final_decision: FinalDecision) -> str:
    keys = [
        "fundamentals.latest_financial_filing",
        "fundamentals.latest_earnings_8k",
        "fundamentals.latest_earnings_release",
        "earnings.actual_vs_consensus",
        "guidance.management",
        "business.rpo_or_backlog",
        "cashflow.fcf_inputs",
        "valuation.forward_pe_basis",
    ]
    rows = []
    for key in keys:
        item = evidence_store.get(key)
        status = evidence_store.status(key).value
        source = item.source_name if item else "Not promoted"
        note = "; ".join(item.limitations or []) if item else "Missing from reconciled evidence store."
        rows.append([key, status, source, note])
    return (
        "### Fundamental Analysis\n\n"
        "Fundamental claims are rendered from reconciled typed evidence. Invalid retrieved facts, proxy misuse, and unitless numeric artifacts are not promoted.\n\n"
        + _markdown_table(["Evidence Key", "Canonical Status", "Source", "Validation Note"], rows)
        + f"\n\nCurrent fundamental actionability: **{final_decision.rating}**."
    )


def _sentiment_positioning_markdown(evidence_store: EvidenceStore) -> str:
    keys = ["consensus.analyst", "positioning.short_interest", "options.put_call", "ownership.form4_90d", "ownership.13f_latest"]
    rows = []
    for key in keys:
        item = evidence_store.get(key)
        rows.append([
            key,
            evidence_store.status(key).value,
            item.source_name if item else "Not promoted",
            "; ".join(item.limitations or []) if item else "No canonical evidence available.",
        ])
    return (
        "### Sentiment & Positioning\n\n"
        "Sentiment is split into analyst consensus, short interest, options, and ownership context. Technical labels and media headlines are not treated as fundamentals.\n\n"
        + _markdown_table(["Evidence Key", "Canonical Status", "Source", "Note"], rows)
    )


def _execution_plan_markdown(final_decision: FinalDecision, metrics: dict[str, Any], latest_close: float | None) -> str:
    rows = [
        ["Final action", final_decision.rating],
        ["Executable trade", "No" if final_decision.blocked_keys else "Conditional"],
        ["Primary monitoring level", _money(metrics.get("ema_10")), classify_price_level(metrics.get("ema_10"), latest_close)],
        ["Medium-term level", _money(metrics.get("sma_50")), classify_price_level(metrics.get("sma_50"), latest_close)],
        ["Long-term level", _money(metrics.get("sma_200")), classify_price_level(metrics.get("sma_200"), latest_close)],
    ]
    return (
        "### Trader Execution Plan\n\n"
        "No executable trade is rendered while critical blockers remain. The report provides monitoring levels only.\n\n"
        + _markdown_table(["Item", "Value", "Context"], rows)
    )


def _research_manager_markdown(baseline_sections: dict[str, str], safety: Any, evidence_store: EvidenceStore) -> str:
    raw = strip_agent_scratchpad(baseline_sections.get("investment_plan", ""))
    rows = [
        ["Accepted evidence keys", len([item for item in evidence_store.items.values() if item.status in {EvidenceStatus.RETRIEVED, EvidenceStatus.COMPUTED}]), "Usable in synthesis."],
        ["Rejected claims", len(safety.rejected_claims), "Excluded unless repaired by upstream tool evidence or RAG."],
        ["Unresolved gaps", len(safety.unresolved_gaps), "Must constrain final actionability."],
    ]
    excerpt = _compact_plain(raw, 1200) if raw else "No Research Manager narrative was available from the upstream run."
    return (
        "### Research Manager Adjudication\n\n"
        + _markdown_table(["Adjudication Item", "Value", "Decision Use"], rows)
        + "\n\n#### Sanitized Manager Synthesis\n\n"
        + excerpt
    )


def _debate_outcomes_markdown(baseline_fresh: dict[str, Any], safety: Any) -> str:
    inv = baseline_fresh.get("investment_debate_state") or {}
    risk = baseline_fresh.get("risk_debate_state") or {}
    rows = [
        ["Bull researcher", _compact_plain(inv.get("bull_history", ""), 900) or "Not captured"],
        ["Bear researcher", _compact_plain(inv.get("bear_history", ""), 900) or "Not captured"],
        ["Research manager decision", _compact_plain(inv.get("judge_decision", ""), 900) or "Not captured"],
        ["Aggressive risk analyst", _compact_plain(risk.get("aggressive_history", ""), 900) or "Not captured"],
        ["Neutral risk analyst", _compact_plain(risk.get("neutral_history", ""), 900) or "Not captured"],
        ["Conservative risk analyst", _compact_plain(risk.get("conservative_history", ""), 900) or "Not captured"],
        ["Portfolio risk decision", _compact_plain(risk.get("judge_decision", ""), 900) or "Not captured"],
    ]
    return (
        "### Debate & Risk Outcomes\n\n"
        "The original TradingAgents architecture depends on analyst reports, Bull/Bear debate, trader synthesis, risk debate, and Portfolio Manager review. "
        "This section preserves that structure while the safety layer separately excludes unsupported claims.\n\n"
        + _markdown_table(["Role", "Sanitized Outcome"], rows)
        + f"\n\nExcluded claims after evidence checks: {len(safety.rejected_claims)}."
    )


def _compact_plain(text: Any, limit: int = 800) -> str:
    value = strip_agent_scratchpad(str(text or ""))
    value = re.sub(r"\s+", " ", re.sub(r"[*_`#>|]+", " ", value)).strip()
    return value if len(value) <= limit else value[: limit - 3] + "..."


def _rich_upstream_appendix(title: str, markdown_text: str | None, *, max_chars: int = 9000) -> str:
    if not markdown_text or not str(markdown_text).strip():
        return ""
    text = strip_agent_scratchpad(str(markdown_text)).strip()
    if len(text) > max_chars:
        text = text[: max_chars - 120].rstrip() + "\n\n> Evidence note: upstream narrative truncated for report readability; full raw baseline remains in run artifacts."
    return (
        f"\n\n#### {title}\n\n"
        "The following upstream TradingAgents narrative is preserved for analytical richness. "
        "Inline evidence notes mark claims that are scenarios, unresolved, or not promoted as final truth.\n\n"
        + text
    )


def _relation_text(price: float | None, level: float | None, label: str) -> str:
    if price is None or level is None:
        return f"{label} relation cannot be computed because price or level is unavailable."
    try:
        price_f = float(price)
        level_f = float(level)
    except (TypeError, ValueError):
        return f"{label} relation cannot be computed because price or level is nonnumeric."
    if level_f == 0:
        return f"{label} relation cannot be computed because the level is zero."
    diff = price_f - level_f
    pct = (diff / level_f) * 100
    side = "above" if diff > 0 else "below" if diff < 0 else "at"
    relation = classify_price_level(level_f, price_f)
    return f"Price is {_money(abs(diff))} ({abs(pct):.2f}%) {side} {label}; classified as {relation}."


def _baseline_integrity_summary(baseline: dict[str, Any]) -> dict[str, Any]:
    sections = _baseline_section_dict(baseline)
    return {
        "baseline_source": "baseline_fresh",
        "rule": "Baseline sections are preserved only after code-level contamination screening; rejected claims render in the excluded-claims section.",
        "section_count": len([v for v in sections.values() if v]),
        "sections": {
            name: {
                "present": bool(text.strip()),
                "characters": len(text),
                "title_count": len(re.findall(r"^#{1,4}\s+", text, flags=re.MULTILINE)),
                "table_count": len(re.findall(r"^\|", text, flags=re.MULTILINE)),
            }
            for name, text in sections.items()
        },
    }


def _strip_html(html_text: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", " ", html_text))


def _baseline_title_audit(baseline: dict[str, Any], html_text: str) -> dict[str, Any]:
    rendered_text = re.sub(r"\s+", " ", re.sub(r"[^\w\s$%./:&+-]", " ", _strip_html(html_text))).strip().lower()
    sections = _baseline_section_dict(baseline)
    audit: dict[str, Any] = {}
    for name, text in sections.items():
        titles = [re.sub(r"[*_`#]+", "", m.group(1)).strip() for m in re.finditer(r"^#{1,4}\s+(.+)$", text, flags=re.MULTILINE)]
        missing = []
        for title in titles:
            simplified = re.sub(r"\s+", " ", re.sub(r"[^\w\s$%./:&+-]", " ", title)).strip().lower()
            if simplified and simplified not in rendered_text:
                missing.append(title)
        audit[name] = {
            "baseline_title_count": len(titles),
            "missing_rendered_titles": missing,
        }
    return audit


def _baseline_proposal_map(baseline: dict[str, Any]) -> list[list[Any]]:
    sections = [
        ("Portfolio Manager / Final Trade Decision", "final_trade_decision"),
        ("Market Analyst", "market_report"),
        ("News Analyst", "news_report"),
        ("Fundamentals Analyst", "fundamentals_report"),
        ("Sentiment Analyst", "sentiment_report"),
        ("Research Manager / Investment Plan", "investment_plan"),
        ("Trader Investment Plan", "trader_investment_plan"),
    ]
    out: list[list[Any]] = []
    for label, key in sections:
        text = baseline.get(key) or ""
        matches = re.findall(
            r"(?:Final Trading Decision|FINAL TRANSACTION PROPOSAL|Final Stance|Recommendation)[:\s*]*(.{0,180})",
            text,
            flags=re.IGNORECASE,
        )
        if not matches:
            continue
        cleaned_matches = [re.sub(r"[*_`#]+", "", m).strip() for m in matches if m.strip()]
        generic_options = [m for m in cleaned_matches if m.upper() == "BUY/HOLD/SELL"]
        concrete = [m for m in cleaned_matches if m.upper() != "BUY/HOLD/SELL"]
        if generic_options and concrete:
            cleaned = concrete[-1]
            treatment = "Screened baseline output; source states the BUY/HOLD/SELL decision field and then selects BUY."
            overlay = "Interpret BUY/HOLD/SELL as the classification scale. The concrete selected baseline classification for this role is BUY."
        else:
            cleaned = "; ".join(cleaned_matches)
            treatment = "Screened baseline output"
            overlay = "Read as section-specific unless reconciled by final TITAN overlay."
        out.append([label, cleaned, treatment, overlay])
    return out


def _baseline_decision(baseline: dict[str, Any]) -> str:
    for key in ("processed_decision", "final_decision", "decision", "stance"):
        value = baseline.get(key)
        if value:
            return str(value).strip()
    proposals = _baseline_proposal_map(baseline)
    if proposals:
        return str(proposals[-1][1]).strip()
    return "Evidence-Gated"


def _merged_equity_evidence_store(stage1: dict[str, Any], stage2: dict[str, Any], stage2b: dict[str, Any], baseline_fresh: dict[str, Any] | None = None) -> EvidenceStore:
    base_payload = stage1.get("mandatory_equity_data_scan") or {}
    if base_payload:
        try:
            base = EvidenceStore.from_dict(base_payload)
        except Exception:
            base = EvidenceStore(
                ticker=stage1.get("ticker", "UNKNOWN"),
                report_date=stage1.get("trade_date", ""),
                generated_at=stage1.get("generated_at_utc", ""),
            )
    else:
        base = EvidenceStore(
            ticker=stage1.get("ticker", "UNKNOWN"),
            report_date=stage1.get("trade_date", ""),
            generated_at=stage1.get("generated_at_utc", ""),
        )
    promoted = stage2b.get("promoted_equity_evidence_store") or {}
    if promoted:
        try:
            promoted_store = EvidenceStore.from_dict(promoted)
            for item in promoted_store.items.values():
                base.add_item(item)
            for attempt in promoted_store.resolver_attempts:
                base.resolver_attempts.append(attempt)
        except Exception:
            pass
    store = promoted_store_from_stage_packets(
        ticker=stage1.get("ticker", "UNKNOWN"),
        report_date=stage1.get("trade_date", ""),
        stage2=stage2,
        stage2b=stage2b,
        base_store=base,
    )
    _inject_canonical_market_snapshot(store, stage1)
    if baseline_fresh:
        records = load_upstream_tool_records(baseline_fresh.get("upstream_tool_evidence_path"))
        promote_upstream_tool_records(store, records)
    return reconcile_evidence_status(store)


def _inject_canonical_market_snapshot(store: EvidenceStore, stage1: dict[str, Any]) -> None:
    price = stage1.get("price_data_audit", {}) or {}
    bar = price.get("latest_bar", {}) or {}
    if not isinstance(bar, dict) or bar.get("close") is None:
        return
    metrics = price.get("computed_metrics", {}) or {}
    source_name = str((bar.get("source") or {}).get("provider") or "normalized market data")
    source_url = str((bar.get("source") or {}).get("source_url") or "https://finance.yahoo.com/")
    as_of = bar.get("date")
    retrieved_at = (bar.get("source") or {}).get("retrieved_at_utc") or utc_now_iso()
    avg_volume = metrics.get("volume_ma_20") or metrics.get("avg_volume_20") or metrics.get("avg_20_volume")
    bar_status, is_eod = infer_market_bar_status(
        research_date=(stage1.get("research_cycle") or {}).get("requested_analysis_date") or stage1.get("trade_date"),
        market_data_as_of=as_of,
        latest_volume=bar.get("volume"),
        avg_volume=avg_volume,
    )
    snapshot = {
        "ticker": store.ticker,
        "provider": source_name,
        "source_url": source_url,
        "retrieved_at_utc": retrieved_at,
        "bar_date": as_of,
        "bar_status": bar_status,
        "latest_price_is_eod": is_eod,
        "open": bar.get("open"),
        "high": bar.get("high"),
        "low": bar.get("low"),
        "close_or_last": bar.get("close"),
        "volume": bar.get("volume"),
        "provider_reconciliation": [
            {
                "provider": source_name,
                "timestamp": retrieved_at,
                "open": bar.get("open"),
                "high": bar.get("high"),
                "low": bar.get("low"),
                "last_or_close": bar.get("close"),
                "volume": bar.get("volume"),
                "bar_status": bar_status,
            }
        ],
    }
    item = EvidenceItem(
        key="market.snapshot.primary",
        value=snapshot,
        status=EvidenceStatus.RETRIEVED,
        source_name=source_name,
        source_url=source_url,
        source_level=SourceLevel.AGGREGATOR_OR_MARKET_DATA,
        as_of_date=as_of,
        retrieved_at=retrieved_at,
        retrieval_method="canonical_market_snapshot",
        confidence="medium",
        direct_or_proxy="direct",
    )
    store.add_item(item)
    store.add_item(
        EvidenceItem(
            key="market.latest_price",
            value={"close": bar.get("close"), "date": as_of, "volume": bar.get("volume"), "bar_status": bar_status},
            status=EvidenceStatus.RETRIEVED,
            source_name=source_name,
            source_url=source_url,
            source_level=SourceLevel.AGGREGATOR_OR_MARKET_DATA,
            as_of_date=as_of,
            retrieved_at=retrieved_at,
            retrieval_method="canonical_market_snapshot",
            confidence="medium",
            direct_or_proxy="direct",
        )
    )


def _excluded_claim_rows(safety: Any) -> list[list[Any]]:
    rows: list[list[Any]] = []
    for claim in safety.rejected_claims:
        rows.append(
            [
                claim.agent_name,
                claim.severity,
                claim.exact_claim,
                claim.reason,
                claim.correction_rule,
                "Yes" if claim.recurrence else "No",
            ]
        )
    if not rows:
        rows.append(["System", "N/A", "None", "No rejected baseline claims detected.", "Continue evidence-led validation.", "No"])
    return rows


def _record_safety_errors(output_dir: Path, ticker: str, run_id: str, safety: Any) -> None:
    store = ErrorLearningStore(output_dir.parents[1] / "error_learning" / "agent_error_records.json")
    for claim in safety.rejected_claims:
        store.append(
            make_error_record(
                run_id=run_id,
                ticker=ticker,
                agent=claim.agent_name,
                error_type=claim.pattern or claim.reason[:80],
                severity=claim.severity,
                exact_error=claim.exact_claim,
                correction_rule=claim.correction_rule,
                evidence_dependency=claim.pattern,
            )
        )


def _guidance_reinforced(stage2b: dict[str, Any]) -> bool:
    return _downstream_claim_supported(stage2b, ("guidance",))


def _downstream_claim_supported(stage2b: dict[str, Any], needles: tuple[str, ...]) -> bool:
    for claim in stage2b.get("reinforced_claims", []) or []:
        text = f"{claim.get('claim', '')} {claim.get('evidence_class', '')}".lower()
        status = str(claim.get("reinforced_status", "")).lower()
        if status == "supported" and any(needle in text for needle in needles):
            return True
    return False


def _downstream_claim_source_ids(stage2b: dict[str, Any], needles: tuple[str, ...]) -> list[str]:
    source_ids: list[str] = []
    for claim in stage2b.get("reinforced_claims", []) or []:
        text = f"{claim.get('claim', '')} {claim.get('evidence_class', '')}".lower()
        status = str(claim.get("reinforced_status", "")).lower()
        if status == "supported" and any(needle in text for needle in needles):
            source_ids.extend(claim.get("source_ids", []) or [])
    return list(dict.fromkeys(source_ids))


def _metric_point_estimate_blocked(stage2c: dict[str, Any]) -> bool:
    for metric in stage2c.get("reconciled_metrics", []) or []:
        status = str(metric.get("specific_claim_status", "")).lower()
        if status in {"blocked", "contradictory", "not validated"}:
            return True
    return False


def _effective_mandatory_rows(stage1: dict[str, Any], stage2b: dict[str, Any]) -> list[list[Any]]:
    downstream_needles = {
        "latest_company_guidance": ("guidance",),
        "catalyst_calendar": ("catalyst", "next earnings"),
        "sentiment_positioning": ("positioning", "short interest", "days-to-cover", "days to cover"),
    }
    rows: list[list[Any]] = []
    for item in stage1.get("mandatory_evidence_audit", []) or []:
        status = item.get("status", "")
        evidence_id = item.get("evidence_id", "")
        rationale = item.get("validation_result", "")
        attempted = "; ".join(item.get("source_classes_attempted", []))
        needles = downstream_needles.get(evidence_id)
        if needles and _downstream_claim_supported(stage2b, needles):
            status = "Supported"
            source_ids = _downstream_claim_source_ids(stage2b, needles)
            attempted = "; ".join(source_ids) if source_ids else attempted
            rationale = "Downstream citation/reinforcement evidence validated this mandatory evidence block."
        rows.append(
            [
                item.get("label", evidence_id),
                SafeHtml(_badge(status)),
                item.get("gap_severity", ""),
                attempted,
                item.get("thesis_impact", ""),
                rationale,
            ]
        )
    return rows


def _mandatory_scan_rows(evidence_store: EvidenceStore) -> list[list[Any]]:
    rows: list[list[Any]] = []
    for item in evidence_store.items.values():
        rows.append(
            [
                item.key,
                item.status.value,
                item.source_name,
                item.as_of_date,
                _format_evidence_value(item.value),
            ]
        )
    for gap in evidence_store.gaps.values():
        rows.append(
            [
                gap.key,
                gap.status.value,
                "; ".join(gap.source_classes_attempted),
                "N/A",
                gap.constrained_conclusion,
            ]
        )
    return rows[:28]


def _format_evidence_value(value: Any) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, float):
        return _num(value)
    if isinstance(value, int):
        return _integer(value)
    if isinstance(value, dict):
        parts = []
        for key, item in list(value.items())[:5]:
            parts.append(f"{key}: {_format_evidence_value(item)}")
        if len(value) > 5:
            parts.append(f"+{len(value) - 5} more")
        return "; ".join(parts)
    if isinstance(value, list):
        items = [_format_evidence_value(item) for item in value[:6]]
        if len(value) > 6:
            items.append(f"+{len(value) - 6} more")
        return ", ".join(items)
    text = str(value)
    return text if len(text) <= 220 else text[:217].rstrip() + "..."


def _resolver_trace_rows(evidence_store: EvidenceStore) -> list[list[Any]]:
    rows: list[list[Any]] = []
    for trace in evidence_store.resolver_traces:
        rows.append(
            [
                trace.evidence_key,
                trace.validation_status,
                "; ".join(trace.attempted_sources),
                "; ".join(trace.attempted_queries[:3]),
                trace.selected_source or "N/A",
                trace.failure_reason or "Resolved",
            ]
        )
    if not rows:
        rows.append(["N/A", "not_run", "N/A", "N/A", "N/A", "No dynamic RAG repair trace was recorded."])
    return rows


def _equity_enforcement_rows(stage1: dict[str, Any], stage2c: dict[str, Any], evidence_store: EvidenceStore | None = None) -> list[list[Any]]:
    scan = stage1.get("mandatory_equity_data_scan", {}) or {}
    attempts = scan.get("resolver_attempts") or []
    items = scan.get("items") or {}
    def gate_status(*keys: str) -> str:
        if evidence_store is not None:
            statuses = [evidence_store.status(key).value for key in keys]
            if any(status == "retrieved_invalid" for status in statuses):
                return "failed"
            if any(status in {"retrieved", "computed"} for status in statuses):
                return "passed"
            if any(status in {"partial", "proxy_only"} for status in statuses):
                return "warning"
            return "failed"
        statuses = [str((items.get(key) or {}).get("status", "")).lower() for key in keys]
        if any(status == "retrieved_invalid" for status in statuses):
            return "failed"
        if any(status in {"retrieved", "computed"} for status in statuses):
            return "passed"
        if any(status in {"partial", "proxy_only"} for status in statuses):
            return "warning"
        return "failed"
    rows = [
        ["Mandatory data scan", "passed" if scan else "failed", "Runs before final synthesis and records mandatory fact/gap status."],
        ["Earnings classifier", gate_status("earnings.actual_vs_consensus"), "Actual-vs-consensus table required before beat/miss or disappointment language."],
        ["CapEx resolver", gate_status("capex.guidance", "guidance.management"), "Management guidance must override annualized fallback when available."],
        ["FCF reconciliation", gate_status("cashflow.fcf_inputs", "cashflow.latest.fcf"), "OCF and CapEx must reconcile before FCF values can differ across sections."],
        ["Forward P/E resolver", "warning" if attempts or stage2c else "failed", "FY1/FY2/NTM EPS resolver must run before valuation remains blocked."],
        ["Short interest dependency", gate_status("positioning.short_interest", "short_interest.shares_short"), "Positioning claims require retrieved short interest or explicit DATA-MISSING penalty."],
        ["Analyst consensus dependency", gate_status("consensus.analyst"), "At least two aggregators required before single-firm action can be called consensus."],
        ["Debate validation", "warning", "Bull/Bear debate requires five rounds before Portfolio Manager verdict."],
        ["PM sanity gate", "failed" if not scan else "warning", "Consensus, guidance, short interest, evidence status, and debate status must pass before final verdict."],
    ]
    return rows


def _decision_integrity_overlay(
    *,
    baseline_decision: str,
    stage1: dict[str, Any],
    stage2b: dict[str, Any],
    stage2c: dict[str, Any],
) -> tuple[str, str, list[list[Any]]]:
    mandatory_rows = _effective_mandatory_rows(stage1, stage2b)
    critical_open = [
        row[0]
        for row in mandatory_rows
        if "Critical" in str(row[2]) and "Supported" not in str(row[1])
    ]
    point_blocked = _metric_point_estimate_blocked(stage2c)
    if critical_open or point_blocked:
        reasons = []
        if critical_open:
            reasons.append("decision-critical evidence is still unresolved")
        if point_blocked:
            reasons.append("at least one exact valuation point estimate is blocked")
        return (
            "Evidence-Gated Conditional Candidate",
            (
                f"The preserved baseline decision was {baseline_decision}, but "
                f"{' and '.join(reasons)}. The final report must keep conclusions constrained until those checks are resolved."
            ),
            mandatory_rows,
        )
    if baseline_decision:
        return (
            f"Evidence-Gated {baseline_decision.title()} Candidate",
            (
                "No decision-critical mandatory evidence block is open after downstream reinforcement; "
                "the baseline decision can be displayed as evidence-gated rather than unconditional."
            ),
            mandatory_rows,
        )
    return (
        "Evidence-Gated Candidate",
        "No concrete baseline decision was found; report remains evidence-gated.",
        mandatory_rows,
    )


def _cards(items: list[tuple[str, str, str]]) -> str:
    return "<div class=\"card-grid\">" + "\n".join(
        f"<div class=\"metric-card\"><div class=\"metric-label\">{_e(label)}</div><div class=\"metric-value\">{value}</div><div class=\"metric-note\">{_e(note)}</div></div>"
        for label, value, note in items
    ) + "</div>"


def _price_snapshot_rows(bar: dict[str, Any], metrics: dict[str, Any], report_context: ReportContext, evidence_store: EvidenceStore) -> list[list[Any]]:
    high_52 = metrics.get("week_52_high_bar") or {}
    low_52 = metrics.get("week_52_low_bar") or {}
    distance_high = metrics.get("distance_from_52w_high_pct")
    distance_low = metrics.get("distance_from_52w_low_pct")
    snapshot = evidence_store.value("market.snapshot.primary", {}) or {}
    provider_rows = snapshot.get("provider_reconciliation") if isinstance(snapshot, dict) else None
    provider_context = "Provider reconciliation: " + "; ".join(
        f"{row.get('provider')} {row.get('timestamp')} {row.get('bar_status')}"
        for row in (provider_rows or [])[:3]
    ) if provider_rows else "Provider reconciliation unavailable."
    price_label = "Latest close" if report_context.latest_price_is_eod else "Current / intraday price"
    return [
        ["Provider / timestamp", report_context.latest_price_source or "N/A", provider_context],
        ["Bar status", report_context.market_bar_status, "Only `eod_final` bars are labelled as latest close; partial bars are labelled current/intraday."],
        ["Latest market-data date", bar.get("date") or report_context.market_data_as_of or "N/A", "Latest normalized market-data bar used by this research packet."],
        ["Open", _money(bar.get("open")), "Daily open for the latest market-data bar."],
        ["High", _money(bar.get("high")), "Daily high for the latest market-data bar."],
        ["Low", _money(bar.get("low")), "Daily low for the latest market-data bar."],
        [price_label, _money(bar.get("close")), "Canonical price used in the report after provider/bar-status reconciliation."],
        ["Volume", _integer(bar.get("volume")), "Latest daily volume from normalized market data."],
        [
            "52-week high",
            _money(high_52.get("high")),
            f"{high_52.get('date', 'N/A')}; canonical price is {_pct(distance_high)} versus this high.",
        ],
        [
            "52-week low",
            _money(low_52.get("low")),
            f"{low_52.get('date', 'N/A')}; canonical price is {_pct(distance_low)} above this low.",
        ],
        [
            "Intraday resolver",
            "Attempted" if evidence_store.resolver_traces else "Not run",
            "If bid/ask/depth are unavailable, the trace records resolver attempts and the report does not pretend execution evidence is complete.",
        ],
    ]


def _table(headers: list[str], rows: list[list[Any]], css_class: str = "") -> str:
    head = "".join(f"<th>{_e(header)}</th>" for header in headers)
    body = []
    for row in rows:
        body.append("<tr>" + "".join(f"<td>{cell if isinstance(cell, SafeHtml) else _e(cell)}</td>" for cell in row) + "</tr>")
    return f'<div class="table-wrap {css_class}"><table><thead><tr>{head}</tr></thead><tbody>{"".join(body)}</tbody></table></div>'


class SafeHtml(str):
    pass


def _first_metric(stage2c: dict[str, Any]) -> dict[str, Any]:
    metrics = stage2c.get("reconciled_metrics") or []
    return metrics[0] if metrics else {}


def _bar_from_typed_market_evidence(stage1: dict[str, Any]) -> dict[str, Any]:
    value = (
        stage1.get("mandatory_equity_data_scan", {})
        .get("items", {})
        .get("market.latest_price", {})
        .get("value", {})
    )
    if not isinstance(value, dict):
        return {}
    close = _as_float(value.get("close"))
    if close is None:
        return {}
    return {
        "date": value.get("date"),
        "open": value.get("open"),
        "high": value.get("high"),
        "low": value.get("low"),
        "close": close,
        "volume": value.get("volume"),
        "source": "mandatory_equity_data_scan.market.latest_price",
    }


def _company_name(ticker: str, baseline: dict[str, Any]) -> str:
    for key in ("company", "company_name", "full_name"):
        value = baseline.get(key)
        if value:
            return str(value)
    for key in ("market_report", "fundamentals_report", "sentiment_report"):
        text = baseline.get(key) or ""
        match = re.search(rf"{re.escape(ticker)}\s*\(([^)]+)\)", text)
        if match:
            return match.group(1).strip()
        match = re.search(r"#\s+(.+?)\s*(?:\(|–|-)", text)
        if match:
            candidate = re.sub(r"^[^\w]+", "", match.group(1)).strip()
            if candidate and ticker.lower() not in candidate.lower():
                return candidate
    return ticker.upper()


def _logo_html(ticker: str) -> str:
    logo_path = None
    for ext in (".svg", ".png", ".jpg", ".jpeg", ".webp", ".ico"):
        candidate = LOGO_DIR / f"{ticker.upper()}{ext}"
        if candidate.exists() and candidate.stat().st_size > 0:
            logo_path = candidate
            break
    if logo_path:
        mime = {
            ".svg": "image/svg+xml",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
            ".ico": "image/x-icon",
        }.get(logo_path.suffix.lower(), "image/png")
        data = base64.b64encode(logo_path.read_bytes()).decode("ascii")
        return f'<div class="logo-frame"><img src="data:{mime};base64,{data}" alt="{_e(ticker)} logo"></div>'
    return f'<div class="logo-mark">{_e(str(ticker)[:4])}</div>'


def _source_map(*packets: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for packet in packets:
        for key in ("citation_sources", "refreshed_sources"):
            for source in packet.get(key, []) or []:
                sid = source.get("source_id")
                if sid:
                    out[sid] = source
        for source in packet.get("source_reliability_table", []) or []:
            sid = source.get("source_id") or source.get("provider")
            if sid:
                out.setdefault(
                    sid,
                    {
                        "source_id": sid,
                        "title": source.get("role") or source.get("publisher") or sid,
                        "publisher": source.get("publisher") or source.get("provider") or sid,
                        "url": source.get("url") or "",
                        "reliability_tier": source.get("reliability_tier") or source.get("reliability") or "",
                        "source_type": source.get("source_type") or source.get("role") or "",
                        "evidence_summary": source.get("notes") or "",
                        "limitations": [],
                    },
                )
    return out


def build_preview_html(
    *,
    baseline_full: dict[str, Any],
    baseline_fresh: dict[str, Any],
    stage1: dict[str, Any],
    stage2: dict[str, Any],
    stage2b: dict[str, Any],
    stage2c: dict[str, Any],
    stage2d: dict[str, Any],
    stage1b: dict[str, Any],
    delta: dict[str, Any],
    stage4: dict[str, Any],
) -> str:
    ticker = stage1.get("ticker", "UNKNOWN")
    company_name = sanitize_issuer_display_name(_company_name(ticker, baseline_fresh), ticker)
    assert_clean_issuer_display_name(company_name)
    asset_class = stage1.get("asset_class") or stage4.get("asset_class") or "Equity"
    logo_html = _logo_html(ticker)
    cycle = stage4.get("research_cycle") or stage1.get("research_cycle") or {}
    price = stage1.get("price_data_audit", {})
    bar = price.get("latest_bar", {}) or _bar_from_typed_market_evidence(stage1)
    metrics = price.get("computed_metrics", {})
    metric = _first_metric(stage2c)
    reported = metric.get("reported_values", {})
    usable = metric.get("usable_range", {})
    user_summary = stage1.get("user_supplied_evidence_audit", {}).get("summary", {})
    mft = stage1b.get("multi_timeframe_read", {})
    quality = reader_status(stage4.get("compliance_status"))
    source_by_id = _source_map(stage2, stage2b, stage2d, stage1)
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    market_date = cycle.get("market_data_as_of") or (bar.get("date") if isinstance(bar, dict) else None)
    report_dates = build_report_dates(
        market_data_as_of=market_date,
        requested_analysis_date=cycle.get("research_generated_at_utc", generated_at)[:10],
        report_mode=ReportMode.PRE_TRADE,
    )
    research_date = report_dates.research_date
    baseline_sections = _baseline_section_dict(baseline_fresh)
    evidence_store = _merged_equity_evidence_store(stage1, stage2, stage2b, baseline_fresh)
    repair_fixture = Path(__file__).resolve().parents[1] / "research_packets" / "pre_render_repair" / f"{str(ticker).upper()}_{research_date}_resolver_sources.json"
    repair_result = pre_render_repair_loop(
        evidence_store,
        company=company_name,
        fixture_path=repair_fixture if repair_fixture.exists() else None,
        allow_network=True,
    )
    evidence_store = repair_result.store
    safety = build_final_report_safety_result(baseline_sections, evidence_store)
    baseline_sections = safety.sanitized_sections
    baseline_proposals = _baseline_proposal_map(baseline_fresh)
    baseline_decision = _baseline_decision(baseline_fresh)
    report_context = _build_report_context(
        ticker=ticker,
        company_name=company_name,
        report_dates=report_dates,
        bar=bar,
        metrics=metrics,
        price_audit=price,
    )
    final_decision = _build_final_decision(
        baseline_decision=baseline_decision,
        safety=safety,
        evidence_store=evidence_store,
    )
    report_title = (
        "DIAGNOSTIC RESEARCH PACKET - NOT FINAL"
        if not repair_result.institutional_mode_allowed
        else "STAGE 5 V2 FINAL INSTITUTIONAL REPORT"
    )
    report_heading_suffix = "Diagnostic Research Packet" if not repair_result.institutional_mode_allowed else "Institutional Research Report"
    report_mode_note = (
        "Critical evidence gates remain unresolved after the full dynamic RAG repair chain. This packet is diagnostic and does not provide an executable final action."
        if not repair_result.institutional_mode_allowed
        else "Critical evidence gates passed after dynamic RAG repair; reader-facing sections are rendered as an institutional report."
    )
    baseline_sections = _constrain_rejected_decision_sections(baseline_sections, safety, baseline_decision)
    institutional_sections = {
        "final_trade_decision": _final_decision_markdown(final_decision) + _rich_upstream_appendix("Sanitized Portfolio Manager Context", baseline_sections.get("final_trade_decision")),
        "market_report": _technical_analysis_markdown(report_context, metrics, stage1b, stage4) + _rich_upstream_appendix("Sanitized Upstream Technical Narrative", baseline_sections.get("market_report")),
        "news_report": _market_analysis_markdown(report_context, stage2d, evidence_store) + _rich_upstream_appendix("Sanitized Upstream Market and Catalyst Narrative", baseline_sections.get("news_report")),
        "fundamentals_report": _fundamental_analysis_markdown(evidence_store, final_decision) + _rich_upstream_appendix("Sanitized Upstream Fundamental Narrative", baseline_sections.get("fundamentals_report")),
        "sentiment_report": _sentiment_positioning_markdown(evidence_store) + _rich_upstream_appendix("Sanitized Upstream Sentiment Narrative", baseline_sections.get("sentiment_report")),
        "investment_plan": _research_manager_markdown(baseline_sections, safety, evidence_store),
        "trader_investment_plan": _execution_plan_markdown(final_decision, metrics, report_context.latest_price) + _rich_upstream_appendix("Sanitized Upstream Trader Narrative", baseline_sections.get("trader_investment_plan")),
    }
    baseline_sections = institutional_sections
    final_posture, final_posture_reason, mandatory_rows = _decision_integrity_overlay(
        baseline_decision=baseline_decision,
        stage1=stage1,
        stage2b=stage2b,
        stage2c=stage2c,
    )
    specific_forward_pe = reported.get("tradingagents_reported_forward_pe")
    specific_forward_pe_label = (
        f"{_num(specific_forward_pe)}x"
        if specific_forward_pe is not None
        else "the reported point estimate"
    )

    horizon_rows = []
    for item in stage4.get("horizon_decisions", []):
        horizon_rows.append(
            [
                item.get("horizon", ""),
                SafeHtml(_badge(item.get("classification"))),
                item.get("evidence_status", ""),
                item.get("rationale", ""),
            ]
        )

    user_rows = [
        [
            item.get("detected_timeframe", ""),
            item.get("latest_timestamp", ""),
            _money(item.get("latest_close")),
            _vwap_cell(item),
            _rsi_cell(item),
            _adx_cell(item),
            _volume_cell(item),
        ]
        for item in sorted(
            stage1b.get("feature_summaries", []),
            key=lambda item: _timeframe_sort_key(item.get("detected_timeframe")),
        )
    ]
    if not user_rows:
        user_rows = [
            [
                "1d",
                bar.get("date", ""),
                _money(bar.get("close")),
                _signal_metric_cell(
                    "Dynamic resolver",
                    f"EMA10 {_money(metrics.get('ema_10'))}; VWMA20 {_money(metrics.get('vwma_20'))}",
                ),
                _signal_metric_cell("Dynamic resolver", f"RSI {_num(metrics.get('rsi_14'))}"),
                _signal_metric_cell("Dynamic resolver", "ADX unavailable from daily fallback"),
                _signal_metric_cell("Dynamic resolver", f"Vol {_integer(bar.get('volume'))}; MA {_integer(metrics.get('volume_ma_20'))}"),
            ]
        ]

    source_rows = []
    for source in sorted(source_by_id.values(), key=lambda x: (x.get("reliability_tier", ""), x.get("source_id", ""))):
        source_rows.append(
            [
                SafeHtml(_source_link(source)),
                source.get("publisher", ""),
                source.get("reliability_tier", ""),
                source.get("source_type", ""),
                source.get("evidence_summary", ""),
                "; ".join(source.get("limitations") or []),
            ]
        )

    valuation_rows = [
        ["TradingAgents reported Forward P/E", _num(reported.get("tradingagents_reported_forward_pe")), SafeHtml(_badge(metric.get("specific_claim_status", "Blocked"))), "Specific point estimate not accepted because the exact EPS input is not independently sourced in the evidence packet."],
        ["StockAnalysis reported Forward P/E", _num(reported.get("stockanalysis_reported_forward_pe")), "Scenario input", "Secondary valuation data point used in the assumption-based range."],
        ["External annualized EPS scenario", _num(reported.get("computed_using_external_annualized_eps")), "Computed scenario", "External EPS estimate annualized against report-timestamp price where available."],
        ["TradingAgents EPS scenario", _num(reported.get("computed_using_tradingagents_forward_eps")), "Computed scenario", "Agent-supplied forward EPS computed against report-timestamp price; not independently validated unless externally sourced."],
        ["Usable Forward P/E Range", f"{_num(usable.get('low'))}x to {_num(usable.get('high'))}x", SafeHtml(_badge(metric.get("reconciliation_status"))), usable.get("business_interpretation", "")],
    ]

    catalyst_rows = []
    for claim in stage2d.get("refreshed_claims", []):
        links = []
        for sid in claim.get("source_ids", []):
            source = source_by_id.get(sid, {"source_id": sid, "title": sid})
            links.append(_source_link(source))
        catalyst_rows.append([claim.get("claim", ""), SafeHtml(_badge(claim.get("refresh_status"))), SafeHtml("<br>".join(links)), claim.get("rationale", "")])

    pivot_level = metrics.get("bb_middle") or metrics.get("ema_10") or bar.get("close")
    reclaim_level = metrics.get("ema_10") or metrics.get("vwma_20") or bar.get("close")
    deep_pullback = metrics.get("bb_lower") or metrics.get("sma_50")
    close_value = bar.get("close") if isinstance(bar, dict) else None
    key_levels = [
        [f"Immediate {classify_price_level(pivot_level, close_value)}", _money(pivot_level), "Nearest normalized pivot from available Bollinger/EMA/close evidence; a break lower weakens the short-term setup."],
        [f"Medium {classify_price_level(metrics.get('sma_50'), close_value)}", _money(metrics.get("sma_50")), "50-day moving average classified by its position versus latest close."],
        [f"Long-term {classify_price_level(metrics.get('sma_200'), close_value)}", _money(metrics.get("sma_200")), "200-day moving average classified by its position versus latest close."],
        [f"Short-term {classify_price_level(reclaim_level, close_value)} zone", _money(reclaim_level), "10 EMA / VWMA reference classified by its position versus latest close."],
        ["Bullish confirmation", "Baseline-defined resistance / volume-confirmed breakout", "Use the preserved baseline technical section for exact resistance language; Titan requires confirmation before execution."],
        ["Deep pullback watch", _money(deep_pullback), "Lower-band/deeper pullback zone where waning volume and RSI reset would matter."],
    ]
    diagnostic_appendices = f"""
  <section class="section appendix-section">
    <h2>Appendix A: Excluded Claims / Errors and Recommendations</h2>
    <p>These items were generated by upstream agents but removed from the normal report narrative because required evidence was missing, blocked, contested, or not promoted into the typed evidence store.</p>
    {_table(["Agent", "Severity", "Exact Rejected Claim", "Why It Failed", "Correction Rule", "Recurrence"], _excluded_claim_rows(safety))}
  </section>
  <section class="section appendix-section">
    <h2>Appendix B: Mandatory Evidence Integrity Check</h2>
    {_table(["Evidence Block", "Effective Status", "Severity", "Attempted Source Classes", "Decision Impact", "Validation Result"], mandatory_rows, "diagnostic-table mandatory-evidence-table")}
  </section>
  <section class="section appendix-section">
    <h2>Appendix C: Code-Enforced Equity Evidence Scan</h2>
    {_table(["Evidence Key", "Status", "Source / Attempted Class", "As-Of", "Value / Constrained Conclusion"], _mandatory_scan_rows(evidence_store), "diagnostic-table evidence-scan-table")}
  </section>
  <section class="section appendix-section">
    <h2>Appendix D: Global Equity Enforcement Gates</h2>
    {_table(["Gate", "Status", "Enforcement Rule"], _equity_enforcement_rows(stage1, stage2c, evidence_store), "diagnostic-table enforcement-table")}
  </section>
  <section class="section appendix-section">
    <h2>Appendix E: Dynamic RAG Resolver Trace</h2>
    <p>Critical evidence can remain incomplete only after this API/issuer/SEC/news/aggregator/web/search-expansion/extraction-retry chain has run and recorded the result.</p>
    {_table(["Evidence Key", "Final Status", "Resolver Chain", "Queries", "Selected Source", "Failure / Result"], _resolver_trace_rows(evidence_store), "diagnostic-table resolver-trace-table")}
  </section>
"""

    css = _css()
    html_doc = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{_e(ticker)} Stage 5 v2 Institutional Preview</title>
  <style>{css}</style>
</head>
<body>
<main class="report theme-{_e(str(asset_class).lower().replace(' ', '-'))}">
  <section class="hero">
    <div>
      <div class="brand-row">
        {logo_html}
        <div>
          <div class="brand-name">{_e(company_name)}</div>
          <div class="brand-meta">{_e(ticker)} · {_e(asset_class)} Research</div>
        </div>
      </div>
      <p class="eyebrow">{_e(report_title)}</p>
      <h1>{_e(company_name)} ({_e(ticker)}) {_e(report_heading_suffix)}</h1>
      <p class="subtitle">Fusion of DeepSeek baseline structure with Titan evidence graph, dynamic RAG repair, valuation reconciliation, supplemental technical evidence, and horizon validation. {_e(report_mode_note)}</p>
    </div>
    <div class="quality-card">
      <div class="quality-title">Research Quality Status</div>
      <div>{_badge(stage4.get("compliance_status"))}</div>
      <p>{_e(quality.summary)}</p>
    </div>
    <div class="hero-legal">
      <strong>Research-only:</strong> Informational decision-support report only; not financial, investment, legal, tax, accounting, or brokerage advice, and not a solicitation or recommendation to transact. <strong>Logo notice:</strong> The {_e(company_name)} logo or ticker mark is used solely for issuer identification and does not imply affiliation, sponsorship, approval, or endorsement by {_e(company_name)}.
    </div>
  </section>

  {_cards([
      ("Final Reader Action", f"<strong>{_e(final_decision.rating)}</strong>", final_decision.actionability),
      ("Validated Horizon", f"<strong>{_e(stage4.get('validated_trading_horizon', 'N/A'))}</strong>", "Intraday, swing, positional, and long-term are evaluated independently."),
      ("Latest Close" if report_context.latest_price_is_eod else "Current / Intraday Price", f"<strong>{_money(bar.get('close'))}</strong>", f"Latest OHLC date: {bar.get('date') or report_dates.market_data_as_of or 'N/A'}. Analysis date: {report_dates.research_date}. Intended trade date: {report_dates.intended_trade_date or 'N/A'}. Bar status: {report_context.market_bar_status}."),
      ("User Evidence", f"<strong>{user_summary.get('file_count', 0)} files / {len(stage1b.get('feature_summaries', []))} timeframes</strong>", "TradingView-style CSV evidence is supplemental and deduplicated."),
  ])}

  <section class="section price-snapshot">
    <h2><span class="section-icon">▣</span>Price Snapshot</h2>
    <p>Key price facts are shown before interpretation so the reader can anchor the report to the exact market-data bar used by the research cycle.</p>
    {_table(["Item", "Value", "Context"], _price_snapshot_rows(bar, metrics, report_context, evidence_store))}
  </section>

  <section class="section horizon-matrix">
    <h2><span class="section-icon">▣</span>Horizon Matrix</h2>
    <p>All trading horizons are shown before the narrative so the reader can see which timeframes are supported, conditional, or blocked.</p>
    {_table(["Horizon", "Classification", "Evidence Status", "Rationale"], horizon_rows)}
  </section>

  <section class="section executive-bridge">
    <h2><span class="section-icon">🧭</span>How to Read This Preview</h2>
    <p>This institutional version renders reader-facing sections from canonical context and reconciled typed evidence. Raw baseline role outputs are diagnostic artifacts and do not control final action, dates, prices, source status, or technical interpretation.</p>
    {_table(["Conclusion Layer", "Reader Meaning", f"Current {_e(ticker)} Read"], [
        ["Canonical report context", "Dates, prices, levels, and final action are rendered from typed context.", f"{report_context.research_date}; latest price {_money(report_context.latest_price)}; bar status {report_context.market_bar_status}."],
        ["FinalDecision object", "Cover, summary, decision, and trader sections share one reader-facing action.", f"{final_decision.rating}; confidence {final_decision.confidence}."],
        ["Baseline role outputs", "Raw agent outputs are diagnostics, not controlling narrative.", "Rejected claims are isolated in appendices and operational-learning records."],
    ])}
    <div class="status-strip">
      <span>{_badge('Validated')} Fully supported items are usable.</span>
      <span>{_badge('Conditional Candidate')} Candidate ideas require confirmation.</span>
      <span>{_badge('Blocked')} Specific unsupported point estimates are isolated.</span>
      <span>{_badge('Usable Range - Assumption-Based')} Scenario ranges remain usable with assumptions.</span>
    </div>
  </section>

  {_baseline_block(
      "Final Trade Decision",
      "Screened Baseline Content",
      baseline_sections["final_trade_decision"],
      icon="🎯",
      note="Titan overlay: baseline decision text is screened before display. Excluded claims are listed in the appendices and cannot support the final conclusion.",
  )}

  {_baseline_block(
      "Technical Analysis",
      "Typed Evidence Section",
      baseline_sections["market_report"],
      icon="📈",
      note="Titan overlay: the technical report is retained in full. Later user CSV evidence and Stage 4 horizon logic add confirmation requirements for live tape, session liquidity, and opening-range structure before any intraday execution call.",
  )}

  {_baseline_block(
      "Market & Catalyst Analysis",
      "Typed Evidence Section",
      baseline_sections["news_report"],
      icon="📰",
      note="Titan overlay: this section keeps the baseline news and macro structure. Stage 2D refreshed stale catalyst and earnings-timing claims; proxy evidence remains useful context but not direct issuer validation.",
  )}

  {_baseline_block(
      "Fundamental Analysis",
      "Typed Evidence Section",
      baseline_sections["fundamentals_report"],
      icon="📊",
      note=f"Titan overlay: the fundamental narrative is preserved. The exact forward P/E point estimate ({specific_forward_pe_label}) remains blocked unless the exact forward EPS input is independently sourced; the broader assumption-based forward P/E range remains usable for scenarios.",
  )}

  {_baseline_block(
      "Sentiment & Positioning",
      "Typed Evidence Section",
      baseline_sections["sentiment_report"],
      icon="🔎",
      note=f"Titan timestamp note: research run date is {_pretty_date(research_date)}. Any baseline lookback period or market-data as-of date ending {_pretty_date(market_date)} is preserved as part of the original baseline text.",
  )}

  {_baseline_block(
      "Research Manager Adjudication",
      "Typed Evidence Section",
      baseline_sections["investment_plan"],
      icon="⚖️",
      note="Titan overlay: retain the debate structure and full reasoning. Use the Titan addendum below for reconciled valuation, source audit, and horizon validation.",
  )}

  {_baseline_block(
      "Debate & Risk Outcomes",
      "Sanitized TradingAgents Debate",
      _debate_outcomes_markdown(baseline_fresh, safety),
      icon="⚔️",
      note="Titan overlay: debate and risk-team outputs are preserved as structured, sanitized synthesis. Unsupported claims remain governed by the excluded-claim and resolver-trace appendices.",
  )}

  {_baseline_block(
      "Trader Execution Plan",
      "Typed Evidence Section",
      baseline_sections["trader_investment_plan"],
      icon="💡",
      note="Titan overlay: execution instructions must remain conditional until the relevant horizon-specific evidence is confirmed.",
  )}

  <section class="section">
    <h2><span class="section-icon">🧩</span>TITAN Addendum A: Decision Reconciliation Overlay</h2>
    <div class="decision-grid">
      <div class="callout">
        <h3>Decision</h3>
        <p><strong>{_e(final_posture)} / Wait for Confirmed Horizon Evidence.</strong> The fresh TradingAgents run produced a {_e(baseline_decision)} decision. Stage 5 v2 preserves that baseline conclusion, but it does not convert it into an unconditional trade call. {_e(final_posture_reason)}</p>
      </div>
      <div class="callout muted">
        <h3>Why This Is Evidence-Gated</h3>
        <p>The report distinguishes the preserved baseline decision from Titan validation. SEC-backed fundamentals, external citations, user-supplied technical evidence, and graph status are considered together; where a required block is absent, proxy-only, contradictory, or assumption-based, the limitation remains visible rather than being hidden inside a single headline stance.</p>
      </div>
    </div>
    <h3>Key Evidence from the Debate</h3>
    <div class="three-col">
      <div><h4>Aggressive / Bull Case</h4><p>Positive baseline thesis elements, sector demand, and long-term moving-average structure remain visible where supported by the evidence packet.</p></div>
      <div><h4>Conservative / Bear Case</h4><p>Distribution volume, short-term trend loss, momentum deterioration, cyclical risk, beta, and valuation uncertainty justify caution where present.</p></div>
      <div><h4>Neutral / Synthesis</h4><p>Long-term trend is not broken, but execution should remain staged until price either confirms support, reclaims resistance, or resets into a better reward-to-risk zone.</p></div>
    </div>
  </section>

  <section class="section">
    <h2>TITAN Addendum B: Normalized Technical Evidence Overlay</h2>
    <p><strong>Analysis date:</strong> {_e(cycle.get('requested_analysis_date'))} | <strong>Market data as of:</strong> {_e(cycle.get('market_data_as_of'))} | <strong>Latest close:</strong> {_money(bar.get('close'))}</p>
    <h3>Price Action Overview</h3>
    <p>{_e(ticker)} rallied roughly {_pct(metrics.get('recent_swing_move_pct'))} across the recent computed swing window before pulling back into the latest market-data close. The latest evidence distinguishes medium/long-term structure from short-term momentum pressure.</p>
    <h3>Moving Averages and Trend Structure</h3>
    {_table(["Indicator", "Value", "Interpretation"], [
        ["10 EMA", _money(metrics.get("ema_10")), _relation_text(close_value, metrics.get("ema_10"), "10 EMA")],
        ["50 SMA", _money(metrics.get("sma_50")), _relation_text(close_value, metrics.get("sma_50"), "50 SMA")],
        ["200 SMA", _money(metrics.get("sma_200")), _relation_text(close_value, metrics.get("sma_200"), "200 SMA")],
        ["20 VWMA", _money(metrics.get("vwma_20")), _relation_text(close_value, metrics.get("vwma_20"), "20 VWMA")],
    ])}
    <h3>Momentum, Volatility, and Volume</h3>
    <p>The baseline MACD/RSI narrative remains important: momentum, RSI, and volume evidence are interpreted against the latest market-data window. Stage 1 flags a recent high-volume down day as a distribution warning only when the generic volume/down-day criteria are met.</p>
    <h3>Key Levels and Scenario Triggers</h3>
    {_table(["Level / Trigger", "Price", "Business Use"], key_levels)}
  </section>

  <section class="section">
    <h2>TITAN Addendum C: User-Supplied Multi-Timeframe Technical Evidence</h2>
    <p>{_e(mft.get('summary_read'))}</p>
    {_table(["TF", "Latest Timestamp", "Close", "VWAP", "RSI", "ADX", "Volume"], user_rows, "technical-mtf-table")}
    <p class="note">Business interpretation: user CSV evidence is optional and supplemental. When CSV files are absent, the dynamic technical resolver supplies comparable market/technical evidence from normalized provider data. When CSV files are older than the canonical market snapshot, they are treated as prior-session context and cannot override current OHLCV.</p>
  </section>

  <section class="section">
    <h2>TITAN Addendum D: Citation Refresh and Catalyst Evidence Overlay</h2>
    <p>Stage 2D refreshed stale catalyst and earnings-timing items so they do not disappear from repeat research solely because the fresh LLM run omitted them. Proxy evidence remains useful, but it is not treated as direct issuer revenue validation.</p>
    {_table(["Claim", "Reader-Facing Status", "Sources", "Rationale"], catalyst_rows)}
    <h3>Macro and Sector Backdrop</h3>
    <p>Official macro evidence and reputable industry evidence support the broader market backdrop when present in the source ledger. Sector, supplier, customer, commodity, or geopolitical evidence may be useful as indirect read-through context, but it must stay labeled as proxy evidence unless it directly validates the issuer's own facts.</p>
  </section>

  <section class="section">
    <h2>TITAN Addendum E: SEC Fundamentals Evidence Overlay</h2>
    <p>SEC EDGAR evidence is available for issuer-backed core financial facts, including revenue, earnings, assets, liabilities, operating income, stockholders' equity, and diluted EPS concepts. The baseline's strong fundamental narrative is therefore preserved, but long-term validation still requires a dedicated moat, cycle-normalized return, and valuation packet.</p>
    {_table(["Field", "Value"], [
        ["SEC status", stage1.get("sec_fundamentals_audit", {}).get("status", "N/A")],
        ["CIK", stage1.get("sec_fundamentals_audit", {}).get("cik", "N/A")],
        ["Available fact keys", ", ".join(stage1.get("sec_fundamentals_audit", {}).get("fact_keys", []))],
        ["Latest filing", (stage1.get("sec_fundamentals_audit", {}).get("recent_filings") or [{}])[0].get("form", "N/A")],
    ])}
  </section>

  <section class="section">
    <h2>TITAN Addendum F: Valuation and Metric Reconciliation</h2>
    <p>{_e(metric.get('conclusion', 'No valuation reconciliation was available.'))}</p>
    {_table(["Metric", "Value", "Reader-Facing Status", "Business Meaning"], valuation_rows)}
  </section>

  <section class="section">
    <h2>TITAN Addendum G: Validated Trading Horizon</h2>
    <p>Each horizon is evaluated independently. These labels are reader-facing descriptions, not internal shorthand.</p>
    {_table(["Horizon", "Reader-Facing Classification", "Evidence Status", "Why It Was Assigned"], horizon_rows)}
  </section>

  <section class="section">
    <h2>TITAN Addendum H: Evidence Graph and Source Audit</h2>
    <p>The evidence graph preserves supported, updated, newly discovered, and blocked items. The latest delta shows {_e(delta.get('delta_counts', {}).get('Unchanged Supported', 0))} unchanged supported items, {_e(delta.get('delta_counts', {}).get('Updated', 0))} updated items, {_e(delta.get('delta_counts', {}).get('Newly Discovered', 0))} newly discovered items, and {_e(delta.get('delta_counts', {}).get('Still Blocked', 0))} still-blocked item. The remaining blocked item is the forward valuation point estimate, not the entire valuation section.</p>
    <div class="status-strip">
      <span>{_badge('Supported')} Supported facts remain usable.</span>
      <span>{_badge('Blocked')} Specific conflicts remain visible.</span>
      <span>{_badge('Usable Range - Assumption-Based')} Scenario ranges require caveats.</span>
    </div>
  </section>

  <section class="section">
    <h2>TITAN Addendum I: Self-Audit and Research Quality Notes</h2>
    <p><strong>Research Quality Status:</strong> {_badge(stage4.get('compliance_status'))}</p>
    <p>{_e(quality.summary)}</p>
    <ul>
      <li>No full-framework validation is claimed while evidence blockers remain.</li>
      <li>No long-term thesis is used to validate intraday execution.</li>
      <li>Proxy evidence is identified as indirect context, not direct issuer validation.</li>
      <li>Open validation items are presented as audit discipline, not report failure.</li>
    </ul>
  </section>

  {diagnostic_appendices}

  <section class="section references">
    <h2>TITAN Addendum J: Citations and References</h2>
    {_table(["Source", "Publisher", "Reliability", "Type", "Evidence Summary", "Limitations"], source_rows, "citations-table")}
  </section>
</main>
</body>
</html>"""
    return html_doc


def write_preview(
    *,
    baseline_full_path: Path,
    baseline_fresh_path: Path,
    stage1_path: Path,
    stage2_path: Path,
    stage2b_path: Path,
    stage2c_path: Path,
    stage2d_path: Path,
    stage1b_path: Path,
    delta_path: Path,
    stage4_path: Path,
    output_dir: Path,
) -> PreviewArtifacts:
    baseline_full = _load_json(baseline_full_path)
    baseline_fresh = _load_json(baseline_fresh_path)
    stage1 = _load_json(stage1_path)
    stage2 = _load_json(stage2_path)
    stage2b = _load_json(stage2b_path)
    stage2c = _load_json(stage2c_path)
    stage2d = _load_json(stage2d_path)
    stage1b = _load_json(stage1b_path)
    delta = _load_json(delta_path)
    stage4 = _load_json(stage4_path)

    output_dir.mkdir(parents=True, exist_ok=True)
    html_path = output_dir / "preview.html"
    manifest_path = output_dir / "preview_manifest.json"
    html_text = build_preview_html(
        baseline_full=baseline_full,
        baseline_fresh=baseline_fresh,
        stage1=stage1,
        stage2=stage2,
        stage2b=stage2b,
        stage2c=stage2c,
        stage2d=stage2d,
        stage1b=stage1b,
        delta=delta,
        stage4=stage4,
    )
    html_path.write_text(html_text, encoding="utf-8")
    evidence_store = _merged_equity_evidence_store(stage1, stage2, stage2b, baseline_fresh)
    ticker = stage1.get("ticker", "UNKNOWN")
    issuer_name = sanitize_issuer_display_name(_company_name(ticker, baseline_fresh), ticker)
    repair_date = (stage4.get("research_cycle") or stage1.get("research_cycle") or {}).get("research_generated_at_utc", "")[:10] or (stage1.get("trade_date") or "")
    repair_fixture = Path(__file__).resolve().parents[1] / "research_packets" / "pre_render_repair" / f"{str(ticker).upper()}_{repair_date}_resolver_sources.json"
    repair_result = pre_render_repair_loop(
        evidence_store,
        company=issuer_name,
        fixture_path=repair_fixture if repair_fixture.exists() else None,
        allow_network=True,
    )
    evidence_store = repair_result.store
    safety = build_final_report_safety_result(_baseline_section_dict(baseline_fresh), evidence_store)
    cycle = stage4.get("research_cycle") or stage1.get("research_cycle") or {}
    _record_safety_errors(
        output_dir,
        stage1.get("ticker", "UNKNOWN"),
        cycle.get("research_run_id") or output_dir.name,
        safety,
    )
    manifest_report_dates = build_report_dates(
        market_data_as_of=(stage1.get("research_cycle") or {}).get("market_data_as_of"),
        requested_analysis_date=(stage4.get("research_cycle") or stage1.get("research_cycle") or {}).get("research_generated_at_utc", "")[:10] or None,
        report_mode=ReportMode.PRE_TRADE,
    )
    price = stage1.get("price_data_audit", {})
    bar = price.get("latest_bar", {}) or _bar_from_typed_market_evidence(stage1)
    metrics = price.get("computed_metrics", {}) or {}
    manifest_context = _build_report_context(
        ticker=ticker,
        company_name=issuer_name,
        report_dates=manifest_report_dates,
        bar=bar,
        metrics=metrics,
        price_audit=price,
    )
    manifest_decision = _build_final_decision(
        baseline_decision=_baseline_decision(baseline_fresh),
        safety=safety,
        evidence_store=evidence_store,
    )
    manifest = {
        "stage": "Stage 5 v2 HTML Preview",
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "html_path": str(html_path),
        "final_markdown_pdf_paused": True,
        "baseline_integrity": _baseline_integrity_summary(baseline_fresh),
        "baseline_title_audit": _baseline_title_audit(baseline_fresh, html_text),
        "baseline_proposal_map": _baseline_proposal_map(baseline_fresh),
        "report_dates": manifest_report_dates.to_dict(),
        "report_context": manifest_context.to_dict(),
        "final_decision": manifest_decision.to_dict(),
        "issuer_metadata": {
            "ticker": ticker,
            "issuer_display_name": issuer_name,
        },
        "report_mode": ReportMode.PRE_TRADE.value,
        "render_mode": "diagnostic_research_packet" if not repair_result.institutional_mode_allowed else "institutional_report",
        "dynamic_rag_repair": {
            "repaired_keys": repair_result.repaired_keys,
            "unresolved_keys": repair_result.unresolved_keys,
            "institutional_mode_allowed": repair_result.institutional_mode_allowed,
            "resolver_traces": [trace.__dict__ for trace in repair_result.traces],
        },
        "final_report_safety": {
            "accepted_claims": safety.accepted_claims,
            "rejected_claims": [claim.__dict__ for claim in safety.rejected_claims],
            "unresolved_gaps": safety.unresolved_gaps,
            "self_audit_passed": safety.self_audit_passed,
        },
        "promoted_equity_evidence_store": evidence_store.to_dict(),
        "source_paths": {
            "baseline_full": str(baseline_full_path),
            "baseline_fresh": str(baseline_fresh_path),
            "stage1": str(stage1_path),
            "stage2": str(stage2_path),
            "stage2b": str(stage2b_path),
            "stage2c": str(stage2c_path),
            "stage2d": str(stage2d_path),
            "stage1b": str(stage1b_path),
            "delta": str(delta_path),
            "stage4": str(stage4_path),
        },
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return PreviewArtifacts(html_path=html_path, manifest_path=manifest_path)


def _css() -> str:
    return """
:root{--ink:#1f2937;--muted:#667085;--line:#cfd6df;--blue:#123f68;--blue2:#edf5fd;--green:#15945b;--amber:#b47a00;--red:#be334a;--bg:#f3f5f7;--card:#fff;--soft:#f8fafc}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.62 "Segoe UI",Arial,sans-serif}.report{max-width:1240px;margin:0 auto;padding:34px}.hero{display:grid;grid-template-columns:1fr 390px;gap:24px;align-items:stretch;background:linear-gradient(135deg,#0d2a49,#1c658e);color:white;border-radius:12px;padding:34px;margin-bottom:22px;box-shadow:0 12px 28px rgba(16,34,61,.18)}.eyebrow{text-transform:uppercase;letter-spacing:.09em;font-size:12px;color:#c9e6fb;margin:0 0 8px}.hero h1{font-size:40px;line-height:1.08;margin:0 0 12px}.subtitle{font-size:17px;color:#e4f1fb;max-width:760px}.quality-card{background:rgba(255,255,255,.13);border:1px solid rgba(255,255,255,.32);border-radius:10px;padding:18px}.quality-title,.section-kicker{text-transform:uppercase;letter-spacing:.08em;font-size:11px;color:var(--muted);font-weight:700;margin-bottom:8px}.quality-title{color:#d9edf9}.section{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:28px;margin:22px 0;box-shadow:0 2px 8px rgba(16,34,61,.05)}.baseline-section{padding:30px 34px}.executive-bridge{border-left:6px solid var(--blue)}h2{font-size:25px;color:#1d2939;margin:0 0 16px;display:flex;align-items:center;gap:10px}.section-icon{font-size:25px}h3{font-size:20px;margin:24px 0 10px;color:#202b3c}.md-heading{display:flex;align-items:center;gap:9px}h4{margin:0 0 8px;color:#24364b}p{margin:0 0 13px}.baseline-content p{max-width:1140px}.baseline-content hr{border:0;border-top:2px solid #d4dae2;margin:26px 0}.card-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:0 0 22px}.metric-card{background:white;border:1px solid var(--line);border-radius:10px;padding:16px;box-shadow:0 1px 4px rgba(16,34,61,.04)}.metric-label{text-transform:uppercase;color:var(--muted);font-size:11px;letter-spacing:.06em}.metric-value{font-size:18px;margin:7px 0;color:var(--ink)}.metric-note{font-size:12px;color:var(--muted)}.decision-grid,.two-col{display:grid;grid-template-columns:1fr 1fr;gap:16px}.three-col{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}.callout,.titan-note{border-left:5px solid var(--blue);background:var(--blue2);padding:15px 16px;border-radius:7px;margin:12px 0}.callout.muted{border-left-color:#7b8794;background:#f2f5f8}.proposal{border-left:5px solid #44546a;background:#f4f6f8;padding:15px 16px;margin:18px 0;font-weight:600}.case{border-radius:8px;padding:16px;border:1px solid var(--line)}.case.bull{background:#eef8f2}.case.bear{background:#fff2f2}.table-wrap{overflow-x:auto;margin:14px 0 22px}table{width:100%;border-collapse:collapse;background:white}th{background:#eef2f6;color:#111827;text-align:left;font-weight:800}th,td{border:1px solid #c9ced6;padding:9px 12px;vertical-align:top;font-size:14px}td:first-child{font-weight:600}.baseline-table table{width:auto;min-width:58%;max-width:100%}.baseline-table th{text-align:center}.signal{display:inline-flex;gap:7px;align-items:center;white-space:normal;min-width:0}.signal-dot{width:13px;height:13px;min-width:13px;border-radius:999px;display:inline-block;box-shadow:inset 0 -2px 3px rgba(0,0,0,.18),0 1px 2px rgba(16,34,61,.18)}.signal-red{color:#9f1239}.signal-red .signal-dot{background:linear-gradient(135deg,#fb7185,#be123c)}.signal-green{color:#087443}.signal-green .signal-dot{background:linear-gradient(135deg,#6ee7a8,#10a466)}.signal-amber{color:#a16207}.signal-amber .signal-dot{background:linear-gradient(135deg,#facc5c,#d69b12)}.signal-neutral{color:#475467}.signal-neutral .signal-dot{background:#64748b}.badge{display:inline-block;border-radius:999px;padding:4px 9px;font-size:12px;font-weight:800;border:1px solid transparent}.badge.positive{background:#e6f6ed;color:var(--green);border-color:#b6e2c7}.badge.watch{background:#fff5d8;color:var(--amber);border-color:#f0d28a}.badge.caution{background:#fff2e8;color:#9a4b00;border-color:#f2c59e}.badge.blocked{background:#fdecec;color:var(--red);border-color:#efb6b6}.badge.neutral{background:#edf1f5;color:#4a5565;border-color:#cbd5df}.note{color:var(--muted);font-size:13px;border-left:3px solid #c7d4e2;padding-left:12px}.status-strip{display:flex;flex-wrap:wrap;gap:10px}.references td{font-size:12px}.references a,.citations-table a{color:#064e8a;text-decoration:underline;text-decoration-thickness:1.5px;text-underline-offset:2px;font-weight:700}a{color:#075d9b;text-decoration:underline;text-underline-offset:2px}a:hover{text-decoration-thickness:2px}ul,ol{margin-top:7px;margin-bottom:18px}li{margin:5px 0}strong{font-weight:800}@media(max-width:900px){.hero,.card-grid,.decision-grid,.two-col,.three-col{grid-template-columns:1fr}.report{padding:18px}.hero h1{font-size:30px}.baseline-section{padding:24px 18px}}
.technical-mtf-table,.citations-table,.diagnostic-table{overflow-x:visible}.technical-mtf-table table,.citations-table table,.diagnostic-table table{table-layout:fixed;width:100%;min-width:0}.technical-mtf-table th,.technical-mtf-table td,.citations-table th,.citations-table td,.diagnostic-table th,.diagnostic-table td{white-space:normal;overflow-wrap:anywhere;word-break:normal;line-height:1.42}.diagnostic-table th,.diagnostic-table td{font-size:12px;padding:7px 9px}.technical-mtf-table th:nth-child(1),.technical-mtf-table td:nth-child(1){width:7%}.technical-mtf-table th:nth-child(2),.technical-mtf-table td:nth-child(2){width:18%}.technical-mtf-table th:nth-child(3),.technical-mtf-table td:nth-child(3){width:9%}.technical-mtf-table th:nth-child(4),.technical-mtf-table td:nth-child(4){width:17%}.technical-mtf-table th:nth-child(5),.technical-mtf-table td:nth-child(5){width:13%}.technical-mtf-table th:nth-child(6),.technical-mtf-table td:nth-child(6){width:17%}.technical-mtf-table th:nth-child(7),.technical-mtf-table td:nth-child(7){width:19%}.citations-table th:nth-child(1),.citations-table td:nth-child(1){width:22%}.citations-table th:nth-child(2),.citations-table td:nth-child(2){width:13%}.citations-table th:nth-child(3),.citations-table td:nth-child(3){width:12%}.citations-table th:nth-child(4),.citations-table td:nth-child(4){width:13%}.citations-table th:nth-child(5),.citations-table td:nth-child(5){width:25%}.citations-table th:nth-child(6),.citations-table td:nth-child(6){width:15%}.mandatory-evidence-table th:nth-child(1),.mandatory-evidence-table td:nth-child(1){width:18%}.mandatory-evidence-table th:nth-child(2),.mandatory-evidence-table td:nth-child(2){width:12%}.mandatory-evidence-table th:nth-child(3),.mandatory-evidence-table td:nth-child(3){width:9%}.mandatory-evidence-table th:nth-child(4),.mandatory-evidence-table td:nth-child(4){width:20%}.mandatory-evidence-table th:nth-child(5),.mandatory-evidence-table td:nth-child(5){width:20%}.mandatory-evidence-table th:nth-child(6),.mandatory-evidence-table td:nth-child(6){width:21%}.evidence-scan-table th:nth-child(1),.evidence-scan-table td:nth-child(1){width:24%}.evidence-scan-table th:nth-child(2),.evidence-scan-table td:nth-child(2){width:11%}.evidence-scan-table th:nth-child(3),.evidence-scan-table td:nth-child(3){width:20%}.evidence-scan-table th:nth-child(4),.evidence-scan-table td:nth-child(4){width:10%}.evidence-scan-table th:nth-child(5),.evidence-scan-table td:nth-child(5){width:35%}.resolver-trace-table th:nth-child(1),.resolver-trace-table td:nth-child(1){width:17%}.resolver-trace-table th:nth-child(2),.resolver-trace-table td:nth-child(2){width:13%}.resolver-trace-table th:nth-child(3),.resolver-trace-table td:nth-child(3){width:20%}.resolver-trace-table th:nth-child(4),.resolver-trace-table td:nth-child(4){width:24%}.resolver-trace-table th:nth-child(5),.resolver-trace-table td:nth-child(5){width:12%}.resolver-trace-table th:nth-child(6),.resolver-trace-table td:nth-child(6){width:14%}
.technical-mtf-table .signal{align-items:flex-start}.technical-mtf-table .signal-dot{margin-top:3px}.signal-stack{display:flex;flex-direction:column;gap:2px;min-width:0}.signal-label{font-weight:700}.signal-detail{display:block;color:#475467;font-size:12px;line-height:1.28}
.proposal-label{font-size:11px;text-transform:uppercase;letter-spacing:.08em;color:#667085;margin-bottom:6px}
body,.hero,.section,.metric-card,.quality-card,.badge,.callout,.titan-note,table,th,td{-webkit-print-color-adjust:exact;print-color-adjust:exact}.hero{position:relative;overflow:hidden;background:#0b4f38!important;background-image:linear-gradient(135deg,#071f2f 0%,#0b4f38 48%,#77b900 140%)!important;color:#fff!important}.hero:before{content:"";position:absolute;inset:0;background:radial-gradient(circle at 82% 18%,rgba(118,185,0,.35),transparent 34%),linear-gradient(90deg,rgba(255,255,255,.07),transparent 45%);pointer-events:none}.hero>*{position:relative;z-index:1}.hero h1,.hero .subtitle,.hero .eyebrow,.hero .brand-name,.hero .brand-meta{color:#fff!important}.brand-row{display:flex;align-items:center;gap:14px;margin-bottom:18px}.logo-mark{width:58px;height:58px;border-radius:14px;display:flex;align-items:center;justify-content:center;background:#76b900;color:#071f2f;font-weight:900;font-size:18px;letter-spacing:.02em;box-shadow:inset 0 0 0 1px rgba(255,255,255,.42),0 10px 24px rgba(0,0,0,.24)}.brand-name{font-weight:800;font-size:18px}.brand-meta{text-transform:uppercase;letter-spacing:.12em;font-size:11px;color:#d9f99d!important}.quality-card{background:rgba(4,20,32,.66)!important;border-color:rgba(255,255,255,.45)!important}.theme-equity .section h2{border-bottom:2px solid rgba(118,185,0,.28);padding-bottom:8px}.theme-equity .executive-bridge{border-left-color:#76b900}.theme-equity .callout,.theme-equity .titan-note{border-left-color:#76b900;background:#f0f8e8}.theme-equity th{background:#eaf3e1;color:#142033}.theme-equity a{color:#075e45}.theme-equity .metric-card{border-top:4px solid #76b900}@media print{body{background:#eef3ed!important}.report{max-width:none;padding:0}.hero{border-radius:12px!important;margin:0 0 12px!important;break-inside:avoid;page-break-inside:avoid}.section,.metric-card{break-inside:auto}.quality-card{background:rgba(4,20,32,.72)!important}.badge.watch{background:#fff5d8!important;color:#8a5a00!important;border-color:#f0d28a!important}.badge.positive{background:#e6f6ed!important;color:#106b43!important;border-color:#b6e2c7!important}.badge.blocked{background:#fdecec!important;color:#9f2339!important;border-color:#efb6b6!important}}
.logo-frame{width:112px;height:58px;border-radius:14px;display:flex;align-items:center;justify-content:center;background:rgba(4,20,32,.70);padding:9px 12px;border:1px solid rgba(255,255,255,.38);box-shadow:inset 0 0 0 1px rgba(255,255,255,.08),0 10px 24px rgba(0,0,0,.24)}.logo-frame img{display:block;max-width:100%;max-height:100%;object-fit:contain}
.legal-notice{border-left:6px solid #b47a00;background:#fffaf0;padding:16px 22px;margin:12px 0 16px}.legal-notice h2{font-size:17px;color:#513a00;border-bottom:1px solid rgba(180,122,0,.28)!important;margin-bottom:8px}.legal-notice p{font-size:12px;line-height:1.42;color:#3f3f46;margin-bottom:6px}
.hero-legal{grid-column:1/-1;margin-top:2px;border-left:4px solid #f7c948;background:rgba(255,250,240,.12);border-radius:8px;padding:10px 13px;font-size:11px;line-height:1.45;color:#fff}.hero-legal strong{color:#fff4c2}
"""

