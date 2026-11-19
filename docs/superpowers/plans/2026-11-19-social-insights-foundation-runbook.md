---
title: "Autonomous run — Social insights foundation"
status: "draft"
date: "2026-11-19"
milestone: ""
issue: ""
---
# Autonomous run — Social insights foundation

> **Durable spine (autonomous run, 2026-11-19).** Survives context compaction / blocker.
> A fresh session resumes from HERE.
> **Resume:** `autonomous-run resume docs/superpowers/plans/2026-11-19-social-insights-foundation-runbook.md`

## Durable-spine header

Authorized: autonomous delivery through handoff. On a **hard-stop or unresolvable blocker**
→ run `h2t-core:handoff` — NOT on a default-shaped decision (those are auto-resolved, see
Decision-protocol). Verify the branch before every commit.

## Where things are

- Branch: `feat/social-insights-foundation`
- Spec: `docs/superpowers/specs/2026-11-19-social-pipeline-design.md`
- Issue: none
- Tests: `C:/dev/h2t-skills-wt-social-insights/.venv/Scripts/pytest tests/core tests/connectors tests/governance -q`
- e2e applicability: BLOCKED-DEFERRED (live smoke needs author's secrets migration, plan Task 9)

## Pipeline steps

- [x] **write-spec** — skill: `superpowers:brainstorming (spec tail)` · input: `docs/superpowers/specs/2026-11-19-social-pipeline-design.md` (bb57d28f, 3b39789a) · done: spec file exists + frontmatter · failure: escalate · re-entry: idempotent: overwrite spec
- [x] **review-spec** — skill: `codex review (embedded)` · input: previous session (two Codex passes, findings closed per handoff 8cde21ba) · done: no [P1] · failure: fix P1 then re-run (<=N) · re-entry: idempotent: re-review
- [x] **write-plan** — skill: `superpowers:writing-plans` · input: `docs/superpowers/plans/2026-11-19-social-insights-foundation.md` (9a586f2c) · done: plan file exists · failure: escalate · re-entry: idempotent: overwrite plan
- [x] **plan-gate** — skill: `codex review (embedded)` · input: previous session (two Codex passes on the plan, closed) · done: no [P1] · failure: fix P1 then re-run (<=N) · re-entry: idempotent: re-review
- [x] **subagent-driven-dev** — skill: `superpowers:subagent-driven-development` · input: plan Tasks 1-8 (Task 9 manual, needs the author), commits 5b0ce166..3408408d, per-task Codex review clean · done: all tasks green · failure: per-task gate; escalate on repeated fail · re-entry: continue from first unchecked task
- [x] **gates** — skill: `codex + pre-merge-check` · input: final Codex gate + Opus standards/spec reviews, fix wave c9eab57f..c5b43e49, verdict `docs/reports/2026-11-19-council-validation-social-insights.md` · done: no [P1]; suite green · failure: fix then re-run (<=N) · re-entry: idempotent: re-run gate
- [x] **e2e** — skill: `real entrypoint run` · input: DONE 2026-11-19 (plan Task 9, owner present) — secret key names moved to config (Task 10, 43c87e9e..3781d3d0, Codex PASS); no secret files moved; live `discover --write` found 7 IG, 15 FB, 2 Threads; `check` → 3 enabled accounts, username + 3 posts each; `run insights --account instagram:hou2touch` → 120 posts, report `~/.h2t/data/social/insights/instagram_hou2touch/2026-11-19.json`, journal steps 2→3→4→6 linked by run b14aa4bd; `online_followers` returned `value: {}` from Meta (empty, not a code fault) · done: DONE / N/A / BLOCKED-DEFERRED · failure: BLOCKED->handoff; behavioral fail->fix · re-entry: idempotent: re-run
- [x] **PR** — skill: `superpowers:finishing-a-development-branch` · input: https://github.com/lichtpfad/h2t-skills/pull/667 (not merged; merge is the author's call) · done: PR opened · failure: escalate · re-entry: continue: reuse branch
- [x] **handoff** — skill: `h2t-core:handoff` · input: session record 9ebdf6c0-83d8-4ea2-94b2-63b9727d0ca3 · done: session record written · failure: n/a (terminal) · re-entry: idempotent: re-run handoff

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
- Operator instruction 2026-11-19: autonomous; per-task review by Codex (checker != writer); final review on spec + development standards. Final review = `mattpocock-skills:code-review` (Standards + Spec axes, two Claude lenses) + Codex final gate — serves as the council finish-gate.
- Plan Task 9 (secrets migration + live smoke) is not executed: needs the author and touches secrets (hard-stop). e2e stays BLOCKED-DEFERRED.
- Pre-flight rulings live in `.superpowers/sdd/2026-11-19-social-insights-foundation/progress.md`.
- PR step: opening a PR is outward but reversible; merge to main is NOT done (hard-stop).
