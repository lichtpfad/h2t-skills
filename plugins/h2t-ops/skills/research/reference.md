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
