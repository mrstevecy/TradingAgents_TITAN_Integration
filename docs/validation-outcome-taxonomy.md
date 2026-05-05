# Validation Outcome Taxonomy

Date: 2026-05-02

## Purpose

This taxonomy is core business logic for the research system. It applies to all
future research cycles across tickers, instruments, and asset classes.

## Outcomes

| Outcome | Required Interpretation |
|---|---|
| `Validated` | Evidence fully satisfies Titan requirements. |
| `Conditional` | Evidence is useful and directionally relevant, but additional confirmation is required. |
| `Conditional Candidate` | Candidate quality is present before full validation is possible, such as pre-open intraday setups awaiting live tape. |
| `Not Validated` | The required evidence stack is incomplete, insufficiently aligned, or not collected for that horizon or claim. |
| `Blocked` | A specific claim is not acceptable because evidence is contradictory, unsourced, proxy-only, or fails Titan criteria. |
| `Usable Range - Assumption-Based` | A range can be used when assumptions are explicit and independently sourced scenarios reasonably cluster. |

## Business Rules

- Always explain why an item is blocked, conditional, or not validated.
- Do not let a blocked point estimate automatically invalidate a broader
  valuation range.
- Do not use an assumption-based range to validate an unsupported point estimate.
- Do not treat proxy evidence as direct issuer validation.
- Do not convert pre-open intraday evidence into a validated intraday trade call.
- Do allow pre-open conditional intraday candidate classification when technical,
  liquidity, catalyst, macro, and event context justify monitoring the open.

## NVDA Current Example

- Specific `17.7x` forward P/E point estimate: `Blocked`.
- Forward P/E range around `24.28x` to `29.14x`: `Usable Range - Assumption-Based`.
- Intraday: `Conditional Candidate`, requiring live tape/opening confirmation.
- Swing: `Conditional`.
- Positional: `Conditional Candidate`.
- Long-Term: `Not Validated`, because moat, secular thesis, balance-sheet,
  durable-return, and complete cycle-aware valuation evidence are not fully
  source-mapped.
