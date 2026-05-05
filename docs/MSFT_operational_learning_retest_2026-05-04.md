# MSFT Operational-Learning Retest

Date: 2026-05-04

## Scope

This retest used the latest live source files after the operational-learning
patch. The baseline run was generated with DeepSeek V4 Flash and the full
Stage 0A through Stage 5 v2 workflow was completed for `MSFT` on
`2026-05-03`.

## Run Artifacts

- Fresh run ID: `MSFT_20260504T103153Z`
- Final HTML:
  `research_packets\stage5_final_report\MSFT_20260504T103153Z\MSFT_20260504T103153Z_stage5_v2_final_report.html`
- Final Markdown:
  `research_packets\stage5_final_report\MSFT_20260504T103153Z\MSFT_20260504T103153Z_stage5_v2_final_report.md`
- Final PDF:
  `research_packets\stage5_final_report\MSFT_20260504T103153Z\MSFT_20260504T103153Z_stage5_v2_final_report.pdf`
- Final manifest:
  `research_packets\stage5_final_report\MSFT_20260504T103153Z\MSFT_20260504T103153Z_stage5_v2_final_report_manifest.json`
- Archived cycle:
  `research_cycles\MSFT_20260504T103153Z`

## Outcome

- Baseline processed decision: `Hold`
- Stage 1 status: `Conditional - Pre-Compliance Only`
- Stage 2 status: `Not Titan-Compliant`
- Stage 2B status counts: `Supported: 10`, `Conditional: 3`,
  `Usable Range - Assumption-Based: 1`, `Not Validated: 2`
- Stage 2C status: `Blocked - Missing Valuation Inputs`
- Stage 4 validated horizon:
  `Conditional Candidate: Intraday / Day Trading, Swing`
- Stage 5 safety:
  - Accepted claim dependencies: `11`
  - Rejected baseline claims: `19`
  - Self-audit passed: `False`

## Improvements Versus Prior MSFT Reports

- The fresh report no longer contains the prior visible phrases
  `Disappointing Earnings Reaction`, `fell short`, or `annualized CapEx` in the
  normal reader-facing narrative.
- Forward P/E is now blocked when the system lacks a dated forward multiple or
  FY1/FY2/NTM EPS basis. Stage 2C no longer crashes on missing valuation
  inputs; it produces a constrained valuation gap.
- Stage 5 promotes validated Stage 2B source-backed facts into the typed equity
  evidence store, including analyst consensus, next earnings date, filing,
  transcript, guidance, price/OHLCV, and short-interest evidence.
- Rejected claims are captured in the controlled Excluded Claims / Errors and
  Recommendations section, and they are written to the persistent operational
  error-learning store with role, dependency, severity, recurrence, and
  correction rule.
- The new operational-learning path is role-specific. Relevant prior failures
  are injected into the responsible agent role before future baseline analysis
  starts.

## Remaining Issues

- The report remains evidence-gated rather than Titan-compliant because several
  mandatory dependencies remain unresolved or unpromoted:
  `capex.guidance`, `earnings.actual_vs_consensus`,
  `fundamentals.latest_earnings_release`, `options.put_call`,
  `ownership.13f_latest`, and `ownership.form4_90d`.
- The Fundamentals Analyst still generated multiple FCF and forward-valuation
  claims that had to be excluded by Stage 5. The guard worked, but the next
  improvement should push resolver outputs even earlier and make analyst-stage
  claim validation reject those statements before they reach final rendering.
- Exact institutional valuation requires stronger external estimate providers
  or licensed estimate feeds. Without FY1/FY2/NTM EPS or a dated forward
  multiple, the correct output is a constrained valuation gap.

## Verification

- `python -B -m compileall -q scripts titan_integration TradingAgents\tradingagents`
  passed.
- `cd TradingAgents; uv run pytest -q tests\test_global_equity_evidence_enforcement.py`
  passed with `21 passed`.

Full repository verification should be rerun during the final GitHub-readiness
audit.
