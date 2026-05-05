# Status Register

Date: 2026-05-02

## Completed

- Completed global issuer/SEC evidence-promotion refinement:
  - Stage 2/2B source promotion now deep-reads cited issuer IR, SEC,
    earnings-release, filing, and transcript URLs before typing facts.
  - SEC EDGAR companyfacts now promotes operating cash flow and
    property/equipment CapEx concepts into the equity evidence store; latest
    FCF is computed centrally as same-period OCF minus CapEx.
  - RPO/backlog is now business-model and thesis conditional, with numeric
    artifact rejection for CIK/accession-like values.
  - Stale earnings-date conflicts remain quarantined diagnostics after the
    canonical earnings-event resolver succeeds, but they no longer force
    `DATA-INCOMPLETE` by themselves.
  - Stage 1 can reuse valid provider evidence already captured by the baseline
    run if a local optional market-data dependency is unavailable during a
    rebuild.
  - MSFT `MSFT_20260504T213159Z` was regenerated with no blocked evidence keys:
    RPO `$627B`, SEC OCF, SEC CapEx, computed FCF, actual-vs-consensus, market
    data, short interest, and Form 4 are all promoted.
  - Targeted verification:
    - `cd TradingAgents; uv run pytest -q tests\test_global_equity_evidence_enforcement.py`
      passed with `65 passed`.

- Implemented dynamic web-RAG planner and source-link agent context:
  - Added source-aware query planning in `titan_integration\dynamic_rag.py`.
  - Unresolved evidence keys now expand into official issuer, SEC/regulatory,
    reputable news/wire, specialist aggregator, and general web query variants
    before being marked unavailable.
  - Candidate URLs are deduplicated, source-class filtered, lightly reranked,
    fetched, and stored with query text, source class, retrieval score,
    publisher, URL, confidence, and source level.
  - Agent evidence context now includes source URLs and recent resolver trace
    summaries so analysts, Bull/Bear debaters, risk analysts, Trader, Research
    Manager, and Portfolio Manager can inspect the same links TITAN validated.
  - Added targeted regression coverage for query planning, source-class
    ranking, and source-link injection.
  - Targeted verification:
    - `cd TradingAgents; uv run pytest -q tests\test_global_equity_evidence_enforcement.py`
      passed with `48 passed`.
  - Full verification:
    - `python -B -m compileall -q scripts titan_integration TradingAgents\tradingagents` passed.
    - `python scripts\publication_safety_check.py` passed.
    - `cd TradingAgents; uv run pytest -q` passed with `168 passed, 42 subtests passed`.

- Implemented global pre-agent earnings-event resolution:
  - Added `titan_integration\earnings_event_resolver.py`.
  - The mandatory equity scan now classifies latest reported earnings and next
    estimated earnings before TradingAgents analysts, debaters, risk analysts,
    Trader, Research Manager, and Portfolio Manager receive their evidence
    context.
  - The resolver records the full API/provider, issuer IR, SEC/regulatory,
    reputable news/wire, specialist aggregator, general web, query-expansion,
    extraction-retry, and conflict-reconciliation chain.
  - Stale near-term catalyst dates are quarantined under
    `catalyst.stale_earnings_date_conflict`; Stage 5 annotates any surviving
    upstream prose that mentions those stale dates instead of allowing them to
    become final decision logic.
  - Added generic regression coverage proving an issuer latest-reported event
    plus a valid next estimated date overrides a stale near-term aggregator
    date without ticker-specific production logic.
  - Added regression coverage blocking two root causes found during smoke
    verification: a report/as-of date cannot be promoted as the next earnings
    date, and a short-interest page cannot satisfy the latest earnings-release
    requirement merely because its navigation mentions earnings links.
  - Targeted verification:
    - `cd TradingAgents; uv run pytest -q tests\test_global_equity_evidence_enforcement.py`
      passed with `45 passed`.
  - Full verification:
    - `python -B -m compileall -q scripts titan_integration TradingAgents\tradingagents` passed.
    - `python scripts\publication_safety_check.py` passed.
    - `cd TradingAgents; uv run pytest -q` passed with `165 passed, 42 subtests passed`.

- Completed global rich-but-evidence-clean report safety refinement:
  - Replaced blunt paragraph-level removal for unresolved-but-useful dependency
    claims with inline evidence notes.
  - Preserved rich upstream analyst, market, fundamental, sentiment, trader,
    Research Manager, and risk/debate narrative in reader-facing diagnostic
    sections while marking unsupported scenario claims at the point of use.
  - Appendix A is now reserved for truly rejected claims, not every useful
    paragraph that mentions one unresolved evidence dependency.
  - Split actual CapEx/FCF handling from forward CapEx guidance:
    - `cashflow.latest.ocf`
    - `cashflow.latest.capex`
    - `cashflow.fcf_inputs`
    - `cashflow.fcf_conversion`
    - `cashflow.annual.ocf`
    - `cashflow.annual.capex`
    - `cashflow.annual.fcf_inputs`
    - `capex.actual.same_period`
  - Prevented annual cash-flow records from overwriting latest quarterly
    cash-flow records.
  - Fresh MSFT export for `MSFT_20260504T134651Z` now has `0` Appendix A
    rejected claims, `18` inline evidence notes, and a report body of roughly
    `104k` Markdown characters, restoring much of the earlier rich-report
    feel while keeping `DATA-INCOMPLETE / MONITOR ONLY` until remaining hard
    evidence gaps are resolved.
  - Verification:
    - `python scripts\publication_safety_check.py` passed.
    - `python -B -m compileall -q scripts titan_integration TradingAgents\tradingagents` passed.
    - `cd TradingAgents; uv run pytest -q` passed with `160 passed, 42 subtests passed`.

- Completed upstream-tool evidence capture and promotion retest after the
  Appendix A over-blocking investigation:
  - Added best-effort capture of TradingAgents upstream dataflow tool outputs
    through `TRADINGAGENTS_TOOL_EVIDENCE_PATH`.
  - Baseline runs now persist
    `<TICKER>_<DATE>_upstream_tool_evidence.jsonl` and include the path in the
    baseline summary.
  - Stage 5 now promotes captured upstream provider/tool facts into the typed
    equity evidence store before dynamic RAG repair and final-report safety
    filtering.
  - Added priority-aware evidence-store replacement so later weak web artifacts
    cannot overwrite stronger provider, issuer, regulatory, or computed facts.
  - Restored sanitized Bull/Bear, Research Manager, Trader, and
    aggressive/neutral/conservative risk debate outcomes into the diagnostic
    report surface.
  - Added regression coverage for upstream tool promotion and invalid
    late-resolver overwrite prevention.
  - Fresh MSFT export for `MSFT_20260504T134651Z` improved rejected claims from
    `61` to `36`; all remaining rejected claims are now tied to the unresolved
    `capex.guidance` dependency.
  - Stage 3 evidence graph refreshed with `151` nodes and `363` edges, graph
    share package regenerated, and research cycle archived under
    `research_cycles\MSFT_20260504T134651Z`.
  - Evidence now promoted correctly for latest price, 52-week range, FCF
    inputs, OCF, CapEx, forward P/E basis, FY1 EPS, TTM EPS, and technical
    indicators.
  - Remaining report mode: `diagnostic_research_packet` / `DATA-INCOMPLETE /
    MONITOR ONLY` because issuer-backed CapEx guidance and several non-CapEx
    mandatory keys remain unresolved.
  - Verification:
    - `python scripts\publication_safety_check.py` passed.
    - `python -B -m compileall -q scripts titan_integration TradingAgents\tradingagents` passed.
    - `cd TradingAgents; uv run pytest -q` passed with `158 passed, 42 subtests passed`.

