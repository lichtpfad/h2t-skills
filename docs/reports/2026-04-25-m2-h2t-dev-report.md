---
title: "M2: h2t-dev — Phase Report"
status: "closed"
date: "2026-04-25"
milestone: "M2: h2t-dev"
---

# M2: h2t-dev — Phase Report

**Plan:** `docs/superpowers/plans/2026-04-13-docs-skills-implementation.md`
**Period:** 2026-04-13 → 2026-04-25
**Issues closed:** 14

---

## What Was Implemented

### h2t-dev plugin (новый)

| Issue | Deliverable |
|-------|-------------|
| #26 | Scaffold h2t-dev plugin (`plugins/h2t-dev/`) |
| #27 | Migrate `pre-merge-check` skill |
| #28 | Migrate `github-issues` skill |
| #29 | Migrate `gh-memory` skill |
| #30 | Migrate `milestone-closure` skill |

### Documentation Skills (Phase 7)

| Issue | Skill | Script |
|-------|-------|--------|
| #64 | Phase 7 umbrella | — |
| #65 | `docs-lint` | `scripts/lint.py` — frontmatter validation, docs structure compliance |
| #66 | `docs-init` | `scripts/init.py` — scaffold standard docs dirs + rules |
| #67 | `docs-cleanup` | `scripts/cleanup.py` — archive old plans/specs after milestone |
| #68 | `docs-sync-labels` | `scripts/sync_labels.py` + `data/labels.json` |

Shared lib: `plugins/h2t-dev/lib/docs/common.py` — REPO_MANIFEST (16 repos), tier helpers, git/fs utilities.

### Bulk Operations

| Issue | Deliverable |
|-------|-------------|
| #69 | Refactor `h2t-ops:research-agent` → curl-first Exa + Anysite + fail-loud |
| #76 | Bulk frontmatter fix — 179 files across h2t-* repos via `docs-lint --fix-frontmatter` |
| #77 | Legacy label migration — 505 issues relabelled, 329 labels deleted across 16 repos via `migrate_legacy_labels.py` |

### h2t-core: scaffold-project

| Issue | Deliverable |
|-------|-------------|
| #18 | `scaffold-project` wizard skill — `SKILL.md` + `scaffold_project.py` (create + github subcommands) |

---

## Key Architectural Decisions

- **Shared lib pattern**: `plugins/h2t-dev/lib/docs/` со `sys.path` inject — та же схема, что в gather CLI. Позволяет переиспользовать `REPO_MANIFEST` и хелперы во всех 4 skills без дублирования.
- **Claude as wizard**: `scaffold-project` реализован как разговорный wizard в SKILL.md, Python скрипт только создаёт файлы/git. Не нужен Inquirer.js или интерактивный ввод.
- **Idempotent migrations**: `migrate_legacy_labels.py` с `--dry-run` по умолчанию, `--apply` флаг — безопасно запускать повторно.
- **labels.json в плагине**: canonical labels.json bundled в `docs-sync-labels/data/` для offline-доступа без зависимости от `C:/dev/docs/standards/`.

---

## Changed Files (by area)

```
plugins/h2t-dev/
  .claude-plugin/plugin.json
  lib/docs/__init__.py, common.py
  skills/docs-cleanup/, docs-init/, docs-lint/, docs-sync-labels/
  skills/gh-memory/, github-issues/, milestone-closure/, pre-merge-check/
  skills/docs-sync-labels/scripts/migrate_legacy_labels.py

plugins/h2t-core/
  skills/scaffold-project/SKILL.md
  skills/scaffold-project/scripts/scaffold_project.py
  .claude-plugin/plugin.json  (3.0.14 → 3.0.17)

.claude-plugin/marketplace.json
scripts/bump_plugin.py, check_marketplace_sync.py
```

---

## Test Coverage

- `tests/` — 45 tests pass (gather CLI, init-project, detect_project)
- `scaffold_project.py` — dry-run mode verified manually
- `migrate_legacy_labels.py` — dry-run validated before `--apply` run

---

## Candidates for Next Phase

- **#71** `h2t-ops:research` — JSON/MD role docs, retention policy, multi-key routing
- **#70** `h2t-ops:research` v0.2 — fork, eval mode, h2t-evals integration
- **#75** 4 orphan plugins not in marketplace.json
- **#73** `run-hook.cmd` cross-platform fix
