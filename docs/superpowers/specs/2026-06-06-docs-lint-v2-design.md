---
title: "docs-lint v2: Full Audit + Maintenance Pipeline"
status: approved
owner: stanislav
date: 2026-06-06
---

# docs-lint v2: Full Audit + Maintenance Pipeline

## Problem

Current docs-lint runs a minimal mechanical check (orphans, frontmatter) and stops after
every finding to ask the user what to do next. It doesn't detect project type, doesn't
analyze code organization or agent accessibility, and has no concept of project lifecycle
stage. The result: shallow output that misses structural chaos, and constant friction from
confirmation prompts.

## Goal

A single skill invocation that:
1. Sniffs the project and shows a 3-line assessment
2. Asks **one** question about project stage
3. Either runs a full multi-angle audit → plan → issues → fixes, or runs maintenance lint
4. Validates results with a script gate, not the model

---

## Architecture

```
/h2t-dev:docs-lint
       │
       ▼
  [Phase 1: Sniff]        — automatic, no questions
  git ls-files
  CLAUDE.md, pyproject.toml, docs/README.md, .claude/rules/
  lint.py doctor --json
  → 3-line model assessment
       │
       ▼
  [Gate — ONE question]
  «Стадия: (1) наводим порядок  (2) зрелый проект»
       │
      / \
     /   \
    ▼     ▼
[Full   [Maintenance]
Audit]   lint.py audit
         safe-fixes авто
         show delta vs last .h2t-lint-state.jsonl
         done
    │
    ▼
[Multi-angle Analysis]   — model reads references on demand
    │
    ▼
[Prioritized Report]
    │
    ▼
[Write plan + commit]
    │
    ▼
[Create GitHub issues]   — immediately, not "later"
    │
    ▼
[Apply safe-fixes auto, destructive with confirm]
    │
    ▼
[Validation Gate]        — script, not model
    │
    ▼
[Append .h2t-lint-state.jsonl]
```

---

## Phase 1: Sniff

Sources read automatically (no user input):

| Source | Purpose |
|---|---|
| `git ls-files --cached --others --exclude-standard` | Full file tree, respects .gitignore |
| `CLAUDE.md` | Project type hints, rules |
| `pyproject.toml` / `package.json` / `requirements.txt` | Stack, setup maturity |
| `docs/README.md` | Navigation index presence |
| `.claude/rules/` | Agent instructions presence |
| `lint.py doctor --json` | Mechanical findings in ~2s |

Model outputs exactly 3 lines:
```
Тип: Python-инструмент, organic-grow
Состояние: docs частичные, code layout нестандартный, agent instructions отсутствуют
Сигнал: хаос → рекомендую full audit
```

---

## Audit Dimensions (Full mode)

Model loads references from `references/` on demand. All 8 dimensions run:

| # | Dimension | Source | What it checks |
|---|---|---|---|
| 1 | Docs structure | lint.py + documentation-structure.md | Orphans, required dirs, README navigation |
| 2 | Naming | lint.py + naming-conventions.md | ADR prefix, kebab-case, date prefix |
| 3 | Code organization | git ls-files + code-organization.md | src/ layout, tests inside packages, stray scripts |
| 4 | Data storage | git ls-files | Operational data (results/, runtime/) — isolated or in root |
| 5 | Agent accessibility | CLAUDE.md + .claude/rules/ | Env, commands, arch invariants, secrets, what's forbidden |
| 6 | Frontmatter | lint.py | Required fields by file type |
| 7 | Root hygiene | git ls-files (root only) | File count, snake_case names, stray scripts |
| 8 | Non-standard dirs/files | git ls-files vs standard template | Presence + meaningfulness of everything outside standard config |

Each dimension yields findings with severity: `critical / important / low`.

Model adds **semantic layer on top of scripts** — e.g. "CLAUDE.md mentions Phase A as
current but git log shows it closed 3 weeks ago" or "docs/README.md exists but 5 of 9
plans are unindexed."

---

## Non-Standard Dirs/Files (Dimension 8)

Everything not in the standard project template is evaluated:

```
Found non-standard path
        │
        ▼
   Is it needed?
   (git activity last 30d + content scan)
       / \
     Yes   No → DELETE (confirm)
     │
     ▼
  Covered by standard?
      / \
    Yes   No
    │          │
    ▼          ▼
 Misplaced   Project-specific?
 → MOVE           / \
   (confirm)    Yes   No → repeats across repos?
                │              │
                ▼              ▼
           EXCEPTION      ADD PROJECT TYPE
           (.h2t/         (PR to h2t-skills
           docs-lint.yaml) standards/)
```

