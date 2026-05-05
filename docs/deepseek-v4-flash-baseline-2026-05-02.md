# DeepSeek V4 Flash Baseline Test

Date: 2026-05-02  
Purpose: validate a low-cost hosted model baseline before adding Titan wrapper context.

## Configuration

Provider:

- `deepseek`

Models:

- `quick_think_llm`: `deepseek-v4-flash`
- `deep_think_llm`: `deepseek-v4-flash`

TradingAgents scope:

- `selected_analysts=["market"]`

Ticker/date:

- `NVDA`
- `2026-05-01`

Runtime paths:

- Results/cache/memory were routed to `/tmp/tradingagents/...` to avoid Docker volume permission issues seen earlier.

## Connectivity Check

A minimal direct invocation succeeded:

- Prompt expected exact output: `deepseek v4 flash ok`
- Model returned the expected response.

## Graph Result

The market-only TradingAgents graph completed successfully.

Final decision:

- `Hold`

This is the first tested backend that completed the clean upstream market-only graph without hitting LangGraph recursion limits.

## Compatibility Patch

After the first successful baseline, DeepSeek emitted API-level structured-output warnings:

- DeepSeek rejected LangChain's forced `tool_choice` path for structured output.
- TradingAgents then retried those steps as free text and completed.

Patch applied:

- `tradingagents/llm_clients/openai_client.py`
- `tests/test_deepseek_reasoning.py`

The DeepSeek client now raises `NotImplementedError` for `with_structured_output` across current DeepSeek models. This routes Research Manager, Trader, and Portfolio Manager directly to TradingAgents' existing free-text fallback instead of first causing a DeepSeek API 400 error.

Post-patch verification:

- Docker image rebuilt successfully.
- Focused smoke test confirmed `deepseek-reasoner`, `deepseek-v4-flash`, and `deepseek-v4-pro` all raise the intended structured-output fallback signal.
- Market-only NVDA run completed again.
- Final decision remained `Hold`.
- The previous DeepSeek API 400 `tool_choice` warnings did not recur.

## Observed Behavior

Positive:

- API authentication worked through `TradingAgents\.env`.
- Docker container received the key through the compose `env_file`.
- Tool calls executed correctly.
- The model retrieved stock data and a compact indicator set.
- The graph reached a final portfolio decision.
- After the compatibility patch, DeepSeek avoids the rejected structured-output API path.

Expected local notices:

- Research Manager, Trader, and Portfolio Manager report that DeepSeek does not support `with_structured_output` through the current binding.
- These are compatibility guard notices, not API failures.
- The fallback path completed successfully.

## Baseline Output Summary

The model produced a market-only NVDA technical read:

- Near-term momentum weakening after a sharp pullback.
- Long-term trend still intact above major moving averages.
- Elevated volatility and high-volume distribution risk.
- Final stance: `Hold`.

## Assessment

DeepSeek V4 Flash is currently the best validated baseline candidate for the next clean TradingAgents run.

It performed better than local LM Studio models for the specific blocker we observed: clean graph termination.

Follow-up fuller baseline:

- A four-analyst clean run was completed with `market`, `news`, `fundamentals`, and `social`.
- The final processed decision was again `Hold`.
- Artifacts were saved under `outputs\deepseek_full_baseline`.
- See `docs\full-deepseek-baseline-2026-05-02.md`.

Do not add Titan OS / DTP / Activation Trigger / Graphify injection yet. The next step should be:

1. Evaluate clean baseline quality against Titan requirements.
2. Implement the first thin wrapper module only after that assessment is documented.

## Security Note

The DeepSeek API key was provided in chat and configured locally. Rotate the key after testing is complete.