- Completed global MSFT QA report-hardening pass after the
  `MSFT_20260504T134651Z` review:
  - Added dynamic RAG pre-render repair: unresolved critical evidence keys now
    trigger evidence-key-specific query planning and the API, issuer, SEC,
    news/wire, aggregator, public web, query-expansion, extraction-retry, and
    source-reconciliation chain before `DATA-INCOMPLETE` can remain.
  - Added resolver traces to the Stage 5 manifest and report appendix.
  - Added diagnostic-mode gating: if critical gates remain failed after repair,
    the report renders as `DIAGNOSTIC RESEARCH PACKET - NOT FINAL` rather than
    a final institutional report.
  - Clarified CSV handling in code and docs: CSVs are optional/supplemental and
    cannot override newer canonical OHLCV; provider-derived technical evidence
    is used as fallback when CSVs are absent.
  - Added canonical `ReportContext` and `FinalDecision` rendering so all
    reader-facing sections use one date/price/action source of truth.
  - Regenerated institutional report sections from typed evidence instead of
    raw baseline prose.
  - Replaced generic/raw section titles with meaningful report titles:
    `Technical Analysis`, `Market & Catalyst Analysis`, `Fundamental Analysis`,
    `Sentiment & Positioning`, `Research Manager Adjudication`, and
    `Trader Execution Plan`.
  - Added evidence-store reconciliation, source-permission checks, and numeric
    artifact rejection through `retrieved_invalid` evidence status.
  - Regenerated the MSFT Stage 5 v2 HTML, Markdown, PDF, and manifest.
  - Body-only QA checks confirmed no raw `News Report` / `Fundamentals Report`
    / `Sentiment Report` / `Market Report` labels, no scratchpad phrases, no
    stale `$414.44` / May 1 price text, and no baseline sell/reduce/CapEx/FCF
    rejected claims in the reader-facing body.
  - Rejected baseline claims remain in Appendix A only as controlled audit
    records.
  - Added documentation record:
    - `docs\MSFT_QA_global_report_hardening_2026-05-04.md`
  - Verification:
    - `python -B -m compileall -q scripts titan_integration TradingAgents\tradingagents` passed.
    - `uv run pytest -q tests\test_global_equity_evidence_enforcement.py` passed with `34 passed`.
  - Remaining MSFT decision status: `DATA-INCOMPLETE / MONITOR ONLY`; render
    mode is `diagnostic_research_packet` because critical evidence keys remain
    blocked or `retrieved_invalid` after the dynamic repair loop.

- Completed clean MSFT end-to-end retest after dated input discovery and final
  report quarantine hardening:
  - Latest report run ID after price-snapshot enhancement: `MSFT_20260504T134651Z`.
  - Stage 0A selected `inputs\MSFT\2026-05-04`.
  - Stage 0A through Stage 5, final graph refresh, graph package, and archive completed.
  - Final report path:
    `research_packets\stage5_final_report\MSFT_20260504T134651Z\MSFT_20260504T134651Z_stage5_v2_final_report.pdf`
  - Added top-of-report price snapshot with latest OHLC, volume, 52-week high/low, and distance from 52-week levels.
  - Added documentation record:
    - `docs\MSFT_retrieval_promotion_retest_2026-05-04.md`
  - Remaining status: `Not Titan-Compliant` because `capex.guidance`,
    `earnings.actual_vs_consensus`, and `fundamentals.latest_earnings_release`
    remain unresolved.

- Implemented dated user-input folder discovery:
  - Added `titan_integration\input_discovery.py`.
  - Stage 0A now resolves the latest eligible dated user-input folder under `inputs\<TICKER>` on or before the analysis date.
  - If an older folder is supplied while a newer eligible folder exists, Stage 0A selects the newer folder and records the warning in the request packet.
  - Added regression coverage so future runs do not silently use stale user-supplied CSV folders when newer dated inputs are available.

- Implemented global Equity v1 retrieval and evidence-promotion hardening:
  - Added a pre-agent public equity resolver layer that promotes public-source facts into `EvidenceStore` before analyst generation.
  - Split generic filing handling into financial filing, earnings 8-K, and ownership filing categories so ownership forms cannot satisfy 10-Q/10-K requirements.
  - Added source metadata for retrieval method, source URL, as-of date, confidence, and direct/proxy classification.
  - Added cloud/SaaS metric extraction, cash-flow/FCF input promotion, CapEx/guidance promotion, analyst consensus, short interest, options put/call, next earnings date, and technical indicator promotion paths.
  - Added `ReportDates`, `ReportMode`, issuer display-name sanitation, scratchpad phrase cleanup, and support/resistance/pivot classification by latest close.
  - Updated Stage 5 institutional rendering so diagnostic/error tables move to appendices, Final Trade Decision appears near the front, and legal/title text cannot use technical indicator strings.
  - Preserved and extended continuous operational learning behavior through role-specific prior-error injection and recurrence escalation.
  - Added documentation record:
    - `docs\global-equity-retrieval-promotion-2026-05-04.md`
  - Verification:
    - `python scripts\publication_safety_check.py` passed.
    - `python -B -m compileall -q scripts titan_integration TradingAgents\tradingagents` passed.
    - `uv run pytest -q` passed with `149 passed, 42 subtests passed`.

- Implemented global equity evidence enforcement after the MSFT corrected-report review:
  - Added `titan_integration\equity_evidence.py` with typed evidence store, mandatory equity scan, earnings classifier, CapEx/FCF/forward P/E resolvers, consensus/earnings-date/short-interest helpers, peer comparison validation, debate validation, contamination checks, Research Manager adjudication validation, and Portfolio Manager sanity gate.
  - Added `titan_integration\error_learning.py` for persistent agent error records and recurrence escalation.
  - Updated `scripts\run_tradingagents_baseline.py` so mandatory equity evidence scan runs before agents, writes a store artifact, passes evidence context into agent state, and hard-fails below five Bull/Bear debate rounds.
  - Updated TradingAgents state/config and selected agent surfaces to receive code-generated mandatory evidence context.
  - Updated Stage 1 and Stage 5 v2 contracts to expose mandatory equity scan and global enforcement gates.
  - Removed older fixed-date technical references from active `titan_integration` logic and replaced them with generic recent swing/distribution calculations.
  - Added `TradingAgents\tests\test_global_equity_evidence_enforcement.py`.
  - Added documentation record:
    - `docs\global-equity-evidence-enforcement-2026-05-04.md`
  - Targeted verification:
    - `uv run pytest tests/test_global_equity_evidence_enforcement.py tests/test_institutional_evidence_policy.py -q` passed with `25 passed`.

- Implemented the Equity Evidence Root-Fix patch:
  - Expanded Equity v1 mandatory evidence discipline with fallback discovery attempts, transcript/guidance emphasis, optional ownership/options evidence keys, and a stronger do-not-claim context for unresolved facts.
  - Added Stage 2B source-to-fact promotion so validated citation/reinforcement sources can populate a typed promoted evidence store:
    - `research_packets\stage2b\<TICKER>_<DATE>_equity_evidence_store_promoted.json`
  - Upgraded Bull/Bear validation from count-only to semantic five-round enforcement: Opening Thesis, Data Challenge, Narrative Counter, Invalidation Stress-Test, and Convergence / Residual Disagreement.
  - Updated Stage 5 v2 so contaminated baseline passages are removed from ordinary reader-facing narrative and appear only in the controlled Excluded Claims / Errors and Recommendations table.
  - Added final-report safety metadata to the Stage 5 manifest: accepted claims, rejected claims, unresolved gaps, self-audit status, and promoted evidence store.
  - Updated documentation:
    - `docs\global-equity-evidence-enforcement-2026-05-04.md`
    - `docs\USER_MANUAL_STAGE0A_TO_STAGE5.md`
  - Targeted verification:
    - `uv run pytest tests/test_global_equity_evidence_enforcement.py -q` passed with `17 passed`.
  - Full verification after MSFT Stage 2B/Stage 5 smoke regeneration:
    - `python scripts\publication_safety_check.py` passed.
    - `python -B -m compileall -q scripts titan_integration` passed.
    - `uv run pytest -q` passed with `137 passed, 42 subtests passed`.
  - MSFT smoke result:
    - Stage 2B regenerated `research_packets\stage2b\MSFT_2026-05-03_equity_evidence_store_promoted.json`.
    - Stage 5 regenerated the `MSFT_20260504T090723Z` final HTML, Markdown, and PDF.
    - The MSFT earnings-disappointment and annualized-CapEx wording now appears only in the controlled Excluded Claims / Errors and Recommendations table, not as ordinary baseline narrative.

