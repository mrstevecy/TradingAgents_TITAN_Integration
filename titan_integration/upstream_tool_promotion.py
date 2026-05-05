"""Promote TradingAgents upstream tool outputs into TITAN evidence."""

from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import Any

from .equity_evidence import EvidenceItem, EvidenceStatus, EvidenceStore, SourceLevel, utc_now_iso


@dataclass(frozen=True)
class UpstreamToolRecord:
    captured_at_utc: str
    method: str
    vendor: str
    args: list[Any]
    kwargs: dict[str, Any]
    result: str


def load_upstream_tool_records(path: str | Path | None) -> list[UpstreamToolRecord]:
    if not path:
        return []
    source = Path(path)
    if not source.exists():
        return []
    records: list[UpstreamToolRecord] = []
    for line in source.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        records.append(
            UpstreamToolRecord(
                captured_at_utc=str(item.get("captured_at_utc") or utc_now_iso()),
                method=str(item.get("method") or ""),
                vendor=str(item.get("vendor") or ""),
                args=list(item.get("args") or []),
                kwargs=dict(item.get("kwargs") or {}),
                result=str(item.get("result") or ""),
            )
        )
    return records


def promote_upstream_tool_records(store: EvidenceStore, records: list[UpstreamToolRecord]) -> None:
    for record in records:
        if record.method == "get_fundamentals":
            _promote_fundamentals(store, record)
        elif record.method == "get_cashflow":
            _promote_cashflow(store, record)
        elif record.method == "get_income_statement":
            _promote_income_statement(store, record)
        elif record.method == "get_stock_data":
            _promote_stock_data(store, record)
        elif record.method == "get_indicators":
            _promote_indicator(store, record)
        elif record.method in {"get_news", "get_global_news", "get_insider_transactions"}:
            _promote_news_or_insider(store, record)
    _compute_from_promoted(store)


def _add(
    store: EvidenceStore,
    key: str,
    value: Any,
    record: UpstreamToolRecord,
    *,
    status: EvidenceStatus = EvidenceStatus.RETRIEVED,
    level: SourceLevel = SourceLevel.AGGREGATOR_OR_MARKET_DATA,
    limitations: list[str] | None = None,
) -> None:
    source = f"{record.vendor}:{record.method}"
    store.add_item(
        EvidenceItem(
            key=key,
            value=value,
            status=status,
            source_name=source,
            source_url=_source_url(record.vendor),
            source_level=level,
            as_of_date=_date_arg(record),
            retrieved_at=record.captured_at_utc,
            limitations=limitations or ["Promoted from upstream TradingAgents tool output."],
            retrieval_method="upstream_tool_capture",
            confidence="medium",
            direct_or_proxy="direct",
        )
    )
    store.record_attempt("upstream_tool_promotion", key, status, f"Promoted from {source}.")


def _promote_fundamentals(store: EvidenceStore, record: UpstreamToolRecord) -> None:
    text = record.result
    forward_pe = _field_number(text, "Forward PE")
    forward_eps = _field_number(text, "Forward EPS")
    trailing_eps = _field_number(text, "EPS (TTM)")
    free_cash_flow = _field_number(text, "Free Cash Flow")
    high_52 = _field_number(text, "52 Week High")
    low_52 = _field_number(text, "52 Week Low")
    if forward_eps is not None:
        _add(store, "valuation.fy1_eps", forward_eps, record)
    if trailing_eps is not None:
        _add(store, "valuation.ttm_eps", trailing_eps, record)
    if forward_pe is not None:
        _add(store, "valuation.forward_pe_reported", forward_pe, record)
    if forward_pe is not None or forward_eps is not None:
        _add(store, "valuation.forward_pe_basis", {"forward_pe": forward_pe, "forward_eps": forward_eps}, record)
    if free_cash_flow is not None and abs(free_cash_flow) > 1_000:
        _add(store, "cashflow.free_cash_flow_ttm", free_cash_flow, record)
    if high_52 is not None and low_52 is not None:
        _add(store, "market.52w_range", {"high": high_52, "low": low_52}, record)


def _promote_cashflow(store: EvidenceStore, record: UpstreamToolRecord) -> None:
    rows = _parse_csv_from_tool_output(record.result)
    if not rows:
        return
    latest = _latest_numeric_column(rows)
    if not latest:
        return
    period_type = str(record.args[1] if len(record.args) > 1 else "").lower()
    prefix = "cashflow.annual" if period_type == "annual" else "cashflow.latest"
    ocf = _row_value(rows, latest, ("Operating Cash Flow", "Total Cash From Operating Activities", "Net Cash Provided By Operating Activities"))
    capex = _row_value(rows, latest, ("Capital Expenditure", "Capital Expenditures", "Additions To Property Plant And Equipment"))
    fcf = _row_value(rows, latest, ("Free Cash Flow",))
    if ocf is not None:
        _add(store, f"{prefix}.ocf", ocf, record, level=SourceLevel.AGGREGATOR_OR_MARKET_DATA)
    if capex is not None:
        _add(store, f"{prefix}.capex", abs(capex), record, level=SourceLevel.AGGREGATOR_OR_MARKET_DATA)
    if ocf is not None and capex is not None and abs(ocf) >= 1_000 and abs(capex) >= 1_000:
        fcf_key = "cashflow.annual.fcf_inputs" if prefix == "cashflow.annual" else "cashflow.fcf_inputs"
        _add(store, fcf_key, {"period": latest, "ocf": ocf, "capex": abs(capex), "fcf": ocf - abs(capex)}, record)
    elif fcf is not None:
        _add(store, f"{prefix}.fcf", fcf, record, status=EvidenceStatus.PARTIAL)


