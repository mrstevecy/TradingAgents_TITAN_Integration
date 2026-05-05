# Stage 1B User Technical Feature Extraction

Date: 2026-05-02

## Purpose

Stage 1B converts user-supplied TradingView CSV files into derived technical evidence.

Stage 1A remains responsible for file discovery, timestamp coverage, hashing, and duplicate-ingestion protection. Stage 1B is responsible for extracting meaningful technical features from the selected context windows.

During a full Stage 1 research cycle, Stage 1B reuses the Stage 1A scan result already collected for that run. This prevents a second registry classification pass while still allowing the standalone Stage 1B script to scan inputs directly when run by itself.

## Implemented Components

- `titan_integration\user_technical_features.py`
- `scripts\build_stage1b_user_technical_features_packet.py`
- Stage 1 integration:
  - `titan_integration\validation_packet.py`
- Stage 2 source registration:
  - `titan_integration\citation_retrieval.py`
- Stage 3 graph nodes:
  - `titan_integration\evidence_graph.py`
- Stage 4 horizon usage:
  - `titan_integration\horizon_validation.py`

## Columns Used

Stage 1B currently recognizes and uses the following TradingView CSV columns:

| Column | Current Role |
|---|---|
| `time` | Timestamp parsing, selected window boundaries, latest technical timestamp. |
| `open`, `high`, `low`, `close` | Latest close and price context; close is used against VWAP, bands, ATR percent, and moving averages. |
| `Rolling VWAP` | VWAP positioning by timeframe. |
| `Upper band 1`, `Lower band 1`, `Upper band 2`, `Lower band 2`, `Upper band 3`, `Lower band 3` | Band-position classification. |
| `MA`, duplicate `MA` normalized as `MA_2` | Price position versus available moving averages. |
| `Volume` | Latest volume level. |
| `Volume MA` | Volume regime classification versus moving average. |
| `RSI` | Momentum regime classification. |
| `RSI-based MA` | Preserved as an available technical column for later enhancement. |
| `Regular Bullish`, `Regular Bullish Label` | Recent bullish divergence flag counts. |
| `Regular Bearish`, `Regular Bearish Label` | Recent bearish divergence flag counts. |
| `ATR` | Latest ATR and ATR percent of close. |
| `ADX` | Trend-strength regime classification. |

Duplicate CSV headers are handled explicitly. The second `MA` column is normalized to `MA_2` so it is not silently lost.

## Derived Features

For each timeframe, Stage 1B produces:

- latest timestamp
- latest close
- latest rolling VWAP
- VWAP position
- latest volume and volume MA
- volume regime
- latest RSI and RSI regime
- latest ATR and ATR as percent of close
- latest ADX and ADX regime
- moving-average position
- band position
- recent bullish/bearish divergence counts
- concise technical read

It also produces a multi-timeframe read summarizing:

- analyzed timeframes
- latest user technical timestamp
- above-VWAP timeframes
- below-VWAP timeframes
- strong-trend timeframes
- weak-momentum timeframes
- elevated-volume timeframes
- summary interpretation

## NVDA Verification Result

Input folder:

```text
D:\Projects\CodeX\TradingAgents_Integration\inputs\NVDA\2026-05-02\
```

Output packet:

```text
D:\Projects\CodeX\TradingAgents_Integration\research_packets\stage1b_user_technical_features\NVDA_2026-05-02_stage1b_user_technical_features_packet.md
```

Stage 1B extracted seven timeframe summaries:

- `1mo`
- `1w`
- `1d`
- `4h`
- `1h`
- `15m`
- `5m`

Multi-timeframe read:

- Above VWAP: `1mo`, `1w`, `1d`
- Below VWAP: `4h`, `1h`, `15m`, `5m`
- Strong trend: `1mo`, `1d`, `4h`, `1h`
- Weak momentum: `1h`, `15m`, `5m`
- Elevated volume: `1w`, `15m`, `5m`
- Summary: user technical evidence leans defensive because more timeframes are below VWAP and weak-momentum flags are present.

## Downstream Integration

Stage 1 now includes:

- `user_technical_feature_audit`
- generated claims for:
  - user-derived multi-timeframe technical features
  - user-derived VWAP positioning
  - user-derived momentum and trend-strength features

Stage 2 now registers:

```text
stage1b_user_technical_features
```

as a `user_derived` source.

Stage 3 now creates:

- seven `user_technical_feature` nodes
- one `user_technical_mtf_read` node

Stage 4 now uses these nodes in Intraday and Swing horizon reasoning while preserving the Titan rule that live intraday validation still requires tape, session liquidity, spread/depth, and opening-range evidence.

## Latest Graph Result

After the Stage 1B integration, the refreshed NVDA graph contains:

- Nodes: `87`
- Edges: `151`
- User technical feature nodes: `7`
- User technical multi-timeframe read nodes: `1`
- Sources: `22`
- Claims: `12`

## Governance Notes

- User-derived indicators are supplemental and do not silently override yfinance, SEC, or other provider data.
- Conflicts must be preserved for Titan review.
- Historical intraday CSVs can improve conditional intraday setup assessment, but cannot validate live intraday execution.
- The system still requires fresh catalyst, earnings-timing, valuation, and live-market evidence before final Titan-compliant reporting.
