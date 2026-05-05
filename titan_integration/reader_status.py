"""Reader-facing status translations for institutional reports."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReaderStatus:
    internal: str
    label: str
    summary: str
    tone: str


_STATUSES = {
    "Validated": ReaderStatus(
        internal="Validated",
        label="Fully Supported by Required Evidence",
        summary="The required evidence blocks are present, cross-checked, and aligned for this claim or horizon.",
        tone="positive",
    ),
    "Supported": ReaderStatus(
        internal="Supported",
        label="Supported by Available Evidence",
        summary="The claim is backed by the cited evidence available in this research cycle.",
        tone="positive",
    ),
    "Conditional Candidate": ReaderStatus(
        internal="Conditional Candidate",
        label="High-Quality Candidate Requiring Confirmation",
        summary="The setup is strong enough to monitor, but final validation depends on specific confirmation evidence.",
        tone="watch",
    ),
    "Conditional": ReaderStatus(
        internal="Conditional",
        label="Supported, but Awaiting Specific Confirmation",
        summary="The evidence is useful and directionally relevant, but one or more required confirmation blocks remain open.",
        tone="watch",
    ),
    "Not Validated": ReaderStatus(
        internal="Not Validated",
        label="Not Yet Fully Supported for This Horizon",
        summary="The available evidence does not yet satisfy the full standard required for this claim or horizon.",
        tone="caution",
    ),
    "Blocked": ReaderStatus(
        internal="Blocked",
        label="Specific Claim Not Accepted Due to Evidence Conflict or Missing Input",
        summary="A specific point estimate or claim cannot be accepted because the evidence is conflicting, incomplete, proxy-only, or missing a required input.",
        tone="blocked",
    ),
    "Contradictory": ReaderStatus(
        internal="Contradictory",
        label="Evidence Conflict Preserved",
        summary="Available sources conflict with the claim, so the report preserves the disagreement instead of forcing a conclusion.",
        tone="blocked",
    ),
    "Usable Range - Assumption-Based": ReaderStatus(
        internal="Usable Range - Assumption-Based",
        label="Usable Scenario Range With Explicit Assumptions",
        summary="The range may be used for scenario framing because assumptions are explicit and independently sourced scenarios reasonably cluster.",
        tone="watch",
    ),
    "Not Titan-Compliant": ReaderStatus(
        internal="Not Titan-Compliant",
        label="Evidence-Gated, With Open Validation Items",
        summary="The report is usable as evidence-gated research, but it intentionally preserves open validation items and does not claim final full-framework validation.",
        tone="watch",
    ),
}


def reader_status(value: str | None) -> ReaderStatus:
    if not value:
        return ReaderStatus(
            internal="Unknown",
            label="Status Not Specified",
            summary="No explicit evidence status was provided for this item.",
            tone="neutral",
        )
    return _STATUSES.get(
        value,
        ReaderStatus(
            internal=value,
            label=value,
            summary="This status is carried from the evidence system; review the surrounding rationale and citations for context.",
            tone="neutral",
        ),
    )
