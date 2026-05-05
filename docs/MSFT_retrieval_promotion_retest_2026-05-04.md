# MSFT Retrieval Promotion Retest

Date: 2026-05-04  
Run ID: `MSFT_20260504T132858Z`

## Scope

This retest reran Microsoft equity research from Stage 0A through Stage 5 after
the global Equity v1 retrieval, evidence promotion, dated input-folder
discovery, and final report quarantine updates.

## Input Discovery

Stage 0A selected the latest eligible user-input folder:

```text
D:\Projects\CodeX\TradingAgents_Integration\inputs\MSFT\2026-05-04
```

Stage 1 detected seven user-supplied CSV files and latest user evidence as of
`2026-05-01T22:55:00`.

## Outputs

- Final PDF:
  `research_packets\stage5_final_report\MSFT_20260504T134651Z\MSFT_20260504T134651Z_stage5_v2_final_report.pdf`
- Final Markdown:
  `research_packets\stage5_final_report\MSFT_20260504T134651Z\MSFT_20260504T134651Z_stage5_v2_final_report.md`
- Final manifest:
  `research_packets\stage5_final_report\MSFT_20260504T134651Z\MSFT_20260504T134651Z_stage5_v2_final_report_manifest.json`
- Evidence graph:
  `research_packets\stage3_graphify\MSFT_2026-05-04\graph.html`
- Archive:
  `research_cycles\MSFT_20260504T134651Z`

## Price Snapshot Enhancement

The Stage 5 report now shows a top-of-report price snapshot before narrative
interpretation:

- latest market-data date
- latest open, high, low, close, and volume
- 52-week high and high date
- 52-week low and low date
- latest close distance from the 52-week high and low
- current/intraday price status, clearly labeled when not separately validated

For this MSFT retest, the latest normalized market-data bar is `2026-05-04`,
with close near `$417.46`, 52-week high near `$555.45`, and 52-week low near
`$356.28`.

## Improvements Versus Prior MSFT Report

- Stage 0A no longer depends on manual stale-folder selection; it selected the
  latest eligible dated input folder.
- Legal/title metadata no longer contains technical strings such as `200 SMA`.
- Report dates are separated correctly:
  - research date: `2026-05-04`
  - market data as of: `2026-05-01`
  - intended trade date: `2026-05-04`
- The 200-day SMA is classified as long-term resistance, not support, because it
  is above the latest close.
- Agent scratchpad phrases are removed.
- Rejected FCF, CapEx, and forward-P/E claims are no longer shown as normal
  reader-facing decision narrative.
- Decision sections with rejected dependencies are replaced by
  `Evidence-Gated Constrained Decision` summaries.
- Exact rejected claims remain available only in Appendix A with failure reasons
  and correction rules.

## Remaining Constraints

The run remains `Not Titan-Compliant` because unresolved evidence gaps remain:

- `capex.guidance`
- `earnings.actual_vs_consensus`
- `fundamentals.latest_earnings_release`

The final report therefore remains a constrained research report, not a clean
actionable Buy/Sell/Exit instruction.

## Verification Notes

The main report body before Appendix A was checked for known leakage phrases:

- `FCF conversion collapsed`: 0
- `spending cliff`: 0
- `CapEx remains elevated`: 0
- `CapEx annualization`: 0
- raw `Sell 20` instruction: 0
- normal-body `Excluded claim removed from final narrative` placeholders: 0

Rejected claim details are preserved in Appendix A for audit and operational
learning.
