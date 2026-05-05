# Implementation Roadmap

Date: 2026-05-02

## Phase 0: Documentation and Baseline Preservation

Status: In progress.

Tasks:

- Create dedicated documentation directory.
- Record architecture decision.
- Preserve review summary.
- Maintain status register.

## Phase 1: Clean Docker Baseline

Objective: verify the original TradingAgents project works locally before Titan augmentation.

Tasks:

- Build Docker image from the clean repo.
- Configure `.env` with the selected LLM provider and any data API keys.
- Run one controlled ticker dry run, likely `NVDA` or `MU`.
- Save full raw output:
  - analyst reports
  - debate logs
  - trader proposal
  - risk debate
  - portfolio decision
  - full state JSON

Success criteria:

- Docker build completes.
- A single-ticker run completes.
- Output files are created.
- No Titan logic is injected yet.

## Phase 2: Baseline Quality Assessment

Objective: compare unmodified TradingAgents output against Titan requirements.

Assessment dimensions:

- Trade stance clarity.
- Thesis specificity.
- Entry / exit / invalidation quality.
- Risk-reward clarity.
- Source quality.
- Horizon classification quality.
- Whether confidence is overstated.
- Whether output distinguishes trade horizon from investment horizon.

Deliverable:

- Baseline assessment note under `docs/`.

## Phase 3: Thin Titan Wrapper

Objective: add Titan governance without modifying upstream internals heavily.

Proposed wrapper components:

- `universal_research`
  - Defines the Stage 0A universal research request schema.
  - Resolves each request through the instrument registry.
  - Routes `Equity` to the existing equity_v1 workflow.
  - Stops gracefully for registered but unimplemented profiles instead of faking multi-asset coverage.

- `prior_graph_context_loader`
  - Loads prior graph-backed research for the same ticker or asset.
  - Carries supported claims as timestamped historical context.
  - Carries blocked items and residual gaps into the fresh research plan.
  - Prevents repeated research from starting cold when prior graph evidence exists.

- `data_providers`
  - Normalizes yfinance, SEC EDGAR, and Stooq data.
  - Keeps Alpaca Basic and Alpha Vantage as optional inactive adapters.
  - Attaches source-audit metadata to provider outputs.

- `titan_context_loader`
  - Loads Primary Graphify corpus.
  - Loads Secondary reference-output corpus.

- `titan_run_orchestrator`
  - Runs TradingAgents for selected tickers.
  - Stores raw state.
  - Controls output directories.

- `titan_validator`
  - Normalizes trade stance.
  - Validates horizon classification.
  - Checks source integrity.
  - Checks risk-reward completeness.
  - Applies Conditional / Not Validated reasoning rules.

- `citation_retrieval`
  - Links claims to primary, official, and reputable secondary sources.
  - Builds an evidence ledger from timestamped source records before assigning Stage 2 claim status.
  - Prevents manifest rules from marking claims Supported when source IDs are missing, future-dated, or unrelated to the claim.
  - Preserves unresolved requirements when evidence is partial.
  - Produces Stage 2 citation packets for Graphify and later Titan validation.

- `evidence_reinforcement`
  - Converts Conditional / Not Validated claim gaps into explicit retrieval tasks.
  - Routes reinforcement upgrades through the evidence ledger before a stronger status can survive.
  - Attempts to upgrade, preserve, or contradict claims based on stronger evidence.
  - Produces Stage 2B packets before Graphify so the graph receives reinforced evidence states, not unresolved prose only.

- `evidence_ledger`
  - Acts as the source-led validation authority for external facts.
  - Requires source ID, source metadata, publication date/retrieval timestamp, supported claims, and limitations.
  - Blocks agent prose from validating facts without an as-of-valid matching source record.

- `retrieval_plan`
  - Defines asset-class-aware source search playbooks.
  - Requires primary, secondary, and fallback source-class attempts before evidence can be labeled missing.
  - Starts with equity mandatory evidence tasks and remains extensible for ETF, index, options, crypto, FX, futures, commodity, and CFD phases.

- `metric_reconciliation`
  - Applies explicit formulas to computable financial and valuation metric conflicts.
  - Stores inputs, formula, computed result, reported values, source IDs, limitations, and reconciliation status.
  - Prevents unsupported numerical claims from entering final Titan language even when the arithmetic is internally coherent.

- `stale_claim_refresh`
  - Refreshes previously supported claims that disappear from a fresh repeated-ticker graph.
  - Re-attaches prior source evidence with fresh reachability metadata.
  - Prevents catalyst and earnings-timing claims from remaining stale solely because the fresh LLM run omitted the claim text.

- `graphify_evidence_layer`
  - Converts Stage 1, Stage 2, Stage 2B, Stage 2C, Stage 2D, citation manifests, and reinforcement manifests into a knowledge graph.
  - Encodes claim, source, reliability, status, residual gap, and evidence-class relationships.
  - Supports later Titan horizon classification and self-audit.

- `evidence_delta`
  - Compares prior graph context with fresh evidence.
  - Classifies each item as unchanged, updated, strengthened, weakened, contradicted, stale, newly discovered, still blocked, or needing fresh evidence.
  - Feeds horizon validation and final report generation.

- `horizon_validator`
  - Reads the evidence graph.
  - Evaluates Intraday, Swing, Positional, and Long-Term independently.
  - Preserves Conditional / Not Validated outcomes with explicit business-facing rationale.
  - Blocks final validated horizons when evidence is contradictory, proxy-only, or missing a mandatory Titan evidence block.

