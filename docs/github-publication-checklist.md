# GitHub Publication Checklist

Date: 2026-05-03

## Required Publication Model

Publish as a new wrapper repository. Do not publish the current workspace as a
monorepo snapshot.

## Required Included Files

- `README.md`
- `LICENSE`
- `NOTICE.md`
- `SECURITY.md`
- `.gitignore`
- `.env.example`
- `docs/`
- `scripts/`
- `titan_integration/`
- `inputs/README.md`
- non-secret `citation_manifests/` files, if needed for examples

## Required Exclusions

Do not publish:

- `TradingAgents/`
- `TradingAgents/.env`
- `.env`
- API keys
- `data/`
- `corpus/`
- user files under `inputs/` except `inputs/README.md`
- `outputs/`
- `output/`
- `research_materials/`
- `research_packets/`
- `research_cycles/`
- `normalized_data/`
- `provider_cache/`
- `assets/`
- `test-results/`
- `playwright-report/`
- `.tmp*`
- `logs/`
- `embeddings/`
- SQLite or database files
- generated Graphify outputs
- Titan private corpora

For normal local development, these private/generated folders may remain inside
`D:\Projects\CodeX\TradingAgents_Integration` because `.gitignore` excludes
them. This keeps the workflow convenient while still protecting GitHub from
private artifacts.

Use `git status --short --ignored` before pushing:

- `!!` means ignored and not pushed.
- `??` means untracked and must be reviewed before pushing.
- `A`, `M`, or `D` means staged/tracked changes and must be intentional.

`D:\Projects\CodeX\TradingAgents_Integration_Data\` may be used as an optional
backup/archive folder, but it is not required for ordinary development.

## Required Checks

Run before any GitHub push:

```powershell
python scripts\publication_safety_check.py
```

The check must pass.

## Required Attribution

The public repository must:

- credit TauricResearch / TradingAgents
- link to https://github.com/TauricResearch/TradingAgents
- cite https://arxiv.org/abs/2412.20138
- preserve the verified Apache-2.0 license terms currently present in the
  local upstream TradingAgents clone and this wrapper
- state that the Titan wrapper is independent unless an affiliation is
  explicitly established
- include a research-only and not-financial-advice disclaimer

If the upstream repository changes its license in the future, re-check the
upstream license before publication and update `README.md`, `NOTICE.md`, and
`LICENSE` accordingly. Do not state MIT attribution unless the upstream license
has been verified as MIT at publication time.

## Publication Gate

No GitHub push should occur until:

- Stage 0A generic equity resolution passes
- Stage 0A unsupported-profile resolution passes
- Stage 5 v2 report rendering passes for the latest equity regression run
- publication safety check passes
- docs are reviewed
- local secrets have been removed or rotated if exposure is possible
- all private material remains local-only