- Completed fresh MSFT retest after the role-specific operational-learning patch:
  - Fresh run ID: `MSFT_20260504T103153Z`.
  - Completed Stage 0A through Stage 5 v2, graph refresh, graph share packaging, and research-cycle archive.
  - Final report generated under:
    - `research_packets\stage5_final_report\MSFT_20260504T103153Z`
  - Stage 2C now blocks missing forward valuation inputs instead of crashing when no usable forward P/E candidate is available.
  - Final report no longer contains the prior visible `Disappointing Earnings Reaction`, `fell short`, or `annualized CapEx` wording as normal reader-facing narrative.
  - Remaining status: evidence-gated with unresolved dependencies, including CapEx guidance, actual-vs-consensus earnings, latest earnings release, ownership, and options/put-call evidence.
  - Retest record added:
    - `docs\MSFT_operational_learning_retest_2026-05-04.md`
  - Targeted verification:
    - `python -B -m compileall -q scripts titan_integration TradingAgents\tradingagents` passed.
    - `uv run pytest -q tests\test_global_equity_evidence_enforcement.py` passed with `21 passed`.
  - Completed operational learning loop:
    - Stage 5 rejected claims are persisted into `research_packets\error_learning\agent_error_records.json`.
    - Records include responsible agent role, evidence dependency, exact failure, concrete correction rule, recurrence status, severity, and timestamp.
    - Duplicate records from the same run are ignored.
    - Recurrence escalation is global across tickers by normalized agent role, error type, and evidence dependency.
    - Future baseline runs build role-specific feedback memory and inject only relevant prior failures into each responsible agent's context before analysis begins.
    - Decision agents still receive relevant high-severity learning so Research Manager, Trader, and Portfolio Manager can block inherited contamination.
    - Targeted verification updated to `20 passed`.

- Completed live MSFT retest after the global equity enforcement patch:
  - Fresh run ID: `MSFT_20260504T090723Z`.
  - Stage 0A through Stage 5 v2 completed and archived under `research_cycles\MSFT_20260504T090723Z`.
  - New final report generated:
    - `research_packets\stage5_final_report\MSFT_20260504T090723Z\MSFT_20260504T090723Z_stage5_v2_final_report.html`
    - `research_packets\stage5_final_report\MSFT_20260504T090723Z\MSFT_20260504T090723Z_stage5_v2_final_report.md`
    - `research_packets\stage5_final_report\MSFT_20260504T090723Z\MSFT_20260504T090723Z_stage5_v2_final_report.pdf`
  - Confirmed improvements: code-enforced equity scan appears in the final report, global enforcement gates appear in the final report, and the Bull/Bear debate validator passed with `10` contributions against the required five-round minimum.
  - Retest comparison added:
    - `docs\MSFT_live_retest_comparison_2026-05-04.md`
  - Publication status: still blocked because the final report preserves some baseline-generated contaminated wording in the reader-facing body even though the TITAN overlay later constrains or rejects the claims.

- Completed final GitHub-readiness documentation and safety audit pass:
  - Added `docs\github-readiness-final-audit-2026-05-03.md`.
  - Rebuilt root `README.md` into a repository-wide, institution-grade entry point covering lineage, direct interfaces, environment model, workflow, outputs, evidence governance, publication safety, and disclaimers.
  - Updated `docs\github-publication-checklist.md`, `docs\direct-user-interface-and-deployment-path.md`, `docs\README.md`, and `inputs\README.md`.
  - Tightened `.gitignore` and `scripts\publication_safety_check.py` for local-only assets, output folders, test results, temporary folders, research cycles, and publication guard checks.
  - Neutralized remaining ticker-specific legacy report text in `titan_integration\report_exporter.py`, changed the Stage 5 v2 fallback ticker from `NVDA` to `UNKNOWN`, and generalized ecosystem proxy detection in `titan_integration\validation_packet.py`.
  - License attribution caveat: local upstream and wrapper license files are Apache-2.0, so docs preserve Apache-2.0 attribution rather than incorrectly stating MIT.
  - Verification:
    - `python scripts\publication_safety_check.py` passed.
    - `python -B -m compileall -q scripts titan_integration` passed.
    - `uv run pytest -q` passed with `120 passed, 42 subtests passed`.
  - Confidentiality note:
    - Broad local scan found a real provider key in ignored `TradingAgents\.env`; it is outside the publication candidate set, but should be removed locally and rotated before any publication step if exposure is possible.

- Added business-user operating manual for the full research workflow:
  - `docs\USER_MANUAL_STAGE0A_TO_STAGE5.md`
  - Covers PowerShell setup, project path, `uv` execution pattern, user input folders, Stage 0A through Stage 5 commands, evidence graph generation, final report export, share packaging, archival, outputs, interpretation, and common mistakes.
  - Linked from:
    - `docs\README.md`
    - `README.md`

- Completed third full equity regression scenario for `MSFT` / `2026-05-03`:
  - Stage 0A resolved `MSFT` to active `equity_v1`.
  - TradingAgents DeepSeek V4 Flash baseline completed with processed decision `Hold`.
  - User CSV evidence was detected under `inputs\MSFT\2026-05-03`.
  - Stage 1 through Stage 5 v2 completed.
  - Stage 2 and Stage 2B used the evidence ledger and MSFT-specific source manifests without ticker-specific code changes.
  - Stage 3 graph after final-report overlay contains 147 nodes and 342 edges.
  - Stage 4 validated trading horizon: `Conditional Candidate: Intraday / Day Trading, Swing, Positional`.
  - Stage 5 v2 final report generated:
    - `research_packets\stage5_final_report\MSFT_20260503T161816Z\MSFT_20260503T161816Z_stage5_v2_final_report.html`
    - `research_packets\stage5_final_report\MSFT_20260503T161816Z\MSFT_20260503T161816Z_stage5_v2_final_report.md`
    - `research_packets\stage5_final_report\MSFT_20260503T161816Z\MSFT_20260503T161816Z_stage5_v2_final_report.pdf`
  - Added regression record:
    - `docs\MSFT_final_equity_regression_test_2026-05-03.md`
  - Verification:
    - `uv run pytest -q` passed with `120 passed, 42 subtests passed`
  - Cosmetic report update after review:
    - Stage 5 v2 TITAN Addendum C now displays numeric VWAP, RSI, ADX, volume, volume-MA, and volume/MA ratio values next to the existing signal labels.
    - Regenerated the MSFT Stage 5 v2 final HTML, Markdown, and PDF after the renderer update.

- Added source-led validation hardening after the MU temporal-source review:
  - Implemented the evidence ledger:
    - `titan_integration\evidence_ledger.py`
  - Implemented the asset-class-aware retrieval plan:
    - `titan_integration\retrieval_plan.py`
  - Routed Stage 2 citation linking through ledger validation:
    - `titan_integration\citation_retrieval.py`
  - Routed Stage 2B reinforcement upgrades through ledger validation:
    - `titan_integration\evidence_reinforcement.py`
  - Added regression coverage:
    - no `Supported` external fact without a source record
    - no unrelated source record validating an unrelated claim
    - equity retrieval plan includes required source classes
    - broad single-word Stage 2B task patterns do not attach to unrelated claims
  - Added documentation:
    - `docs\evidence-led-validation-architecture-2026-05-03.md`
  - Verification:
    - `uv run pytest -q` passed with `120 passed, 42 subtests passed`
    - MU Stage 2 and Stage 2B smoke packets generated under `.tmp_evidence_ledger_smoke`

- Completed second full equity end-to-end generalization validation for `MU` / `2026-05-03`:
  - TradingAgents DeepSeek V4 Flash baseline completed.
  - Stage 0A resolved `MU` to active `equity_v1`.
  - Stage 1 through Stage 2D packets generated.
  - Stage 3F graph generated with report, horizon, legal, logo, source, metric, and user technical feature overlays.
  - Stage 4 horizon validation generated.
  - Stage 5 v2 HTML, Markdown, PDF, and manifest generated.
  - Micron official-website logo was discovered and applied with issuer-specific legal attribution.
  - Report screenshot and graph screenshot were captured for visual QA.
  - Added validation record:
    - `docs\mu-end-to-end-generalization-validation-2026-05-03.md`
- Generalized active equity workflow logic exposed by the MU run:
  - `titan_integration\metric_reconciliation.py` no longer uses NVIDIA-specific source IDs or guidance assumptions in the generic Stage 2C path.
  - `titan_integration\horizon_validation.py` no longer references NVIDIA-specific valuation numbers in generic horizon decisions.
  - `titan_integration\report_preview_v2.py` now derives issuer, posture, legal text, logo display, and key technical levels from packet data instead of NVIDIA-specific fixed text.

- Created isolated integration workspace:
  - `D:\Projects\CodeX\TradingAgents_Integration`
- Cloned TradingAgents repository:
  - `D:\Projects\CodeX\TradingAgents_Integration\TradingAgents`
- Downloaded and extracted arXiv paper:
  - `research_materials\TradingAgents_2412.20138.pdf`
  - `research_materials\TradingAgents_2412.20138.txt`
- Downloaded and cleaned YouTube transcript:
  - `research_materials\youtube_tradingagents_9FoEsXNGLwI.en.vtt`
  - `research_materials\youtube_tradingagents_9FoEsXNGLwI_clean.txt`
- Captured CodeWiki static HTML shell:
  - `research_materials\codewiki_tradingagents.html`
