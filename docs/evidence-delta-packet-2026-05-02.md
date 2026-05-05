# Evidence Delta Packet

Date: 2026-05-02

## Purpose

The Evidence Delta Packet compares prior graph-backed research against a fresh evidence graph before Stage 4 horizon validation.

Its purpose is to prevent repeated ticker research from either:

- Re-processing everything from scratch without using prior grounded evidence, or
- Reusing prior evidence as if it were current without fresh timestamped validation.

## Implemented Components

- `titan_integration\evidence_delta.py`
- `scripts\build_evidence_delta_packet.py`

## Input Artifacts

Initial NVDA structural test:

- Prior graph:
  - `research_packets\stage3_graphify\NVDA_2026-05-01\graph.json`
- Fresh graph:
  - `research_packets\stage3_graphify\NVDA_2026-05-01\graph.json`

Because the same graph is used for the first test, this packet is a structural validation of the delta layer, not a true fresh-market update.

True NVDA fresh-market update:

- Prior graph:
  - `research_packets\stage3_graphify\NVDA_2026-05-01\graph.json`
- Fresh graph:
  - `research_packets\stage3_graphify\NVDA_2026-05-02\graph.json`
- Fresh TradingAgents run:
  - `outputs\deepseek_fresh_baseline\NVDA_2026-05-02_deepseek_fresh_baseline_summary.json`

## Output Artifacts

- JSON:
  - `research_packets\evidence_delta\NVDA_2026-05-02_evidence_delta_packet.json`
- Markdown:
  - `research_packets\evidence_delta\NVDA_2026-05-02_evidence_delta_packet.md`

## Delta Classifications

Initial structural-test result:

- `Needs Fresh Evidence`: 9
- `Still Blocked`: 2

`Needs Fresh Evidence` means the claim was supported in the prior graph but must be refreshed before it can be treated as current.

`Still Blocked` means the item cannot enter final Titan language until the blocking evidence issue is resolved.

True fresh-market result:

- `Unchanged Supported`: 6
- `Updated`: 2
- `Stale`: 2
- `Still Blocked`: 1

`Updated` means the prior graph and fresh graph both contain the item but the status or value changed.

`Stale` means the prior graph contained an item that the fresh graph did not reproduce. This does not automatically invalidate the item; it requires a freshness check before Stage 4.

## NVDA Result

Still blocked after fresh run:

- Forward valuation claim: `Contradictory`

Updated after fresh run:

- TradingAgents final stance changed from `Hold` to `Underweight`.
- Forward P/E changed from `Computed - Source Conflict Preserved` to `Not Computable - Missing Explicit Input` because the fresh run did not expose the complete ratio input set.

Unchanged supported:

- April 30 high-volume down-day/distribution warning
- Ecosystem proxy claims
- Macro/geopolitical claims
- Official SEC evidence availability
- Price below short-term trend but above 50-day and 200-day averages
- TradingAgents reference price alignment with normalized market data

Stale and requiring freshness review:

- Pentagon AI contract claim
- Next earnings timing claim

## Robustness Fixes Added

The fresh run exposed two wrapper issues before Stage 4:

- Stage 1 previously hard-coded a `HOLD` stance claim label. It now generates the stance claim dynamically from the current run.
- Stage 1 previously hard-coded a prior reference price level. It now anchors the claim to normalized market data for the requested trade date.
- Stage 2C previously failed when a fresh run omitted explicit forward EPS input text. It now emits `Not Computable - Missing Explicit Input` and keeps valuation blocked rather than crashing or inferring a ratio.
- The delta layer now normalizes TradingAgents stance into one stable item so business users see `Hold -> Underweight` instead of separate stale/new stance rows.

## Next Step

The fresh NVDA repeat-ticker update has now been completed. The output should feed Stage 4 Titan horizon validation.

Stage 4 must treat:

- `Still Blocked` valuation evidence as unavailable for validated positional/long-term valuation support.
- `Updated` stance and metric evidence as requiring explicit rationale.
- `Stale` catalyst/timing claims as needing freshness review before horizon classification.

Future repeat-ticker updates should continue to classify changes as:

- Unchanged supported
- Strengthened
- Weakened
- Blocked
- Still blocked
- Stale
- Newly discovered
- Needs fresh evidence
