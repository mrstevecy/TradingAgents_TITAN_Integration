# Universal Research Request Schema

Date: 2026-05-02

## Purpose

The universal request schema is the single entry shape for future multi-asset
research. Stage 0A resolves this request into an implemented or planned
research profile.

## Required Fields

| Field | Purpose |
|---|---|
| `asset` | Human-readable asset name or asset label. |
| `ticker` | Symbol or instrument code used by the workflow. |
| `full_name` | Full issuer, instrument, or asset name. |
| `instrument_type` | Instrument type such as `Equity`, `ETF`, `Crypto`, or `Equity-Option`. |
| `asset_class` | Broader class such as `Equity`, `ETF`, `Index`, `Commodity`, `Futures`, `FX`, or `Crypto`. |
| `primary_strategy` | Research intent such as `Long`, `Short`, `Hedge`, `Spread`, or `Event`. |
| `trading_horizon` | Requested horizon such as `Intraday`, `Swing`, `Positional`, or `Long-Term`. |
| `execution_platform` | Intended platform context, for example `TradingView`, `IBKR`, `NinjaTrader`, or `eToro`. |
| `analysis_date` | Requested research date. |
| `input_folder` | Local folder for user-supplied evidence for this asset and date. |

## NVDA Equity Example

```json
{
  "asset": "NVIDIA Corporation",
  "ticker": "NVDA",
  "full_name": "NVIDIA Corporation",
  "instrument_type": "Equity",
  "asset_class": "Equity",
  "primary_strategy": "Long/Short/Hold",
  "trading_horizon": "Intraday/Swing/Positional/Long-Term",
  "execution_platform": "TradingView",
  "analysis_date": "2026-05-02",
  "input_folder": "D:\\Projects\\CodeX\\TradingAgents_Integration\\inputs\\NVDA\\2026-05-02"
}
```

## Unsupported Profile Rule

If the requested `instrument_type` is registered but not implemented, Stage 0A
must stop gracefully. It must not route the asset through the equity pipeline or
produce simulated Titan validation.
