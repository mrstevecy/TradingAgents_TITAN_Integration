"""Stage 1A user-supplied evidence ingestion.

The loader scans local input folders for user-provided files such as
TradingView CSV exports. It summarizes and fingerprints them without treating
them as a replacement for external provider data.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from statistics import median
from typing import Any

from .research_cycle import utc_now_iso


@dataclass(frozen=True)
class UserEvidenceFile:
    file_path: str
    file_name: str
    file_sha256: str
    evidence_type: str
    detected_timeframe: str
    ingestion_status: str
    prior_ingested_at_utc: str | None
    timestamp_column: str | None
    first_timestamp: str | None
    last_timestamp: str | None
    row_count: int
    selected_row_count: int
    selected_start_timestamp: str | None
    selected_end_timestamp: str | None
    columns: list[str]
    ohlcv_columns: dict[str, str]
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class UserEvidencePacket:
    ticker: str
    trade_date: str
    generated_at_utc: str
    input_directories_checked: list[str]
    registry_path: str
    files: list[UserEvidenceFile]
    status: str
    summary: dict[str, Any]
    integration_policy: dict[str, Any]


def build_user_evidence_packet(
    *,
    ticker: str,
    trade_date: str,
    input_root: Path,
    registry_path: Path | None = None,
) -> UserEvidencePacket:
    dirs = _candidate_dirs(input_root, ticker, trade_date)
    registry_path = registry_path or Path.cwd() / "normalized_data" / "user_evidence_registry.json"
    registry = _read_registry(registry_path)
    files: list[UserEvidenceFile] = []
    for directory in dirs:
        if not directory.exists() or not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.csv")):
            files.append(_inspect_csv(path, trade_date, registry))

    _update_registry(registry_path, registry, ticker, files)

    latest = max((item.last_timestamp for item in files if item.last_timestamp), default=None)
    timeframes = sorted({item.detected_timeframe for item in files})
    return UserEvidencePacket(
        ticker=ticker,
        trade_date=trade_date,
        generated_at_utc=utc_now_iso(),
        input_directories_checked=[str(path) for path in dirs],
        registry_path=str(registry_path),
        files=files,
        status="Available" if files else "No User Evidence Found",
        summary={
            "file_count": len(files),
            "new_file_count": sum(1 for item in files if item.ingestion_status == "New"),
            "already_ingested_count": sum(1 for item in files if item.ingestion_status == "Already Ingested"),
            "timeframes_detected": timeframes,
            "latest_user_evidence_timestamp": latest,
            "total_rows_observed": sum(item.row_count for item in files),
            "total_rows_selected": sum(item.selected_row_count for item in files),
        },
        integration_policy={
            "stage": "Stage 1A - User-Supplied Evidence",
            "policy": "Supplement external provider evidence; do not override provider data silently.",
            "dedupe_policy": "Do not re-ingest identical file hashes already present in the local ingestion registry.",
            "conflict_handling": "Preserve both user-supplied and provider evidence and flag conflicts for Titan review.",
            "graph_policy": "Represent user evidence as user_supplied source nodes with file hashes and selected windows.",
        },
    )


def write_user_evidence_packet(packet: UserEvidencePacket, out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{packet.ticker}_{packet.trade_date}_stage1a_user_evidence_packet"
    json_path = out_dir / f"{stem}.json"
    md_path = out_dir / f"{stem}.md"
    payload = asdict(packet)
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(_to_markdown(payload), encoding="utf-8")
    return json_path, md_path


def _candidate_dirs(input_root: Path, ticker: str, trade_date: str) -> list[Path]:
    return [
        input_root / ticker.upper() / trade_date,
        input_root / f"{ticker.upper()}_{trade_date}",
        input_root / ticker.upper(),
        input_root,
    ]


def _inspect_csv(path: Path, trade_date: str, registry: dict[str, Any]) -> UserEvidenceFile:
    file_hash = _sha256(path)
    warnings: list[str] = []
    columns: list[str] = []
    timestamps: list[datetime] = []
    row_count = 0
    timestamp_col: str | None = None
    ohlcv: dict[str, str] = {}

    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            columns = list(reader.fieldnames or [])
            timestamp_col = _timestamp_column(columns)
            ohlcv = _ohlcv_columns(columns)
            if not timestamp_col:
                warnings.append("No timestamp/date column detected.")
            for row in reader:
                row_count += 1
                if timestamp_col:
                    parsed = _parse_timestamp(row.get(timestamp_col, ""))
                    if parsed:
                        timestamps.append(parsed)
    except UnicodeDecodeError:
        with path.open("r", encoding="cp1252", newline="") as handle:
            reader = csv.DictReader(handle)
            columns = list(reader.fieldnames or [])
            timestamp_col = _timestamp_column(columns)
            ohlcv = _ohlcv_columns(columns)
            for row in reader:
                row_count += 1
                if timestamp_col:
                    parsed = _parse_timestamp(row.get(timestamp_col, ""))
                    if parsed:
                        timestamps.append(parsed)
        warnings.append("File decoded with cp1252 fallback.")

    timestamps.sort()
    detected = _detect_timeframe(path.name, timestamps)
    selected = _select_context_window(timestamps, detected, trade_date)
    prior = _registry_match(registry, file_hash)
    ingestion_status = "Already Ingested" if prior else "New"
    if row_count and not timestamps:
        warnings.append("Rows exist, but no parseable timestamps were found.")
    missing = [name for name in ("open", "high", "low", "close") if name not in ohlcv]
    if missing:
        warnings.append("Missing OHLC columns: " + ", ".join(missing))

    return UserEvidenceFile(
        file_path=str(path),
        file_name=path.name,
        file_sha256=file_hash,
        evidence_type="tradingview_csv",
        detected_timeframe=detected,
        ingestion_status=ingestion_status,
        prior_ingested_at_utc=prior.get("ingested_at_utc") if prior else None,
        timestamp_column=timestamp_col,
        first_timestamp=_iso(timestamps[0]) if timestamps else None,
        last_timestamp=_iso(timestamps[-1]) if timestamps else None,
        row_count=row_count,
        selected_row_count=len(selected),
        selected_start_timestamp=_iso(selected[0]) if selected else None,
        selected_end_timestamp=_iso(selected[-1]) if selected else None,
        columns=columns,
        ohlcv_columns=ohlcv,
        warnings=warnings,
    )


def _timestamp_column(columns: list[str]) -> str | None:
    candidates = {"time", "datetime", "date", "timestamp", "time utc", "date/time"}
    for column in columns:
        if column.strip().lower() in candidates:
            return column
    for column in columns:
        lowered = column.strip().lower()
        if "time" in lowered or "date" in lowered:
            return column
    return None


def _ohlcv_columns(columns: list[str]) -> dict[str, str]:
    aliases = {
        "open": {"open", "o"},
        "high": {"high", "h"},
        "low": {"low", "l"},
        "close": {"close", "c"},
        "volume": {"volume", "vol"},
    }
    found: dict[str, str] = {}
    for normalized, names in aliases.items():
        for column in columns:
            if column.strip().lower() in names:
                found[normalized] = column
                break
    return found


def _read_registry(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"version": 1, "files": []}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"version": 1, "files": [], "warnings": ["Registry JSON was unreadable and was reset."]}


def _update_registry(path: Path, registry: dict[str, Any], ticker: str, files: list[UserEvidenceFile]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing_hashes = {item.get("file_sha256") for item in registry.get("files", [])}
    now = utc_now_iso()
    for item in files:
        if item.file_sha256 in existing_hashes:
            for existing in registry.get("files", []):
                if existing.get("file_sha256") == item.file_sha256:
                    existing.update(
                        {
                            "ticker": ticker.upper(),
                            "file_name": item.file_name,
                            "detected_timeframe": item.detected_timeframe,
                            "first_timestamp": item.first_timestamp,
                            "last_timestamp": item.last_timestamp,
                            "row_count": item.row_count,
                            "last_seen_at_utc": now,
                        }
                    )
                    break
            continue
        registry.setdefault("files", []).append(
            {
                "ticker": ticker.upper(),
                "file_sha256": item.file_sha256,
                "file_name": item.file_name,
                "detected_timeframe": item.detected_timeframe,
                "first_timestamp": item.first_timestamp,
                "last_timestamp": item.last_timestamp,
                "row_count": item.row_count,
                "ingested_at_utc": now,
            }
        )
        existing_hashes.add(item.file_sha256)
    path.write_text(json.dumps(registry, indent=2, ensure_ascii=False), encoding="utf-8")


def _registry_match(registry: dict[str, Any], file_hash: str) -> dict[str, Any] | None:
    for item in registry.get("files", []):
        if item.get("file_sha256") == file_hash:
            return item
    return None


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


def _detect_timeframe(file_name: str, timestamps: list[datetime]) -> str:
    by_name = _timeframe_from_name(file_name)
    if by_name != "unknown":
        return by_name
    if len(timestamps) < 2:
        return "unknown"
    deltas = [
        (timestamps[index] - timestamps[index - 1]).total_seconds()
        for index in range(1, len(timestamps))
        if timestamps[index] > timestamps[index - 1]
    ]
    if not deltas:
        return "unknown"
    seconds = median(deltas)
    if seconds <= 6 * 60:
        return "5m"
    if seconds <= 20 * 60:
        return "15m"
    if seconds <= 75 * 60:
        return "1h"
    if seconds <= 5 * 60 * 60:
        return "4h"
    if seconds <= 2 * 24 * 60 * 60:
        return "1d"
    if seconds <= 10 * 24 * 60 * 60:
        return "1w"
    return "1mo"


def _timeframe_from_name(file_name: str) -> str:
    name = file_name.lower()
    patterns = [
        ("1mo", r"(monthly|month|1mo|1mth)"),
        ("1w", r"(weekly|week|1w)"),
        ("1d", r"(daily|day|1d)"),
        ("4h", r"(^|[^0-9])(4h|240m|240|4hour)([^0-9]|$)"),
        ("1h", r"(^|[^0-9])(1h|60m|60|1hour)([^0-9]|$)"),
        ("15m", r"(15m|15min)"),
        ("5m", r"(5m|5min)"),
    ]
    for timeframe, pattern in patterns:
        if re.search(pattern, name):
            return timeframe
    return "unknown"


def _select_context_window(timestamps: list[datetime], timeframe: str, trade_date: str) -> list[datetime]:
    if not timestamps:
        return []
    end = _parse_timestamp(trade_date) or timestamps[-1]
    if timestamps[-1] < end:
        end = timestamps[-1]
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
    selected = [item for item in timestamps if start <= item <= end]
    return selected[-5000:]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _iso(value: datetime) -> str:
    return value.isoformat()


def _to_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# Stage 1A User Evidence Packet: {payload['ticker']} {payload['trade_date']}",
        "",
        f"Generated UTC: {payload['generated_at_utc']}",
        f"Status: {payload['status']}",
        "",
        "## Summary",
        "",
        "```json",
        json.dumps(payload["summary"], indent=2, ensure_ascii=False),
        "```",
        "",
        "## Files",
        "",
        "| Timeframe | Status | Rows | Selected | First | Last | File | Warnings |",
        "|---|---|---:|---:|---|---|---|---|",
    ]
    for item in payload["files"]:
        lines.append(
            f"| {item['detected_timeframe']} | {item['ingestion_status']} | {item['row_count']} | {item['selected_row_count']} | "
            f"{item['first_timestamp']} | {item['last_timestamp']} | {item['file_name']} | "
            f"{'; '.join(item['warnings']) or 'None'} |"
        )
    lines.extend(["", "## Integration Policy", "", "```json", json.dumps(payload["integration_policy"], indent=2, ensure_ascii=False), "```"])
    return "\n".join(lines) + "\n"
