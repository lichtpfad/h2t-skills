---
title: "KB Skill Consolidation Implementation Plan"
status: "draft"
date: "2026-07-24"
milestone: ""
issue: ""
---
# KB Skill Consolidation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Consolidate `h2t-ops:kb-ingest`, `h2t-ops:kb-lint`, and the orphaned `kb-lookup.md` rule into one `h2t-ops:kb` skill with three modes (ingest / query / lint) via progressive disclosure.

**Architecture:** A thin dispatcher `SKILL.md` (overview + shared resolve-root + guardrails + a positive-REQUIRED routing table + one unified triggers-only `description`) routes to `references/{ingest,query,lint}.md`. ingest/lint bodies migrate as-is; query is newly authored from `kb-lookup.md`, generalized KB-agnostic. Old skill dirs are `git rm`-ed; the research-kb rule becomes a pointer stub that keeps the council-PASS rule inline.

**Tech Stack:** Claude Code plugin skills (markdown + YAML frontmatter). Testing = retrieval checks with subagents (writing-skills Iron Law), not pytest — the "code" is documentation.

**Spec:** `docs/superpowers/specs/2026-07-24-kb-skill-consolidation-design.md`

---

## File Structure

**Create (h2t-skills, branch `feat/kb-skill-consolidation`):**
- `plugins/h2t-ops/skills/kb/SKILL.md` — dispatcher
- `plugins/h2t-ops/skills/kb/references/ingest.md` — migrated kb-ingest body
- `plugins/h2t-ops/skills/kb/references/query.md` — newly authored, generalized
- `plugins/h2t-ops/skills/kb/references/lint.md` — migrated kb-lint body

**Remove (h2t-skills):**
- `plugins/h2t-ops/skills/kb-ingest/` (whole dir)
- `plugins/h2t-ops/skills/kb-lint/` (whole dir)

**Modify (separate repo research-kb, separate commit):**
- `C:/dev/research-kb/.claude/rules/kb-lookup.md` → pointer stub

**Test scaffolding (h2t-skills):**
- `docs/superpowers/plans/kb-consolidation-tests/fixture-kb/taxonomy.md` + minimal artifacts — for the KB-agnostic test (Task 8)

### Shared-snippet convention (DRY vs self-contained)

`SKILL.md` holds the canonical `resolve-root` snippet and guardrails. Each `references/*.md`
opens with a one-line back-reference **plus** the 2-line snippet repeated, so a mode file is a
self-contained linear pipeline once entered (project finding: linear pipeline guarantees the
gate is not jumped). This 2-line repeat is deliberate, not a DRY violation.

---

## Task 1: RED baseline — capture the real pre-change defect

**Files:** none (produces a baseline note appended to the plan or kept in the session).

The genuine defect: query does not exist as a skill; entry is fragmented. Capture it verbatim
BEFORE building, per the Iron Law.

- [ ] **Step 1: Dispatch a baseline subagent against the CURRENT plugin surface**

Dispatch one subagent (Agent tool, `general-purpose`) with this prompt:

```
You have the h2t-ops plugin skills available. For EACH request below, name which
skill (if any) you would invoke and why. Do NOT perform the work — just name the skill.
1. "заземли это решение в базе знаний" / "look it up in the KB"
2. "наполни KB по теме X" / "add findings to the knowledge base"
3. "проверь целостность KB" / "kb health"
4. "поискать и добавить в базу знаний" (search AND add)
Report each as: <request> -> <skill name or "none / would improvise / would ask operator">.
```

- [ ] **Step 2: Record the result verbatim**

Expected RED signal (documents the defect the consolidation fixes):
- Request 1 (query) → **no skill** surfaces the lookup protocol (it is not in the plugin).
- Requests 2 & 3 → resolve, but to two *separate* skills (`kb-ingest`, `kb-lint`).
- Request 4 (compound) → no single owner.

Paste the subagent's actual output under a "RED baseline" heading in this plan file. If request 1
already routes somewhere sensible, STOP — the premise is wrong and the plan needs revisiting.

- [ ] **Step 3: Commit the baseline record**

```bash
git -C C:/dev/h2t-skills add docs/superpowers/plans/2026-07-24-kb-skill-consolidation.md
git -C C:/dev/h2t-skills commit -m "test(kb): RED baseline — query absent, entry fragmented"
```

