"""Stage 0A universal research request and instrument registry."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .input_discovery import resolve_latest_input_folder
from .research_cycle import utc_now_iso


IMPLEMENTED = "Implemented"
REGISTERED_NOT_IMPLEMENTED = "Registered But Not Implemented"


@dataclass(frozen=True)
class UniversalResearchRequest:
    asset: str
    ticker: str
    full_name: str
    instrument_type: str
    asset_class: str
    primary_strategy: str
    trading_horizon: str
    execution_platform: str
    analysis_date: str
    input_folder: str
    input_folder_resolution: dict[str, Any] | None = None


@dataclass(frozen=True)
class InstrumentProfile:
    instrument_type: str
    asset_class: str
    status: str
    active_research_profile: str
    expected_data_providers: list[str]
    supported_user_evidence_types: list[str]
    titan_evidence_requirements: list[str]
    enabled_stages: list[str]
    unsupported_explanation: str | None = None


@dataclass(frozen=True)
class ResearchResolutionPacket:
    ticker: str
    generated_at_utc: str
    stage: str
    request: dict[str, Any]
    registry_status: str
    active_research_profile: str
    expected_data_providers: list[str]
    supported_user_evidence_types: list[str]
    titan_evidence_requirements: list[str]
    enabled_stages: list[str]
    unsupported_explanation: str | None
    next_action: str
    compliance_status: str


def _planned(instrument_type: str, asset_class: str) -> InstrumentProfile:
    return InstrumentProfile(
        instrument_type=instrument_type,
        asset_class=asset_class,
        status=REGISTERED_NOT_IMPLEMENTED,
        active_research_profile=f"{instrument_type.lower().replace('-', '_')}_planned",
        expected_data_providers=[],
        supported_user_evidence_types=[],
        titan_evidence_requirements=[],
        enabled_stages=["Stage 0A universal request resolution"],
        unsupported_explanation=(
            f"{instrument_type} is registered for the universal framework roadmap but is not implemented in v1. "
            "The system must not reuse the equity pipeline or generate a simulated Titan result for this profile."
        ),
    )


INSTRUMENT_REGISTRY: dict[str, InstrumentProfile] = {
    "Equity": InstrumentProfile(
        instrument_type="Equity",
        asset_class="Equity",
        status=IMPLEMENTED,
        active_research_profile="equity_v1",
        expected_data_providers=["TradingAgents", "yfinance", "SEC EDGAR", "user_supplied_inputs"],
        supported_user_evidence_types=[
            "TradingView OHLCV CSV",
            "multi-timeframe technical CSV",
            "local supplemental documents as future extension",
        ],
        titan_evidence_requirements=[
            "liquidity and market-quality evidence",
            "price/volume/technical structure",
            "SEC fundamentals and filings",
            "news, macro, catalyst, and valuation source mapping",
            "independent horizon validation for Intraday, Swing, Positional, and Long-Term",
        ],
        enabled_stages=[
            "Stage 0 prior graph context",
            "Stage 0A universal request resolution",
            "Stage 1 pre-compliance packet",
            "Stage 1A user evidence ingestion",
            "Stage 1B user technical features",
            "Stage 2 citation linking",
            "Stage 2B evidence reinforcement",
            "Stage 2C metric reconciliation",
            "Stage 3 evidence graph",
            "Evidence delta",
            "Stage 4 horizon validation",
        ],
    ),
    "ETF": _planned("ETF", "ETF"),
    "Index": _planned("Index", "Index"),
    "Crypto": _planned("Crypto", "Crypto"),
    "FX": _planned("FX", "FX"),
    "Futures": _planned("Futures", "Futures"),
    "Commodity": _planned("Commodity", "Commodity"),
    "Equity-Option": _planned("Equity-Option", "Equity"),
    "ETF-Option": _planned("ETF-Option", "ETF"),
    "Index-Option": _planned("Index-Option", "Index"),
    "Futures-Option": _planned("Futures-Option", "Futures"),
    "Commodity-Option": _planned("Commodity-Option", "Commodity"),
    "Crypto-Option": _planned("Crypto-Option", "Crypto"),
    "CFD": _planned("CFD", "Commodity"),
}


def resolve_research_request(request: UniversalResearchRequest) -> ResearchResolutionPacket:
    profile = INSTRUMENT_REGISTRY.get(request.instrument_type)
    if not profile:
        profile = InstrumentProfile(
            instrument_type=request.instrument_type,
            asset_class=request.asset_class,
            status=REGISTERED_NOT_IMPLEMENTED,
            active_research_profile="unregistered_profile",
            expected_data_providers=[],
            supported_user_evidence_types=[],
            titan_evidence_requirements=[],
            enabled_stages=["Stage 0A universal request resolution"],
            unsupported_explanation=(
                f"Instrument type {request.instrument_type!r} is not registered in Stage 0A. "
                "No research workflow may run until a profile is explicitly registered."
            ),
        )
    next_action = (
        "Proceed to existing equity_v1 Stage 1 through Stage 4 workflow."
        if profile.status == IMPLEMENTED
        else "Stop gracefully; do not run equity-specific workflow for this instrument type."
    )
    return ResearchResolutionPacket(
        ticker=request.ticker.upper(),
        generated_at_utc=utc_now_iso(),
        stage="Stage 0A - Universal Research Request Resolution",
        request=asdict(request),
        registry_status=profile.status,
        active_research_profile=profile.active_research_profile,
        expected_data_providers=profile.expected_data_providers,
        supported_user_evidence_types=profile.supported_user_evidence_types,
        titan_evidence_requirements=profile.titan_evidence_requirements,
        enabled_stages=profile.enabled_stages,
        unsupported_explanation=profile.unsupported_explanation,
        next_action=next_action,
        compliance_status="Pre-Compliance Routing Only",
    )


def request_from_mapping(payload: dict[str, Any]) -> UniversalResearchRequest:
    required = [
        "asset",
        "ticker",
        "full_name",
        "instrument_type",
        "asset_class",
        "primary_strategy",
        "trading_horizon",
        "execution_platform",
        "analysis_date",
        "input_folder",
    ]
    if ("input_folder" not in payload or payload.get("input_folder") in {None, ""}) and payload.get("ticker") and payload.get("analysis_date"):
        resolution = resolve_latest_input_folder(
            input_root=Path(payload.get("input_root") or Path.cwd() / "inputs"),
            ticker=str(payload["ticker"]),
            analysis_date=str(payload["analysis_date"]),
        )
        payload["input_folder"] = resolution.selected_input_folder
        payload["input_folder_resolution"] = resolution.to_dict()
    missing = [field for field in required if field not in payload or payload[field] in {None, ""}]
    if missing:
        raise ValueError("Missing required research request field(s): " + ", ".join(missing))
    request_values = {field: str(payload[field]) for field in required}
    if isinstance(payload.get("input_folder_resolution"), dict):
        request_values["input_folder_resolution"] = payload["input_folder_resolution"]
    return UniversalResearchRequest(**request_values)


def write_resolution_packet(packet: ResearchResolutionPacket, out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{packet.ticker}_{packet.request['analysis_date']}_stage0a_research_resolution"
    json_path = out_dir / f"{stem}.json"
    md_path = out_dir / f"{stem}.md"
    payload = asdict(packet)
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(_to_markdown(payload), encoding="utf-8")
    return json_path, md_path


def _to_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# Stage 0A Research Resolution: {payload['ticker']}",
        "",
        f"Generated UTC: {payload['generated_at_utc']}",
        f"Registry Status: {payload['registry_status']}",
        f"Active Research Profile: {payload['active_research_profile']}",
        f"Compliance Status: {payload['compliance_status']}",
        "",
        "## Request",
        "",
        "```json",
        json.dumps(payload["request"], indent=2, ensure_ascii=False),
        "```",
        "",
        "## Enabled Stages",
        "",
    ]
    lines.extend(f"- {stage}" for stage in payload["enabled_stages"])
    lines.extend(
        [
            "",
            "## Expected Data Providers",
            "",
        ]
    )
    lines.extend(f"- {provider}" for provider in payload["expected_data_providers"] or ["None"])
    lines.extend(["", "## Titan Evidence Requirements", ""])
    lines.extend(f"- {item}" for item in payload["titan_evidence_requirements"] or ["Not implemented for this profile."])
    if payload.get("unsupported_explanation"):
        lines.extend(["", "## Unsupported Profile Handling", "", payload["unsupported_explanation"]])
    lines.extend(["", "## Next Action", "", payload["next_action"], ""])
    return "\n".join(lines)