- `titan_report_exporter`
  - Converts TradingAgents state plus Titan validation into institutional Markdown/PDF reports.
  - Uses the Stage 5 final-report quality gate to preserve useful baseline structure while preventing unsupported baseline claims from entering final language.
  - Requires report metadata, executive decision summary, technical analysis, user evidence where present, fundamentals, valuation, news/catalyst/macro context, evidence/source audit, validated trading horizon, and self-audit.
  - Current implementation: `titan_integration\report_exporter.py` and `scripts\build_stage5_final_report.py`.

## Phase 4: Controlled Prompt Injection

Objective: improve TradingAgents reasoning quality only where baseline gaps justify it.

Injection order:

1. Portfolio Manager.
2. Trader.
3. Research Manager.
4. Analyst prompts only if needed.

Rules:

- Avoid dumping full corpora into every prompt.
- Use compact governance summaries and retrieved relevant context.
- Keep Primary Corpus authoritative.
- Keep Secondary Corpus limited to reference-output and presentation-quality guidance.

## Phase 5: Multi-Ticker Research Workflow

Objective: integrate TradingAgents into the broader Titan research process.

Status update, 2026-05-03:

- Completed the second full equity end-to-end validation using `MU` after the original `NVDA` control run.
- Confirmed the active Stage 5 v2 report path preserves baseline sections and layers TITAN commentary without rewriting baseline content.
- Confirmed Stage 3F graph overlay includes report section, horizon decision, legal notice, logo attribution, and source/evidence traceability nodes for both `NVDA` and `MU`.
- Generalized Stage 2C, Stage 4, and Stage 5 v2 logic where the MU test exposed NVIDIA-specific assumptions.
- Remaining before broader multi-ticker production: automate citation-manifest retrieval so future tickers do not require hand-curated source manifests.

Likely pattern:

1. Existing Titan screen identifies candidates.
2. TradingAgents performs deep single-ticker or small-basket analysis.
3. Titan validator adjudicates and classifies.
4. Final institutional report is generated.

Stage 5 report-generation rule:

- Baseline reports are structured inputs, not final authority.
- Every final section must be fact-checked, source-audited, and linked to the evidence graph or an explicit residual gap.
- All conditional, blocked, not validated, and assumption-based items must include business-facing rationale.

## Phase 6: Universal Multi-Asset Expansion

Objective: expand from the equity reference implementation to a unified
multi-asset framework.

Dependency-ordered sequence:

1. Finish and freeze `Equity v1` as the active regression profile.
   - Keep `NVDA` and `MU` as historical equity regression cases.
   - Require automated evidence retrieval, source validation, decision-integrity checks, graph generation, and Stage 5 reporting to remain stable across generic equity tickers.
2. Add `ETF` profile.
   - Reuse equity market-data and technical evidence where appropriate.
   - Add holdings, issuer/sponsor, NAV/discount-premium, expense ratio, flows, liquidity, concentration, and underlying exposure evidence.
   - Do not treat an ETF like a single operating company; SEC issuer fundamentals and company guidance rules must be replaced by fund-specific evidence.
3. Add `Index` profile.
   - Build on equity and ETF evidence patterns.
   - Add constituent breadth, sector weights, index methodology, macro/factor regime, earnings breadth, rates/liquidity context, and futures/ETF proxy mapping.
4. Add listed options on supported underlyings.
   - Start with `Equity-Option` once `Equity v1` is stable.
   - Add `ETF-Option` after ETF profile is stable.
   - Add `Index-Option` after index profile is stable.
   - Required evidence includes expiry, strike, moneyness, implied volatility, realized volatility, Greeks, open interest, volume, bid/ask spread, skew, term structure, assignment/exercise style, event risk, and underlying linkage.
   - Options reports must never be produced from underlying-only research; the option contract must have its own evidence packet and risk model.
5. Add `Crypto` spot profile.
   - Add exchange/venue data, liquidity, order-book context where available, funding/derivatives context as optional evidence, on-chain/network metrics where relevant, custody/regulatory/news risk, and 24/7 session handling.
6. Add `FX` spot profile.
   - Add pair-specific macro, rates, central-bank, inflation, balance-of-payments, positioning, cross-asset risk, session/liquidity, and calendar-event evidence.
7. Add `Futures` profile.
   - Add contract metadata, front/next contract mapping, roll schedule, open interest, volume, curve structure, basis, margin, tick value, session calendar, and expiry/roll risk.
8. Add `Commodity` profile.
   - Build on futures infrastructure where applicable.
   - Add commodity-specific supply/demand evidence such as inventories, production, consumption, weather, OPEC/EIA/API data for energy, real yields/DXY/central-bank flows for gold, and sector-specific physical-market evidence.
9. Add `CFD` profile after the underlying asset model exists.
   - CFD support is a wrapper over an underlying asset class, not a standalone research shortcut.
   - Required evidence includes platform symbol mapping, spread, overnight financing, leverage/margin, session rules, contract specification, and relationship to the underlying spot/futures/index/commodity instrument.
10. Add advanced derivatives after the underlying and listed-option models are stable.
    - Examples: futures options, commodity options, crypto options, spreads, volatility structures, and multi-leg strategies.

Rule:

- Registered but unimplemented profiles must produce a clear unsupported-profile packet and must not reuse equity assumptions.

## Phase 7: GitHub Publication Readiness

Objective: publish a clean wrapper repository without exposing private data.

Tasks:

- Keep upstream TradingAgents as an external dependency/source reference.
- Exclude nested `TradingAgents/`, secrets, local data, corpora, generated packets, graphs, archives, caches, and user inputs.
- Maintain `NOTICE.md`, `SECURITY.md`, `.env.example`, and root `README.md`.
- Run `scripts\publication_safety_check.py` before any push.

## Deferred / Not in Scope

- Live brokerage execution.
- Automatic order placement.
- Treating TradingAgents final recommendation as final without Titan validation.
- Heavy upstream fork before baseline evidence supports it.
