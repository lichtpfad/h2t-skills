# KB Skill Consolidation — Design

*Date: 2026-07-24 · Repo: h2t-skills · Branch: `feat/kb-skill-consolidation`*

## Problem

Three related capabilities for the shared Ecosystem Research KB (and any `llm-kb-template`
instance) are fragmented:

- `h2t-ops:kb-ingest` — heavy E→T→L pipeline (Tier-1 lightweight default + `--strict` council). Working, in `main`.
- `h2t-ops:kb-lint` — thin wrapper over the engine's `lint_wiki.py`. Working, in `main`.
- **query** — NOT a skill yet: it lives as a rule at `research-kb/.claude/rules/kb-lookup.md`, invisible to the global plugin surface. Promoting it into a command is a **new feature**.

Two working skills plus one orphaned rule mean: no single entry point, duplicated
KB-root resolution and guardrails, and the lookup protocol only reachable from inside
one KB instance.

## Goal

One consolidated `h2t-ops:kb` skill with **three working modes** (ingest / query / lint)
via progressive disclosure: a thin dispatcher `SKILL.md` + `references/*` per mode.

Grounded in first-party skill-authoring guidance (`superpowers:writing-skills`,
`plugin-dev:skill-development`, project `docs/SKILL-BEST-PRACTICES.md`) — NOT external
web research (the authoritative sources for "how to build skills" are local and first-party;
web harvest would be strictly weaker for this topic).

## Non-goals

- No changes to the `llm-kb-template` engine — the skill only drives existing deterministic seams.
- No live dogfood-ingest run as part of this work (that is a separate engine-validation task, Plan C).
- No new engine CLI stages; query reads existing KB artifacts (`taxonomy.md`, `index.md`, `wiki/<slug>.md`, `data/pipeline-state.json`, `filter-logs/<slug>.md`).

## Architecture

```
h2t-ops/skills/kb/
  SKILL.md            # thin dispatcher (<500 words, loads into context)
  references/
    ingest.md         # kb-ingest content as-is (Tier-1 default + --strict council)
    query.md          # generalized lookup protocol (promotion of kb-lookup.md)
    lint.md           # lint_wiki.py wrapper
```

### SKILL.md — dispatcher only

Carries the shared, mode-independent parts once (no duplication across references):

- KB overview: what the shared Ecosystem Research KB is; that the skill drives an `llm-kb-template` instance.
- Shared **resolve-root** snippet: `KB="${H2T_KB_ROOT:-C:/dev/research-kb}"`, `PY="$KB/.venv/Scripts/python"`.
- Shared **guardrails**: Python never calls an LLM; agents dispatched only via the Agent tool; council never skipped under `--strict`.
- **Routing table** (linear, one target per intent):

  | Intent | Trigger words | Read |
  |--------|---------------|------|
  | Fill the KB from research | ingest, наполни KB, add to knowledge base, зафиксируй ресёрч | `references/ingest.md` |
  | Ground a decision in the KB | ground, заземли, узнать из базы знаний, kb-lookup, look up in KB | `references/query.md` |
  | Check KB integrity | lint, проверь KB, KB health | `references/lint.md` |
  | **Compound: search AND add** | поискать и добавить в базу знаний, search and add to the KB | `query.md` **first** (is it already grounded?) → `ingest.md` only if the query mode's gap-fill fires |

  The compound intent is explicitly query-then-ingest, not a fourth mode: query first to
  avoid re-ingesting an already-grounded topic; ingest only on a genuine gap.

  **Routing must be a positive REQUIRED instruction**, not a prohibition (project finding:
  "запреты игнорируются — работают только позитивные инструкции"). Phrase each row's action as
  `**REQUIRED:** read references/<mode>.md and follow it before any <mode> action` — this
  matters most for ingest, whose cost-gate hard-stop lives inside `ingest.md`: a weak router
  risks Claude improvising an ingest and skipping the gate. The mode files stay linear so the
  gate cannot be jumped once entered.

### description — triggers only, no workflow summary

Single `description` covering all three modes, **triggering conditions only** (project +
first-party finding: a workflow summary in the description makes Claude improvise from the
description instead of reading the routed reference). Broad natural-language triggers, RU+EN,
per operator requirement:

> Use when working with the Ecosystem Research KB (or any `llm-kb-template` instance):
> knowledge base, база знаний, add to the knowledge base / добавить в базу знаний,
> learn from the knowledge base / узнать из базы знаний, search and add to the KB /
> поискать и добавить в базу знаний, kb-ingest, kb-lint, ground a decision in the KB.

Constraint: ≤1024 chars total frontmatter, no process/workflow wording.

### query mode — KB-agnostic

The current `kb-lookup.md` embeds **research-kb-specific** ontology (role tiers
Ventures/Craft/Educator/Builder) and federation pointers. In the skill, query is
**generalized**: the ontology is read from the KB instance itself
(`$KB/taxonomy.md`, `$KB/index.md`) via `H2T_KB_ROOT`, so the mode works against any
`llm-kb-template` instance. The protocol is preserved verbatim in intent:

1. Find the cluster (Grep `wiki/`, keyword from `taxonomy.md`).
2. Read the topic at 3 levels (L1 `index.md` → L2 `evidence[]` frontmatter → L3 full page).
3. Check the council (mandatory): `data/pipeline-state.json` → `council_results.round_N.pass[]`.
4. Apply the trust hierarchy (CONFIRMED+replicated+PASS ★★★ … council FAIL ✗).
5. Gap → fill it (capture ≠ ingest; urgent gap → cost-gated **`kb ingest --strict`**).

