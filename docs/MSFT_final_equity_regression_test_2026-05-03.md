# MSFT Final Equity Regression Test

Date: 2026-05-03  
Ticker: `MSFT`  
Asset class: `Equity`  
Purpose: third end-to-end equity regression scenario after `NVDA` and `MU`.

## Input Folder

User-supplied CSV evidence should be placed under:

```text
inputs\MSFT\2026-05-03
```

Expected first-pass files are TradingView-style OHLCV/indicator CSV exports,
typically covering:

- monthly
- weekly
- daily
- 4h
- 1h
- 15m
- 5m

Exact filenames do not need to match a rigid convention. The ingestion layer
detects timeframe, timestamp columns, OHLCV columns, file hashes, row counts, and
selected analysis windows.

## Planned Workflow

After the CSV files are placed, the MSFT run will follow the full equity_v1
protocol:

1. Stage 0A universal request resolution.
2. TradingAgents DeepSeek baseline run.
3. Stage 1 validation packet with provider evidence and mandatory evidence audit.
4. Stage 1A user-supplied evidence ingestion.
5. Stage 1B user technical feature extraction.
6. Stage 2 citation/evidence linking through the evidence ledger.
7. Stage 2B evidence reinforcement through the evidence ledger.
8. Stage 2C computable metric reconciliation.
9. Stage 2D stale or carried-forward claim refresh where applicable.
10. Stage 3 evidence graph generation.
11. Stage 4 horizon validation.
12. Stage 5 v2 final report export.
13. Regression review against prior NVDA/MU lessons:
    - no ticker-specific hard-coding
    - no future-dated source validation
    - no unsupported final consensus inheritance
    - no `Supported` external fact without ledger-backed source records
    - constrained conclusions where gaps remain

## Status

Completed.

## Completed Workflow Result

Research run ID: `MSFT_20260503T161816Z`

TradingAgents baseline:

- Provider/model: DeepSeek / `deepseek-v4-flash`
- Processed decision: `Hold`
- Summary:
  - `outputs\deepseek_fresh_baseline\MSFT_2026-05-03_deepseek_fresh_baseline_summary.json`
  - `outputs\deepseek_fresh_baseline\MSFT_2026-05-03_deepseek_fresh_baseline_summary.md`

Research-cycle metadata:

- Requested analysis date: `2026-05-03`
- Market data as of: `2026-05-01`
- User evidence latest timestamp: `2026-05-01T22:55:00`
- Session context: research run after latest available regular-session market data

## Generated Artifacts

Stage 0A:

- `research_packets\stage0a_research_resolution\MSFT_2026-05-03_stage0a_research_resolution.json`
- `research_packets\stage0a_research_resolution\MSFT_2026-05-03_stage0a_research_resolution.md`
- Result: `Equity` resolved to implemented profile `equity_v1`

Stage 1:

- `research_packets\stage1\MSFT_2026-05-03_stage1_validation_packet.json`
- `research_packets\stage1\MSFT_2026-05-03_stage1_validation_packet.md`
- Preliminary status: `Conditional - Pre-Compliance Only`
- Claim status counts: `Supported` 8, `Conditional` 3, `Not Validated` 3

Stage 1B:

- `research_packets\stage1b_user_technical_features\MSFT_2026-05-03_stage1b_user_technical_features_packet.json`
- `research_packets\stage1b_user_technical_features\MSFT_2026-05-03_stage1b_user_technical_features_packet.md`
- Feature summaries: 7

Stage 2:

- `citation_manifests\msft_2026-05-03_stage2_sources.json`
- `research_packets\stage2\MSFT_2026-05-03_stage2_citation_packet.json`
- `research_packets\stage2\MSFT_2026-05-03_stage2_citation_packet.md`
- Claim status counts: `Supported` 10, `Conditional` 4

Stage 2B:

- `citation_manifests\msft_2026-05-03_stage2b_reinforcement.json`
- `research_packets\stage2b\MSFT_2026-05-03_stage2b_reinforcement_packet.json`
- `research_packets\stage2b\MSFT_2026-05-03_stage2b_reinforcement_packet.md`
- Reinforced status counts: `Supported` 10, `Conditional` 3, `Usable Range - Assumption-Based` 1

Stage 2C:

