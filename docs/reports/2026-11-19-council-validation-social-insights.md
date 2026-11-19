---
title: "Council validation — social insights foundation"
status: "done"
date: "2026-11-19"
milestone: ""
issue: ""
---

# Council validation — social insights foundation

Branch `feat/social-insights-foundation`, range `3b39789a..c5b43e49`.
Plan: `docs/superpowers/plans/2026-11-19-social-insights-foundation.md` (Tasks 1-8; Task 9 is manual).
Spec: `docs/superpowers/specs/2026-11-19-social-pipeline-design.md`.

## Lenses

| Lens | Engine | First verdict | After fix wave |
|---|---|---|---|
| Correctness / runtime | Codex (gpt-5.6-terra, high) | FAIL: 2 P1, 3 P2 | F1-F12 addressed, no new P2 |
| Repo standards | Claude Opus | 4 P2 + P3 judgement calls | fixed in the wave or ruled |
| Spec compliance | Claude Opus | 3 P2 + P3 | fixed in the wave or ruled |

Every task had its own Codex review before this (checker is not the writer).

## Fix wave

`c9eab57f..c5b43e49`, 8 commits, items F1-F13:
a step-6 failure record on every mid-run error;
API base overrides refused when they carry a query, fragment or userinfo;
Graph error bodies journaled;
the token-key prefix must match the network;
the limit must be positive;
Facebook handle collisions;
exit codes 3/5;
the spec §6 journal fields;
one page-lookup helper;
help text, test names, runbook frontmatter.

## Residual

- F13 "frontmatter omits `reason:`" — parked. The frontmatter matches the sibling
  `2026-08-23-wave2-consistency-runbook.md` field for field.
- Rulings kept against reviewer findings:
  - no per-plugin version bump, because the pack releases in lockstep;
  - the shared `_graph.py` stays;
  - plan-mandated interfaces for later processes stay.

## Gates (command output)

```text
pytest tests/ -q                         4669 passed, 55 skipped, 2 deselected
uvx ruff==0.16.4 check plugins/ lib/ h2t_ops/ tests/ scripts/   All checks passed!
gitleaks git --log-opts=3b39789a..HEAD   26 commits scanned, no leaks found
uv build --wheel                         h2t_ops-4.1.0-py3-none-any.whl, social package + resources/social/defaults.yaml present
pip-audit -r constraints.txt             96 known vulnerabilities in 8 packages; pre-existing (branch does not touch constraints.txt, uv.lock, pyproject.toml)
```

## Verdict

SOUND for review and merge by the author.

Not verified:
- the live API: metric names, Threads insight shapes, and online_followers;
- that waits for plan Task 9, run with the author's tokens.
