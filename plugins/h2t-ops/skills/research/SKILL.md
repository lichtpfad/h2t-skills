---
name: h2t-ops:research
description: "Semantic web research via Exa API. Modes: fast / generic / news / academic / competitor / people / deep. Transparent telemetry, fail-loud protocol. Use for web search, news tracking, academic papers, competitor intel, people research. NOT for LinkedIn lead-gen (use /search-leads from BayramAnnakov plugin). Triggers: 'research', 'find out', 'look up', 'исследуй', 'h2t:research'."
compatibility: "Requires h2t-ops CLI with the research connector and EXA_API_KEY configured via env, H2T_SECRETS_FILE, ~/.dor/secrets/secrets.env, or ~/.dor/secrets.env. Optional JINA_API_KEY enables authenticated Jina Reader fetches. URL fetch uses direct and Jina providers by default; Playwright/Crawl4AI/Firecrawl/Browserless are stubbed follow-ups."
metadata:
  author: lichtpfad
  version: 0.1.2
---

# h2t-ops:research

Use `h2t-ops research` for provider-backed web research via Exa and the URL fetch ladder.

## Boundary

Research artifacts are evidence, not canonical knowledge. This skill may create
traceable research artifacts under `~/.h2t/research/`; POS owns indexing, dedupe,
linking, and promotion into KB/journal/tasks/decisions.

## Commands

```bash
h2t-ops research preflight --json
h2t-ops research search --query "..." --mode generic --num-results 10 --json
h2t-ops research crawl --url "https://..." --json
h2t-ops research fetch --url "https://..." --provider auto --json
h2t-ops research visual-ocr --fetch-sidecar "...sources.json" --image-path "...png" --json
```

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

- No silent WebSearch/WebFetch fallback.
- No paywall/login bypass.
- No screenshot capture inside `h2t-ops research`; use `h2t-tools:screenshot`.
- No POS DB/vault/lake/context writes.
- No finding without URL + quote + confidence.
- No automatic KB promotion.
