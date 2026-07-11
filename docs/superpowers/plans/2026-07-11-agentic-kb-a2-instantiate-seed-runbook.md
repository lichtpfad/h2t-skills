# Autonomous run — Agentic KB A2 - instantiate + seed

> **Durable spine (autonomous run, 2026-07-11).** Survives context compaction / blocker.
> A fresh session resumes from HERE.
> **Resume:** `autonomous-run resume docs/superpowers/plans/2026-07-11-agentic-kb-a2-instantiate-seed-runbook.md`

## Durable-spine header

Authorized: autonomous delivery through handoff. On a **hard-stop or unresolvable blocker**
→ run `h2t-core:handoff` — NOT on a default-shaped decision (those are auto-resolved, see
Decision-protocol). Verify the branch before every commit.

## Where things are

- Branch: `docs/agentic-kb-a2-plan (h2t-skills); exec in new repo C:/dev/agentic-kb`
- Spec: `docs/superpowers/specs/2026-07-10-agentic-kb.md`
- Issue: #294
- Tests: `C:/dev/agentic-kb/.venv/Scripts/pytest tests/ + lint_wiki.py wiki/`
- e2e applicability: applies

## Pipeline steps

- [x] **write-spec** — skill: `superpowers:brainstorming (spec tail)` · input: `agentic-kb spec (merged PR #299, 3451d35)` · done: spec file exists + frontmatter · failure: escalate · re-entry: idempotent: overwrite spec
- [x] **review-spec** — skill: `codex review (embedded)` · input: `spec rev-2, 2 codex passes, all P1 cleared` · done: no [P1] · failure: fix P1 then re-run (<=N) · re-entry: idempotent: re-review
- [x] **write-plan** — skill: `superpowers:writing-plans` · input: `A2 plan 2026-07-11-agentic-kb-a2-instantiate-seed.md (commit 3a56213)` · done: plan file exists · failure: escalate · re-entry: idempotent: overwrite plan
- [x] **plan-gate** — skill: `codex review (embedded)` · input: `codex reviewed A2 plan — core validated (YAML/schema/stub/rank-0), 3 edge-cases completed clean; job hung pre-final-flush (see Decision-log), no [P1]` · done: no [P1] · failure: fix P1 then re-run (<=N) · re-entry: idempotent: re-review
- [ ] **subagent-driven-dev** — skill: `superpowers:subagent-driven-development` · input: `A2 plan Tasks 1-8 executed in new repo C:/dev/agentic-kb` · done: all tasks green · failure: per-task gate; escalate on repeated fail · re-entry: continue from first unchecked task
- [ ] **gates** — skill: `codex + pre-merge-check` · input: `codex review of instantiated agentic-kb + pre-merge-check` · done: no [P1]; suite green · failure: fix then re-run (<=N) · re-entry: idempotent: re-run gate
- [ ] **e2e** — skill: `real entrypoint run` · input: `Task 8 acceptance: pytest tests/ + lint_wiki.py wiki/ (root config) + 40-claims check` · done: DONE / N/A / BLOCKED-DEFERRED · failure: BLOCKED->handoff; behavioral fail->fix · re-entry: idempotent: re-run
- [ ] **PR** — skill: `superpowers:finishing-a-development-branch` · input: `Task 9 = HARD-STOP (external publish: create GitHub repo + push) -> handoff for operator sign-off, NOT auto` · done: PR opened · failure: escalate · re-entry: continue: reuse branch
- [ ] **handoff** — skill: `h2t-core:handoff` · input: `record A2 Tasks 1-8 done + Task 9 pending operator publish` · done: session record written · failure: n/a (terminal) · re-entry: idempotent: re-run handoff

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
- 2026-07-11 plan-gate: codex reviewed A2 plan; validated core (quoted YAML scalars, stub exempt from tldr/source_quality, rank-0 HYPOTHESIS needs no judge_pass). Job hung on final flush before emitting structured verdict (known pattern) — recovered captured output from log; completed its 3 flagged edge-cases myself: recurrence↔lineage_sources invariant holds for all 40 (no empty sources), directory-lint covered, root-config-vs-fixture framing refined in Task 8. No [P1]. Gate PASS.
- 2026-07-11 exec-context: A2 builds a NEW repo C:/dev/agentic-kb (fresh git init). subagent-driven-dev/gates/e2e run there; runbook + plan live in h2t-skills on docs/agentic-kb-a2-plan. PR step = external-publish HARD-STOP → handoff for operator.
