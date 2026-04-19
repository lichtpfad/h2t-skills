---
name: research
description: "Semantic web research via Exa API. Modes: fast / generic / news / academic / competitor / people / deep. Transparent telemetry, fail-loud protocol. Use for web search, news tracking, academic papers, competitor intel, people research. NOT for LinkedIn lead-gen (use /search-leads from BayramAnnakov plugin). Triggers: 'research', 'find out', 'look up', 'исследуй', 'h2t:research'."
compatibility: "Requires $EXA_API_KEY env var. Get key at https://dashboard.exa.ai/api-keys. Requires ~/.h2t/venv (run /h2t-core:setup if missing)."
metadata:
  author: lichtpfad
  version: 0.1.0
---

# h2t-ops:research

Semantic research via Exa HTTP API. Transparent (all tool calls visible in main conversation), fail-loud (no silent fallbacks), debug-friendly (telemetry block in every report).

## Architecture

```
User query
    ↓
Step 0: Preflight (env + connectivity)
    ↓
Step 1: Parse request → mode, depth, filters
Step 1b: Check cache → ~/.h2t/research/
    ↓
Step 2: Load systemprompts/{mode}.md
    ↓
Step 3: Call exa_search.py (search / crawl, parallel where possible)
    ↓
Step 4: Fail-loud checks (exit code ≠ 0 → STATUS:DEGRADED)
    ↓
Step 5: Synthesize findings (grounded — URL + quote + confidence)
    ↓
Step 6: Persist (script auto-writes .partial.md + .sources.json)
    ↓
Step 7: Present Output (agent finalises .md per REPORT-SPEC.md)
```

## Файлы скилла

| Файл | Назначение |
|---|---|
| `SKILL.md` | Этот файл — workflow, runtime contract, antipatterns |
| `REPORT-SPEC.md` | Точный формат report markdown |
| `reference.md` | Exa API reference, mode mapping, limitations (lazy-loaded) |
| `examples.md` | CLI invocation examples + output samples |
| `systemprompts/{mode}.md` | 7 готовых systemPrompt templates |
| `scripts/exa_search.py` | Python CLI wrapper (stdlib urllib, no pip) |
| `tests/test_exa_search.py` | pytest suite |

## Выходные файлы

| Файл | Когда | Writer |
|---|---|---|
| `~/.h2t/research/{project}-{slug}-{date}.partial.md` | После HTTP call | script |
| `~/.h2t/research/{project}-{slug}-{date}.sources.json` | После HTTP call | script |
| `~/.h2t/research/{project}-{slug}-{date}.md` | После synthesis | **agent** |
| `~/.h2t/research/.pending_telemetry.jsonl` | When evals unreachable | script |

## Runtime variables (set once at Step 0)

```bash
H2T_PYTHON="${H2T_PYTHON:-}"
[ -z "$H2T_PYTHON" ] && [ -f "$HOME/.h2t/venv/Scripts/python.exe" ] && H2T_PYTHON="$HOME/.h2t/venv/Scripts/python.exe"
[ -z "$H2T_PYTHON" ] && [ -f "$HOME/.h2t/venv/bin/python" ] && H2T_PYTHON="$HOME/.h2t/venv/bin/python"
[ -z "$H2T_PYTHON" ] && echo "ERROR: h2t venv not found. Run /h2t-core:setup" && exit 1

EXA_CLI="$H2T_PYTHON ${CLAUDE_PLUGIN_ROOT}/skills/research/scripts/exa_search.py"
```

## Tool Restriction (critical)

**ONLY use `$EXA_CLI`.** Do NOT use `WebSearch`, `WebFetch`, or direct `curl` as substitutes. If `$EXA_CLI` fails, return `STATUS: DEGRADED` with exact `EXA_ERROR:*` — never silently substitute.

## Workflow

### Step 0: Preflight

```bash
$EXA_CLI preflight
```

Failures:
- Exit 4 + `EXA_ERROR:ENV EXA_API_KEY missing` → tell user to export key, STOP
- Exit 4 + `EXA_ERROR:NETWORK` → api.exa.ai unreachable, STOP

No silent fallback. No WebSearch substitution.

### Step 1: Parse Research Request

Accept natural language OR structured input. Extract:

| Field | Required | Default | Notes |
|---|---|---|---|
| `topic` | yes | — | passed as `--query` |
| `mode` | no | `generic` | one of fast / generic / news / academic / competitor / people / deep |
| `depth` | no | `standard` | shallow (1 call) / standard (search + crawl top-3) / deep (+ deep_reasoning synthesis) |
| `country` | no | — | ISO code, e.g. `CH`, `US` |
| `start_date` / `end_date` | no | — | ISO date (content date filter) |
| `include_domains` / `exclude_domains` | no | — | CSV list; see filter matrix in reference.md |
| `num_results` | no | mode default | override |
| `project` | no | `default` | for output filename prefix |