---

## Task 2: Author the dispatcher SKILL.md

**Files:**
- Create: `plugins/h2t-ops/skills/kb/SKILL.md`

- [ ] **Step 1: Write `plugins/h2t-ops/skills/kb/SKILL.md`**

```markdown
---
name: h2t-ops:kb
description: "Use when working with the Ecosystem Research KB or any llm-kb-template instance: knowledge base, база знаний, add to the knowledge base / добавить в базу знаний, learn from the knowledge base / узнать из базы знаний, search and add to the KB / поискать и добавить в базу знаний, ground a decision in the KB, kb-ingest, kb-lint, kb-lookup, KB health. Human-invoked; ingest is COST-GATED."
compatibility: "Requires an llm-kb-template instance (default C:/dev/research-kb, override H2T_KB_ROOT) with its .venv, and the h2t-ops research connector for ingest harvest."
metadata:
  author: lichtpfad
  version: 0.1.0
---

# h2t-ops:kb

One entry point for the shared Ecosystem Research KB (an `llm-kb-template` instance). Three
modes; read the mode file before acting.

## Resolve the KB root (all modes)

```bash
KB="${H2T_KB_ROOT:-C:/dev/research-kb}"
PY="$KB/.venv/Scripts/python"      # Windows; Linux/mac: $KB/.venv/bin/python
```

## Guardrails (all modes)

- **Python never calls an LLM** — agents are dispatched only via the Agent tool, between deterministic Python stages.
- **Council never skipped under `--strict`** — poisoning the KB is worst where the operator is blind.
- One stage per CLI call. Frequent small commits. `git mv` / `git rm` only.

## Routing

| Intent | Action |
|--------|--------|
| Fill the KB from research (ingest, наполни KB, add to knowledge base, зафиксируй ресёрч) | **REQUIRED:** read `references/ingest.md` and follow it before any ingest action (it holds the cost-gate). |
| Ground a decision in the KB (ground, заземли, узнать из базы знаний, kb-lookup, look up in KB) | **REQUIRED:** read `references/query.md` and follow it before grounding. |
| Check KB integrity (lint, проверь KB, KB health) | **REQUIRED:** read `references/lint.md` and follow it. |
| Compound: search AND add (поискать и добавить в базу знаний, search and add to the KB) | **REQUIRED:** read `references/query.md` first; only if its gap-fill fires, then read `references/ingest.md`. Query-then-ingest, not a fourth mode. |
```

- [ ] **Step 2: Verify frontmatter is under the 1024-char limit**

Run: `git -C C:/dev/h2t-skills diff --cached` is not needed yet; instead eyeball the frontmatter
block (lines between the two `---`). The `description` above is ~430 chars; `name` +
`compatibility` + `metadata` add ~230 → ~660 total, under 1024. If a later edit pushes it over,
trim the `compatibility` line first (least load-bearing).

- [ ] **Step 3: Commit**

```bash
git -C C:/dev/h2t-skills add plugins/h2t-ops/skills/kb/SKILL.md
git -C C:/dev/h2t-skills commit -m "feat(kb): dispatcher SKILL.md — triggers-only description + positive routing"
```

---

## Task 3: Migrate ingest.md

**Files:**
- Create: `plugins/h2t-ops/skills/kb/references/ingest.md`
- Source: `plugins/h2t-ops/skills/kb-ingest/SKILL.md` (still present; removed in Task 6)

- [ ] **Step 1: Copy the kb-ingest body into the reference, minus the frontmatter and the hoisted shared parts**

Create `references/ingest.md`. Take the ENTIRE body of `kb-ingest/SKILL.md` (everything after the
closing `---` of its frontmatter) with these edits:
- Drop the YAML frontmatter (the dispatcher owns `name`/`description`).
- Replace its `## 0. Resolve the KB root` section with the 2-line self-contained opener:

```markdown
# kb — ingest mode

> Resolve `KB`/`PY` per SKILL.md § "Resolve the KB root" (repeated for a self-contained run):
> `KB="${H2T_KB_ROOT:-C:/dev/research-kb}"` · `PY="$KB/.venv/Scripts/python"`
```

