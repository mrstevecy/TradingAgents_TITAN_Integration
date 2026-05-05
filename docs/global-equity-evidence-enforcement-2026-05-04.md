# Global Equity Evidence Enforcement

Date: 2026-05-04

## Purpose

This patch converts the MSFT corrected-report findings into code-level equity
research gates. Microsoft is used only as a regression fixture; the production
logic is ticker-generic for the active `Equity v1` workflow.

## Implemented Enforcement

- Typed equity evidence store with source ranking, statuses, timestamps,
  limitations, blocking gaps, resolver attempts, and agent-facing context.
- Mandatory equity data scan before non-interactive TradingAgents baseline
  execution.
- Code validators and resolvers for earnings classification, CapEx guidance
  precedence, FCF reconciliation, forward P/E resolution, analyst consensus,
  earnings date confidence, short-interest positioning dependency, peer
  comparison scale context, five-round debate validation, contamination checks,
  Research Manager adjudication, and Portfolio Manager sanity checks.
- Persistent error-learning records with role-specific feedback memory,
  evidence-dependency tracking, and recurrence escalation.
- Stage 1 and Stage 5 v2 visibility for the mandatory equity scan and global
  enforcement gates.
- Hybrid public-first retrieval discipline: direct provider/official adapters
  run first, and unresolved facts record fallback web-discovery search
  categories and source classes before a gap is accepted.
- Stage 2B source-to-fact promotion. Validated citation and reinforcement
  sources now produce a promoted typed evidence artifact instead of remaining
  isolated citation text.
- Semantic five-round debate validation:
  Opening Thesis, Data Challenge, Narrative Counter, Invalidation Stress-Test,
  and Convergence / Residual Disagreement must appear in order with evidence
  keys and both Bull/Bear participation.
- Stage 5 clean-report rendering. Raw baseline passages that trigger blocked
  evidence dependencies are removed from ordinary narrative and shown only in
  the controlled Excluded Claims / Errors and Recommendations table.
- Official/issuer source deep-read promotion. When Stage 2 or Stage 2B cites an
  issuer IR, SEC, earnings-release, filing, or transcript URL, the promotion
  layer now reads the source body before typing facts. This prevents short
  citation summaries from hiding facts already present on the issuer page, such
  as commercial remaining performance obligation / RPO, cash-flow values, or
  guidance context.
- SEC cash-flow extraction. The SEC EDGAR adapter now carries operating cash
  flow and property/equipment CapEx concepts from companyfacts into the typed
  evidence store. FCF is computed centrally from same-period OCF minus CapEx.
- RPO/backlog handling is business-model and claim conditional. RPO is required
  when the company or thesis relies on subscription, cloud, backlog, or
  contracted-revenue visibility. It is not a blind universal blocker for every
  equity ticker.
- Stale earnings-date conflicts are diagnostic once the canonical earnings
  event state is resolved. A stale May-style date is quarantined and prevented
  from reader-facing narrative, but it does not force `DATA-INCOMPLETE` if the
  latest reported and next estimated dates are already validated.
- Provider-scan fallback. If a local optional market-data dependency is missing
  during Stage 1, valid provider/tool evidence already captured by the baseline
  run may be reused instead of erasing market context.

## Workflow Impact

The baseline runner now runs `run_equity_data_scan(ticker, trade_date)` before
agents begin. The generated evidence context is passed into agent state and
written to the baseline summary artifact.

Before agents begin, the baseline runner also loads
`research_packets\error_learning\agent_error_records.json`, builds
role-specific operational-learning context for each analyst, researcher,
trader, risk analyst, Research Manager, and Portfolio Manager, and injects only
the relevant prior failures into that role's prompt surface. The common
evidence store remains available to all agents, but a CapEx guidance failure by
the Fundamentals Analyst does not become ordinary context for the News Analyst,
and a short-interest failure by the sentiment layer is routed back to the
sentiment role and final decision gates.

The default Bull/Bear debate setting is five rounds. The baseline runner
hard-fails if the final debate contribution count is below ten contributions.

Final reporting remains productive under evidence gaps, but dependent claims
must remain constrained until resolvers retrieve or compute the required facts.

Stage 2B also writes:

```text
research_packets\stage2b\<TICKER>_<DATE>_equity_evidence_store_promoted.json
```

This promoted store lets downstream governance use source-backed facts found
after Stage 1, such as analyst consensus, short interest, guidance, transcripts,
earnings dates, and cash-flow/CapEx evidence.

## Verification

Targeted verification:

```powershell
cd D:\Projects\CodeX\TradingAgents_Integration\TradingAgents
uv run pytest tests/test_global_equity_evidence_enforcement.py tests/test_institutional_evidence_policy.py -q
```

Latest targeted result after the issuer/SEC promotion patch:

- `65 passed` for `tests/test_global_equity_evidence_enforcement.py`

Full publication verification remains required before GitHub push.
