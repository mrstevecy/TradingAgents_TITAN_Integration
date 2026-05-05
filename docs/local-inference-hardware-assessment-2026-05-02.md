# Local Inference and Hardware Assessment

Date: 2026-05-02  
Project: TradingAgents Integration  
Decision context: validate local inference before spending API tokens or running the official paid baseline.

## Executive Recommendation

Use LM Studio as the first local inference backend and keep Codex as the orchestration/development environment, not as the runtime LLM endpoint.

Recommended validation order:

1. `openai/gpt-oss-20b` in LM Studio for the first TradingAgents compatibility smoke test.
2. `qwen/qwen3-coder-next` if the first test passes technically but needs stronger tool-following or longer-context behavior.
3. `meta/llama-3.3-70b` only after measuring memory headroom and tokens/sec, because it is likely slower and memory-sensitive on this machine.
4. Escalate to direct API or a hybrid workflow if local output quality, determinism, or structured-tool behavior is below research-report standards.

The practical near-term decision is hybrid-ready local-first: local models for plumbing, exploration, and draft reasoning; paid or higher-quality API models for final institutional reports until local quality is proven.

## Hardware Inventory

Update from Windows System > About screenshot provided by user:

- Processor: AMD Ryzen AI MAX+ 395 w/ Radeon 8060S
- Installed RAM: 128 GB, 63.6 GB usable by Windows
- Graphics: AMD Radeon 8060S Graphics, 64 GB shown for graphics
- Storage: 5.50 TB total, 1.79 TB used

This supersedes the earlier WMI-only read that understated the full installed memory picture. The practical interpretation is a high-memory AMD unified-memory system: roughly 64 GB is available/allocated for graphics and roughly 64 GB remains usable by Windows. This materially improves local 70B feasibility, while still requiring benchmark validation because it is not a discrete NVIDIA CUDA workstation.

### CPU

- System: GMKtec NucBox_EVO-X2
- CPU: AMD Ryzen AI MAX+ 395 w/ Radeon 8060S
- Architecture: x64
- Cores / threads: 16 cores / 32 logical processors
- Reported max clock: 3.0 GHz
- Cache: 16 MB L2, 64 MB L3

Assessment: strong CPU for local inference support, but sustained long-context generation on CPU-heavy paths will be slower than a discrete high-VRAM GPU workstation.

### Memory

- Installed physical memory: 128 GB
- Windows usable memory: about 63.6 GB
- Graphics allocation shown by Windows: 64 GB for AMD Radeon 8060S Graphics
- Available Windows memory during inspection: about 10 GB
- Memory: high-speed LPDDR-class modules reported around 8000 MT/s effective configured speed

Assessment: this is stronger than a typical 64 GB local inference machine. 20B-32B quantized models should be comfortable. 70B Q4 is a realistic local candidate if LM Studio can use the AMD graphics allocation effectively. 120B MXFP4 may be technically testable in constrained form, but should not be assumed interactive or reliable for research workflows without benchmarking. Close other heavy applications before loading 70B+ models.

### GPU

- GPU: AMD Radeon 8060S integrated graphics
- Windows System > About reports 64 GB graphics memory.
- No NVIDIA GPU detected (`nvidia-smi` unavailable).
- LM Studio has local backends installed for ROCm, Vulkan, CPU, and CUDA, but this machine should be treated as AMD integrated/shared-memory rather than discrete CUDA.

Assessment: use Vulkan/ROCm acceleration where LM Studio supports it. The 64 GB graphics allocation makes 70B Q4 much more plausible than initially assessed, but it remains a unified-memory AMD path rather than a discrete CUDA path, so tokens/sec and stability must be measured.

### Storage

- C: 2 TB Phison NVMe, about 366 GB free
- D: 4 TB Lexar NQ790 NVMe, about 3.7 TB free
- Both drives are NVMe and healthy.

Assessment: storage is not a blocker. Use D: for model caches, research artifacts, and Docker volumes where possible.

### Thermal

- Windows ACPI thermal sensor query did not return reliable temperature readings.
- Because this is a compact mini-PC form factor, sustained 70B inference may throttle.

Required validation: measure LM Studio tokens/sec, CPU/GPU utilization, memory pressure, and fan/temperature behavior during a 15-30 minute controlled generation test before declaring any large model stable.

