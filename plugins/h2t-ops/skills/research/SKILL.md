---
name: research
description: "Provider-routed web research via Exa-backed search/crawl and URL fetch providers. Search modes: instant / fast / generic / news / academic / competitor / people / deep-lite / deep / deep-reasoning. Also: async research (deep dig) and agent (premium data-source fusion for LeadGen/enrichment). Transparent telemetry + cost logging, fail-loud protocol. Use for web search, news tracking, academic papers, competitor intel, people research, and direct URL fetch. NOT for LinkedIn lead-gen (use /search-leads from BayramAnnakov plugin). Triggers: 'research', 'find out', 'look up', 'исследуй', 'h2t:research'."
compatibility: "Requires h2t-ops CLI with the research connector. Direct URL fetch works without a provider key. Optional JINA_API_KEY enables authenticated Jina Reader fetches. EXA_API_KEY is required only for Exa-backed capabilities such as search, answer, similar, crawl, and author resolution. Keys may be configured via env, H2T_SECRETS_FILE, ~/.dor/secrets/secrets.env, or ~/.dor/secrets.env. Playwright/Crawl4AI/Firecrawl/Browserless are stubbed follow-ups."
metadata:
  author: lichtpfad
  version: 0.1.3
---

# h2t-ops:research

Use `h2t-ops research` for provider-backed web research via Exa and the URL fetch ladder.

## Capability decision guide

Pick the narrowest capability that answers the request. Prefer **retrieval + your own
grounded synthesis** over black-box synthesis for client deliverables.

| Request shape | Use | Notes |
|---|---|---|
| Single known fact, lowest latency | `search --mode instant` | Exa `instant`, sub-second |
| Quick lookup, "what's the latest", single fact | `search --mode fast` | shallow, ~1–4 s |
| General topic, mixed sources | `search --mode generic` | default web search |
| News tracking, recent events | `search --mode news` | category=news |
| Academic papers, citations | `search --mode academic` | category=research paper |
| Competitor / company intel | `search --mode competitor` | category=company |
| People research | `search --mode people` | category=people |
| Structured dig, budget-conscious | `search --mode deep-lite` + `--schema` | lighter synthesis, cheaper than `deep` |
| One-shot structured deep dig | `search --mode deep` + `--schema` | synchronous, ~4 s |
| Genuine multi-step reasoning in one call | `search --mode deep-reasoning` + `--schema` | Exa `deep-reasoning`, ~13 s, real multi-hop |
| Multi-hop deep dig, "разберись в теме X" | `research --instructions "..."` | async Exa Agent API, ~20–120 s, cited report |
| LeadGen / enrichment / invest from premium sources | `agent --query "..." --schema ...` | Exa Agent API, schema+citations; paid providers via `--data-source` (see Agent mode) |
| Pull raw text of a known URL | `fetch` / `crawl` | fetch ladder / Exa contents |
| Find pages like a known URL | `similar` | Exa /findSimilar |
| Direct grounded answer + citations | `answer` | short answer, cited |
| Rescue OCR after failed fetch | `visual-ocr` | needs fetch sidecar + screenshot |

**Type ladder (fast → deep):** `instant → fast → auto (generic/news/…) → deep-lite → deep
→ deep-reasoning`. Higher rungs cost more latency/budget for more synthesis. `deep` and
`deep-reasoning` run their own reasoning, so with `--schema` their highlights are collapsed
to save tokens.

**When to prefer `search --mode deep*` vs `research`:** the `deep*` modes are synchronous
one-shot structured extractions where you already know the output shape (`--schema`).
`deep` ≈ ~4 s; `deep-reasoning` ≈ ~13 s with real multi-step reasoning; `deep-lite` is the
budget option. For a genuine multi-hop investigation (plan → many searches → crawl → cited
synthesis) use the `research` capability (async, see below).

**Freshness:** `--max-age-hours N` caps content age; `--max-age-hours 0` forces a live
crawl (Exa `maxAgeHours`). Use it when recency matters (breaking news, prices, live status).

## Research mode (async deep dig)

```bash
h2t-ops research research --instructions "..." --model exa-research-fast --project "$RESEARCH_PROJECT" --json
h2t-ops research research --instructions "..." --no-wait --json      # returns researchId
h2t-ops research research-get --id r_xxx --project "$RESEARCH_PROJECT" --json   # redeem it later
```

