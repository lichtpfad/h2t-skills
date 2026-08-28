---
title: "docs-lint v2: Full Audit + Maintenance Pipeline"
status: approved
owner: stanislav
date: 2026-06-06
revised: 2026-06-06
milestone: ""
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

## Scope

**This skill is scoped to h2t-stack repos** — projects using Claude Code, `.claude/rules/`,
`docs/superpowers/`, and h2t standards. It is not a general-purpose docs linter.

**In scope:**
- Rewrite of `SKILL.md` — new pipeline instructions
- Extension of `lint.py` — stable finding IDs, `.h2t/docs-lint.yaml` exceptions, per-dimension limits
- New `references/non-standard-resolution.md` — decision tree doc for model

**Out of scope:**
- lint.py rewrite from scratch — extend only; existing checks stay unchanged
- Standards changes — ADD PROJECT TYPE outcome creates a PR proposal, doesn't auto-merge
- CI integration — future milestone
- Non-Claude-Code / non-h2t repos

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
  Stage: (1) cleanup  (2) mature  (3) greenfield  (4) archived/read-only
       │
      / \
     /   \
    ▼     ▼
[Full   [Maintenance]
Audit]   lint.py audit
         safe-fixes авто
         show delta vs last .h2t/lint-state.jsonl
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
[Pre-flight checks]      — before any writes or issues
    │
    ▼
[Create GitHub issues]   — critical + important only
    │
    ▼
[Apply safe-fixes auto, destructive with confirm]
    │
    ▼
[Validation Gate]        — script, not model
    │
    ▼
[Append .h2t/lint-state.jsonl]
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

**Project type autodetect precedence** (first match wins):
1. `.h2t/docs-lint.yaml` `project_type` field — explicit override
2. `CLAUDE.md` — look for `type:` or project description keywords
3. `pyproject.toml` / `package.json` — stack type
4. Directory structure heuristics (presence of `plugins/`, `src/`, `hta/`, etc.)
5. Default: `unknown`

**Lifecycle stage gate options** — model suggests, user confirms one:
- `(1) cleanup` — organic-grow, structural chaos, needs full audit
- `(2) mature` — stable structure, maintenance lint only
- `(3) greenfield` — new repo, minimal content, setup-focused audit
- `(4) archived` — read-only, skip destructive suggestions entirely

Model outputs exactly 3 lines before the gate question:
```
Тип: Python-инструмент, organic-grow
Состояние: docs частичные, code layout нестандартный, agent instructions отсутствуют
Сигнал: хаос → рекомендую (1) cleanup
```

---

## Audit Dimensions (Full mode)

Model loads references from `references/` on demand. Per-dimension limits: max 50
findings per dimension, skip binary/vendor/generated paths (`.venv/`, `node_modules/`,
`__pycache__/`, `*.pyc`, `dist/`, `build/`). Timeout per dimension: 30s script, no
model timeout (model reads pre-fetched data).

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

If references are missing from `references/`, the model skips that dimension and logs:
`[dim-N] reference missing — skipped`.

---

## Non-Standard Dirs/Files (Dimension 8)

Everything not in the standard project template for the detected project type is evaluated:

```
Found non-standard path
        │
        ▼
   Is it needed?
   (git activity last 30d + content scan)
       / \
     Yes   No → DELETE (confirm, archived stage: skip)
     │
     ▼
  Covered by standard?
      / \
    Yes   No
    │          │
    ▼          ▼
 Misplaced   Project-specific?
 → MOVE           / \
   (confirm +    Yes   No → repeats across h2t repos?
    dep check)   │              │
                 ▼              ▼
            EXCEPTION      ADD PROJECT TYPE
            (.h2t/         (PR proposal only,
            docs-lint.yaml) not auto-merged)
```

**MOVE pre-checks before confirming:**
- `grep -r "path" .` import/reference search (skip if > 1000 results)
- Check if file is generated (in .gitignore, build output)
- Check for symlinks, submodules

**EXCEPTION format** in `.h2t/docs-lint.yaml`:

```yaml
# .h2t/docs-lint.yaml
project_type: td-tool   # override if autodetect wrong

exceptions:
  - path: benchmark_results/
    reason: "TD performance operational data, updated live"
    type: operational_data
    reviewed: 2026-06-06   # updated each time exception is confirmed
  - path: setlists/
    reason: "performance setlists archive"
    type: archive
    reviewed: 2026-06-06
```

lint.py reads `.h2t/docs-lint.yaml` and skips documented exceptions. Exceptions without
`reviewed` field within last 90 days emit a `[P2] stale exception` warning. Exceptions
whose `path` no longer exists emit `[P1] orphan exception — remove from config`.

---

## Pre-flight Checks (before any writes)

Before writing plan file, creating issues, or applying fixes:

