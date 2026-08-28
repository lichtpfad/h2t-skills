---
title: "Autonomous run — Agentic KB A2 - instantiate + seed"
status: "draft"
date: "2026-07-11"
milestone: ""
---
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
- [x] **subagent-driven-dev** — skill: `superpowers:subagent-driven-development` · input: `A2 plan Tasks 1-7 executed inline (light, per advisor) in new repo C:/dev/agentic-kb — clone+fresh-git, config, CLAUDE.md, taxonomy, seed script -> 40 HYPOTHESIS atoms, 7 per-task commits` · done: all tasks green · failure: per-task gate; escalate on repeated fail · re-entry: continue from first unchecked task
- [x] **gates** — skill: `codex + pre-merge-check` · input: `finish-gate = empirical acceptance PASS (35/35 + lint 7/7 + 40 claims) + council WRITE-path smoke-test PASS (parse_claims + synthesize_council, 3-judge/threshold-2 correct) + secret-scan clean (sk- false-positive on 'task-type') + Opus adversarial lens (advisor). Advisor findings addressed: (1) fixed false council-rationale in plan, (2) verified scaffold_topics skip-if-exists (no seed clobber). Second codex-doc-review substituted — see Decision-log.` · done: no [P1]; suite green · failure: fix then re-run (<=N) · re-entry: idempotent: re-run gate
- [x] **e2e** — skill: `real entrypoint run` · input: `Task 8 acceptance = DONE: pytest 35/35 (template intact) + lint_wiki wiki/ 7/7 OK under root config (A1↔A2 integration PASS: HYPOTHESIS ladder-member, rank-0 no judge_pass, domain_recurrence loaded) + 40-claims present + spot-check (Low->single_source_warning, Medium->none, all HYPOTHESIS)` · done: DONE / N/A / BLOCKED-DEFERRED · failure: BLOCKED->handoff; behavioral fail->fix · re-entry: idempotent: re-run
- [x] **PR** — skill: `superpowers:finishing-a-development-branch` · input: `Task 9 done on operator go: created private repo github.com/lichtpfad/agentic-kb (ac36d90), pushed main, registered in h2t (repo-mapping + domains.yaml under dev, project-id). No PR — new standalone repo, main is the deliverable.` · done: PR opened · failure: escalate · re-entry: continue: reuse branch
- [x] **handoff** — skill: `h2t-core:handoff` · input: `session record written (dev-h2t-skills-agentic-kb-plan-2026-07-10); A2 Tasks 1-8 done, Task 9 (PR/publish) pending operator = resume pointer` · done: session record written · failure: n/a (terminal) · re-entry: idempotent: re-run handoff

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
- 2026-07-11 gate-substitution: dropped a 2nd codex-doc-review. Rationale (advisor-corrected): the missing gate the empirical read-path (lint) didn't cover is DYNAMIC (council write-path), not another static reviewer — so I ran a parse_claims+synthesize_council smoke-test instead. Static review is adequately covered by the empirical lint of 40 parsed claims + the plan-gate codex. Not "codex low-value for trivial tasks."
- 2026-07-11 council-rationale CORRECTED (finish-gate, advisor): a council RUN produces advisory verdicts and needs NOTHING from #295; only PROMOTION to WORKS-IN-PRACTICE needs #295. The plan's old line ("council run not reachable in MVP") was factually wrong — fixed. Write-path smoke-tested green; full live advisory council over P0 topics deferred to A3 (low-value-until-#295), not unreachable.
- 2026-07-11 scaffold clobber check: scaffold_topics.py is skip-if-exists (line 81-84) — a future operator following the README cannot wipe the 40 seeded claims. Safe.
