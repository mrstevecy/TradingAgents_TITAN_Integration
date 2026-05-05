# User-Supplied Evidence Drop Zone

Place local evidence files here. This directory is ignored by Git except for this README.

Recommended folder pattern:

```text
inputs/
  <TICKER>/
    <YYYY-MM-DD>/
      <TICKER>_monthly.csv
      <TICKER>_weekly.csv
      <TICKER>_daily.csv
      <TICKER>_4h.csv
      <TICKER>_1h.csv
      <TICKER>_15m.csv
      <TICKER>_5m.csv
```

Example equity research drop zone:

```text
inputs/
  <TICKER>/
    <YYYY-MM-DD>/
```

Accepted first-pass file type:

- `.csv` TradingView-style OHLCV exports, one timeframe per file.

The loader will detect timestamp, OHLCV columns, row counts, first/last timestamps, timeframe, and a context-appropriate selected window.

User-supplied evidence supplements external provider data. It does not silently override provider evidence.
