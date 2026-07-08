# Exa API Reference — h2t-ops:research

> Lazy-loaded by agent when detailed API knowledge is needed. Not in main SKILL.md to keep it under 500 lines.

## Endpoints Used

Current invocation is the CLI: `h2t-ops research <subcommand>` (backed by
`h2t_ops/connectors/research/exa.py`). The legacy `exa_search.py` script is superseded.

| Endpoint | Purpose | Subcommand |
|---|---|---|
| `POST /search` | Semantic / keyword / deep search (10-mode ladder) | `research search` |
| `POST /contents` | Fetch clean text (JS-rendered, PDFs auto-handled) | `research crawl` |
| `POST /findSimilar` | Pages similar to a URL | `research similar` |
| `POST /research/v1` → poll `GET /research/v1/{id}` | Async multi-hop research | `research research` / `research-get` |
| `POST /agent/runs` → poll `GET /agent/runs/{id}` | Premium data-source fusion (LeadGen) | `research agent` |

Base URL: `https://api.exa.ai`.
Auth: `x-api-key: $EXA_API_KEY` header.

## Search Types (6-level ladder)

| type | Median latency | Use |
|---|---|---|
| `instant` | sub-second | Single most-direct fact, lowest latency |
| `fast` | ~500ms–4s | Single-step factual Q&A, autocomplete, voice agents |
| `auto` (default) | ~1000ms | Balanced general-purpose (neural + keyword) |
| `deep-lite` | ~few s | Budget structured synthesis |
| `deep` | ~5000ms | Multi-hop synthesis, agentic workflows |
| `deep-reasoning` | ~13s | Genuine multi-step reasoning in one call |

**Compare within latency classes only** — `instant` vs `deep-reasoning` = different use cases.

## Mode → Exa Params Mapping (canonical)

| mode | type | category | highlights.maxChars | default numResults |
|---|---|---|---|---|
| `instant` | `instant` | — | 2000 | 10 |
| `fast` | `fast` | — | 2000 | 10 |
| `generic` | `auto` | — | 4000 | 10 |
| `news` | `auto` | `news` | 3000 | 10 |
| `academic` | `auto` | `research paper` | 4000 | 8 |
| `competitor` | `auto` | `company` | 4000 | 10 |
| `people` | `auto` | `people` | 3000 | 10 |
| `deep-lite` | `deep-lite` | — | 5000 | 10 |
| `deep` | `deep` | — | 5000 | 10 |
| `deep-reasoning` | `deep-reasoning` | — | 5000 | 10 |

**Freshness:** `--max-age-hours N` sets Exa `maxAgeHours` (caps content age); `0` forces a
live crawl. Applies to any mode.

## Supported Filters per Mode (critical — prevents 400 errors)

| mode | date filters | include/excludeDomains | include/excludeText | country |
|---|:---:|:---:|:---:|:---:|
| `instant` | ✅ | ✅ | ⚠ single-item | ✅ |
| `fast` | ✅ | ✅ | ⚠ single-item | ✅ |
| `generic` | ✅ | ✅ | ⚠ single-item | ✅ |
| `news` | ✅ | ✅ | ⚠ single-item | ✅ |
| `academic` | ✅ | ✅ | ⚠ single-item | ✅ |
| `competitor` | ❌ | ❌ | ⚠ single-item | ✅ |
| `people` | ❌ | ⚠ linkedin.com only | ❌ | ✅ |
| `deep-lite` | ✅ | ✅ | ⚠ single-item | ✅ |
| `deep` | ✅ | ✅ | ⚠ single-item | ✅ |
| `deep-reasoning` | ✅ | ✅ | ⚠ single-item | ✅ |

Workarounds: need date/domain filters + company context → switch to `mode=news` or `mode=generic` (loses `category` boost but filters work).

## outputSchema Constraints