```bash
# 1. Dirty worktree check
git status --porcelain | grep -v '^??' | head -1
# If non-empty: warn "Uncommitted changes detected — plan file will be committed
# alongside existing changes. Continue? (y/n)"

# 2. gh auth check (only if GitHub issues requested)
gh auth status 2>/dev/null || echo "GH_AUTH_FAILED"
# If failed: skip GitHub issues, note in report

# 3. Branch check
git branch --show-current
# If main/master: warn "About to commit to main. Continue? (y/n)"

# 4. Duplicate issue check (only if GH auth ok)
gh issue list --label "type:docs-lint" --json number,title --limit 20 2>/dev/null
# If similar title found: show existing issue, ask "Update existing or create new?"
```

---

## GitHub Issues

Created for `critical` and `important` findings only. One issue per dimension (grouped).

**Label spec:**
- `type:docs-lint` — always applied (created if missing: `gh label create "type:docs-lint" --color "0075ca"`)
- `priority:p0` for critical, `priority:p1` for important
- Standard h2t labels from `docs/standards/labels.json` — if label missing, create it

**Issue title format:** `{repo-short}: [docs-lint] {dimension} — {N} findings`

**Dry-run mode:** if `--dry-run` flag passed to skill, print issues to stdout instead
of creating them.

---

## Safe Fixes — Invariants

Applied automatically (no confirmation needed):

| Fix | Idempotency rule |
|---|---|
| Create missing dirs | `mkdir -p` — no-op if exists |
| Add frontmatter | Only if file has no `---` block at line 1; never overwrites existing |
| fix-index rebuild | Only touches content between `<!-- h2t-index-start -->` markers |

**Not safe** (always require confirmation): rename, move, delete, rewrite README outside markers.

---

## Validation Gate

lint.py exposes stable finding IDs in `doctor --json` output:
```json
{"findings": [{"id": "orphan:docs/plans/foo.md", "severity": "important", ...}]}
```

IDs are `{check_type}:{path}` — deterministic, stable across runs.

```bash
# Before fixes
lint.py doctor --json --root . > .h2t/lint-before.json

# safe-fixes applied by lint.py fix-safe + model-guided destructive actions

# After fixes — jq delta using stable IDs
jq -n \
  --slurpfile before .h2t/lint-before.json \
  --slurpfile after .h2t/lint-after.json \
  '($before[0].findings | map(.id)) as $b_ids |
   ($after[0].findings | map(.id)) as $a_ids |
   {
     fixed:     ($b_ids - $a_ids | length),
     remaining: ($after[0].findings | length),
     new:       ($a_ids - $b_ids),
     pass:      (($a_ids - $b_ids | length) == 0)
   }'
```

`pass: true` requires zero new findings. Severity regressions (same count, different
severity) are surfaced via `new` list — gate fails if any `critical` IDs appear in `new`.

Temp files `.h2t/lint-before.json` and `.h2t/lint-after.json` are deleted after append.

---

## State File

Location: `.h2t/lint-state.jsonl` (consistent with `.h2t/docs-lint.yaml` namespace).

**First-run behavior:** if file missing, maintenance mode falls back to full audit
with a note: `No previous state found — running full audit instead`.

**Schema versioning:** each line includes `"schema": 1`. Reader ignores lines with
unknown schema version.

**Corruption handling:** if last line is not valid JSON, skip it and use the
previous valid line. If all lines corrupt, fall back to full audit.

```json
{"schema":1,"ts":"2026-06-06T14:00:00Z","mode":"full","project_type":"td-tool","findings_before":12,"findings_after":4,"fixed":8,"new":[],"pass":true}
```

---

## Maintenance Mode

Triggered by stage `(2) mature`.

1. Read last valid entry from `.h2t/lint-state.jsonl` (schema=1, handle corrupt/missing)
2. Run `lint.py audit --root .`
3. Compare finding IDs: show **only delta** (new IDs not in last state)
4. Apply safe-fixes automatically (idempotent)
5. Append new state entry to `.h2t/lint-state.jsonl`

No deep analysis, no GitHub issues, no plan file.

---

## Delegation Model

| Layer | Responsibility | Tools |
|---|---|---|
| **Scripts** | Deterministic mechanical checks, stable finding IDs | `lint.py doctor --json` |
| **Model** | Semantic analysis: meaningfulness, context, staleness | git ls-files + references |
| **Validation** | Post-fix state comparison | `lint.py doctor --json` + `jq` |

Scripts are ground truth for **mechanical** checks (orphan, naming, frontmatter).
Model is ground truth for **semantic** checks (non-standard dirs, CLAUDE.md staleness,
agent accessibility quality). The two domains don't overlap.

Model never approves destructive actions unilaterally. Pre-flight gates run before
any writes. Validation gate confirms net improvement.

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
findings_before: 12  findings_after: 4  fixed: 8  new: []  PASS
```
