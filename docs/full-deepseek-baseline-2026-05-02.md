# Full DeepSeek Baseline Run

Date: 2026-05-02  
Ticker/date: `NVDA` / `2026-05-01`  
Provider: `deepseek`  
Model: `deepseek-v4-flash` for quick and deep reasoning  
Titan injection: not used

## Scope

This was the first fuller clean upstream TradingAgents run after the DeepSeek structured-output compatibility patch.

Enabled analysts:

- `market`
- `news`
- `fundamentals`
- `social`

Runtime settings:

- `max_debate_rounds`: `1`
- `max_risk_discuss_rounds`: `1`
- `max_recur_limit`: `100`
- Results written to the integration workspace through a Docker bind mount.

## Output Artifacts

Summary files:

- `outputs\deepseek_full_baseline\NVDA_2026-05-01_deepseek_full_baseline_summary.md`
- `outputs\deepseek_full_baseline\NVDA_2026-05-01_deepseek_full_baseline_summary.json`

Full TradingAgents state log:

- `outputs\deepseek_full_baseline\runtime_logs\NVDA\TradingAgentsStrategy_logs\full_states_log_2026-05-01.json`

## Result

The full clean baseline completed successfully.

Processed final decision:

- `Hold`

Decision summary:

- The upstream agents converged on `Hold`.
- Fundamental, news, and social/sentiment reports leaned bullish.
- Market/technical analysis and risk debate identified near-term deterioration, including bearish momentum shift, high-volume distribution, and price below short-term trend measures.
- The final decision recommended no new add at current levels and no reduction unless structural support breaks.

Key levels from the generated output:

- Current area: approximately `$199`
- Immediate reclaim area: approximately `$203`
- Primary support/stop reference: approximately `$187`
- Deeper structural reference: approximately `$184`

## Compatibility Observations

The previous DeepSeek API 400 `tool_choice` failure did not recur.

Expected local notices still appeared:

- Research Manager, Trader, and Portfolio Manager reported that DeepSeek does not support `with_structured_output` through the current binding.
- These notices confirm the compatibility guard is active and routing those steps to TradingAgents' free-text fallback.

## Initial Quality Assessment

Strengths:

- Clean graph completion with all default analyst families enabled.
- Coherent final stance.
- Clear reconciliation of bullish fundamental/news evidence against bearish short-term technical/risk evidence.
- Useful action conditions and levels were produced.

Limitations before Titan integration:

- The report is not yet Titan OS / DTP compliant.
- Source citations are not institution-grade.
- Horizon classification is absent.
- Evidence integrity, macro/news cross-checking, and self-audit are not yet enforced by the wrapper.
- Some generated claims require independent verification before business use.

## Recommendation

Use this run as the clean baseline for wrapper design.

Next engineering step:

1. Build a thin wrapper that preserves upstream TradingAgents execution.
2. Add a post-processing research packet that performs Titan-style evidence validation, horizon classification, citations, and self-audit.
3. Compare wrapped output against this clean baseline before modifying any upstream internals.

See also:

- `docs\baseline-quality-assessment-2026-05-02.md`
