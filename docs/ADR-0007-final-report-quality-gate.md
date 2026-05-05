# ADR-0007: Evidence-Gated Final Report Quality Standard

Date: 2026-05-02

## Status

Accepted

## Context

The DeepSeek baseline report for `NVDA_2026-05-01` provided useful structure:
market/technical analysis, news and macro context, fundamentals, sentiment, and
an investment plan. However, a baseline LLM report is not itself a Titan-final
report. Some claims may be supported, some may be strengthened later, and some
may remain blocked or usable only within assumption-based ranges.

The final reporting layer must therefore preserve the strengths of the baseline
format while enforcing fact-checking, source audit, valuation reconciliation,
horizon validation, and self-audit.

## Decision

Adopt a Stage 5 final-report quality gate as core business logic.

The final report must include, at minimum:

- Report Metadata
- Executive Decision Summary
- Technical Analysis
- User-Supplied Multi-Timeframe Technical Evidence, when present
- Fundamental Analysis
- Valuation Section
- News, Catalysts, Macro, and Narrative Context
- Evidence Graph and Source Audit
- Validated Trading Horizon
- Self-Audit and Internal Checks

Each section must be evidence-gated. Baseline report structure may be reused, but
baseline claims cannot be copied into final language unless their evidence status
is clear.

## Rules

- Preserve useful baseline organization and analytical depth.
- Do not blindly copy baseline conclusions.
- Every material claim must be linked to a source, graph node, computed metric,
  or explicit residual gap.
- Every `Conditional`, `Conditional Candidate`, `Not Validated`, `Blocked`, or
  `Usable Range - Assumption-Based` item must include business-facing rationale.
- A blocked point estimate does not automatically block a broader
  assumption-based valuation range.
- A usable range does not validate an unsupported point estimate.
- Direct issuer evidence, official evidence, secondary evidence, and proxy
  ecosystem evidence must remain separated.
- The final report must not claim Titan compliance when required evidence blocks
  remain incomplete or contradictory.

## Implementation

The report-quality contract is encoded in:

- `titan_integration\report_quality.py`
- `docs\final-report-quality-gate.md`

Future Stage 5 report generation must use this section contract before producing
Markdown or PDF output.

## Consequences

- Final reports remain professionally structured while staying honest and
  audit-ready.
- Baseline reports become inputs, not final authority.
- Repeated ticker research improves over time because prior graph evidence,
  deltas, stale-claim refreshes, user evidence, valuation reconciliation, and
  horizon validation are all carried into the final report layer.

