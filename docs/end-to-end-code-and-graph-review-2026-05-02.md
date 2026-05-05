# End-to-End Code and Graph Review

Date: 2026-05-02

## Scope

Reviewed the current NVDA pipeline from structured evidence packet generation
through final Stage 5 v2 report export:

- Stage 1 price / SEC / user evidence packet
- Stage 1A user evidence ingestion
- Stage 1B user technical feature packet
- Stage 2 citation packet
- Stage 2B reinforcement packet
- Stage 2C metric reconciliation packet
- Stage 2D stale claim refresh packet
- Stage 3 evidence graph
- Evidence delta packet
- Stage 4 horizon validation packet
- Stage 5 v2 preview/final HTML, Markdown, and PDF export
- Logo/theme/legal notice layer
- Publication safety check

## Checks Performed

- Python compile check:
  - `python -m compileall titan_integration scripts`
- Publication safety check:
  - `python scripts\publication_safety_check.py`
- Final report text checks:
  - `Trading Team Plan` absent
  - `Trader Investment Plan` present
  - `Research-only` present
  - `Logo notice` present
  - `Not Titan-Compliant` absent from final reader-facing report
- Final report manifest check:
  - `final_markdown_pdf_paused` now correctly reports `false`
- Stage 3 graph rebuild:
  - `research_packets\stage3_graphify\NVDA_2026-05-02`
- Graph visual smoke check:
  - `output\playwright\stage3_graph_review_after_fix.png`

## Fixes Applied During Review

1. Final report manifest correction:
   - File: `scripts\export_stage5_v2_final_report.py`
   - Issue: final export inherited the preview manifest field
     `final_markdown_pdf_paused: true`.
   - Fix: final export now overrides it to `false`.

2. Graph drag stability:
   - File: `titan_integration\evidence_graph.py`
   - Issue: node drag release reset `node.fixed = false`, allowing dragged nodes
     to move back under physics.
   - Fix: dragged nodes now remain fixed until reset/physics controls are used.

## Current Graph Assessment

Current graph artifact:

- `research_packets\stage3_graphify\NVDA_2026-05-02\graph.html`
- `research_packets\stage3_graphify\NVDA_2026-05-02\graph.json`

Current graph metrics:

- Nodes: `90`
- Edges: `162`
- Sources: `22`
- Residual gaps: `6`
- Claims: `14`
- Computed metrics: `1`

The graph currently supports:

- Interactive SVG rendering
- Search
- Node-type filtering
- Reset / fit
- Label and edge-label toggles
- Physics toggle
- Node list
- Inspector panel
- Source-link rendering for source nodes
- Relationship navigation through `selectEvidenceNode`

## Remaining Graph Gap

The current graph is still a Stage 3 evidence graph. It contains Stage 1 through
Stage 2D evidence, user technical features, metric reconciliation, refreshed
claims, sources, and residual gaps.

It does **not** yet fully represent:

- Stage 4 horizon validation decisions
- Horizon-specific evidence blocks
- Stage 5 final report sections
- Final report legal/logo/theme metadata
- Final report reader-facing conclusions

This means the graph is useful for evidence navigation, but it is not yet a
complete final-report traceability graph. The recommended next build step is a
Stage 3F / Stage 5 graph overlay that adds final report and horizon-validation
nodes without altering the deterministic Stage 3 evidence graph.

## Recommendation

Before treating the graph as the single source of evidence navigation for
business users, implement a final-report graph overlay with:

- `stage4_horizon_packet` node
- one node per horizon decision
- horizon evidence/support/gap edges
- `stage5_final_report` node
- report section nodes
- legal notice / logo attribution nodes
- links from report conclusions back to supporting evidence nodes

This will close the mismatch between the final PDF and the current evidence
graph.
