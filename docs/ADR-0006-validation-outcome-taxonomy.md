# ADR-0006: Validation Outcome Taxonomy

Date: 2026-05-02

## Status

Accepted

## Context

Prior packets used labels such as `Blocked`, `Conditional`, and `Not
Validated`, but the business meaning was not always explicit. This created risk
that users could interpret a blocked point estimate as meaning the entire
research area was unusable, or interpret not validated as missing effort rather
than failed or incomplete Titan evidence.

## Decision

Adopt a core validation-outcome taxonomy across all future research cycles and
asset classes:

| Outcome | Meaning |
|---|---|
| `Validated` | All mandatory evidence blocks are collected, cross-verified, aligned, and audit-passed. |
| `Conditional` | Evidence is materially useful, but one or more required confirmation blocks remain incomplete or conditional. |
| `Conditional Candidate` | Pre-validation evidence supports monitoring or further research, but final validation depends on future/session-specific confirmation. |
| `Not Validated` | Required evidence for that horizon or claim is not sufficiently present, aligned, or complete. |
| `Blocked` | A specific claim cannot be accepted because evidence is contradictory, unsourced, proxy-only, or fails Titan criteria. |
| `Usable Range - Assumption-Based` | A metric range is usable when assumptions are explicit and independently sourced scenarios reasonably cluster, even if a specific point estimate remains blocked. |

## Consequences

- A blocked point estimate does not automatically block a broader assumption
  range if independently sourced scenarios cluster.
- Intraday can be a `Conditional Candidate` before live tape if the pre-session
  evidence stack supports monitoring, but it cannot be `Validated` without live
  microstructure confirmation.
- Positional and long-term horizons may use assumption-based valuation ranges,
  but final validation still requires their full Titan evidence stacks.
- All reports must state why each non-validated, conditional, or blocked item
  received that status.
