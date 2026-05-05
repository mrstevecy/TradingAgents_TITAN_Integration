# Stage 5 v2 HTML Preview

Date: 2026-05-02

## Purpose

Stage 5 v2 is the preview-first institutional report layer. It fuses the
DeepSeek baseline's rich narrative structure with Titan evidence packets,
Graphify-style evidence graph context, user-supplied multi-timeframe technical
features, valuation reconciliation, evidence deltas, and horizon validation.

The first deliverable is HTML only. Final Markdown and PDF export remain paused
until the HTML preview is visually reviewed and approved.

## Implementation

Added:

- `titan_integration\reader_status.py`
- `titan_integration\report_preview_v2.py`
- `scripts\build_stage5_v2_preview.py`

Updated:

- `titan_integration\horizon_validation.py`
- `docs\final-report-quality-gate.md`
- `docs\stage5-final-report-exporter-2026-05-02.md`

## Enhanced Preview Update

The preview now mirrors the upstream TradingAgents consolidation sequence:

1. Analyst Team Reports
2. Research Team Decision
3. Trading Team Plan
4. Portfolio Management Decision

The latest fresh baseline sections are preserved in full instead of summarized
away. Titan notes are layered around those sections to explain discrepancies,
evidence gates, valuation conflicts, and horizon-validation limits.

The renderer includes a local Markdown-to-HTML path for the TradingAgents report
subset so tables, headings, lists, bold text, icons, horizontal rules, and final
transaction proposal blocks retain the visual language of the original baseline.

The manifest now includes baseline preservation checks:

- `baseline_integrity`
- `baseline_title_audit`
- `baseline_proposal_map`

The latest audit confirms seven fresh-baseline sections are present and all
baseline titles extracted from those sections render in the preview.

## Final Refinement Pass

