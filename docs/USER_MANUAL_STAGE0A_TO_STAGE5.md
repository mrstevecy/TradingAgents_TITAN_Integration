# TradingAgents TITAN Research User Manual

Date: 2026-05-03  
Project path: `D:\Projects\CodeX\TradingAgents_Integration`

This manual explains how a user runs a full equity research cycle from Stage 0A
through Stage 5, where to place files, what each stage does, and where outputs
are generated.

The instructions are written for Windows PowerShell and the current local
project layout.

## 1. What This System Does

The system combines:

- TradingAgents: the upstream multi-agent research workflow that generates the
  initial analyst, debate, trader, and portfolio-manager output.
- TITAN OS integration layers: the local validation, evidence, graph, horizon,
  and report-governance pipeline built around the TradingAgents output.

The workflow does not treat the raw TradingAgents recommendation as final. It
passes the baseline output through evidence checks, source validation, user CSV
technical evidence, metric reconciliation, graph generation, horizon validation,
and final report governance.

The final output is an institutional-style research report plus an interactive
evidence graph.

The Stage 5 report begins with key price context, including latest close date,
latest open/high/low/close/volume, 52-week high/low, distance from those
52-week levels, and current/intraday status when separately validated.
Stage 5 now uses a canonical `ReportContext` so the cover, price snapshot,
technical section, fundamentals section, sentiment section, and final decision
all use the same research date, intended trade date, market-data date, latest
price, and market-bar status. If the latest bar appears to be partial intraday
data, the report labels it as `intraday_partial` instead of calling it a final
end-of-day close.

The reader-facing report uses one canonical `FinalDecision` object. Baseline
agent labels such as underweight, sell, reduce, or hold remain diagnostic
artifacts unless the TITAN evidence gates promote them. In the default
institutional report mode, raw baseline role prose does not control the final
reader-facing action, dates, prices, source status, or technical interpretation.

For equity research, the system now runs a mandatory code-level evidence scan
before agents begin. This scan records mandatory facts, missing evidence,
attempted source classes, resolver attempts, fallback discovery attempts, and
constrained conclusions. It is not optional prompt language. It supports
earnings beat/miss classification, transcript and guidance checks, CapEx
guidance precedence, FCF reconciliation, forward P/E resolution, analyst
consensus minimums, short-interest positioning checks, next earnings date
resolution, contamination checks, semantic five-round debate validation, and
Portfolio Manager sanity checks.

The pre-agent scan now also promotes typed public-source facts into the evidence
store before analysts write. Financial filings, earnings 8-Ks, ownership forms,
transcripts, guidance, CapEx, FCF inputs, analyst consensus, short interest,
options put/call, next earnings date, and technical indicators are kept as
separate evidence categories. Proxy context can inform the report, but it does
not validate direct issuer or financial-filing requirements.

The evidence store also performs source-permission and numeric plausibility
checks. For example, an options page cannot validate management guidance, a
13G/13D/13F ownership filing cannot satisfy a 10-Q/10-K financial-filing
requirement, and unitless artifacts such as implausibly small revenue, OCF, or
short-interest values are marked `retrieved_invalid` before agents or reports
can treat them as final facts.

Before Stage 5 renders, the system now runs a dynamic RAG repair loop for
missing or invalid critical equity evidence. For each unresolved evidence key,
the repair loop builds an evidence-key-specific query plan and attempts the
full resolver chain:

- API/provider retrieval
- official issuer site
- SEC/regulatory site
- reputable news or wire source
- specialist aggregator
- general web source
- search-query expansion
- extraction retry
- source-conflict reconciliation

The dynamic web-RAG layer expands queries by source class, deduplicates URL
candidates, filters them by the evidence key's permitted source class, reranks
them before fetching, and stores the actual source URL, query text, source
class, confidence, and retrieval score. Those source links are included in the
agent evidence context, so analysts and debate agents receive the same
validated links that TITAN uses for validation.

The report may say `DATA-INCOMPLETE` only after those attempts are recorded in
the resolver trace. If critical gates still fail after the repair loop, Stage 5
renders as `DIAGNOSTIC RESEARCH PACKET - NOT FINAL` rather than a final
institutional report.