- Keep verbatim (load-bearing, do NOT paraphrase): the Default Tier-1 flow, the **Tier-1 cost
  gate hard-stop**, the Strict tier (§1–§7 including the ⛔ COST GATE), the grounded-guard
  paragraph, both Lint+commit blocks, and the Guardrails list.
- In the Guardrails list, you may drop the two lines already hoisted to SKILL.md (Python-never-
  LLM; git mv/rm) to avoid duplication — but KEEP the ingest-specific ones (grounded synthesis,
  default-tier-lightweight, council-never-skipped-when-strict).

- [ ] **Step 2: Verify the two cost-gates survived the move**

Run: `grep -n "COST GATE" C:/dev/h2t-skills/plugins/h2t-ops/skills/kb/references/ingest.md`
Expected: at least the Tier-1 "hard-stop — human go" gate and the strict "⛔ COST GATE" are present.
Run: `grep -n "strict" C:/dev/h2t-skills/plugins/h2t-ops/skills/kb/references/ingest.md`
Expected: `--strict` tier section present.

- [ ] **Step 3: Commit**

```bash
git -C C:/dev/h2t-skills add plugins/h2t-ops/skills/kb/references/ingest.md
git -C C:/dev/h2t-skills commit -m "feat(kb): migrate kb-ingest body -> references/ingest.md (gates preserved)"
```

---

## Task 4: Migrate lint.md

**Files:**
- Create: `plugins/h2t-ops/skills/kb/references/lint.md`
- Source: `plugins/h2t-ops/skills/kb-lint/SKILL.md`

- [ ] **Step 1: Write `references/lint.md`**

```markdown
# kb — lint mode

> Resolve `KB`/`PY` per SKILL.md § "Resolve the KB root" (repeated for a self-contained run):
> `KB="${H2T_KB_ROOT:-C:/dev/research-kb}"` · `PY="$KB/.venv/Scripts/python"`

Thin wrapper over the engine's `lint_wiki.py` (config-bound source-type / verdict / council
checks). Read-only.

```bash
$PY "$KB/scripts/lint_wiki.py" "$KB/wiki/"        # all pages; or a single wiki/<slug>.md
```

Exit 0 = all pages PASS; non-zero = at least one violation (printed per page). On FAIL, report
the offending pages + first violations; do not "fix" content silently — a lint failure on a KB
page means the claim/verdict/council data is malformed and needs the operator or a kb re-ingest
(mode: ingest), not a cosmetic patch.
```

- [ ] **Step 2: Verify the read-only clause survived**

Run: `grep -n "do not .fix. content silently\|read-only\|Read-only" C:/dev/h2t-skills/plugins/h2t-ops/skills/kb/references/lint.md`
Expected: the "do not fix silently" clause is present.

- [ ] **Step 3: Commit**

```bash
git -C C:/dev/h2t-skills add plugins/h2t-ops/skills/kb/references/lint.md
git -C C:/dev/h2t-skills commit -m "feat(kb): migrate kb-lint body -> references/lint.md"
```

---

## Task 5: Author query.md (generalized, KB-agnostic)

**Files:**
- Create: `plugins/h2t-ops/skills/kb/references/query.md`
- Source of intent: `C:/dev/research-kb/.claude/rules/kb-lookup.md`

- [ ] **Step 1: Write `references/query.md`**

