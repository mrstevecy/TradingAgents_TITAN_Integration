# Instrument Registry

Date: 2026-05-02

## Purpose

The instrument registry defines which asset and instrument profiles the
universal framework understands, and whether each profile is currently
implemented.

## Registry Status

| Instrument Type | Asset Class | Status | Notes |
|---|---|---|---|
| `Equity` | `Equity` | Implemented | Uses the existing NVDA-tested equity workflow. |
| `ETF` | `ETF` | Registered But Not Implemented | Next profile after equity; requires holdings, NAV, flows, liquidity, sponsor, expense, and exposure evidence. |
| `Index` | `Index` | Registered But Not Implemented | Planned after ETF; requires constituents, breadth, sector weights, methodology, factor/macro regime, and proxy mapping. |
| `Equity-Option` | `Equity` | Registered But Not Implemented | Planned after Equity v1 stabilization; requires contract-specific expiry, strike, IV, Greeks, OI, volume, spread, skew, event risk, and underlying linkage. |
| `ETF-Option` | `ETF` | Registered But Not Implemented | Planned after ETF profile; requires option chain, ETF exposure model, liquidity, IV/skew, and underlying ETF evidence. |
| `Index-Option` | `Index` | Registered But Not Implemented | Planned after Index profile; requires index option chain, settlement/exercise style, macro/index evidence, IV/skew, and breadth/futures proxy context. |
| `Crypto` | `Crypto` | Registered But Not Implemented | Planned after equity-adjacent and listed-option foundations; requires venue, liquidity, 24/7 session, regulatory/news, and optional on-chain evidence. |
| `FX` | `FX` | Registered But Not Implemented | Requires macro, rates, central-bank, calendar-event, positioning, and pair-specific evidence model. |
| `Futures` | `Futures` | Registered But Not Implemented | Requires contract metadata, front/next mapping, roll, curve, open interest, tick value, margin, and expiry/session logic. |
| `Commodity` | `Commodity` | Registered But Not Implemented | Requires futures/spot mapping plus supply/demand and commodity-specific evidence. |
| `CFD` | `Commodity / FX / Index / Equity` | Registered But Not Implemented | Planned only after the relevant underlying profile exists; requires platform-specific symbol mapping, spread, financing, leverage/margin, and contract specs. |
| `Futures-Option` | `Futures` | Registered But Not Implemented | Advanced derivative profile after futures and listed-option models are stable. |
| `Commodity-Option` | `Commodity` | Registered But Not Implemented | Advanced derivative profile after commodity and options evidence models are stable. |
| `Crypto-Option` | `Crypto` | Registered But Not Implemented | Advanced derivative profile after crypto spot and options evidence models are stable. |

## Equity v1 Active Profile

The `Equity` profile enables:

- TradingAgents baseline summary
- yfinance prototype OHLCV
- SEC EDGAR fundamentals and filings
- Stage 1A user evidence ingestion
- Stage 1B user technical feature extraction
- Stage 2 citation linking
- Stage 2B evidence reinforcement
- Stage 2C metric reconciliation
- Stage 3 evidence graph
- Evidence delta
- Stage 4 horizon validation

## Governance Rule

Registered but unimplemented profiles must return a clear unsupported-profile
packet. They must not reuse equity assumptions, SEC-only fundamentals, or
equity valuation rules.

## Dependency Rule

Derivative profiles depend on the underlying profile. For example:

- `Equity-Option` depends on `Equity`.
- `ETF-Option` depends on `ETF`.
- `Index-Option` depends on `Index`.
- `Futures-Option` depends on `Futures`.
- `Commodity-Option` depends on `Commodity`.
- `CFD` depends on the relevant underlying spot, futures, index, equity, FX, or commodity model plus platform-specific contract evidence.

An underlying-only report is not sufficient for an option, futures-option, commodity-option, crypto-option, CFD, spread, or multi-leg strategy. The derivative contract must receive its own evidence packet, validation checks, and risk model.
