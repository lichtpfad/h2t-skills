# Autonomous run — Wave 1 — one behaviour, one code path

> **Durable spine (autonomous run, 2026-08-23).** Survives context compaction / blocker.
> A fresh session resumes from HERE.
> **Resume:** `autonomous-run resume docs/superpowers/plans/2026-08-23-wave1-one-code-path-runbook.md`

## Durable-spine header

Authorized: autonomous delivery through handoff. On a **hard-stop or unresolvable blocker**
→ run `h2t-core:handoff` — NOT on a default-shaped decision (those are auto-resolved, see
Decision-protocol). Verify the branch before every commit.

## Where things are

- Branch: `feat/wave1-one-code-path`
- Spec: `docs/superpowers/plans/2026-08-23-skills-release-hardening.md`
- Issue: #392 (Tasks 1-3), #381 (Task 4)
- Tests: `.venv/bin/pytest tests/ lib/ -q`
- e2e applicability: applies — the hook path (a live session-start briefing) is an externally-observable surface unit tests do not exercise end-to-end

## Pipeline steps

> Tasks 1-5 done. Every task passed its own codex diff gate; three needed a second or third
> pass. Findings that mattered: argv slicing rejected a valid legacy shape (Task 1); an
> importorskip would have made a CI step green while running nothing (Task 4); the prewrite
> tripwire was vacuous twice before a planted gate finally turned it red (Task 5).
> Cumulative wave gate: no [P1].
>
> e2e measured green: the hook emits a briefing carrying `### Previous Session`; both
> `h2t-ops gather` and `h2t-gather` emit it; `h2t-gather --cwd /nonexistent` exits 3.
> pre-merge-check: no secrets in the diff, 1956 passed / 7 skipped, wheel builds, and ruff
> is three findings lighter than main with none added.

- [x] **write-spec** — skill: `superpowers:brainstorming (spec tail)` · input: `the plan itself is the spec — docs/superpowers/plans/2026-08-23-skills-release-hardening.md, merged in #393. Each task argues from a re-runnable measurement instead of a separate spec doc.` · done: spec file exists + frontmatter · failure: escalate · re-entry: idempotent: overwrite spec
- [x] **review-spec** — skill: `codex review (embedded)` · input: `folded into plan-gate: one codex pass covers both, since spec and plan are one document.` · done: no [P1] · failure: fix P1 then re-run (<=N) · re-entry: idempotent: re-review
- [x] **write-plan** — skill: `superpowers:writing-plans` · input: `superpowers:writing-plans, 9 tasks; Wave 1 = Tasks 1-5. Merged #393, measured #394, gated #395.` · done: plan file exists · failure: escalate · re-entry: idempotent: overwrite plan
- [x] **plan-gate** — skill: `codex review (embedded)` · input: `four codex passes (exec -s read-only, reasoning=high, embedded). Six findings closed, two of them [P1]: the pyproject contradiction in Task 4 and the argv[2:] slice in Task 1. Fourth pass: no open [P1], GATE PASS (#395).` · done: no [P1] · failure: fix P1 then re-run (<=N) · re-entry: idempotent: re-review
- [x] **subagent-driven-dev** — skill: `superpowers:subagent-driven-development` · input: `Tasks 1-5 of the plan, executed INLINE via superpowers:executing-plans rather than subagents — this session is not authorised to dispatch the Agent tool. TDD per task: red first, read the failure text, then implement.` · done: all tasks green · failure: per-task gate; escalate on repeated fail · re-entry: continue from first unchecked task
- [x] **gates** — skill: `codex + pre-merge-check` · input: `codex review over the Wave 1 diff after each task and once at the end; then h2t-dev:pre-merge-check. GATE FAIL on any [P1].` · done: no [P1]; suite green · failure: fix then re-run (<=N) · re-entry: idempotent: re-run gate
- [x] **e2e** — skill: `real entrypoint run` · input: `the hook path end to end: a fresh session-start whose briefing carries '### Previous Session', plus `h2t-ops gather session-start` and `h2t-gather` producing byte-identical output.` · done: DONE / N/A / BLOCKED-DEFERRED · failure: BLOCKED->handoff; behavioral fail->fix · re-entry: idempotent: re-run
- [ ] **PR** — skill: `superpowers:finishing-a-development-branch` · input: `one PR for Wave 1 off feat/wave1-one-code-path, closing #392 and advancing #381.` · done: PR opened · failure: escalate · re-entry: continue: reuse branch
- [ ] **handoff** — skill: `h2t-core:handoff` · input: `h2t-core:handoff — now writes without asking for a name (#391).` · done: session record written · failure: n/a (terminal) · re-entry: idempotent: re-run handoff

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