```markdown
# kb — query mode

Ground a decision in the KB instead of asking the operator: justify/refute a claim, choose a
method in an unfamiliar domain, or check a fact where neither you nor the operator has verified
expertise. **Only council-PASS claims may drive conclusions.**

> Resolve `KB`/`PY` per SKILL.md § "Resolve the KB root" (repeated for a self-contained run):
> `KB="${H2T_KB_ROOT:-C:/dev/research-kb}"` · `PY="$KB/.venv/Scripts/python"`

This mode is **KB-agnostic**: instance ontology is read from the KB (`$KB/taxonomy.md`,
`$KB/index.md`); the `llm-kb-template` artifact **schema** is assumed (every instance shares the
one engine). **Fail loud** if a required artifact is missing (no page, no `pipeline-state.json`,
no council round) — never silently answer ungrounded.

## Step 1 — Find the cluster

Read `$KB/taxonomy.md` for the instance's ontology, then keyword-search:
```
Grep pattern="<keyword>" path="$KB/wiki/" --output_mode content -C 2
```

## Step 2 — Read the topic (3 levels)

- **L1** overview: `$KB/index.md` (keywords + tldr).
- **L2** evidence (frontmatter of `$KB/wiki/<slug>.md`): in `evidence[]` look at `claim`,
  `verdict`, `replicated: true` (≥2 independent sources), `single_source_warning: true`,
  `sources[].ref`, `confidence`.
- **L3** full page: read `$KB/wiki/<slug>.md` whole (Key Concepts / What Works / What Doesn't Work).

## Step 3 — Check the council (mandatory)

A claim that only passed lint is NOT verified. Only council PASS = reliable.
```
Read "$KB/data/pipeline-state.json"
```
For the slug find `council_results.round_N.pass[]` / `fail[]` (id-keyed `ev-xxxx`; `round_N.labels`
maps id→claim). Judging detail: `Read "$KB/filter-logs/<slug>.md"`. If the file, the slug, or a
council round is absent → fail loud (do not fall back to an unrecorded answer).

## Step 4 — Trust hierarchy

| Signal | Weight | Use |
|--------|--------|-----|
| CONFIRMED + replicated + council PASS | ★★★ | strong — cite directly |
| CONFIRMED + council PASS | ★★ | sufficient |
| LIKELY + council PASS | ★ | moderate — add a caveat |
| HYPOTHESIS / single_source_warning + council PASS | ⚠ | weak — state the limit |
| council FAIL (any verdict) | ✗ | do NOT use as grounding |

## Step 5 — Gap → fill it (capture ≠ ingest)

If the KB has no PASS-claim for the question, do NOT silently fall back to an unrecorded search.
- **Routine:** any `h2t-ops research` you run captures to `~/.h2t/research/`; mark it for KB
  ingest (interactive: ask; autonomous: auto-mark). Heavy ingest runs in batch, not per lookup.
- **Urgent gap** (need a verified claim NOW to decide): run a targeted **`kb ingest --strict
  "<the question>"`** (cost-gated) and ground on the council-PASS result.
  **Why `--strict`:** default ingest is Tier-1 lightweight — no council, `partial` page, never
  council-PASS. Query may ground only on council-PASS, so the urgent-gap path REQUIRES strict.

## Antipatterns

- No claim used without a council check — the wiki verdict was set by an agent; the council may
  have overturned it.
- Don't generalize one FAIL to a whole topic. Don't cite HYPOTHESIS as fact.
- Don't ignore `What Doesn't Work` — council-verified failures are often more valuable.
```

- [ ] **Step 2: Verify the two load-bearing rules are present**

Run: `grep -n "council-PASS\|council PASS" C:/dev/h2t-skills/plugins/h2t-ops/skills/kb/references/query.md`
Expected: the "only council-PASS" rule appears (overview + step 3 + step 5).
Run: `grep -n "strict" C:/dev/h2t-skills/plugins/h2t-ops/skills/kb/references/query.md`
Expected: the `--strict` urgent-gap rule with its "why" is present.

- [ ] **Step 3: Commit**

```bash
git -C C:/dev/h2t-skills add plugins/h2t-ops/skills/kb/references/query.md
git -C C:/dev/h2t-skills commit -m "feat(kb): author query mode — KB-agnostic, council-PASS + --strict gap-fill"
```

---

## Task 6: Remove the old skills

**Files:**
- Remove: `plugins/h2t-ops/skills/kb-ingest/` and `plugins/h2t-ops/skills/kb-lint/`

- [ ] **Step 1: `git rm` both old skill dirs**

```bash
git -C C:/dev/h2t-skills rm -r plugins/h2t-ops/skills/kb-ingest plugins/h2t-ops/skills/kb-lint
```

- [ ] **Step 2: Confirm the plugin now exposes only `kb`**

Run: `ls C:/dev/h2t-skills/plugins/h2t-ops/skills/ | grep -i kb`
Expected: only `kb` (no `kb-ingest`, no `kb-lint`).

- [ ] **Step 3: Commit**

```bash
git -C C:/dev/h2t-skills commit -m "refactor(kb): git rm kb-ingest/kb-lint — folded into unified kb skill"
```

---

## Task 7: GREEN — routing + content-preservation

**Files:** none (verification).

- [ ] **Step 1: Dispatch a routing subagent with the new dispatcher as context**

To test routing deterministically (not dependent on plugin auto-discovery inside a subagent),
pass the actual dispatcher. Dispatch one `general-purpose` subagent:

```
Below is the FULL text of a skill's SKILL.md. For EACH request, name which references/*.md
file the routing table tells you to read, in order. Answer ONLY from the SKILL.md text.

