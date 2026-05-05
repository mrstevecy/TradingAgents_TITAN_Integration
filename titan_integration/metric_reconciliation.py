"""Stage 2C computable metric reconciliation.

This layer handles conflicts in ratios and valuation metrics where the formula
is explicit and the inputs can be tied to timestamped sources. It does not try
to reconcile news or narrative claims.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .research_cycle import inherit_research_cycle, utc_now_iso
from .validation_outcomes import BLOCKED, USABLE_RANGE_ASSUMPTION_BASED


@dataclass(frozen=True)
class MetricInput:
    name: str
    value: float
    unit: str
    source_id: str
    source_type: str
    timestamp: str | None
    notes: str = ""


@dataclass(frozen=True)
class MetricCalculation:
    metric: str
    formula: str
    inputs: list[MetricInput]
    computed_value: float | None
    reported_values: dict[str, Any]
    tolerance_pct: float
    reconciliation_status: str
    specific_claim_status: str
    usable_range: dict[str, Any]
    conclusion: str
    source_ids: list[str]
    limitations: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Stage2CPacket:
    ticker: str
    trade_date: str
    generated_at_utc: str
    research_cycle: dict[str, Any]
    stage: str
    compliance_status: str
    upstream_stage2b_status: str
    reconciled_metrics: list[MetricCalculation]
    status_counts: dict[str, int]
    residual_evidence_gaps: list[str]
    graphify_readiness: dict[str, Any]
    next_required_evidence: list[str]


def build_stage2c_packet(
    *,
    stage1_packet_path: Path,
    stage2b_packet_path: Path,
    baseline_summary_path: Path,
) -> Stage2CPacket:
    stage1 = _read_json(stage1_packet_path)
    stage2b = _read_json(stage2b_packet_path)
    baseline = _read_json(baseline_summary_path)

    calculations = [_forward_pe_reconciliation(stage1, stage2b, baseline)]
    generated_at_utc = utc_now_iso()
    return Stage2CPacket(
        ticker=stage2b["ticker"],
        trade_date=stage2b["trade_date"],
        generated_at_utc=generated_at_utc,
        research_cycle=inherit_research_cycle(
            stage2b,
            fallback_ticker=stage2b["ticker"],
            fallback_trade_date=stage2b["trade_date"],
            fallback_generated_at_utc=generated_at_utc,
        ),
        stage="Titan Validation Packet Stage 2C - Computable Metric Reconciliation",
        compliance_status="Not Titan-Compliant",
        upstream_stage2b_status=stage2b.get("compliance_status", "Unknown"),
        reconciled_metrics=calculations,
        status_counts=_status_counts(calculations),
        residual_evidence_gaps=_residual_gaps(calculations),
        graphify_readiness={
            "ready_for_graphify": True,
            "recommended_input": "Stage 2C packet + Stage 3 graph refresh",
            "edge_policy": (
                "Computed metric nodes must link to formula, input sources, original "
                "reported values, and reconciliation status."
            ),
        },
        next_required_evidence=[
            "Refresh Stage 3 graph with Stage 2C computed metric nodes.",
            "Use computed metric reconciliation before final valuation language.",
            "Add licensed estimates providers where exact institutional forward multiples are required.",
            "Apply Titan horizon validation only after valuation conflicts are resolved or explicitly blocked.",
        ],
    )


def write_stage2c_packet(packet: Stage2CPacket, out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{packet.ticker}_{packet.trade_date}_stage2c_metric_reconciliation_packet"
    json_path = out_dir / f"{stem}.json"
    md_path = out_dir / f"{stem}.md"
    payload = asdict(packet)
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(_to_markdown(payload), encoding="utf-8")
    return json_path, md_path


def _forward_pe_reconciliation(
    stage1: dict[str, Any], stage2b: dict[str, Any], baseline: dict[str, Any]
) -> MetricCalculation:
    ticker = str(stage1.get("ticker") or stage2b.get("ticker") or "").lower()
    price = _reference_price(stage1)
    price_timestamp = stage1.get("price_data_audit", {}).get("source", {}).get("retrieved_at_utc")
    text_blob = json.dumps(baseline, ensure_ascii=False)
    tradingagents_forward_pe = _find_optional_float(
        r"Forward P/E[^0-9]{0,80}([0-9]+(?:\.[0-9]+)?)", text_blob
    )
    tradingagents_forward_eps = _find_optional_float(
        r"Forward EPS Est\.\D+\$?([0-9]+(?:\.[0-9]+)?)", text_blob
    )
    stockanalysis_source = _first_source_matching(stage2b, ["stockanalysis", ticker, "statistics"])
    stockanalysis_forward_pe = _source_forward_pe_from_source(stockanalysis_source)
    eps_source = _first_source_matching(stage2b, ["marketbeat", ticker]) or _first_source_matching(
        stage2b, ["earnings", ticker]
    )
    external_eps = _source_eps_from_source(eps_source)
    external_annualized_eps = external_eps * 4 if external_eps is not None else None
    computed_from_external_eps = price / external_annualized_eps if external_annualized_eps else None
    implied_stockanalysis_eps = price / stockanalysis_forward_pe if stockanalysis_forward_pe else None
    usable_values = [
        value
        for value in (
            stockanalysis_forward_pe,
            computed_from_external_eps,
        )
        if value is not None
    ]
    if not usable_values and tradingagents_forward_pe is not None:
        usable_values.append(tradingagents_forward_pe)

    external_inputs = [
        MetricInput(
            name="report_timestamp_price",
            value=price,
            unit="USD",
            source_id="stage1_yfinance",
            source_type="prototype_market_data",
            timestamp=price_timestamp,
            notes="Reference price used by TradingAgents/Stage 1 for the valuation claim.",
        )
    ]
    if external_annualized_eps is not None and eps_source:
        external_inputs.append(
            MetricInput(
                name="external_eps_estimate_annualized",
                value=external_annualized_eps,
                unit="USD/share",
                source_id=eps_source.get("source_id", "external_eps_source"),
                source_type=eps_source.get("source_type", "secondary_market_data"),
                timestamp=None,
                notes="External EPS estimate annualized for an assumption-based forward P/E scenario.",
            )
        )
    if implied_stockanalysis_eps is not None and stockanalysis_source:
        external_inputs.append(
            MetricInput(
                name="stockanalysis_implied_forward_eps",
                value=implied_stockanalysis_eps,
                unit="USD/share",
                source_id=stockanalysis_source.get("source_id", "stockanalysis_statistics"),
                source_type=stockanalysis_source.get("source_type", "secondary_market_data"),
                timestamp=None,
                notes="Implied from externally reported forward P/E and report-timestamp price; not an independent EPS estimate.",
            )
        )
    source_ids = ["stage1_yfinance", "stage1_tradingagents_summary"]
    if eps_source and eps_source.get("source_id"):
        source_ids.append(eps_source["source_id"])
    if stockanalysis_source and stockanalysis_source.get("source_id"):
        source_ids.append(stockanalysis_source["source_id"])

    if not usable_values:
        return MetricCalculation(
            metric="Forward P/E",
            formula="Forward P/E = report-timestamp price / forward EPS estimate",
            inputs=external_inputs,
            computed_value=None,
            reported_values={
                "tradingagents_reported_forward_pe": tradingagents_forward_pe,
                "tradingagents_forward_eps_estimate": tradingagents_forward_eps,
                "stockanalysis_reported_forward_pe": stockanalysis_forward_pe,
                "computed_using_external_annualized_eps": None,
                "external_annualized_eps_estimate": None,
                "implied_eps_from_stockanalysis_forward_pe": None,
            },
            tolerance_pct=3.0,
            reconciliation_status="Blocked - Missing Valuation Inputs",
            specific_claim_status=BLOCKED,
            usable_range={
                "metric": "Forward P/E",
                "low": None,
                "high": None,
                "unit": "x",
                "basis": [],
                "business_interpretation": (
                    "No usable forward P/E range can be computed until at least one "
                    "dated forward multiple or FY1/FY2/NTM EPS estimate is retrieved."
                ),
            },
            conclusion=(
                "Forward P/E reconciliation is blocked because neither the baseline "
                "nor the external source packet supplied enough validated numeric "
                "valuation inputs. The final report must treat valuation as an "
                "unresolved evidence gap, not as a computable range."
            ),
            source_ids=source_ids,
            limitations=[
                "No externally validated FY1, FY2, or NTM EPS estimate was available to this packet.",
                "No externally validated forward multiple was available to this packet.",
                "A final valuation conclusion must remain constrained until a resolver supplies dated inputs.",
            ],
        )

    usable_low = round(min(usable_values), 2)
    usable_high = round(max(usable_values), 2)

    if tradingagents_forward_pe is None or tradingagents_forward_eps is None:
        return MetricCalculation(
            metric="Forward P/E",
            formula="Forward P/E = report-timestamp price / forward EPS estimate",
            inputs=external_inputs,
            computed_value=round(usable_values[0], 2),
            reported_values={
                "tradingagents_reported_forward_pe": tradingagents_forward_pe,
                "tradingagents_forward_eps_estimate": tradingagents_forward_eps,
                "stockanalysis_reported_forward_pe": stockanalysis_forward_pe,
                "computed_using_external_annualized_eps": round(computed_from_external_eps, 2) if computed_from_external_eps else None,
                "external_annualized_eps_estimate": round(external_annualized_eps, 2) if external_annualized_eps else None,
                "implied_eps_from_stockanalysis_forward_pe": round(implied_stockanalysis_eps, 2) if implied_stockanalysis_eps else None,
            },
            tolerance_pct=3.0,
            reconciliation_status=USABLE_RANGE_ASSUMPTION_BASED,
            specific_claim_status=BLOCKED,
            usable_range={
                "metric": "Forward P/E",
                "low": usable_low,
                "high": usable_high,
                "unit": "x",
                "basis": [
                    "Externally reported forward P/E where available",
                    "External EPS estimate annualized against report-timestamp price where available",
                ],
                "business_interpretation": (
                    "Usable as an assumption-based valuation range; not usable to validate "
                    "any missing or unsourced TradingAgents point estimate."
                ),
            },
            conclusion=(
                "The fresh TradingAgents output did not expose both numeric inputs needed "
                "to validate its own forward P/E point estimate. That specific point "
                "estimate remains blocked. However, independently sourced or computable "
                "valuation scenarios are retained as an assumption-based range where "
                "the required inputs are present."
            ),
            source_ids=source_ids,
            limitations=[
                "Fresh TradingAgents text did not expose the complete computable metric input set.",
                "Assumption-based range does not validate a missing TradingAgents point estimate.",
                "External EPS estimates and secondary forward multiples require explicit source caveats.",
            ],
        )

    computed_from_tradingagents_eps = price / tradingagents_forward_eps

    reported = {
        "tradingagents_reported_forward_pe": tradingagents_forward_pe,
        "stockanalysis_reported_forward_pe": stockanalysis_forward_pe,
        "computed_using_tradingagents_forward_eps": round(computed_from_tradingagents_eps, 2),
        "computed_using_external_annualized_eps": round(computed_from_external_eps, 2) if computed_from_external_eps else None,
        "external_annualized_eps_estimate": round(external_annualized_eps, 2) if external_annualized_eps else None,
        "implied_eps_from_stockanalysis_forward_pe": round(implied_stockanalysis_eps, 2) if implied_stockanalysis_eps else None,
    }

    status = USABLE_RANGE_ASSUMPTION_BASED
    conclusion = (
        "The specific TradingAgents forward P/E claim is mathematically "
        "coherent only when using its own stated forward EPS estimate, "
        "but that EPS input is not independently sourced in the current packet. "
        "That point estimate remains blocked for final Titan use. Separately, "
        "external valuation references and computable EPS scenarios are retained "
        "as an assumption-based forward P/E range. "
        "For positional and long-term analysis, that clustered range is usable "
        "with explicit assumptions because small scenario differences are not "
        "business-material at cent-level precision. The contradiction is between "
        "the specific unsourced point estimate and the independently supported "
        "valuation range, not between immaterial scenario-level rounding differences."
    )

    return MetricCalculation(
        metric="Forward P/E",
        formula="Forward P/E = report-timestamp price / forward EPS estimate",
        inputs=[
            MetricInput(
                name="report_timestamp_price",
                value=price,
                unit="USD",
                source_id="stage1_yfinance",
                source_type="prototype_market_data",
                timestamp=price_timestamp,
                notes="Reference price used by TradingAgents/Stage 1 for the valuation claim.",
            ),
            MetricInput(
                name="tradingagents_forward_eps_estimate",
                value=tradingagents_forward_eps,
                unit="USD/share",
                source_id="stage1_tradingagents_summary",
                source_type="agent_output",
                timestamp=baseline.get("trade_date"),
                notes="Agent-generated EPS estimate; mathematically supports the reported forward P/E but lacks external source validation.",
            ),
        ] + [item for item in external_inputs if item.name != "report_timestamp_price"],
        computed_value=round(computed_from_external_eps or computed_from_tradingagents_eps, 2),
        reported_values=reported,
        tolerance_pct=3.0,
        reconciliation_status=status,
        specific_claim_status=BLOCKED,
        usable_range={
            "metric": "Forward P/E",
            "low": usable_low,
                "high": usable_high,
                "unit": "x",
                "basis": [
                    "TradingAgents reported forward EPS computed against report-timestamp price",
                    "Externally reported forward P/E where available",
                    "External EPS estimate annualized against report-timestamp price where available",
                ],
                "business_interpretation": (
                    "Usable as an assumption-based valuation range; not usable to validate "
                    "TradingAgents' specific point estimate unless its exact EPS input is independently sourced."
                ),
            },
            conclusion=conclusion,
            source_ids=source_ids,
            limitations=[
                "External EPS estimates may be quarterly values annualized as a simple run-rate check.",
                "Secondary forward P/E values are not official company guidance.",
                "TradingAgents' forward EPS estimate needs external source validation before final point-estimate use.",
            ],
    )


def _reference_price(stage1: dict[str, Any]) -> float:
    for item in stage1.get("claim_evidence_map", []):
        if "reference close" in item.get("claim", "").lower():
            claim_price = _find_optional_float(
                r"\$([0-9]+(?:\.[0-9]+)?)", item.get("claim", "")
            )
            if claim_price is not None:
                return claim_price
            evidence_price = _find_optional_float(
                r"reference bar .*? close=([0-9]+(?:\.[0-9]+)?)",
                item.get("evidence", ""),
            )
            if evidence_price is not None:
                return evidence_price
    latest_bar = stage1.get("price_data_audit", {}).get("latest_bar")
    if isinstance(latest_bar, dict) and latest_bar.get("close") is not None:
        return float(latest_bar["close"])
    latest_price = (
        stage1.get("mandatory_equity_data_scan", {})
        .get("items", {})
        .get("market.latest_price", {})
        .get("value", {})
    )
    if isinstance(latest_price, dict) and latest_price.get("close") is not None:
        return float(latest_price["close"])
    raise KeyError("No reference price found in Stage 1 packet.")


def _source_eps(stage2b: dict[str, Any], source_id: str) -> float | None:
    source = _source(stage2b, source_id)
    if not source:
        return None
    return _source_eps_from_source(source)


def _source_forward_pe(stage2b: dict[str, Any], source_id: str) -> float | None:
    source = _source(stage2b, source_id)
    if not source:
        return None
    return _source_forward_pe_from_source(source)


def _source_eps_from_source(source: dict[str, Any] | None) -> float | None:
    if not source:
        return None
    return _find_optional_float(r"EPS(?: estimate)?(?: of| near| around|:)?\s*\$?([0-9]+(?:\.[0-9]+)?)", source.get("evidence_summary", ""))


def _source_forward_pe_from_source(source: dict[str, Any] | None) -> float | None:
    if not source:
        return None
    return _find_optional_float(
        r"forward P/E (?:near |around |of )?([0-9]+(?:\.[0-9]+)?)",
        source.get("evidence_summary", ""),
    )


def _first_source_matching(stage2b: dict[str, Any], needles: list[str]) -> dict[str, Any] | None:
    lowered = [needle.lower() for needle in needles if needle]
    for source in stage2b.get("citation_sources", []) or []:
        blob = " ".join(
            str(source.get(key, ""))
            for key in ("source_id", "title", "publisher", "evidence_summary", "source_type")
        ).lower()
        if all(needle in blob for needle in lowered):
            return source
    return None


def _source(stage2b: dict[str, Any], source_id: str) -> dict[str, Any] | None:
    for source in stage2b.get("citation_sources", []):
        if source.get("source_id") == source_id:
            return source
    return None


def _find_float(pattern: str, text: str) -> float:
    match = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        raise ValueError(f"Could not extract numeric input using pattern: {pattern}")
    return float(match.group(1))


def _find_optional_float(pattern: str, text: str) -> float | None:
    match = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
    return float(match.group(1)) if match else None


def _status_counts(calculations: list[MetricCalculation]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for calculation in calculations:
        counts[calculation.reconciliation_status] = (
            counts.get(calculation.reconciliation_status, 0) + 1
        )
    return counts


def _residual_gaps(calculations: list[MetricCalculation]) -> list[str]:
    gaps = [
        "Titan Primary Corpus evidence gates have not yet been applied.",
        "Validated Trading Horizon classification has not yet been performed.",
        "Final source-integrity self-audit has not yet been run.",
    ]
    for calculation in calculations:
        gaps.extend(calculation.limitations)
    return list(dict.fromkeys(gaps))


def _to_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# Titan Validation Packet Stage 2C: {payload['ticker']} {payload['trade_date']}",
        "",
        f"Generated UTC: {payload['generated_at_utc']}",
        f"Research Run ID: {payload.get('research_cycle', {}).get('research_run_id')}",
        f"Market Data As Of: {payload.get('research_cycle', {}).get('market_data_as_of')}",
        f"Compliance Status: {payload['compliance_status']}",
        "",
        "## Reconciled Metrics",
        "",
    ]
    for metric in payload["reconciled_metrics"]:
        lines.extend(
            [
                f"### {metric['metric']}",
                "",
                f"Status: {metric['reconciliation_status']}",
                "",
                f"Specific claim status: {metric['specific_claim_status']}",
                "",
                f"Formula: `{metric['formula']}`",
                "",
                f"Computed value: `{metric['computed_value']}`",
                "",
                "Reported / computed comparison:",
                "",
                _code_json(metric["reported_values"]),
                "",
                "Usable range:",
                "",
                _code_json(metric["usable_range"]),
                "",
                "Inputs:",
                "",
            ]
        )
        for item in metric["inputs"]:
            lines.append(
                f"- {item['name']}: {item['value']} {item['unit']} "
                f"({item['source_id']}; {item['source_type']})"
            )
        lines.extend(["", f"Conclusion: {metric['conclusion']}", ""])
        lines.extend(["Limitations:", ""])
        lines.extend(f"- {item}" for item in metric["limitations"])
        lines.append("")

    lines.extend(["## Status Counts", "", _code_json(payload["status_counts"])])
    lines.extend(["", "## Residual Evidence Gaps", ""])
    lines.extend(f"- {gap}" for gap in payload["residual_evidence_gaps"])
    lines.extend(["", "## Graphify Readiness", "", _code_json(payload["graphify_readiness"])])
    lines.extend(["", "## Next Required Evidence", ""])
    lines.extend(f"- {item}" for item in payload["next_required_evidence"])
    return "\n".join(lines) + "\n"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _code_json(value: Any) -> str:
    return "```json\n" + json.dumps(value, indent=2, ensure_ascii=False) + "\n```"