For equity catalyst dates, the system now runs an earnings-event resolver before
agents begin and again during Stage 5 repair. This resolver first determines
whether the latest quarter has already been reported from issuer/official or
high-quality public evidence, then resolves the next estimated earnings date.
Near-term dates from weaker calendars are quarantined if they conflict with the
latest reported event state. This prevents agents from debating as if a stale
earnings date is still upcoming, while still documenting the conflict in the
evidence store and report notes.

The baseline TradingAgents run also captures the raw upstream tool outputs that
agents used while researching. These are written to a JSONL artifact named like:

```text
outputs\deepseek_fresh_baseline\<TICKER>_<DATE>_upstream_tool_evidence.jsonl
```

Stage 5 reads this artifact and promotes usable provider/tool facts into the
typed evidence store before final validation. This prevents the system from
discarding valid facts that the upstream agents already found. The evidence
store is priority-aware: stronger provider, issuer, regulatory, or computed
facts are retained over later weaker web artifacts, and invalid numeric scraps
cannot overwrite valid evidence.

The final report now follows a rich-but-evidence-clean rendering rule. Useful
upstream analysis is preserved for the reader, but unsupported scenario claims
receive inline evidence notes at the point where they appear. For example,
actual CapEx, OCF, and FCF conversion can be shown when same-period cash-flow
evidence exists, while a future CapEx peak/decline claim is labeled as an
unvalidated scenario unless management guidance has been retrieved. Appendix A
is reserved for truly rejected claims such as false, stale, source-misused, or
numerically invalid assertions.

Actual cash-flow evidence is separated from forward guidance evidence. The
system stores latest-period OCF/CapEx/FCF separately from annual OCF/CapEx/FCF
and separately from management forward CapEx guidance, so one missing forward
guidance item does not erase valid actual financial analysis.

CSV files are optional. If supplied, they supplement TITAN Addendum C. If they
are absent, the system uses provider-derived market and technical evidence as a
fallback. CSV evidence is not allowed to override newer canonical OHLCV or live
market-snapshot evidence.

The default report sections use business-readable titles:

- `Final Trade Decision`
- `Technical Analysis`
- `Market & Catalyst Analysis`
- `Fundamental Analysis`
- `Sentiment & Positioning`
- `Research Manager Adjudication`
- `Trader Execution Plan`

Older labels such as `News Report`, `Social Media Report`, or raw baseline
role-map titles are diagnostic only and should not appear as ordinary
reader-facing institutional sections.

The system also keeps an operational error-learning file. When Stage 5 rejects
an unsupported or contaminated claim, the error is recorded with the responsible
agent role, evidence dependency, correction rule, recurrence flag, and severity.
Future runs load that memory before agents begin and inject only relevant prior
failures into the responsible role's context. This is not model fine-tuning; it
is code-controlled feedback memory that helps the same mistake get challenged
earlier in later research cycles.

The evidence layer now deep-reads cited official sources. If Stage 2 cites an
issuer IR page, SEC filing, earnings release, or transcript, the system reads
the source body before promotion so important facts are not lost merely because
the citation summary was short. For equity reports this is especially important
for RPO/backlog, guidance, OCF, CapEx, and FCF.

RPO/backlog is treated as conditional evidence. It is required when the company
or thesis depends on subscription, cloud, backlog, or contracted-revenue
visibility, but it is not a blind blocker for every equity ticker. Stale
earnings-date conflicts are quarantined as diagnostics after the canonical
latest-reported and next-estimated earnings dates are resolved.

## 2. Open the Correct Terminal

Use Windows PowerShell.

1. Open the Windows Start menu.
2. Type `PowerShell`.
3. Open `Windows PowerShell`.

Do not use the forbidden older project folders. Use only:

```powershell
D:\Projects\CodeX\TradingAgents_Integration
```

For most commands, navigate into the nested `TradingAgents` folder because that
is where the Python `uv` environment is configured:

```powershell
cd D:\Projects\CodeX\TradingAgents_Integration\TradingAgents
```

## 3. Environment Setup

The project uses `uv` to run Python inside the project environment. You usually
do not need to activate a virtual environment manually.

Run this once before the first research cycle:

```powershell
uv sync --dev
```

Confirm the environment can run tests:

```powershell
uv run pytest tests\test_institutional_evidence_policy.py -q
```

Expected result:

```text
12 passed
```

Provider keys and local settings live in:

```text
D:\Projects\CodeX\TradingAgents_Integration\TradingAgents\.env
```

