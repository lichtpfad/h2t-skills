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
5. Gap → fill it (capture ≠ ingest; urgent gap → cost-gated `kb ingest`).

`research-kb/.claude/rules/kb-lookup.md` is replaced by a thin pointer: "lookup protocol
now lives in `h2t-ops:kb` query; this KB is the research-kb instance — its ontology is in
`taxonomy.md`, federation to quant-kb / agentic-kb noted here." (Federation is instance
knowledge, stays in the KB; the mode stays generic.)

## Migration

- `git rm` the old `kb-ingest/` and `kb-lint/` skill dirs; their triggers fold into the
  unified `description`.
- Move `kb-ingest/SKILL.md` body → `kb/references/ingest.md` (content preserved; only the
  shared resolve-root/guardrails hoisted up to `SKILL.md`).
- Move `kb-lint/SKILL.md` body → `kb/references/lint.md`.
- Author `kb/references/query.md` from `kb-lookup.md`, generalized as above.
- Replace `research-kb/.claude/rules/kb-lookup.md` with the pointer stub (separate repo, separate commit).

## Testing (Iron Law — no skill edit without a failing test first)

Editing/creating skills requires a failing test first. Retrieval-style tests with subagents:

**RED (baseline):** with the current three-way state (or a deliberately weak unified
description), give a subagent each intent and observe mis-routing:
- "наполни KB по теме X" / "add findings to the knowledge base"
- "заземли это решение в базе знаний" / "look it up in the KB"
- "проверь целостность KB" / "kb health"

Document verbatim which mode it picks and where it improvises.

**GREEN:** with the unified `kb` skill, each intent routes to the correct `references/*` file.

**REFACTOR:** disambiguate overlapping triggers; add a **false-trigger** check — an
unrelated "knowledge base" mention (Notion, an external wiki) must NOT fire the skill (it is
scoped to `llm-kb-template`/research-kb instances).

Success: 3/3 intents route correctly + no false trigger on out-of-scope KBs.

## Risks

- **Unified description covering 3 modes without a workflow summary** — the tightest part;
  validated by the retrieval test, not by inspection.
- **Over-broad triggers** ("any knowledge base") causing false activation — mitigated by the
  false-trigger REFACTOR check and by scoping wording to the KB instances.

## Open follow-ups (out of scope here)

- Live dogfood-ingest run to validate the engine end-to-end on a real topic under the KB ontology (Plan C).
- Federated `kb-lookup` rules in quant-kb / agentic-kb could later point at the same `kb` query mode.