- Reviewed core repository files, graph architecture, agent roles, dataflows, schemas, Docker files, and changelog.
- Confirmed Docker and Docker Compose are available locally.
- Accepted architecture decision: clean upstream core plus Titan thin wrapper.
- Created internal documentation directory:
  - `docs`
- Built the clean upstream TradingAgents Docker image:
  - image: `tradingagents-tradingagents:latest`
- Added a non-secret baseline `.env` placeholder under the TradingAgents repo.
- Completed a Docker import smoke test:
  - `TradingAgentsGraph` imports successfully.
  - `DEFAULT_CONFIG` loads successfully.
  - upstream defaults observed: `llm_provider=openai`, `quick_think_llm=gpt-5.4-mini`, `deep_think_llm=gpt-5.4`.
- Inspected local inference runtimes:
  - Ollama is running on port `11434`.
  - LM Studio is running on port `1234`.
  - Docker container can reach both through `host.docker.internal`.
- Added backend options assessment:
  - `docs\backend-options-assessment-2026-05-02.md`
- Added local inference and hardware assessment:
  - `docs\local-inference-hardware-assessment-2026-05-02.md`
- Ran first LM Studio local inference validation:
  - Direct `/v1/chat/completions` call to `openai/gpt-oss-20b` succeeded.
  - Docker container can call LM Studio through `http://host.docker.internal:1234/v1`.
  - TradingAgents market-only NVDA dry run reached tools and yfinance data retrieval.
  - `openai/gpt-oss-20b` entered repeated `get_stock_data` calls and hit LangGraph recursion limit.
  - `qwen/qwen3-coder-next` progressed into indicators but still repeated tool calls and hit LangGraph recursion limit.
  - `meta/llama-3.3-70b` loaded and answered a direct endpoint check, but the market-only TradingAgents graph did not complete within a 15-minute guardrail.
  - Downloaded `qwen3-30b-a3b-instruct-2507` Q4_K_M GGUF through LM Studio CLI.
  - `qwen3-30b-a3b-instruct-2507` passed direct endpoint check and progressed through stock data plus multiple indicators, but still repeated indicator calls and hit LangGraph recursion limit.
- Added local dry-run record:
  - `docs\local-lmstudio-dryrun-2026-05-02.md`
- Configured DeepSeek API key in ignored local `.env` file.
- Ran DeepSeek V4 Flash baseline:
  - Direct connectivity check succeeded.
  - Market-only NVDA TradingAgents run completed.
  - Final decision returned: `Hold`.
  - Structured-output calls emitted DeepSeek `tool_choice` warnings and fell back to free text.
- Added hosted baseline record:
  - `docs\deepseek-v4-flash-baseline-2026-05-02.md`
- Patched DeepSeek structured-output compatibility:
  - Updated `tradingagents\llm_clients\openai_client.py`.
  - Updated `tests\test_deepseek_reasoning.py`.
  - DeepSeek models now route directly to TradingAgents' free-text fallback for structured decision steps.
  - Rebuilt Docker image successfully.
  - Focused smoke test confirmed `deepseek-reasoner`, `deepseek-v4-flash`, and `deepseek-v4-pro` raise the intended `NotImplementedError` for `with_structured_output`.
  - Re-ran market-only NVDA DeepSeek V4 Flash baseline after patch.
  - Final decision remained: `Hold`.
  - Previous DeepSeek API 400 `tool_choice` warnings did not recur.
- Ran fuller clean DeepSeek V4 Flash baseline with `market`, `news`, `fundamentals`, and `social` analysts enabled:
  - Ticker/date: `NVDA` / `2026-05-01`.
  - Final processed decision: `Hold`.
  - Output artifacts saved under `outputs\deepseek_full_baseline`.
  - Added full-run record:
    - `docs\full-deepseek-baseline-2026-05-02.md`
- Added baseline quality assessment:
  - `docs\baseline-quality-assessment-2026-05-02.md`
- Accepted free data-provider architecture:
  - `yfinance` for prototype OHLCV.
  - `SEC EDGAR` for official filings and XBRL company facts.
  - `Stooq CSV` as EOD fallback requiring `STOOQ_API_KEY`.
  - `Alpaca Basic` and `Alpha Vantage` as inactive optional adapters.
- Added provider abstraction layer:
  - `titan_integration\data_providers`
- Added provider probe:
  - `scripts\probe_data_providers.py`
- Ran provider probe in Docker:
  - `yfinance` returned NVDA OHLCV bars.
  - `SEC EDGAR` returned NVDA CIK, facts, and recent filings.
  - `Stooq` correctly reported missing `STOOQ_API_KEY`.
- Added data-provider ADR:
  - `docs\ADR-0002-free-data-provider-stack.md`
- Configured environment placeholders in ignored `TradingAgents\.env`:
  - `SEC_EDGAR_USER_AGENT="TitanTradingResearch/0.1 Steve <your-email>"`
  - `STOOQ_API_KEY=`
- Added root `.gitignore` to keep local data, corpora, outputs, packets, Graphify artifacts, logs, caches, embeddings, and environment files out of version control.
- Reviewed the IBKR Quant historical market data source article and recorded its implications for provider selection.
- Added data/Graphify separation ADR:
  - `docs\ADR-0003-data-and-graphify-separation.md`
- Implemented Titan Validation Packet Stage 1:
  - `titan_integration\validation_packet.py`
  - `scripts\build_stage1_validation_packet.py`
- Generated Stage 1 packet for `NVDA` / `2026-05-01`:
  - `research_packets\stage1\NVDA_2026-05-01_stage1_validation_packet.json`
  - `research_packets\stage1\NVDA_2026-05-01_stage1_validation_packet.md`
- Added Stage 1 documentation:
  - `docs\stage1-validation-packet-2026-05-02.md`
- Stage 1 status:
  - Overall: `Conditional - Pre-Compliance Only`
  - Compliance: `Not Titan-Compliant`
  - Supported claims: 5
  - Not Validated claims: 5
- Implemented Titan Validation Packet Stage 2:
  - `titan_integration\citation_retrieval.py`
  - `scripts\build_stage2_citation_packet.py`
- Added NVDA Stage 2 citation manifest:
  - `citation_manifests\nvda_2026-05-01_stage2_sources.json`
- Generated Stage 2 packet:
  - `research_packets\stage2\NVDA_2026-05-01_stage2_citation_packet.json`
  - `research_packets\stage2\NVDA_2026-05-01_stage2_citation_packet.md`
- Added Stage 2 documentation:
  - `docs\stage2-citation-packet-2026-05-02.md`
- Stage 2 claim outcomes:
  - Pentagon AI contract claim: `Supported`
  - Next earnings timing claim: `Supported`
  - Forward valuation claim: `Conditional`
  - Ecosystem proxy claims: `Conditional`
  - Macro/geopolitical claims: `Conditional`
- Implemented Titan Validation Packet Stage 2B:
  - `titan_integration\evidence_reinforcement.py`
  - `scripts\build_stage2b_reinforcement_packet.py`
- Added NVDA Stage 2B reinforcement manifest:
  - `citation_manifests\nvda_2026-05-01_stage2b_reinforcement.json`
- Generated Stage 2B packet:
  - `research_packets\stage2b\NVDA_2026-05-01_stage2b_reinforcement_packet.json`
  - `research_packets\stage2b\NVDA_2026-05-01_stage2b_reinforcement_packet.md`
- Added Stage 2B documentation:
  - `docs\stage2b-reinforcement-packet-2026-05-02.md`
- Stage 2B claim outcomes:
  - Supported claims: 9
  - Contradictory claims: 1
  - Ecosystem proxy claims strengthened from `Conditional` to `Supported` using primary and SEC-filed Micron and Vertiv evidence.
  - Macro/geopolitical claims strengthened from `Conditional` to `Supported` using official Federal Reserve sources and energy-market context.
  - Forward valuation claim moved from `Conditional` to `Contradictory` because stronger secondary valuation evidence conflicts with the TradingAgents forward P/E figure.
- Implemented Titan Validation Packet Stage 3:
  - `titan_integration\evidence_graph.py`
  - `scripts\build_stage3_evidence_graph.py`
- Generated deterministic Graphify-compatible evidence graph:
  - `research_packets\stage3_graphify\NVDA_2026-05-01\graph.json`
  - `research_packets\stage3_graphify\NVDA_2026-05-01\GRAPH_REPORT.md`
  - `research_packets\stage3_graphify\NVDA_2026-05-01\graph.html`
