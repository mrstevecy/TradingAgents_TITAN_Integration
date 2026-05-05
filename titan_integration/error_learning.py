"""Persistent error-learning records for repeated equity research failures."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from .equity_evidence import utc_now_iso


@dataclass(frozen=True)
class AgentErrorRecord:
    run_id: str
    ticker: str
    agent: str
    error_type: str
    severity: str
    exact_error: str
    correction_rule: str
    recurrence: bool
    status: str
    created_at: str
    evidence_dependency: str | None = None


class ErrorLearningStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> list[AgentErrorRecord]:
        if not self.path.exists():
            return []
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        return [AgentErrorRecord(**item) for item in payload.get("records", [])]

    def append(self, record: AgentErrorRecord) -> None:
        records = self.load()
        if any(
            item.run_id == record.run_id
            and item.ticker == record.ticker
            and _agent_key(item.agent) == _agent_key(record.agent)
            and item.error_type == record.error_type
            and item.exact_error == record.exact_error
            for item in records
        ):
            return
        recurrence = any(
            _agent_key(item.agent) == _agent_key(record.agent)
            and item.error_type == record.error_type
            and item.evidence_dependency == record.evidence_dependency
            for item in records
        )
        final_record = AgentErrorRecord(
            **{
                **asdict(record),
                "recurrence": recurrence or record.recurrence,
                "severity": _escalate(record.severity) if recurrence else record.severity,
            }
        )
        records.append(final_record)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps({"records": [asdict(item) for item in records]}, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def prior_context(self, ticker: str) -> str:
        ticker = ticker.upper()
        all_records = self.load()
        ticker_records = [item for item in all_records if item.ticker == ticker]
        recurring_records = [
            item
            for item in all_records
            if item.ticker != ticker and (item.recurrence or item.severity.upper() in {"HIGH", "CRITICAL"})
        ]
        records = (ticker_records + recurring_records)[-15:]
        if not records:
            return "No prior error-learning records for this ticker."
        lines = ["Prior error-learning records:"]
        for item in records[-10:]:
            scope = "same ticker" if item.ticker == ticker else f"global prior from {item.ticker}"
            dependency = f" / dependency={item.evidence_dependency}" if item.evidence_dependency else ""
            lines.append(f"- {item.agent} / {item.error_type}{dependency} / {item.severity} / {scope}: {item.correction_rule}")
        return "\n".join(lines)

    def prior_context_for_agent(self, ticker: str, agent: str) -> str:
        ticker = ticker.upper()
        agent_key = _agent_key(agent)
        all_records = [
            item
            for item in self.load()
            if _agent_key(item.agent) == agent_key or _agent_key(item.agent) in _DECISION_AGENT_KEYS
        ]
        ticker_records = [item for item in all_records if item.ticker == ticker]
        recurring_records = [
            item
            for item in all_records
            if item.ticker != ticker and (item.recurrence or item.severity.upper() in {"HIGH", "CRITICAL"})
        ]
        records = (ticker_records + recurring_records)[-12:]
        if not records:
            return f"No prior role-specific error-learning records for {agent}."
        lines = [f"Role-specific operational learning for {agent}:"]
        for item in records[-8:]:
            scope = "same ticker" if item.ticker == ticker else f"global prior from {item.ticker}"
            dependency = f"; evidence dependency: {item.evidence_dependency}" if item.evidence_dependency else ""
            recurrence = "; recurring pattern" if item.recurrence else ""
            lines.append(
                f"- {item.error_type} ({item.severity}, {scope}{recurrence}{dependency}): "
                f"{item.correction_rule} Exact prior failure: {item.exact_error}"
            )
        return "\n".join(lines)


def make_error_record(
    *,
    run_id: str,
    ticker: str,
    agent: str,
    error_type: str,
    severity: str,
    exact_error: str,
    correction_rule: str,
    status: str = "open",
    evidence_dependency: str | None = None,
) -> AgentErrorRecord:
    return AgentErrorRecord(
        run_id=run_id,
        ticker=ticker.upper(),
        agent=agent,
        error_type=error_type,
        severity=severity,
        exact_error=exact_error,
        correction_rule=correction_rule,
        recurrence=False,
        status=status,
        created_at=utc_now_iso(),
        evidence_dependency=evidence_dependency,
    )


def _escalate(severity: str) -> str:
    order = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    upper = severity.upper()
    if upper not in order:
        return severity
    return order[min(order.index(upper) + 1, len(order) - 1)]


_AGENT_ALIASES = {
    "market analyst": "market",
    "technical analyst": "market",
    "news analyst": "news",
    "news and catalyst analyst": "news",
    "fundamentals analyst": "fundamentals",
    "fundamental analyst": "fundamentals",
    "social analyst": "sentiment",
    "sentiment analyst": "sentiment",
    "social/sentiment analyst": "sentiment",
    "social media analyst": "sentiment",
    "bull analyst": "bull",
    "bull researcher": "bull",
    "bear analyst": "bear",
    "bear researcher": "bear",
    "research manager": "research_manager",
    "trader": "trader",
    "portfolio manager": "portfolio_manager",
    "aggressive analyst": "aggressive_risk",
    "aggressive risk analyst": "aggressive_risk",
    "conservative analyst": "conservative_risk",
    "conservative risk analyst": "conservative_risk",
    "neutral analyst": "neutral_risk",
    "neutral risk analyst": "neutral_risk",
}

_DECISION_AGENT_KEYS = {"research_manager", "trader", "portfolio_manager"}


def _agent_key(agent: str) -> str:
    normalized = " ".join(agent.replace("/", " / ").lower().split()).replace(" / ", "/")
    return _AGENT_ALIASES.get(normalized, normalized)