Ambiguous? Ask ONE clarifying question. Example: user says "research Rejuve.bio" → ask: "Company intel, press coverage, or team research? (competitor / news / people)"

### Step 1b: Check Cached Research

```bash
ls ~/.h2t/research/*{slug}* 2>/dev/null
```

If file < 7 days old exists — show path, ask: *"Use cached or re-search?"*

### Step 2: Load systemPrompt Template

Agent does NOT read `systemprompts/{mode}.md` directly — the script does. Agent just selects `--mode`.

### Step 3: Execute Search (parallel where independent)

```bash
# depth=shallow: one call
$EXA_CLI search --query "..." --mode generic --num-results 5 --project X

# depth=standard/deep: 2–3 query variations in parallel + dedupe
$EXA_CLI search \
  --query "Rejuve.bio Switzerland press 2026" \
  --additional-queries "Swiss longevity startups,DAO biotech 2026" \
  --mode news --start-date 2025-10-01 \
  --num-results 10 --project rejuve

# depth=deep phase 2: parallel crawl top-3 URLs in a single message
$EXA_CLI crawl --url "URL_1" --project X &
$EXA_CLI crawl --url "URL_2" --project X &
$EXA_CLI crawl --url "URL_3" --project X &
wait
```

**Batch independent calls in a single message.** Never sequentialize parallel searches.

### Step 4: Fail-Loud Checks

On any non-zero exit from `$EXA_CLI`:

- Read first stderr line (structured `EXA_ERROR:*`)
- Return `STATUS: DEGRADED` + exact cause + what was attempted
- **Forbidden phrasing:** `"permission blocked"`, `"tool failed"` without specifics
- **Required phrasing:** exact `EXA_ERROR:*` message from stderr

| Exit | Meaning | Action |
|---|---|---|
| 0 | Success | Continue |
| 1 | Args error | Stop, fix invocation |
| 2 | HTTP error (4xx/5xx) | STATUS:DEGRADED, report exact code |
| 3 | Network timeout | STATUS:DEGRADED, suggest retry |
| 4 | Preflight (env/connectivity) | STOP, fix env |

### Step 5: Synthesize Findings

Read script's markdown stdout (title + URL + highlight per result).

**Grounding rule (ALL depths, no exceptions):** every Key Finding MUST have:
- Verbatim quote from highlight (double-quoted string)
- URL to source
- Confidence label: high / medium / low + one-sentence reason

No grounding → not a finding. Move to Limitations or flag as `[research incomplete]`.

### Step 6: Persist (script auto-done)

Script wrote `.partial.md` + `.sources.json`. Agent now reads `.partial.md` and builds final `.md` per `REPORT-SPEC.md`.

### Step 7: Present Output

Write final report to `~/.h2t/research/{project}-{slug}-{date}.md` following REPORT-SPEC.md. Delete `.partial.md` after writing. In main conversation, show:

- Path to saved file
- Summary (top 3 findings as bullets)
- Status label (✅ completed / ⚠ partial / ❌ degraded)
- Telemetry status literal

## Error Handling

| Signal | Reaction |
|---|---|
| User query too vague (e.g. "research stuff") | Ask ONE clarifying question with mode examples |
| User asks "how many results?" Ambiguous | Ask: "10 (default), 5 (quick), or 50 (bulk)?" |
| Exa returns 0 results | Report honestly. Suggest query variations or broader category. Do NOT synthesize from general knowledge. |
| User asks for LinkedIn lead-gen | Route to `/search-leads` (BayramAnnakov plugin, Anysite engine). This skill does Exa only. |
| `.partial.md` missing when writing final | Script failed silently (bug). Re-run search; if still failing, check stderr. |

## Antipatterns

- **Synthesize findings without URL + quote** — violates grounding rule. #69 root cause.
- **Claim `depth=deep` when only `search` was called** — status lying. Integrity check row in telemetry catches this.
- **Hide tool failures** — any non-zero exit code must propagate to Meta.Status.
- **"permission blocked" as diagnosis** — forbidden without evidence of CC permission denial. Use exact `EXA_ERROR:*`.
- **Silent fallback to WebSearch** — script never does this; agent must not either.
- **Parse HTML inline in agent** — script's job. Agent reads cleaned markdown only.
- **Forget to delete `.partial.md`** — leaves stale files. Always `rm .partial.md` after writing final `.md`.

## When to use this skill

✅ "Find companies in longevity space"
✅ "Recent news about AI chip export controls"
✅ "Academic papers on LLM RAG evaluation"
✅ "Who is the CEO of Insilico Medicine?"

❌ "Generate leads for my outbound campaign" → use `/search-leads`
❌ "Monitor Twitter for brand mentions" → use `/search-leads` (Anysite has Twitter)
❌ "Scrape this internal URL" → use WebFetch / Playwright (auth-gated)

## Research Request

$ARGUMENTS
