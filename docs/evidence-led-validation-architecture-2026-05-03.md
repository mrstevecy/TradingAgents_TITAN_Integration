# Evidence-Led Validation Architecture

Date: 2026-05-03

## Purpose

This update strengthens the research workflow at the root of the hallucination
problem. Agent prose, debate output, and report text may propose claims, but
they no longer have authority to mark external facts as validated by themselves.

Validation authority belongs to structured evidence records:

- source ID
- publisher
- title
- URL
- publication date
- retrieval timestamp
- source class
- supported claims
- limitations

If a claim cannot be linked to an as-of-valid source record whose supported
claims or extracted facts match the claim, the system must keep the claim
conditional, not validated, blocked, or explicitly gap-labeled.

## Implemented Components

Code:

- `titan_integration\evidence_ledger.py`
- `titan_integration\retrieval_plan.py`
- `titan_integration\citation_retrieval.py`
- `titan_integration\evidence_reinforcement.py`

Tests:

- `TradingAgents\tests\test_institutional_evidence_policy.py`

## Evidence Ledger Rule

The evidence ledger is the system of record for validation. It enforces:

- No source ID means no validated external fact.
- Missing source IDs are downgraded to `Not Validated`.
- Future-dated publication sources are excluded for as-of research conclusions.
- Future catalyst/event dates remain valid when the source publication or
  retrieval date is valid as of the research date.
- A source must support the actual claim, not merely appear in the same packet.
- LLM-generated text may describe an assumption or gap, but cannot validate the
  fact.

## Retrieval Plan Rule

The retrieval plan defines what the system must attempt before treating evidence
as unavailable. For equity research, mandatory tasks include:

- latest company guidance and filing-backed outlook
- price, volume, and liquidity context
- valuation basis and estimate inputs
- catalyst calendar and event timing
- sentiment, analyst consensus, and positioning
- macro, policy, industry, and news context

Each task defines primary, secondary, and fallback source classes. A missing-data
outcome is acceptable only after the appropriate source classes have been
attempted and documented.

## Stage 2 and Stage 2B Integration

Stage 2 citation linking now builds an evidence ledger from the citation manifest
and Stage 1 provider records before assigning claim status.

Stage 2B reinforcement now validates reinforcement outcomes through the same
ledger before upgrading a claim.

This means a manifest rule or reinforcement task can request `Supported`, but
the ledger can still downgrade the outcome when:

- the source record is missing,
- the source is future-dated relative to the research date,
- the source exists but does not match the claim,
- or no source ID is attached.

Stage 2B task matching was also tightened so broad single-word task patterns
cannot accidentally attach a reinforcement task to an unrelated claim. For
example, a task intended for issuer earnings context must not upgrade a separate
next-earnings-calendar claim merely because both contain the word "earnings."

## Global Scope

This implementation is ticker-agnostic. It does not reference MU, NVDA, or any
single test case in the validation logic. The same ledger and retrieval-plan
rules apply to future tickers and to additional asset-class profiles as they are
implemented.

## Current Limit

The system now has the enforcement layer that prevents unsupported validation
labels from surviving Stage 2 and Stage 2B. The next production-grade upgrade is
automated source retrieval, so manifests can be built by source adapters rather
than manual curation.