def _promote_income_statement(store: EvidenceStore, record: UpstreamToolRecord) -> None:
    rows = _parse_csv_from_tool_output(record.result)
    latest = _latest_numeric_column(rows) if rows else None
    if not latest:
        return
    revenue = _row_value(rows, latest, ("Total Revenue", "Revenue"))
    eps = _row_value(rows, latest, ("Diluted EPS", "Basic EPS"))
    if revenue is not None:
        _add(store, "earnings.revenue.actual", revenue, record, level=SourceLevel.AGGREGATOR_OR_MARKET_DATA)
    if eps is not None:
        _add(store, "earnings.eps.actual", eps, record, level=SourceLevel.AGGREGATOR_OR_MARKET_DATA)


def _promote_stock_data(store: EvidenceStore, record: UpstreamToolRecord) -> None:
    rows = _parse_csv_from_tool_output(record.result)
    if not rows:
        return
    latest = rows[-1]
    close = _to_float(latest.get("Close"))
    if close is None:
        return
    _add(
        store,
        "market.latest_price",
        {"close": close, "date": latest.get("Date") or latest.get("") or _date_arg(record), "volume": _to_float(latest.get("Volume"))},
        record,
    )


def _promote_indicator(store: EvidenceStore, record: UpstreamToolRecord) -> None:
    text = record.result
    indicator = str(record.args[1] if len(record.args) > 1 else "").lower()
    latest = None
    for match in re.finditer(r"(20\d{2}-\d{2}-\d{2}):\s*([-+]?\d+(?:\.\d+)?)", text):
        latest = (match.group(1), float(match.group(2)))
    if not latest:
        return
    key_map = {
        "close_10_ema": "technical.ema_10",
        "close_50_sma": "technical.sma_50",
        "close_200_sma": "technical.sma_200",
        "rsi": "technical.rsi_14",
        "vwma": "technical.vwma_20",
    }
    key = key_map.get(indicator)
    if key:
        _add(store, key, latest[1], record)


def _promote_news_or_insider(store: EvidenceStore, record: UpstreamToolRecord) -> None:
    text = record.result.lower()
    if "earnings" in text:
        _add(store, "catalyst.news_earnings_mentions", _compact(record.result), record, status=EvidenceStatus.PARTIAL)
    if "insider" in text or record.method == "get_insider_transactions":
        _add(store, "ownership.form4_90d", _compact(record.result), record, status=EvidenceStatus.PARTIAL)


def _compute_from_promoted(store: EvidenceStore) -> None:
    price = store.value("market.latest_price", {}) or {}
    close = price.get("close") if isinstance(price, dict) else None
    fy1 = store.value("valuation.fy1_eps")
    if close and fy1 and not store.is_usable("valuation.forward_pe_basis"):
        _add_synthetic(store, "valuation.forward_pe_basis", {"price": close, "fy1_eps": fy1, "fy1_pe": float(close) / float(fy1)})


def _add_synthetic(store: EvidenceStore, key: str, value: Any) -> None:
    store.add_item(
        EvidenceItem(
            key=key,
            value=value,
            status=EvidenceStatus.COMPUTED,
            source_name="Titan upstream tool promotion",
            source_url=None,
            source_level=SourceLevel.AGGREGATOR_OR_MARKET_DATA,
            as_of_date=store.report_date,
            retrieved_at=utc_now_iso(),
            limitations=["Computed from promoted upstream tool evidence."],
            retrieval_method="upstream_tool_promotion",
            confidence="medium",
            direct_or_proxy="direct",
        )
    )


def _field_number(text: str, label: str) -> float | None:
    match = re.search(rf"{re.escape(label)}:\s*([-+]?\d+(?:\.\d+)?)", text, re.I)
    return float(match.group(1)) if match else None


def _parse_csv_from_tool_output(text: str) -> list[dict[str, str]]:
    lines = [line for line in text.splitlines() if line and not line.startswith("#")]
    if not lines:
        return []
    try:
        return list(csv.DictReader(StringIO("\n".join(lines))))
    except Exception:
        return []


def _latest_numeric_column(rows: list[dict[str, str]]) -> str | None:
    if not rows:
        return None
    columns = list(rows[0].keys())
    date_like = [col for col in columns if re.match(r"20\d{2}-\d{2}-\d{2}", str(col))]
    return sorted(date_like)[-1] if date_like else None


def _row_value(rows: list[dict[str, str]], column: str, labels: tuple[str, ...]) -> float | None:
    for row in rows:
        row_name = str(row.get("") or row.get("Breakdown") or row.get("index") or row.get("Unnamed: 0") or "").lower()
        if any(label.lower() in row_name for label in labels):
            return _to_float(row.get(column))
    return None


def _to_float(value: Any) -> float | None:
    if value in (None, "", "None", "nan", "NaN"):
        return None
    try:
        return float(str(value).replace(",", ""))
    except ValueError:
        return None


def _source_url(vendor: str) -> str | None:
    return {
        "yfinance": "https://finance.yahoo.com/",
        "alpha_vantage": "https://www.alphavantage.co/",
    }.get(vendor)


def _date_arg(record: UpstreamToolRecord) -> str | None:
    for value in list(record.args) + list(record.kwargs.values()):
        if isinstance(value, str) and re.match(r"20\d{2}-\d{2}-\d{2}", value):
            return value[:10]
    return None


def _compact(text: str, limit: int = 500) -> str:
    value = re.sub(r"\s+", " ", text).strip()
    return value if len(value) <= limit else value[: limit - 3] + "..."
