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

| issue #N | merged PR referencing it | `status` |
|---|---|---|
| open | none | `draft` |
| open | at least one | `partial` |
| closed as completed | — | `done` |
| closed as not planned | — | `rejected` |
| does not exist | — | finding `orphaned`, not a status |

The predicate for `partial` is **a merged PR that references the issue**, read from
`CROSS_REFERENCED_EVENT` — *not* `closedByPullRequestsReferences`. A PR that closes an issue
is by construction a PR of a *closed* issue, so the closing edge can never witness `partial`.
An earlier draft of this spec said "PR closing it" and was wrong for that reason.

`done` and `rejected` need no PR at all: `stateReason` on the issue carries them.

**Measured 2026-08-26, live API:**

| probe | result |
|---|---|
| closed issues, closing PR recoverable | 21 of 24 (the 25th is `NOT_PLANNED`, which needs none) |
| #386 (open) | `closedBy` empty, `xref` = #389, #390, #404, all merged → `partial` |
| #414–#420 (open) | no cross-reference → `draft` |
| #421–#424 (open) | `xref` = #425, **not** merged → correctly excluded |

The last row is the negative control: the mechanism distinguishes a merged reference from an
open one, so an empty result means "nothing merged" rather than "probe broken".

Squash merges do not break this. The closing keyword lives in the PR body, not only in the
commit message, so `gh pr merge --squash` keeps the edge — the 21-of-24 above is under squash
throughout.

**Known noise.** A cross-reference is any mention: a PR saying "see #386" in passing marks the
document `partial`. This is tolerable because `partial` is the one derived value that triggers
nothing — it is not in `_CLOSED`, so it neither archives nor retires. It costs a false
"in progress", never a false deletion.

`partial` is a new value. The manual review of the 42 produced exactly this bucket — ten
documents whose code landed while the work continued — and today's schema cannot express it,
so those ten are indistinguishable from `draft`. The table yields it as a join, not as
judgement.

`partial` must **not** enter `_CLOSED` in `retire.py`: partially shipped work is live work.

## Guarantee

Nothing can be guaranteed inside a document — a document does not resist editing. The
invariant holds at the **entry paths** through which a file reaches the repository. There are
five, and one and a half are covered.

| path | today | needed |
|---|---|---|
| `docs-lint new plan <slug>` | nothing; `status: "draft"` is hardcoded (`new_doc.py:100`) | `--issue N` required, or `--new-issue "<title>"` creates it and stamps the number |
| Write by an agent | `structure_guard.check_frontmatter_presence` runs (`structure_guard.py:282`) | the same function checks that `issue:` is in it |
| Edit / MultiEdit by an agent | path gate only — the frontmatter check is behind `if tool_name == "Write"` | re-read the file and check the field after the edit |
| **Bash heredoc, `sed`, any script** | **nothing** — `_WRITE_TOOLS = {"Write", "Edit", "MultiEdit"}` (`structure_guard.py:24`) | cannot be hooked; CI is the only cover |
| hand edit in an IDE, merge from elsewhere | **nothing** — `.github/workflows/evals.yml` runs ruff and pytest and never looks at `docs/` | `docs-lint audit` in CI |

The first draft of this spec listed three paths and missed two. It was itself written with a
Bash heredoc, straight past row four — which is the shortest possible demonstration that the
hook cannot be the guarantee. **CI is load-bearing, not a backstop.**

`post_git_commit_docs_lint.py` looks like a sixth cover and is not one: it runs after a commit
touching `docs/*.md` (`post_git_commit_docs_lint.py:46`) but exits 0 even on findings
(`:206`, `:221`). It reports; it does not gate.

**Escape hatch, mandatory.** A gate with no named exception gets routed around. `issue: none`
with a `reason:` on the next line — deny-by-default plus an explicit exception, the same shape
as `allowed_doc_dirs` in `structure_guard`. This very spec is that case: an architectural
record that has no issue and should not have one.

**And the hatch needs its own pressure**, or it becomes the default. Three rules, all in
`audit`:

- an empty `issue:` is a finding, not a pass — key-presence validation alone
  (`lint.py:408`) would let `issue: ""` through as compliant;
- `issue: none` with an empty or missing `reason` is a finding;
- every `issue: none` is listed by `audit` under its own dimension, with its reason, so the
  set of exceptions is readable in one place rather than scattered across files.

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

Each is independently verifiable; the order is a dependency order, not a preference. Two
ordering hazards are named below and are part of the contract, not advice.

1. **Field** (#421). `issue` into `FRONTMATTER_RULES` for `superpowers/plans` and
   `superpowers/specs`; `issue: none` + `reason` accepted; empty value is a finding. Verify:
   `fix-safe --only=frontmatter` backfills, `audit` reports the gap as a dimension.
2. **Generator** (#422). `docs-lint new` requires `--issue N` / `--new-issue "<title>"` /
   `--no-issue "<reason>"`. Verify: no argument → non-zero exit, no file created.
3. **Gates** (#423). `structure_guard` rejects a plan without the field on Write *and* on
   Edit; `docs-lint audit` runs in `evals.yml`, failing on the `unlinked` dimension only.
   Verify: a planted file blocks at the hook and fails in CI; a compliant file passes both.
4. **Reconciliation** (#424). `docs-lint reconcile [--apply]` computes the table above via
   `gh` and reports drift; `plan_closer` switches to the derived value; the weekly cron runs
   it and opens a PR. Verify: a doc whose cache is deliberately wrong shows up as drift; a
   correct one does not.

**Hazard 1 — steps 1 and 2 must land in the same PR.** `new_doc.py:106` builds its field list
from `FRONTMATTER_RULES` and emits `values.get(f, "")` (`:109`). Adding the field alone makes
`docs-lint new` write `issue: ""` into every new document, and `fix-safe` do the same to
existing ones (`lint.py:526`, `:538`). Step 1's "empty is a finding" rule keeps that loud
rather than silent, but the generator must stop producing it in the same change.

**Hazard 2 — `plan_closer` must learn `partial` before anything writes it.** The hook treats
any status outside `_CLOSED` as closable (`plan_closer.py:95`, `:99`) and rewrites it to
`status: "done"` (`:102`). A document reconciled to `partial` would be silently promoted to
`done` by the next merge that touches it. Both halves live in step 4 and must ship together.

## Legacy is not migrated

The 111 overdue documents either have no issue or have one closed long ago. Reconstructing
the address after the fact is the same mistake a third time — a record written on the word of
someone who was not a witness. The contract applies to documents created after the gate
lands; the old ones go to the archive, which asserts nothing about state.

Measured 2026-08-26 across 73 live plan/spec files: **1 carries an `issue:` field** (this
spec's own future case is not among them), and **54 mention `#N` somewhere in prose**. The
link largely exists already; it is simply not machine-readable. Extracting it is a one-off
migration needing human review, because `#123` in running text can be anything.