Four outcomes: **DELETE / MOVE / EXCEPTION / ADD PROJECT TYPE**

EXCEPTION is stored in `.h2t/docs-lint.yaml` (machine-readable, parsed by lint.py):

```yaml
# .h2t/docs-lint.yaml
exceptions:
  - path: benchmark_results/
    reason: "TD performance operational data, updated live"
    type: operational_data
  - path: setlists/
    reason: "performance setlists archive"
    type: archive

project_type: td-tool   # override if autodetect wrong
```

lint.py reads this file and skips documented exceptions silently.

---

## Report Format

```
## docs-lint audit — {project} — {date}

### Critical (must fix)
- [code-org] hta/, engine/, td/ в корне → src/h2t_kraken/
- [agent] CLAUDE.md не содержит команды запуска тестов

### Important
- [non-standard] benchmark_results/ — нет документации назначения
- [docs] 3 orphan-файла не проиндексированы в docs/README.md

### Low
- [naming] docs/adr/_parking-lot.md → parking-lot.md

### Auto-fixed
- Созданы missing dirs: docs/reports/, docs/.artifacts/
- Добавлен frontmatter: td-scene-v0-implementation.md

### Validation gate
findings_before: 12  findings_after: 4  fixed: 8  new: 0  PASS
```

---

## Output Pipeline

1. **Plan file** → `docs/superpowers/plans/YYYY-MM-DD-docs-audit.md` + commit
2. **GitHub issues** → created immediately for critical + important findings
   - One issue per dimension with multiple findings grouped
   - Label: `type:docs`, priority from severity
3. **Safe fixes** → applied automatically (create dirs, add frontmatter, fix-index)
4. **Destructive actions** → confirm before: rename, move, delete
5. **Validation gate** → `lint.py doctor --json` after fixes, jq delta comparison
6. **State append** → `.h2t-lint-state.jsonl` (one line per run, used by maintenance delta)

---

## Maintenance Mode

Triggered when user answers "зрелый" at the gate.

1. Read last entry from `.h2t-lint-state.jsonl`
2. Run `lint.py audit`
3. Compare: show **only delta** (new findings since last run)
4. Apply safe-fixes automatically
5. Append new state to `.h2t-lint-state.jsonl`

No deep analysis, no GitHub issues, no plan file — just clean up accumulation.

---

## Delegation Model

| Layer | What it does | Tools |
|---|---|---|
| **Scripts** | Deterministic mechanical checks | lint.py doctor --json, jq |
| **Model** | Semantic analysis, meaningfulness, context | Reads git ls-files + references |
| **Validation** | Post-fix gate | lint.py doctor --json + jq delta |

Model never makes final calls on destructive actions. Scripts provide ground truth.
Model provides interpretation. Validation confirms state change.

---

## Validation Gate Detail

```bash
# Before fixes — capture state
lint.py doctor --json --root . > .h2t-lint-before.json

# safe-fixes applied by lint.py fix-safe + model-guided destructive actions

# After fixes — compare
lint.py doctor --json --root . > .h2t-lint-after.json

jq -n \
  --slurpfile before .h2t-lint-before.json \
  --slurpfile after .h2t-lint-after.json \
  '{
    fixed: ($before[0].findings | length) - ($after[0].findings | length),
    remaining: ($after[0].findings | length),
    new: [($after[0].findings[].id) - ($before[0].findings[].id)],
    pass: (($after[0].findings | length) < ($before[0].findings | length))
  }'
```

Result appended to `.h2t-lint-state.jsonl`:
```json
{"ts":"2026-06-06T14:00:00Z","mode":"full","findings_before":12,"findings_after":4,"fixed":8,"new":0,"pass":true}
```

---

## Scope

**In scope:**
- Rewrite of `SKILL.md` — new pipeline instructions
- Extension of `lint.py` — read `.h2t/docs-lint.yaml` exceptions, expose findings IDs for jq delta
- New `references/non-standard-resolution.md` — decision tree doc for model

**Out of scope:**
- lint.py rewrite — extend only
- Standards changes — ADD PROJECT TYPE outcome creates a PR proposal, doesn't auto-merge
- CI integration — future milestone
