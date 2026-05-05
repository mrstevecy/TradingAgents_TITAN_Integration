# Backend Options Assessment

Date: 2026-05-02

## Purpose

Clarify whether the baseline TradingAgents run should use Codex, direct API keys, local models, or a hybrid inference configuration.

## Codex as Inference Backend

Assessment: not suitable as a direct drop-in inference endpoint for TradingAgents.

Reasoning:

- Codex is available to us as an engineering/research orchestration environment.
- TradingAgents requires an LLM endpoint callable by its LangChain clients.
- Current Codex access does not expose a stable local OpenAI-compatible `/v1/chat/completions` or Responses API endpoint for arbitrary Docker containers.
- Official Codex CLI documentation describes Codex as a local coding agent that authenticates to API-backed models, not as a model server for other applications.
- Codex can supervise, edit, test, and document the integration, but it should not be treated as the runtime LLM backend for TradingAgents.

Conclusion:

- Use Codex as the orchestrator and implementation assistant.
- Do not route TradingAgents inference through Codex directly.

## Direct API Keys

Assessment: best baseline for research-grade output quality.

Pros:

- Highest expected instruction-following quality.
- Best compatibility with TradingAgents structured-output agents.
- Most stable path for the clean upstream baseline.
- Easier to compare against the repository's intended configuration.

Cons:

- Requires API key management.
- Token cost can be material because each ticker triggers multiple agent and debate calls.

Recommended use:

- Use for the first controlled baseline if the objective is quality assessment.
- Keep yfinance-only data for the first run unless Alpha Vantage is intentionally configured.

## Ollama

Detected:

- Runtime present and listening on port `11434`.
- Docker container can reach host Ollama via `http://host.docker.internal:11434`.

Installed models:

- `llama3.2:3b`
  - 3.2B, Q4_K_M, local.
  - Not research-grade for this multi-agent workflow.
- `deepseek-v3.1:671b-cloud`
  - Cloud remote through Ollama.
  - Large model, but not a purely local inference path.
- `bge-m3:latest`
  - Embedding model, not a chat/reasoning backend.

Assessment:

- Current local Ollama list is not ideal for the first baseline.
- `llama3.2:3b` is too small for institutional research synthesis.
- `deepseek-v3.1:671b-cloud` may be capable but is remote/cloud-backed and should be treated separately from local inference.

## LM Studio

Detected:

- LM Studio is running.
- OpenAI-compatible endpoint listening at `127.0.0.1:1234`.
- Docker container can reach it via `http://host.docker.internal:1234/v1`.

Available models:

- `qwen3-omni-30b-a3b-thinking`
  - F16, 65,536 context, tool-use capable, not loaded.
- `qwen/qwen3-coder-next`
  - Q4_K_M, 262,144 context, tool-use capable, not loaded.
- `meta/llama-3.3-70b`
  - Q4_K_M, 131,072 context, tool-use capable, not loaded.
- `deepseek-r1-distill-llama-8b`
  - Q4_K_M, 131,072 context, not loaded.
- `dolphin3.0-llama3.1-8b`
  - Q4_K_M, 131,072 context, not loaded.
- `openai/gpt-oss-20b`
  - MXFP4, 131,072 context, tool-use capable, not loaded.
- `text-embedding-nomic-embed-text-v1.5`
  - embedding model.

Assessment:

- Best local candidates are `meta/llama-3.3-70b`, `qwen/qwen3-coder-next`, and `openai/gpt-oss-20b`.
- LM Studio is likely the best local route because it exposes an OpenAI-compatible `/v1` endpoint.
- Structured output and tool-calling behavior must be tested before using it for baseline quality assessment.

## Recommended Backend Path

1. First baseline quality run:
   - Use direct OpenAI API if available.
   - Purpose: establish a high-quality upstream reference output.

2. Local model compatibility run:
   - Use LM Studio after baseline.
   - Start with `meta/llama-3.3-70b` or `qwen/qwen3-coder-next`.
   - Configure TradingAgents as OpenAI-compatible or Ollama-style endpoint depending on client behavior.

3. Hybrid operating model:
   - API-backed model for final research-grade reports.
   - Local model for low-cost experimentation, prompt testing, wrapper development, and non-final drafts.

## Current Recommendation

Do not use Codex as the TradingAgents inference backend.

Preferred sequence:

1. Direct API baseline for quality.
2. LM Studio local compatibility test.
3. Compare output quality and latency.
4. Decide whether local models can support draft-only, partial, or final research workloads.