- Added Stage 3 documentation:
  - `docs\stage3-graphify-evidence-graph-2026-05-02.md`
- Stage 3 graph outcomes:
  - Nodes: 76
  - Edges: 127
  - Sources: 20
  - Residual gaps: 7
  - Computed metrics: 1
  - Claim statuses: 9 `Supported`, 1 `Contradictory`
  - No LLM semantic extraction was used; all edges are deterministic from structured packets and manifests.
- Upgraded Stage 3 `graph.html` into a self-contained interactive graph explorer:
  - Force-directed SVG layout
  - Node dragging
  - Pan and zoom
  - Search and node-type filtering
  - Click-to-inspect node attributes and relationships
  - Neighbor highlighting
  - Toggleable labels and edge labels
  - Clickable external source URLs in the inspector
  - Auto-settling physics after initial layout stabilization
  - Selected-node pinning for stable inspection
- Added one-step interactive graph share packaging:
  - `titan_integration\share_package.py`
  - `scripts\package_graph_share.py`
  - Generated package:
    - `research_packets\stage3_graphify\NVDA_2026-05-01\NVDA_2026-05-01_interactive_evidence_graph_share_package.zip`
  - Package includes `graph.html`, `graph.json`, `GRAPH_REPORT.md`, `README_SHARE.md`, and `share_manifest.json`.
- Implemented Titan Validation Packet Stage 2C:
  - `titan_integration\metric_reconciliation.py`
  - `scripts\build_stage2c_metric_reconciliation.py`
- Generated Stage 2C computable metric reconciliation packet:
  - `research_packets\stage2c\NVDA_2026-05-01_stage2c_metric_reconciliation_packet.json`
  - `research_packets\stage2c\NVDA_2026-05-01_stage2c_metric_reconciliation_packet.md`
- Added Stage 2C documentation:
  - `docs\stage2c-computable-metric-reconciliation-2026-05-02.md`
- Stage 2C result:
  - Forward P/E status: `Computed - Source Conflict Preserved`
  - TradingAgents' `17.7x` forward P/E is mathematically coherent when using its own `$11.24` forward EPS estimate.
  - The `$11.24` EPS estimate is not externally sourced in the current packet.
  - NVIDIA guidance-derived annualized EPS scenario implies `29.31x`.
  - MarketBeat annualized EPS implies `28.35x`, and StockAnalysis reports `24.28x`.
  - Final Titan language must keep the original valuation claim blocked unless the `$11.24` forward EPS estimate is independently sourced.
- Refreshed Stage 3 graph with Stage 2C computed metric nodes:
  - `research_packets\stage3_graphify\NVDA_2026-05-01\graph.json`
  - `research_packets\stage3_graphify\NVDA_2026-05-01\GRAPH_REPORT.md`
  - `research_packets\stage3_graphify\NVDA_2026-05-01\graph.html`
- Implemented Stage 0 prior graph context loader:
  - `titan_integration\prior_graph_context.py`
  - `scripts\load_prior_graph_context.py`
- Generated NVDA prior context packet as of `2026-05-02`:
  - `research_packets\prior_context\NVDA_2026-05-02_prior_graph_context.json`
  - `research_packets\prior_context\NVDA_2026-05-02_prior_graph_context.md`
- Added prior context documentation:
  - `docs\stage0-prior-graph-context-loader-2026-05-02.md`
- Stage 0 prior context result:
  - Found prior NVDA graph for `2026-05-01`.
  - Loaded reusable supported claims.
  - Carried forward blocked items:
    - Forward valuation claim: `Contradictory`
    - Forward P/E: `Computed - Source Conflict Preserved`
- Implemented Evidence Delta Packet:
  - `titan_integration\evidence_delta.py`
  - `scripts\build_evidence_delta_packet.py`
- Generated initial NVDA evidence delta structural test:
  - `research_packets\evidence_delta\NVDA_2026-05-02_evidence_delta_packet.json`
  - `research_packets\evidence_delta\NVDA_2026-05-02_evidence_delta_packet.md`
- Added evidence delta documentation:
  - `docs\evidence-delta-packet-2026-05-02.md`
- Evidence delta result:
  - `Needs Fresh Evidence`: 9
  - `Still Blocked`: 2
  - This first packet compares the graph to itself as a structural test; a true repeated-ticker update requires a new fresh evidence graph.

- Implemented Stage 5 v2 HTML-preview-first report architecture:
  - `titan_integration\reader_status.py`
  - `titan_integration\report_preview_v2.py`
  - `scripts\build_stage5_v2_preview.py`
  - `docs\stage5-v2-html-preview-2026-05-02.md`
- Rebuilt fresh NVDA research chain through Stage 4 using run id:
  - `NVDA_20260502T150558Z`
- Generated Stage 5 v2 HTML preview only:
  - `research_packets\stage5_final_report\NVDA_20260502T150558Z\preview.html`
  - `research_packets\stage5_final_report\NVDA_20260502T150558Z\preview_manifest.json`
- Stage 5 v2 behavior:
  - Final Markdown/PDF generation paused pending visual approval.
  - Reader-facing status labels replace raw internal shorthand.
  - Fresh stance is `Overweight`, expressed as an evidence-gated overweight candidate with conditional entry monitoring.
  - Exact `17.7x` forward P/E point estimate remains blocked, while the broader forward P/E range is usable as an assumption-based scenario range.
  - HTML scan confirmed no unexplained `Not Titan-Compliant`, `TITAN-compliant`, or stale `Underweight` wording remains in the preview body.
- Enhanced Stage 5 v2 preview after visual review feedback:
  - Mirrored upstream TradingAgents report consolidation structure.
  - Preserved full baseline sections rather than summarizing them away.
  - Added richer Markdown-to-HTML rendering for headings, icons, tables, lists, horizontal rules, and final proposal blocks.
  - Corrected reader-facing date handling: research date is `May 2, 2026`, while `May 1, 2026` remains the market-data as-of/lookback end where applicable.
- Added non-interactive fresh TradingAgents runner:
  - `scripts\run_tradingagents_baseline.py`
- Ran true fresh NVDA repeated-ticker baseline:
  - Ticker/date: `NVDA` / `2026-05-02`
  - Provider/model: `deepseek` / `deepseek-v4-flash`
  - Output:
    - `outputs\deepseek_fresh_baseline\NVDA_2026-05-02_deepseek_fresh_baseline_summary.json`
    - `outputs\deepseek_fresh_baseline\NVDA_2026-05-02_deepseek_fresh_baseline_summary.md`
  - Fresh processed decision: `Underweight`
- Rebuilt fresh NVDA validation chain:
  - Stage 1:
    - `research_packets\stage1\NVDA_2026-05-02_stage1_validation_packet.json`
    - `research_packets\stage1\NVDA_2026-05-02_stage1_validation_packet.md`
  - Stage 2:
    - `research_packets\stage2\NVDA_2026-05-02_stage2_citation_packet.json`
    - `research_packets\stage2\NVDA_2026-05-02_stage2_citation_packet.md`
  - Stage 2B:
    - `research_packets\stage2b\NVDA_2026-05-02_stage2b_reinforcement_packet.json`
    - `research_packets\stage2b\NVDA_2026-05-02_stage2b_reinforcement_packet.md`
  - Stage 2C:
    - `research_packets\stage2c\NVDA_2026-05-02_stage2c_metric_reconciliation_packet.json`
    - `research_packets\stage2c\NVDA_2026-05-02_stage2c_metric_reconciliation_packet.md`
  - Stage 3 graph:
    - `research_packets\stage3_graphify\NVDA_2026-05-02\graph.json`
    - `research_packets\stage3_graphify\NVDA_2026-05-02\GRAPH_REPORT.md`
    - `research_packets\stage3_graphify\NVDA_2026-05-02\graph.html`
- Generated fresh NVDA graph share package:
  - `research_packets\stage3_graphify\NVDA_2026-05-02\NVDA_2026-05-02_interactive_evidence_graph_share_package.zip`
- Rebuilt corrected prior NVDA graph after Stage 1 dynamic-claim fix:
  - `research_packets\stage3_graphify\NVDA_2026-05-01\graph.json`
  - `research_packets\stage3_graphify\NVDA_2026-05-01\GRAPH_REPORT.md`
  - `research_packets\stage3_graphify\NVDA_2026-05-01\graph.html`
