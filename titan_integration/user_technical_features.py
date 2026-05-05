"""Stage 1B technical feature extraction from user-supplied CSV evidence.

Stage 1A proves that user files exist, fingerprints them, and summarizes their
coverage. Stage 1B reads the selected portions of those files and extracts
technical feature evidence without allowing local files to silently override
external provider data.
"""

from __future__ import annotations

import csv
import json
import math
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from statistics import median
from typing import Any

from .research_cycle import utc_now_iso
from .user_evidence import UserEvidencePacket, build_user_evidence_packet


@dataclass(frozen=True)
class TechnicalFeatureSummary:
    file_name: str
    detected_timeframe: str
    selected_row_count: int
    selected_start_timestamp: str | None
    selected_end_timestamp: str | None
    latest_timestamp: str | None
    latest_close: float | None
    latest_rolling_vwap: float | None
    vwap_position: str
    latest_volume: float | None
    latest_volume_ma: float | None
    volume_regime: str
    latest_rsi: float | None
    rsi_regime: str
    latest_atr: float | None
    atr_pct_of_close: float | None
    latest_adx: float | None
    adx_regime: str
    ma_position: str
    band_position: str
    recent_bullish_divergence_count: int
    recent_bearish_divergence_count: int
    technical_read: str
    columns_used: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class UserTechnicalFeaturePacket:
    ticker: str
    trade_date: str
    generated_at_utc: str
    stage: str
    status: str
    source_stage1a_packet: dict[str, Any]
    feature_summaries: list[TechnicalFeatureSummary]
    multi_timeframe_read: dict[str, Any]
    generated_claims: list[dict[str, Any]]
    integration_policy: dict[str, Any]


def build_user_technical_feature_packet(
    *,
    ticker: str,
    trade_date: str,
    input_root: Path,
    registry_path: Path | None = None,
    stage1a_packet: UserEvidencePacket | None = None,
) -> UserTechnicalFeaturePacket:
    stage1a = stage1a_packet or build_user_evidence_packet(
        ticker=ticker,
        trade_date=trade_date,
        input_root=input_root,
        registry_path=registry_path,
    )
    summaries = [_extract_features(Path(item.file_path), item.detected_timeframe, trade_date) for item in stage1a.files]
    summaries = [item for item in summaries if item.selected_row_count > 0]
    mtf = _multi_timeframe_read(summaries)
    claims = _claims_from_features(summaries, mtf)
    return UserTechnicalFeaturePacket(
        ticker=ticker.upper(),
        trade_date=trade_date,
        generated_at_utc=utc_now_iso(),
        stage="Stage 1B - User Technical Feature Extraction",
        status="Available" if summaries else "No Technical Features Extracted",
        source_stage1a_packet={
            "status": stage1a.status,
            "summary": stage1a.summary,
            "registry_path": stage1a.registry_path,
        },
        feature_summaries=summaries,
        multi_timeframe_read=mtf,
        generated_claims=claims,
        integration_policy={
            "policy": "Derived technical evidence from user CSV files supplements external provider evidence.",
            "override_policy": "User-derived indicators do not override provider data without explicit conflict review.",
            "horizon_policy": (
                "Intraday evidence from historical intraday CSVs can support conditional setup assessment, "
                "but cannot validate live intraday execution without tape, spread/depth, and opening-range evidence."
            ),
            "graph_policy": "Represent Stage 1B as derived user technical feature nodes linked to the local user source.",
        },
    )


def write_user_technical_feature_packet(
    packet: UserTechnicalFeaturePacket, out_dir: Path
) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{packet.ticker}_{packet.trade_date}_stage1b_user_technical_features_packet"
    json_path = out_dir / f"{stem}.json"
    md_path = out_dir / f"{stem}.md"
    payload = asdict(packet)
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(_to_markdown(payload), encoding="utf-8")
    return json_path, md_path


