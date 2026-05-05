"""Evidence ledger for source-led validation.

The ledger is the system-of-record for external evidence. Agent prose can
reference facts, but only ledger sources and extracted facts can validate them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Protocol


SUPPORTED = "Supported"
NOT_VALIDATED = "Not Validated"
CONDITIONAL = "Conditional"
FUTURE_DATED_EXCLUDED = "Future-Dated Evidence Excluded"
SOURCE_MISSING = "Source Missing"


@dataclass(frozen=True)
class EvidenceFact:
    fact_id: str
    claim: str
    fact_type: str
    value: Any | None = None
    unit: str | None = None
    as_of_date: str | None = None
    confidence: str = "source_reported"


@dataclass(frozen=True)
class EvidenceSourceRecord:
    source_id: str
    publisher: str
    title: str
    url: str
    published_date: str | None
    retrieved_at_utc: str
    source_class: str
    source_type: str
    evidence_summary: str
    supported_claims: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    facts_extracted: list[EvidenceFact] = field(default_factory=list)


@dataclass(frozen=True)
class ClaimValidationResult:
    claim: str
    status: str
    evidence_class: str
    rationale: str
    source_ids: list[str] = field(default_factory=list)
    unresolved_requirements: list[str] = field(default_factory=list)


class CitationLikeSource(Protocol):
    source_id: str
    publisher: str
    title: str
    url: str
    published_date: str | None
    retrieved_at_utc: str
    reliability_tier: str
    source_type: str
    evidence_summary: str
    supported_claims: list[str]
    limitations: list[str]


class EvidenceLedger:
    def __init__(self, *, research_date: str, asset: str | None = None) -> None:
        self.research_date = research_date
        self.asset = asset
        self._sources: dict[str, EvidenceSourceRecord] = {}

    @classmethod
    def from_citation_sources(
        cls,
        *,
        research_date: str,
        sources: list[CitationLikeSource],
        asset: str | None = None,
    ) -> "EvidenceLedger":
        ledger = cls(research_date=research_date, asset=asset)
        for source in sources:
            ledger.add_source(
                EvidenceSourceRecord(
                    source_id=source.source_id,
                    publisher=source.publisher,
                    title=source.title,
                    url=source.url,
                    published_date=source.published_date,
                    retrieved_at_utc=source.retrieved_at_utc,
                    source_class=source.reliability_tier,
                    source_type=source.source_type,
                    evidence_summary=source.evidence_summary,
                    supported_claims=list(source.supported_claims),
                    limitations=list(source.limitations),
                    facts_extracted=_facts_from_supported_claims(source),
                )
            )
        return ledger

    def add_source(self, source: EvidenceSourceRecord) -> None:
        self._sources[source.source_id] = source

    def source(self, source_id: str) -> EvidenceSourceRecord | None:
        return self._sources.get(source_id)

    def sources(self) -> list[EvidenceSourceRecord]:
        return list(self._sources.values())

    def validate_claim(
        self,
        *,
        claim: str,
        source_ids: list[str],
        requested_status: str,
        evidence_class: str,
        rationale: str,
        unresolved_requirements: list[str] | None = None,
    ) -> ClaimValidationResult:
        missing = [source_id for source_id in source_ids if source_id not in self._sources]
        if missing:
            return ClaimValidationResult(
                claim=claim,
                status=NOT_VALIDATED,
                evidence_class=SOURCE_MISSING,
                rationale=f"Claim references source IDs missing from the evidence ledger: {', '.join(missing)}.",
                source_ids=source_ids,
                unresolved_requirements=["Retrieve or register the missing evidence source records before validation."],
            )

        future = [source_id for source_id in source_ids if self.is_future_dated(source_id)]
        valid_source_ids = [source_id for source_id in source_ids if source_id not in set(future)]
        if future and not valid_source_ids:
            return ClaimValidationResult(
                claim=claim,
                status=NOT_VALIDATED,
                evidence_class="future_dated_evidence_excluded",
                rationale=(
                    "Claim references only source records dated after the research date. "
                    "Future-dated evidence cannot validate an as-of research claim."
                ),
                source_ids=[],
                unresolved_requirements=[
                    f"Replace future-dated source(s) with as-of-date evidence: {', '.join(future)}."
                ],
            )

        if not valid_source_ids and requested_status == SUPPORTED:
            return ClaimValidationResult(
                claim=claim,
                status=NOT_VALIDATED,
                evidence_class="no_source_id_no_validation",
                rationale="No source ID was provided. Agent prose cannot validate an external fact.",
                source_ids=[],
                unresolved_requirements=["Attach at least one ledger source ID or mark the claim as a gap/assumption."],
            )

        matched_source_ids = [
            source_id
            for source_id in valid_source_ids
            if self.source_supports_claim(source_id=source_id, claim=claim)
        ]
        if requested_status == SUPPORTED and not matched_source_ids:
            return ClaimValidationResult(
                claim=claim,
                status=CONDITIONAL,
                evidence_class="source_link_requires_fact_match",
                rationale=(
                    "Source IDs exist and are as-of valid, but no source supported-claim or extracted fact clearly "
                    "matches the claim text. Keep the claim conditional until fact extraction is explicit."
                ),
                source_ids=valid_source_ids,
                unresolved_requirements=(unresolved_requirements or [])
                + ["Extract a matching source fact or downgrade the claim."],
            )

        return ClaimValidationResult(
            claim=claim,
            status=requested_status,
            evidence_class=evidence_class,
            rationale=(
                rationale
                if not future
                else f"{rationale} Future-dated source(s) excluded: {', '.join(future)}."
            ),
            source_ids=valid_source_ids,
            unresolved_requirements=(unresolved_requirements or [])
            + ([f"Future-dated source(s) excluded: {', '.join(future)}."] if future else []),
        )

    def is_future_dated(self, source_id: str) -> bool:
        source = self._sources.get(source_id)
        if not source:
            return False
        published = parse_date(source.published_date)
        research_date = parse_date(self.research_date)
        if not published or not research_date:
            return False
        return published > research_date

    def source_supports_claim(self, *, source_id: str, claim: str) -> bool:
        source = self._sources[source_id]
        normalized_claim = _normalize(claim)
        for supported in source.supported_claims:
            if _semantic_overlap(normalized_claim, _normalize(supported)):
                return True
        for fact in source.facts_extracted:
            if _semantic_overlap(normalized_claim, _normalize(fact.claim)):
                return True
        return False


def parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _facts_from_supported_claims(source: CitationLikeSource) -> list[EvidenceFact]:
    facts: list[EvidenceFact] = []
    for index, claim in enumerate(source.supported_claims):
        facts.append(
            EvidenceFact(
                fact_id=f"{source.source_id}_claim_{index + 1}",
                claim=claim,
                fact_type=source.source_type,
                as_of_date=source.published_date,
            )
        )
    return facts


def _normalize(value: str) -> str:
    return " ".join(str(value).lower().replace("-", " ").replace("/", " ").split())


def _semantic_overlap(left: str, right: str) -> bool:
    if not left or not right:
        return False
    if left in right or right in left:
        return True
    left_terms = {term for term in left.split() if len(term) > 3}
    right_terms = {term for term in right.split() if len(term) > 3}
    if not left_terms or not right_terms:
        return False
    return len(left_terms & right_terms) >= min(2, len(left_terms), len(right_terms))

