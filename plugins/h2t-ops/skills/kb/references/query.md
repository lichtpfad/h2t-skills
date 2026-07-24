# kb — query mode

Ground a decision in the KB instead of asking the operator: justify/refute a claim, choose a method in an unfamiliar domain, or check a fact where neither you nor the operator has verified expertise. **Only council-PASS claims may drive conclusions.**

> Resolve `KB`/`PY` per SKILL.md § "Resolve the KB root" (repeated for a self-contained run):
> `KB="${H2T_KB_ROOT:-C:/dev/research-kb}"` · `PY="$KB/.venv/Scripts/python"`

This mode is **KB-agnostic**: instance ontology is read from the KB (`$KB/taxonomy.md`, `$KB/index.md`); the `llm-kb-template` artifact **schema** is assumed (every instance shares the one engine). **Fail loud** if a required artifact is missing (no page, no `pipeline-state.json`, no council round) — never silently answer ungrounded.

## Step 1 — Find the cluster

Read `$KB/taxonomy.md` for the instance's ontology, then keyword-search:
```
Grep pattern="<keyword>" path="$KB/wiki/" --output_mode content -C 2
```

## Step 2 — Read the topic (3 levels)

- **L1** overview: `$KB/index.md` (keywords + tldr).
- **L2** evidence (frontmatter of `$KB/wiki/<slug>.md`): in `evidence[]` look at `claim`, `verdict`, `replicated: true` (≥2 independent sources), `single_source_warning: true`, `sources[].ref`, `confidence`.
- **L3** full page: read `$KB/wiki/<slug>.md` whole (Key Concepts / What Works / What Doesn't Work).

## Step 3 — Check the council (mandatory)

A claim that only passed lint is NOT verified. Only council PASS = reliable.
```
Read "$KB/data/pipeline-state.json"
```

For the slug find `council_results.round_N.pass[]` / `fail[]` (id-keyed `ev-xxxx`; `round_N.labels` maps id→claim). Judging detail: `Read "$KB/filter-logs/<slug>.md"`. If the file, the slug, or a council round is absent → fail loud (do not fall back to an unrecorded answer).

## Step 4 — Trust hierarchy

| Signal | Weight | Use |
|---|---|---|
| CONFIRMED + replicated + council PASS | ★★★ | strong — cite directly |
| CONFIRMED + council PASS | ★★ | sufficient |
| LIKELY + council PASS | ★ | moderate — add a caveat |
| HYPOTHESIS / single_source_warning + council PASS | ⚠ | weak — state the limit |
| council FAIL (any verdict) | ✗ | do NOT use as grounding |

## Step 5 — Gap → fill it (capture ≠ ingest)

If the KB has no PASS-claim for the question, do NOT silently fall back to an unrecorded search.
- **Routine:** any `h2t-ops research` you run captures to `~/.h2t/research/`; mark it for KB ingest (interactive: ask; autonomous: auto-mark). Heavy ingest runs in batch, not per lookup.
- **Urgent gap** (need a verified claim NOW to decide): run a targeted **`kb ingest --strict "<the question>"`** (cost-gated) and ground on the council-PASS result. **Why `--strict`:** default ingest is Tier-1 lightweight — no council, `partial` page, never council-PASS. Query may ground only on council-PASS, so the urgent-gap path REQUIRES strict.

## Antipatterns

- No claim used without a council check — the wiki verdict was set by an agent; the council may have overturned it.
- Don't generalize one FAIL to a whole topic. Don't cite HYPOTHESIS as fact.
- Don't ignore `What Doesn't Work` — council-verified failures are often more valuable.