def _extract_features(path: Path, timeframe: str, trade_date: str) -> TechnicalFeatureSummary:
    rows, columns, warnings = _read_rows(path)
    rows = [row for row in rows if row.get("time_parsed")]
    rows.sort(key=lambda row: row["time_parsed"])
    selected = _select_rows(rows, timeframe, trade_date)
    latest = selected[-1] if selected else {}
    recent = selected[-50:] if selected else []

    latest_close = _num(latest.get("close"))
    latest_vwap = _num(latest.get("Rolling VWAP"))
    latest_volume = _num(latest.get("Volume"))
    latest_volume_ma = _num(latest.get("Volume MA"))
    latest_rsi = _num(latest.get("RSI"))
    latest_atr = _num(latest.get("ATR"))
    latest_adx = _num(latest.get("ADX"))
    atr_pct = (latest_atr / latest_close * 100) if latest_atr is not None and latest_close else None
    ma_values = [_num(latest.get(name)) for name in ("MA", "MA_2") if _num(latest.get(name)) is not None]
    band_values = {
        name: _num(latest.get(name))
        for name in ("Upper band 1", "Lower band 1", "Upper band 2", "Lower band 2", "Upper band 3", "Lower band 3")
    }
    columns_used = [
        name
        for name in (
            "time",
            "open",
            "high",
            "low",
            "close",
            "Rolling VWAP",
            "Upper band 1",
            "Lower band 1",
            "Upper band 2",
            "Lower band 2",
            "Upper band 3",
            "Lower band 3",
            "MA",
            "MA_2",
            "Volume",
            "Volume MA",
            "RSI",
            "RSI-based MA",
            "Regular Bullish",
            "Regular Bullish Label",
            "Regular Bearish",
            "Regular Bearish Label",
            "ATR",
            "ADX",
        )
        if name in columns
    ]

    vwap_position = _price_position(latest_close, latest_vwap, "VWAP")
    volume_regime = _volume_regime(latest_volume, latest_volume_ma)
    rsi_regime = _rsi_regime(latest_rsi)
    adx_regime = _adx_regime(latest_adx)
    ma_position = _ma_position(latest_close, ma_values)
    band_position = _band_position(latest_close, band_values)
    bullish_count = sum(1 for row in recent if _flag(row.get("Regular Bullish")) or _flag(row.get("Regular Bullish Label")))
    bearish_count = sum(1 for row in recent if _flag(row.get("Regular Bearish")) or _flag(row.get("Regular Bearish Label")))

    return TechnicalFeatureSummary(
        file_name=path.name,
        detected_timeframe=timeframe,
        selected_row_count=len(selected),
        selected_start_timestamp=_iso(selected[0]["time_parsed"]) if selected else None,
        selected_end_timestamp=_iso(selected[-1]["time_parsed"]) if selected else None,
        latest_timestamp=_iso(latest["time_parsed"]) if latest else None,
        latest_close=latest_close,
        latest_rolling_vwap=latest_vwap,
        vwap_position=vwap_position,
        latest_volume=latest_volume,
        latest_volume_ma=latest_volume_ma,
        volume_regime=volume_regime,
        latest_rsi=latest_rsi,
        rsi_regime=rsi_regime,
        latest_atr=latest_atr,
        atr_pct_of_close=atr_pct,
        latest_adx=latest_adx,
        adx_regime=adx_regime,
        ma_position=ma_position,
        band_position=band_position,
        recent_bullish_divergence_count=bullish_count,
        recent_bearish_divergence_count=bearish_count,
        technical_read=_technical_read(
            timeframe=timeframe,
            vwap_position=vwap_position,
            volume_regime=volume_regime,
            rsi_regime=rsi_regime,
            adx_regime=adx_regime,
            ma_position=ma_position,
            bullish_count=bullish_count,
            bearish_count=bearish_count,
        ),
        columns_used=columns_used,
        warnings=warnings,
    )


