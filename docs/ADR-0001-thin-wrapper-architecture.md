# ADR-0001: Clean Upstream Core with Titan Thin Wrapper

Date: 2026-05-02

## Status

Accepted.

## Context

The project is evaluating `TauricResearch/TradingAgents` as an auxiliary multi-agent research engine for trade and investment decision support.

The goal is not live brokerage execution. The goal is a final research report supporting:

- Trade stance: long, short, hold, wait, conditional, or not validated.
- Directionality and thesis articulation.
- Entry, exit, invalidation, and risk-reward characteristics.
- Multi-agent research features available in the original project.
- Additional Titan OS / DTP / Activation Trigger / Graphify governance where it improves quality.

The key design question is whether to keep the implementation clean and faithful to the original GitHub project or augment it with Titan OS 2.9, Titan DTP 1.6, the Activation Trigger Framework, and Graphify corpora.

## Decision

Use a layered architecture:

1. **Upstream TradingAgents Core**
   - Keep the cloned repository clean or near-clean.
   - Use Docker to verify the original system behavior.
   - Preserve upstream maintainability and baseline comparability.

2. **Titan Integration Wrapper**
   - Implement external wrapper scripts/configuration around TradingAgents.
   - Load the Primary Graphify corpus and Secondary reference-output corpus.
   - Add Titan prompt/context injection only after baseline verification.
   - Add post-run Titan validation for stance, horizon, sources, risk-reward, and self-audit.

3. **Titan Final Decision Layer**
   - Treat TradingAgents output as advisory evidence.
   - Keep Titan OS 2.9, Titan DTP 1.6, and the Activation Trigger Framework as final validation authority.
   - Do not mark horizons or trade stances as validated unless Titan evidence gates are satisfied.

## Rationale

A pure clean implementation is useful for baseline testing but insufficient as a final Titan-grade research engine.

A heavy internal fork is premature because it can:

- Reduce upgradeability from upstream.
- Make debugging harder.
- Create prompt conflicts between original TradingAgents roles and Titan governance logic.
- Overload agents with framework text, degrading asset-specific analysis.

The thin-wrapper approach provides the best balance:

- Preserves upstream behavior.
- Enables disciplined Titan validation.
- Allows staged testing.
- Maintains traceability.
- Keeps implementation reversible and auditable.

## Consequences

Positive:

- Easier upstream updates.
- Clear baseline-vs-enhanced comparison.
- Stronger audit trail.
- Lower implementation risk.
- Titan remains final research authority.

Trade-offs:

- Some integration features require wrapper-level orchestration rather than direct internal hooks.
- Full Titan-native behavior may require later targeted patches after baseline testing.
- There will be two layers of output to reconcile: TradingAgents state and Titan report output.

## Immediate Next Step

Build and run TradingAgents in Docker with one controlled ticker, likely `NVDA` or `MU`, without Titan prompt injection. Save the raw full-state output for baseline comparison.