## Installed Model Inventory

### LM Studio

LM Studio is running and exposes an OpenAI-compatible endpoint at:

- Host: `http://127.0.0.1:1234/v1`
- Docker access: `http://host.docker.internal:1234/v1`

Installed models:

| Model | Type | Quantization | Context | Tool Use | Assessment |
|---|---:|---:|---:|---:|---|
| `openai/gpt-oss-20b` | LLM | MXFP4 | 131k | Yes | Best first local compatibility test. Reasonable fit for 64 GB memory; designed for local low-latency use. |
| `qwen/qwen3-coder-next` | LLM | Q4_K_M | 262k | Yes | Strong agent/tool candidate and long context, but likely slower and heavier. Use second. |
| `meta/llama-3.3-70b` | LLM | Q4_K_M | 131k | Yes | Strong open model, but heavy on this hardware. Benchmark before relying on it. |
| `qwen3-omni-30b-a3b-thinking` | LLM/VLM-oriented | F16 | 65k | Yes | Multimodal-capable family, but F16 is memory-heavy. Not needed for text-first TradingAgents. |
| `deepseek-r1-distill-llama-8b` | LLM | Q4_K_M | 131k | Not primary | Useful for quick smoke tests, below research-grade target. |
| `dolphin3.0-llama3.1-8b` | LLM | Q4_K_M | 131k | Not primary | Useful for quick smoke tests, below research-grade target. |
| `minicpm-v-2_6` | VLM | Q4_K_M | 32k | No | Image/VLM utility model, not relevant to text-first TradingAgents baseline. |
| `text-embedding-nomic-embed-text-v1.5` | Embedding | Q4_K_M | 2k | N/A | Useful for local retrieval experiments, not a chat model. |

### Ollama

Ollama is running at:

- Host: `http://127.0.0.1:11434`
- Docker access: `http://host.docker.internal:11434`

Installed models:

| Model | Type | Quantization | Assessment |
|---|---:|---:|---|
| `llama3.2:3b` | Local chat | Q4_K_M | Too small for TradingAgents research quality. Keep only for plumbing tests. |
| `deepseek-v3.1:671b-cloud` | Remote/cloud | FP8 remote | Not local. Treat as cloud dependency, not local validation. |
| `bge-m3:latest` | Embedding | F16 | Useful embedding model, not a chat model. |

Ollama should not be the first runtime for this project because the locally installed chat model is too small. LM Studio has better candidate models already installed.

## Model Update and Suitability Notes

- `openai/gpt-oss-20b`: current and highly relevant for local compatibility. Official OpenAI documentation describes it as a 21B-parameter open-weight model with 3.6B active parameters for low-latency local or specialized use. Hugging Face notes MXFP4 quantization and local use within about 16 GB memory. It is the right first test.
- `qwen/qwen3-coder-next`: current and relevant for tool/agent workflows. Hugging Face notes LM Studio support and 256k default context, with guidance to reduce context if the server fails to start. Good second test.
- `meta/llama-3.3-70b`: still a strong model, 128k context, text-only, released December 2024. It is not deprecated, but it is heavy for this hardware.
- `qwen3-omni-30b-a3b-thinking`: current multimodal family, but the installed F16 variant is not the right first choice for a text-first agent pipeline.
- `llama3.2:3b`: not deprecated in a strict sense, but sub-optimal for this research workflow.
- `bge-m3` and `nomic-embed-text-v1.5`: useful embeddings; neither is a candidate for final reasoning.

No installed model should be declared production-ready for Titan or TradingAgents research until it passes the controlled dry run and quality audit.

## Feasible Model Sizes

| Class | Feasibility | Notes |
|---|---:|---|
| 3B-8B Q4/Q5 | Easy | Fast, useful for smoke tests, insufficient for final research quality. |
| 20B MXFP4/Q4 | Strong | Best first interactive local range on this machine. |
| 30B Q4 | Strong | Likely feasible; F16 variants still require care. |
| 70B Q4 | Realistic but benchmark required | The 64 GB graphics allocation makes this plausible; validate tokens/sec, memory, and thermals. |
| 120B MXFP4/Q4 | Experimental | May be technically possible only with constrained context/offload; not recommended for first TradingAgents workflow. |
| 405B/671B | Not local | Cloud/remote only. |