def _read_rows(path: Path) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    warnings: list[str] = []
    try:
        raw = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        raw = path.read_text(encoding="cp1252")
        warnings.append("File decoded with cp1252 fallback.")
    lines = raw.splitlines()
    if not lines:
        return [], [], ["File is empty."]
    reader = csv.reader(lines)
    raw_header = next(reader)
    header = _dedupe_header(raw_header)
    rows: list[dict[str, Any]] = []
    for values in reader:
        row = {header[index]: values[index] if index < len(values) else "" for index in range(len(header))}
        row["time_parsed"] = _parse_timestamp(row.get("time", ""))
        rows.append(row)
    return rows, header, warnings


def _dedupe_header(header: list[str]) -> list[str]:
    seen: dict[str, int] = {}
    result: list[str] = []
    for raw in header:
        name = raw.strip()
        count = seen.get(name, 0) + 1
        seen[name] = count
        result.append(name if count == 1 else f"{name}_{count}")
    return result


def _select_rows(rows: list[dict[str, Any]], timeframe: str, trade_date: str) -> list[dict[str, Any]]:
    if not rows:
        return []
    end = _parse_timestamp(trade_date) or rows[-1]["time_parsed"]
    if rows[-1]["time_parsed"] < end:
        end = rows[-1]["time_parsed"]
    lookbacks = {
        "1mo": timedelta(days=365 * 5),
        "1w": timedelta(days=365 * 3),
        "1d": timedelta(days=430),
        "4h": timedelta(days=180),
        "1h": timedelta(days=90),
        "15m": timedelta(days=45),
        "5m": timedelta(days=15),
    }
    start = end - lookbacks.get(timeframe, timedelta(days=365))
    selected = [row for row in rows if start <= row["time_parsed"] <= end]
    return selected[-5000:]


def _multi_timeframe_read(summaries: list[TechnicalFeatureSummary]) -> dict[str, Any]:
    order = {"1mo": 1, "1w": 2, "1d": 3, "4h": 4, "1h": 5, "15m": 6, "5m": 7}
    summaries = sorted(summaries, key=lambda item: order.get(item.detected_timeframe, 99))
    below_vwap = [item.detected_timeframe for item in summaries if item.vwap_position == "Below VWAP"]
    above_vwap = [item.detected_timeframe for item in summaries if item.vwap_position == "Above VWAP"]
    strong_trend = [item.detected_timeframe for item in summaries if item.adx_regime in {"Strong Trend", "Very Strong Trend"}]
    weak_momentum = [item.detected_timeframe for item in summaries if item.rsi_regime in {"Bearish", "Oversold"}]
    elevated_volume = [item.detected_timeframe for item in summaries if item.volume_regime == "Above Volume MA"]
    latest = max((item.latest_timestamp for item in summaries if item.latest_timestamp), default=None)
    return {
        "timeframes_analyzed": [item.detected_timeframe for item in summaries],
        "latest_user_technical_timestamp": latest,
        "above_vwap_timeframes": above_vwap,
        "below_vwap_timeframes": below_vwap,
        "strong_trend_timeframes": strong_trend,
        "weak_momentum_timeframes": weak_momentum,
        "elevated_volume_timeframes": elevated_volume,
        "summary_read": _mtf_summary_read(above_vwap, below_vwap, strong_trend, weak_momentum, elevated_volume),
    }


