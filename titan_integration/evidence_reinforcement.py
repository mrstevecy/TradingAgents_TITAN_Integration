"""Stage 2B evidence reinforcement.

Stage 2B turns "path to strengthen" notes into explicit tasks. It consumes the
Stage 2 citation packet and a reinforcement manifest, then produces a packet
showing whether Conditional claims were strengthened, stayed Conditional, or
were contradicted by stronger evidence.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .citation_retrieval import CitationSource
from .evidence_ledger import EvidenceLedger
from .equity_evidence import EvidenceStore, promoted_store_from_stage_packets
from .research_cycle import inherit_research_cycle, utc_now_iso


@dataclass(frozen=True)
class ReinforcementTask:
    task_id: str
    target_claim_contains: list[str]
    original_stage2_status: str
    missing_evidence: list[str]
    retrieval_actions: list[str]
    added_source_ids: list[str]
    reinforced_status: str
    evidence_class: str
    rationale: str
    residual_gaps: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ReinforcedClaim:
    claim: str
    previous_status: str
    reinforced_status: str
    evidence_class: str
    rationale: str
    source_ids: list[str]
    residual_gaps: list[str]
    task_id: str | None = None


@dataclass(frozen=True)
class Stage2BPacket:
    ticker: str
    trade_date: str
    generated_at_utc: str
    research_cycle: dict[str, Any]
    stage: str
    compliance_status: str
    upstream_stage2_status: str
    reinforcement_manifest_path: str
    reinforced_claims: list[ReinforcedClaim]
    reinforcement_tasks: list[ReinforcementTask]
    citation_sources: list[CitationSource]
    status_counts: dict[str, int]
    residual_evidence_gaps: list[str]
    next_required_evidence: list[str]
    promoted_equity_evidence_store: dict[str, Any]


def build_stage2b_packet(*, stage2_packet_path: Path, manifest_path: Path) -> Stage2BPacket:
    stage2 = json.loads(stage2_packet_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    base_sources = [CitationSource(**source) for source in stage2.get("citation_sources", [])]
    added_sources = [CitationSource(**source) for source in manifest.get("added_sources", [])]
    all_sources = _dedupe_sources(base_sources + added_sources)
    tasks = [ReinforcementTask(**task) for task in manifest.get("reinforcement_tasks", [])]

    sources_by_id = {source.source_id: source for source in all_sources}
    trade_date = stage2["trade_date"]
    ledger = EvidenceLedger.from_citation_sources(
        research_date=trade_date,
        sources=all_sources,
        asset=stage2["ticker"],
    )
    reinforced_claims = [
        _reinforce_claim(claim, tasks, sources_by_id, ledger) for claim in stage2.get("linked_claims", [])
    ]
    promoted_store = promoted_store_from_stage_packets(
        ticker=stage2["ticker"],
        report_date=stage2["trade_date"],
        stage2=stage2,
        stage2b={
            "citation_sources": [source.__dict__ for source in all_sources],
            "reinforced_claims": [claim.__dict__ for claim in reinforced_claims],
        },
        base_store=EvidenceStore(
            ticker=stage2["ticker"],
            report_date=stage2["trade_date"],
            generated_at=utc_now_iso(),
        ),
    )

    generated_at_utc = utc_now_iso()
    return Stage2BPacket(
        ticker=stage2["ticker"],
        trade_date=stage2["trade_date"],
        generated_at_utc=generated_at_utc,
        research_cycle=inherit_research_cycle(
            stage2,
            fallback_ticker=stage2["ticker"],
            fallback_trade_date=stage2["trade_date"],
            fallback_generated_at_utc=generated_at_utc,
        ),
        stage="Titan Validation Packet Stage 2B - Evidence Reinforcement",
        compliance_status="Not Titan-Compliant",
        upstream_stage2_status=stage2.get("compliance_status", "Unknown"),
        reinforcement_manifest_path=str(manifest_path),
        reinforced_claims=reinforced_claims,
        reinforcement_tasks=tasks,
        citation_sources=all_sources,
        status_counts=_status_counts(reinforced_claims),
        residual_evidence_gaps=_residual_gaps(reinforced_claims),
        next_required_evidence=_next_required_evidence(),
        promoted_equity_evidence_store=promoted_store.to_dict(),
    )


def write_stage2b_packet(packet: Stage2BPacket, out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{packet.ticker}_{packet.trade_date}_stage2b_reinforcement_packet"
    json_path = out_dir / f"{stem}.json"
    md_path = out_dir / f"{stem}.md"

    payload = asdict(packet)
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(_to_markdown(payload), encoding="utf-8")
    promoted_path = out_dir / f"{packet.ticker}_{packet.trade_date}_equity_evidence_store_promoted.json"
    promoted_path.write_text(
        json.dumps(packet.promoted_equity_evidence_store, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return json_path, md_path


def _reinforce_claim(
    claim: dict[str, Any],
    tasks: list[ReinforcementTask],
    sources_by_id: dict[str, CitationSource],
    ledger: EvidenceLedger,
) -> ReinforcedClaim:
    matching_task = _match_task(claim["claim"], tasks)
    if not matching_task:
        return ReinforcedClaim(
            claim=claim["claim"],
            previous_status=claim["stage2_status"],
            reinforced_status=claim["stage2_status"],
            evidence_class=claim["evidence_class"],
            rationale="No Stage 2B reinforcement task targeted this claim.",
            source_ids=claim.get("source_ids", []),
            residual_gaps=claim.get("unresolved_requirements", []),
        )

    candidate_source_ids = list(dict.fromkeys(claim.get("source_ids", []) + matching_task.added_source_ids))
    validation = ledger.validate_claim(
        claim=claim["claim"],
        source_ids=candidate_source_ids,
        requested_status=matching_task.reinforced_status,
        evidence_class=matching_task.evidence_class,
        rationale=matching_task.rationale,
        unresolved_requirements=matching_task.residual_gaps,
    )
    return ReinforcedClaim(
        claim=claim["claim"],
        previous_status=claim["stage2_status"],
        reinforced_status=validation.status,
        evidence_class=validation.evidence_class,
        rationale=validation.rationale,
        source_ids=validation.source_ids,
        residual_gaps=validation.unresolved_requirements,
        task_id=matching_task.task_id,
    )


def _match_task(claim: str, tasks: list[ReinforcementTask]) -> ReinforcementTask | None:
    normalized = claim.lower()
    for task in tasks:
        if any(_specific_pattern_matches(pattern, normalized) for pattern in task.target_claim_contains):
            return task
    return None


def _specific_pattern_matches(pattern: str, normalized_claim: str) -> bool:
    normalized_pattern = " ".join(pattern.lower().split())
    if not normalized_pattern:
        return False
    pattern_terms = [term for term in normalized_pattern.replace("/", " ").replace("-", " ").split() if term]
    if len(pattern_terms) < 2:
        return normalized_pattern == normalized_claim
    return normalized_pattern in normalized_claim


def _dedupe_sources(sources: list[CitationSource]) -> list[CitationSource]:
    seen: set[str] = set()
    deduped: list[CitationSource] = []
    for source in sources:
        if source.source_id in seen:
            continue
        seen.add(source.source_id)
        deduped.append(source)
    return deduped


def _status_counts(claims: list[ReinforcedClaim]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for claim in claims:
        counts[claim.reinforced_status] = counts.get(claim.reinforced_status, 0) + 1
    return counts


def _residual_gaps(claims: list[ReinforcedClaim]) -> list[str]:
    gaps = [
        "Titan Primary Corpus evidence gates have not yet been applied.",
        "Graphify evidence graph has not yet been generated.",
        "Validated Trading Horizon classification has not yet been performed.",
        "Final source-integrity self-audit has not yet been run.",
    ]
    for claim in claims:
        for gap in claim.residual_gaps:
            if gap not in gaps:
                gaps.append(gap)
    return gaps


def _next_required_evidence() -> list[str]:
    return [
        "Graphify Stage 1, Stage 2, Stage 2B, citation manifest, and reinforcement manifest.",
        "Use graph relationships to support Titan horizon classification.",
        "Add automated source retrieval so future tickers do not rely on hand-curated manifests.",
        "Run Titan self-audit before any final institutional report.",
    ]


def _to_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# Titan Validation Packet Stage 2B: {payload['ticker']} {payload['trade_date']}",
        "",
        f"Generated UTC: {payload['generated_at_utc']}",
        f"Research Run ID: {payload.get('research_cycle', {}).get('research_run_id')}",
        f"Market Data As Of: {payload.get('research_cycle', {}).get('market_data_as_of')}",
        f"Compliance Status: {payload['compliance_status']}",
        "",
        "## Reinforced Claim Outcomes",
        "",
        "| Reinforced Status | Previous Status | Evidence Class | Claim | Sources |",
        "|---|---|---|---|---|",
    ]
    for claim in payload["reinforced_claims"]:
        lines.append(
            f"| {claim['reinforced_status']} | {claim['previous_status']} | "
            f"{claim['evidence_class']} | {claim['claim']} | "
            f"{', '.join(claim['source_ids']) or 'None'} |"
        )

    lines.extend(["", "## Reinforcement Rationales", ""])
    for claim in payload["reinforced_claims"]:
        lines.extend(
            [
                f"### {claim['reinforced_status']}: {claim['claim']}",
                "",
                f"Task: {claim['task_id'] or 'None'}",
                "",
                f"Rationale: {claim['rationale']}",
                "",
                f"Residual gaps: {', '.join(claim['residual_gaps']) or 'None'}",
                "",
            ]
        )

    lines.extend(["## Reinforcement Tasks", ""])
    for task in payload["reinforcement_tasks"]:
        lines.extend(
            [
                f"### {task['task_id']}",
                "",
                f"Target status: {task['reinforced_status']}",
                "",
                "Retrieval actions:",
                "",
            ]
        )
        lines.extend(f"- {action}" for action in task["retrieval_actions"])
        lines.extend(["", f"Rationale: {task['rationale']}", ""])

    lines.extend(
        [
            "## Added / Available Sources",
            "",
            "| Source ID | Publisher | Tier | Type | Date | URL |",
            "|---|---|---|---|---|---|",
        ]
    )
    for source in payload["citation_sources"]:
        lines.append(
            f"| {source['source_id']} | {source['publisher']} | {source['reliability_tier']} | "
            f"{source['source_type']} | {source['published_date']} | {source['url']} |"
        )

    lines.extend(["", "## Status Counts", "", _code_json(payload["status_counts"])])
    lines.extend(["", "## Residual Evidence Gaps", ""])
    lines.extend(f"- {gap}" for gap in payload["residual_evidence_gaps"])
    lines.extend(["", "## Next Required Evidence", ""])
    lines.extend(f"- {item}" for item in payload["next_required_evidence"])
    return "\n".join(lines) + "\n"


def _code_json(value: Any) -> str:
    return "```json\n" + json.dumps(value, indent=2, ensure_ascii=False) + "\n```"
