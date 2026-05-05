# ADR-0004: Universal Research Framework

Date: 2026-05-02

## Status

Accepted

## Context

The current implementation is an equity-first Titan wrapper around
TradingAgents, validated with NVDA. Titan OS 2.9 and Titan DTP 1.6 require a
broader path toward multi-instrument and multi-asset research without breaking
the working equity flow.

## Decision

Add Stage 0A as a universal request-resolution layer before asset-specific
research stages.

Stage 0A defines a canonical request containing:

- `asset`
- `ticker`
- `full_name`
- `instrument_type`
- `asset_class`
- `primary_strategy`
- `trading_horizon`
- `execution_platform`
- `analysis_date`
- `input_folder`

Stage 0A also defines an instrument registry. In v1, only `Equity` is
implemented. Other profiles are registered but explicitly not implemented.

## Consequences

- The existing equity workflow remains the reference implementation.
- Unsupported asset classes stop gracefully instead of receiving fake equity
  analysis.
- Future ETF, index, crypto, FX, futures, commodity, CFD, and options support
  can be added as modular profiles.
- Titan evidence and horizon validation stay as the common governance layer
  across future asset classes.