def _claims_from_features(
    summaries: list[TechnicalFeatureSummary], mtf: dict[str, Any]
) -> list[dict[str, Any]]:
    if not summaries:
        return []
    claims: list[dict[str, Any]] = [
        {
            "claim": "User-derived multi-timeframe technical features are available for Titan review.",
            "status": "Supported",
            "evidence": (
                f"Analyzed {len(summaries)} timeframe(s): "
                f"{', '.join(mtf.get('timeframes_analyzed', []))}; "
                f"latest technical timestamp={mtf.get('latest_user_technical_timestamp')}"
            ),
            "source_refs": ["user_technical_features"],
            "reason": "Stage 1B extracted VWAP, volume, RSI, ATR, ADX, MA, band, and divergence feature summaries.",
        },
        {
            "claim": "User-derived technical context shows multi-timeframe VWAP positioning.",
            "status": "Supported" if mtf.get("above_vwap_timeframes") or mtf.get("below_vwap_timeframes") else "Conditional",
            "evidence": (
                f"Above VWAP: {', '.join(mtf.get('above_vwap_timeframes', [])) or 'None'}; "
                f"Below VWAP: {', '.join(mtf.get('below_vwap_timeframes', [])) or 'None'}"
            ),
            "source_refs": ["user_technical_features"],
            "reason": "VWAP positioning is extracted from user-supplied TradingView columns and used as supplemental technical context.",
        },
        {
            "claim": "User-derived momentum and trend-strength features are available by timeframe.",
            "status": "Supported",
            "evidence": (
                f"Strong trend timeframes: {', '.join(mtf.get('strong_trend_timeframes', [])) or 'None'}; "
                f"Weak momentum timeframes: {', '.join(mtf.get('weak_momentum_timeframes', [])) or 'None'}"
            ),
            "source_refs": ["user_technical_features"],
            "reason": "RSI and ADX features are extracted by timeframe for later Titan horizon classification.",
        },
    ]
    return claims


def _technical_read(
    *,
    timeframe: str,
    vwap_position: str,
    volume_regime: str,
    rsi_regime: str,
    adx_regime: str,
    ma_position: str,
    bullish_count: int,
    bearish_count: int,
) -> str:
    parts = [
        f"{timeframe}: {vwap_position}",
        volume_regime,
        f"RSI {rsi_regime}",
        f"ADX {adx_regime}",
        ma_position,
    ]
    if bullish_count or bearish_count:
        parts.append(f"recent divergence flags bull={bullish_count}, bear={bearish_count}")
    return "; ".join(parts)


def _mtf_summary_read(
    above_vwap: list[str],
    below_vwap: list[str],
    strong_trend: list[str],
    weak_momentum: list[str],
    elevated_volume: list[str],
) -> str:
    if len(below_vwap) > len(above_vwap) and weak_momentum:
        base = "User technical evidence leans defensive: more timeframes are below VWAP and weak-momentum flags are present."
    elif len(above_vwap) > len(below_vwap) and strong_trend:
        base = "User technical evidence leans constructive: more timeframes are above VWAP with trend-strength support."
    else:
        base = "User technical evidence is mixed and requires Titan conflict handling."
    if elevated_volume:
        base += f" Elevated volume is present on: {', '.join(elevated_volume)}."
    return base


def _price_position(price: float | None, reference: float | None, label: str) -> str:
    if price is None or reference is None:
        return f"{label} Not Available"
    if math.isclose(price, reference, rel_tol=0.0005, abs_tol=0.01):
        return f"At {label}"
    return f"Above {label}" if price > reference else f"Below {label}"


def _volume_regime(volume: float | None, volume_ma: float | None) -> str:
    if volume is None or volume_ma is None or volume_ma == 0:
        return "Volume MA Not Available"
    if volume >= volume_ma * 1.2:
        return "Above Volume MA"
    if volume <= volume_ma * 0.8:
        return "Below Volume MA"
    return "Near Volume MA"


def _rsi_regime(value: float | None) -> str:
    if value is None:
        return "RSI Not Available"
    if value >= 70:
        return "Overbought"
    if value >= 55:
        return "Bullish"
    if value >= 45:
        return "Neutral"
    if value >= 30:
        return "Bearish"
    return "Oversold"


def _adx_regime(value: float | None) -> str:
    if value is None:
        return "ADX Not Available"
    if value >= 40:
        return "Very Strong Trend"
    if value >= 25:
        return "Strong Trend"
    if value >= 20:
        return "Developing Trend"
    return "Weak/Range"