- Max 10 properties total across all nesting levels
- Array items: flat objects only, primitive fields (`string` / `integer` / `boolean` / `array` of strings)
- No nested objects inside array items (400)
- Root must be `{"type": "object"}`
- `null` silently ignored
- Every string field description MUST include a length constraint (e.g. "in 12 words or less")

## Deep-family Params

For deep-family modes (`deep-lite` / `deep` / `deep-reasoning`) `build_body` auto-sets:
- `type:` the matching Exa type
- `structuredOutput: true` (when outputSchema present)
- `highlights.maxCharacters: 1` (when outputSchema present — these modes synthesize, so
  highlights are redundant; collapsing minimizes token duplication)
- Default `numResults: 10` (override via `--num-results` if systemPrompt requires batch)

## Cost (observed; updated via telemetry)

| Operation | Typical cost |
|---|---|
| `search` mode=instant / generic, few results | ~$0.007–0.017 |
| `search` mode=deep / deep-reasoning, 5 results | $0.02–0.05 |
| `crawl` single URL with text | $0.001–0.003 |
| `research` (async) | model-dependent; telemetry reports `total_cost_usd` + searches/pages/reasoning_units |
| `agent` web-only (no `--data-source`) | ~$0.01–0.02 (agentCompute + search) |
| `agent` + premium provider | additive per provider (see Agent providers below) |

See `~/.h2t/research/.pending_telemetry.jsonl` for accumulated observations.

## Agent providers (premium data sources)

`research agent --data-source <provider>` (repeatable, PAID; omit for web-only). Prices are
base estimates as of 2026-07 — verify at <https://exa.ai/pricing>; machine copy is
`exa.AGENT_PROVIDERS`. Unknown provider → `400 INVALID_DATA_SOURCE` before any charge.

| provider | returns | ~base cost |
|---|---|---|
| `fiber_ai` | B2B contact data (emails, titles) | $0.02 |
| `similar_web` | website traffic estimates | $0.03 |
| `baselayer` | US business verification | $0.022 |
| `financial_datasets` | company financials | $0.01 |
| `particle_news` | podcast transcripts / news | $0.015 |

No Exa pre-execution cost endpoint exists. The envelope logs actual `total_cost_usd` +
`cost_breakdown` + `usage`; a floor estimate (`estimated_floor_usd`, catalog base prices
only) is attached when paid providers are requested. Control cost with `maxItems` in the
output schema.

## Synthesis contract (retrieval-first)

For client deliverables, prefer **Exa retrieval → our grounded synthesis** over the
black-box `output.content` / agent answer. Take the returned `citations` /
`output.grounding` and synthesize under `C:/dev/docs/standards/evidence-grounded-synthesis.md`
(anti-hallucination: every assertion carries a URL + verbatim support).

## Known Limitations (Exa, documented)

- Cannot filter by gender, ethnicity, or other demographics
- `people` category: `includeDomains` = LinkedIn only (other domains get 400)
- Multi-item `includeText`/`excludeText` arrays = 400 error; use separate calls
- `context` parameter deprecated (use `text` or `highlights` instead)
- No real-time monitoring (see Exa Monitors — separate API, not in v0.1)

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `EXA_ERROR:ENV EXA_API_KEY missing` | env var not exported | `export EXA_API_KEY=...` |
| `EXA_ERROR:NETWORK` | firewall / proxy / api.exa.ai down | Check proxy, retry later |
| `EXA_ERROR:API http=429` | rate limit | Wait 60s; Exa deep has lower QPS |
| `EXA_ERROR:API http=401` | invalid API key | Rotate at dashboard.exa.ai |
| `EXA_ERROR:ARGS ... incompatible with --start-date` | mode=competitor/people blocks filter | Switch to `--mode news` or `generic` |
| Empty results | query too narrow or niche vertical | Try query variations, widen date range, switch category |

---

## Envelope Schema (v1)

`research search` (and minimal-form `crawl`) emit a provider envelope.
Persisted in the artifact `.sources.json`; emitted to stdout via `--json`.

