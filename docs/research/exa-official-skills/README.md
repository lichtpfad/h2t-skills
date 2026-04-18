# Exa Official Skills — Reference Material

**Source:** User-provided from Exa docs (docs.exa.ai), 2026-04-18. Seven official skill templates that Exa publishes as reference implementations.

**Why we keep these:** Exa's own skills show how they think research agents should be built. We adopt their patterns but diverge on **transport** — they use MCP, we use curl/Python wrapper (see our design spec for rationale).

**Our design doc:** `docs/superpowers/specs/2026-04-18-research-skill-architecture-design.md`

---

## Seven Official Skills

| # | Skill | Tool | Use Case |
|---|---|---|---|
| 1 | `company-research` | `web_search_advanced_exa` | Company/competitor/market research, LinkedIn companies |
| 2 | `exa-lead-gen` | `deep_search_exa` | ICP-driven bulk lead generation with CSV output |
| 3 | `get-code-context-exa` | `get_code_context_exa` | Code snippets from GitHub/StackOverflow/docs |
| 4 | `people-research` | `web_search_advanced_exa` | LinkedIn profiles, expert discovery |
| 5 | `web-search-advanced-financial-report` | `web_search_advanced_exa` | SEC filings, earnings reports |
| 6 | `web-search-advanced-research-paper` | `web_search_advanced_exa` | Academic papers, arXiv |
| 7 | `web-search-advanced-personal-site` | `web_search_advanced_exa` | Personal blogs, portfolios |

---

## Patterns Adopted (incorporated into our spec)

### 1. Tool Restriction Section (Critical)

Every Exa skill has a prominent section declaring the allowed tool. Example:

> *"ONLY use `web_search_advanced_exa`. Do NOT use `web_search_exa` or any other Exa tools."*

**Our adaptation:** SKILL.md explicitly says *"ONLY use `scripts/exa_search.py`. Never use WebSearch / WebFetch / curl directly."* — prevents silent fallback.

---

### 2. Token Isolation via Subagent / `context: fork`

**All 7 Exa skills use `context: fork`** in frontmatter. Their rationale:

> *"Never run Exa searches in main context. Always spawn Task agents: Agent runs Exa search internally, processes results, returns only distilled output. Main context stays clean regardless of search volume."*

**Our current stance:** inline skill (no fork) for transparency + debuggability. The silent-fallback bug was discovered because agent output was in main context.

**Revision opportunity:** offer `context: fork` as a separate `/research-deep` skill for heavy runs (v0.2). Default `/research` stays inline. See spec §2.2.

---

### 3. Dynamic numResults Tuning

> *"No hardcoded numResults. Tune to user intent:*
> - *User says 'a few' → 10-20*
> - *User says 'comprehensive' → 50-100*
> - *User specifies number → match it*
> - *Ambiguous? Ask: 'How many results would you like?'"*

**Our adaptation:** use `depth: shallow/standard/deep` as the primary control but allow `--num-results` override. If ambiguous, agent asks user.

---

### 4. Query Variation for Coverage

> *"Exa returns different results for different phrasings. For coverage:*
> - *Generate 2-3 query variations*
> - *Run in parallel*
> - *Merge and deduplicate"*

**Our adaptation:** In Step 3 for `depth=standard|deep`, agent generates 2-3 variations, runs parallel via `exa_search.py search` with `--additional-queries` flag. Script dedupes by URL.

---

### 5. Category-Specific Filter Restrictions (critical gotchas)

Exa has undocumented-but-real restrictions per category. From the official skills:

**`category: "company"`** — CAUSES 400 ERRORS if used with:
- `includeDomains` / `excludeDomains`
- `startPublishedDate` / `endPublishedDate`
- `startCrawlDate` / `endCrawlDate`

**`category: "people"`** — CAUSES ERRORS if used with:
- `startPublishedDate` / `endPublishedDate`
- `startCrawlDate` / `endCrawlDate`
- `includeText` / `excludeText`
- `excludeDomains`
- `includeDomains` — **LinkedIn domains only** (e.g., "linkedin.com")