- Runs on the Exa **Agent API** (`/agent/runs`); the legacy Research API (`/research/v1`)
  was retired (HTTP 410). The `--model` tiers map onto Agent `effort`:
  `exa-research-fast`→`low` (default) / `exa-research`→`medium` / `exa-research-pro`→`high`
  (deeper, pricier).
- `--wait` (default) blocks and polls with backoff; `--no-wait` returns the run id
  immediately — redeem it later with `research-get --id <id>` (status `RUNNING`
  until done, then `OK` with the result + artifacts).
- Telemetry reports `num_searches` / `reasoning_units` (agent compute units) and
  `total_cost_usd` (top-level `costDollars` on the completed run). `num_pages` is not
  reported by the Agent API.
- Retrieval-first: prefer taking the returned `citations` and synthesizing under
  `evidence-grounded-synthesis` over shipping the black-box `output.content` verbatim for
  client deliverables.

## Agent mode (premium data-source fusion)

LeadGen / enrichment / invest. The Exa Agent API fuses premium data partners + web
search into one schema-validated output with per-field citations (`output.grounding`).
Synchronous (runs ~4–13 s); `POST /agent/runs` → poll `GET /agent/runs/{id}`.

```bash
# Web-only (no paid providers) — cheap, use for a schema-shaped structured dig
h2t-ops research agent --query "Profile Anthropic: HQ, founded year" \
  --schema schema.json --project "$RESEARCH_PROJECT" --json

# With premium providers (PAID — each --data-source adds per-provider cost)
h2t-ops research agent --query "Profile Anthropic: funding + monthly web traffic" \
  --data-source fiber_ai --data-source similar_web --schema schema.json --json
```

**Cost gate:** paid providers run **only** when you pass `--data-source`. Omit it →
web-only (agentCompute + search only; a trivial query costs ~$0). Providers are
pass-through: an unknown name returns a clean `400 INVALID_DATA_SOURCE` **before any
charge**.

