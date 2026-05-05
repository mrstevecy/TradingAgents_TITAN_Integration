# MSFT QA Global Report Hardening - 2026-05-04

## Scope

This note records the global Python fixes made after the QA review of
`MSFT_20260504T134651Z_stage5_v2_final_report.pdf`.

The fixes are equity-wide. Microsoft is used only as the live regression case;
the production logic is ticker-generic.

## Global Fixes Implemented

- Added a dynamic RAG pre-render repair loop. Missing or invalid critical
  evidence keys now trigger evidence-key-specific query planning and a full
  API/issuer/SEC/news/aggregator/web/search-expansion/extraction-retry/source
  reconciliation chain before the report can remain data-incomplete.
- Added resolver traces to the final manifest and diagnostic appendix so the
  system documents what was attempted, what source was selected, what value was
  promoted, and why a key remains unresolved.
- Added diagnostic-mode gating. If critical evidence gates remain failed after
  repair, Stage 5 renders as `DIAGNOSTIC RESEARCH PACKET - NOT FINAL` instead
  of a final institutional report.
- Added upstream TradingAgents tool-output capture and promotion. Baseline runs
  now write an upstream tool-evidence JSONL artifact, and Stage 5 promotes
  usable provider/tool facts from that artifact into the typed evidence store
  before dynamic RAG and final safety filtering.
- Added priority-aware evidence-store replacement. A later weak scrape or
  invalid numeric artifact can no longer overwrite stronger provider, issuer,
  regulatory, or computed evidence for the same key.
- Added rich-but-evidence-clean rendering. Useful upstream analysis is preserved
  in the reader-facing report with inline evidence notes for unsupported
  scenario claims instead of being removed wholesale.
- Split actual CapEx/FCF evidence from forward CapEx guidance so valid
  same-period OCF, CapEx, FCF, and FCF conversion analysis survives even when
  future management CapEx guidance is unresolved.
- Separated latest-period cash-flow records from annual cash-flow records so
  annual values cannot overwrite latest quarterly OCF/CapEx/FCF inputs.
- Added canonical `ReportContext` handling for research date, intended trade
  date, market-data date, latest price, market-bar status, price source, and
  end-of-day versus intraday status.
- Added canonical `FinalDecision` rendering so the cover, summary, trader, and
  portfolio-manager surfaces use one reader-facing action.
- Updated institutional Stage 5 rendering so ordinary reader-facing sections
  are generated from typed evidence and canonical context instead of raw
  baseline prose.
- Replaced generic baseline section labels with business-readable titles:
  `Technical Analysis`, `Market & Catalyst Analysis`, `Fundamental Analysis`,
  `Sentiment & Positioning`, `Research Manager Adjudication`, and
  `Trader Execution Plan`.
- Added a top-of-report price snapshot with latest open, high, low, close,
  volume, 52-week high/low, and distance from the 52-week range.
- Added market-bar status detection. Partial same-day bars are labeled
  `intraday_partial` instead of being treated as final EOD closes.
- Clarified CSV policy. User CSVs are optional and supplemental; if absent, the
  dynamic technical resolver uses provider-derived market/technical evidence as
  fallback, and stale CSVs cannot override newer canonical OHLCV.
- Added evidence-store reconciliation before final rendering so retrieved,
  computed, partial, missing, stale, contested, rejected, and
  `retrieved_invalid` statuses are globally consistent.
- Added source-permission checks by evidence key. Proxy or wrong-source
  evidence cannot validate direct issuer, financial-filing, guidance, RPO,
  short-interest, options, or analyst-consensus facts.
- Added numeric artifact validation so unitless or implausibly small values
  such as revenue `5.0`, OCF `1.0`, or shares short `10.0` are marked
  `retrieved_invalid` and blocked from agent/report promotion.
- Kept rejected baseline claims in the controlled Excluded Claims appendix,
  while preventing those claims from appearing as normal reader-facing
  narrative.
- Updated global enforcement gate labels to use pass/fail/warning style
  statuses instead of ambiguous operational wording.