<paste the full contents of plugins/h2t-ops/skills/kb/SKILL.md>

Requests:
1. "заземли это решение в базе знаний"           (expect: references/query.md)
2. "наполни KB по теме X"                         (expect: references/ingest.md)
3. "проверь целостность KB"                       (expect: references/lint.md)
4. "поискать и добавить в базу знаний"            (expect: query.md FIRST, then ingest.md)
5. "kb-ingest"                                     (expect: references/ingest.md — legacy name)
6. "kb-lint"                                       (expect: references/lint.md — legacy name)
7. "add this Notion knowledge base page to my wiki"        (expect: NONE — out of scope)
8. "search our Confluence knowledge base"                  (expect: NONE — out of scope)
9. "what does Salesforce Knowledge Base say about X"       (expect: NONE — out of scope)
Report each as: <n> -> <file(s) or NONE>.
```

- [ ] **Step 2: Assert 6/6 in-scope route correctly + 0/3 false triggers**

Expected: requests 1–6 match the parenthesized target; requests 7–9 return NONE (the skill is
scoped to `llm-kb-template`/research-kb instances, not arbitrary "knowledge base" products).
If any in-scope request mis-routes → REFACTOR the routing table wording and re-run.
If any of 7–9 fires → tighten the `description` scoping and re-run.

- [ ] **Step 3: Content-preservation diff for migrated bodies**

Run each and confirm the safety gates survived migration (they must still be present):
```bash
grep -c "COST GATE" C:/dev/h2t-skills/plugins/h2t-ops/skills/kb/references/ingest.md
grep -c "strict"    C:/dev/h2t-skills/plugins/h2t-ops/skills/kb/references/ingest.md
grep -c "silently"  C:/dev/h2t-skills/plugins/h2t-ops/skills/kb/references/lint.md
grep -c "council-PASS\|council PASS" C:/dev/h2t-skills/plugins/h2t-ops/skills/kb/references/query.md
```
Expected: all counts ≥ 1. A zero = a dropped safety gate → fix before proceeding.

- [ ] **Step 4: Record GREEN result + commit**

Paste the subagent output + grep counts under a "GREEN" heading in this plan.
```bash
git -C C:/dev/h2t-skills add docs/superpowers/plans/2026-07-24-kb-skill-consolidation.md
git -C C:/dev/h2t-skills commit -m "test(kb): GREEN — routing 6/6, 0/3 false triggers, gates preserved"
```

---

## Task 8: KB-agnostic proof against a second instance

**Files:**
- Create: `docs/superpowers/plans/kb-consolidation-tests/fixture-kb/taxonomy.md`
- Create: `docs/superpowers/plans/kb-consolidation-tests/fixture-kb/index.md`
- Create: `docs/superpowers/plans/kb-consolidation-tests/fixture-kb/wiki/widget-testing.md`
- Create: `docs/superpowers/plans/kb-consolidation-tests/fixture-kb/data/pipeline-state.json`

- [ ] **Step 1: Build a minimal fixture KB with a DIFFERENT taxonomy**

Create `fixture-kb/taxonomy.md` with an ontology unlike research-kb's role tiers:

```markdown
# Fixture Taxonomy
- domain: widgets
  - slug: widget-testing — how to test widgets
```

Create `fixture-kb/index.md`:

```markdown
# Index
- widget-testing — keywords: widget, test, assertion — tldr: how to test widgets
```

Create `fixture-kb/wiki/widget-testing.md`:

```markdown
---
slug: widget-testing
evidence:
  - id: ev-0001
    claim: "Widgets must be tested in isolation"
    verdict: CONFIRMED
    replicated: true
    sources:
      - ref: "src-a"
    confidence: 0.9