def _ma_position(price: float | None, ma_values: list[float]) -> str:
    if price is None or not ma_values:
        return "MA Not Available"
    above = sum(1 for value in ma_values if price > value)
    if above == len(ma_values):
        return "Above Available MAs"
    if above == 0:
        return "Below Available MAs"
    return "Mixed vs Available MAs"


def _band_position(price: float | None, bands: dict[str, float | None]) -> str:
    if price is None:
        return "Band Position Not Available"
    upper1 = bands.get("Upper band 1")
    lower1 = bands.get("Lower band 1")
    upper2 = bands.get("Upper band 2")
    lower2 = bands.get("Lower band 2")
    if upper2 is not None and price > upper2:
        return "Above Upper Band 2"
    if upper1 is not None and price > upper1:
        return "Above Upper Band 1"
    if lower2 is not None and price < lower2:
        return "Below Lower Band 2"
    if lower1 is not None and price < lower1:
        return "Below Lower Band 1"
    if upper1 is not None and lower1 is not None:
        return "Inside Band 1"
    return "Band Position Not Available"


def _flag(value: Any) -> bool:
    text = str(value or "").strip().lower()
    return bool(text) and text not in {"false", "0", "na", "nan", "none", "null"}


def _num(value: Any) -> float | None:
    text = str(value or "").strip().replace(",", "")
    if not text:
        return None
    try:
        result = float(text)
    except ValueError:
        return None
    if math.isnan(result) or math.isinf(result):
        return None
    return result


def _parse_timestamp(value: str) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    raw = raw.replace(" UTC", "+00:00")
    try:
        return _naive(datetime.fromisoformat(raw))
    except ValueError:
        pass
    for pattern in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        "%m/%d/%Y %H:%M:%S",
        "%m/%d/%Y %H:%M",
        "%m/%d/%Y",
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y %H:%M",
        "%d/%m/%Y",
    ):
        try:
            return _naive(datetime.strptime(raw, pattern))
        except ValueError:
            continue
    return None


def _naive(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.replace(tzinfo=None)


def _iso(value: datetime) -> str:
    return value.isoformat()


def _to_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# Stage 1B User Technical Features: {payload['ticker']} {payload['trade_date']}",
        "",
        f"Generated UTC: {payload['generated_at_utc']}",
        f"Status: {payload['status']}",
        "",
        "## Multi-Timeframe Read",
        "",
        "```json",
        json.dumps(payload["multi_timeframe_read"], indent=2, ensure_ascii=False),
        "```",
        "",
        "## Feature Summaries",
        "",
        "| Timeframe | Latest | Close | VWAP Position | Volume | RSI | ADX | ATR % | MA Position | Divergence Flags |",
        "|---|---|---:|---|---|---|---|---:|---|---|",
    ]
    for item in payload["feature_summaries"]:
        lines.append(
            f"| {item['detected_timeframe']} | {item['latest_timestamp']} | {_fmt(item['latest_close'])} | "
            f"{item['vwap_position']} | {item['volume_regime']} | {item['rsi_regime']} ({_fmt(item['latest_rsi'])}) | "
            f"{item['adx_regime']} ({_fmt(item['latest_adx'])}) | {_fmt(item['atr_pct_of_close'])} | "
            f"{item['ma_position']} | bull={item['recent_bullish_divergence_count']}, bear={item['recent_bearish_divergence_count']} |"
        )
    lines.extend(["", "## Generated Claims", ""])
    for claim in payload["generated_claims"]:
        lines.extend(
            [
                f"### {claim['status']}: {claim['claim']}",
                "",
                f"Evidence: {claim['evidence']}",
                "",
                f"Reason: {claim['reason']}",
                "",
            ]
        )
    lines.extend(["## Integration Policy", "", "```json", json.dumps(payload["integration_policy"], indent=2, ensure_ascii=False), "```"])
    return "\n".join(lines) + "\n"


def _fmt(value: Any) -> str:
    if value is None:
        return "None"
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)