- Ran true fresh evidence delta:
  - `research_packets\evidence_delta\NVDA_2026-05-02_evidence_delta_packet.json`
  - `research_packets\evidence_delta\NVDA_2026-05-02_evidence_delta_packet.md`
  - Delta counts:
    - `Unchanged Supported`: 6
    - `Updated`: 2
    - `Stale`: 2
    - `Still Blocked`: 1
  - Key delta:
    - TradingAgents final stance changed from `Hold` to `Underweight`.
    - Forward P/E moved from `Computed - Source Conflict Preserved` to `Not Computable - Missing Explicit Input`.
    - Forward valuation claim remains `Contradictory` and blocked.
- Added wrapper robustness fixes:
  - Stage 1 stance claims are now generated dynamically from the run result.
  - Stage 1 reference-price claims now align to normalized market data instead of a hard-coded prior value.
  - Stage 2C now emits `Not Computable - Missing Explicit Input` instead of failing when a ratio cannot be recomputed.
  - Delta normalization now treats TradingAgents stance as one stable item so changes appear as `Hold -> Underweight`.
- Added research-cycle metadata model:
  - `titan_integration\research_cycle.py`
  - Every rebuilt Stage 1, Stage 2, Stage 2B, Stage 2C, Stage 3 graph, and delta artifact now carries `research_cycle` metadata.
  - The metadata separates:
    - `research_run_id`
    - `research_generated_at_utc`
    - `research_generated_at_local`
    - `requested_analysis_date`
    - `market_data_as_of`
    - `session_context`
  - Fresh NVDA graph header now displays `Research Run` separately from `Market Data As Of`.
- Added research-cycle archive generator:
  - `scripts\archive_research_cycle.py`
  - Generated archive:
    - `research_cycles\NVDA_20260502T112932Z`
  - Archive includes 54 artifacts and a `research_cycle_manifest.json`.
- Implemented Titan Validation Packet Stage 4:
  - `titan_integration\horizon_validation.py`
  - `scripts\build_stage4_horizon_validation.py`
- Generated Stage 4 horizon validation packet:
  - `research_packets\stage4_horizon_validation\NVDA_20260502T112932Z_stage4_horizon_validation_packet.json`
  - `research_packets\stage4_horizon_validation\NVDA_20260502T112932Z_stage4_horizon_validation_packet.md`
- Added Stage 4 documentation:
  - `docs\stage4-horizon-validation-2026-05-02.md`
- Stage 4 result:
  - Validated Trading Horizon: `Conditional: Swing`
  - Intraday / Day Trading: `Not Validated`
  - Swing: `Conditional`
  - Positional: `Not Validated`
  - Long-Term Investment: `Not Validated`
  - Stance delta: `Hold -> Underweight`
  - Self-audit passed for no full-compliance claim, no timeframe mixing, blocked-evidence preservation, and independent evaluation of all four horizons.
- Implemented Stage 1A user-supplied evidence ingestion:
  - `titan_integration\user_evidence.py`
  - `scripts\build_stage1a_user_evidence_packet.py`
  - `inputs\README.md`
- Updated `.gitignore` to keep `inputs/**` local-only while preserving `inputs\README.md`.
- Integrated Stage 1A into Stage 1:
  - Stage 1 now includes `user_supplied_evidence_audit`.
  - Stage 1 source reliability table includes `user_supplied_inputs`.
  - Stage 1 adds a supported user-evidence claim only when files are actually present.
  - Stage 2 creates a `stage1_user_supplied_evidence` source only when Stage 1A file count is greater than zero.
- Verified Stage 1A with a temporary TradingView-style `5m` sample CSV:
  - Detected timestamp column, OHLCV columns, row count, selected row count, first/last timestamps, timeframe, and SHA-256 hash.
  - Removed the temporary sample after verification.
- Added Stage 1A documentation:
  - `docs\stage1a-user-evidence-ingestion-2026-05-02.md`
- Implemented Stage 1B user technical feature extraction:
  - `titan_integration\user_technical_features.py`
  - `scripts\build_stage1b_user_technical_features_packet.py`
  - Output:
    - `research_packets\stage1b_user_technical_features\NVDA_2026-05-02_stage1b_user_technical_features_packet.json`
    - `research_packets\stage1b_user_technical_features\NVDA_2026-05-02_stage1b_user_technical_features_packet.md`
- Stage 1B extracts from user CSVs:
  - `time`
  - `open`, `high`, `low`, `close`
  - `Rolling VWAP`
  - `Upper band 1`, `Lower band 1`, `Upper band 2`, `Lower band 2`, `Upper band 3`, `Lower band 3`
  - duplicate `MA` columns, with the second normalized to `MA_2`
  - `Volume`, `Volume MA`
  - `RSI`, `RSI-based MA`
  - `Regular Bullish`, `Regular Bullish Label`
  - `Regular Bearish`, `Regular Bearish Label`
  - `ATR`
  - `ADX`
- Stage 1B derived features:
  - VWAP position
  - volume regime
  - RSI regime
  - ATR percent of close
  - ADX trend-strength regime
  - moving-average position
  - band position
  - recent bullish/bearish divergence counts
  - multi-timeframe technical read
- Tightened research-cycle input handling:
  - Stage 1 performs external provider retrieval first.
  - Stage 1 then scans the local asset-specific input folder for user-supplied evidence.
  - Stage 1B reuses the Stage 1A scan result from the same run instead of re-scanning the registry.
  - If no relevant local files are present, the workflow proceeds with externally sourced data only.
- Added Stage 1B documentation:
  - `docs\stage1b-user-technical-feature-extraction-2026-05-02.md`
- Implemented Stage 0A universal research request resolution:
  - `titan_integration\universal_research.py`
  - `scripts\build_stage0a_research_resolution.py`
  - `Equity` resolves as `Implemented` and routes to `equity_v1`.
  - `ETF`, `Index`, `Crypto`, `FX`, `Futures`, `Commodity`, `Equity-Option`, `ETF-Option`, `Index-Option`, and `CFD` resolve as `Registered But Not Implemented`.
  - Unsupported profiles stop gracefully and do not run the equity workflow.
- Added Stage 0A and publication documentation:
  - `docs\ADR-0004-universal-research-framework.md`
  - `docs\ADR-0005-github-publication-and-attribution.md`
  - `docs\universal-research-request-schema.md`
  - `docs\instrument-registry.md`
  - `docs\github-publication-checklist.md`
- Prepared GitHub-safe wrapper publication files:
  - `README.md`
  - `LICENSE`
  - `NOTICE.md`
  - `SECURITY.md`
  - `.env.example`
  - `scripts\publication_safety_check.py`
- Hardened root `.gitignore`:
  - nested `TradingAgents/` clone remains local-only.
  - secrets, corpora, data, user inputs, generated packets, graphs, archives, caches, and provider outputs remain excluded.
- Verified Stage 0A and publication safety:
  - `NVDA` / `Equity` resolved as `Implemented` with active profile `equity_v1`.
  - `BTC` / `Crypto` resolved as `Registered But Not Implemented` with active profile `crypto_planned`.
  - Unsupported crypto request stops gracefully and does not run the equity workflow.
  - `python scripts\publication_safety_check.py` passed.
- Added core validation outcome taxonomy:
  - `titan_integration\validation_outcomes.py`
  - `docs\ADR-0006-validation-outcome-taxonomy.md`
  - `docs\validation-outcome-taxonomy.md`
  - Outcomes:
    - `Validated`
    - `Conditional`
    - `Conditional Candidate`
    - `Not Validated`
    - `Blocked`
    - `Usable Range - Assumption-Based`
- Updated Stage 2C valuation logic:
  - The specific `17.7x` forward P/E point estimate remains `Blocked`.
  - The broader forward P/E valuation range is now `Usable Range - Assumption-Based`.
  - Current usable range: approximately `24.28x` to `29.14x`.
  - The range is usable for scenario framing with assumptions; it does not validate the unsupported `17.7x` point estimate.
- Implemented Stage 2D stale claim refresh:
  - `titan_integration\stale_claim_refresh.py`
  - `scripts\build_stage2d_stale_claim_refresh_packet.py`
  - Output:
    - `research_packets\stage2d_stale_claim_refresh\NVDA_2026-05-02_stage2d_stale_claim_refresh_packet.json`
    - `research_packets\stage2d_stale_claim_refresh\NVDA_2026-05-02_stage2d_stale_claim_refresh_packet.md`
  - Refreshed stale claims:
    - `Next earnings timing claim`
    - `Pentagon AI contract claim`
  - Status counts:
    - `Supported`: `2`
  - Source reachability:
    - `nvidia_q1_fy2027_call`: `Available`, HTTP 200
    - `marketbeat_nvda_q1_2027`: `Reachability Restricted`, HTTP 403
    - `dow_classified_ai_agreements`: `Reachability Restricted`, HTTP 403
