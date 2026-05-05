# Stage 1A User Evidence Ingestion

Date: 2026-05-02

## Purpose

Stage 1A ingests user-supplied evidence before Stage 1 validation merges the evidence set.

The intent is to let local files supplement external provider evidence without replacing or overriding provider data.

## Input Folder

Recommended NVDA drop folder:

```text
inputs\NVDA\2026-05-02\
```

Supported first-pass file type:

- TradingView-style `.csv` OHLCV exports

Expected files may include:

- Monthly
- Weekly
- Daily
- 4-hour
- 1-hour
- 15-minute
- 5-minute

One timeframe should be supplied per CSV file.

## Detection Logic

The loader detects:

- Timestamp/date column
- OHLCV columns
- File SHA-256 hash
- Ingestion status versus the local registry
- Row count
- First and last timestamp
- Timeframe from filename or timestamp spacing
- Context-appropriate selected window

Selected-window policy:

- Monthly: up to 5 years
- Weekly: up to 3 years
- Daily: about 430 days
- 4-hour: about 180 days
- 1-hour: about 90 days
- 15-minute: about 45 days
- 5-minute: about 15 days

Large CSVs are summarized rather than fully embedded into Stage 1.

## Integration Policy

External providers remain primary.

Per research cycle, Stage 1 performs external provider retrieval first, then scans the local input folder for user-supplied evidence. If no relevant files are present, the workflow proceeds using externally sourced data only.

User-supplied evidence:

- is marked `user_supplied`,
- is fingerprinted by file hash,
- is checked against the local ingestion registry before being marked new,
- is treated as supplemental,
- does not silently override yfinance, SEC, or other provider data,
- must preserve conflicts for Titan review.

Stage 1B reuses the Stage 1A scan result from the same run so duplicate-prevention is applied once per research cycle before technical features are extracted.

## Implemented Components

- `titan_integration\user_evidence.py`
- `scripts\build_stage1a_user_evidence_packet.py`
- Stage 1 integration through:
  - `titan_integration\validation_packet.py`
  - `scripts\build_stage1_validation_packet.py`

## Verification

Verification completed with a temporary `5m` TradingView-style sample CSV.

The loader correctly detected:

- timeframe: `5m`
- timestamp column: `time`
- row count: `3`
- selected row count: `3`
- first timestamp: `2026-05-01T09:30:00`
- last timestamp: `2026-05-01T09:40:00`
- file hash

The same sample was then ingested a second time to verify deduplication. The second pass marked the unchanged file as `Already Ingested`.

The temporary file was removed after verification.

The real NVDA input folder was then populated with seven TradingView CSV exports under:

```text
D:\Projects\CodeX\TradingAgents_Integration\inputs\NVDA\2026-05-02\
```

Detected timeframes:

- `15m`
- `1d`
- `1h`
- `1mo`
- `1w`
- `4h`
- `5m`

The current packet shows:

- file count: `7`
- new file count: `0`
- already ingested count: `7`
- latest user evidence timestamp: `2026-05-01T22:55:00`
- total rows observed: `20,771`
- total rows selected for context: `2,894`

The `0` new files result is expected on repeat runs: the first pass registered each file hash, and subsequent runs correctly mark unchanged files as `Already Ingested`.

Current packet:

```text
D:\Projects\CodeX\TradingAgents_Integration\research_packets\stage1a_user_evidence\NVDA_2026-05-02_stage1a_user_evidence_packet.md
```

## Downstream Refresh

After real-file ingestion, the downstream chain was rebuilt through Stage 4:

- Stage 1 included the user-supplied evidence audit.
- Stage 2 added `stage1_user_supplied_evidence` as a source.
- Stage 2B preserved supported/contradictory claim logic.
- Stage 2C preserved valuation computation blockers where explicit inputs were unavailable.
- Stage 3 rebuilt the evidence graph with the user evidence source included.
- Evidence Delta identified the user-supplied multi-timeframe evidence as `Newly Discovered`.
- Stage 4 remained `Conditional: Swing`, with full Titan compliance withheld.

## Dedupe Registry

Stage 1A writes a local-only registry:

```text
normalized_data\user_evidence_registry.json
```

The registry is ignored by Git. It stores file hashes, ticker, timeframe, timestamp range, row count, and first ingested timestamp.

If a CSV is unchanged, Stage 1A marks it as:

- `Already Ingested`

If a CSV changes, its SHA-256 hash changes and Stage 1A marks it as:

- `New`

This prevents repeated processing of identical historical monthly, weekly, daily, hourly, and minute datasets.

The registry updates `last_seen_at_utc` on repeat scans while preserving the original `ingested_at_utc`, which allows the system to prove the file was re-seen without reclassifying it as newly ingested.
