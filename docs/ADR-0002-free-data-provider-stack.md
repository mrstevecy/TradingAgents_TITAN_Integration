# ADR-0002: Free Data Provider Stack

Date: 2026-05-02

## Status

Accepted.

## Context

The TradingAgents/Titan integration needs a cost-controlled data stack for local development before any paid institutional feed is introduced.

The stack must support:

- price/technical prototypes,
- official fundamentals and filings,
- source-audit metadata,
- fallback behavior,
- later migration to paid feeds without rewriting the Titan wrapper.

## Decision

Use a normalized provider abstraction outside the upstream TradingAgents repo.

Active initial providers:

- `yfinance`
  - Role: broad prototype OHLCV and initial technical data.
  - Reliability label: `prototype`.
  - Caveat: unofficial Yahoo Finance access; not sole institutional source.

- `sec_edgar`
  - Role: official U.S. filings, CIK mapping, XBRL company facts, recent filing metadata.
  - Reliability label: `official`.
  - Caveat: requires careful concept mapping and SEC-compliant user-agent configuration.

- `stooq`
  - Role: historical EOD CSV fallback.
  - Reliability label: `fallback`.
  - Caveat: Stooq does not provide an official documented public API with API
    keys. Any programmatic use should be treated as unofficial CSV/download or
    scraping-style fallback access, not an institutional primary source.

Inactive optional providers:

- `alpaca_basic`
  - Use later for structured intraday/IEX data if account keys and entitlement rules are configured.

- `alpha_vantage`
  - Keep as optional enrichment only. Do not make it a core dependency because the free tier is limited to 25 requests/day.

## Implementation

Files added under:

- `titan_integration\data_providers`

Core files:

- `schemas.py`
- `base.py`
- `registry.py`
- `yfinance_provider.py`
- `sec_edgar_provider.py`
- `stooq_provider.py`
- `optional.py`

Probe script:

- `scripts\probe_data_providers.py`

Probe output:

- `outputs\data_provider_probe\NVDA_provider_probe.json`

## Validation

Docker probe succeeded for:

- `yfinance` price bars for `NVDA`.
- `sec_edgar` CIK, company facts, and recent filings for `NVDA`.

Stooq behavior:

- Stooq remains optional fallback-only evidence.
- Direct CSV URL patterns and wrappers such as `pandas-datareader` are
  unofficial access paths.
- Excessive automated use may be rate-limited or blocked.
- No malformed CSV parsing should be allowed to contaminate the typed evidence
  store.

## Configuration

Recommended environment variables:

- `SEC_EDGAR_USER_AGENT`
  - Set to an identifiable research user-agent string.

Future optional variables:

- `ALPACA_API_KEY_ID`
- `ALPACA_API_SECRET_KEY`
- `ALPHA_VANTAGE_API_KEY`

## Consequences

Positive:

- Keeps upstream TradingAgents clean.
- Creates a stable normalization boundary.
- Makes source-audit metadata first-class.
- Allows later provider replacement or cross-checking.

Trade-offs:

- yfinance remains suitable only for prototype use.
- SEC EDGAR fundamentals require concept-level normalization before final Titan reports.
- Stooq fallback is unofficial and should not be relied on as a primary
  market-data source.
- Intraday full-market coverage still requires either paid data or a separately entitled provider.

## Next Step

Build the first Titan validation packet generator that consumes:

- TradingAgents raw output,
- normalized price bars,
- SEC facts/filings,
- provider audit metadata.

The packet should not yet claim full Titan validation; it should expose evidence availability, source quality, and gaps.