- Integrated Stage 2D into Stage 3 graph generation:
  - Stage 3 now accepts optional Stage 2D stale-refresh packets.
  - Refreshed stale claims are graph nodes with refreshed source links.
- Rebuilt NVDA graph, delta, Stage 4, and archive after Stage 2D:
  - Stage 3 graph:
    - Nodes: `91`
    - Links: `164`
    - Refreshed claims: `2`
  - Evidence delta after validation-taxonomy update:
    - `Newly Discovered`: `4`
    - `Still Blocked`: `1`
    - `Unchanged Supported`: `8`
    - `Updated`: `2`
    - `Stale`: `0`
  - Stage 4:
    - Research run id: `NVDA_20260502T123138Z`
    - Validated Trading Horizon: `Conditional Candidate: Intraday / Day Trading, Swing, Positional`
    - Intraday / Day Trading: `Conditional Candidate`
    - Swing: `Conditional`
    - Positional: `Conditional Candidate`
    - Long-Term Investment: `Not Validated`
    - Stale claim count: `0`
    - Assumption-based valuation range present: `true`
  - Archive:
    - `research_cycles\NVDA_20260502T123138Z`
- Added Stage 2D documentation:
  - `docs\stage2d-stale-claim-refresh-2026-05-02.md`
- Added Stage 5 final report quality gate as core business logic:
  - `titan_integration\report_quality.py`
  - `docs\ADR-0007-final-report-quality-gate.md`
  - `docs\final-report-quality-gate.md`
  - The rule preserves useful baseline-report structure while requiring every final-report section to be fact-checked, source-audited, and routed through Titan evidence status.
  - Required sections:
    - Report Metadata
    - Executive Decision Summary
    - Technical Analysis
    - User-Supplied Multi-Timeframe Technical Evidence, when present
    - Fundamental Analysis
    - Valuation Section
    - News, Catalysts, Macro, and Narrative Context
    - Evidence Graph and Source Audit
    - Validated Trading Horizon
    - Self-Audit and Internal Checks
  - Baseline reports are now explicitly treated as structured inputs, not final authority.
- Implemented Stage 5 final report exporter:
  - `titan_integration\report_exporter.py`
  - `scripts\build_stage5_final_report.py`
  - Added documentation:
    - `docs\stage5-final-report-exporter-2026-05-02.md`
  - Generated NVDA Stage 5 artifacts:
    - `research_packets\stage5_final_report\NVDA_20260502T123138Z\NVDA_20260502T123138Z_stage5_final_report.md`
    - `research_packets\stage5_final_report\NVDA_20260502T123138Z\NVDA_20260502T123138Z_stage5_final_report.pdf`
    - `research_packets\stage5_final_report\NVDA_20260502T123138Z\NVDA_20260502T123138Z_stage5_final_report_manifest.json`
  - Rendered PDF pages to PNG for visual QA:
    - `research_packets\stage5_final_report\NVDA_20260502T123138Z\rendered_pages`
  - Stage 5 output uses the May 1 full baseline as the structural baseline reference and the May 2 fresh evidence chain for updated stance, valuation, graph, delta, and horizon validation.
- Implemented Stage 1A duplicate-ingestion protection:
  - Local-only registry:
    - `normalized_data\user_evidence_registry.json`
  - Unchanged CSVs are fingerprinted by SHA-256 and marked `Already Ingested` on repeat scans.
  - Changed CSVs receive a new hash and are marked `New`.
  - Registry preserves original `ingested_at_utc` and updates `last_seen_at_utc`.
- Ingested real NVDA TradingView CSV files from:
  - `inputs\NVDA\2026-05-02`
  - Detected seven timeframes:
    - `15m`
    - `1d`
    - `1h`
    - `1mo`
    - `1w`
    - `4h`
    - `5m`
  - File count: `7`
  - New file count on verified repeat scan: `0`
  - Already ingested count on verified repeat scan: `7`
  - Latest user evidence timestamp: `2026-05-01T22:55:00`
  - Total rows observed: `20,771`
  - Total rows selected for context: `2,894`
- Rebuilt canonical Stage 1 for `NVDA` / `2026-05-02` with real user evidence:
  - `research_packets\stage1\NVDA_2026-05-02_stage1_validation_packet.json`
  - `research_packets\stage1\NVDA_2026-05-02_stage1_validation_packet.md`
  - Current user evidence status: `User Evidence Available`
- Rebuilt downstream packets with real user evidence:
  - Stage 2:
    - `research_packets\stage2\NVDA_2026-05-02_stage2_citation_packet.json`
    - `research_packets\stage2\NVDA_2026-05-02_stage2_citation_packet.md`
  - Stage 2B:
    - `research_packets\stage2b\NVDA_2026-05-02_stage2b_reinforcement_packet.json`
    - `research_packets\stage2b\NVDA_2026-05-02_stage2b_reinforcement_packet.md`
  - Stage 2C:
    - `research_packets\stage2c\NVDA_2026-05-02_stage2c_metric_reconciliation_packet.json`
    - `research_packets\stage2c\NVDA_2026-05-02_stage2c_metric_reconciliation_packet.md`
  - Stage 3:
    - `research_packets\stage3_graphify\NVDA_2026-05-02\graph.json`
    - `research_packets\stage3_graphify\NVDA_2026-05-02\GRAPH_REPORT.md`
    - `research_packets\stage3_graphify\NVDA_2026-05-02\graph.html`
  - Evidence Delta:
    - `research_packets\evidence_delta\NVDA_2026-05-02_evidence_delta_packet.json`
    - `research_packets\evidence_delta\NVDA_2026-05-02_evidence_delta_packet.md`
  - Stage 4:
    - `research_packets\stage4_horizon_validation\NVDA_20260502T122415Z_stage4_horizon_validation_packet.json`
    - `research_packets\stage4_horizon_validation\NVDA_20260502T122415Z_stage4_horizon_validation_packet.md`
- Current refreshed graph outcome:
  - Research run id: `NVDA_20260502T122415Z`
  - Research timestamp: `2026-05-02T12:24:15Z`
  - Market data as of: `2026-05-01`
  - Market data granularity: `1d`
  - User evidence latest timestamp: `2026-05-01T22:55:00`
  - User technical latest timestamp: `2026-05-01T22:55:00`
  - Nodes: `87`
  - Links: `151`
  - Sources: `22`
  - Claims: `12`
  - User technical feature nodes: `7`
  - User technical multi-timeframe read nodes: `1`
- Current evidence delta outcome:
  - `Newly Discovered`: `4`
  - `Updated`: `1`
  - `Unchanged Supported`: `6`
  - `Stale`: `2`
  - `Still Blocked`: `2`
  - New items include:
    - `User-supplied multi-timeframe evidence is available for supplemental validation.`
    - user-derived multi-timeframe technical features
    - user-derived VWAP positioning
    - user-derived momentum and trend-strength features
- Current Stage 4 result:
  - Validated Trading Horizon: `Conditional: Swing`
  - Compliance: `Not Titan-Compliant`
  - Intraday / Day Trading: `Not Validated`
  - Swing: `Conditional`
  - Positional: `Not Validated`
  - Long-Term Investment: `Not Validated`
  - Intraday and Swing rationales now include user-derived VWAP, RSI, ADX, ATR, volume, MA, and divergence evidence.
- Generated refreshed interactive graph share package:
  - `research_packets\stage3_graphify\NVDA_2026-05-02\NVDA_2026-05-02_interactive_evidence_graph_share_package.zip`
- Archived refreshed research cycle:
  - `research_cycles\NVDA_20260502T122415Z`
- Refined Stage 5 v2 HTML preview after baseline-preservation review:
  - Updated:
    - `titan_integration\report_preview_v2.py`
    - `docs\stage5-v2-html-preview-2026-05-02.md`
  - Regenerated preview only:
    - `research_packets\stage5_final_report\NVDA_20260502T150558Z\preview.html`
    - `research_packets\stage5_final_report\NVDA_20260502T150558Z\preview_manifest.json`
  - Added `Baseline Internal Conclusion Map` so preserved baseline `HOLD`,
    `BUY`, and `Overweight` role-specific proposals are visible but no longer
    appear as unresolved final-report contradictions.
  - Restored baseline wrapper labels to baseline section names, including
    `Trader Investment Plan`.
  - Removed heuristic heading icons, H-label inserts, and proposal labels from
    rendered baseline content; Titan commentary now appears beneath preserved
    baseline sections or in separate overlay sections.
  - Renamed Titan-added sections as `TITAN Addendum` overlays and removed
    duplicated Titan-added sentiment / bull-bear sections because the preserved
    baseline already contains those sections.
  - Verification result:
    - Fresh-baseline sections present: `7`
    - Missing rendered baseline titles: `0`
    - Baseline proposal map rows: `7`
    - Final Markdown/PDF export remains paused pending user approval.
