---
name: h2t-ops:research
description: "Provider-routed web research via Exa-backed search/crawl and URL fetch providers. Modes: fast / generic / news / academic / competitor / people / deep. Transparent telemetry, fail-loud protocol. Use for web search, news tracking, academic papers, competitor intel, people research, and direct URL fetch. NOT for LinkedIn lead-gen (use /search-leads from BayramAnnakov plugin). Triggers: 'research', 'find out', 'look up', 'исследуй', 'h2t:research'."
compatibility: "Requires h2t-ops CLI with the research connector. Direct URL fetch works without a provider key. Optional JINA_API_KEY enables authenticated Jina Reader fetches. EXA_API_KEY is required only for Exa-backed capabilities such as search, answer, similar, crawl, and author resolution. Keys may be configured via env, H2T_SECRETS_FILE, ~/.dor/secrets/secrets.env, or ~/.dor/secrets.env. Playwright/Crawl4AI/Firecrawl/Browserless are stubbed follow-ups."
metadata:
  author: lichtpfad
  version: 0.1.2
---

# h2t-ops:research

Use `h2t-ops research` for provider-backed web research via Exa and the URL fetch ladder.

## Capability decision guide

Pick the narrowest capability that answers the request. Prefer **retrieval + your own
grounded synthesis** over black-box synthesis for client deliverables.

| Request shape | Use | Notes |
|---|---|---|
| Quick lookup, "what's the latest", single fact | `search --mode fast` | shallow, ~1–4 s |
| General topic, mixed sources | `search --mode generic` | default web search |
| News tracking, recent events | `search --mode news` | category=news |
| Academic papers, citations | `search --mode academic` | category=research paper |
| Competitor / company intel | `search --mode competitor` | category=company |
| People research | `search --mode people` | category=people |
| One-shot structured deep dig | `search --mode deep` + `--schema` | synchronous, ~4 s |
| Pull raw text of a known URL | `fetch` / `crawl` | fetch ladder / Exa contents |
| Find pages like a known URL | `similar` | Exa /findSimilar |
| Direct grounded answer + citations | `answer` | short answer, cited |
| Rescue OCR after failed fetch | `visual-ocr` | needs fetch sidecar + screenshot |

**When to prefer `search --mode deep` vs a quick mode:** deep is for one-shot
structured extraction where you already know the output shape (`--schema`). It is
**not** a multi-step research agent — for genuine multi-hop research use the planned
`research` capability below.

### Planned capabilities (not yet available — do not call)

Tracked in `docs/superpowers/specs/2026-07-08-exa-research-capability.md`. Until the
commands exist, use the modes above; do not invent flags.

- **`research`** (Exa Research API, async) — real multi-hop agent: plan → many
  searches → crawl pages → synthesized report with citations. For "разберись глубоко
  в теме X". Models `exa-research-fast` / `exa-research` / `exa-research-pro`.
- **`agent`** (Exa Agent API, async) — LeadGen / enrichment / invest: fuses premium
  data partners (Fiber.ai contacts, Similarweb traffic, Baselayer US-business,
  Financial Datasets, Particle podcasts) + web into one structured output. Paid
  per-provider — enable only with an explicit data-source flag.

For both planned modes the intended pattern is **retrieval-first**: let Exa return
structured, cited data, then do the final synthesis under our
`evidence-grounded-synthesis` discipline rather than shipping the black-box answer.

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