**`category: "financial report"`** — `excludeText` NOT SUPPORTED

**Universal:** `includeText` and `excludeText` support **single-item arrays only** (multi-item arrays cause 400 errors)

**Our adaptation:** `exa_search.py` validates category-parameter combinations before sending. Script exits code 1 with `EXA_ERROR:ARGS` if caller combines unsupported params (fail-fast vs HTTP 400).

---

### 6. outputSchema Constraints

From `exa-lead-gen` skill:

- **Max 10 properties total** across all nesting levels (wrapper array + item fields)
- Items inside arrays must be **flat objects with primitive fields only** (string, integer, boolean, array of strings)
- No nested objects inside array items (causes 400)
- Must be valid object with `"type": "object"` at root
- `null` silently ignored (no schema applied)
- Supported field types: `string`, `integer`, `boolean`, `array` (of strings)

**Our adaptation:** Documented in `reference.md`. Our `systemprompts/*.md` outputSchema fragments must obey these constraints.

---

### 7. String Field Rule

> *"All string fields in any outputSchema MUST include a length constraint in their description — e.g. 'in 12 words or less', 'under 15 words', 'one sentence max'. This keeps responses punchy, reduces token waste, produces cleaner CSV output."*

**Our adaptation:** `systemprompts/` template guide says every string field description must include a length constraint. Script doesn't enforce (too hard), but reference.md makes it a hard rule.

---

### 8. Required Parameters for Deep Search

From `exa-lead-gen`:

- `structuredOutput: true`
- `numResults: 50` (matches systemPrompt target)
- `highlightMaxCharacters: 1` (minimizes response when using structured output)
- `type: "deep"`

**Critical:** `numResults` and `systemPrompt` target must align. If systemPrompt says "return 50 companies" but `numResults: 20`, results will be inconsistent.

**Our adaptation:** When `mode=deep`, script auto-sets these params as defaults. Can be overridden via CLI flags but mode=deep implies them.

---

### 9. Batch Subagent Pattern (for massive parallel research)

`exa-lead-gen` architecture:

```
Main Agent (orchestrator — lean context)
├── Step 1: ICP research (1 exa call, user confirms/refines)
├── Step 2: Generate micro-verticals (LLM, no API)
├── Step 3: Design outputSchema (LLM, no API)
├── Step 4: Launch batch subagents (5 calls per batch, 6+ batches)
├── Step 5: Python CSV compiler (reads /tmp JSON files, dedups, outputs CSV)
└── Step 6: Summary
```

**Each subagent:** receives 5 micro-verticals, runs 5 parallel Exa calls, writes JSON to `/tmp/`, reports back ONLY the count (no raw data in main context).

**Our adaptation:** NOT in v0.1 MVP. Added to v0.2 roadmap as `/research-batch` skill for high-volume research (100+ items across multiple queries).

---

### 10. Browser Fallback (out of scope for us)

Exa suggests Claude in Chrome as fallback when Exa returns insufficient results or content is auth-gated. We have `h2t-tools:playwright-agent` as equivalent but **not integrated** with research skill in v0.1.

---

## What We Diverge On

| Decision | Exa Official | Our Spec |
|---|---|---|
| Transport | MCP (`mcp.exa.ai/mcp?tools=...`) | curl/Python wrapper (stdlib urllib) |
| Context mode | `context: fork` (isolated) | inline (default), fork option in v0.2 |
| Tool selection | one MCP per skill, tool-restricted | one script, routed by `--mode` |
| Per-category skills | 7 separate skills | 1 skill, 6 modes |
| Lead-gen | own skill (`exa-lead-gen`) | delegated to BayramAnnakov plugin (Anysite-based) |

**Why we diverge on transport:** MCP tools proved unreliable for sub-agents (deferred schema loading issue — see issue #69). curl avoids this entirely.

**Why 1 skill / 6 modes vs 7 separate skills:** our users are one person (me), not a platform — 6 modes in one skill is easier to maintain than 7 copy-paste skill files that drift apart.
