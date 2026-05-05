# Baseline Runbook

Date: 2026-05-02

## Objective

Run one clean upstream TradingAgents baseline analysis before adding Titan prompt injection or validation wrappers.

## Current State

- Docker image built successfully.
- Container import smoke test passed.
- `.env` exists with placeholder keys only.
- No LLM provider key is currently configured.

## Recommended First Ticker

Use one of:

- `NVDA` - broad AI/semi relevance, high liquidity, frequent analyst/news flow.
- `MU` - directly relevant to prior Titan research artifacts in this workspace.

Recommended first baseline: `NVDA`.

## Recommended First Date

Use a recent completed market date for stable data retrieval and post-run review.

Recommended first baseline date: `2026-05-01`.

## Baseline Command Pattern

The upstream CLI is interactive. For a controlled baseline, use Docker and the CLI:

```powershell
docker compose run --rm tradingagents analyze --checkpoint
```

Then select:

- Ticker: `NVDA`
- Date: `2026-05-01`
- Provider: selected configured provider
- Analysts: market, news, fundamentals, social
- Research depth: `1` for the first baseline

## Provider Configuration

Before the run, configure exactly one provider key in:

```text
D:\Projects\CodeX\TradingAgents_Integration\TradingAgents\.env
```

Keep unused keys blank.

## Output Handling

For the first baseline, preserve:

- CLI saved report.
- TradingAgents logs under the Docker volume.
- Any full-state JSON produced by the run.
- Message/tool log if generated.

After completion, create:

- `docs/baseline-assessment-YYYY-MM-DD.md`

The assessment must compare the raw TradingAgents output against Titan requirements without modifying the upstream output.
