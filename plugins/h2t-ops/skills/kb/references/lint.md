# kb — lint mode

> Resolve `KB` per SKILL.md § "Resolve the KB root": `KB="${H2T_KB_ROOT:-C:/dev/research-kb}"`.
> The engine is the installed `llm-kb-engine` tool; `kb-lint` is a console-script (data-only model).

Thin wrapper over the engine's `kb-lint` (config-bound source-type / verdict / council checks). Read-only.

```bash
kb-lint --repo "$KB"                    # all pages (default: $KB/wiki); or add "$KB/wiki/<slug>.md" for one
```

Exit 0 = all pages PASS; non-zero = at least one violation (printed per page). On FAIL, report the offending pages + first violations; do not "fix" content silently — a lint failure on a KB page means the claim/verdict/council data is malformed and needs the operator or a kb re-ingest (mode: ingest), not a cosmetic patch.

## Provenance warnings (quote↔raw binding)

`kb-lint` also emits `WARN:` lines when a claim's `quote` cannot be verified against its committed immutable capture — `quote ⊄ capture`, a `capture_hash` that no longer matches the stored body, `loc` drift, or a missing capture. **WARN never flips the exit code** — it is a measurement, not a gate. On WARN lines, do NOT hand-edit the quote to silence them; instead:

```bash
kb-rebind --repo "$KB"            # dry-run report: which sources can be re-bound to their capture
kb-rebind --repo "$KB" --write    # apply: mints/corrects loc from the committed body only
```

`kb-rebind` re-derives each `quote`'s segment address (`loc`) from the committed capture and never touches the claim, verdict, or council state. Statuses that it **cannot** auto-repair — `unresolvable` (the quote is not a span of the stored source), `capture-missing`, `hash-mismatch` — mean genuine drift (paywalled / refetched / pre-contract): leave them as honestly-flagged best-effort anchors and route to the operator or a targeted re-ingest. `kb-rebind` exits non-zero when any such source remains.

## Semantic health pass (agent-driven — the pattern's real Lint leg)

The checks above are structural. The LLM-Wiki pattern's "lint" is a periodic **read** pass the agent runs over the wiki — Python never does this (no script calls an LLM). **Propose, never auto-edit:** a real fix is an ingest or an `open_questions[]` entry, not a cosmetic patch. Read the pages and look for:

- **Contradictions** — two pages (or two claims) asserting opposing things → add the tension to the relevant page's `open_questions[]`; keep both claims, drop neither.
- **Stale claims** — a page whose `updated` predates a newer source that supersedes its `tldr` → flag for re-ingest.
- **Orphans** — a page no other page links via `see_also` → wire a real cross-reference or question whether it earns its place.
- **Concept-without-page** — a term recurring across pages with no page of its own → propose a taxonomy row → `kb-scaffold`.
- **Missing cross-refs** — related pages not linked → propose `see_also` additions.
- **Data gaps** — a thin `tldr` or an `open_question` a search could close → route to `query.md` gap-fill / ingest (capture ≠ ingest; cost-gated).

Output a short report of findings + proposed actions. A good synthesis of the health pass is itself worth keeping — file it back per `query.md` § "Compound the KB".
