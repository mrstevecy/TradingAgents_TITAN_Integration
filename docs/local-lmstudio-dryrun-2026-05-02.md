# Local LM Studio Dry Run

Date: 2026-05-02  
Objective: validate local LM Studio inference with the clean upstream TradingAgents graph before adding Titan wrapper context.

## Endpoint Validation

LM Studio endpoint:

- Host: `http://127.0.0.1:1234/v1`
- Docker route: `http://host.docker.internal:1234/v1`

Result:

- `openai/gpt-oss-20b` successfully answered a direct `/v1/chat/completions` request.
- Response was correct: `local inference ok`.
- This confirms LM Studio, model serving, Docker-to-host routing, and OpenAI-compatible chat completion basics are working.

## TradingAgents Configuration Used

The run used TradingAgents' existing OpenAI-compatible `ollama` provider with an explicit LM Studio `backend_url`.

```python
config.update({
    "results_dir": "/tmp/tradingagents/logs",
    "data_cache_dir": "/tmp/tradingagents/cache",
    "memory_log_path": "/tmp/tradingagents/memory/trading_memory.md",
    "llm_provider": "ollama",
    "backend_url": "http://host.docker.internal:1234/v1",
    "quick_think_llm": "<local model>",
    "deep_think_llm": "<local model>",
    "max_debate_rounds": 1,
    "max_risk_discuss_rounds": 1,
    "max_recur_limit": 60,
    "output_language": "English",
})
```

Selected analyst scope:

- `selected_analysts=["market"]`

Ticker/date:

- `NVDA`
- `2026-05-01`

## Attempt 1: `openai/gpt-oss-20b`

Outcome:

- Docker launched.
- TradingAgents graph initialized.
- LM Studio model was reached successfully.
- The market analyst called `get_stock_data` repeatedly.
- Data retrieval worked through yfinance.
- The graph did not reach a final answer.
- LangGraph stopped with `GraphRecursionError: Recursion limit of 100 reached without hitting a stop condition`.

Interpretation:

- Basic local inference works.
- Tool calling works.
- Market data tools work.
- The model did not manage the tool loop correctly under the upstream agent prompt.
- `openai/gpt-oss-20b` is not yet suitable as the default local TradingAgents runtime without additional prompt/tool-loop constraints.

## Attempt 2: `qwen/qwen3-coder-next`

Outcome:

- Docker launched.
- TradingAgents graph initialized.
- LM Studio model was reached successfully.
- The model retrieved stock data and moved into technical indicators.
- It called `get_indicators` for SMA, EMA, RSI, MACD, MACD signal, and MACD histogram.
- It repeated several indicator calls.
- The graph again stopped with `GraphRecursionError: Recursion limit of 100 reached without hitting a stop condition`.

Interpretation:

- `qwen/qwen3-coder-next` showed better agent progression than `gpt-oss-20b`.
- It still did not terminate reliably under the current upstream graph.
- The failure mode is tool-loop control, not endpoint availability, Docker networking, or market data retrieval.

## Attempt 3: `meta/llama-3.3-70b`

Endpoint check:

- Direct `/v1/chat/completions` call succeeded.
- Model loaded in LM Studio.
- Response was correct: `llama 70b local ok`.
- First small call took about one minute, likely due to model load time.

TradingAgents market-only run:

- Started with the same clean upstream configuration.
- Did not complete within the 15-minute guardrail.
- The container was still running and was manually stopped.

Interpretation:

- The model is loadable on this hardware.
- It may be usable for standalone local reasoning or summarization.
- It is not currently practical as the first upstream TradingAgents runtime without either longer run windows, performance tuning, or wrapper-level controls.

## Attempt 4: `qwen3-30b-a3b-instruct-2507`

Reason for test:

- User requested this specific model before moving to API baseline.
- Qwen's model card describes Qwen3-30B-A3B-Instruct-2507 as a 30.5B total / 3.3B active MoE model with 262,144 native context and improved instruction following, logical reasoning, coding, and tool usage.
- The model supports non-thinking mode only, which is desirable for cleaner tool-loop behavior.

Download:

- Source: `lmstudio-community/Qwen3-30B-A3B-Instruct-2507-GGUF`
- Quantization selected by LM Studio CLI: `Q4_K_M`
- Size: 18.56 GB
- Local model ID: `qwen3-30b-a3b-instruct-2507`
- Local file: `C:\Users\Steve\.lmstudio\models\lmstudio-community\Qwen3-30B-A3B-Instruct-2507-GGUF\Qwen3-30B-A3B-Instruct-2507-Q4_K_M.gguf`

Endpoint check:

- Direct `/v1/chat/completions` call succeeded.
- Response was correct: `qwen 30b local ok`.
- Direct response was materially faster than the first `meta/llama-3.3-70b` endpoint check.

TradingAgents market-only run:

- Started with the same clean upstream configuration.
- Retrieved one year of NVDA stock data.
- Retrieved multiple indicators including 50 SMA, 200 SMA, 10 EMA, MACD, MACD signal, MACD histogram, RSI, and Bollinger bands.
- Repeated several indicator calls.
- Stopped with `GraphRecursionError: Recursion limit of 100 reached without hitting a stop condition`.

Interpretation:

- This was the best local candidate tested so far in terms of endpoint speed and useful progression through the market analyst workflow.
- It still did not terminate reliably under the clean upstream TradingAgents graph.
- The limiting issue remains agent/tool-loop control in the upstream graph when served by local GGUF models.

## Current Technical Assessment

Local LM Studio can serve the project, but the clean upstream TradingAgents graph is not yet reliable with the tested local models. `openai/gpt-oss-20b`, `qwen/qwen3-coder-next`, and `qwen3-30b-a3b-instruct-2507` entered repeated tool-call loops; `meta/llama-3.3-70b` loaded successfully but did not complete the market-only graph within the 15-minute guardrail.

This supports the hybrid architecture:

- Local models remain useful for endpoint validation, draft analysis, summarization, and non-tool-loop tasks.
- For the first clean full TradingAgents baseline, a hosted model with stronger function-calling discipline is likely needed unless we add a small wrapper guard around tool calls.
- Titan prompt/context injection should still wait until a clean baseline can complete.

## Recommended Next Step

Updated after hosted baseline test:

- DeepSeek V4 Flash was tested through the clean upstream TradingAgents graph.
- The market-only NVDA run completed and returned `Hold`.
- This confirms the next baseline path should use hosted DeepSeek before adding Titan injection.

Original local-only recommendations:

1. Add a thin wrapper-level guard for local-only experiments that caps repeated identical tool calls and forces synthesis after sufficient data is collected, while keeping upstream internals clean.
2. Or test a hosted API model through existing provider support, preferably Gemini, DeepSeek V4 Flash/Pro, OpenAI, or another provider with strong tool/function behavior.
3. Revisit local 70B only after measuring LM Studio generation speed and context settings outside the graph.

## Important Note

These failed dry runs do not invalidate the integration. They establish that local model compatibility requires more than an OpenAI-compatible endpoint: the model must also follow the agent graph's stop conditions and avoid redundant tool calls.
