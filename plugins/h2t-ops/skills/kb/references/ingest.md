# kb — ingest mode

> Resolve `KB`/`PY` per SKILL.md § "Resolve the KB root" (repeated for a self-contained run):
> `KB="${H2T_KB_ROOT:-C:/dev/research-kb}"` · `PY="$KB/.venv/Scripts/python"`

Turn a research question into a **grounded knowledge page** in the shared KB. The engine
(`llm-kb-template`, vendored in research-kb) owns every deterministic seam; this skill drives
them and dispatches the agents. **Python never calls an LLM.**

Two flows:

- **DEFAULT — Tier-1 lightweight (navigation tier).** Fast, cheap: an honesty screen drops
  promo/hype sources, the deterministic T-prep + extractor mint evidence, and a grounded
  synthesis writes readable prose that may cite ONLY minted `(ev-xxxx)` ids (a Python
  fail-closed guard rejects any un-minted citation). Result: a `partial` page, `tier:
  lightweight`. No council.
- **`--strict <topic>` — full council tier.** The complete E→T→L judge-council flow
  (extractor + faithfulness + conflict + majority-vote council). Slower and more expensive;
  use it when a decision needs council-verified grounding in a domain the operator can't
  personally verify. Never auto-run — see § Strict tier.

Pick the target `slug` from `$KB/taxonomy.md` (existing topic) or add a new row under the
right role-tier domain first. A `$KB/wiki/<slug>.md` stub must exist before ingest writes onto it.

## Default: Tier-1 lightweight flow

One CLI call per step (`$PY -m pipeline.run <stage>`). The agent passes (honesty, extractor,
synthesis) are dispatched via the Agent tool between the deterministic stages.

```
1. Harvest (Exa) -> harvest.json  [reuse the §1 mapping to the raw_source schema below]
2. Honesty (agent):
   - Build ONE honesty prompt per source in the skill (input = a bounded head of the body + type + url).
   - Prompt LENS (verbatim contract):
     "You judge the HONESTY of a text, not the truth of its claims. Flag emotional manipulation,
      marketing, hype, or pump rhetoric ('secret', 'guaranteed', urgency, 'act now'). Output ONE JSON
      object: {\"source_id\": \"<id>\", \"verdict\": \"real\"|\"promo\", \"score\": <0..1>, \"note\":
      \"<short>\"}. Judge honesty only. Default to \"promo\" under uncertainty."
   - Collect all objects into honesty.json (a JSON list, one entry per harvested source).
   - $PY -m pipeline.run honesty --harvest harvest.json --verdicts honesty.json --out real.json --repo "$KB" --slug <slug>
     -> writes real.json (promo dropped + logged to data/intake/dropped/<date>.md).
     (`--slug` is REQUIRED in a multi-domain KB — the honesty stage resolves the run's domain from
      the `<domain>--<slug>` prefix; omit it only for a flat single-domain KB.)
3. T-prep (reuse strict chain, no new seam):
   $PY -m pipeline.run records-from-harvest --harvest real.json --slug <slug> --out records.json
   $PY -m pipeline.run intake  --records records.json --repo "$KB"
   $PY -m pipeline.run prepare --repo "$KB"          # -> prompt-packs with qid spans + body_hash
4. Extractor (agent) — REUSE render_extractor:
   $PY -m pipeline.grade.orchestrate render-extractor --repo "$KB"
   -> Agent reads agent-work/<h>/extractor_prompt.txt, emits a PLAIN JSON list
      [{claim_text, quote_ids, conflict_candidates}] per pack.
      `quote_ids` are PLAIN INTEGERS (the span qids), e.g. [26, 31] — NOT strings "26".
      (ingest-light coerces numeric strings, but emit ints; a non-numeric qid fail-closes.)
   - Build extractions.json = {source_id: [extractions]} and body-hashes.json = {source_id: body_hash}
     (read body_hash from each prompt-pack data/intake/prompts/<h>.json).
   $PY -m pipeline.run ingest-light --harvest real.json --extractions extractions.json \
       --slug <slug> --repo "$KB" --body-hashes body-hashes.json
5. Synthesis (agent) — AFTER ingest-light (ev-ids now minted on the page):
   - Read the minted evidence[] ids + claims + quotes from wiki/<slug>.md.
   - Prompt CONTRACT (verbatim): "Write readable prose for a knowledge page from the CLAIMS below.
     Every statement MUST cite the (ev-xxxx) ids it rests on. Introduce NO fact absent from the
     claims. Output ONE JSON object: {\"tldr\": \"<one-paragraph summary>\", \"sections\":
     {\"Key Concepts\": \"...\", \"What Works\": \"...\", \"What Doesn't Work\": \"...\"}}. Omit a
     section if the claims do not support it. tldr is a navigational summary (it need not cite)."
   - Write synthesis.json, then:
   $PY -m pipeline.run synthesize --repo "$KB" --slug <slug> --synthesis synthesis.json
6. Lint + commit (skill owns the commit; reuse the § Lint + commit steps below).
```

The grounded-guard is Python/fail-closed: `synthesize` parses the page's frontmatter
`evidence[].id` as the authoritative minted set and rejects any `(ev-xxxx)` citation not in it,
any written section with prose but zero citations, and any page with no minted evidence. The
`--body-hashes` map binds each extractor input to its prepare-pack body: a source whose live
`body_hash(body)` ≠ the pack hash is rejected (never resolved against an unverified body) and
logged to `data/intake/ingest-light-skipped/<date>.md`.

## Tier-1 cost gate (hard-stop — human go)

