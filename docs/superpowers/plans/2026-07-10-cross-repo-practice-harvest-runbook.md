# Autonomous run — Cross-repo practice harvest

> **Durable spine (autonomous run, 2026-07-10).** Survives context compaction / blocker.
> A fresh session resumes from HERE.
> **Resume:** `autonomous-run resume docs/superpowers/plans/2026-07-10-cross-repo-practice-harvest-runbook.md`

## Durable-spine header

Authorized: autonomous delivery through handoff. On a **hard-stop or unresolvable blocker**
→ run `h2t-core:handoff` — NOT on a default-shaped decision (those are auto-resolved, see
Decision-protocol). Verify the branch before every commit.

## Where things are

- Branch: `docs/practice-harvest`
- Spec: `docs/superpowers/specs/2026-07-10-cross-repo-practice-harvest.md`
- Issue: none
- Tests: `C:/dev/h2t-skills/.venv/Scripts/pytest tests/practice_harvest/`
- e2e applicability: applies

## Pipeline steps

- [x] **write-spec** — skill: `superpowers:brainstorming (spec tail)` · input: `docs/superpowers/specs/2026-07-10-cross-repo-practice-harvest.md` · done: spec file exists + frontmatter · failure: escalate · re-entry: idempotent: overwrite spec
- [ ] **review-spec** — skill: `codex review (embedded)` · input: `codex reads spec + plan together (combined pass with plan-gate)` · done: no [P1] · failure: fix P1 then re-run (<=N) · re-entry: idempotent: re-review
- [x] **write-plan** — skill: `superpowers:writing-plans` · input: `docs/superpowers/plans/2026-07-10-cross-repo-practice-harvest.md (8 tasks, advisor-hardened)` · done: plan file exists · failure: escalate · re-entry: idempotent: overwrite plan
- [ ] **plan-gate** — skill: `codex review (embedded)` · input: `codex-rescue reads spec + full plan, emits [P1]/[P2]` · done: no [P1] · failure: fix P1 then re-run (<=N) · re-entry: idempotent: re-review
- [ ] **subagent-driven-dev** — skill: `superpowers:subagent-driven-development` · input: `Tasks 1-8 from plan; per-task implementer + spec + quality review` · done: all tasks green · failure: per-task gate; escalate on repeated fail · re-entry: continue from first unchecked task
- [ ] **gates** — skill: `codex + pre-merge-check` · input: `full pytest tests/practice_harvest/ + codex final read` · done: no [P1]; suite green · failure: fix then re-run (<=N) · re-entry: idempotent: re-run gate
- [ ] **e2e** — skill: `real entrypoint run` · input: `build_index on real corpus -> synthesize registry -> validate_registry with coverage gate PASS` · done: DONE / N/A / BLOCKED-DEFERRED · failure: BLOCKED->handoff; behavioral fail->fix · re-entry: idempotent: re-run
- [ ] **PR** — skill: `superpowers:finishing-a-development-branch` · input: `branch docs/practice-harvest -> PR to main` · done: PR opened · failure: escalate · re-entry: continue: reuse branch
- [ ] **handoff** — skill: `h2t-core:handoff` · input: `session record + run outcome` · done: session record written · failure: n/a (terminal) · re-entry: idempotent: re-run handoff

## Gates

- Codex review-gate after each milestone/checkpoint AND at the end (embedded content,
  read-only). GATE FAIL if any `[P1]`.
- Council finish-gate at the end (codex + >=2 Opus lenses) -> SOUND / blockers.
- pre-merge-check before PR.
- `N_gate_attempts` = 2. One attempt = one fix edit + one gate/test re-run.

## Decision-protocol

Auto-resolve ONLY allow-listed, reversible decisions (library/API call shape; formatting/
naming within conventions; test-fixture values; doc wording): research best-practice ->
pick -> append to Decision-log -> continue. Escalate everything else.

Hard-stops (stop -> eligible WIP-commit -> handoff; never auto-resolve):
- **Irreversible / destructive** (delete/force-push, merge to main, external publish/send,
  deleting/modifying pre-existing untracked files).
- **Money / budget** (paid runs, token budget over limit, council/codex beyond cost-gate).
- **Scope / architecture change** (deviation from approved spec, new invariant, redefined goal).
- **Gate not fixable in** `N_gate_attempts`.

## Execution principles

Verify branch before every commit; `git mv`/`git rm` only; never delete/modify pre-existing
untracked files (creating this run's own artifacts is allowed). One command per Bash call.
Frequent small commits. Codex subagents one-at-a-time, never parallel.

## Blocker / fail-safe protocol

Record the blocker + what was tried -> eligible WIP-commit (stage only intentional files,
never `git add -A`, never commit a red suite as green, message `WIP:` + what was left) ->
`h2t-core:handoff`. Never force a broken merge or a false-green.

## Decision-log

- (append-only; auto-resolved defaults recorded here)
- 2026-07-10 · write-spec, write-plan pre-satisfied (artifacts exist, operator-approved spec via brainstorming user-review gate; plan advisor-hardened) → checked without re-run.
- 2026-07-10 · review-spec + plan-gate merged into ONE codex-rescue pass (codex reads spec + full plan together). Rationale: spec is short methodology, plan operationalizes it; single pass gives both the codex lens without double cost. Both gates still gated on `no [P1]`. Reversible process decision.