- `research_packets\stage2c\MSFT_2026-05-03_stage2c_metric_reconciliation_packet.json`
- `research_packets\stage2c\MSFT_2026-05-03_stage2c_metric_reconciliation_packet.md`
- Result: valuation carried as `Usable Range - Assumption-Based`

Stage 2D:

- `research_packets\stage2d_stale_claim_refresh\MSFT_2026-05-03_stage2d_stale_claim_refresh_packet.json`
- `research_packets\stage2d_stale_claim_refresh\MSFT_2026-05-03_stage2d_stale_claim_refresh_packet.md`
- Refreshed stale claims: 0 because this is the first MSFT graph-backed run in the project

Stage 3:

- `research_packets\stage3_graphify\MSFT_2026-05-03\graph.json`
- `research_packets\stage3_graphify\MSFT_2026-05-03\GRAPH_REPORT.md`
- `research_packets\stage3_graphify\MSFT_2026-05-03\graph.html`
- Final graph after Stage 5 overlay: 147 nodes, 342 edges
- Share package:
  - `research_packets\stage3_graphify\MSFT_2026-05-03\MSFT_2026-05-03_interactive_evidence_graph_share_package.zip`

Evidence delta:

- `research_packets\evidence_delta\MSFT_2026-05-03_evidence_delta_packet.json`
- `research_packets\evidence_delta\MSFT_2026-05-03_evidence_delta_packet.md`
- First-run structural delta: `Needs Fresh Evidence` 13, `Still Blocked` 2

Stage 4:

- `research_packets\stage4_horizon_validation\MSFT_20260503T161816Z_stage4_horizon_validation_packet.json`
- `research_packets\stage4_horizon_validation\MSFT_20260503T161816Z_stage4_horizon_validation_packet.md`
- Validated trading horizon: `Conditional Candidate: Intraday / Day Trading, Swing, Positional`
- Horizon classifications:
  - Intraday / Day Trading: `Conditional Candidate`
  - Swing: `Conditional`
  - Positional: `Conditional Candidate`
  - Long-Term Investment: `Not Validated`

Stage 5:

- `research_packets\stage5_final_report\MSFT_20260503T161816Z\MSFT_20260503T161816Z_stage5_v2_final_report.html`
- `research_packets\stage5_final_report\MSFT_20260503T161816Z\MSFT_20260503T161816Z_stage5_v2_final_report.md`
- `research_packets\stage5_final_report\MSFT_20260503T161816Z\MSFT_20260503T161816Z_stage5_v2_final_report.pdf`
- `research_packets\stage5_final_report\MSFT_20260503T161816Z\MSFT_20260503T161816Z_stage5_v2_final_report_manifest.json`

Archive:

- `research_cycles\MSFT_20260503T161816Z`

## Evidence-Governance Observations

- No future-dated citation source was accepted as validation evidence.
- Stage 2 and Stage 2B used the evidence ledger; no external fact was upgraded solely from agent prose.
- Latest guidance was supported by Microsoft investor-relations evidence plus secondary transcript/report guidance context.
- Catalyst calendar remained `Conditional` because the next-event date is secondary-source supported and still prefers issuer IR calendar confirmation.
- Sentiment/positioning was supported with secondary short-interest and analyst-consensus evidence, while direct exchange/FINRA evidence remains preferred for production-grade crowding or squeeze claims.
- Valuation was kept as `Usable Range - Assumption-Based`, not a forced point estimate.
- Long-term investment horizon remained `Not Validated`, which is the correct constrained outcome given unresolved longer-horizon moat/valuation evidence requirements.

## Verification

- `uv run pytest tests\test_institutional_evidence_policy.py -q`
  - `12 passed`
- `uv run pytest -q`
  - `120 passed, 42 subtests passed`
- Final PDF exists and is non-empty:
  - size: `3,770,155` bytes
- Future-date smoke scan of the Stage 5 Markdown found no May 4-9, 2026 source-date references.

## Cosmetic Report Update

After report review, TITAN Addendum C was enhanced globally in the Stage 5 v2
renderer so the user-supplied multi-timeframe technical table shows both signal
labels and numeric values:

- VWAP cells now show VWAP value plus close-vs-VWAP difference and percent.
- RSI cells now show the RSI value.
- ADX cells now show the ADX value.
- Volume cells now show latest volume, volume moving average, and volume/MA ratio.

The MSFT final HTML, Markdown, and PDF were regenerated after this renderer
update.
