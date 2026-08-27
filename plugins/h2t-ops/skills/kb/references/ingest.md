# kb — ingest mode

> **Data-only model.** The engine is installed as the `llm-kb-engine` tool (`uv tool install
> llm-kb-engine`); the KB is data-only (no engine files). Resolve the KB root per SKILL.md
> § "Resolve the KB root": `H2T_KB_ROOT` is required.
>
> **Two ways the engine is invoked:**
> - **Console-scripts** — cwd-independent, always driven with `--repo "$KB"`:
>   `run <stage>` · `kb-lint` · `kb-index` · `kb-parse-claims` · `kb-council`.
> - **`ENGINE_PY`** — one module (`pipeline.grade.orchestrate`) has no console-script, so call it
>   with the engine-venv python:
>   `ENGINE_PY="$(uv tool dir)/llm-kb-engine/Scripts/python"` (Win) ·
>   `.../llm-kb-engine/bin/python` (Linux/mac). **Prefix `PYTHONIOENCODING=utf-8`** — orchestrate
>   prints non-ASCII quotes and crashes on the Windows default codepage otherwise.

Turn a research question into a **grounded knowledge page** in the shared KB. The engine
(`llm-kb-engine`) owns every deterministic seam; this skill drives them and dispatches the
agents. **Python never calls an LLM.**

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

Resolve the target **domain and slug** first. Read `$KB/kb.config.json`:

- **Multi-domain KB** (`domains[]` present): resolve the domain with the **classify → propose →
  confirm** gate (mirrors the query L0 router, but STRICTER because ingest is a durable write —
  writing a page into the wrong domain is a mutation, not a re-read). Classify the topic against
  `kb.config.json.domains[].name`, then:
  - **Always PROPOSE the target domain and get the operator's confirmation before writing**
    (AskUserQuestion) — even when one domain looks obvious. **Never** silently write to the
    in-conversation / "current" domain; a gap-fill inherited from a read must NOT reuse the read's
    domain without re-classifying and asking.
  - Ambiguous / low-confidence / two plausible domains → propose the best-fit options and let the
    operator pick.
  - No existing domain fits → **propose** creating one (gated — operator approves); **never**
    silently invent a domain, **never** decline.

  Once confirmed, the page slug is `<domain>--<topic-slug>`, and the stub
  `$KB/wiki/<domain>--<topic-slug>.md` must exist AND carry a `domain: <domain>` frontmatter field.
  Scaffold it with `kb-scaffold --repo "$KB"` (it stamps `domain:`); never hand-write a stub without
  the `domain:` field — the linter rejects it. Every `<slug>` below is this domain-prefixed value.
- **Flat single-domain KB** (no `domains[]`): `<slug>` is a plain topic slug from `$KB/taxonomy.md`
  (existing topic) or a new row you add first; no `domain:` field. A `$KB/wiki/<slug>.md` stub must
  exist before ingest writes onto it.

One ingest run targets **exactly one domain** — the engine derives it from the slug prefix and
fails loud on a batch that mixes domains.

## Multi-domain KB

One central KB can hold many specialised domains via `base ⊕ override(domain)`: shared defaults in
`kb.config.json.base`, per-domain overrides in `domains[].override` (judges, `source_type_policy`,
verdicts, …). Every grading stage resolves the run's domain from the `<domain>--<slug>` page slug
and applies that domain's config; there is no global "current domain". A **flat** single-domain KB
(no `base`/`domains`) is unaffected — behaves exactly as before. Pick the domain before ingest;
one run = one domain.

## Default: Tier-1 lightweight flow

One CLI call per step (`run <stage> --repo "$KB"`). The agent passes (honesty, extractor,
synthesis) are dispatched via the Agent tool between the deterministic stages.

