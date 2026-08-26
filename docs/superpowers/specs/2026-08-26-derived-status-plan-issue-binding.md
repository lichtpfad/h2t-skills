---
title: "Derived status: binding plans to issues"
status: "draft"
owner: "lichtpfad"
date: "2026-08-26"
milestone: ""
---

# Derived status: binding plans to issues

Companion to [2026-08-24-repo-governance-architecture](2026-08-24-repo-governance-architecture.md),
which defined the three loops. This one fixes the field all three of them read.

## The defect

`status` in a plan or spec is written once, by `new_doc.py:100`, and never again by
anything that knows whether the work happened. Every consumer treats it as a measurement:
`retire.py:27` filters on `_CLOSED`, `audit` reports on it, the archive sweep selects by it.

The field is **unfalsifiable**. No check can call a value wrong, because there is nothing to
compare it against. There is no such thing as a stale value here — there is a value with no
source.

Measured 2026-08-26 over the 42 legacy documents reviewed by hand:

| | |
|---|---|
| carry `status: draft` | 41 of 42 |
| shipped in full | 29 |
| shipped in part | 10 |
| the field moved | never |

The in-body prose fails in both directions too, so it is not a fallback:
`agent-profile-design.md:11` says "implementation not started" on fully shipped work;
`semantic-renderer-v0.md:12` says "SUPERSEDED / DO NOT EXECUTE" while frontmatter says draft.

The `plan-closer` hook (#410) narrows the window — the machine writes the field at merge
time instead of a human at creation time — but the field stays a stored copy of state, and
copies diverge: a PR merged without the plan in its diff, an issue closed by hand, work
continued on another branch.

## The contract

Stop storing state as truth. Store an **address**; derive the state.

```yaml
issue: 91            # address — never changes
status: "partial"    # cache of the derivation — owned by the machine, not by a person
```

`status` stays in the file, because a document must read correctly on GitHub and offline.
What changes is its standing: from *assertion* to *cache*, and with it comes the obligation
that did not exist before — **the cache must equal the derivation, and a mismatch is a
finding.**

One field is what makes the other one checkable.

## Derivation

Entirely from state GitHub already maintains. No new store.

| issue #N | PR closing it | `status` |
|---|---|---|
| open | none merged | `draft` |
| open | one merged | `partial` |
| closed as completed | — | `done` |
| closed as not planned | — | `rejected` |
| does not exist | — | finding `orphaned`, not a status |

`partial` is a new value. The manual review of the 42 produced exactly this bucket — ten
documents whose code landed while the work continued — and today's schema cannot express it,
so those ten are indistinguishable from `draft`. The table yields it as a join, not as
judgement.

`partial` must **not** enter `_CLOSED` in `retire.py`: partially shipped work is live work.

## Guarantee

Nothing can be guaranteed inside a document — a document does not resist editing. The
invariant holds at the **entry paths** through which a file reaches the repository. There
are three, and one is covered.

| path | today | needed |
|---|---|---|
| `docs-lint new plan <slug>` | nothing; `status: "draft"` is hardcoded | `--issue N` required, or `--new-issue "<title>"` creates it and stamps the number |
| Write/Edit by an agent | `structure_guard.check_frontmatter_presence` checks that frontmatter exists | the same function checks that `issue:` is in it |
| hand edit in an IDE, merge from elsewhere | **nothing** — `.github/workflows/evals.yml` runs ruff and pytest and never looks at `docs/` | `docs-lint audit` in CI |

The third row is how 111 overdue documents accumulated: path 1 held by convention only,
path 2 arrived recently, path 3 has never been closed.

**Escape hatch, mandatory.** A gate with no named exception gets routed around. `issue: none`
with a `reason:` on the next line — deny-by-default plus an explicit exception, the same
shape as `allowed_doc_dirs` in `structure_guard`. This very spec is that case: an
architectural record that has no issue and should not have one.

**Reverse edge.** The issue body carries `Plan: docs/superpowers/plans/...`. Then
`gh issue view --json body` walks the link the other way with no extra storage, and `audit`
can find an issue labelled `phase:design` with no document.

## Where it lands in the three loops

No new machinery. Each piece attaches to a loop that already exists.

- **Loop 1, prohibition** — `structure_guard` refuses a plan without `issue:`.
- **Loop 2, recording** — `plan_closer` writes the *derived* value at merge instead of the
  literal `"done"`. Same hook, different function.
- **Loop 3, cleanup** — the weekly cron (decision A, 2026-08-26) reconciles: walk every
  `issue: N`, derive, compare against the cache, open a PR with the differences.

Reconciliation also repairs a hole in decision A itself. The cron was scoped to retirement,
and `STALE_DAYS = 60` leaves its domain empty until roughly 2026-10-25 — two months in which
an empty report and a broken report are indistinguishable, which is the missing-positive-control
failure `.claude/rules/verification.md` describes. Reconciliation gives it work from the first
run and makes silence meaningful.

## Steps

Each is independently verifiable; the order is a dependency order, not a preference.

1. **Field** (#421). `issue` into `FRONTMATTER_RULES` for `superpowers/plans` and `superpowers/specs`;
   `issue: none` + `reason` accepted. Verify: `fix-safe --only=frontmatter` backfills empty
   values, `audit` reports the gap as a dimension.
2. **Generator** (#422). `docs-lint new` requires `--issue N` / `--new-issue "<title>"` / `--no-issue
   "<reason>"`. Verify: no argument → non-zero exit, no file created.
3. **Gates** (#423). `structure_guard` rejects a plan without the field; `docs-lint audit` runs in
   `evals.yml`. Verify: a planted file blocks at the hook and fails in CI.
4. **Reconciliation** (#424). `docs-lint reconcile [--apply]` computes the table above via `gh` and
   reports drift; the weekly cron runs it and opens a PR. Verify: a doc whose cache is
   deliberately wrong shows up as drift; a correct one does not.

## Legacy is not migrated

The 111 overdue documents either have no issue or have one closed long ago. Reconstructing
the address after the fact is the same mistake a third time — a record written on the word of
someone who was not a witness. The contract applies to documents created after the gate
lands; the old ones go to the archive, which asserts nothing about state.

Of the 72 live documents, **52 mention `#N` somewhere in prose** — the link largely exists
already, it is simply not machine-readable. Extracting it is a one-off migration needing
human review, because `#123` in running text can be anything.