For DeepSeek runs, confirm the DeepSeek key is configured there. Do not commit
`.env` to GitHub.

## 4. Choose Ticker and Date

Use these values consistently through the run:

- Ticker: stock symbol, for example `MSFT`
- Analysis date: the research date, for example `2026-05-03`

In the commands below, replace:

- `MSFT` with the ticker you want
- `2026-05-03` with the analysis date you want
- `MSFT_20260503T161816Z` with the run ID generated by Stage 1

Important: after Stage 1 completes, open the Stage 1 JSON or read the command
output to get the exact `research_run_id`. That run ID is needed for Stage 4 and
Stage 5.

## 5. Where to Place User-Supplied Files

Place user-supplied files under:

```text
D:\Projects\CodeX\TradingAgents_Integration\inputs\<TICKER>\<YYYY-MM-DD>
```

Example for Microsoft:

```text
D:\Projects\CodeX\TradingAgents_Integration\inputs\MSFT\2026-05-03
```

Stage 0A performs dated input-folder discovery. For the requested ticker and
analysis date, it selects the latest dated folder under `inputs\<TICKER>\` that
contains supported user files and is on or before the analysis date. If an older
folder is supplied while a newer eligible dated folder exists, Stage 0A records
a warning and selects the newer folder. This prevents stale user CSVs or
supporting files from being used because an older command was copied.

Recommended CSV files:

```text
inputs/
  MSFT/
    2026-05-03/
      MSFT_monthly.csv
      MSFT_weekly.csv
      MSFT_daily.csv
      MSFT_4h.csv
      MSFT_1h.csv
      MSFT_15m.csv
      MSFT_5m.csv
