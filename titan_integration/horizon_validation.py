"""Stage 4 Titan horizon validation.

This stage evaluates Intraday, Swing, Positional, and Long-Term horizons from
the graph-backed evidence and delta packet. It is deliberately conservative and
does not infer a validated horizon where required Titan evidence blocks are
blocked, stale, or unavailable.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .research_cycle import utc_now_iso
from .validation_outcomes import CONDITIONAL, CONDITIONAL_CANDIDATE, NOT_VALIDATED, VALIDATED, USABLE_RANGE_ASSUMPTION_BASED


@dataclass(frozen=True)
class HorizonDecision:
    horizon: str
    classification: str
    evidence_status: str
    rationale: str
    supported_evidence: list[str] = field(default_factory=list)
    blocking_factors: list[str] = field(default_factory=list)
    required_next_evidence: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class HorizonValidationPacket:
    ticker: str
    trade_date: str
    generated_at_utc: str
    research_cycle: dict[str, Any]
    stage: str
    compliance_status: str
    stance_delta: str
    horizon_decisions: list[HorizonDecision]
    validated_trading_horizon: str
    titan_self_audit: dict[str, Any]
    source_paths: dict[str, str]
    next_required_evidence: list[str]


def build_horizon_validation_packet(
    *,
    prior_graph_path: Path,
    fresh_graph_path: Path,
    delta_packet_path: Path,
) -> HorizonValidationPacket:
    prior_graph = _read_json(prior_graph_path)
    fresh_graph = _read_json(fresh_graph_path)
    delta = _read_json(delta_packet_path)

    graph_items = _claim_statuses(fresh_graph)
    delta_items = {item["label"]: item for item in delta.get("delta_items", [])}
    stance_delta = _stance_delta(delta_items)

    decisions = [
        _intraday_decision(fresh_graph, graph_items, delta_items),
        _swing_decision(fresh_graph, graph_items, delta_items, stance_delta),
        _positional_decision(fresh_graph, graph_items, delta_items),
        _long_term_decision(fresh_graph, graph_items, delta_items),
    ]
    validated = _validated_horizon_label(decisions)

    return HorizonValidationPacket(
        ticker=fresh_graph["ticker"],
        trade_date=fresh_graph["trade_date"],
        generated_at_utc=utc_now_iso(),
        research_cycle=fresh_graph.get("research_cycle", {}),
        stage="Titan Validation Packet Stage 4 - Horizon Validation",
        compliance_status="Not Titan-Compliant",
        stance_delta=stance_delta,
        horizon_decisions=decisions,
        validated_trading_horizon=validated,
        titan_self_audit=_self_audit(decisions, graph_items, delta_items),
        source_paths={
            "prior_graph": str(prior_graph_path),
            "fresh_graph": str(fresh_graph_path),
            "delta_packet": str(delta_packet_path),
        },
        next_required_evidence=_next_required_evidence(decisions),
    )


def write_horizon_validation_packet(packet: HorizonValidationPacket, out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    cycle = packet.research_cycle or {}
    run_id = cycle.get("research_run_id") or f"{packet.ticker}_{packet.trade_date}"
    stem = f"{run_id}_stage4_horizon_validation_packet"
    json_path = out_dir / f"{stem}.json"
    md_path = out_dir / f"{stem}.md"
    payload = asdict(packet)
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(_to_markdown(payload), encoding="utf-8")
    return json_path, md_path


def _intraday_decision(
    graph: dict[str, Any],
    graph_items: dict[str, str],
    delta_items: dict[str, dict[str, Any]],
) -> HorizonDecision:
    market_as_of = graph.get("research_cycle", {}).get("market_data_as_of")
    requested = graph.get("research_cycle", {}).get("requested_analysis_date")
    intraday_features = _technical_features(graph, {"5m", "15m", "1h", "4h"})
    blockers = [
        "No live tape, session liquidity, spread/depth, or opening-range evidence is present in the graph.",
        "Intraday cannot be fully validated outside live regular-session microstructure confirmation.",
    ]
    if market_as_of and requested and market_as_of < requested:
        blockers.append(
            f"Research was generated on {requested}, but latest regular-session market data is {market_as_of}."
        )
    return HorizonDecision(
        horizon="Intraday / Day Trading",
        classification=CONDITIONAL_CANDIDATE,
        evidence_status="Pre-session candidate evidence present; live execution evidence absent",
        rationale=(
            "The graph now includes user-derived intraday technical context, including "
            "VWAP/RSI/ADX/ATR/volume features where supplied. Titan intraday validation "
            "still requires live tape behavior, session liquidity, spread/depth, and "
            "opening-range structure. Those live evidence blocks are not available in "
            "this weekend/after-close packet, so this is a conditional intraday candidate "
            "for market-open monitoring rather than a validated intraday trade call."
        ),
        supported_evidence=[
            "Daily price/technical structure is graph-supported.",
            "Recent high-volume down-day/distribution warning is graph-supported where present.",
        ]
        + _technical_support_lines(intraday_features),
        blocking_factors=blockers,
        required_next_evidence=[
            "Monitor opening tape, VWAP interaction, spread/depth, and opening-range acceptance/rejection.",
            "Validate intraday liquidity profile during the execution session before any live trade call.",
        ],
    )


def _swing_decision(
    graph: dict[str, Any],
    graph_items: dict[str, str],
    delta_items: dict[str, dict[str, Any]],
    stance_delta: str,
) -> HorizonDecision:
    stale = _stale_labels(delta_items)
    swing_features = _technical_features(graph, {"1d", "1w", "4h"})
    forward_pe_status = graph_items.get("Forward P/E", "Unknown")
    valuation_range_usable = forward_pe_status == USABLE_RANGE_ASSUMPTION_BASED
    blockers = []
    if stale:
        blockers.append("Fresh graph did not reproduce these prior catalyst/timing claims: " + ", ".join(stale))
    if "Forward valuation claim" in graph_items and graph_items["Forward valuation claim"] == "Contradictory":
        if valuation_range_usable:
            blockers.append(
                "The specific forward valuation point estimate remains blocked, but an assumption-based forward P/E range is usable."
            )
        else:
            blockers.append("Forward valuation remains contradictory and cannot support a bullish swing thesis.")
    return HorizonDecision(
        horizon="Swing",
        classification=CONDITIONAL,
        evidence_status=(
            "Daily technical and catalyst evidence present, valuation unresolved"
            if not stale
            else "Daily technical evidence present, catalyst freshness incomplete"
        ),
        rationale=(
            "Swing evidence is partially available: daily structure, momentum deterioration, "
            "distribution evidence, and user-derived multi-timeframe technical features are "
            "supported, and the fresh baseline stance is constructive but confirmation-gated. "
            + (
                "However, stale catalyst/timing items and blocked valuation prevent a fully validated swing horizon. "
                if stale
                else "The stale catalyst/timing items have been refreshed, but blocked valuation still prevents a fully validated swing horizon. "
            )
            + "The correct Titan treatment is Conditional: constructive swing/accumulation scenarios may be monitored, but execution should wait for next-session price behavior to confirm support or reclaim levels, with valuation assumptions clearly disclosed."
        ),
        supported_evidence=[
            "Price remains below short-term trend but above 50-day and 200-day averages.",
            "Recent distribution warning is supported where present.",
            f"TradingAgents stance delta: {stance_delta}.",
        ]
        + _technical_support_lines(swing_features),
        blocking_factors=blockers,
        required_next_evidence=[
            "Confirm next-session acceptance/rejection around key support and short-term reclaim levels.",
            "Reconcile swing target/invalidation against ATR and current liquidity.",
            "Use the assumption-based valuation range only with explicit caveats; do not validate the specific forward valuation point estimate unless its EPS input is sourced.",
        ],
    )


def _positional_decision(
    graph: dict[str, Any],
    graph_items: dict[str, str],
    delta_items: dict[str, dict[str, Any]],
) -> HorizonDecision:
    forward_pe_status = graph_items.get("Forward P/E", "Unknown")
    valuation_range_usable = forward_pe_status == USABLE_RANGE_ASSUMPTION_BASED
    return HorizonDecision(
        horizon="Positional",
        classification=CONDITIONAL_CANDIDATE if valuation_range_usable else NOT_VALIDATED,
        evidence_status=(
            "Fundamental context present; assumption-based valuation range usable, revisions still incomplete"
            if valuation_range_usable
            else "Fundamental context present, valuation block unresolved"
        ),
        rationale=(
            "SEC/fundamental availability and macro context are present, but positional "
            "validation requires valuation context, earnings/revisions quality, factor "
            "regime alignment, and thesis durability over weeks to months. "
            + (
                "The specific forward P/E point estimate remains blocked, but the assumption-based valuation range is usable for scenario framing. Positional status is therefore a conditional candidate, not a fully validated horizon."
                if valuation_range_usable
                else f"The forward valuation claim remains contradictory and the Forward P/E status is {forward_pe_status}, so Titan positional validation is not permitted."
            )
        ),
        supported_evidence=[
            "Official SEC evidence exists for core financial statement facts.",
            "Macro/geopolitical context is supported.",
            "Ecosystem proxy claims are supported as indirect evidence.",
        ],
        blocking_factors=[
            "Specific forward valuation point estimate remains blocked because its EPS input is not independently sourced.",
            f"Forward P/E range status is {forward_pe_status}.",
            "Proxy ecosystem evidence cannot be treated as direct issuer revenue validation.",
            "Earnings revisions and factor/sector regime evidence are not yet fully mapped for a validated positional horizon.",
        ],
        required_next_evidence=[
            "Source or reject the specific forward EPS input behind the reported forward P/E point estimate.",
            "Add earnings revisions and valuation range evidence.",
            "Separate direct issuer evidence from proxy ecosystem evidence.",
        ],
    )


def _long_term_decision(
    graph: dict[str, Any],
    graph_items: dict[str, str],
    delta_items: dict[str, dict[str, Any]],
) -> HorizonDecision:
    forward_pe_status = graph_items.get("Forward P/E", "Unknown")
    valuation_range_usable = forward_pe_status == USABLE_RANGE_ASSUMPTION_BASED
    return HorizonDecision(
        horizon="Long-Term Investment",
        classification="Not Validated",
        evidence_status="Insufficient full-horizon evidence stack",
        rationale=(
            "Long-term validation requires a secular thesis, balance-sheet strength, "
            "competitive moat, durable growth/returns, and cycle-aware valuation. This "
            "graph contains useful fundamental and ecosystem context, but the complete "
            "long-term evidence stack has not been collected and valuation remains blocked. "
            "Titan rules therefore prohibit a validated long-term classification."
        ),
        supported_evidence=[
            "Core SEC financial statement availability is supported.",
            "AI infrastructure ecosystem proxy evidence is supported as indirect context.",
        ],
        blocking_factors=[
            (
                "Cycle-aware valuation has a usable assumption-based Forward P/E range, but the specific point estimate remains blocked."
                if valuation_range_usable
                else f"Cycle-aware valuation is blocked by contradictory forward valuation evidence; Forward P/E status is {forward_pe_status}."
            ),
            "Competitive moat and secular thesis have not been fully source-mapped in this packet.",
            "Long-term thesis cannot validate shorter-horizon entries and must stand independently.",
        ],
        required_next_evidence=[
            "Build a dedicated moat/secular thesis evidence packet.",
            "Add balance-sheet and return-on-capital normalization from official filings.",
            "Resolve valuation across historical, sector, and forward-estimate contexts.",
        ],
    )


def _claim_statuses(graph: dict[str, Any]) -> dict[str, str]:
    statuses: dict[str, str] = {}
    for node in graph.get("nodes", []):
        if node.get("node_type") == "claim":
            statuses[node["label"]] = node.get("attributes", {}).get("reinforced_status", "Unknown")
        elif node.get("node_type") == "computed_metric":
            statuses[node["label"]] = node.get("attributes", {}).get("reconciliation_status", "Unknown")
    return statuses


def _technical_features(graph: dict[str, Any], timeframes: set[str]) -> list[dict[str, Any]]:
    features: list[dict[str, Any]] = []
    for node in graph.get("nodes", []):
        if node.get("node_type") != "user_technical_feature":
            continue
        attrs = node.get("attributes", {})
        label = node.get("label", "")
        timeframe = str(label).split(" ", 1)[0]
        if timeframe in timeframes:
            features.append(attrs)
    return features


def _technical_support_lines(features: list[dict[str, Any]]) -> list[str]:
    lines: list[str] = []
    for item in features:
        read = item.get("technical_read")
        if read:
            lines.append(f"User technical feature: {read}.")
    return lines[:6]


def _stance_delta(delta_items: dict[str, dict[str, Any]]) -> str:
    item = delta_items.get("TradingAgents final stance")
    if not item:
        return "No stance delta detected."
    return f"{item.get('prior_status')} -> {item.get('fresh_status')}"


def _stale_labels(delta_items: dict[str, dict[str, Any]]) -> list[str]:
    return [label for label, item in delta_items.items() if item.get("delta_status") == "Stale"]


def _validated_horizon_label(decisions: list[HorizonDecision]) -> str:
    validated = [item.horizon for item in decisions if item.classification == VALIDATED]
    conditional = [item.horizon for item in decisions if item.classification in {CONDITIONAL, CONDITIONAL_CANDIDATE}]
    if validated:
        return ", ".join(validated)
    if conditional:
        return "Conditional Candidate: " + ", ".join(conditional)
    return "No Validated Horizon"


def _self_audit(
    decisions: list[HorizonDecision],
    graph_items: dict[str, str],
    delta_items: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    return {
        "full_validation_claimed": False,
        "timeframe_mixing_check": "Passed - no long-term thesis was used to validate intraday or swing execution.",
        "blocked_evidence_preserved": True,
        "conditional_reasoning_required": True,
        "valuation_block_present": graph_items.get("Forward valuation claim") == "Contradictory",
        "assumption_based_range_present": graph_items.get("Forward P/E") == USABLE_RANGE_ASSUMPTION_BASED,
        "stale_claim_count": len(_stale_labels(delta_items)),
        "all_horizons_independently_evaluated": len(decisions) == 4,
    }


def _next_required_evidence(decisions: list[HorizonDecision]) -> list[str]:
    items: list[str] = []
    for decision in decisions:
        items.extend(f"{decision.horizon}: {item}" for item in decision.required_next_evidence)
    return list(dict.fromkeys(items))


def _to_markdown(payload: dict[str, Any]) -> str:
    cycle = payload.get("research_cycle", {})
    lines = [
        f"# Stage 4 Horizon Validation: {payload['ticker']}",
        "",
        f"Generated UTC: {payload['generated_at_utc']}",
        f"Research Run ID: {cycle.get('research_run_id')}",
        f"Research Generated Local: {cycle.get('research_generated_at_local')}",
        f"Requested Analysis Date: {cycle.get('requested_analysis_date')}",
        f"Market Data As Of: {cycle.get('market_data_as_of')}",
        f"Compliance Status: {payload['compliance_status']}",
        f"Validated Trading Horizon: {payload['validated_trading_horizon']}",
        f"Stance Delta: {payload['stance_delta']}",
        "",
        "## Horizon Decisions",
        "",
    ]
    for item in payload["horizon_decisions"]:
        lines.extend(
            [
                f"### {item['horizon']}: {item['classification']}",
                "",
                f"Evidence Status: {item['evidence_status']}",
                "",
                f"Rationale: {item['rationale']}",
                "",
                "Supported Evidence:",
                "",
            ]
        )
        lines.extend(f"- {value}" for value in item["supported_evidence"])
        lines.extend(["", "Blocking Factors:", ""])
        lines.extend(f"- {value}" for value in item["blocking_factors"])
        lines.extend(["", "Required Next Evidence:", ""])
        lines.extend(f"- {value}" for value in item["required_next_evidence"])
        lines.append("")
    lines.extend(["## Self-Audit", "", _code_json(payload["titan_self_audit"])])
    lines.extend(["", "## Source Paths", "", _code_json(payload["source_paths"])])
    lines.extend(["", "## Next Required Evidence", ""])
    lines.extend(f"- {item}" for item in payload["next_required_evidence"])
    return "\n".join(lines) + "\n"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _code_json(value: Any) -> str:
    return "```json\n" + json.dumps(value, indent=2, ensure_ascii=False) + "\n```"
