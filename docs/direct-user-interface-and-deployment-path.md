# Direct User Interface and Deployment Path

Date: 2026-05-03

## Current Direct Access

Codex is currently used as the development orchestrator for this workspace. It
is not the production interface.

The project can be used directly through:

- `TradingAgents` interactive CLI for direct multi-agent TradingAgents runs.
- `scripts\run_tradingagents_baseline.py` for non-interactive baseline runs.
- `scripts\build_stage*.py` for Titan evidence packets, graph generation,
  horizon validation, and report rendering.
- Stage 5 v2 HTML/Markdown/PDF files for report consumption.

The documented business-user operating path is PowerShell plus `uv run python`
commands from `D:\Projects\CodeX\TradingAgents_Integration`. The upstream
`TradingAgents\` clone owns the active Python dependency environment through
`uv`. Docker remains available through the upstream project for containerized
baseline operation, but the wrapper's Stage 0A through Stage 5 manual currently
standardizes on the `uv` command path.

## Current Request Path

The current non-interactive path is:

1. User or operator invokes a CLI/script with ticker, trade date, provider, and
   model arguments.
2. TradingAgents routes prompts and tool calls through the configured LLM
   provider.
3. For DeepSeek runs, the configured provider sends model calls to DeepSeek.
4. Titan scripts consume the baseline artifact and generate validation packets,
   evidence graph artifacts, horizon validation, and final reports.

## API Status

No committed HTTP API service or web application endpoint exists in the wrapper
at this stage. A production deployment can expose the same workflow through an
API or UI later, but that is a distinct productization layer.

Recommended future API boundary:

- `POST /research-runs` to submit ticker, date, asset class, input folder, LLM
  provider, and model.
- `GET /research-runs/{run_id}` for status and artifact links.
- `GET /research-runs/{run_id}/report` for final HTML/PDF/Markdown artifacts.
- `GET /research-runs/{run_id}/graph` for graph JSON/HTML artifacts.

The API should call the same generic pipeline scripts/modules used by the CLI so
that CLI and API behavior remain identical.

The first production API should be a thin orchestration layer, not a second
research implementation. It should submit the same asset request, input folder,
provider, model, and run-id parameters used by the CLI, then expose the generated
packet, graph, report, and log artifact locations.

## Deployment Principle

Direct user access should not depend on Codex. Codex may help develop, audit,
or repair the project, but production users should interact through a documented
CLI, API, or web UI that invokes the same pipeline deterministically.
