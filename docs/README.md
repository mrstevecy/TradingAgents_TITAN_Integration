# TradingAgents Integration Documentation

This directory is the internal documentation set for the TradingAgents integration project.
It is part of the project itself, not a temporary note area.

## Purpose

- Preserve architectural decisions and rationale.
- Track what has been reviewed, implemented, verified, deferred, or rejected.
- Maintain traceability between TradingAgents, Titan OS 2.9, Titan DTP 1.6, the Activation Trigger Framework, and Graphify corpora.
- Support future audits, implementation iterations, and report-quality governance.

## Current Documentation

- `ADR-0001-thin-wrapper-architecture.md` - decision to use a clean upstream core plus Titan wrapper.
- `ADR-0002-free-data-provider-stack.md` - accepted free data-provider stack and normalized adapter approach.
- `ADR-0003-data-and-graphify-separation.md` - local-only data separation and governed Graphify integration.
- `ADR-0004-universal-research-framework.md` - Stage 0A universal request and instrument registry decision.
- `ADR-0005-github-publication-and-attribution.md` - publication model, attribution, and safety decision.
- `ADR-0006-validation-outcome-taxonomy.md` - core validated / conditional / blocked / usable-range taxonomy.
- `ADR-0007-final-report-quality-gate.md` - evidence-gated final report quality standard.
- `universal-research-request-schema.md` - canonical multi-asset research request shape.
- `instrument-registry.md` - implemented and planned instrument profiles.
- `validation-outcome-taxonomy.md` - business-facing validation outcome definitions used across research stages.
- `final-report-quality-gate.md` - required final report sections and section-level evidence gates.
- `USER_MANUAL_STAGE0A_TO_STAGE5.md` - business-user operating manual with exact PowerShell commands for Stage 0A through Stage 5.
- `global-equity-evidence-enforcement-2026-05-04.md` - code-level equity evidence scan, resolver, contamination, debate, PM sanity, and MSFT regression enforcement record.
- `MSFT_QA_global_report_hardening_2026-05-04.md` - global Stage 5 report hardening after the MSFT QA review, including dynamic RAG repair traces, diagnostic-mode gating, canonical report context, one final decision object, source-permission checks, numeric artifact rejection, and business-readable section titles.
- `github-readiness-final-audit-2026-05-03.md` - final repository-wide documentation, code, workflow, attribution, and confidentiality audit before GitHub publication.
- `github-publication-checklist.md` - required checks before any GitHub push.
- `stage0-prior-graph-context-loader-2026-05-02.md` - prior graph continuity layer for repeat ticker research.
- `review-summary-2026-05-02.md` - structured review of repo, paper, wiki/video material, and workflow fit.
- `implementation-roadmap.md` - staged build and integration plan.
- `baseline-runbook.md` - clean upstream baseline execution procedure.
- `backend-options-assessment-2026-05-02.md` - Codex/API/local model backend assessment.
- `local-inference-hardware-assessment-2026-05-02.md` - local model inventory, hardware capacity, and inference decision path.
- `local-lmstudio-dryrun-2026-05-02.md` - first LM Studio endpoint and TradingAgents dry-run results.
- `deepseek-v4-flash-baseline-2026-05-02.md` - first hosted low-cost baseline that completed the market-only graph.
- `full-deepseek-baseline-2026-05-02.md` - four-analyst clean DeepSeek baseline output record.
- `baseline-quality-assessment-2026-05-02.md` - quality assessment against Titan requirements before wrapper implementation.
- `stage1-validation-packet-2026-05-02.md` - first Titan pre-compliance validation packet record.
- `stage2-citation-packet-2026-05-02.md` - citation retrieval and evidence-linking packet record.
- `stage2b-reinforcement-packet-2026-05-02.md` - evidence reinforcement layer that pursues closure of Conditional claims before Graphify.
- `stage2c-computable-metric-reconciliation-2026-05-02.md` - formula-based reconciliation for computable valuation and financial metrics.
- `stage2d-stale-claim-refresh-2026-05-02.md` - stale prior-claim refresh layer for repeated ticker research.
- `stage3-graphify-evidence-graph-2026-05-02.md` - deterministic Graphify-compatible evidence graph record.
- `evidence-delta-packet-2026-05-02.md` - prior-vs-fresh graph comparison layer before horizon validation.
- `stage5-final-report-exporter-2026-05-02.md` - Stage 5 Markdown/PDF final report exporter and generated NVDA artifacts.
- `status-register.md` - completed work, open questions, and next steps.

## Documentation Rules

- Record every material design decision as an ADR.
- Keep implementation notes concise and dated.
- Separate verified facts from assumptions.
- Do not treat TradingAgents output as Titan-validated unless it passes the Titan wrapper checks.
- Preserve useful baseline-report structure, but route final report language through evidence status, source audit, horizon validation, and self-audit.
- Preserve upstream-vs-wrapper boundaries so future upgrades remain manageable.