```json
{
  "status": "OK | DEGRADED | FAILED",
  "primary_engine": "exa",
  "fallback_engine_used": null,
  "results": [...],
  "telemetry": {
    "attempts": [
      {"engine": "exa", "endpoint": "/search", "http": 200, "latency_ms": 1234, "error": null}
    ],
    "reason_for_fallback": null,
    "total_latency_ms": 1234,
    "total_cost_usd": 0.012
  },
  "meta": {
    "query": "...",
    "mode": "generic",
    "num_results_requested": 10,
    "num_results_returned": 7,
    "timestamp": "2026-05-07T12:34:56+00:00",
    "envelope_version": "1"
  }
}
```

### Status decision matrix

| Status | Exit | When |
|---|---|---|
| `OK` | 0 | HTTP 200 + ≥1 result after retries |
| `DEGRADED` | 0 | HTTP 200 + 0 results after retries |
| `FAILED` | 1 | Args validation error |
| `FAILED` | 2 | HTTP 4xx (no retry), HTTP 5xx after retries, malformed JSON |
| `FAILED` | 3 | Network/timeout after retries |
| `FAILED` | 4 | Env / preflight error |

### Attempt error labels

`null` (success), `exa_5xx_retryable` (5xx + 429), `exa_4xx_nonretryable`, `exa_network_timeout`, `exa_empty_results`, `exa_malformed_json`.

### Retry policy

| Class | Retryable? | Max attempts | Backoff |
|---|---|---|---|
| 200 + non-empty | — | 1 | — |
| 200 + empty | yes | 2 | 1.0s + jitter |
| 5xx / 429 | yes | 2 | 2.0s + jitter |
| 4xx (other) | no | 1 | — |
| Network/timeout | yes | 2 | 1.5s + jitter |
| Malformed JSON | no | 1 | — |

Hard cap on cumulative sleep: 10 seconds. When exceeded: `EXA_WARN:RETRY_BUDGET_EXHAUSTED` to stderr, retry skipped.

---

## Fetch Envelope Schema (fetch_url.py)

Same `envelope_version: "1"` as Exa search envelope (status semantics OK / DEGRADED / FAILED), but flat single-URL shape:

```json
{
  "status": "OK | DEGRADED | FAILED",
  "url": "https://...",
  "final_url": "https://... (after redirects)",
  "provider_used": "direct | jina | none",
  "content_type": "article | listing | js_shell | gated | short_body | unknown",
  "content_gate": "none | login_required | paid | unknown",
  "title": "...",
  "body_markdown": "...",
  "body_text": "...",
  "body_chars": 1234,
  "links": [{"href": "...", "text": "...", "rel": ""}],
  "metadata": {
    "canonical_url": "...",
    "site": "alltd.org",
    "lang": "en",
    "detected_reason": null,
    "site_adapter": null,
    "raw_html_path": null
  },
  "telemetry": {
    "attempts": [{"provider": "direct", "http": 403, "latency_ms": 100, "error": "fetch_http_4xx_nonretryable"}],
    "reason_for_degraded": null,
    "reason_for_failed": null,
    "total_latency_ms": 100,
    "providers_skipped": ["playwright", "crawl4ai", "firecrawl", "browserless"],
    "providers_skipped_reason": {"playwright": "not_configured_stub"}
  },
  "meta": {
    "primary_engine": "fetch_ladder",
    "envelope_version": "1",
    "fetch_envelope_version": "1",
    "timestamp": "2026-05-07T12:34:56+00:00",
    "user_agent": "h2t-research-fetch/0.0.1 ..."
  }
}
```

Adapters (#104/#105) extend by setting `metadata.site_adapter` and adding adapter-specific fields under `metadata`. The `list-by-tag` subcommand introduces a separate envelope variant with `items[]` instead of body fields — see adapter docs when those land.
