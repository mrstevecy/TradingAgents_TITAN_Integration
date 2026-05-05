# ADR-0005: GitHub Publication and Attribution

Date: 2026-05-02

## Status

Accepted

## Context

The integration workspace contains local data, private corpora, user-provided
inputs, generated research packets, graph outputs, provider caches, and a
nested upstream TradingAgents clone. Publishing the workspace as-is would risk
exposing confidential or generated material and would blur the boundary between
the upstream project and the Titan wrapper.

## Decision

Publish this project as a new wrapper repository, not as a monorepo snapshot.

The public repository should include wrapper code, scripts, documentation,
examples, and safety templates. It should exclude:

- nested `TradingAgents/` clone
- `.env` files
- API keys and provider credentials
- `data/`
- `corpus/`
- user inputs except `inputs/README.md`
- `outputs/`
- `research_materials/`
- `research_packets/`
- `research_cycles/`
- `normalized_data/`
- `provider_cache/`
- logs, embeddings, SQLite databases, and generated artifacts

The repository must credit TauricResearch / TradingAgents, link to the upstream
GitHub project, cite the arXiv paper, and state that this wrapper is
independent unless an affiliation is explicitly established.

## Consequences

- The wrapper remains clean and auditable.
- Upstream TradingAgents can be upgraded independently.
- Private Titan OS 2.9 / Titan DTP 1.6 corpora remain local-only.
- A publication safety check must pass before any GitHub push.
