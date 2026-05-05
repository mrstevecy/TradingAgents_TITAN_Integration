# GitHub Readiness Final Audit

Date: 2026-05-03

## Scope

This audit covers the publishable TradingAgents Titan Integration wrapper:

- root publication files
- `docs/`
- `scripts/`
- `titan_integration/`
- `citation_manifests/`
- `inputs/README.md`

The nested `TradingAgents/` clone, generated research outputs, user inputs,
private corpora, provider caches, archives, local assets, temporary folders, and
runtime artifacts are local-only and must not be published.

## Publication Model

The repository should be published as a clean wrapper repository. It should not
be pushed as the current full workspace snapshot.

Required public boundary:

- Include wrapper code, documentation, safe templates, and attribution files.
- Exclude nested upstream source, secrets, local datasets, generated reports,
  graph outputs, research cycles, provider caches, and local logo/assets.
- Recreate or clone the upstream TradingAgents dependency separately during
  installation.

## Upstream Attribution and License

The local upstream TradingAgents clone and the wrapper currently contain
Apache-2.0 license text. Documentation now states the verified license as
Apache-2.0 and credits:

- TauricResearch and contributors
- https://github.com/TauricResearch/TradingAgents
- https://arxiv.org/abs/2412.20138

If the upstream project changes its license before publication, the license must
be re-verified directly from the upstream repository and `README.md`,
`NOTICE.md`, and `LICENSE` must be updated before push.

## Documentation Audit

Updated or verified:

- `README.md`
  - explains upstream lineage, current capability, direct user interfaces,
    environment model, configuration, workflow, outputs, evidence governance,
    publication safety, and research-only disclaimers
- `NOTICE.md`
  - credits upstream TradingAgents and describes the independent TITAN wrapper
- `SECURITY.md`
  - documents secret handling and local-only material
- `.env.example`
  - remains a placeholder-only template
- `docs/USER_MANUAL_STAGE0A_TO_STAGE5.md`
  - provides business-user PowerShell commands and folder/output instructions
- `docs/direct-user-interface-and-deployment-path.md`
  - clarifies CLI/script access today and future API boundary
- `docs/implementation-roadmap.md`
  - records the dependency-ordered universal asset-class roadmap
- `docs/stage3-graphify-evidence-graph-2026-05-02.md`
  - explains graph generation and evidence graph outputs
- `docs/evidence-led-validation-architecture-2026-05-03.md`
  - documents the source-led validation ledger and anti-hallucination controls
- `docs/github-publication-checklist.md`
  - updated with final exclusions, license caveat, and publication gates
- `docs/README.md`
  - indexes this audit and the current operating manual

## Workflow Audit

Active equity workflow:

1. Stage 0A resolves the request and confirms the asset profile.
2. TradingAgents baseline generates the multi-agent research state.
3. Stage 1 validates provider, filing, mandatory evidence, and user evidence.
4. Stage 1A ingests user documents and prevents duplicate evidence.
5. Stage 1B extracts multi-timeframe technical features from user CSV files.
6. Stage 2 links claims to timestamped citation records through the evidence
   ledger.
7. Stage 2B reinforces weak or missing evidence through ledger-gated source
   records.
8. Stage 2C reconciles computable financial and valuation metrics.
9. Stage 2D refreshes stale repeated-research claims.
10. Stage 3 builds deterministic evidence graph JSON and HTML.
11. Stage 4 validates horizons independently.
12. Stage 5 v2 renders HTML, Markdown, PDF, and manifest outputs.

Current direct operating path is CLI/script execution, not Codex. No HTTP API is
currently committed.

## Hardcoding Review

The active Stage 5 v2 path and evidence-led validation path are ticker-generic.
The latest equity regressions covered `NVDA`, `MU`, and `MSFT` without adding
ticker-specific business logic.

Remediation completed during this audit:

- Removed a ticker-specific fallback in `titan_integration/report_preview_v2.py`.
- Replaced sector-overfit ecosystem-proxy detection in
  `titan_integration/validation_packet.py` with generic ecosystem, supplier,
  customer, sector, industry, and proxy-evidence language.
- Neutralized legacy `titan_integration/report_exporter.py` hardcoded
  NVDA/NVIDIA narrative and source path text so the old exporter no longer emits
  ticker-specific report conclusions.
- Replaced the `inputs/README.md` regression-specific example with a generic
  ticker/date folder pattern.

Remaining ticker strings in publishable code are command-line example defaults,
test/probe examples, or documentation/history references. Production runs should
pass explicit ticker, date, input-folder, and run-id arguments as shown in the
user manual.

## Confidentiality Audit

Publication exclusions are enforced in `.gitignore` and
`scripts/publication_safety_check.py` for:

- `.env` and nested upstream `.env` files
- `TradingAgents/`
- `data/`
- `inputs/` except `inputs/README.md`
- `corpus/`
- `output/` and `outputs/`
- `research_materials/`
- `research_packets/`
- `research_cycles/`
- `normalized_data/`
- `provider_cache/`
- `assets/`
- `test-results/`
- `playwright-report/`
- temporary `.tmp*` paths
- logs, caches, embeddings, SQLite/database files, and Graphify outputs

Mandatory pre-push command:

```powershell
python scripts\publication_safety_check.py
```

Important local finding: the ignored nested upstream file `TradingAgents/.env`
contains a real provider key in this workspace. It is outside the publication
candidate set, but the key should be removed locally and rotated before any
publication step if there is any possibility it was exposed.

## Code Verification

Required checks before final push:

```powershell
python scripts\publication_safety_check.py
python -B -m compileall -q scripts titan_integration
cd TradingAgents
uv run pytest -q
```

Final verification result after this audit pass:

- `120 passed, 42 subtests passed`

The publication safety check and `compileall` syntax check also passed after the
cleanup changes.

## Current Limitations

- Only `Equity v1` is implemented.
- ETF, index, listed options, crypto, FX, futures, commodity, and CFD profiles
  are registered but not implemented.
- The current user interface is CLI/script based.
- No production API server or web UI is committed yet.
- Citation manifests are still part of the controlled evidence workflow; broader
  automated retrieval remains the next production-hardening step.

## GitHub Readiness Conclusion

Update 2026-05-04: GitHub publication remains paused while the MSFT global
equity enforcement patch is fully verified. The wrapper is structurally ready
for publication only after:

- local secrets are removed/rotated
- the publication safety check passes
- syntax checks pass
- the upstream `uv run pytest -q` suite passes
- the global equity evidence enforcement regression tests pass
- the actual pushed repository contains only the public wrapper candidate, not
  the full local workspace snapshot

No ticker-specific fixes should be required for future equity tickers if runs
use the documented generic Stage 0A through Stage 5 workflow and supply explicit
runtime arguments.
