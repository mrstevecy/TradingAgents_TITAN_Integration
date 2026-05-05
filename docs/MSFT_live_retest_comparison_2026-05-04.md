# MSFT Live Retest Comparison - 2026-05-04

## Scope

This note records the live end-to-end Microsoft retest performed after the global equity evidence enforcement patch.

- Ticker: `MSFT`
- Analysis date: `2026-05-03`
- Fresh run ID: `MSFT_20260504T090723Z`
- Prior system report compared: `research_packets/stage5_final_report/MSFT_20260503T161816Z/MSFT_20260503T161816Z_stage5_v2_final_report.md`
- New report compared: `research_packets/stage5_final_report/MSFT_20260504T090723Z/MSFT_20260504T090723Z_stage5_v2_final_report.md`

## End-to-End Workflow Completed

The retest completed Stage 0A through Stage 5 and archival:

1. Stage 0A research profile resolution.
2. Fresh TradingAgents baseline run with mandatory equity evidence context.
3. Stage 1 validation packet.
4. Stage 1B user technical feature packet from the seven supplied MSFT CSV datasets.
5. Stage 2 citation packet.
6. Stage 2B reinforcement packet.
7. Stage 2C metric reconciliation packet.
8. Stage 3 evidence graph.
9. Evidence delta packet.
10. Stage 2D stale-claim refresh packet.
11. Stage 4 horizon validation.
12. Stage 5 v2 final report PDF/HTML/Markdown export.
13. Final evidence graph rebuild and research-cycle archive.

## Improvements Confirmed

The global evidence patch is active in the new MSFT run:

- The new report includes `Code-Enforced Equity Evidence Scan`.
- The new report includes `Global Equity Enforcement Gates`.
- The Bull/Bear debate validator passed with `10` contributions against a minimum requirement of `5` debate rounds.
- The final report now explicitly constrains conclusions around missing earnings, guidance, consensus, short-interest, and cash-flow evidence.
- The report no longer silently treats the Research Manager or Portfolio Manager conclusion as fully validated when mandatory evidence remains missing.
- The report exposes unresolved evidence gaps instead of hiding them behind a high-conviction final call.

## Mandatory Scan Result

Stage 1 mandatory equity scan returned:

- Retrieved evidence items: `3`
- Missing evidence items: `8`
- Blocking gaps: `4`

Blocking gaps:

- `fundamentals.latest_earnings_release`
- `earnings.actual_vs_consensus`
- `guidance.management`
- `cashflow.fcf_inputs`

These gaps correctly forced constrained conclusions.

## Remaining Recurring Issues

The retest did not fully prevent every corrected-report error from appearing in the reader-facing report body.

The new report still preserves baseline-generated wording such as:

- `Disappointing Earnings Reaction`
- claims that an earnings detail `fell short of elevated expectations`
- an annualized CapEx run-rate claim
- a point forward P/E claim that later has to be blocked by the TITAN overlay

The overlay does constrain or reject several of these claims later in the report, but the contaminated baseline text is still visible in the final report. That means the system has improved materially, but the MSFT remediation is not complete enough for GitHub publication.

## Root Cause

The code-level gates are active, but the final-report renderer still preserves baseline debate/report sections before fully quarantining or suppressing contaminated claims. This allows invalid LLM-generated statements to appear as part of the report narrative even when downstream TITAN validation rejects or constrains them.

A second issue remains in the resolver path: some facts that appear in citation or reinforcement layers are not promoted back into the typed mandatory evidence store. As a result, the final report can cite or discuss a source while the mandatory evidence scan still marks the corresponding institutional fact as missing.

## Required Follow-Up Before GitHub Publication

The next patch should enforce reader-facing contamination control:

- Quarantine or suppress baseline passages containing blocked earnings-reaction, CapEx, FCF, forward P/E, analyst-consensus, and positioning claims.
- Prevent final report export from presenting rejected baseline claims without a nearby explicit rejection label.
- Promote validated Stage 2 and Stage 2B source records into typed evidence-store facts when they satisfy resolver requirements.
- Add regression tests proving that MSFT-style corrected-report errors cannot survive into the final report body as unqualified statements.

## Publication Status

GitHub publication remains blocked. The global gates are active, but the current retest shows remaining reader-facing contamination and evidence-store promotion gaps.

## Root-Fix Follow-Up - 2026-05-04

The Equity Evidence Root-Fix patch remediated the specific reader-facing contamination identified above:

- Stage 2B now writes a promoted typed evidence store from validated citation and reinforcement sources.
- Stage 5 now screens baseline sections before display.
- Unsupported baseline claims are removed from ordinary narrative and listed only in the controlled Excluded Claims / Errors and Recommendations table.
- The regenerated MSFT `MSFT_20260504T090723Z` final report no longer shows the earnings-disappointment or annualized-CapEx wording as normal baseline narrative.

Verification after the patch:

- `python scripts\publication_safety_check.py` passed.
- `python -B -m compileall -q scripts titan_integration` passed.
- `uv run pytest -q` passed with `137 passed, 42 subtests passed`.
