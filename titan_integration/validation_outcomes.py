"""Core validation outcome taxonomy used across Titan research stages."""

from __future__ import annotations


VALIDATED = "Validated"
CONDITIONAL = "Conditional"
CONDITIONAL_CANDIDATE = "Conditional Candidate"
NOT_VALIDATED = "Not Validated"
BLOCKED = "Blocked"
USABLE_RANGE_ASSUMPTION_BASED = "Usable Range - Assumption-Based"


OUTCOME_DEFINITIONS = {
    VALIDATED: "All mandatory evidence blocks are collected, cross-verified, contextually aligned, and audit-passed.",
    CONDITIONAL: "Evidence is materially useful but one or more required confirmation blocks remain incomplete or conditional.",
    CONDITIONAL_CANDIDATE: "Pre-validation evidence supports monitoring or further research, but final validation depends on future/session-specific confirmation.",
    NOT_VALIDATED: "The required evidence stack for this horizon or claim is not sufficiently present or aligned.",
    BLOCKED: "A specific claim cannot be accepted because evidence is contradictory, unsourced, proxy-only, or fails Titan criteria.",
    USABLE_RANGE_ASSUMPTION_BASED: "A metric range is usable when assumptions are explicit and independently sourced scenarios reasonably cluster, even if a specific point estimate remains blocked.",
}


def is_conditional_family(status: str | None) -> bool:
    return status in {CONDITIONAL, CONDITIONAL_CANDIDATE, USABLE_RANGE_ASSUMPTION_BASED}


def is_blocking_status(status: str | None) -> bool:
    return status in {BLOCKED, NOT_VALIDATED, "Contradictory", "Computed - Source Conflict Preserved", "Not Computable - Missing Explicit Input"}
