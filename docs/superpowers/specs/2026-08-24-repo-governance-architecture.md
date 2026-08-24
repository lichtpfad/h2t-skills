---
title: "Repo governance architecture"
status: "draft"
owner: "lichtpfad"
date: "2026-08-24"
milestone: ""
---

# Repo governance architecture

How a repository stays in order without the owner holding it there. Written
2026-08-24 after a day of measurements on h2t-skills; every number below was
taken from this repo, and the ones that failed are kept because they are the
reason the design has the shape it has.

## The failure this replaces

`docs-lint` measures form: naming, frontmatter fields, reachability from the
index, directory structure. Across 261 documents it found 22 naming problems —
form was never the thing going wrong.

What was going wrong: **141 of 144 plans, specs and ADRs stood open, 111 of them
past 60 days.** Those documents are flawless by every check the tool has. A plan
written in May and abandoned in May stays a perfectly valid document forever.

The number existed, was displayed nowhere, and no command could reduce it. Six
months passed.

## The law the day produced

> A check without a source of fact runs empty and looks healthy.

`docs-cleanup` (deleted in #411) is the proof. Written 2026-04-13, it contained:

```python
def find_implemented_specs(rp):
    if fm and fm.get("status") in ("implemented", "done", "completed"):
```

Correct code. It returned an empty list every time for four months, because
nothing in the system ever set `status`. The automation was present; the
observation was not.

Every other failure that day is the same shape. Retrospective inference of "is
this plan done" failed on both available signals:

| signal | measurement |
|---|---|
| plan slug in a merged PR body | 7 of 60 PRs |
| commits touching the file | modal value 2, and the second commit was one bulk `--fix-frontmatter` sweep for dozens of files |

Neither separates *done and never updated* from *abandoned*. The information was
not hard to compute — it was never written down while it was still free.

## Three levels, by kind of witness

Only the bottom one needs a person, and only until its witness accumulates.

### 1. Prohibition — decides without a witness, by deciding in advance

Hooks. `structure_guard` blocks a write that lands in an unlisted root
directory, a new first-level section under `docs/`, a loose file in the `docs/`
root, or a plan/spec/ADR with no frontmatter.

The white list is the load-bearing idea, and it enumerates almost nothing:

* the repo root has had `allowed_root_dirs` from the start and holds 14
  deliberate directories;
* `docs/` had no such rule and grew twelve sections nobody planned —
  `wireframes`, `library`, `protocols`, `visual-regression`,
  `agent-instructions`, `architecture`, `research`, and a `docs/plans/` beside
  `docs/superpowers/plans/`;
* `forbidden_patterns` cannot close that. A blacklist has to name what the next
  write invents, and the next write invents something else.

A section already holding a file is grandfathered by holding it, so no legacy
directory is listed anywhere. `allowed_doc_dirs` names four canonical sections
solely so the rule works in a repo scaffolded five minutes ago.

**An empty directory grandfathers nothing.** `mkdir docs/kb` took the check from
exit 2 to exit 0 until fixed: an empty directory is produced by the very write it
would authorise, and `mkdir -p` before writing is a reflex, not a decision. An
witness is only a witness if the action it sanctions cannot fabricate it.

Status: working. `structure_guard`, `test_no_ghost_skills`.

### 2. Recording — writes the fact while it is still free

`plan-closer` (PostToolUse, first of its kind here). On `gh pr merge <N>`:
`gh pr view` lists the PR's own files, and a plan among them is a plan that
shipped. Nothing is inferred.

Every uncertain case is a no-op, because it runs unattended: an unmerged PR, a
file the PR deleted, a document with no frontmatter, one already closed, and
`gh pr merge` with no explicit number — resolving that once the branch is gone
would stamp the wrong plan. Always exits 0: bookkeeping must never look like a
failed merge.

Status: working (#410).

Candidates to add later: stamping the PR number when a plan is created, and the
closing of a linked issue.

### 3. Cleanup — reads the records and acts

`docs-lint retire` today lists candidates and moves them on `--apply`. It is
manual because until #410 there was nothing to read.

**The turn: once the stamp exists, its absence becomes evidence.** Today "no
`pr:` in the frontmatter" means nothing — no document ever had the field. From
the hook onward, *open, older than N days, no `pr:`* means exactly one thing:
no PR ever carried it, nothing shipped under it. That is the missing witness for
"abandoned", and it makes level 3 decidable.

Consequence worth stating plainly: **the 111 legacy documents will never enter
the autonomous loop.** They are from the era before observation. They are a
one-time migration, not a steady state.

Status: manual. Becomes decidable roughly 60 days after #410 lands.

## Cleanup needs no agent

Once the witness exists, the whole level is a predicate:

```
retire      open + no pr: + older than N  →  git mv
fix-index   link graph                     →  regenerate README
fix-safe    FRONTMATTER_RULES              →  add missing fields
```

No judgement anywhere. An agent here adds nondeterminism and token cost without
adding correctness. Intelligence was needed exactly where observation was
missing — and there it failed (7 slugs of 140). A 200-line hook removed the need
for judgement entirely.

**The better the witness, the less agent is required.** That is the inversion of
the original goal, and it is the finding, not a compromise.

## Open decision: what triggers level 3

Both options measured on this repo. Repo is private, so Actions minutes are
metered; the last 30 CI runs cost 2613s (~44 min), one run ~87s.

### A — cron in GitHub Actions, opens a PR

*Cost.* Checkout, python, script, `gh pr create` when there are changes —
estimated ~40s. Weekly is ~3 min/month, daily ~20 min/month, against 44 min
already spent. Zero tokens.

*Risks.* Runs unsupervised over the repository: a bug in the predicate moves 111
files — mitigated by a PR being the only outlet, never a push to `main`. Creates
its own debt: a hygiene mechanism opening a PR nobody reads is another queue —
mitigated by opening one only when something changed. Does not travel: another
repo needs the plugin fetched by the workflow.

### B — a step at the end of a session

*Cost.* No infrastructure, milliseconds inside a session already open.

*Risks.* Fires 7 times a month here, and only when the skill is invoked — a
return to model discipline, which is what the whole design avoids. Curable by
moving it to a `Stop` hook, but that is a different option. Mutates the working
tree at a moment when the owner is often absent: `.claude/rules/gates.md`
records the night handoff asked for a session name while the user slept and the
summary was lost — a mass `git mv` at that moment is the same situation with a
write. And the end of a session is usually a dirty tree; cleanup would add to it.

### Recommendation

Split by whether the step changes files, not by trigger.

```
count and show   →  session-start briefing. Done, free, mutates nothing.
change files     →  cron → PR. ~3 min/month weekly, review is the only outlet.
```

End of session is the wrong place for mutation precisely because nobody is
there. The place that is looked at daily — the briefing — is already taken by
the number.

Weekly, not daily: commits land in bursts (2, 10, 39, 12 per week over the last
four), and the debt is measured in tens of days, not hours.

## Why not a governance skill

Everything such a skill would do is already distributed across the three levels.
It would add a fourth way to invoke the same code, and `docs-cleanup` is the
record of how that ends: demoted to "CLI" without becoming one, then rebuilt
from scratch four months later by someone who did not know it existed.

`tests/dev/test_no_ghost_skills.py` guards that specific failure: a directory
under `skills/` has a `SKILL.md` or is one of four named exceptions, and every
exception must be referenced from outside its own directory. That reference
count is what separates live code filed under `skills/` from a ghost — it was 0
for `docs-cleanup` and at least 1 for all four survivors.

## State on 2026-08-24

| piece | state |
|---|---|
| debt line in the briefing | shipped, #408 |
| deny-by-default under `docs/` | shipped, #408; empty-dir hole closed same PR |
| `docs-lint retire` | shipped, #408; evidence column corrected #409 |
| close plans on merge | PR #410, CI green |
| remove `docs-cleanup` + ghost guard | PR #411, CI green |
| weekly cleanup workflow | not built — the open decision above |
| retire the 111 legacy documents | not run — the owner's call about their own history |