**Why `--strict` on the urgent-gap path (codex block #1):** query grounds only on
council-PASS claims (step 3). But the default ingest tier is Tier-1 lightweight, which runs
NO council and emits a `partial` page — its claims can never be council-PASS. So an urgent
gap that query must ground on *requires* the strict council tier. Calling default ingest
here would produce a page query is contractually barred from using as grounding.

**Schema assumption + fail-loud (codex #2):** query hard-reads the `llm-kb-template`
artifact shape — `evidence[]` frontmatter, the `data/pipeline-state.json` council-state
layout, the verdict ladder. This is safe because every KB instance shares the one engine
(see consolidation-direction: single multi-domain engine). query therefore **assumes the
`llm-kb-template` schema and fails loud** if a required artifact is missing (no page,
no `pipeline-state.json`, no council round) — it never silently degrades to an ungrounded
answer. What is instance-specific *and machine-readable* (taxonomy via `taxonomy.md`) is read
from the KB; what is engine-invariant (schema) is assumed. **Federation** (which sibling KB
owns a domain) is NOT read from the KB by the query mode — it is prose guidance that lives in
each instance's per-KB pointer stub (e.g. research-kb's stub names quant-kb / agentic-kb);
the query mode itself stays federation-agnostic.

`research-kb/.claude/rules/kb-lookup.md` is replaced by a thin pointer that **still carries
the load-bearing rule inline** (codex #4): "Ground only on council-PASS claims. Full lookup
protocol: `h2t-ops:kb` query. This KB = research-kb instance — ontology in `taxonomy.md`;
federation to quant-kb / agentic-kb below." Keeping the one-line policy in the stub means
the council-PASS discipline survives even if the plugin skill fails to load; the protocol
detail lives in the skill, the non-negotiable rule is duplicated for safety.

## Migration

- `git rm` the old `kb-ingest/` and `kb-lint/` skill dirs; their triggers fold into the
  unified `description`.
- Move `kb-ingest/SKILL.md` body → `kb/references/ingest.md` (content preserved; only the
  shared resolve-root/guardrails hoisted up to `SKILL.md`).
- Move `kb-lint/SKILL.md` body → `kb/references/lint.md`.
- Author `kb/references/query.md` from `kb-lookup.md`, generalized as above.
- Replace `research-kb/.claude/rules/kb-lookup.md` with the pointer stub — which retains the
  council-PASS rule inline (see query section) — separate repo, separate commit.

**Accepted risk — no compatibility alias (codex #3):** old skill names `h2t-ops:kb-ingest` /
`h2t-ops:kb-lint` are removed, not aliased. The operator chose `git rm` over
deprecate-redirect knowing this can break a call site that hard-codes the old names. The
skills are recent (kb-ingest v0.2.0 / kb-lint v0.1.0, both merged 2026-07-24) with no known
external callers, and their trigger words fold into the unified `description`, so
natural-language invocation continues to resolve. Deliberate, risk accepted.

## Testing (Iron Law — no skill edit without a failing test first)

Editing/creating skills requires a failing test first. Retrieval-style tests with subagents.

**RED — a REAL baseline, not a manufactured one (codex #6).** Do NOT weaken the description
to fake a failure. The genuine pre-change defect the consolidation fixes is that **query does
not exist as a skill at all** and the entry is fragmented across two skills. Baseline on the
*current* plugin state:
- "заземли это решение в базе знаний" / "look it up in the KB" → **no skill surfaces** the
  lookup protocol (it lives only in `research-kb/.claude/rules/kb-lookup.md`, invisible to the
  plugin) → the subagent improvises or asks the operator. This is the real RED.
- "наполни KB" and "проверь целостность KB" resolve today, but to two *separate* skills; the
  compound "поискать и добавить" has no single owner. Document the fragmentation verbatim.

**GREEN — routing AND preserved safety properties (codex #7).** With the unified `kb` skill:
1. *Routing:* each intent (below) routes a subagent to the correct `references/*` file.
2. *Content preservation:* the migrated `ingest.md` / `lint.md` still carry their
   load-bearing gates verbatim — assert by diff that the moved bodies retain the ingest
   cost-gate hard-stop, the `--strict` council step, and `lint.md`'s read-only "do not fix
   silently" clause. For the newly-authored `query.md`, assert the council-PASS-only rule is
   present (not a diff — it is authored from `kb-lookup.md`). Consolidation must not quietly
   drop a safety gate while relocating text.

**KB-agnostic proof (codex #8).** Run query with `H2T_KB_ROOT` pointed at a *second* instance
whose `taxonomy.md` differs from research-kb's (a minimal fixture KB is enough): the mode must
find the cluster from that instance's own taxonomy and still enforce council-PASS. This is the
only test that actually exercises the central KB-agnostic claim.

**Retrieval matrix** — must include, per codex #9/#10:
- The exact legacy names `kb-ingest` / `kb-lint` (verify the folded triggers still fire the unified skill).
- The compound "поискать и добавить в базу знаний" (verify query-then-ingest, not a single mode).
- **2–3 false-trigger cases**, not one: a Notion knowledge base, an external wiki, a
  third-party product's "knowledge base" — none may fire the skill (scoped to
  `llm-kb-template`/research-kb instances).

**REFACTOR:** disambiguate overlapping triggers from whatever the matrix mis-routes.

Success: real RED reproduced → all intents route correctly + content-preservation diff clean
+ KB-agnostic query passes against a second instance + 0/3 false triggers.

## Risks

- **Unified description covering 3 modes without a workflow summary** — the tightest part;
  validated by the retrieval test, not by inspection.
- **Over-broad triggers** ("any knowledge base") causing false activation — mitigated by the
  2–3 false-trigger checks and by scoping wording to the KB instances.

## Codex review adjudication (2026-07-24)

Read-only codex review flagged 9 items; adjudicated and folded into this spec:
- #1 urgent-gap must call `kb ingest --strict` (Tier-1 default has no council) — **fixed** (query §5).
- #2 KB-agnostic schema assumption + fail-loud contract — **fixed** (query mode).
- #4 pointer stub retains council-PASS rule inline — **fixed** (query + migration).
- #5/#9 compound "search and add" routes query→ingest — **fixed** (routing table, matrix).
- #6 RED must be a real baseline (query absent, entry fragmented) — **fixed** (testing).
- #7 GREEN adds content-preservation of safety gates — **fixed** (testing).
- #8 KB-agnostic tested against a second `H2T_KB_ROOT` — **fixed** (testing).
- #10 2–3 false-trigger cases — **fixed** (matrix).
- #3 no compat alias for old skill names — **accepted risk** (operator decision; migration).

## Open follow-ups (out of scope here)

- Live dogfood-ingest run to validate the engine end-to-end on a real topic under the KB ontology (Plan C).
- Federated `kb-lookup` rules in quant-kb / agentic-kb could later point at the same `kb` query mode.
