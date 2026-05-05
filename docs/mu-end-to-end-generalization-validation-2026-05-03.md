# MU End-to-End Generalization Validation

Date: 2026-05-03

## Objective

Run Micron Technology Corporation (`MU`) through the same equity workflow previously validated on `NVDA` to confirm that Stage 0A through Stage 5 v2 are system-wide and not hard-coded to one ticker.

## Input Evidence

- User-supplied CSV folder:
  - `inputs\MU\2026-05-03`
- Files detected:
  - `BATS_MU, 5_e3567.csv`
  - `BATS_MU, 15_16731.csv`
  - `BATS_MU, 60_0ecfd.csv`
  - `BATS_MU, 240_a53e5.csv`
  - `BATS_MU, 1D_c2c87.csv`
  - `BATS_MU, 1W_13061.csv`
  - `BATS_MU, 1M_5e728.csv`
- Stage 1B extracted seven technical timeframes in the expected order:
  - `5m -> 15m -> 1h -> 4h -> 1d -> 1w -> 1mo`

## Pipeline Outputs

| Stage | Output |
|---|---|
| Stage 0A | `research_packets\stage0a_research_resolution\MU_2026-05-03_stage0a_research_resolution.json` |
| TradingAgents baseline | `outputs\deepseek_fresh_baseline\MU_2026-05-03_deepseek_fresh_baseline_summary.json` |
| Stage 1 | `research_packets\stage1\MU_2026-05-03_stage1_validation_packet.json` |
| Stage 1A | `research_packets\stage1a_user_evidence\MU_2026-05-03_stage1a_user_evidence_packet.json` |
| Stage 1B | `research_packets\stage1b_user_technical_features\MU_2026-05-03_stage1b_user_technical_features_packet.json` |
| Stage 2 | `research_packets\stage2\MU_2026-05-03_stage2_citation_packet.json` |
| Stage 2B | `research_packets\stage2b\MU_2026-05-03_stage2b_reinforcement_packet.json` |
| Stage 2C | `research_packets\stage2c\MU_2026-05-03_stage2c_metric_reconciliation_packet.json` |
| Stage 2D | `research_packets\stage2d_stale_claim_refresh\MU_2026-05-03_stage2d_stale_claim_refresh_packet.json` |
| Delta | `research_packets\evidence_delta\MU_2026-05-03_evidence_delta_packet.json` |
| Stage 4 | `research_packets\stage4_horizon_validation\MU_20260503T093416Z_stage4_horizon_validation_packet.json` |
| Stage 5 v2 | `research_packets\stage5_final_report\MU_20260503T093416Z\MU_20260503T093416Z_stage5_v2_final_report.pdf` |
| Stage 3F graph | `research_packets\stage3_graphify\MU_2026-05-03\graph.html` |

## Validation Results

- Stage 0A resolved `MU` as:
  - Asset class: `Equity`
  - Registry status: `Implemented`
  - Active profile: `equity_v1`
- TradingAgents processed decision:
  - `Sell`
- Stage 1 user evidence:
  - `7` local files detected.
  - `7` user technical feature summaries produced.
- Stage 2B status counts:
  - `Supported`: 8
  - `Conditional`: 3
  - `Usable Range - Assumption-Based`: 1
- Stage 2C forward P/E reconciliation:
  - TradingAgents reported forward P/E: `5.34x`
  - StockAnalysis reported forward P/E: `5.17x`
  - External EPS scenario: `12.70x`
  - Usable range: `5.17x to 12.70x`
  - Specific point estimate remains blocked unless the exact EPS input is independently sourced.
- Stage 4 validated trading horizon:
  - `Conditional Candidate: Intraday / Day Trading, Swing, Positional`
  - Long-term remains not fully validated because full long-horizon moat, cycle-normalized valuation, and durable thesis evidence are not yet complete.

## Graph Comparison Against NVDA

| Metric | MU | NVDA | Result |
|---|---:|---:|---|
| Nodes | 142 | 153 | Comparable; MU has fewer sources and residual gaps. |
| Links / Edges | 335 | 393 | Comparable; NVDA has extra refreshed-claim and proxy-source relationships. |
| Sources | 16 | 22 | Expected difference due to issuer-specific citation set. |
| Report section nodes | 12 | 12 | Passed. |
| Horizon decision nodes | 4 | 4 | Passed. |
| Legal notice nodes | 1 | 1 | Passed. |
| Logo attribution nodes | 1 | 1 | Passed. |
| User technical feature nodes | 7 | 7 | Passed. |
| Computed metric nodes | 1 | 1 | Passed. |

## Report Comparison Against NVDA

- Stage 5 v2 report structure is identical at the framework level:
  - Preserved baseline sections:
    - `final_trade_decision`
    - `market_report`
    - `news_report`
    - `fundamentals_report`
    - `sentiment_report`
    - `investment_plan`
    - `trader_investment_plan`
  - TITAN addenda:
    - Decision reconciliation overlay
    - Normalized technical evidence overlay
    - User-supplied multi-timeframe technical evidence
    - Citation refresh and catalyst evidence overlay
    - SEC fundamentals evidence overlay
    - Valuation and metric reconciliation
    - Validated trading horizon
    - Evidence graph and source audit
    - Self-audit and research quality notes
    - Citations and references
- Baseline title audit:
  - MU: no missing rendered baseline titles.
  - NVDA: no missing rendered baseline titles.
- Logo behavior:
  - MU logo was discovered from Micron's official website and reused as a local approved asset.
  - The logo frame was updated to support white issuer logos on a dark translucent tile.
- Legal notes:
  - Research-only disclaimer appears in the hero.
  - Logo attribution disclaimer appears in the hero and is issuer-specific.

## Graph Interaction Check

The MU graph HTML includes the same interactive behavior as NVDA:

- Node-type dropdown filters the graph visually.
- Legend pills filter the graph visually.
- Dashboard cards filter the graph visually.
- Filters preserve one-hop context so the selected category remains readable.
- Node dragging, pan/zoom, labels, edge toggles, physics toggle, inspector, and clickable source URLs are present.

## Engineering Findings Closed During MU Test

- Stage 2C valuation reconciliation previously contained NVIDIA-specific source IDs and assumptions.
  - Updated to use ticker-generic external valuation and EPS source discovery.
- Stage 4 horizon language previously referenced NVIDIA-specific valuation examples.
  - Updated to use generic “specific forward valuation point estimate” language.
- Stage 5 v2 preview previously contained NVIDIA-specific final-posture, key-level, and logo language.
  - Updated to derive posture, issuer, legal text, and technical levels from packet data.

## Residual Notes

- `titan_integration\report_exporter.py` is a legacy Stage 5 v1 exporter and still contains NVDA-specific narrative examples. The active approved final-report path is Stage 5 v2 via `titan_integration\report_preview_v2.py` and `scripts\export_stage5_v2_final_report.py`.
- MU has no older prior graph before this run. Therefore, the MU delta packet is a seed comparison rather than a true prior-vs-fresh repeated-ticker delta. Future MU reruns will use this graph as the prior context.

## Conclusion

MU passed the second-ticker generalization test for the active equity workflow. The system now demonstrates that Stage 0A through Stage 5 v2 can operate on a non-NVDA equity ticker with issuer-specific citations, user-supplied multi-timeframe data, logo/legal handling, graph overlays, horizon validation, and baseline-preservation rules.