**Provider catalog** (per-provider base cost, as of 2026-07 — verify at
<https://exa.ai/pricing>; the code catalog is `exa.AGENT_PROVIDERS`):

| `--data-source` | Returns | ~Base cost |
|---|---|---|
| `fiber_ai` | B2B contact data (emails, titles) | $0.02 |
| `similar_web` | website traffic estimates | $0.03 |
| `baselayer` | US business verification | $0.022 |
| `financial_datasets` | company financials | $0.01 |
| `particle_news` | podcast transcripts / news | $0.015 |

**Cost logging:** Exa has **no** pre-execution cost endpoint. The envelope telemetry
reports `total_cost_usd` + `cost_breakdown` (agentCompute / search / emails /
phoneNumbers / dataSources) and `usage` from the response. When paid providers are
requested, `estimated_floor_usd` is a **floor** (sum of catalog base prices only —
excludes variable agentCompute + search); `estimated_unknown_providers` flags names not
in the catalog. Control scope/cost with `maxItems` in the output schema.

**Retrieval-first:** take `output.structured` + `output.grounding` citations and do the
final synthesis under `evidence-grounded-synthesis`, rather than shipping the black-box
answer for client deliverables. Positioning vs `mcp__anysite` / `/search-leads`:
schema-driven fusion of several premium sources in one call, not a replacement.

## Boundary

Research artifacts are evidence, not canonical accepted knowledge.
POS may later ingest them, but local object JSON remains the canonical runtime
source in this phase.

## Local Artifact Model

`h2t-ops:research` now maintains a local JSON-first artifact layer:

- Canonical local truth = JSON object artifacts.
- Indexes are rebuildable navigation caches.
- Markdown = review/presentation mirror only.
- shared navigation caches:
  - `threads.index.json`
  - `documents.index.json`
  - `syntheses.index.json`
  - `aliases.index.json`

Agent lookup order:

1. query shared index
2. resolve object ids / aliases
3. read canonical object JSON via `show`
4. open Markdown mirror only for human review

If index and object disagree, object wins.

## Navigation Commands

Use the local navigation surface for deterministic lookups:

```bash
h2t-ops research index documents --project <project_id_or_context_id> --output-dir <dir> --json
h2t-ops research index threads --output-dir <dir> --json
h2t-ops research index syntheses --output-dir <dir> --json
h2t-ops research show document <document_id> --output-dir <dir> --json
h2t-ops research show thread <thread_id> --output-dir <dir> --json
h2t-ops research show run <run_id> --output-dir <dir> --json
h2t-ops research show synthesis <synthesis_id> --output-dir <dir> --json
h2t-ops research resolve --url <url> --output-dir <dir> --json
h2t-ops research resolve --alias <value> --alias-type <type> --output-dir <dir> --json
```

Core rule:

- JSON object artifacts are the canonical truth.
- Index files (`*.index.json`) are caches to locate object ids quickly and must not be treated as source truth.
- Markdown mirrors are for human review only; do not treat them as authoritative for data extraction.

## Maintenance Commands

Use maintenance commands to validate and refresh local research artifacts:

```bash
h2t-ops research doctor --output-dir <dir> --json
h2t-ops research rebuild-indexes --output-dir <dir> --json
h2t-ops research cleanup --dry-run --output-dir <dir> --json
```

Retention policy:

- Canonical object JSON is never deleted by default.
- doctor is read-only.
- `rebuild-indexes` writes only `indexes/*.index.json`.
- `cleanup --dry-run` reports non-canonical cleanup candidates and does not delete files.
- indexes are rebuildable caches; if an index and object disagree, object JSON wins.
- Markdown mirrors and `.partial.md` files are human/operator surfaces, not canonical knowledge.

## Project Context (REQUIRED)

**Always resolve `RESEARCH_PROJECT` before any search or crawl command.**

```bash
# From session-start output (preferred):
RESEARCH_PROJECT="<GATHER_RESULT.project.id>"   # e.g. "rejuve", "h2t-skills", "crypto-orchestrator"

# Fallback if no session context:
RESEARCH_PROJECT=$(git remote get-url origin 2>/dev/null | sed 's|.*/||;s|\.git$||')
```

`--project default` is **forbidden**. If project cannot be resolved — ask the user before running.

## Commands

```bash
h2t-ops research preflight --json
h2t-ops research search --query "..." --mode generic --num-results 10 --project "$RESEARCH_PROJECT" --json
h2t-ops research crawl --url "https://..." --project "$RESEARCH_PROJECT" --json
h2t-ops research fetch --url "https://..." --provider auto --json
h2t-ops research visual-ocr --fetch-sidecar "...sources.json" --image-path "...png" --json
```

## Provider Key Routing

Use provider routing before dispatching provider-backed research when key availability is uncertain:

```bash
h2t-ops research providers --json
h2t-ops research providers --capability fetch --json
h2t-ops research route --capability search --json
h2t-ops research route --capability fetch --json
```

Rules:

- EXA_API_KEY is required for search, answer, similar, crawl, and author resolution.
- JINA_API_KEY is optional for fetch.
- direct fetch is available without a provider key.
- Routing checks are local and do not call provider networks.
- Missing required provider keys fail before artifact writes.
- If routing reports no configured provider, fix keys/configuration before running the provider command.

`visual-ocr` is a rescue path after `research fetch` returns `FAILED` or specific
degraded reasons. It creates a review-required artifact from one fetch sidecar and
one existing page image.

Screenshot capture is an operator concern, not a research connector concern.
Preferred workflow: capture the page with `h2t-tools:screenshot`, then pass that
image into `h2t-ops research visual-ocr`.

## References

Load only what the request needs:

- `references/research-artifact-contract.md`
- `references/traceability-policy.md`
- `references/telemetry-policy.md`
- `references/templates/technical-decision.md`
- `references/templates/api-audit.md`
- `references/templates/market-research.md`
- `references/templates/company.md`
- `references/templates/academic.md`
- `references/templates/news-monitoring.md`
- `references/templates/person.md`

## Required Workflow

1. Pick a template if the request has a clear domain.
2. Run the relevant `h2t-ops research ...` command.
3. For `visual-ocr`, first produce the fetch sidecar with `h2t-ops research fetch`,
   then capture the page screenshot via `h2t-tools:screenshot`.
4. Inspect `result.status`; `exit 0` can still mean `DEGRADED`.
5. Write final findings only with source URL + quote + confidence.
6. Preserve artifact paths and telemetry.
7. Fill `research_artifact_registration/v1` context while the session context is fresh.
8. If POS intake exists, hand it the registration manifest; otherwise leave the manifest ready.

## Antipatterns

- No `--project default` — forbidden. Always pass real project id from session context.
- No silent WebSearch/WebFetch fallback.
- No paywall/login bypass.
- No screenshot capture inside `h2t-ops research`; use `h2t-tools:screenshot`.
- No POS DB/vault/lake/context writes.
- No finding without URL + quote + confidence.
- No automatic KB promotion.