## Cloud and Low-Cost Fallback Options

### Google Gemini API

Google's Gemini API pricing page currently lists free-tier access for several Gemini models, with paid per-token pricing available when moving beyond free-tier constraints. The models page describes Gemini 2.5 Flash as the price-performance model for low-latency reasoning and Gemini 2.5 Pro as the more advanced reasoning/coding model. Rate limits are tiered by project usage and spend.

Use case: best low-cost/free candidate for larger-context research experiments, but not the sole production baseline unless rate limits and data-use terms are acceptable.

### Groq

Groq currently lists fast hosted inference for models including Qwen3 32B 131k and Llama 3.3 70B Versatile 128k, with low per-token pricing and very high advertised throughput.

Use case: strong speed/cost fallback for open-weight models when local inference is too slow.

### OpenRouter

OpenRouter provides an OpenAI-compatible API and exposes free-model routing plus paid access to many models. It supports tool/function calling when the underlying model supports it.

Use case: useful for experiments and provider comparison. For production-grade research, pin explicit models/providers and monitor pricing/data-retention terms rather than relying on a generic free router.

### Direct Premium API Baseline

If the local model cannot maintain structured tool use, determinism, source handling, and final-report quality, use a direct premium API model for the official baseline. This is likely the most reliable path for final institutional reports, with local models retained for draft/exploratory work.

## Decision Path

1. Keep the upstream TradingAgents repository clean.
2. Configure a local LM Studio endpoint for Docker:
   - Base URL: `http://host.docker.internal:1234/v1`
   - First model: `openai/gpt-oss-20b`
3. Run a controlled single-symbol dry run using a liquid ticker such as NVDA or MU.
4. Evaluate:
   - whether LangChain/OpenAI-compatible calls work,
   - whether tool-like prompts are followed,
   - output coherence,
   - hallucination rate,
   - source discipline,
   - latency and stability,
   - memory and thermal behavior.
5. If technically successful but quality is weak, repeat with `qwen/qwen3-coder-next`.
6. If quality remains weak, move to hybrid:
   - local model for exploration and cheap intermediate reasoning,
   - direct API or selected hosted provider for final report generation and audit.
7. Only after the clean baseline is validated should Titan OS / DTP / Activation Trigger / Graphify context injection be added through the thin wrapper.

## Initial Model Recommendation

Primary local test model:

- `openai/gpt-oss-20b`

Reason:

- fits the hardware better than 70B,
- has tool-use-oriented local model support,
- has a large enough context window for early TradingAgents tests,
- has a lower risk of memory pressure,
- is already installed.

Secondary local test model:

- `qwen/qwen3-coder-next`

Reason:

- stronger agentic/tool-call orientation,
- very large context,
- already installed,
- likely better for code/tool discipline than general chat models.

Not recommended for first TradingAgents run:

- `llama3.2:3b`: too small,
- `qwen3-omni-30b-a3b-thinking` F16: too memory-heavy and multimodal capability is not needed yet,
- `meta/llama-3.3-70b`: strong but should follow a smaller compatibility test.

## Sources

- Google Gemini API pricing: https://ai.google.dev/gemini-api/docs/pricing
- Google Gemini API rate limits: https://ai.google.dev/gemini-api/docs/rate-limits
- Google Gemini model overview: https://ai.google.dev/gemini-api/docs/models
- Groq pricing: https://groq.com/pricing
- OpenRouter pricing and compatibility notes: https://openrouter.ai/pricing
- OpenAI `gpt-oss-20b` model documentation: https://developers.openai.com/api/docs/models/gpt-oss-20b
- `openai/gpt-oss-20b` Hugging Face model card: https://huggingface.co/openai/gpt-oss-20b
- `Qwen/Qwen3-Coder-Next` Hugging Face model card: https://huggingface.co/Qwen/Qwen3-Coder-Next
- `Qwen/Qwen3-Omni-30B-A3B-Thinking` Hugging Face model card: https://huggingface.co/Qwen/Qwen3-Omni-30B-A3B-Thinking
- `meta-llama/Llama-3.3-70B-Instruct` Hugging Face model card: https://huggingface.co/meta-llama/Llama-3.3-70B-Instruct