```

Exact filenames do not have to match this pattern. The current loader detects
TradingView-style CSV files by content and timeframe.

Accepted automated input today:

- TradingView-style `.csv` files with timestamp, OHLCV, VWAP, RSI, ATR, ADX,
  moving-average, volume, and divergence columns when available.

Supplementary documents, screenshots, PDFs, or supporting files:

- Put them in the same ticker/date folder.
- The current automated Stage 1B technical extraction focuses on CSV files.
- Non-CSV supporting files can still be preserved in the folder for audit or
  manual citation-manifest work, but they are not yet fully parsed into the
  automated technical feature packet.

## 6. Folder Overview

Important folders:

```text
inputs\                         user-supplied ticker/date files
outputs\deepseek_fresh_baseline  raw TradingAgents baseline summaries
citation_manifests\              source manifests for Stage 2 and Stage 2B
research_packets\stage0a_research_resolution
research_packets\stage1
research_packets\stage1b_user_technical_features
research_packets\stage2
research_packets\stage2b
research_packets\stage2c
research_packets\stage2d_stale_claim_refresh
research_packets\stage3_graphify
research_packets\evidence_delta
research_packets\stage4_horizon_validation
research_packets\stage5_final_report
research_cycles\                archived run bundles
```

## 7. Full Workflow Command Sequence

All commands in this section should be run from:

```powershell
cd D:\Projects\CodeX\TradingAgents_Integration\TradingAgents
```

The examples use:

- Ticker: `MSFT`
- Analysis date: `2026-05-03`
- Provider: `deepseek`
- Model: `deepseek-v4-flash`

### Stage 0A: Resolve the Research Request

Purpose:

Stage 0A confirms whether the requested instrument is supported and which
research profile will be used.

Command:

```powershell
uv run python ..\scripts\build_stage0a_research_resolution.py --ticker MSFT --asset-class Equity --analysis-date 2026-05-03 --input-root ..\inputs
```

`--input-folder` is optional. Use it only when you need to point at a specific
folder for audit purposes; Stage 0A still prefers a newer eligible dated folder
for the same ticker and analysis date and writes the selection metadata into the
Stage 0A packet.

Expected result:

- Registry Status: `Implemented`
- Active Research Profile: `equity_v1`

Outputs:

```text
research_packets\stage0a_research_resolution\MSFT_2026-05-03_stage0a_research_resolution.json
research_packets\stage0a_research_resolution\MSFT_2026-05-03_stage0a_research_resolution.md
```

If the status says `Registered But Not Implemented`, stop. The asset class is
recognized but not yet production-ready.

### Baseline: Run TradingAgents

Purpose:

This runs the upstream TradingAgents workflow and creates the baseline analyst,
debate, trader, and portfolio-manager output. TITAN will validate it later.

Command:

```powershell
uv run python ..\scripts\run_tradingagents_baseline.py --ticker MSFT --trade-date 2026-05-03 --provider deepseek --model deepseek-v4-flash --out-dir ..\outputs\deepseek_fresh_baseline
```

Outputs:

```text
outputs\deepseek_fresh_baseline\MSFT_2026-05-03_deepseek_fresh_baseline_summary.json
outputs\deepseek_fresh_baseline\MSFT_2026-05-03_deepseek_fresh_baseline_summary.md
outputs\deepseek_fresh_baseline\runtime_logs
outputs\deepseek_fresh_baseline\cache
outputs\deepseek_fresh_baseline\memory
```

The command prints a processed decision such as `Hold`, `Buy`, `Sell`, or
another normalized stance. This is not the final TITAN decision.

### Stage 1: Build the Validation Packet

Purpose:

Stage 1 combines the TradingAgents summary with provider evidence such as price
data, SEC evidence, mandatory evidence checks, and user-supplied evidence
discovery.

Command:

```powershell
uv run python ..\scripts\build_stage1_validation_packet.py --summary ..\outputs\deepseek_fresh_baseline\MSFT_2026-05-03_deepseek_fresh_baseline_summary.json --out-dir ..\research_packets\stage1 --input-root ..\inputs
```

Outputs:

```text
research_packets\stage1\MSFT_2026-05-03_stage1_validation_packet.json
research_packets\stage1\MSFT_2026-05-03_stage1_validation_packet.md
```

Important:

Open the Stage 1 JSON and find:

```json
"research_run_id": "MSFT_20260503T161816Z"
```

Write this run ID down. You will use it in later commands.

### Stage 1B: Extract User Technical Features

Purpose:

Stage 1B reads the user-supplied CSV files and extracts multi-timeframe
technical evidence such as VWAP, RSI, ADX, volume regime, ATR, moving averages,
and divergence counts.

Command:

```powershell
uv run python ..\scripts\build_stage1b_user_technical_features_packet.py --ticker MSFT --trade-date 2026-05-03 --input-root ..\inputs --out-dir ..\research_packets\stage1b_user_technical_features
```

Outputs:

```text
research_packets\stage1b_user_technical_features\MSFT_2026-05-03_stage1b_user_technical_features_packet.json
research_packets\stage1b_user_technical_features\MSFT_2026-05-03_stage1b_user_technical_features_packet.md
```

Stage 1B feeds TITAN Addendum C in the final report.

### Stage 2 Prerequisite: Create the Citation Manifest

Purpose:

Stage 2 requires a source manifest that lists the external sources used for the
ticker. The manifest tells the system which official, regulatory, financial-data,
news, catalyst, valuation, and sentiment sources are available.

Manifest location:

```text
citation_manifests\msft_2026-05-03_stage2_sources.json
```

For a new ticker, create a file with this naming pattern:

```text
citation_manifests\<ticker-lowercase>_<YYYY-MM-DD>_stage2_sources.json
```

Examples:

```text
citation_manifests\msft_2026-05-03_stage2_sources.json
citation_manifests\mu_2026-05-03_stage2_sources.json
```

The manifest should include source records such as:

- issuer investor relations earnings release
- SEC EDGAR 8-K, 10-Q, or 10-K
- earnings transcript or prepared remarks
- reputable valuation or analyst forecast source
- reputable earnings-calendar source
- short-interest or positioning source
- official macro or central-bank source where relevant
- reputable industry/news source where relevant

Each source must include:

- `source_id`
- `title`
- `publisher`
- `url`
- `published_date`
- `retrieved_at_utc`
- `reliability_tier`
- `source_type`
- `evidence_summary`
- `supported_claims`
- `limitations`

Do not use future-dated sources to validate an as-of-date research conclusion.

### Stage 2: Link Claims to Citations

Purpose:

Stage 2 links claims to source records and uses the evidence ledger to prevent
unsupported validation. A claim cannot become `Supported` merely because the
agent said it was true.

Command:

```powershell
uv run python ..\scripts\build_stage2_citation_packet.py --stage1 ..\research_packets\stage1\MSFT_2026-05-03_stage1_validation_packet.json --manifest ..\citation_manifests\msft_2026-05-03_stage2_sources.json --out-dir ..\research_packets\stage2
```

Outputs:

```text
research_packets\stage2\MSFT_2026-05-03_stage2_citation_packet.json
research_packets\stage2\MSFT_2026-05-03_stage2_citation_packet.md
```

### Stage 2B Prerequisite: Create the Reinforcement Manifest

Purpose:

Stage 2B tries to strengthen unresolved or conditional evidence areas.

Manifest location:

```text
citation_manifests\msft_2026-05-03_stage2b_reinforcement.json
```

For a new ticker, create:

```text
citation_manifests\<ticker-lowercase>_<YYYY-MM-DD>_stage2b_reinforcement.json
```

This file lists:

- added sources
- reinforcement tasks
- claim patterns to target
- residual gaps that still remain

### Stage 2B: Reinforce Evidence

Purpose:

Stage 2B upgrades, preserves, or constrains claims based on stronger source
evidence. It also uses the evidence ledger, so a task cannot mark a claim
`Supported` without matching source records.

Stage 2B also writes a promoted typed evidence store:

```text
research_packets\stage2b\<TICKER>_<DATE>_equity_evidence_store_promoted.json
```

This file converts validated source records into typed facts where possible,
including analyst consensus, short interest, guidance, transcripts, earnings
dates, and cash-flow or CapEx evidence.

Command:

```powershell
uv run python ..\scripts\build_stage2b_reinforcement_packet.py --stage2 ..\research_packets\stage2\MSFT_2026-05-03_stage2_citation_packet.json --manifest ..\citation_manifests\msft_2026-05-03_stage2b_reinforcement.json --out-dir ..\research_packets\stage2b
```

Outputs:

```text
research_packets\stage2b\MSFT_2026-05-03_stage2b_reinforcement_packet.json
research_packets\stage2b\MSFT_2026-05-03_stage2b_reinforcement_packet.md
```

### Stage 2C: Reconcile Computable Metrics

Purpose:

Stage 2C checks computable valuation or financial metric claims. It prevents
unsupported point estimates from becoming final facts. When exact inputs are not
fully sourced, valuation may be carried as an assumption-based range.

Command:

```powershell
uv run python ..\scripts\build_stage2c_metric_reconciliation.py --stage1 ..\research_packets\stage1\MSFT_2026-05-03_stage1_validation_packet.json --stage2b ..\research_packets\stage2b\MSFT_2026-05-03_stage2b_reinforcement_packet.json --baseline-summary ..\outputs\deepseek_fresh_baseline\MSFT_2026-05-03_deepseek_fresh_baseline_summary.json --out-dir ..\research_packets\stage2c
```

Outputs:

```text
research_packets\stage2c\MSFT_2026-05-03_stage2c_metric_reconciliation_packet.json
research_packets\stage2c\MSFT_2026-05-03_stage2c_metric_reconciliation_packet.md
```

### Stage 3: Build the First Evidence Graph

Purpose:

Stage 3 creates the evidence graph from Stage 1, Stage 2, Stage 2B, Stage 2C,
and the source manifests. This graph is deterministic and does not rely on LLM
semantic extraction.

Command:

```powershell
uv run python ..\scripts\build_stage3_evidence_graph.py --stage1 ..\research_packets\stage1\MSFT_2026-05-03_stage1_validation_packet.json --stage2 ..\research_packets\stage2\MSFT_2026-05-03_stage2_citation_packet.json --stage2b ..\research_packets\stage2b\MSFT_2026-05-03_stage2b_reinforcement_packet.json --stage2c ..\research_packets\stage2c\MSFT_2026-05-03_stage2c_metric_reconciliation_packet.json --stage2d ..\research_packets\stage2d_stale_claim_refresh\MSFT_2026-05-03_stage2d_stale_claim_refresh_packet.json --stage4 ..\research_packets\stage4_horizon_validation\MSFT_20260503T161816Z_stage4_horizon_validation_packet.json --stage5-manifest ..\research_packets\stage5_final_report\MSFT_20260503T161816Z\MSFT_20260503T161816Z_stage5_v2_final_report_manifest.json --citation-manifest ..\citation_manifests\msft_2026-05-03_stage2_sources.json --reinforcement-manifest ..\citation_manifests\msft_2026-05-03_stage2b_reinforcement.json --out-dir ..\research_packets\stage3_graphify\MSFT_2026-05-03
```

If Stage 2D, Stage 4, or Stage 5 files do not exist yet, the graph builder skips
those overlays and still builds the graph.

Outputs:

```text
research_packets\stage3_graphify\MSFT_2026-05-03\graph.json
research_packets\stage3_graphify\MSFT_2026-05-03\GRAPH_REPORT.md
research_packets\stage3_graphify\MSFT_2026-05-03\graph.html
```

Open `graph.html` in a browser to inspect the interactive evidence graph.

### Evidence Delta: Compare Prior and Fresh Graphs

Purpose:

The evidence delta compares a prior graph with the fresh graph. For the first
run of a ticker, use the fresh graph as both prior and fresh graph. This creates
a structural baseline.

First-run command:

```powershell
uv run python ..\scripts\build_evidence_delta_packet.py --prior-graph ..\research_packets\stage3_graphify\MSFT_2026-05-03\graph.json --fresh-graph ..\research_packets\stage3_graphify\MSFT_2026-05-03\graph.json --fresh-research-date 2026-05-03 --out-dir ..\research_packets\evidence_delta
```

Repeated-ticker command:

```powershell
uv run python ..\scripts\build_evidence_delta_packet.py --prior-graph ..\research_packets\stage3_graphify\MSFT_2026-05-03\graph.json --fresh-graph ..\research_packets\stage3_graphify\MSFT_2026-05-04\graph.json --fresh-research-date 2026-05-04 --out-dir ..\research_packets\evidence_delta
```

Outputs:

```text
research_packets\evidence_delta\MSFT_2026-05-03_evidence_delta_packet.json
research_packets\evidence_delta\MSFT_2026-05-03_evidence_delta_packet.md
```

### Stage 2D: Refresh Stale Claims

Purpose:

Stage 2D refreshes prior supported claims that are missing or stale in a fresh
run. For a first ticker run, this usually produces zero refreshed claims.

Command:

```powershell
uv run python ..\scripts\build_stage2d_stale_claim_refresh_packet.py --delta ..\research_packets\evidence_delta\MSFT_2026-05-03_evidence_delta_packet.json --prior-graph ..\research_packets\stage3_graphify\MSFT_2026-05-03\graph.json --out-dir ..\research_packets\stage2d_stale_claim_refresh --no-url-check
```

Outputs:

```text
research_packets\stage2d_stale_claim_refresh\MSFT_2026-05-03_stage2d_stale_claim_refresh_packet.json
research_packets\stage2d_stale_claim_refresh\MSFT_2026-05-03_stage2d_stale_claim_refresh_packet.md
```

### Stage 4: Validate Trading Horizon

Purpose:

Stage 4 evaluates Intraday, Swing, Positional, and Long-Term horizons separately.
It prevents a long-term thesis from silently validating an intraday trade, or an
intraday setup from becoming a long-term investment thesis.

Command:

```powershell
uv run python ..\scripts\build_stage4_horizon_validation.py --prior-graph ..\research_packets\stage3_graphify\MSFT_2026-05-03\graph.json --fresh-graph ..\research_packets\stage3_graphify\MSFT_2026-05-03\graph.json --delta ..\research_packets\evidence_delta\MSFT_2026-05-03_evidence_delta_packet.json --out-dir ..\research_packets\stage4_horizon_validation
```

Outputs:

```text
research_packets\stage4_horizon_validation\MSFT_20260503T161816Z_stage4_horizon_validation_packet.json
research_packets\stage4_horizon_validation\MSFT_20260503T161816Z_stage4_horizon_validation_packet.md
```

The filename uses the run ID from Stage 1.

### Stage 5 Preview: Build HTML Preview

Purpose:

Stage 5 preview creates an HTML report for review. It screens baseline
TradingAgents sections before display and adds TITAN evidence addenda.
Unsupported baseline claims are removed from normal narrative and listed in
the Excluded Claims / Errors and Recommendations table with correction rules.

For a first run, copy the fresh baseline into the full-baseline folder so the
preview exporter has both required inputs:

```powershell
New-Item -ItemType Directory -Force -Path ..\outputs\deepseek_full_baseline | Out-Null
Copy-Item -Force ..\outputs\deepseek_fresh_baseline\MSFT_2026-05-03_deepseek_fresh_baseline_summary.json ..\outputs\deepseek_full_baseline\MSFT_2026-05-03_deepseek_full_baseline_summary.json
Copy-Item -Force ..\outputs\deepseek_fresh_baseline\MSFT_2026-05-03_deepseek_fresh_baseline_summary.md ..\outputs\deepseek_full_baseline\MSFT_2026-05-03_deepseek_full_baseline_summary.md
```

Preview command:

```powershell
uv run python ..\scripts\build_stage5_v2_preview.py --ticker MSFT --baseline-date 2026-05-03 --trade-date 2026-05-03 --run-id MSFT_20260503T161816Z
```

Outputs:

```text
research_packets\stage5_final_report\MSFT_20260503T161816Z\preview.html
research_packets\stage5_final_report\MSFT_20260503T161816Z\preview_manifest.json
```

Open `preview.html` in a browser and review it before exporting PDF.

### Stage 5 Final Export: Build HTML, Markdown, and PDF

Purpose:

This creates the final report files. The final report is the governed
business-user output. Rejected or unsupported claims should not appear as
ordinary narrative; they should appear only in the controlled excluded-claims
section.

Command:

```powershell
uv run python ..\scripts\export_stage5_v2_final_report.py --ticker MSFT --baseline-date 2026-05-03 --trade-date 2026-05-03 --run-id MSFT_20260503T161816Z --official-website https://www.microsoft.com --no-logo-discovery
```

Use `--no-logo-discovery` if you do not want the system to fetch logo assets
from the internet. In that case the report uses a ticker badge fallback.

Outputs:

```text
research_packets\stage5_final_report\MSFT_20260503T161816Z\MSFT_20260503T161816Z_stage5_v2_final_report.html
research_packets\stage5_final_report\MSFT_20260503T161816Z\MSFT_20260503T161816Z_stage5_v2_final_report.md
research_packets\stage5_final_report\MSFT_20260503T161816Z\MSFT_20260503T161816Z_stage5_v2_final_report.pdf
research_packets\stage5_final_report\MSFT_20260503T161816Z\MSFT_20260503T161816Z_stage5_v2_final_report_manifest.json
```

### Stage 3 Final Overlay Rebuild

Purpose:

After Stage 5 final export, rebuild the graph so it includes final report
sections, horizon decisions, legal notice, logo attribution, and report
traceability edges.

Command:

```powershell
uv run python ..\scripts\build_stage3_evidence_graph.py --stage1 ..\research_packets\stage1\MSFT_2026-05-03_stage1_validation_packet.json --stage2 ..\research_packets\stage2\MSFT_2026-05-03_stage2_citation_packet.json --stage2b ..\research_packets\stage2b\MSFT_2026-05-03_stage2b_reinforcement_packet.json --stage2c ..\research_packets\stage2c\MSFT_2026-05-03_stage2c_metric_reconciliation_packet.json --stage2d ..\research_packets\stage2d_stale_claim_refresh\MSFT_2026-05-03_stage2d_stale_claim_refresh_packet.json --stage4 ..\research_packets\stage4_horizon_validation\MSFT_20260503T161816Z_stage4_horizon_validation_packet.json --stage5-manifest ..\research_packets\stage5_final_report\MSFT_20260503T161816Z\MSFT_20260503T161816Z_stage5_v2_final_report_manifest.json --citation-manifest ..\citation_manifests\msft_2026-05-03_stage2_sources.json --reinforcement-manifest ..\citation_manifests\msft_2026-05-03_stage2b_reinforcement.json --out-dir ..\research_packets\stage3_graphify\MSFT_2026-05-03
```

### Package the Interactive Graph

Purpose:

This creates a single ZIP file that can be shared with another user.

Command:

```powershell
uv run python ..\scripts\package_graph_share.py --graph-dir ..\research_packets\stage3_graphify\MSFT_2026-05-03
```

Outputs:

```text
research_packets\stage3_graphify\MSFT_2026-05-03\MSFT_2026-05-03_interactive_evidence_graph_share_package.zip
research_packets\stage3_graphify\MSFT_2026-05-03\share_manifest.json
```

### Archive the Research Cycle

Purpose:

This gathers important artifacts into a run-id-specific archive folder.

Command:

```powershell
uv run python ..\scripts\archive_research_cycle.py --graph ..\research_packets\stage3_graphify\MSFT_2026-05-03\graph.json --delta ..\research_packets\evidence_delta\MSFT_2026-05-03_evidence_delta_packet.json --summary ..\outputs\deepseek_fresh_baseline\MSFT_2026-05-03_deepseek_fresh_baseline_summary.json --stage4 ..\research_packets\stage4_horizon_validation\MSFT_20260503T161816Z_stage4_horizon_validation_packet.json --out-root ..\research_cycles
```

Outputs:

```text
research_cycles\MSFT_20260503T161816Z
research_cycles\MSFT_20260503T161816Z\research_cycle_manifest.json
research_cycles\MSFT_20260503T161816Z\README.md
```

## 8. How to Interpret the Final Outputs

Final report:

- Open the `.html` for interactive browser reading.
- Open the `.pdf` for sharing and presentation.
- Open the `.md` for text/audit review.

Evidence graph:

- Open `graph.html`.
- Use the node-type filter to inspect claims, sources, residual gaps, metrics,
  report sections, and horizon decisions.
- Click nodes to see details and trace evidence relationships.

Stage 4 horizon packet:

- Shows which horizons are usable.
- `Conditional Candidate` means the setup is promising but still requires
  confirmation.
- `Conditional` means partial evidence exists but limitations remain.
- `Not Validated` means the system does not have enough evidence to support
  that horizon.

Stage 2 and Stage 2B packets:

- Show which claims were source-backed.
- Show which claims remained conditional.
- Show which source IDs support each claim.

Stage 2C:

- Shows whether valuation or financial claims were computed, blocked,
  contradictory, or usable only as an assumption-based range.

Stage 1B:

- Shows user CSV technical features by timeframe.
- Feeds TITAN Addendum C.
- Includes VWAP, RSI, ADX, volume, ATR, moving-average, and divergence summaries
  when available in the CSVs.

## 9. Evidence and Validation Rules

The system follows these rules:

- Agent prose cannot validate an external fact by itself.
- External facts must be linked to source records.
- Future-dated publications cannot validate an as-of-date conclusion.
- Future catalyst dates are allowed only when the source publication or retrieval
  date is valid as of the research date.
- Missing evidence should be documented, not hidden.
- The final report should still produce constrained conclusions where evidence
  gaps remain.

## 10. Common Mistakes

Wrong folder:

- Do not run from the old project folders.
- Use `D:\Projects\CodeX\TradingAgents_Integration\TradingAgents`.

Wrong Python:

- Do not run scripts with plain `python` if dependencies are missing.
- Use `uv run python ..\scripts\...`.

Missing Stage 2 manifest:

- Stage 2 cannot run without a ticker/date citation manifest.

Wrong run ID:

- Stage 4 and Stage 5 filenames use `research_run_id`, not just ticker/date.
- Get the run ID from Stage 1.

Missing CSV files:

- If no CSV files are placed under `inputs\<TICKER>\<DATE>`, Stage 1B cannot
  produce user technical evidence.

Confusing raw baseline with final report:

- The TradingAgents baseline is input.
- The TITAN Stage 5 report is the governed output.
- If the final report shows an Excluded Claims table, those claims are not
  accepted evidence and must not be used for a trading or investment decision.

## 11. Quick Checklist

Before running:

- PowerShell opened.
- Current directory is `D:\Projects\CodeX\TradingAgents_Integration\TradingAgents`.
- `uv sync --dev` has been run.
- `.env` contains the required provider key.
- CSVs are in `inputs\<TICKER>\<DATE>`.
- Stage 2 and Stage 2B manifests exist for the ticker/date.

Run sequence:

1. Stage 0A
2. TradingAgents baseline
3. Stage 1
4. Stage 1B
5. Stage 2
6. Stage 2B
7. Stage 2C
8. Stage 3 first graph
9. Evidence delta
10. Stage 2D
11. Stage 4
12. Stage 5 preview
13. Stage 5 final export
14. Stage 3 final overlay rebuild
15. Graph share package
16. Research-cycle archive

Final files to review:

```text
research_packets\stage5_final_report\<RUN_ID>\<RUN_ID>_stage5_v2_final_report.pdf
research_packets\stage5_final_report\<RUN_ID>\<RUN_ID>_stage5_v2_final_report.html
research_packets\stage3_graphify\<TICKER>_<DATE>\graph.html
research_cycles\<RUN_ID>\research_cycle_manifest.json
```