The preview now preserves the fresh baseline as the primary narrative artifact
and separates Titan material into clearly labeled addenda. The baseline wrapper
labels use the baseline report's own section names, including `Trader Investment
Plan`. The renderer does not add heuristic icons, heading labels, or proposal
labels inside baseline content.

Added a `Baseline Internal Conclusion Map` near the top of the preview. This
table explains that the baseline contains role-specific proposals from multiple
agents, including `HOLD`, `BUY`, and `Overweight`. Those preserved outputs are
not deleted or overwritten. They are treated as section-specific baseline
conclusions and reconciled by the Titan overlay as:

- Baseline decision: `Overweight` / tactical buy-on-weakness.
- Baseline trading plan: staged entry around the documented buy range, not a
  blind market chase.
- Titan overlay: evidence-gated overweight candidate requiring confirmation,
  with specific valuation and horizon-validation caveats.

Final transaction proposal lines that appear inside the preserved baseline are
rendered as ordinary baseline text. Any reconciliation happens only in the
separate map or in Titan commentary beneath the preserved baseline section.

The date handling rule is now overlay-based:

- Baseline date language remains preserved as part of the original source text.
- Titan timestamp notes clarify that the research run date is May 2, 2026.
- May 1, 2026 remains valid as latest regular-session market-data as-of date
  and lookback end where applicable.

## NVDA Preview Artifact

Run id:

- `NVDA_20260502T150558Z`

Output:

- `research_packets\stage5_final_report\NVDA_20260502T150558Z\preview.html`
- `research_packets\stage5_final_report\NVDA_20260502T150558Z\preview_manifest.json`

## Business Logic

The preview translates internal research states into reader-facing language.
Examples:

- `Not Titan-Compliant` becomes `Evidence-Gated, With Open Validation Items`.
- `Conditional Candidate` becomes `High-Quality Candidate Requiring Confirmation`.
- `Blocked` becomes `Specific Claim Not Accepted Due to Evidence Conflict or Missing Input`.
- `Usable Range - Assumption-Based` becomes `Usable Scenario Range With Explicit Assumptions`.

Every status must answer what it means, why it was assigned, what supports it,
what remains unresolved, and whether the limitation is missing evidence,
conflicting evidence, proxy-only evidence, or a failed validation threshold.

## Current NVDA Interpretation

- Fresh TradingAgents stance: `Overweight`.
- Stage 5 v2 posture: evidence-gated overweight candidate with conditional entry
  monitoring.
- Intraday: high-quality candidate requiring live tape, liquidity, spread/depth,
  and opening-range confirmation.
- Swing: supported but awaiting confirmation because valuation remains
  unresolved at the point-estimate level.
- Positional: high-quality candidate requiring further revisions/factor-regime
  confirmation.
- Long-term: not yet fully supported for the long-term horizon because the full
  secular/moat/cycle-aware valuation stack has not been collected.
- Forward P/E point estimate: blocked at the exact `17.7x` claim level.
- Forward P/E range: usable as an assumption-based scenario range.

## Verification

- Fresh NVDA chain rebuilt through Stage 4.
- Stage 5 v2 preview generated.
- Python compile check passed with bytecode redirected to a clean temp cache.
- HTML scan confirms no unexplained `Not Titan-Compliant`,
  `TITAN-compliant`, or `Underweight` wording remains in the preview body.

## Next Gate

The user should visually review `preview.html`. After approval, the system can
generate the final Markdown and PDF, render PDF pages for QA, and run the
publication safety check.

## Final Export After Preview Approval

Added:

- `scripts\export_stage5_v2_final_report.py`

Generated from the approved Stage 5 v2 HTML:

- `research_packets\stage5_final_report\NVDA_20260502T150558Z\NVDA_20260502T150558Z_stage5_v2_final_report.html`
- `research_packets\stage5_final_report\NVDA_20260502T150558Z\NVDA_20260502T150558Z_stage5_v2_final_report.md`
- `research_packets\stage5_final_report\NVDA_20260502T150558Z\NVDA_20260502T150558Z_stage5_v2_final_report.pdf`
- `research_packets\stage5_final_report\NVDA_20260502T150558Z\NVDA_20260502T150558Z_stage5_v2_final_report_manifest.json`

PDF QA:

- Final PDF page count: `39`
- Rendered PDF page PNGs:
  - `research_packets\stage5_final_report\NVDA_20260502T150558Z\rendered_pages_v2`
- Contact sheet:
  - `output\playwright\stage5_v2_pdf_contact_sheet.png`

Text checks confirmed:

- `Trader Investment Plan` is present.
- `Trading Team Plan` is absent.
- `Baseline Internal Conclusion Map` is present.
- `TITAN Addendum` sections are present.

## Themed PDF Enhancement

Added a reusable instrument / asset-class theme layer to the Stage 5 v2 HTML
renderer:

- Ticker identity badge
- Actual issuer logo when a local approved logo asset exists
- Official-website logo discovery for future tickers when a local logo is not
  already available
- Company name in the hero banner
- Asset-class label, currently `Equity`
- Equity color palette using green / deep-blue institutional styling
- Print color preservation using `print-color-adjust`
- Final export wording now replaces preview-only language before PDF creation

The final PDF was regenerated after the theme update.

For NVDA, the local logo asset is:

- `assets\logos\NVDA.svg`
- `assets\logos\logo_manifest.json`

Logo source note:

- Source: Wikimedia Commons copy of the NVIDIA logo, sourced from NVIDIA
  materials.
- Trademark caution: NVIDIA logo usage is subject to NVIDIA trademark and brand
  guidelines. The report uses the mark for issuer identification in a research
  context and does not imply affiliation, sponsorship, or endorsement.

Reusable logo logic:

- Implemented in `titan_integration\logo_assets.py`.
- Final export invokes logo resolution before rendering the report.
- Resolution order:
  1. Use existing local approved logo asset.
  2. If missing, discover the issuer's official website, using an explicit
     `--official-website` override when available or provider metadata where
     supported.
  3. Attempt to download a logo/icon candidate from the issuer's official
     website.
  4. If no suitable official-site asset is available, fall back to a ticker
     badge and record the limitation in the manifest.
- Every final report manifest records `logo_resolution`.

Themed QA artifacts:

- First page render:
  - `research_packets\stage5_final_report\NVDA_20260502T150558Z\rendered_pages_v2\page_01.png`
- Themed contact sheet:
  - `output\playwright\stage5_v2_pdf_contact_sheet_themed.png`

Text checks confirmed:

- `final PDF paused pending review` is absent from the final PDF.
- `NVIDIA Corporation` is present.
- `Trader Investment Plan` remains present.
- `Trading Team Plan` remains absent.
- `Research-only` notice is present on the first PDF page.
- `Logo notice` is present on the first PDF page.
- `does not imply affiliation` wording is present in the PDF.

## Addendum C Numeric Signal Detail

Updated 2026-05-03:

The user-supplied multi-timeframe technical table now displays numeric values
next to the existing signal labels:

- VWAP: position, VWAP value, close-vs-VWAP difference, and percent difference.
- RSI: regime plus RSI value.
- ADX: trend label plus ADX value.
- Volume: volume regime, latest volume, volume moving average, and volume/MA ratio.

This applies globally to Stage 5 v2 reports for all tickers with Stage 1B user
technical feature packets.
