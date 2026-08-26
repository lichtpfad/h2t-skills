---
title: "h2t-ops Connector Development Runbook — Design"
status: "draft"
owner: "Stanislav Glazov"
date: "2026-05-19"
milestone: ""
---
# h2t-ops Connector Development Runbook — Design

**Status:** Draft for review
**Date:** 2026-05-19
**Issue:** #138
**Model:** procedural-index (references authority, does not duplicate it)

**Related authority documents:**

- Roadmap section `skills: [M3] Add connector development skill runbook — #138` (`docs/h2t-ops-roadmap.md`)
- API coverage audit (`docs/reports/2026-05-19-h2t-ops-api-coverage-audit.md`)
- TZ-0 connector architecture spec (`docs/superpowers/specs/2026-05-18-h2t-connector-architecture-design.md`)
- POS operational boundary (`plugins/h2t-ops/references/pos-operational-boundary.md`)
- Testing plan (`docs/h2t-ops-testing-plan.md`)

---

## Goal

A procedural recipe an agent follows to add or migrate a connector to the h2t-ops
standard **without re-deriving the architecture**. The runbook turns the TZ-0 spec,
the API coverage audit, and the POS boundary into an executable, checklist-driven
sequence anchored on the Notion and Gmail connectors as living reference
implementations.

## Authority order

The runbook is a **procedural index**, not a source of truth. When the runbook and
an authority document disagree, the authority wins. Order:

1. **TZ-0 connector architecture spec** — architecture, `ConnectorSpec`, import
   discipline, error/output/SKILL contracts.
2. **API coverage audit (2026-05-19)** — parity gaps, provider-API gaps, the
   9-item checklist text.
3. **POS operational boundary reference** — what a connector must not mutate; the
   `proposed_capture` contract.
4. **Testing plan** — G-gate acceptance + evidence format.
5. **Notion / Gmail connector code** — the canonical pattern to copy.

The runbook references these by stable path; it does not restate their content.

## Scope / non-goals

**In scope:** the step-by-step "add a connector" procedure; the per-connector
review checklist (the 9-item audit gate, referenced verbatim by pointer);
error/output/POS gate pointers; the DoD/PR gate tied to the testing plan.

**Non-goals (excluded to prevent doc-mixing):**

- Architecture rationale → TZ-0 spec.
- Audit findings themselves → audit report.
- POS ADR content → POS repo / boundary reference.
- Connector-specific feature scope → per-issue (#132 Calendar parity, #144 Notion
  patch, #145 Calendar provider features).
- New skill scaffolding — the runbook is a plugin-level reference, not a new skill.
- Connector code changes — this work and the runbook are docs-only.

## Location of deliverable

Runbook: `plugins/h2t-ops/references/h2t-connector-runbook.md` (plugin-level
references, beside `pos-operational-boundary.md`). This satisfies the #138
Definition of Done ("`references/h2t-connector-runbook.md` exists"). The roadmap
#138 wording "under that skill's references/" is reconciled to plugin-level
references in the implementation plan; **no skill is scaffolded**.

## Runbook structure (8 sections)

1. **When to use / scope** — connector vs coordinator/POS work; the boundary
   stated first.
2. **Reference implementations** — Notion (read-centric) and Gmail
   (read + write + OAuth) as the two canons; a file-path map.
3. **Step-by-step procedure** — package layout → `client.py` → `commands.py` →
   `__init__` `ConnectorSpec` → cli wiring/shim → tests → live smoke. Each step:
   what to do, which reference file holds the pattern, the typical pitfall.
4. **API coverage checklist** — the 9-item gate, referenced verbatim from the
   roadmap (not re-authored).
5. **Error / exit-code map** — pointer to `errors.py` + the minimal mapping
   skeleton.
6. **Output contract** — pointer to `output.py` / `envelope.py` + the `--json` /
   `--format` rule.
7. **POS boundary & distribution-without-POS gate** — pointer to
   `pos-operational-boundary.md`; "no `~/.dor` writes; emit `proposed_capture`"
   as a checklist line.
8. **DoD / PR gate** — testing-plan G-gates + evidence format.

### Reference anchoring policy

Default to **stable file-path** references. Use `file:line` anchors **only** for
load-bearing patterns an agent will copy and that are costly to get wrong:

- `ConnectorSpec` definition (`__init__.py`)
- lazy client string (the `"module:attr"` in `ConnectorSpec`)
- cli `_MIGRATED` set / deprecation shim
- error map (`_map_http_error` / `errors.py` table)
- `emit()` / envelope call site
- POS boundary rule

Routine code gets **path-only** references — line anchors there drift and make the
runbook brittle.

## Implementation plan outline (6 tasks, docs-only)

1. Collect & verify the stable file paths + the 6 load-bearing `file:line`
   anchors (Notion / Gmail / core).
2. Write the runbook skeleton (8 section headings + the anchoring-policy note).
3. Fill the step-by-step procedure with path references + the 6 anchors +
   pitfalls.
4. Fill checklists/templates: 9-item gate (by reference), error/output pointers,
   the POS gate line, the DoD/PR gate.
5. Self-review against the 9-item audit checklist; dead-reference check (every
   cited path resolves; each of the 6 anchors points at the right symbol).
6. Reconcile roadmap/#138 wording and add a roadmap → runbook link.

Each task: edit the runbook file, verify cited paths/anchors resolve, touch zero
connector code.

## Review gates

- **Spec self-review (inline):** placeholders, internal consistency, scope,
  ambiguity — fixed before this doc is presented.
- **User review of this design doc** — stop before writing the implementation
  plan.
- **Implementation plan** produced by the `writing-plans` skill at
  `docs/superpowers/plans/2026-05-19-h2t-ops-connector-runbook.md`.
- The runbook's own acceptance is **documentation review** (no live gate); the
  G-gates it *describes* apply to connectors built with it.
