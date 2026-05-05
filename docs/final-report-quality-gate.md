# Final Report Quality Gate

Date: 2026-05-02

## Purpose

This is the Stage 5 business rule for institutional final reports. It applies to
all future research cycles across tickers, instruments, and asset classes.

The final report must be professionally structured, fact-checked, accurate,
quality-driven, and evidence-grounded. Baseline LLM outputs may contribute useful
layout and narrative flow, but final language must be governed by Titan evidence
status and source audit.

## Required Report Sections

| Section | Required | Gate |
|---|---:|---|
| Report Metadata | Yes | Separate research timestamp, requested analysis date, market-data as-of date, and user-evidence timestamps. |
| Executive Decision Summary | Yes | Use Titan-adjudicated stance and stance deltas, not raw baseline stance alone. |
| Technical Analysis | Yes | Tie levels and indicators to normalized market data or user-supplied technical evidence. |
| User-Supplied Multi-Timeframe Technical Evidence | When present | Include timeframe, latest timestamp, selected rows, dedupe status, and derived technical features. |
| Fundamental Analysis | Yes | Separate SEC/issuer-backed facts from secondary-source and proxy evidence. |
| Valuation Section | Yes | Preserve blocked point estimates; disclose assumption-based ranges with inputs and source IDs. |
| News, Catalysts, Macro, and Narrative Context | Yes | Distinguish direct issuer evidence, official/public sources, reputable secondary sources, and proxy ecosystem evidence. |
| Evidence Graph and Source Audit | Yes | Include supported, updated, newly discovered, blocked, stale, and reachability-restricted evidence where applicable. |
| Validated Trading Horizon | Yes | Evaluate Intraday, Swing, Positional, and Long-Term independently with rationale. |
| Self-Audit and Internal Checks | Yes | State limitations, blockers, conditional items, no timeframe mixing, and no unsupported Titan-compliance claim. |

## Stage 5 v2 Preview-First Rule

For shareable research reports, Stage 5 must generate an HTML preview before any
final Markdown or PDF export. The preview is the visual approval checkpoint. It
must use institutional styling, clear hierarchy, readable tables, status badges,
callout panels, and clickable citation links.

Markdown and PDF export remain paused until the HTML preview is approved.

## Reader-Facing Status Rule

No raw internal status may appear without explanation. Every status must explain:

- What it means.
- Why it was assigned.
- What supports it.
- What remains unresolved.
- Whether the limitation is missing evidence, conflicting evidence, proxy-only
  evidence, or a failed validation threshold.

Canonical reader-facing mappings:

| Internal Status | Reader-Facing Label |
|---|---|
| Validated | Fully Supported by Required Evidence |
| Conditional Candidate | High-Quality Candidate Requiring Confirmation |
| Conditional | Supported, but Awaiting Specific Confirmation |
| Not Validated | Not Yet Fully Supported for This Horizon |
| Blocked | Specific Claim Not Accepted Due to Evidence Conflict or Missing Input |
| Usable Range - Assumption-Based | Usable Scenario Range With Explicit Assumptions |
| Not Titan-Compliant | Evidence-Gated, With Open Validation Items |

## Baseline Carry-Forward Rules

- Preserve useful structure from the baseline report.
- Upgrade or downgrade baseline conclusions based on later evidence packets.
- Do not copy unsupported baseline claims into final report language as fact.
- Keep unsupported claims visible only as `Conditional`, `Not Validated`,
  `Blocked`, or explicit residual gaps.
- Use `Usable Range - Assumption-Based` only when assumptions are explicit and
  independently sourced scenarios reasonably cluster.

## NVDA Baseline Application

For `NVDA_2026-05-01_deepseek_full_baseline_summary`, the final report should
carry forward the strong technical, fundamental, valuation, news, macro,
sentiment, and investment-plan structure. It should also apply later Titan
updates:

- Original baseline stance: `Hold`.
- Fresh stance: `Overweight`.
- Final posture: evidence-gated overweight candidate with conditional entry
  monitoring.
- Specific `17.7x` forward P/E point estimate: `Blocked`.
- Forward P/E range around `24.28x` to `29.14x`: `Usable Range - Assumption-Based`.
- Intraday: `Conditional Candidate`.
- Swing: `Conditional`.
- Positional: `Conditional Candidate`.
- Long-Term: `Not Validated`.
- Stale claim count after refresh: `0`.

## Output Standard

The final report must read like an institutional research product, but every
section must preserve the audit trail. Professional presentation must never
remove uncertainty, source limitations, blocked evidence, or required next
evidence.

## Evidence-Led Validation Rule

Final report language must treat the evidence ledger and graph packets as the
validation authority, not the agent debate transcript or preserved baseline
prose. A statement may be included as validated only when it is traceable to an
as-of-valid source record and matching supported claim or extracted fact.

If agent prose says a fact was found, searched, confirmed, or validated but the
ledger does not contain the source record, the report must treat that statement
as an assumption, unresolved gap, or rejected claim. This prevents hallucinated
source dates, invented article references, and unsupported consensus claims from
becoming final report facts.

## Persistent Evidence Retrieval Standard

Agents and downstream Titan stages must treat required external evidence as
findable in normal conditions. A missing-data outcome is exceptional, not a
default. Before any agent or report states that validated evidence is unavailable,
the workflow must document persistent attempts across the appropriate source
classes:

- Primary or official sources first: issuer investor relations, SEC EDGAR,
  earnings releases, transcripts, central banks, official agencies, or exchange
  data.
- Reputable secondary or aggregator sources second: financial-data providers,
  earnings-date providers, analyst-consensus aggregators, and market-data
  aggregators with source dates.
- Reputable industry or financial news third: source-dated reporting from
  credible outlets, industry press, supplier/customer disclosures, and
  equipment-maker commentary.

`No validated data found` is not acceptable unless the report states what source
classes were attempted, what remained missing, why validation failed, how the gap
affects the thesis, and what next evidence would resolve it. The report must
still provide a constrained conclusion with clear caveats rather than stopping
the workflow.

Mandatory equity evidence classes include latest company guidance, market price
and volume context, FY1/FY2/NTM valuation basis, catalyst calendar with next
earnings date, and sentiment/positioning evidence where sentiment conclusions
depend on crowding, short interest, squeeze risk, or professional bearish
conviction.
