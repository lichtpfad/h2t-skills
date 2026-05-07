# Exa API Reference — h2t-ops:research

> Lazy-loaded by agent when detailed API knowledge is needed. Not in main SKILL.md to keep it under 500 lines.

## Endpoints Used

| Endpoint | Purpose | Subcommand |
|---|---|---|
| `POST /search` | Semantic / keyword / deep search | `exa_search.py search` |
| `POST /contents` | Fetch clean text (JS-rendered, PDFs auto-handled) | `exa_search.py crawl` |

Base URL: `https://api.exa.ai`.
Auth: `x-api-key: $EXA_API_KEY` header.

## Search Types (consolidated 4-type model)

| type | Median latency | Use |
|---|---|---|
| `fast` | ~500ms | Single-step factual Q&A, autocomplete, voice agents |
| `auto` (default) | ~1000ms | Balanced general-purpose |
| `deep` | ~5000ms | Multi-hop synthesis, agentic workflows |
| `neural` | embedded | Semantic similarity (incorporated into fast/auto) |

**Compare within latency classes only** — `fast` vs `deep` = different use cases.

## Mode → Exa Params Mapping (canonical)

| mode | type | category | highlights.maxChars | default numResults |
|---|---|---|---|---|
| `fast` | `fast` | — | 2000 | 10 |
| `generic` | `auto` | — | 4000 | 10 |
| `news` | `auto` | `news` | 3000 | 10 |
| `academic` | `auto` | `research paper` | 4000 | 8 |
| `competitor` | `auto` | `company` | 4000 | 10 |
| `people` | `auto` | `people` | 3000 | 10 |
| `deep` | `deep` | — | 5000 | 10 |

## Supported Filters per Mode (critical — prevents 400 errors)

| mode | date filters | include/excludeDomains | include/excludeText | country |
|---|:---:|:---:|:---:|:---:|
| `fast` | ✅ | ✅ | ⚠ single-item | ✅ |
| `generic` | ✅ | ✅ | ⚠ single-item | ✅ |
| `news` | ✅ | ✅ | ⚠ single-item | ✅ |
| `academic` | ✅ | ✅ | ⚠ single-item | ✅ |
| `competitor` | ❌ | ❌ | ⚠ single-item | ✅ |
| `people` | ❌ | ⚠ linkedin.com only | ❌ | ✅ |
| `deep` | ✅ | ✅ | ⚠ single-item | ✅ |

Workarounds: need date/domain filters + company context → switch to `mode=news` or `mode=generic` (loses `category` boost but filters work).

## outputSchema Constraints

- Max 10 properties total across all nesting levels
- Array items: flat objects only, primitive fields (`string` / `integer` / `boolean` / `array` of strings)
- No nested objects inside array items (400)
- Root must be `{"type": "object"}`
- `null` silently ignored
- Every string field description MUST include a length constraint (e.g. "in 12 words or less")

## Deep Mode Required Params

When `mode=deep` script auto-sets:
- `type: "deep"`
- `structuredOutput: true` (when outputSchema present)
- `highlights.maxCharacters: 1` (when outputSchema present — minimizes duplication)
- Default `numResults: 10` (override via `--num-results` if systemPrompt requires batch)

## Cost (observed; updated via telemetry)

| Operation | Typical cost |
|---|---|
| `search` mode=generic, 5 results, highlights | $0.007 |
| `search` mode=deep, 5 results | $0.02–0.05 |
| `crawl` single URL with text | $0.001–0.003 |

See `~/.h2t/research/.pending_telemetry.jsonl` for accumulated observations.

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

`exa_search.py search` (and minimal-form `crawl`) emit a provider envelope.
Always present in `.sources.json` under `meta.envelope`. Optionally to stdout via `--envelope`.

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