---
# Widget Testing
## What Works
Test widgets in isolation (ev-0001).
```

Create `fixture-kb/data/pipeline-state.json`:

```json
{
  "widget-testing": {
    "council_results": {
      "round_1": {
        "pass": ["ev-0001"],
        "fail": [],
        "labels": {"ev-0001": "Widgets must be tested in isolation"}
      }
    }
  }
}
```

- [ ] **Step 2: Dispatch a KB-agnostic subagent**

Dispatch one `general-purpose` subagent:

```
Below is the FULL text of references/query.md. Then follow it to answer, treating
H2T_KB_ROOT = docs/superpowers/plans/kb-consolidation-tests/fixture-kb (read files there).

<paste plugins/h2t-ops/skills/kb/references/query.md>

Question: "Should widgets be tested in isolation? Ground the answer."
Report: (a) which cluster/slug you found from taxonomy.md, (b) the council verdict for the
claim from pipeline-state.json, (c) your grounded answer citing the ev-id, (d) confirm you
would fail loud if pipeline-state.json were absent.
```

- [ ] **Step 3: Assert the mode worked against the foreign taxonomy**

Expected: (a) finds `widget-testing` from the fixture's own `taxonomy.md` (NOT research-kb tiers),
(b) reads `ev-0001` PASS from the fixture `pipeline-state.json`, (c) grounds the answer on
`ev-0001`, (d) affirms fail-loud on missing artifacts. This is the only test that exercises the
KB-agnostic claim. Mis-behavior → fix query.md's KB-root handling.

- [ ] **Step 4: Commit the fixture + result**

```bash
git -C C:/dev/h2t-skills add docs/superpowers/plans/kb-consolidation-tests docs/superpowers/plans/2026-07-24-kb-skill-consolidation.md
git -C C:/dev/h2t-skills commit -m "test(kb): KB-agnostic proof — query grounds against a 2nd instance"
```

---

## Task 9: research-kb pointer stub (separate repo, separate commit)

**Files:**
- Modify: `C:/dev/research-kb/.claude/rules/kb-lookup.md` (replace with stub)

- [ ] **Step 1: Create a branch in research-kb**

```bash
git -C C:/dev/research-kb checkout -b chore/kb-lookup-pointer
```

- [ ] **Step 2: Replace `kb-lookup.md` with the pointer stub**

Overwrite `C:/dev/research-kb/.claude/rules/kb-lookup.md` with:

```markdown
# KB Lookup — pointer

**Ground only on council-PASS claims.** (Non-negotiable — kept here so the rule survives even
if the plugin skill fails to load.)

The full lookup protocol now lives in the **`h2t-ops:kb` skill, query mode**
(`plugins/h2t-ops/skills/kb/references/query.md` in h2t-skills). Invoke it for any KB grounding.

## This instance

This KB is the **research-kb** instance. Its ontology is role-tiered — see `taxonomy.md`
(Ventures · Craft · Educator · Builder).

## Federation (linked, not stored here)