```
1. Harvest (Exa, `--full-text`) -> harvest.json  [reuse the §1 mapping to the raw_source schema
   below — each source MUST carry `fetch_mode: "full-text"` + `fetch_provider`, or ingest-light
   fail-closes it]
2. Honesty (agent):
   - Build ONE honesty prompt per source in the skill (input = a bounded head of the body + type + url).
   - Prompt LENS (verbatim contract):
     "You judge the HONESTY of a text, not the truth of its claims. Flag emotional manipulation,
      marketing, hype, or pump rhetoric ('secret', 'guaranteed', urgency, 'act now'). Output ONE JSON
      object: {\"source_id\": \"<id>\", \"verdict\": \"real\"|\"promo\", \"score\": <0..1>, \"note\":
      \"<short>\"}. Judge honesty only. Default to \"promo\" under uncertainty."
   - Collect all objects into honesty.json (a JSON list, one entry per harvested source).
   - run honesty --harvest harvest.json --verdicts honesty.json --out real.json --repo "$KB" --slug <slug>
     -> writes real.json (promo dropped + logged to data/intake/dropped/<date>.md).
     (`--slug` is REQUIRED in a multi-domain KB — the honesty stage resolves the run's domain from
      the `<domain>--<slug>` prefix; omit it only for a flat single-domain KB.)
3. T-prep (reuse strict chain, no new seam):
   run records-from-harvest --harvest real.json --slug <slug> --out records.json
   run intake  --records records.json --repo "$KB"
   run prepare --repo "$KB"          # -> prompt-packs with qid spans + body_hash
4. Extractor (agent) — REUSE render_extractor:
   PYTHONIOENCODING=utf-8 $ENGINE_PY -m pipeline.grade.orchestrate render-extractor --repo "$KB"
   -> Agent reads agent-work/<h>/extractor_prompt.txt, emits a PLAIN JSON list
      [{claim_text, quote_ids, conflict_candidates}] per pack.
      `quote_ids` are PLAIN INTEGERS (the span qids), e.g. [26, 31] — NOT strings "26".
      (ingest-light coerces numeric strings, but emit ints; a non-numeric qid fail-closes.)
   - Build extractions.json = {source_id: [extractions]} and body-hashes.json = {source_id: body_hash}
     (read body_hash from each prompt-pack data/intake/prompts/<h>.json).
   run ingest-light --harvest real.json --extractions extractions.json \
       --slug <slug> --repo "$KB" --body-hashes body-hashes.json
5. Synthesis (agent) — AFTER ingest-light (ev-ids now minted on the page):
   - Read the minted evidence[] ids + claims + quotes from wiki/<slug>.md.
   - Prompt CONTRACT (verbatim): "Write readable prose for a knowledge page from the CLAIMS below.
     Every statement MUST cite the (ev-xxxx) ids it rests on. Introduce NO fact absent from the
     claims. Output ONE JSON object: {\"tldr\": \"<one-paragraph summary>\", \"sections\":
     {\"Key Concepts\": \"...\", \"What Works\": \"...\", \"What Doesn't Work\": \"...\"}}. Omit a
     section if the claims do not support it. tldr is a navigational summary (it need not cite)."
   - Write synthesis.json, then:
   run synthesize --repo "$KB" --slug <slug> --synthesis synthesis.json
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

Gather 20–40 sources for the topic with the research connector. **`--full-text` is mandatory** —
without it the provider returns only highlights, the body is a snippet, and the engine fail-closes
the whole harvest (see `fetch_mode` below). `--json` gives the nested envelope
`{ok, provider, result: {status, results: [...]}}` — map `result.results[i]`:

```bash
h2t-ops research search --query "<the research question>" --mode deep --full-text --json
```

Map each result into the **raw_source schema** the engine expects and write a harvest JSON
(list of objects). REQUIRED per source: `id` (stable), `type` (one of the config
`source_types`: academic | practitioner | implementation | blog | review — you classify),
`body` (the extractable text), `fetch_mode`, `fetch_provider` (both below). Optional: `url`,
`title`, `authors`, `published_date` (ISO), `doi`, `stars`, `replicated`, `landmark`. A source
missing id/type/body is rejected fail-loud.
(`authors` must be a **list of strings** — a bare string gets split character-by-character.)

**`fetch_mode` — the gated provenance field (spec #6, fail-closed).** `records-from-harvest` and
`ingest-light` REJECT any source whose `fetch_mode != "full-text"` — a snippet body must never
reach extraction. Derive it honestly per source, tied to the SAME decision as `body`:
- the result carried non-empty `text` (full page) → `body` = that `text`, `fetch_mode: "full-text"`.
- only `highlights` came back → you joined them into `body`, `fetch_mode: "highlights"` — this
  source WILL be dropped, and that is intended. Do not label a highlights body `"full-text"`;
  provenance must never disagree with the body it describes.

With `--full-text` every returned result normally has `text` (~15 000 chars, provider-capped), so
all sources should honestly be `"full-text"`. If a source has no `text`, drop it or re-fetch —
never relabel.

**`fetch_provider`** — the provider that returned the body: `"exa"` for the Exa-backed research
search, `"github"` for a repo. Provenance metadata (carried onto the raw capture); not gated, but
always serialize it.

**Classifying `type` — do not over-use `implementation`.** `implementation` means an actual
**code repository** (GitHub/GitLab) — set `stars` for it; the engine applies a repo stars-floor.
A web how-to, tutorial, or engineering article is NOT `implementation` — classify it as `blog`
(identified author / company blog) or `practitioner` (a recognised practitioner writing from
experience). `academic` = paper / preprint (set `doi`); `review` = survey / meta-analysis.
Mis-labelling still matters even though the engine now guards it: an `implementation` source
with no `stars` is auto-reclassified to `blog` at intake (#27), so it is no longer quarantined —
but if you also set a `stars` value it is treated as a real repo and the stars-floor applies.
Classify correctly upfront regardless: that gives the right trust tier and the honesty check
(`implementation` is out of honesty scope); do not rely on the safety net.

### 2. Deterministic T-prep (no LLM)

```bash
run records-from-harvest --harvest harvest.json --slug <slug> --out records.json
run intake  --records records.json --repo "$KB"      # sources → pending
run prepare --repo "$KB"                              # pending → prompt-packs
```

`prepare` prints `{"packs": N}` and writes `$KB/data/intake/prompts/<h>.json` per source.

**If `intake` reports `skipped > 0`, read `skip_reasons` before re-harvesting.** The intake JSON
now names which corpus identity matched each skip, e.g.
`"skip_reasons": {"<id>": "exact-id (raw-index)"}`:

- `exact-id (raw-index)` — the id is in `raw-index.md` but on **no** wiki page: an earlier run was
  interrupted after the index write but before the page write (**partial-run**). The captures
  already exist — do **not** re-harvest. Re-drive the same records through extraction with the
  operator override:

  ```bash
  run intake --records records.json --repo "$KB" --reingest   # alias: --no-dedupe
  ```

  `--reingest` bypasses only the dedup verdicts (duplicate + uncertain-dedupe); the shill/stars/
  below trust gates stay live, bodies are read from the records file (no fetch), and the raw-index
  append is idempotent. Full runbook: `docs/partial-run-resume.md` in the engine repo.
- `exact-id (wiki-ref)` — the source is already bound on a page (genuine full duplicate). Do **not**
  `--reingest` it: the page evidence write is not idempotent and would double-write. Slice it out of
  `records.json` first.

> Scope: `--reingest` is wired on the `intake` subcommand. Threading it through the Tier-1
> `ingest-light`/`finalize` path is a follow-up (engine #57) — for a Tier-1 partial run, re-drive
> via `run intake` on the records, or slice the records to the un-bound sources.

### 3. ⛔ COST GATE (hard-stop — human go)

Before dispatching ANY agent, STOP and report:
`packs = N → up to N×3 agent dispatches (extractor + faithfulness + conflict) + Exa harvest spend.`
**Dry-run:** print the extractor prompt of one pack (`agent-work/<h>/extractor_prompt.txt`) so
the operator sees the sanctioned input, and dispatch NOTHING until they say go. This is a
money hard-stop — never auto-proceed.

### 4. Per-pack agent loop (Transform — the only live step)

For each pack hash `<h>` (run one stage per call — matches the engine convention).
`orchestrate` has no console-script → call it with `$ENGINE_PY` (see header) and
`PYTHONIOENCODING=utf-8`:

```bash
PYTHONIOENCODING=utf-8 $ENGINE_PY -m pipeline.grade.orchestrate render-extractor  --repo "$KB"   # writes extractor_prompt.txt
```
→ **Agent** (extractor): read `agent-work/<h>/extractor_prompt.txt`, emit `extractions.json`.
```bash
PYTHONIOENCODING=utf-8 $ENGINE_PY -m pipeline.grade.orchestrate build-faithfulness --repo "$KB"  # prompt + qids sidecar
```
→ **Agent** (faithfulness): emit `faithfulness.json`.
```bash
PYTHONIOENCODING=utf-8 $ENGINE_PY -m pipeline.grade.orchestrate build-conflict    --repo "$KB"   # iff candidates
```
→ **Agent** (conflict, only if a `conflict_prompt.txt` was written): emit `conflicts.json`.
```bash
PYTHONIOENCODING=utf-8 $ENGINE_PY -m pipeline.grade.orchestrate assemble          --repo "$KB"   # stamps qids → agent-out/<h>.json
```

The agent sees only sanctioned inputs (numbered spans by qid; Python-resolved quote text;
indexed conflict pairs). Python owns quote text and qids — an agent-supplied quote_id is
discarded at assemble (provenance enforced there).

### 5. Finalize (Load, fail-closed)

```bash
run finalize --repo "$KB"     # agent-out → evidence on page + rejected/conflicts reports
```

Fail-closed: a verdict whose stamped `quote_ids` don't bind to the extractor's is rejected.
Prints `{packs, enriched_claims, rejected, conflicts}`.

### 6. Council (Transform — mandatory under --strict, never skip)

In a multi-domain KB, `kb-parse-claims <slug>` and `kb-council <slug>` resolve the domain from the
`<domain>--<slug>` prefix and use **that domain's** judges / vote-threshold / judge-prompts — so the
slug MUST be domain-prefixed, or the council runs under the wrong (base) config.

```bash
kb-parse-claims <slug> --repo "$KB"            # writes round header, prints claims (id-keyed)
# dispatch the judges (Agent tool, parallel) → each appends its section to filter-logs/<slug>.md
kb-council <slug> --repo "$KB"                 # majority vote → data/pipeline-state.json + Council table
```

Loop E→T→L until 2 consecutive rounds add no new PASS (dry_streak = 2). A claim without a
council PASS does NOT belong in `tldr` and must not be cited as grounding.

**Bind the verdict onto the page (S3a).** `kb-council` records the majority vote in
`filter-logs/<slug>.md` + `data/pipeline-state.json`, but to stamp `judge_pass:` onto each
evidence entry — so `synthesize` excludes FAILed ids — apply the id-keyed Council table as a
`{ev-id: PASS|FAIL}` map:

```bash
run apply-verdicts --repo "$KB" --slug <slug> --verdicts verdicts.json   # verdicts.json = {ev-id: PASS|FAIL}
```

Build `verdicts.json` from the id-keyed Council table (first column = ev-id).

### 7. Lint + commit

```bash
kb-lint --repo "$KB" "$KB/wiki/<slug>.md"      # must PASS (or fix)
kb-index --repo "$KB"                          # refresh index.md ($KB, not cwd)
git -C "$KB" add wiki/<slug>.md filter-logs/<slug>.md data/pipeline-state.json index.md log.md
git -C "$KB" commit -m "ingest(<slug>): +N council-verified claims"
```

Append to `$KB/log.md`: `[DATE] ingest | <slug> | <source-id> | "added N claims"`.

## Lint + commit (Tier-1 default)

```bash
kb-lint --repo "$KB" "$KB/wiki/<slug>.md"      # must PASS (or fix)
kb-index --repo "$KB"                          # refresh index.md ($KB, not cwd)
git -C "$KB" add wiki/<slug>.md index.md log.md
git -C "$KB" commit -m "ingest(<slug>): Tier-1 partial page (N grounded claims)"
```

Append to `$KB/log.md`: `[DATE] ingest | <slug> | <source-id> | "Tier-1 partial, N claims"`.

> **Cleanup.** `run` stages leave working files under `$KB/data/intake/{pending,prompts,agent-out,
> agent-work,dropped,…}`. These are ingest scratch, not KB content — do NOT commit them (the KB
> should `.gitignore` `data/intake/`). Commit only `wiki/`, `index.md`, `log.md`, and (strict)
> `filter-logs/` + `data/pipeline-state.json`.

## Craft verdict (Opt3)

A second, ORTHOGONAL axis for a domain whose `override.verdicts` is a craft-ladder (e.g.
art-practice: CONTESTED / SITUATIONAL / ESTABLISHED-CRAFT, ranks 0/1/2). It records
craft-standing (endorsement strength) judged by an LLM-in-the-role-of-practitioner, NOT
evidence accumulation. Run it AFTER a page is council-graded (`judge_pass` stamped).

1. **Blind claim list.** Take ONLY `judge_pass:true` claims and emit `id + text` — NO
   sources / confidence / popularity cues, or the axis collapses into convergence.
   `parse_claims.format_claims_blind(claims)` does this.
2. **One verdict-judge (Agent), prompt verbatim:**

   > You are a seasoned visual-art practitioner and open-call juror (25+ years). For each numbered
   > advice-claim, assign ONE verdict AS PROFESSIONAL CRAFT ADVICE — from your own knowledge, NOT how
   > many sources repeat it:
   > - ESTABLISHED-CRAFT — a principle serious practitioners broadly hold as sound
   > - SITUATIONAL — useful but depends on context/medium/career stage
   > - CONTESTED — templated/superficial, a logistical tip, OR something practitioners disagree on
   > Do NOT default everything to ESTABLISHED-CRAFT. IGNORE any in-text popularity/source cues
   > ("across 11 artists", URLs). Output a table: | id | verdict | reason |

3. The judge appends `### Verdict-Judge: Practitioner` (a `| id | verdict | reason |` table) to
   `filter-logs/<slug>.md` under the current round.
4. **Apply with the engine:** `run apply-craft-verdicts <slug> --repo "$KB"` → page-side gate
   (rank>0 only on `judge_pass:true`) + lint fail-closed + atomic write.

> verdict — SINGLE-judge, un-cross-checked, HYPOTHESIS-grade сигнал: craft-standing по суждению
> LLM-в-роли-практика, не проверенная проф-истина. Валидирован на стабильность+ортогональность
> (проба #10), НЕ на проф-верность. Реальная валидация — за настоящим open-call экспертом.

## Guardrails

- **Grounded synthesis:** the Python guard rejects any non-minted `(ev-xxxx)` citation, any
  un-grounded written section, and any page with no minted evidence — synthesis cannot invent a
  fact or cite a ghost id.
- **Default tier is lightweight** (`tier: lightweight`, `partial` page); the council is opt-in
  via `--strict`.
- **Council never skipped WHEN `--strict` is chosen** — poisoning the KB is worst exactly where
  the operator is blind.
- Never fabricate a source `body` or a quote — quotes are Python-resolved from the source text.
