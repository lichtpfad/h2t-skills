# kb — query mode

Read the KB instead of re-deriving from raw. Two **intents** share one retrieval ladder — the intent decides whether the council is a gate or a label:

- **`read`** — "give me the material / sources on topic X." Retrieval-by-reading, the pattern-native path. **No council gate.** Council status is a label surfaced on a claim, not a filter.
- **`ground`** — "justify a decision in a domain where neither I nor the operator has verified expertise." Same ladder **plus** the mandatory council-PASS filter: **only council-PASS claims may drive a conclusion.**

If unsure which intent applies: a request that will *decide something* is `ground`; a request to *see what we have* is `read`. When a `read` answer starts driving a decision, switch to `ground` and apply the gate.

> Resolve `KB` per SKILL.md § "Resolve the KB root": `KB="${H2T_KB_ROOT:-C:/dev/research-kb}"`.
> Query is read-only (Read/Grep over `$KB`) for L0–L3. Two escape hatches use the engine: the L-raw segment read (`kb-read-span`) and the optional file-back step (§ Compound).

This mode is **KB-agnostic**: instance ontology is read from the KB (`$KB/taxonomy.md`, `$KB/index*.md`); the `llm-kb-engine` artifact **schema** is assumed (every instance shares the one engine). **Fail loud** if a required artifact is missing (no page, no `pipeline-state.json`, no council round for a `ground` query) — never silently answer ungrounded.

## The disclosure ladder

Descend only as far as the question needs. ~95% of queries resolve by **L2** — the quote is already there. Going deeper costs tokens; don't.

### L0 — Route to the domain (multi-domain KB)

A KB may hold several domains, each with its own index (`$KB/index.<domain>.md`) under a root `$KB/index.md`. Classify the question → pick the domain → read that domain's index.
- Unambiguous → route silently.
- Ambiguous / low-confidence / no matching domain → **propose** the best-fit domain(s) and ask (AskUserQuestion). **Never** silently invent a new domain; **never** decline to answer — propose and confirm.
- Federation across *separate* KB instances (e.g. a crypto or agentic KB) is a manual pointer today (`$KB/.claude/rules/kb-lookup.md`) — same classify→route logic, followed by hand.

### L1 — Find the cluster

Read the routed `$KB/index.<domain>.md` (keywords + tldr) for candidate slug(s). Then keyword-search the wiki if needed:
```
Grep pattern="<keyword>" path="$KB/wiki/" --output_mode content -C 2
```

### L2 — Evidence frontmatter (most answers stop here)

Frontmatter of `$KB/wiki/<slug>.md`, in `evidence[]`: `claim`, `verdict`, `confidence`, `replicated: true` (≥2 independent sources), `single_source_warning: true`, `judge_pass`, and `sources[]` with `ref` (URL) **+ `quote`** (the verbatim span the claim was extracted from). The quote *is* the source segment — you usually need neither the page body nor the raw.

### L3 — Full page body