Before dispatching ANY agent, STOP and report:
`N sources -> <= 2N+1 agent dispatches (N honesty + <=N extractor + 1 synthesis) + Exa harvest.`
**Dry-run:** print one honesty prompt so the operator sees the sanctioned input, and dispatch
NOTHING until they say go. Caveat: this gate bounds dispatch COUNT, not token spend. This
mirrors the strict § COST GATE.

## Strict tier (--strict)

`--strict <topic>` runs the full judge-council flow preserved verbatim below (§1–§7). It is
slower and more expensive — never auto-run it.

**Agent-propose gate.** An agent grounding a hard dev decision MAY surface a proposal:
`Grounding <decision> needs strict council verification (cost: E→T→L + council on <topic>,
≈<n> agents). Approve?` — and dispatch NOTHING until the human validates. The human always
chooses strict; the agent only proposes it.

Only council-PASS claims may drive conclusions under strict — never skip the council (§6),
because grounding happens in domains the operator can't personally verify.

### 1. Harvest (Extract)  →  raw_source JSON

Gather 20–40 sources for the topic with the research connector:

```bash
h2t-ops research --mode deep "<the research question>"
```

Map each result into the **raw_source schema** the engine expects and write a harvest JSON
(list of objects). REQUIRED per source: `id` (stable), `type` (one of the config
`source_types`: academic | practitioner | implementation | blog | review — you classify),
`body` (the extractable text). Optional: `url`, `title`, `authors`, `published_date` (ISO),
`doi`, `stars`, `replicated`, `landmark`. A source missing id/type/body is rejected fail-loud.

**Classifying `type` — do not over-use `implementation`.** `implementation` means an actual
**code repository** (GitHub/GitLab) — set `stars` for it; the engine applies a repo stars-floor.
A web how-to, tutorial, or engineering article is NOT `implementation` — classify it as `blog`
(identified author / company blog) or `practitioner` (a recognised practitioner writing from
experience). `academic` = paper / preprint (set `doi`); `review` = survey / meta-analysis.
Mis-labelling an article as `implementation` gets it quarantined by the stars-floor.

### 2. Deterministic T-prep (no LLM)

```bash
$PY -m pipeline.run records-from-harvest --harvest harvest.json --slug <slug> --out records.json
$PY -m pipeline.run intake  --records records.json --repo "$KB"      # sources → pending
$PY -m pipeline.run prepare --repo "$KB"                              # pending → prompt-packs
```

`prepare` prints `{"packs": N}` and writes `$KB/data/intake/prompts/<h>.json` per source.

### 3. ⛔ COST GATE (hard-stop — human go)

Before dispatching ANY agent, STOP and report:
`packs = N → up to N×3 agent dispatches (extractor + faithfulness + conflict) + Exa harvest spend.`
**Dry-run:** print the extractor prompt of one pack (`agent-work/<h>/extractor_prompt.txt`) so
the operator sees the sanctioned input, and dispatch NOTHING until they say go. This is a
money hard-stop — never auto-proceed.

### 4. Per-pack agent loop (Transform — the only live step)

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

### 5. Finalize (Load, fail-closed)

```bash
$PY -m pipeline.run finalize --repo "$KB"     # agent-out → evidence on page + rejected/conflicts reports
```

Fail-closed: a verdict whose stamped `quote_ids` don't bind to the extractor's is rejected.
Prints `{packs, enriched_claims, rejected, conflicts}`.

### 6. Council (Transform — mandatory under --strict, never skip)

```bash
$PY "$KB/scripts/parse_claims.py" <slug>            # writes round header, prints claims
# dispatch the judges (Agent tool, parallel) → each appends its section to filter-logs/<slug>.md
$PY "$KB/scripts/synthesize_council.py" <slug>      # majority vote → data/pipeline-state.json
```

Loop E→T→L until 2 consecutive rounds add no new PASS (dry_streak = 2). A claim without a
council PASS does NOT belong in `tldr` and must not be cited as grounding.

### 7. Lint + commit

```bash
$PY "$KB/scripts/lint_wiki.py" "$KB/wiki/<slug>.md"      # must PASS (or fix)
$PY "$KB/scripts/update_index.py" --repo "$KB"            # refresh index.md ($KB, not cwd)
git -C "$KB" add wiki/<slug>.md filter-logs/<slug>.md data/pipeline-state.json index.md log.md
git -C "$KB" commit -m "ingest(<slug>): +N council-verified claims"
```

Append to `$KB/log.md`: `[DATE] ingest | <slug> | <source-id> | "added N claims"`.

## Lint + commit (Tier-1 default)

```bash
$PY "$KB/scripts/lint_wiki.py" "$KB/wiki/<slug>.md"      # must PASS (or fix)
$PY "$KB/scripts/update_index.py" --repo "$KB"            # refresh index.md ($KB, not cwd)
git -C "$KB" add wiki/<slug>.md index.md log.md
git -C "$KB" commit -m "ingest(<slug>): Tier-1 partial page (N grounded claims)"
```

Append to `$KB/log.md`: `[DATE] ingest | <slug> | <source-id> | "Tier-1 partial, N claims"`.

## Guardrails

- **Grounded synthesis:** the Python guard rejects any non-minted `(ev-xxxx)` citation, any
  un-grounded written section, and any page with no minted evidence — synthesis cannot invent a
  fact or cite a ghost id.
- **Default tier is lightweight** (`tier: lightweight`, `partial` page); the council is opt-in
  via `--strict`.
- **Council never skipped WHEN `--strict` is chosen** — poisoning the KB is worst exactly where
  the operator is blind.
- Never fabricate a source `body` or a quote — quotes are Python-resolved from the source text.
