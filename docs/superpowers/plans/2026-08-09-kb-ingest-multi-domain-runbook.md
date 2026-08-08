# Autonomous run — kb-ingest Multi-Domain Awareness

> **Durable spine (autonomous run, 2026-08-09).** Survives context compaction / blocker.
> A fresh session resumes from HERE.
> **Resume:** `autonomous-run resume docs/superpowers/plans/2026-08-09-kb-ingest-multi-domain-runbook.md`

## Durable-spine header

Authorized: autonomous delivery through handoff. On a **hard-stop or unresolvable blocker**
→ run `h2t-core:handoff` — NOT on a default-shaped decision (those are auto-resolved, see
Decision-protocol). Verify the branch before every commit.

## Where things are

- Branch: `feat/kb-ingest-multi-domain`
- Spec: `docs/superpowers/specs/2026-08-09-kb-ingest-multi-domain-design.md`
- Issue: none
- Tests: `C:/dev/llm-kb-template/.venv/Scripts/pytest tests/ -q`
- e2e applicability: applies

## Pipeline steps

- [x] **write-spec** — skill: `superpowers:brainstorming (spec tail)` · input: `kb-ingest multi-domain design (2-repo)` · done: spec file exists · failure: escalate · re-entry: idempotent: overwrite spec
- [x] **review-spec** — skill: `codex review (embedded)` · input: `covered in plan-gate (codex read spec+plan)` · done: no [P1] · failure: fix P1 then re-run (<=N) · re-entry: idempotent: re-review
- [x] **write-plan** — skill: `superpowers:writing-plans` · input: `E1 engine + S1-S5 skill (71e08d0)` · done: plan file exists · failure: escalate · re-entry: idempotent: overwrite plan
- [x] **plan-gate** — skill: `codex review (embedded)` · input: `codex gate: P1 was false framing; P2 test-desc fixed` · done: no [P1] · failure: fix P1 then re-run (<=N) · re-entry: idempotent: re-review
- [x] **subagent-driven-dev** — skill: `superpowers:executing-plans (inline TDD; 2 repos)` · input: `docs/superpowers/plans/2026-08-09-kb-ingest-multi-domain-plan.md` · done: E1 green (490 passed, llm-kb-template); S1-S5 skill edits applied + self-review PASS · failure: per-task gate; escalate on repeated fail · re-entry: continue from first unchecked task
- [x] **gates** — skill: `codex + pre-merge-check` · input: `engine E1 diff review + full suite; skill self-review` · done: 490 passed (engine, bit-for-bit); E1 code == plan-gate-approved (codex ITEM1 OK), no redundant re-review; skill self-review PASS; both diffs clean of debug/secrets · failure: fix then re-run (<=N) · re-entry: idempotent: re-run gate
- [ ] **e2e** — skill: `real entrypoint run` · input: `honesty --slug on a 2-domain fixture (real CLI)` · done: DONE / N/A / BLOCKED-DEFERRED · failure: BLOCKED->handoff; behavioral fail->fix · re-entry: idempotent: re-run
- [ ] **PR** — skill: `superpowers:finishing-a-development-branch` · input: `engine PR (llm-kb-template) + skill PR (h2t-skills)` · done: PRs opened; merge = operator hard-stop · failure: escalate · re-entry: continue: reuse branch
- [ ] **handoff** — skill: `h2t-core:handoff` · input: `session record` · done: session record written · failure: n/a (terminal) · re-entry: idempotent: re-run handoff

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
- 2026-08-09: two-repo run. E1 (parse_claims) executes in C:/dev/llm-kb-template on branch `fix/parse-claims-domain` → own PR. Skill edits (S1-S5) in C:/dev/h2t-skills on `feat/kb-ingest-multi-domain` → own PR. Both PRs opened, NEITHER merged (merge to main = operator hard-stop). Executed inline per `prescriptive-plan-inline-execution` (codex-gated, sequential).
- 2026-08-09 (S4 correction): the `lichtpfad` marketplace is a GitHub source with `autoUpdate:true` — the live SKILL markdown is served from the GitHub-pulled plugin cache, NOT from `uv tool install` (which only rebuilds CLI binaries). So the live skill reloads AUTOMATICALLY after the skill PR is merged to main; there is no autonomous pre-merge reload. Version bump 1.5.9→1.5.10 is what lets autoUpdate detect the release. `uv tool install` was run (refreshes CLI binaries, harmless) but is NOT the reload path. Recorded for handoff.
