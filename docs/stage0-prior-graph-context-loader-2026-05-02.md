# Stage 0 Prior Graph Context Loader

Date: 2026-05-02

## Purpose

Stage 0 loads prior graph-backed research for the same ticker or asset before a fresh run begins.

This is the continuity layer. It ensures the system does not re-process everything from scratch when prior research already contains grounded evidence, timestamps, source metadata, computed metrics, residual gaps, and graph relationships.

## Implemented Components

- `titan_integration\prior_graph_context.py`
- `scripts\load_prior_graph_context.py`

## Output Artifacts

For the NVDA test case:

- JSON:
  - `research_packets\prior_context\NVDA_2026-05-02_prior_graph_context.json`
- Markdown:
  - `research_packets\prior_context\NVDA_2026-05-02_prior_graph_context.md`

## Current Behavior

For `NVDA` as of `2026-05-02`, the loader found the prior graph:

- `research_packets\stage3_graphify\NVDA_2026-05-01\graph.json`

It extracted:

- Prior research date
- Graph path
- Node count
- Edge count
- Claim status counts
- Computed metric count
- Residual gap count
- Reusable supported claims
- Blocked items requiring refresh

## Continuity Rules

Prior graph context must be treated as historical evidence, not automatically current evidence.

For each repeated ticker or asset run, the system must:

- Load prior graph context before the new analysis.
- Reuse supported claims only as timestamped context.
- Refresh time-sensitive evidence:
  - Price
  - Volume
  - Technical structure
  - Newsflow
  - Macro environment
  - Earnings and estimates
  - Catalysts
  - Valuation ratios
- Carry prior blocked items into the new research plan.
- Generate an evidence delta packet before final reporting.
- Never reuse prior horizon classifications without fresh Titan horizon validation.

## NVDA Prior Context Result

Reusable supported claims include:

- TradingAgents final stance was `HOLD`.
- Reference close and technical structure were supported by Stage 1 provider evidence.
- SEC EDGAR evidence existed for core financial facts.
- Pentagon AI contract claim was supported by official source evidence.
- Ecosystem proxy claims were supported but remain proxy evidence.
- Macro/geopolitical claims were supported as broad context.
- Next earnings timing was supported by company and secondary-market-data sources.

Blocked / refresh items:

- Forward valuation claim: `Contradictory`
- Forward P/E: `Computed - Source Conflict Preserved`

## Next Step

The next architecture layer should be an evidence delta packet. It will compare the prior graph against fresh evidence and classify each item as:

- Unchanged
- Updated
- Strengthened
- Weakened
- Contradicted
- Stale
- Newly discovered

That delta should feed Stage 4 Titan horizon validation and final report generation.