Read `$KB/wiki/<slug>.md` whole (Key Concepts / What Works / What Doesn't Work) only when L2 lacks the nuance the question needs.

### L-raw — the immutable source (escape hatch, NOT routine)

`$KB/sources/<slug>/<id>.md` = the verbatim harvested body + `body_hash`, pinned from `evidence[].sources[].raw`. Descending here routinely = sliding back into RAG (re-reading raw on every question), the exact anti-pattern the wiki exists to avoid. Descend **only** on a trigger:
1. **Verify a quote in context** — the L2 quote looks cherry-picked, contradicts another claim, or the decision is high-stakes → read the surrounding passage.
2. **Re-extract** — the claim doesn't answer the exact question but the source might → extract from raw rather than re-harvest.
3. **Provenance audit** — confirm `body_hash` matches (capture unaltered).

**Segment-addressed read (don't scan the whole body).** When a source carries `loc` (the segment qids the quote resolved from), read just that span + surrounding context via the engine — pass the source's own `raw` pin and its `loc`:
```
kb-read-span --repo "$KB" --raw <evidence sources[].raw> --qids <loc, e.g. 0,2> [--context N] [--verify]
```
It re-segments the immutable capture (Python owns the text) and prints the addressed "chapter". `--verify` runs the provenance audit (`body_hash` match) for trigger 3. If a source has no `loc` (capture predates the pin), fall back to reading the capture at `raw` and locating the quote.

If `evidence[].sources[].raw` is absent, L-raw is unreachable for that page (the capture predates the pin, or the source was never captured) — say so; do not silently fall back to a live fetch.

## Council check — gate for `ground`, label for `read`

A claim that only passed lint is NOT council-verified. The wiki `verdict` was set by an agent; the council may have overturned it.
```
Read "$KB/data/pipeline-state.json"
```
For the slug find `council_results.round_N.pass[]` / `fail[]` (id-keyed `ev-xxxx`; `round_N.labels` maps id→claim). Judging detail: `Read "$KB/filter-logs/<slug>.md"`.
- **`ground`:** council PASS is **mandatory** — a non-PASS claim may not drive the conclusion. If the file, slug, or a council round is absent → fail loud.
- **`read`:** council is **not** a gate — surface the material with its status attached (PASS / not-yet-judged / FAIL). A pure RAW-material request (`index → page/sources`) can bypass the claim layer entirely.

## Trust hierarchy (`ground`)

| Signal | Weight | Use |
|---|---|---|
| CONFIRMED + replicated + council PASS | ★★★ | strong — cite directly |
| CONFIRMED + council PASS | ★★ | sufficient |
| LIKELY + council PASS | ★ | moderate — add a caveat |
| HYPOTHESIS / single_source_warning + council PASS | ⚠ | weak — state the limit |
| council FAIL (any verdict) | ✗ | do NOT use as grounding |

## Gap → fill it (capture ≠ ingest)

If a `ground` query has no PASS-claim for the question, do NOT silently fall back to an unrecorded search.
- **Routine:** any `h2t-ops research` you run captures to `~/.h2t/research/`; mark it for KB ingest (interactive: ask; autonomous: auto-mark). Heavy ingest runs in batch, not per lookup.
- **Domain is re-decided at ingest, not inherited from the read.** The ingest that consumes a gap-fill resolves its OWN target domain via `ingest.md`'s classify → propose → **confirm** gate — do NOT write the material into the domain you happened to be reading. Multi-domain KB: propose the domain and get the operator's OK before any page is written.
- **Urgent gap** (need a verified claim NOW to decide): invoke **ingest mode with `--strict <topic>`** — read `references/ingest.md` §"Strict tier". Strict is **cost-gated and never auto-run** (agent-propose gate; a human approves before any dispatch). Only after it completes may you ground on the council-PASS result. Default ingest is Tier-1 (no council, `partial` page, never council-PASS) → the urgent-gap path REQUIRES `--strict`.

## Compound the KB — file good answers back (query → wiki)

A good answer is an asset; don't let it vanish into chat. When a query produces a synthesis, comparison, or discovered connection worth keeping, **file it back as a `page_kind: synthesis` page via the engine** (interactive: ask; autonomous: file it). **Never hand-write the page** — that drifts from the schema (the historical `query_derived:` hand-filing produced malformed pages). Use the engine seam `kb-writeback`; the read side stays Read/Grep.

```
kb-writeback --repo "$KB" --input <answer.json> [--date YYYY-MM-DD] [--commit]
```

- **Confirm the target domain before filing** (multi-domain KB): classify → propose →
  confirm, exactly as `ingest.md` does. A filed-back page is a durable write, so the
  `domain` field is decided at write time and never inherited from the domain you happened
  to be reading.

`answer.json` is a single JSON object the agent writes:
- `slug` — lowercase alnum + `-`; in a multi-domain KB **prefix the routed domain**: `<domain>--<slug>`.
- `topic`, `tldr` — human title + one-line answer.
- `body` — the synthesized answer prose (markdown).
- `see_also` — the slugs of the pages this answer drew on (**this is the page's provenance**).
- `priority` (default `P2`); `domain` — **required in a multi-domain KB** (the routed domain); `query` — the originating question (logged, not stored on the page).

The engine renders the page (`page_kind: synthesis`, **no `evidence[]`** — a synthesis page carries no ingested sources), gates it (lint + JSON Schema), **refuses to overwrite a source-derived page** (updates an existing synthesis one), regenerates the routed index, and appends a `writeback` log line — all atomically with rollback. `--commit` also git-commits the writeset.

Provenance is `page_kind: synthesis` + `see_also` — a synthesis page is honestly marked as LLM synthesis, never mistaken for an ingested source. It is L3 content, **not council-graded** — a later `ground` use still needs the council gate on the underlying source pages it drew on.

## Antipatterns

- **`ground` only:** no claim drives a conclusion without a council check — the agent-set verdict may have been overturned.
- Don't descend to L-raw for a lookup L1–L3 already answered. Don't generalize one FAIL to a whole topic. Don't cite HYPOTHESIS as fact.
- Don't ignore `What Doesn't Work` — council-verified failures are often the most valuable.
- Don't present a `page_kind: synthesis` (filed-back) page as an independently-sourced ingest.