A domain with its own KB → look there directly, don't duplicate:
- crypto / quant trading → `C:/dev/quant-kb` (has its own kb-lookup).
- DCC (TouchDesigner/Houdini) → `C:/work/TD`.
- agentic-dev / LLM-tooling → `C:/dev/agentic-kb`.
```

- [ ] **Step 3: Commit**

```bash
git -C C:/dev/research-kb add .claude/rules/kb-lookup.md
git -C C:/dev/research-kb commit -m "chore(kb-lookup): point to h2t-ops:kb query; keep council-PASS rule + federation inline"
```

- [ ] **Step 4: (Human) decide merge path for research-kb**

The research-kb change is small and self-contained. Offer the operator: merge the branch or open
a PR. Do not auto-merge — separate repo, operator decision.

---

## Task 10: Finalize h2t-skills branch

**Files:** none.

- [ ] **Step 1: Bump the h2t-ops plugin version if the repo tracks it per-plugin**

Check `plugins/h2t-ops/.claude-plugin/plugin.json` (or equivalent) for a version field. If the
consolidation is a user-visible change, bump the patch/minor per the repo's versioning policy.
If no per-plugin version is tracked, skip.

- [ ] **Step 2: Push and open a PR**

```bash
git -C C:/dev/h2t-skills push -u origin feat/kb-skill-consolidation
```
Then open a PR summarizing: 3→1 skill consolidation, new query mode, migration + tests, codex-adjudicated spec.

- [ ] **Step 3: (Human) merge decision** — operator merges after review.

---

## Self-Review (author checklist — completed)

**Spec coverage:**
- Architecture (thin SKILL.md + 3 references) → Tasks 2–5. ✓
- description triggers-only → Task 2 Step 1 + Task 7 false-trigger check. ✓
- KB-agnostic query + fail-loud + --strict gap-fill → Task 5 + Task 8. ✓
- pointer stub keeps council-PASS inline → Task 9. ✓
- git rm old skills (accepted risk) → Task 6. ✓
- Testing: real RED (Task 1), GREEN routing + content-preservation (Task 7), KB-agnostic (Task 8), false-trigger 3 cases (Task 7). ✓
- Positive-REQUIRED routing → Task 2 routing table. ✓

**Placeholder scan:** no TBD/TODO; every mode file body is shown; grep verifications are exact. ✓

**Type/name consistency:** skill name `h2t-ops:kb`, mode files `references/{ingest,query,lint}.md`,
`H2T_KB_ROOT`/`KB`/`PY`, `council-PASS`, `--strict` — used consistently across tasks. ✓

**Note on testing method:** retrieval tests pass the actual SKILL.md/query.md text to the subagent
rather than relying on plugin auto-discovery inside a subagent (more deterministic; discovery in
subagents is unverified on this setup). This tests the routing/grounding *logic* the skill encodes.

---

## RED baseline (Task 1 — captured 2026-07-24)

Routing oracle given ONLY the two existing kb-skill descriptions (kb-ingest, kb-lint), asked to
route 4 requests. Verbatim result:

1. "заземли/look it up to ground a decision" → **NONE — no skill covers this** (A writes into the
   KB, B lints it; neither reads/queries to ground a decision). ← the real defect query fixes.
2. "наполни KB / add findings" → `h2t-ops:kb-ingest`.
3. "проверь целостность KB / kb health" → `h2t-ops:kb-lint`.
4. "поискать и добавить" (compound) → only `kb-ingest` covers the "add" half; "the search half has
   no dedicated skill" → no single owner. ← confirms query absent + compound unowned.

RED confirmed: query has no skill; entry fragmented across two; compound unowned. Premise holds.

## GREEN (Task 7 — captured 2026-07-24)

Routing oracle given the full unified `SKILL.md`, 9 requests:

1. "заземли..." → `references/query.md` ✓
2. "наполни KB..." → `references/ingest.md` ✓
3. "проверь целостность KB" → `references/lint.md` ✓
4. "поискать и добавить..." → `references/query.md` then `references/ingest.md` (compound) ✓
5. "kb-ingest" (legacy) → `references/ingest.md` ✓
6. "kb-lint" (legacy) → `references/lint.md` ✓
7. "Notion knowledge base" → **NONE — out of scope** ✓
8. "Confluence knowledge base" → **NONE — out of scope** ✓
9. "Salesforce Knowledge Base" → **NONE — out of scope** ✓

Routing 6/6 in-scope correct + 0/3 false triggers.

Content-preservation (grep counts on migrated bodies): `COST GATE`=2 (Tier-1 hard-stop +
strict ⛔), `--strict`=6, lint `"fix" content silently`=1, `council-PASS`=7. No safety gate
dropped in migration. GREEN passes.

## KB-agnostic proof (Task 8 — captured 2026-07-24)

A subagent read the real `references/query.md` and followed it against a fixture KB
(`kb-consolidation-tests/fixture-kb`) whose taxonomy is "widgets" (NOT research-kb's role
tiers), `H2T_KB_ROOT` pointed there. Result:
- (a) found slug `widget-testing` from the fixture's OWN `taxonomy.md` — not research-kb tiers.
- (b) read council PASS `ev-0001` from the fixture `data/pipeline-state.json`
  (`["widget-testing"]["council_results"]["round_1"]["pass"][0]`).
- (c) grounded the answer on `ev-0001` (★★★ CONFIRMED+replicated+PASS).
- (d) restated the fail-loud contract: absent file/slug/round → stop, do not fall back;
  only Step-5 gap path (`kb ingest --strict`) is allowed.

The KB-agnostic claim is exercised and holds: query works against a second instance via
`H2T_KB_ROOT`, reads that instance's own ontology, and enforces council-PASS + fail-loud.
