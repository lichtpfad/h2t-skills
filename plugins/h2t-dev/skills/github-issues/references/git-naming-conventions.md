---
title: Git Naming Conventions
date: 2026-04-13
---
# Git Naming Conventions

Standards for branches, commits, tags, issues, milestones, and labels across all H2T platform repositories.

## Branch Naming

**Format:** `{type}/{issue}-{slug}`

| Type | Purpose | Example |
| --- | --- | --- |
| `feat/` | New functionality | `feat/42-batch-export` |
| `fix/` | Bug fix | `fix/87-srt-timestamp-drift` |
| `refactor/` | Code restructuring | `refactor/103-split-pipeline` |
| `docs/` | Documentation only | `docs/api-reference` |
| `chore/` | CI, deps, config | `chore/update-deps` |

**Rules:**
- Lowercase, hyphens only (not underscores)
- Issue number ties branch to context
- `main` -- protected, always deployable
- For trivial changes without issue: `fix/typo-in-config` (no number)
- Close branch after merge

**Deprecated patterns (do not use):**
- `feature/` (full word) -- use `feat/`
- `codex/feat/` (nested prefix) -- use `feat/`

## Commit Messages

**Format:** `<type>: <description>`

**Types:** `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `perf`

**Rules:**
- Imperative mood in description: "Add", "Fix", "Refactor" (not "Added", "Fixes")
- Multi-line body for context when needed
- Co-author line for AI-assisted commits: `Co-Authored-By: Claude <noreply@anthropic.com>`

**Examples:**
- `feat: add batch export for SRT files`
- `fix: correct timestamp drift in SRT output`
- `docs: archive M8 documents`
- `chore: update dependencies`

## Tag / Release Naming

**Format:** `v{MAJOR}.{MINOR}.{PATCH}`

**Rules:**
- Semver: `v0.1.0`, `v0.2.0`, `v1.0.0`
- Patch (`x.x.N`): iterations and fixes before live confirmation
- Minor (`x.N.0`): only after live confirmation
- Tags on `main` branch only
- Create GitHub Release with changelog for each tag

## Issue Titles

**Format:** `{repo-short}: verb noun` or `{repo-short}({scope}): verb noun`

The repo prefix is **required** — without it, issues are unidentifiable in the unified cross-repo Project dashboard.

| Pattern | Example | When |
| --- | --- | --- |
| `{repo-short}: [MN] verb noun` | `transcription: [M3] Fix SRT timestamp drift` | **Default** (issue in milestone) |
| `{repo-short}({scope}): [MN] verb noun` | `ai(houdini): [M14] Add node layout` | Multi-module + milestone |
| `{repo-short}: verb noun` | `graphs: Fix typo in README` | Backlog (no milestone) |

**Repo short names** (drop `h2t-` prefix):

| Repo | Short | Repo | Short |
| --- | --- | --- | --- |
| h2t-ai | `ai` | h2t-landings | `landings` |
| h2t-business | `business` | h2t-skills | `skills` |
| h2t-client | `client` | h2t-snap | `snap` |
| h2t-content | `content` | h2t-staging | `staging` |
| h2t-dcc | `dcc` | h2t-tools | `tools` |
| h2t-evals | `evals` | h2t-transcription | `transcription` |
| h2t-factory | `factory` | h2t-vision | `vision` |
| h2t-graphs | `graphs` | h2t-voice | `voice` |

**Non-h2t repos:** use full name (`depthkit:`, `creative-thinking:`, `SpecDesigner:`)

**Rules:**
- Imperative mood: "Add", "Fix", "Refactor" (not "Added", "Fixes")
- Max 70 characters (including prefix)
- No type prefixes (bug/feature) -- use labels instead
- Scope (optional) = module/area within repo

**Deprecated patterns (do not use):**
- `FR: description` -- use `feature` label instead
- `[Docs] description` -- use `docs` label instead
- `Master: description` -- use epics/milestones instead
- Bare titles without repo prefix -- always include `{repo-short}:`

## Milestone Naming

**Format:** `M{N} Short Name`

| Pattern | Example | Status |
| --- | --- | --- |
| `M{N} Short Name` | `M8 Ground Truth` | **Standard** |
| `v0.X -- Title` | `v0.8 -- Template Enrichment` | Acceptable for libraries with public API |

**Rules:**
- Sequential numbering: M1, M2, M3...
- No gaps -- if milestone is cancelled, mark as closed with note
- Due date required
- 5-15 issues per milestone
- Close milestone when done + write report in `docs/reports/mN-name-report.md`

**Deprecated patterns (do not use):**
- `MS-A`, `MS-B` (letter-based) -- convert to `M{N}`
- Bare `Studio` without number -- add number prefix
- Mixed `M9` + `M11` with gap -- fill gaps or renumber

## Labels

**Canonical source:** `C:/dev/docs/standards/labels.json` (schema `namespaced-v1`).
Sync to all repos via `/docs-sync-labels --apply` (additive — never deletes custom labels).

**Schema:** namespaced, lowercase everywhere (`priority:p1`, never `priority:P1`).

### Namespaces

| Namespace | Required on issue | Purpose |
| --- | --- | --- |
| `type:*` | yes | bug / feature / enhancement / refactor / docs / chore |
| `priority:*` | yes | p0 / p1 / p2 / p3 |
| `domain:*` | yes | skills / infra / docs / content / research |
| `phase:*` | optional | design / implementation / review |
| `status:*` | optional | triage / blocked / wontfix / superseded |

### Rules

- Always lowercase. `priority:p0`, not `priority:P0`.
- `status:*` is a workflow label (not a duplicate of GitHub's native open/closed state). Use only `status:wontfix` / `status:superseded` / `status:blocked` / `status:triage`.
- Platform taxonomy (if needed later) goes under a separate `platform:*` namespace — do not overload `domain:*`.
- Before inventing a new label, add it to canonical `labels.json`, then run `/docs-sync-labels --apply`.

### Legacy

Flat labels (`bug`, `P0-critical`, `D1-methodology`) exist on GitHub from earlier phases. They are **not** in canonical anymore. Migration of old issues is manual and out of scope for the sync skill.