- Added issuer-page deep-read promotion for cited IR, SEC, earnings-release,
  filing, and transcript URLs. The MSFT IR page now promotes commercial
  remaining performance obligation / RPO when the cited source body contains
  it, instead of relying only on the short citation summary.
- Added SEC companyfacts cash-flow promotion for operating cash flow and
  CapEx. The latest OCF and property/equipment CapEx values are promoted from
  SEC concepts before FCF is computed.
- Added RPO numeric-artifact rejection so CIK/accession-like identifiers cannot
  satisfy backlog evidence. RPO/backlog is now claim/business-model conditional
  rather than a universal equity blocker.
- Updated stale earnings-date governance: stale conflicting dates remain
  quarantined for diagnostics, but once canonical latest-reported and
  next-estimated earnings dates are resolved they do not by themselves force
  `DATA-INCOMPLETE`.
- Added baseline provider-evidence fallback when a local optional dependency
  such as `yfinance` is unavailable during a Stage 1 rebuild.

## MSFT Regression Result

Regenerated report artifacts:

- `research_packets\stage5_final_report\MSFT_20260504T134651Z\MSFT_20260504T134651Z_stage5_v2_final_report.html`
- `research_packets\stage5_final_report\MSFT_20260504T134651Z\MSFT_20260504T134651Z_stage5_v2_final_report.md`
- `research_packets\stage5_final_report\MSFT_20260504T134651Z\MSFT_20260504T134651Z_stage5_v2_final_report.pdf`
- `research_packets\stage5_final_report\MSFT_20260504T134651Z\MSFT_20260504T134651Z_stage5_v2_final_report_manifest.json`

Reader-facing body checks passed for:

- No raw `News Report`, `Fundamentals Report`, `Sentiment Report`, or
  `Market Report` section titles.
- No scratchpad phrases such as `Excellent! I now have` or
  `Now I have a comprehensive dataset`.
- No stale May 1 `$414.44` price/date text in the reader-facing body.
- No visible baseline sell/reduce/annualized-CapEx/FCF-collapse language in
  the reader-facing body.

After upstream tool capture and priority-aware promotion, the MSFT
rejected-claim count improved from `61` to `36`. After the
rich-but-evidence-clean refinement, the remaining `capex.guidance` items are no
longer removed as whole paragraphs. They are preserved with inline evidence
notes where they appear. Appendix A now contains `0` rejected claims for this
run because the remaining issue is scenario caveating, not a hard falsehood.

Additional promoted evidence now includes:

- Latest price and bar status.
- 52-week high/low range.
- Latest-period OCF, CapEx, FCF inputs, computed latest FCF, annual cash-flow
  values, and same-period FCF conversion.
- FY1 EPS, TTM EPS, reported forward P/E, and computed forward P/E basis.
- EMA/SMA/RSI technical indicators from upstream provider tools.
- Sanitized Bull/Bear, Research Manager, Trader, and risk-debate outcomes in
  the diagnostic report surface.

## Current Decision Status

After the issuer/SEC promotion patch and Stage 1 rebuild, the regenerated MSFT
report is:

`EVIDENCE-GATED UNDERWEIGHT`

The latest manifest shows no blocked evidence keys. Key resolved items include:

- `business.rpo_or_backlog`: retrieved as `$627B` from an issuer/transcript
  promotion path.
- `cashflow.latest.ocf`: retrieved from SEC EDGAR companyfacts.
- `cashflow.latest.capex`: retrieved from SEC EDGAR companyfacts.
- `cashflow.fcf_inputs`: computed centrally as OCF minus CapEx.
- `earnings.actual_vs_consensus`: promoted from `EPS of $4.27 versus consensus
  of $4.04` wording.
- `catalyst.stale_earnings_date_conflict`: still stored as a diagnostic stale
  conflict, but no longer a final-decision blocker once canonical earnings
  dates are validated.

The fix does not make the report more permissive. It makes invalid evidence
visible, typed, and blocked before it can control a reader-facing decision.

## Verification

- `python scripts\publication_safety_check.py`
- `python -B -m compileall -q scripts titan_integration TradingAgents\tradingagents`
- `cd TradingAgents; uv run pytest -q`

Latest verification result:

- Targeted equity enforcement: `65 passed`
