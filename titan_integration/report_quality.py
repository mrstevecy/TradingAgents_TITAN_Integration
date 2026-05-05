"""Final report quality contract for Titan research outputs.

This module defines the Stage 5 reporting gate. Baseline LLM reports may supply
useful structure and narrative leads, but final report language must be routed
through evidence status, source audit, and self-audit checks before publication.
"""

from __future__ import annotations

from dataclasses import dataclass

from .validation_outcomes import (
    BLOCKED,
    CONDITIONAL,
    CONDITIONAL_CANDIDATE,
    NOT_VALIDATED,
    USABLE_RANGE_ASSUMPTION_BASED,
    VALIDATED,
)


FINAL_REPORT_STAGE = "Titan Stage 5 - Evidence-Gated Final Report"


@dataclass(frozen=True)
class ReportSectionRule:
    """Defines one required final-report section and its quality gate."""

    section_id: str
    title: str
    required: bool
    purpose: str
    evidence_gate: str


FINAL_REPORT_SECTIONS: tuple[ReportSectionRule, ...] = (
    ReportSectionRule(
        section_id="report_metadata",
        title="Report Metadata",
        required=True,
        purpose="Identify the asset, run timestamp, data as-of timestamp, provider inputs, and session context.",
        evidence_gate="Must separate research timestamp, requested analysis date, market-data as-of date, and user-evidence timestamps.",
    ),
    ReportSectionRule(
        section_id="executive_decision_summary",
        title="Executive Decision Summary",
        required=True,
        purpose="Summarize stance, stance deltas, highest-confidence conclusions, and key residual risks.",
        evidence_gate="Must cite Stage 1 through Stage 4 status. Must not present baseline stance as final without Titan adjudication.",
    ),
    ReportSectionRule(
        section_id="technical_analysis",
        title="Technical Analysis",
        required=True,
        purpose="Carry forward price structure, momentum, volatility, volume, and level analysis.",
        evidence_gate="Must tie levels and indicators to normalized market data or user-supplied technical evidence.",
    ),
    ReportSectionRule(
        section_id="user_multitimeframe_evidence",
        title="User-Supplied Multi-Timeframe Technical Evidence",
        required=False,
        purpose="Incorporate user-provided CSV/chart evidence when present and deduplicated.",
        evidence_gate="Must disclose source path class, timeframe, latest timestamp, selected rows, and derived features. Omit if no user evidence is present.",
    ),
    ReportSectionRule(
        section_id="fundamental_analysis",
        title="Fundamental Analysis",
        required=True,
        purpose="Present official and secondary-source fundamentals, quality of earnings, balance sheet, and cash-flow context.",
        evidence_gate="Must separate SEC/issuer-backed facts from secondary or proxy evidence.",
    ),
    ReportSectionRule(
        section_id="valuation_analysis",
        title="Valuation Section",
        required=True,
        purpose="Present valuation metrics, computable reconciliations, point-estimate blockers, and assumption-based ranges.",
        evidence_gate="Must preserve blocked point estimates and may use assumption-based ranges only with explicit assumptions and source IDs.",
    ),
    ReportSectionRule(
        section_id="news_catalyst_macro",
        title="News, Catalysts, Macro, and Narrative Context",
        required=True,
        purpose="Present current newsflow, catalysts, macro, economic releases, earnings timing, and geopolitical context.",
        evidence_gate="Must distinguish direct issuer evidence, official/public sources, reputable secondary sources, and proxy ecosystem evidence.",
    ),
    ReportSectionRule(
        section_id="evidence_graph_source_audit",
        title="Evidence Graph and Source Audit",
        required=True,
        purpose="Show source quality, claim status, graph continuity, stale-claim refresh, deltas, and blocked items.",
        evidence_gate="Must include supported, updated, newly discovered, blocked, stale, and reachability-restricted evidence where applicable.",
    ),
    ReportSectionRule(
        section_id="validated_trading_horizon",
        title="Validated Trading Horizon",
        required=True,
        purpose="Classify intraday, swing, positional, and long-term horizons independently.",
        evidence_gate="Must include rationale and required next evidence for each non-validated, conditional, or blocked horizon.",
    ),
    ReportSectionRule(
        section_id="self_audit",
        title="Self-Audit and Internal Checks",
        required=True,
        purpose="Confirm source integrity, no timeframe mixing, no unsupported Titan compliance claim, and no hidden blocked evidence.",
        evidence_gate="Must explicitly state remaining blockers, conditional items, assumption-based ranges, and report limitations.",
    ),
)


ALLOWED_FINAL_REPORT_OUTCOMES = {
    VALIDATED,
    CONDITIONAL,
    CONDITIONAL_CANDIDATE,
    NOT_VALIDATED,
    BLOCKED,
    USABLE_RANGE_ASSUMPTION_BASED,
    "Supported",
    "Updated",
    "Unchanged Supported",
    "Newly Discovered",
    "Reachability Restricted",
}


BASELINE_CARRY_FORWARD_RULES = (
    "Preserve useful baseline structure and narrative organization.",
    "Do not copy baseline claims into final language without evidence status.",
    "Carry forward unsupported baseline claims only as blocked, conditional, not validated, or explicit open items.",
    "Upgrade or downgrade baseline conclusions when later evidence packets contradict or strengthen them.",
    "Every material final-report section must show the business reason behind its status.",
    "Do not allow 'no validated data found' as a silent endpoint; final reports must document attempted source classes, missing evidence, thesis impact, next best evidence, and a constrained conclusion.",
    "Final decisions must not silently inherit agent consensus when mandatory evidence classes are missing, stale, proxy-only, contradictory, or based on undocumented searches.",
)


MANDATORY_EVIDENCE_REPORT_RULES = (
    "Company guidance and filings must be searched through primary/official sources before final fundamental synthesis.",
    "Forward valuation metrics must identify FY1, FY2, NTM, formula inputs, source dates, and whether values are point estimates or assumption-based ranges.",
    "Catalyst calendars must include confirmed next earnings date for equities or document exhaustive source-aware attempts when unavailable.",
    "Sentiment conclusions about crowding, squeeze risk, or professional bearish conviction require short interest, days-to-cover, options/put-call, or analyst-consensus evidence.",
    "Reports must remain productive under gaps: publish a constrained, caveated conclusion rather than stopping at missing data.",
)


def required_section_ids() -> tuple[str, ...]:
    """Return required Stage 5 section ids in report order."""

    return tuple(section.section_id for section in FINAL_REPORT_SECTIONS if section.required)


def section_titles() -> tuple[str, ...]:
    """Return final report section titles in report order."""

    return tuple(section.title for section in FINAL_REPORT_SECTIONS)


def is_allowed_final_status(status: str | None) -> bool:
    """Return whether a status may appear in final report evidence language."""

    return status in ALLOWED_FINAL_REPORT_OUTCOMES
