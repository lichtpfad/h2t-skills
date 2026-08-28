---
title: "Autonomous run — Skill telemetry L1 activation"
status: "draft"
date: "2026-07-12"
milestone: ""
---
# Autonomous run — Skill telemetry L1 activation

> **Durable spine (autonomous run, 2026-07-12).** Survives context compaction / blocker.
> A fresh session resumes from HERE.
> **Resume:** `autonomous-run resume docs/superpowers/plans/2026-07-12-skill-telemetry-l1-activation-runbook.md`

## Durable-spine header

Authorized: autonomous delivery through handoff. On a **hard-stop or unresolvable blocker**
→ run `h2t-core:handoff` — NOT on a default-shaped decision (those are auto-resolved, see
Decision-protocol). Verify the branch before every commit.

## Where things are

- Branch: `feat/skill-telemetry-l1-activation`
- Spec: `docs/superpowers/specs/2026-07-12-skill-telemetry-l1-activation.md`
- Issue: #289 (children #306/#307/#309/#310/#312/#313)
- Tests: `C:/dev/h2t-skills/.venv/Scripts/pytest lib tests/core tests/connectors plugins/h2t-core/skills/autonomous-run/scripts -q`
- e2e applicability: N/A (no integration surface — local-only telemetry)

## Pipeline steps

- [x] **write-spec** — skill: `superpowers:brainstorming (spec tail)` · input: `pre-existing eng-reviewed spec 2026-07-12-skill-telemetry-l1-activation.md` · done: spec file exists + frontmatter · failure: escalate · re-entry: idempotent: overwrite spec
- [x] **review-spec** — skill: `codex review (embedded)` · input: `spec carries Eng-review outcome + Codex outside-voice (all findings folded in, no [P1])` · done: no [P1] · failure: fix P1 then re-run (<=N) · re-entry: idempotent: re-review
- [x] **write-plan** — skill: `superpowers:writing-plans` · input: `8-task TDD plan, session.py parity discipline, D8 scoped to research` · done: plan file exists · failure: escalate · re-entry: idempotent: overwrite plan
- [x] **plan-gate** — skill: `codex review (embedded)` · input: `codex 4 passes: attempt1 3xP1 fixed, attempt2 crawl-NameError fixed, close-out CI-scope nit fixed; primary-source verified test reality; green baseline 1097 passed` · done: no [P1] · failure: fix P1 then re-run (<=N) · re-entry: idempotent: re-review
- [x] **subagent-driven-dev** — skill: `executing-plans (inline; cost-gated, mechanical TDD)` · input: `Tasks 1-8 executed in order; each session.py task re-synced both vendored copies + parity + CI-scope green; 8 commits 2bf3145..dc54cf4 + repo-assets + gather-metric; CI-scope 1117 passed; ruff clean on changed lines` · done: all tasks green · failure: per-task gate; escalate on repeated fail · re-entry: continue from first unchecked task
- [x] **gates** — skill: `codex + council + pre-merge-check` · input: `codex review-gate PASS (P2 _emit_eval loader-in-try + P3 comment fixed, 3b5306f); council finish-gate SOUND (codex PASS + advisor Lens1 SOUND + fresh-Opus Lens2 SOUND: every acceptance MET, no P1/P2, P3 residuals R1 proxy-mark→#305/R2 push-untested-out-of-scope/R3 mtime-flake fixed); final CI-scope 1117 passed; pre-merge-check next` · done: no [P1]; suite green · failure: fix then re-run (<=N) · re-entry: idempotent: re-run gate
- [x] **e2e** — skill: `real entrypoint run` · input: `N/A — local-only telemetry, no external service surface (push/central = #305). Runtime import path empirically exercised by test_emit_eval_records_research_cost (vendored eval.session via sys.path + relative .skill_class)` · done: N/A · failure: BLOCKED->handoff; behavioral fail->fix · re-entry: idempotent: re-run
- [x] **PR** — skill: `superpowers:finishing-a-development-branch` · input: `PR #314 opened → main (branch pushed); merge to main is operator hard-stop, NOT auto-done` · done: PR opened · failure: escalate · re-entry: continue: reuse branch
- [x] **handoff** — skill: `h2t-core:handoff` · input: `run complete: PR #314 open, council SOUND; handoff records deferred D8/doc-migration/connector-path + redeploy-needed + codex/research-parity conflict risk` · done: session record written · failure: n/a (terminal) · re-entry: idempotent: re-run handoff

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
- **D7 doc-refs (2026-07-12):** `record_eval`/`estimate_tokens` code deleted (×3 eval.py + ×3 `__init__`
  exports + root/h2t test_eval.py). README/doc references NOT rewritten this run — the 3
  `lib/gather/README.md` copies + `docs/gather-agent-instructions.md` + `docs/briefing-for-evals-agent.md`
  weave `record_eval` in as the whole gather-eval tutorial (import examples, "eval is mandatory", API
  section) and also carry unrelated staleness (old `claude-agent-skills` repo path). A correct migration
  to the SkillEval context-manager API is a separate bounded doc pass → **deferred to handoff follow-up**,
  logged (not silently dropped). Historical `docs/plans/2026-03-25-gather-framework.md` left as-is (archival).
