"""Run a non-interactive TradingAgents baseline and write a summary artifact."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TRADINGAGENTS_ROOT = ROOT / "TradingAgents"
sys.path.insert(0, str(TRADINGAGENTS_ROOT))
sys.path.insert(0, str(ROOT))

from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.graph.trading_graph import TradingAgentsGraph
from titan_integration.equity_evidence import run_equity_data_scan, save_evidence_store
from titan_integration.error_learning import ErrorLearningStore


def main() -> int:
    _load_env_file(TRADINGAGENTS_ROOT / ".env")

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ticker", default="NVDA")
    parser.add_argument("--trade-date", default="2026-05-02")
    parser.add_argument("--provider", default="deepseek")
    parser.add_argument("--model", default="deepseek-v4-flash")
    parser.add_argument(
        "--analysts",
        nargs="+",
        default=["market", "news", "fundamentals", "social"],
        choices=["market", "news", "fundamentals", "social"],
    )
    parser.add_argument("--max-debate-rounds", type=int, default=5)
    parser.add_argument("--max-risk-discuss-rounds", type=int, default=1)
    parser.add_argument("--max-recur-limit", type=int, default=100)
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=ROOT / "outputs" / "deepseek_fresh_baseline",
    )
    args = parser.parse_args()

    run_dir = args.out_dir
    logs_dir = run_dir / "runtime_logs"
    cache_dir = run_dir / "cache"
    memory_path = run_dir / "memory" / "trading_memory.md"
    memory_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_store = run_equity_data_scan(args.ticker, args.trade_date)
    evidence_path = run_dir / f"{args.ticker.upper()}_{args.trade_date}_mandatory_equity_evidence_store.json"
    tool_evidence_path = run_dir / f"{args.ticker.upper()}_{args.trade_date}_upstream_tool_evidence.jsonl"
    if tool_evidence_path.exists():
        tool_evidence_path.unlink()
    os.environ["TRADINGAGENTS_TOOL_EVIDENCE_PATH"] = str(tool_evidence_path)
    save_evidence_store(evidence_store, evidence_path)
    learning_store = ErrorLearningStore(ROOT / "research_packets" / "error_learning" / "agent_error_records.json")
    common_evidence_context = evidence_store.agent_context() + "\n\n" + evidence_store.do_not_claim_context()
    role_contexts = _build_role_error_contexts(learning_store, args.ticker)

    config = DEFAULT_CONFIG.copy()
    config.update(
        {
            "results_dir": str(logs_dir),
            "data_cache_dir": str(cache_dir),
            "memory_log_path": str(memory_path),
            "llm_provider": args.provider,
            "quick_think_llm": args.model,
            "deep_think_llm": args.model,
            "backend_url": None,
            "max_debate_rounds": args.max_debate_rounds,
            "max_risk_discuss_rounds": args.max_risk_discuss_rounds,
            "max_recur_limit": args.max_recur_limit,
            "checkpoint_enabled": False,
            "mandatory_evidence_context": common_evidence_context + "\n\n" + learning_store.prior_context(args.ticker),
            "mandatory_evidence_context_by_agent": role_contexts,
            "mandatory_evidence_store_path": str(evidence_path),
            "upstream_tool_evidence_path": str(tool_evidence_path),
        }
    )

    graph = TradingAgentsGraph(
        selected_analysts=args.analysts,
        debug=False,
        config=config,
    )
    final_state, processed_decision = graph.propagate(args.ticker, args.trade_date)
    debate_count = final_state.get("investment_debate_state", {}).get("count", 0)
    if debate_count < 2 * 5:
        raise RuntimeError(
            f"Bull/Bear debate hard gate failed: expected at least 5 rounds/10 contributions, got {debate_count}."
        )
    summary = _build_summary(args, config, final_state, processed_decision, evidence_store.to_dict())

    run_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{args.ticker.upper()}_{args.trade_date}_{args.provider}_fresh_baseline_summary"
    json_path = run_dir / f"{stem}.json"
    md_path = run_dir / f"{stem}.md"
    json_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(_to_markdown(summary), encoding="utf-8")

    print(f"JSON: {json_path}")
    print(f"Markdown: {md_path}")
    print(f"Processed decision: {processed_decision}")
    return 0


def _build_summary(
    args: argparse.Namespace,
    config: dict[str, Any],
    final_state: dict[str, Any],
    processed_decision: str,
    mandatory_equity_data_scan: dict[str, Any],
) -> dict[str, Any]:
    return {
        "ticker": args.ticker.upper(),
        "trade_date": args.trade_date,
        "provider": args.provider,
        "quick_think_llm": config["quick_think_llm"],
        "deep_think_llm": config["deep_think_llm"],
        "selected_analysts": args.analysts,
        "processed_decision": processed_decision,
        "mandatory_equity_data_scan": mandatory_equity_data_scan,
        "mandatory_evidence_store_path": config.get("mandatory_evidence_store_path"),
        "upstream_tool_evidence_path": config.get("upstream_tool_evidence_path"),
        "debate_validation": {
            "min_rounds_required": 5,
            "contribution_count": final_state.get("investment_debate_state", {}).get("count", 0),
            "status": "passed"
            if final_state.get("investment_debate_state", {}).get("count", 0) >= 10
            else "failed",
        },
        "final_trade_decision": final_state.get("final_trade_decision"),
        "market_report": final_state.get("market_report"),
        "news_report": final_state.get("news_report"),
        "fundamentals_report": final_state.get("fundamentals_report"),
        "sentiment_report": final_state.get("sentiment_report"),
        "trader_investment_plan": final_state.get("trader_investment_plan"),
        "investment_plan": final_state.get("investment_plan"),
        "investment_debate_state": final_state.get("investment_debate_state"),
        "risk_debate_state": final_state.get("risk_debate_state"),
    }


def _build_role_error_contexts(store: ErrorLearningStore, ticker: str) -> dict[str, str]:
    roles = [
        "Market Analyst",
        "News Analyst",
        "Fundamentals Analyst",
        "Social/Sentiment Analyst",
        "Bull Researcher",
        "Bear Researcher",
        "Research Manager",
        "Trader",
        "Portfolio Manager",
        "Aggressive Risk Analyst",
        "Conservative Risk Analyst",
        "Neutral Risk Analyst",
    ]
    return {role: store.prior_context_for_agent(ticker, role) for role in roles}


def _to_markdown(summary: dict[str, Any]) -> str:
    lines = [
        f"# TradingAgents Fresh Baseline: {summary['ticker']} {summary['trade_date']}",
        "",
        f"- Provider: {summary['provider']}",
        f"- Quick model: {summary['quick_think_llm']}",
        f"- Deep model: {summary['deep_think_llm']}",
        f"- Analysts: {', '.join(summary['selected_analysts'])}",
        f"- Processed decision: {summary['processed_decision']}",
        "",
        "## Final Trade Decision",
        "",
        summary.get("final_trade_decision") or "",
        "",
    ]
    for key, title in [
        ("market_report", "Market Report"),
        ("news_report", "News Report"),
        ("fundamentals_report", "Fundamentals Report"),
        ("sentiment_report", "Sentiment Report"),
        ("investment_plan", "Investment Plan"),
        ("trader_investment_plan", "Trader Investment Plan"),
    ]:
        value = summary.get(key)
        if value:
            lines.extend([f"## {title}", "", value, ""])
    return "\n".join(lines).rstrip() + "\n"


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


if __name__ == "__main__":
    raise SystemExit(main())
