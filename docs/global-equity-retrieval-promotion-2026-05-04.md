# Global Equity Retrieval and Evidence Promotion Patch

Date: 2026-05-04

## Summary

This patch strengthens the Equity v1 workflow so mandatory public evidence can
be retrieved, parsed, typed, promoted, and injected before analyst generation.
The implementation keeps report gates strict; the goal is to reduce false
missing-evidence states by making resolver outputs available earlier.

## Implemented Changes

- Added a pre-agent public equity resolver layer:
  - public/fixture source collection
  - source typing as direct issuer, regulatory, transcript/news/aggregator, or
    proxy context
  - source metadata for retrieval method, URL, as-of date, confidence, and
    direct/proxy classification
- Added dynamic web-RAG query planning:
  - every unresolved evidence key now receives a source-aware query plan rather
    than only one or two generic web searches
  - query expansion targets official issuer pages, SEC/EDGAR, reputable
    wires/news, specialist aggregators, and general web fallbacks according to
    the evidence key
  - candidate URLs are deduplicated, source-class filtered, and reranked before
    fetching
  - fetched source records preserve query text, source class, retrieval score,
    URL, publisher, confidence, and source level
  - the mandatory evidence context injected into agents now includes clickable
    source URLs and recent resolver trace summaries so analysts and debaters
    can see exactly where validated facts came from
- Split filing semantics:
  - `fundamentals.latest_financial_filing`
  - `fundamentals.latest_earnings_8k`
  - `ownership.latest_filing`
  - ownership forms can no longer satisfy the financial-filing requirement
- Promoted public-source facts into `EvidenceStore` before agents:
  - earnings release
  - transcript
  - actual vs consensus
  - guidance and CapEx
  - cash-flow and FCF inputs
  - cloud/SaaS metrics such as ARR/run-rate, RPO/backlog, seats/users
  - analyst consensus with multi-source requirement
  - short interest
  - options put/call
  - next earnings date
  - technical indicators from OHLCV
- Added a pre-agent earnings-event resolver:
  - resolves `earnings.latest_reported.date` and fiscal period before analyst
    generation
  - resolves `catalyst.next_earnings_date.value` only after classifying whether
    the latest quarter has already been reported
  - uses the full hybrid chain: API/provider attempt, issuer IR, SEC/regulatory,
    reputable news/wire, specialist aggregator, general web search, query
    expansion, extraction retry, and source-conflict reconciliation
  - quarantines stale near-term catalyst dates under
    `catalyst.stale_earnings_date_conflict` so agents cannot debate as if a
    past or invalidated earnings date is still upcoming
- Added upstream TradingAgents tool-output capture:
  - baseline dataflow calls write a per-run JSONL evidence artifact
  - Stage 5 promotes usable captured provider/tool facts before dynamic RAG
  - upstream `yfinance` fundamentals, stock data, cash-flow, income statement,
    news, insider, and indicator outputs can populate typed evidence keys
- Added priority-aware evidence replacement:
  - valid provider/issuer/regulatory/computed facts are retained over weaker
    later web artifacts
  - implausible numeric artifacts cannot overwrite usable evidence
  - source-list evidence is merged instead of replaced by the last source
- Added central report metadata hygiene:
  - `ReportDates`
  - `ReportMode`
  - issuer-display-name sanitation
  - scratchpad phrase removal
  - support/resistance/pivot classification by latest close
- Added user-input folder discovery:
  - Stage 0A resolves the latest eligible dated folder under `inputs\<TICKER>`
    on or before the analysis date.
  - If an older folder is supplied while a newer eligible folder exists, the
    newer folder is selected and the warning is written to the request packet.
  - This keeps user-supplied CSVs, reports, and supporting files from becoming
    stale because of copied command arguments.
- Updated Stage 5 institutional rendering:
  - default report mode remains institutional
  - diagnostic tables move to appendices
  - Final Trade Decision appears directly after the reader guidance section
  - legal notice and title use sanitized issuer display metadata, not technical
    indicator text
  - stale earnings-catalyst mentions that survive in upstream prose receive an
    inline evidence note and cannot become final decision logic
- Preserved continuous operational learning:
  - rejected claims remain persisted with role, dependency, correction rule,
    recurrence, severity, ticker, run ID, and timestamp
  - future runs inject relevant lessons into responsible agents

## Verification

- `python scripts\publication_safety_check.py` passed.
- `python -B -m compileall -q scripts titan_integration TradingAgents\tradingagents` passed.
- `cd TradingAgents; uv run pytest -q` passed with `168 passed, 42 subtests passed`.
- Targeted dynamic web-RAG planner coverage passed with `48 passed`.

## Latest MSFT Retest Result

The fresh MSFT Stage 5 export for `MSFT_20260504T134651Z` confirmed that
upstream capture, priority-aware evidence promotion, and rich-but-evidence-clean
rendering reduced Appendix A rejected claims to `0` while preserving inline
evidence notes for unresolved scenarios. The new earnings-event resolver closes
the stale catalyst path that allowed a near-term earnings date to appear after a
latest reported quarter had already been released.

## Notes

Live public pages may be unreachable, changed, or blocked in a given runtime.
Regression tests therefore use public-source-shaped fixtures while production
code remains ticker-generic and public-first. MSFT values are confined to test
fixtures and documentation of the validation scenario, not production logic.
