# Stage 3 Graphify Evidence Graph

Date: 2026-05-02

## Purpose

Stage 3 converts the Stage 1, Stage 2, and Stage 2B evidence packets into a deterministic Graphify-compatible evidence graph.

The objective is to make the evidence structure queryable and auditable before Titan horizon classification, final self-audit, or institutional report generation.

## Why Deterministic

The Stage 1, Stage 2, and Stage 2B packets are already structured JSON artifacts. For this layer, the correct institutional behavior is to preserve explicit relationships rather than ask an LLM to reinterpret them.

Therefore:

- No LLM semantic extraction was used.
- All graph edges come directly from structured packets or manifests.
- Edge confidence is `EXTRACTED` for direct relationships.
- Proxy and contradiction relationships are encoded explicitly.

## Input Artifacts

- Stage 1 packet:
  - `research_packets\stage1\NVDA_2026-05-01_stage1_validation_packet.json`
- Stage 2 packet:
  - `research_packets\stage2\NVDA_2026-05-01_stage2_citation_packet.json`
- Stage 2B packet:
  - `research_packets\stage2b\NVDA_2026-05-01_stage2b_reinforcement_packet.json`
- Stage 2C packet:
  - `research_packets\stage2c\NVDA_2026-05-01_stage2c_metric_reconciliation_packet.json`
- Stage 2 citation manifest:
  - `citation_manifests\nvda_2026-05-01_stage2_sources.json`
- Stage 2B reinforcement manifest:
  - `citation_manifests\nvda_2026-05-01_stage2b_reinforcement.json`

## Output Artifacts

- Graph JSON:
  - `research_packets\stage3_graphify\NVDA_2026-05-01\graph.json`
- Graph audit report:
  - `research_packets\stage3_graphify\NVDA_2026-05-01\GRAPH_REPORT.md`
- Lightweight HTML graph view:
  - `research_packets\stage3_graphify\NVDA_2026-05-01\graph.html`

## Interactive Graph View

The HTML view has been upgraded from a static node/edge list to a self-contained interactive graph explorer.

Current capabilities:

- Force-directed SVG layout
- Node dragging
- Pan and zoom
- Search across nodes, sources, attributes, and edge metadata
- Node-type filtering
- Click-to-inspect node attributes
- Neighbor highlighting
- Inbound and outbound relationship inspection
- Source, claim, residual-gap, computed-metric, packet, manifest, and task color coding
- Toggleable node labels
- Toggleable edge labels
- Fit and reset controls
- Clickable source URLs in the inspector for nodes with external citation links
- Auto-settling graph physics after initial layout stabilization
- Selected-node pinning so clicked nodes remain stable while being inspected

This remains deterministic and local-only. It does not use external JavaScript libraries or a remote service.

## Interaction Stabilization

The first interactive graph used a force-directed layout whose physics continued running indefinitely. That made node selection difficult because nodes could keep shifting after the user moved them into view.

The graph now behaves as follows:

- The force layout runs only during the initial stabilization period.
- After the layout settles, physics is automatically disabled.
- When a user selects a node, that node is pinned and its velocity is cleared.
- Reset restores the graph to a fresh movable layout.
- The physics toggle remains available for manual re-layout when needed.

## Sharing Behavior

The generated `graph.html` is self-contained:

- Graph data is embedded directly in the HTML.
- JavaScript and CSS are embedded directly in the HTML.
- No Python environment is required.
- No project checkout is required.
- No local web server is required.
- No Graphify installation is required.

Anyone receiving the file should be able to open it in a modern browser such as Chrome, Edge, Firefox, or Safari.

Practical caveats:

- Internet access is required only when opening external citation links.
- Local file paths shown in node attributes may not exist on another person's machine.
- Some corporate email/security systems may block or strip HTML files with embedded JavaScript. In that case, share the file through a trusted file-share location or package it in a ZIP.
- If a browser blocks local JavaScript execution due to security policy, host the file from a simple static file server or internal SharePoint/static site.

Recommended sharing approach:

- Share the single `graph.html` file when the recipient only needs the interactive graph.
- Share a ZIP containing `graph.html`, `graph.json`, and `GRAPH_REPORT.md` when the recipient needs audit artifacts as well.

## Single-Step Share Package

A one-step share-package generator has been added so users do not need to manually select graph files.

Command:

```powershell
python scripts\package_graph_share.py
```

Default package output:

- `research_packets\stage3_graphify\NVDA_2026-05-01\NVDA_2026-05-01_interactive_evidence_graph_share_package.zip`

The package includes:

- `graph.html`
- `graph.json`
- `GRAPH_REPORT.md`
- `README_SHARE.md`
- `share_manifest.json`

Recipients should extract the ZIP and open `graph.html` in a modern browser. The HTML remains self-contained for interactive viewing; the JSON, report, README, and manifest are included for audit and handoff traceability.

## Implemented Components

- `titan_integration\evidence_graph.py`
- `scripts\build_stage3_evidence_graph.py`
- `titan_integration\share_package.py`
- `scripts\package_graph_share.py`

## Graph Result

- Nodes: 76
- Edges: 127
- Sources: 20
- Residual gaps: 7
- Computed metrics: 1
- Claim status counts:
  - `Supported`: 9
  - `Contradictory`: 1

## Key Governance Findings

- Forward valuation remains a blocking contradiction.
  - The graph links contradiction specifically to StockAnalysis valuation and forecast evidence.
  - Context sources remain context links rather than contradiction links.
  - Stage 2C adds a computed Forward P/E node showing that TradingAgents' `17.7x` is internally coherent only with its unsourced `$11.24` forward EPS estimate.
  - NVIDIA guidance-derived and externally sourced EPS checks imply materially higher forward multiples, so final Titan language must keep the valuation blocked unless the EPS estimate is independently sourced.

- Ecosystem evidence is supported but remains proxy evidence.
  - The graph labels Micron and Vertiv relationships as proxy support.
  - Proxy evidence must not be treated as direct NVIDIA revenue validation.

- Macro/geopolitical evidence is supported as broad context.
  - The graph separates macro backdrop from issuer-specific catalyst validation.

- Horizon classification is not yet performed.
  - Stage 3 supplies the evidence substrate for the Validated Trading Horizon gate.

## Next Step

Stage 4 should apply Titan horizon validation over the evidence graph.

That stage must independently evaluate Intraday, Swing, Positional, and Long-Term classifications using the graph-backed evidence structure, preserving Conditional or Not Validated statuses where required evidence remains incomplete, contradictory, or not aligned with Titan standards.
