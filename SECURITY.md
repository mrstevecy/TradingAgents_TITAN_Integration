# Security Policy

## Secrets

Do not commit API keys, provider tokens, `.env` files, private endpoints, local
research data, Titan corpora, Graphify outputs, user-supplied files, generated
reports, provider caches, or archived research cycles.

Use `.env.example` as the public template and keep the real `.env` local.

## Local-Only Directories

The following paths are intentionally excluded from publication:

- `TradingAgents/`
- `data/`
- `corpus/`
- `inputs/*` except `inputs/README.md`
- `outputs/`
- `research_materials/`
- `research_packets/`
- `research_cycles/`
- `normalized_data/`
- `provider_cache/`
- `logs/`
- `embeddings/`

## Pre-Publication Check

Before creating a GitHub repository or pushing commits, run:

```powershell
python scripts\publication_safety_check.py
```

The check must pass before publication.

## Reporting Issues

If a secret or private artifact is accidentally exposed, remove it immediately,
rotate the affected credential, and rewrite public history before sharing the
repository further.