- Implemented Stage 5 v2 final export after preview approval:
  - Added:
    - `scripts\export_stage5_v2_final_report.py`
  - Generated:
    - `research_packets\stage5_final_report\NVDA_20260502T150558Z\NVDA_20260502T150558Z_stage5_v2_final_report.html`
    - `research_packets\stage5_final_report\NVDA_20260502T150558Z\NVDA_20260502T150558Z_stage5_v2_final_report.md`
    - `research_packets\stage5_final_report\NVDA_20260502T150558Z\NVDA_20260502T150558Z_stage5_v2_final_report.pdf`
    - `research_packets\stage5_final_report\NVDA_20260502T150558Z\NVDA_20260502T150558Z_stage5_v2_final_report_manifest.json`
  - Rendered PDF pages for visual QA:
    - `research_packets\stage5_final_report\NVDA_20260502T150558Z\rendered_pages_v2`
    - Contact sheet:
      - `output\playwright\stage5_v2_pdf_contact_sheet.png`
  - PDF QA result:
    - Page count: `39`
    - PDF size: `3,053,669` bytes
    - `Trader Investment Plan` present
    - `Trading Team Plan` absent
    - `Baseline Internal Conclusion Map` present
    - `TITAN Addendum` sections present
- Added Stage 5 v2 themed PDF enhancement:
  - Updated:
    - `titan_integration\report_preview_v2.py`
    - `scripts\export_stage5_v2_final_report.py`
  - Added reusable instrument / asset-class branding:
    - ticker identity badge
    - local issuer logo when available
    - company name in hero banner
    - asset-class label
    - equity green / deep-blue institutional palette
    - print color preservation for PDF export
  - Regenerated final HTML, Markdown, and PDF.
  - Refreshed rendered PDF pages:
    - `research_packets\stage5_final_report\NVDA_20260502T150558Z\rendered_pages_v2`
  - Refreshed themed contact sheet:
    - `output\playwright\stage5_v2_pdf_contact_sheet_themed.png`
  - Themed PDF QA result:
    - Page count: `39`
    - PDF size: `3,125,032` bytes
    - `final PDF paused pending review` absent
    - `NVIDIA Corporation` present
    - `Trader Investment Plan` present
    - `Trading Team Plan` absent
- Added local NVDA issuer logo asset:
  - `assets\logos\NVDA.svg`
  - `assets\logos\logo_manifest.json`
  - Embedded as a base64 SVG in the final report so the HTML/PDF remains
    self-contained and offline-friendly.
  - Documented trademark / brand-use caution in the Stage 5 v2 docs.
- Added reusable logo resolver:
  - `titan_integration\logo_assets.py`
  - Integrated into:
    - `scripts\export_stage5_v2_final_report.py`
    - `titan_integration\report_preview_v2.py`
  - Resolution order:
    - local approved logo
    - issuer official website discovery/acquisition
    - ticker badge fallback
  - Final report manifest now records `logo_resolution`.
- Added first-page reader-facing legal notice:
  - Research-only / not financial advice wording.
  - Issuer-logo / no affiliation, sponsorship, approval, or endorsement wording.
  - Regenerated final PDF and rendered pages.
  - Latest themed/legal PDF QA result:
    - Page count: `39`
    - PDF size: `3,089,514` bytes
    - `Research-only` present
    - `Logo notice` present
    - `does not imply affiliation` present
- Added Stage 3F / Stage 5 graph overlay and report rendering fixes:
  - Updated:
    - `titan_integration\report_preview_v2.py`
    - `titan_integration\evidence_graph.py`
    - `scripts\build_stage3_evidence_graph.py`
  - Added documentation:
    - `docs\stage3f-stage5-graph-overlay-and-report-rendering-fixes-2026-05-03.md`
  - Titan Addendum C fixes:
    - Timeframes sorted smallest to largest: `5m`, `15m`, `1h`, `4h`, `1d`, `1w`, `1mo`.
    - Table columns now use fixed layout and wrap instead of clipping.
    - Signal dots are standardized CSS indicators across VWAP, RSI, ADX, and Volume.
  - Titan Addendum J fixes:
    - Citation table uses fixed layout and wrapped columns.
    - Rows with URL values render as visually distinct hyperlinks.
  - Stage 3F graph overlay now includes:
    - horizon decision nodes
    - final report section nodes
    - legal notice node
    - logo attribution node
    - final report artifact node
    - traceability edges from report sections back to evidence nodes
  - Rebuilt NVDA graph:
    - 153 nodes
    - 393 edges
    - 22 sources
    - 6 residual gaps
    - 4 horizon decision nodes
    - 12 report section nodes
  - Generated updated v3 final report artifacts because the original final PDF file was locked by an external viewer:
    - `research_packets\stage5_final_report\NVDA_20260502T150558Z\NVDA_20260502T150558Z_stage5_v2_final_report_v3.html`
    - `research_packets\stage5_final_report\NVDA_20260502T150558Z\NVDA_20260502T150558Z_stage5_v2_final_report_v3.md`
    - `research_packets\stage5_final_report\NVDA_20260502T150558Z\NVDA_20260502T150558Z_stage5_v2_final_report_v3.pdf`
    - `research_packets\stage5_final_report\NVDA_20260502T150558Z\NVDA_20260502T150558Z_stage5_v2_final_report_v3_manifest.json`
  - Visual QA artifacts:
    - `output\playwright\stage5_v3_addendum_c_textfrag.png`
    - `output\playwright\stage5_v3_addendum_j_textfrag.png`
    - `output\playwright\stage3_graph_stage5_overlay_check.png`
    - `output\playwright\stage5_v3_pdf_view_check_wait.png`
- Added graph UI interaction fixes:
  - Node-type dropdown now filters and auto-fits the graph canvas.
  - Legend pills are clickable node-type filters.
  - Dashboard cards are clickable shortcuts:
    - `Nodes` clears node-type/search filters.
    - `Sources`, `Metrics`, `Residual Gaps`, and `Claims` filter to the corresponding node type.
    - `Edges` turns on edge labels.
  - Filtered views show the selected node type plus one-hop context nodes and relevant edges.
  - Interaction QA passed:
    - all nodes: 153 nodes / 393 edges
    - dropdown `computed_metric`: 13 nodes / 12 edges
    - legend `claim`: 58 nodes / 110 edges
    - dashboard `source`: 75 nodes / 114 edges
  - Added screenshots:
    - `output\playwright\stage3_graph_filter_computed_metric.png`
    - `output\playwright\stage3_graph_filter_claim_legend.png`
    - `output\playwright\stage3_graph_filter_source_stat.png`

## Open Questions

- Should the next backend comparison include hosted Gemini after the DeepSeek fuller baseline?
- Should output be stored inside TradingAgents' default `~/.tradingagents` volume or mapped into the integration workspace for easier audit access?
- No Alpha Vantage API key is currently configured in `TradingAgents\.env`.
- `SEC_EDGAR_USER_AGENT` is configured in the ignored local `.env`.
- `STOOQ_API_KEY` remains blank; Stooq fallback will stay inactive until the user configures it.

## Next Steps

1. Optionally configure `STOOQ_API_KEY` for EOD fallback.
2. Rotate the DeepSeek API key after testing.
3. Review Stage 0A NVDA equity and unsupported crypto resolution packets.
4. Run publication safety check before any GitHub initialization or push.
5. Resolve or explicitly preserve the remaining valuation blocker:
   - `Forward valuation claim` / specific `17.7x` point estimate
6. Review the generated Stage 5 v3 Markdown/PDF and Stage 3F graph overlay.
7. Run publication safety check again before any GitHub initialization or push.

## Current Recommendation

Stage 0A universal request resolution, Stage 1A user-evidence ingestion, duplicate-ingestion protection, Stage 1B technical feature extraction, source-led Stage 2/2B ledger validation, Stage 2D stale-claim refresh, Stage 5 final-report quality gating/export, and GitHub-safe wrapper publication preparation are implemented. Agent prose can no longer validate external facts without matching ledger source records in Stage 2 and Stage 2B. NVDA no longer has stale catalyst or earnings-timing claims in the latest delta. The generated Stage 5 report preserves the remaining valuation blocker with explicit business rationale and uses the forward P/E range only as an assumption-based range.
