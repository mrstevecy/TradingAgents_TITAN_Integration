# ADR-0003: Local Data Separation and Graphify Integration

Date: 2026-05-02

## Status

Accepted.

## Context

The integration project will produce local research artifacts, provider outputs, SEC data, Stooq data, Titan validation packets, Graphify graphs, and potentially corpus-derived intermediate files.

These artifacts must not be mixed with version-controlled project code.

## Decision

Maintain a strict separation between:

- project code and documentation that may be version controlled,
- local data and generated research artifacts that must never be committed.

Local-only paths are ignored through the project `.gitignore`:

- `data/`
- `corpus/`
- `outputs/`
- `research_materials/`
- `graphify-out/`
- `provider_cache/`
- `normalized_data/`
- `research_packets/`
- `logs/`
- `cache/`
- `embeddings/`

Environment and secrets are also ignored:

- `.env`
- `.env.*`

The upstream `TradingAgents\.env` remains ignored by the upstream repository and now contains placeholders for:

- `SEC_EDGAR_USER_AGENT`
- `STOOQ_API_KEY`

## Graphify Position

Graphify is strategically aligned with this project, but it should be introduced as a governed wrapper-layer capability rather than as an upstream TradingAgents modification.

Recommended uses:

- Convert curated research packets, corpora excerpts, filings, and source notes into graph artifacts.
- Support evidence linkage and claim-to-source traceability.
- Store EXTRACTED / INFERRED / AMBIGUOUS edges for auditability.
- Improve retrieval for Titan validation and report generation.
- Preserve Graphify outputs under local-only ignored paths.

Non-goals:

- Do not commit Graphify outputs to Git.
- Do not use Graphify to bypass Titan evidence gates.
- Do not allow inferred graph edges to become validated claims without source verification.
- Do not inject full graph/corpus dumps into TradingAgents prompts.

## Relationship to Titan Validation Packet Stage 1

Stage 1 should be built without requiring Graphify first.

Graphify can be layered in after Stage 1 as an evidence-linking accelerator:

1. Stage 1 creates structured claim/evidence/source packets.
2. Graphify turns packets and curated corpora into navigable knowledge graphs.
3. Later Titan stages use graph retrieval to strengthen source linkage and audit trails.

## IBKR Data Source Review

The reviewed IBKR Quant article lists free or limited sources such as Alpha Vantage, Yahoo Finance/yfinance, Interactive Brokers, Alpaca, Investing.com, Stooq, Quandl/Nasdaq Data Link, Tiingo, FRED, and CoinDesk. It also emphasizes provider selection criteria:

- accuracy and reliability,
- latency and speed,
- historical data availability,
- cost and subscription limits,
- missing-data handling,
- corporate-action adjustments,
- time-zone and data synchronization.

This supports the current architecture:

- use `yfinance` for prototype OHLCV only,
- use SEC EDGAR for official fundamentals,
- keep Stooq as a fallback,
- keep Alpha Vantage and Alpaca optional,
- add source-audit metadata and validation checks before final reports.

Source:

- https://www.interactivebrokers.com/campus/ibkr-quant-news/historical-market-data-sources/

## Next Step

Proceed to Titan Validation Packet Stage 1 only after:

- `SEC_EDGAR_USER_AGENT` is updated with a real contact email,
- the user decides whether to activate Stooq fallback with `STOOQ_API_KEY`,
- data and Graphify separation is documented.
