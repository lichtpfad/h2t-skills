---
title: "Autonomous run — Wave 2 — consistency before the skills release"
status: "draft"
date: "2026-08-23"
milestone: ""
issue: ""
---
# Autonomous run — Wave 2 — consistency before the skills release

> **Durable spine (autonomous run, 2026-08-23).** Survives context compaction / blocker.
> A fresh session resumes from HERE.
> **Resume:** `autonomous-run resume docs/superpowers/plans/2026-08-23-wave2-consistency-runbook.md`

## Durable-spine header

Authorized: autonomous delivery through handoff. On a **hard-stop or unresolvable blocker**
→ run `h2t-core:handoff` — NOT on a default-shaped decision (those are auto-resolved, see
Decision-protocol). Verify the branch before every commit.

## Where things are

- Branch: `feat/wave2-consistency`
- Spec: `docs/superpowers/plans/2026-08-23-skills-release-hardening.md`
- Issue: #381 (CI coverage), #339 (kb PR to land)
- Tests: `.venv/bin/pytest tests/ lib/ -q`
- e2e applicability: applies — h2t-hook fires a real handler; the wheel is installed into a throwaway venv

## Pipeline steps

- [x] **write-spec** — skill: `superpowers:brainstorming (spec tail)` · input: `the plan itself is the spec; Wave 2 tasks 6-12 written from measurement` · done: spec file exists + frontmatter · failure: escalate · re-entry: idempotent: overwrite spec
- [x] **review-spec** — skill: `codex review (embedded)` · input: `folded into plan-gate — same document` · done: no [P1] · failure: fix P1 then re-run (<=N) · re-entry: idempotent: re-review
- [x] **write-plan** — skill: `superpowers:writing-plans` · input: `Tasks 10-12 added; Task 6 rewritten after measurement contradicted it` · done: plan file exists · failure: escalate · re-entry: idempotent: overwrite plan
- [x] **plan-gate** — skill: `codex review (embedded)` · input: `4 passes, 8 [P1] found and fixed; a 5th finding rejected as a statement about the worktree, not the plan` · done: no [P1] · failure: fix P1 then re-run (<=N) · re-entry: idempotent: re-review
- [x] **subagent-driven-dev** — skill: `superpowers:executing-plans (inline, no subagents)` · input: `Tasks 6-12 done; 11 merged as #339. Codex review after each, all [P1] reproduced before fixing` · done: all tasks green · failure: per-task gate; escalate on repeated fail · re-entry: continue from first unchecked task
- [x] **gates** — skill: `codex + pre-merge-check` · input: `cumulative gate found the T6/T10 seam (1a08d7d); GATE PASS on pass 2; pre-merge-check READY TO MERGE` · done: no [P1]; suite green · failure: fix then re-run (<=N) · re-entry: idempotent: re-run gate
- [x] **e2e** — skill: `real entrypoint run` · input: `DONE — handlers fired from a wheel install with the cache redirected away; evals status/report exit 0` · done: DONE / N/A / BLOCKED-DEFERRED · failure: BLOCKED->handoff; behavioral fail->fix · re-entry: idempotent: re-run
- [x] **PR** — skill: `superpowers:finishing-a-development-branch` · input: `#398 opened; #339 merged 2026-08-23` · done: PR opened · failure: escalate · re-entry: continue: reuse branch
- [x] **handoff** — skill: `h2t-core:handoff` · input: `personal-os-agent-skills-wave2-release-2026-08-24; released as h2t-core 3.2.24` · done: session record written · failure: n/a (terminal) · re-entry: idempotent: re-run handoff

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
