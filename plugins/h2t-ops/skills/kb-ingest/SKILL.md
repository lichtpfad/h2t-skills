---
name: h2t-ops:kb-ingest
description: "Ingest ecosystem research into the shared Ecosystem Research KB via the offline E→T→L engine (source-graded claims + judge council). Human-invoked and COST-GATED: harvests sources on a topic, drives the deterministic Python stages, dispatches the extractor/faithfulness/conflict agents, finalizes fail-closed, runs the council, commits. Use to turn a research question into council-verified claims instead of a dump. Triggers: 'kb-ingest', 'ingest into KB', 'наполни KB', 'зафиксируй ресёрч в KB'."
compatibility: "Requires the research-kb instance (default C:/dev/research-kb, override H2T_KB_ROOT) with its .venv, and the h2t-ops research connector for harvest. Python never calls an LLM — this skill dispatches the agents via the Agent tool between the prepare and finalize stages."
metadata:
  author: lichtpfad
  version: 0.1.0
---

# h2t-ops:kb-ingest

Turn a research question into **council-verified claims** in the shared KB. The engine
(`llm-kb-template`, vendored in research-kb) owns every deterministic seam; this skill drives
them and dispatches the three agents. **Python never calls an LLM.** Only council-PASS claims
may drive conclusions — never skip the council (§ Council), because grounding happens in
domains the operator can't personally verify.

## 0. Resolve the KB root

```bash
KB="${H2T_KB_ROOT:-C:/dev/research-kb}"
PY="$KB/.venv/Scripts/python"      # Windows; Linux/mac: $KB/.venv/bin/python
```

Pick the target `slug` from `$KB/taxonomy.md` (existing topic) or add a new row under the
right role-tier domain first. `scaffold_topics.py` (or a stub) must produce
`$KB/wiki/<slug>.md` before finalize writes evidence onto it.

## 1. Harvest (Extract)  →  raw_source JSON

Gather 20–40 sources for the topic with the research connector:

```bash
h2t-ops research --mode deep "<the research question>"
```

Map each result into the **raw_source schema** the engine expects and write a harvest JSON
(list of objects). REQUIRED per source: `id` (stable), `type` (one of the config
`source_types`: academic | practitioner | implementation | blog | review — you classify),
`body` (the extractable text). Optional: `url`, `title`, `authors`, `published_date` (ISO),
`doi`, `stars`, `replicated`, `landmark`. A source missing id/type/body is rejected fail-loud.

## 2. Deterministic T-prep (no LLM)

```bash
$PY -m pipeline.run records-from-harvest --harvest harvest.json --slug <slug> --out records.json
$PY -m pipeline.run intake  --records records.json --repo "$KB"      # sources → pending
$PY -m pipeline.run prepare --repo "$KB"                              # pending → prompt-packs
```

`prepare` prints `{"packs": N}` and writes `$KB/data/intake/prompts/<h>.json` per source.

## 3. ⛔ COST GATE (hard-stop — human go)

Before dispatching ANY agent, STOP and report:
`packs = N → up to N×3 agent dispatches (extractor + faithfulness + conflict) + Exa harvest spend.`
**Dry-run:** print the extractor prompt of one pack (`agent-work/<h>/extractor_prompt.txt`) so
the operator sees the sanctioned input, and dispatch NOTHING until they say go. This is a
money hard-stop — never auto-proceed.

## 4. Per-pack agent loop (Transform — the only live step)

For each pack hash `<h>` (run one stage per call — matches the engine convention):

```bash
$PY -m pipeline.grade.orchestrate render-extractor  --repo "$KB"   # writes extractor_prompt.txt
```
→ **Agent** (extractor): read `agent-work/<h>/extractor_prompt.txt`, emit `extractions.json`.
```bash
$PY -m pipeline.grade.orchestrate build-faithfulness --repo "$KB"  # prompt + qids sidecar
```
→ **Agent** (faithfulness): emit `faithfulness.json`.
```bash
$PY -m pipeline.grade.orchestrate build-conflict    --repo "$KB"   # iff candidates
```
→ **Agent** (conflict, only if a `conflict_prompt.txt` was written): emit `conflicts.json`.
```bash
$PY -m pipeline.grade.orchestrate assemble          --repo "$KB"   # stamps qids → agent-out/<h>.json
```

The agent sees only sanctioned inputs (numbered spans by qid; Python-resolved quote text;
indexed conflict pairs). Python owns quote text and qids — an agent-supplied quote_id is
discarded at assemble (provenance enforced there).

## 5. Finalize (Load, fail-closed)

```bash
$PY -m pipeline.run finalize --repo "$KB"     # agent-out → evidence on page + rejected/conflicts reports
```

Fail-closed: a verdict whose stamped `quote_ids` don't bind to the extractor's is rejected.
Prints `{packs, enriched_claims, rejected, conflicts}`.

## 6. Council (Transform — mandatory, never skip)

```bash
$PY "$KB/scripts/parse_claims.py" <slug>            # writes round header, prints claims
# dispatch the judges (Agent tool, parallel) → each appends its section to filter-logs/<slug>.md
$PY "$KB/scripts/synthesize_council.py" <slug>      # majority vote → data/pipeline-state.json
```

Loop E→T→L until 2 consecutive rounds add no new PASS (dry_streak = 2). A claim without a
council PASS does NOT belong in `tldr` and must not be cited as grounding.

## 7. Lint + commit

```bash
$PY "$KB/scripts/lint_wiki.py" "$KB/wiki/<slug>.md"      # must PASS (or fix)
$PY "$KB/scripts/update_index.py"                         # refresh index.md
git -C "$KB" add wiki/<slug>.md filter-logs/<slug>.md data/pipeline-state.json index.md log.md
git -C "$KB" commit -m "ingest(<slug>): +N council-verified claims"
```

Append to `$KB/log.md`: `[DATE] ingest | <slug> | <source-id> | "added N claims"`.

## Guardrails

- Python never calls an LLM via subprocess; agents dispatched only here, via the Agent tool.
- Council never skipped — poisoning the KB is worst exactly where the operator is blind.
- One stage per CLI call. Frequent small commits. `git mv`/`git rm` only.
- Never fabricate a source `body` or a quote — quotes are Python-resolved from the source text.
