---
title: "kb-ingest Multi-Domain Awareness — Design"
status: "draft"
owner: "lichtpfad"
date: "2026-08-09"
milestone: ""
---
# kb-ingest Multi-Domain Awareness — Design

**Date:** 2026-08-09
**Status:** Approved (brainstorming)
**Repos touched:** `h2t-skills` (the `h2t-ops:kb` skill) + `llm-kb-template` (engine: `parse_claims.py`)
**Depends on:** llm-kb-template Plan 1 (PR #12, config & structure) + Plan 2 (PR #13, ingest-grading
multi-awareness), both merged.

## Problem

The engine (`llm-kb-template`) is now multi-domain-capable: a single central KB holds many domains
via `base ⊕ override(domain)`, and every grading stage resolves the run's domain from the
`<domain>--<slug>` page slug (Plan 2). Flat single-domain KBs are unchanged.

The **orchestrating skill** `h2t-ops:kb` (`plugins/h2t-ops/skills/kb/references/ingest.md`) was
written before Plan 1/2 and is **not** multi-domain aware. Driving a multi-domain KB through it
today breaks or silently mis-grades:

- **Hard blocker — honesty (`ingest.md:40`)** calls
  `pipeline.run honesty --harvest … --verdicts … --out … --repo "$KB"` with **no `--slug`**. In a
  multi-domain KB the honesty stage resolves its domain from `--slug`; absent it,
  `assert_single_domain([])` raises → the stage returns 1. The first grading step fails.
- **Slug convention (`ingest.md:22-23`, 43, 54, 64, 120, 171-173)** uses a bare `<slug>`
  placeholder. In a multi-domain KB every page slug must be `<domain>--<slug>` and every page must
  carry a `domain:` frontmatter field (Plan 1 lint enforces it). The skill never says this, so an
  agent may pick a prefix-less slug → wrong-domain grading or a crash.
- **Strict-tier engine gap — `parse_claims.py:99`** calls
  `require_all_judge_prompts(load_config())` on the **flat** config. Under `--strict` in a
  multi-domain KB a domain that overrides `judges` / `judge_prompts` would be validated against the
  base set, not its own. `parse_claims.py` already receives the slug (`:96`), so it can resolve the
  domain. (`synthesize_council.py` was already made domain-aware in Plan 2.)

Flat single-domain KBs (research-kb, quant) are unaffected by all three: `assert_single_domain`
returns `None` in flat mode, and `effective_config(flat, None)` returns the config verbatim.

## Non-goals

- No change to the deterministic engine stages already fixed in Plan 2 (intake/prepare/finalize/
  ingest-light/apply-verdicts derive the domain from the stamped `target_slug` automatically once
  the slug is domain-prefixed).
- No tool/knowledge split, no scaffolding of an actual central KB — separate tasks.
- No change to flat-KB behavior or the cost-gate / dry-run protocol.

## Design

### A. Skill edits (`h2t-skills`, `plugins/h2t-ops/skills/kb/references/ingest.md`)

1. **honesty gains `--slug <slug>`** (`ingest.md:40`):
   `pipeline.run honesty --harvest harvest.json --verdicts honesty.json --out real.json --repo "$KB" --slug <slug>`

2. **Slug-convention section** (rewrite `ingest.md:22-23`): before ingest, resolve the target
   **domain**. If `$KB/kb.config.json` is multi-domain (`domains[]` present): pick the domain, and
   the page slug is `<domain>--<topic-slug>`; the stub `$KB/wiki/<domain>--<topic-slug>.md` must
   exist AND carry `domain: <domain>` frontmatter (scaffold via the engine's `scaffold_topics.py`,
   which stamps it). If flat: `<slug>` stays plain, no `domain:` field. Every `<slug>` placeholder
   downstream is this same (possibly domain-prefixed) value.

3. **New "Multi-domain KB" subsection** (short): one central KB holds many domains
   (`base ⊕ override`); **one ingest run targets exactly one domain** (derived from the slug); a
   mixed-domain batch fails loud. Point to `kb.config.json` `domains[]` as the domain list.

4. **Strict-tier note**: `parse_claims.py <slug>` and `synthesize_council.py <slug>` already take
   the (domain-prefixed) slug and now resolve per-domain judges/threshold/prompts — no extra flag,
   but the slug MUST be domain-prefixed for the council to use the domain's judges.

### B. Engine fix (`llm-kb-template`, `scripts/parse_claims.py`)

Resolve the domain from the slug and validate judge-prompts against the domain's effective config:

```python
# main(), replacing line 99 (slug is already bound at line 96)
raw = _kbconfig.load_config()
cfg = _kbconfig.effective_config(raw, _kbconfig.domain_from_slug(slug, raw))
_kbconfig.require_all_judge_prompts(cfg)
```

Flat KB: `domain_from_slug` → `None`, `effective_config(flat, None)` → flat verbatim → identical
behavior (bit-for-bit).

## Verification

- **Engine (`parse_claims`)**: a TDD unit test — a multi-domain cfg whose `research` domain
  overrides `judges`/`judge_prompts`; assert `parse_claims` validates against the domain's set
  (and a flat cfg still passes unchanged). Full engine suite green.
- **Skill**: markdown is not unit-tested. Verification = a manual dry-run against a scaffolded
  2-domain KB: confirm honesty runs (rc 0) with `--slug alpha--x`, and the mixed-domain guard is
  never hit because one run = one domain. A skill self-review checks every `<slug>` occurrence is
  covered by the convention section.

## Delivery

- Engine fix: PR to `llm-kb-template` (small, own commit + test).
- Skill edits: PR to `h2t-skills`; **patch-bump `plugins/h2t-ops` (1.5.8 → 1.5.9)** and reinstall
  (`uv tool install --editable C:/dev/h2t-skills`) so the live skill reloads — a markdown edit
  without a version bump is not picked up by the running plugin.

## Open items (deferred, not blockers)

- Scaffolding an actual central multi-domain KB instance (domains + taxonomies) — separate task.
- Tool/knowledge split (engine as installable CLI) — separate task.
- Whether `parse_claims` should also warn when a domain has no `judge_prompts` override and falls
  back to base — acceptable default; note only.
