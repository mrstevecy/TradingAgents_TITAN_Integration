# Stage 2D Stale Claim Refresh

Date: 2026-05-02

## Purpose

Stage 2D resolves a specific repeated-research problem: a claim may be
supported in a prior graph, but absent from a fresh TradingAgents run because
the model did not repeat that claim. Without a refresh layer, the evidence delta
marks the item as `Stale` even when prior source evidence remains usable.

Stage 2D consumes:

- prior evidence graph
- fresh evidence delta packet

It refreshes prior supported source nodes for stale claims and emits a packet
that Stage 3 can graph as current refreshed evidence.

## Implemented Components

- `titan_integration\stale_claim_refresh.py`
- `scripts\build_stage2d_stale_claim_refresh_packet.py`
- Stage 3 integration through:
  - `titan_integration\evidence_graph.py`
  - `scripts\build_stage3_evidence_graph.py`

## NVDA Verification

Input delta:

```text
D:\Projects\CodeX\TradingAgents_Integration\research_packets\evidence_delta\NVDA_2026-05-02_evidence_delta_packet.json
```

Output packet:

```text
D:\Projects\CodeX\TradingAgents_Integration\research_packets\stage2d_stale_claim_refresh\NVDA_2026-05-02_stage2d_stale_claim_refresh_packet.md
```

Refreshed stale claims:

- `Next earnings timing claim`
- `Pentagon AI contract claim`

Status counts:

```json
{
  "Supported": 2
}
```

Source reachability:

- `nvidia_q1_fy2027_call`: `Available`, HTTP 200
- `marketbeat_nvda_q1_2027`: `Reachability Restricted`, HTTP 403
- `dow_classified_ai_agreements`: `Reachability Restricted`, HTTP 403

Restricted reachability does not mean the source is invalid; it means the
automation could not retrieve the page directly during the check. Stage 2D keeps
that limitation explicit in the refreshed source metadata.

## Downstream Result

After Stage 2D was added to the Stage 3 graph:

- Graph nodes: `91`
- Graph edges: `164`
- Refreshed claims: `2`
- Delta stale count: `0`

Updated evidence delta counts:

```json
{
  "Newly Discovered": 4,
  "Still Blocked": 2,
  "Unchanged Supported": 8,
  "Updated": 1
}
```

Stage 4 now has:

- `stale_claim_count`: `0`
- Validated Trading Horizon: `Conditional: Swing`

The remaining blocker is valuation, not stale catalyst or earnings timing
evidence.

## Governance Notes

- Stage 2D refreshes evidence; it does not create new claims without prior graph support.
- Refreshed claims remain subject to Titan horizon validation and self-audit.
- Reachability restrictions must be preserved in the graph and final report notes.
- Stage 2D does not resolve valuation contradictions.
