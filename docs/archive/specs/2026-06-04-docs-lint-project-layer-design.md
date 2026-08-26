---
title: "docs-lint project-layer extension — design spec"
status: draft
date: 2026-06-04
milestone: v2.16
---

# docs-lint project-layer extension — Design Spec

## Goal

Extend docs-lint beyond docs/* to cover the full project: root structure hygiene, non-docs directories, gitignore, and agent instructions. One tool, two check layers. Self-improving via universal harvest loop.

## Problem

docs-lint covers only docs/**. Outside docs/, chaos accumulates undetected: unjustified root dirs, temp files not gitignored, misplaced artifacts, 25+ manual git mv commands per refactor, agent instructions with stale paths and guardrail gaps. This costs tokens and time on every session.

## Architecture

```
docs-lint doctor / plan / fix-safe / plan --apply
├── docs/* layer (existing)
│   ├── orphan detection
│   ├── naming conventions
│   ├── frontmatter checks
│   └── typed structure (project_types templates)
│
└── project/* layer (new)
    ├── root_structure     — every root item justified?
    ├── root_readmes       — README.md in each template root dir?
    ├── gitignore_hygiene  — temp patterns not gitignored?
    └── agent_instructions — .claude/* structural + LLM clarity
```

New CLI modes: `plan --save`, `plan --apply`, `harvest-review`.

## New Files

| File | Responsibility |
|------|---------------|
| `lib/docs/root_structure.py` | Root item validation: template allowlist + LLM judge + harvest write |
| `lib/docs/agent_instructions.py` | .claude/* audit: stale paths, naming, LLM clarity judge |
| `lib/docs/harvest.py` | Universal harvest read/write helpers |
| `lib/docs/plan_apply.py` | Plan file read/write, git mv/rm execution |

Modified:
- `lib/docs/config.py` — add `custom_root_dirs: []`, `project_checks: true`
- `skills/docs-lint/scripts/lint.py` — wire new checks into doctor/plan/fix-safe, add `plan --save`, `plan --apply`, `harvest-review` CLI modes

---

## Feature 1: Root Structure Validation

### Allowlist resolution

```
allowed = STANDARD_ALLOWLIST ∪ template.root_dirs ∪ custom_root_dirs
```

```python
STANDARD_ALLOWLIST = {
    ".git", ".gitignore", ".gitattributes", ".github",
    "README.md", "CLAUDE.md", "CHANGELOG.md",
    ".claude", "docs-lint-plan.yaml", "LICENSE",
    "pyproject.toml", "package.json", "Makefile",
}
```

`custom_root_dirs` declared in `.claude/rules/docs-lint.yaml` — explicit project exceptions, versioned.

### Check flow

For each item in repo root:
1. In allowlist → skip
2. Matches temp pattern (`*.tmp`, `session_*.txt`, `full_messages.txt`, `*.log`) → finding `type=temp_file, severity=warn, action=add_to_gitignore`
3. Unknown → LLM judge queue

### LLM judge (one call per audit, structured output)

Input: list of unknown items + project_type context.

```json
{"items": [
  {"name": "nimbalyst-local", "verdict": "project_specific", "confidence": 0.9,
   "rationale": "external tool directory, reasonable at root"},
  {"name": "full_messages.txt", "verdict": "delete", "confidence": 0.6,
   "rationale": "looks like a session dump, not a project artifact"}
]}
```

- `confidence >= 0.8` → automatic finding with recommendation
- `confidence < 0.8` → escalate to human: pause, show item + rationale, wait for `allow` / `delete` / `gitignore`
  - `allow` → saved to `custom_root_dirs` in docs-lint.yaml
  - `delete` / `gitignore` → added to plan file

### README presence check

For each dir in `template.root_dirs`: `(repo_root / dir / "README.md").exists()` — warn if missing.

---

## Feature 2: Gitignore Hygiene

Checks repo root for files matching known temp patterns that are NOT in `.gitignore`:

```python
TEMP_PATTERNS = ["*.tmp", "*.log", "session_*.txt", "full_messages.txt",
                 "cryo_*.txt", "*_analysis.txt", "*_summary.txt"]
```

Finding: `type=gitignore_hygiene, severity=info, message="N untracked temp files — add patterns to .gitignore"`.

fix-safe: appends missing patterns to `.gitignore`.

---

## Feature 3: `docs-lint plan --save` / `plan --apply`

### Plan file format

`.claude/docs-lint-plan.yaml` — human-editable, git-versioned:

```yaml
# docs-lint plan — 2026-06-04
# Edit before applying. Comment out lines to skip. 'action: delete' requires skip: false explicitly.

moves:
  - from: docs/product/brief.md
    to: docs/client/brief.md
  - from: pitch-deck.html
    to: deliverables/pitch-deck.html
  - from: session_analysis.txt
    action: delete
    skip: true          # must be set to false to execute

gitignore_additions:
  - "*.tmp"
  - "session_*.txt"
```

### CLI

```
docs-lint plan --save          # scan + generate plan file, print summary table
docs-lint plan --apply         # execute plan file (git mv / git rm one per call)
docs-lint plan --apply --dry-run  # print commands without executing
```

### Execution rules

- Each `git mv` / `git rm` in a separate commit → reversible point by point
- `action: delete` skipped by default (`skip: true`) — human must explicitly set `skip: false`
- After each operation: verify file moved/removed, log result
- Commit message: `chore(docs-lint): plan apply — {from} → {to}`

### Move source mapping

Priority order:
1. `moves:` field in docs-lint.yaml (explicit project override)
2. Template diff: actual path vs expected per `PROJECT_TYPES[template]`
3. Naming rule violations: files in `superpowers/plans/` without date prefix → propose move to correct name

---

## Feature 4: Agent Instructions Audit

### Deterministic checks (`lib/docs/agent_instructions.py`)

```
.claude/rules/*.md
├── naming: all files kebab-case? (no CAPS, no spaces)
├── required: documentation.md, linting.md present?
└── stale paths: all paths mentioned in file content exist on fs?

CLAUDE.md
├── stale paths: regex scan for path-like strings → existence check
└── required sections: "Key Commands" | "Commands" present?
```

Stale path regex: `(docs/[\w/-]+|C:/[\w/.-]+|\.\/[\w/.-]+)`

### LLM clarity judge (one call for all `.claude/*` files)

Three bounded dimensions — structured output, one line per finding:

**1. MODULARIZATION**
- CLAUDE.md > 150 lines? → identify sections that are candidates for extraction to `rules/`
- Output: list of candidate section names (if any)

**2. GUARDRAIL GAPS**
Check presence of standard guardrails against known checklist:
- file ops policy (mv/rm requires confirmation)
- git conventions (commit format, no force-push)
- secrets handling (no commit)
- command safety (no `&&` chaining)
- Output: list of missing standard guardrails

**3. PROGRESSIVE DISCLOSURE**
- CLAUDE.md → rules/ → references/ hierarchy respected?
- Details in CLAUDE.md that belong in rules/?
- References to non-existent files?
- Output: score 1–3 + one-line diagnosis

Finding threshold: score < 3 on any dimension → `severity=warn`. Harvest entry written regardless.

---

## Feature 5: Universal Harvest Loop

Every finding across all checks → optional harvest entry in `harvest.jsonl`:

```json
{"type": "false_positive", "check": "orphan", "template": "client_project",
 "finding_message": "...", "context": "...", "severity": "high",
 "date": "2026-06-04", "project": "rejuve"}

{"type": "unknown_root_item", "check": "root_structure", "name": "nimbalyst-local",
 "verdict": "project_specific", "confidence": 0.9, "human_decision": "allow",
 "project_type": "client_project", "date": "2026-06-04"}

{"type": "guardrail_gap", "check": "agent_instructions", "gap": "secrets handling",
 "file": "CLAUDE.md", "date": "2026-06-04"}
```

Machine-detectable cases written automatically. Subjective observations written by agent during run.

### `docs-lint harvest-review` command

Triggered manually after N runs:

1. Reads all `harvest.jsonl` files across projects (configurable glob)
2. Groups by `(type, check, pattern)` — finds recurring observations (≥3 occurrences)
3. Proposes concrete changes:
   - `unknown_root_item` recurring with `verdict=project_specific` → add to `STANDARD_ALLOWLIST`
   - `false_positive` recurring for same check → add exception rule
   - `guardrail_gap` recurring → generate rule stub for human to fill
4. Outputs proposed changes as diff-style review for human approval
5. Human approves → changes applied to `project_types.py` / `lint.py` / `config.py`

---

## Config Schema Update

```yaml
# .claude/rules/docs-lint.yaml
schema: h2t_docs_lint_config/v0.2

template: client_project
exclude_dirs:
  - docs/superpowers
naming_exceptions:
  - docs/superpowers/plans/docs-lint-skill-log.md
custom_root_dirs:       # NEW: justified project-specific root items
  - nimbalyst-local
project_checks: true    # NEW: enable project/* layer (default: true)
```

---

## Implementation Phases (Codex review 2026-06-04)

Codex review flagged scope overload — split into phases to ship safely:

| Phase | Scope | Notes |
|-------|-------|-------|
| **v1 (this plan)** | Deterministic project-layer findings only — no LLM, no apply, no commits | Safe to ship |
| **v2** | `plan --save` — generate plan file, no execution | Read-only, reviewable |
| **v3** | `plan --apply` — modify worktree only, no auto-commit; `--commit` explicit flag | Needs dirty-worktree guard |
| **v4** | LLM advisory mode — disabled by default, `--llm` opt-in; includes agent instructions clarity | Needs provider/timeout/fallback spec |
| **v5** | Harvest loop — append-only telemetry; `harvest-review` after real data accumulates | Do NOT auto-apply rules |

## What Is NOT in v1

- `plan --apply` / `plan --save` — deferred to v2/v3
- LLM judge for unknown root items — deferred to v4; v1 shows unknown items as findings only
- Agent instructions clarity scoring — deferred to v4
- Auto-commit behavior — v3+ only, behind explicit `--commit` flag
- Harvest auto-application to project_types.py / config.py — v5 only
- Cross-repo batch audit (`--tier product`) — existing h2t-core:project-audit owns this
- CI integration / pre-commit hook

## Deferred Design Decisions (preserve context)

Issues flagged by Codex review that must be resolved before v3+:

**plan --apply (v3):**
- dirty-worktree policy: check `git status --porcelain` before any mutation; abort or `--force` flag
- plan file path: pick ONE — recommend `docs-lint-plan.yaml` at repo root (in STANDARD_ALLOWLIST, not .claude/)
- Reject: absolute paths, `..`, symlinks escaping repo, paths under `.git/`
- Delete actions: require explicit `--allow-delete` flag, never via fix-safe
- Missing error handling to spec before implementing: duplicate destinations, source-not-exists, case-only rename on Windows/macOS, commit hooks, GPG signing, no git identity

**LLM judge (v4):**
- Specify: provider (Anthropic Claude haiku for cost), model, timeout (10s), offline fallback (skip + warn)
- Confidence threshold redesign: 0.8 is fake precision — use structured verdict without numeric confidence
- Interactive gate: `--interactive` flag required for human escalation; noninteractive default = finding only, no pause
- Privacy: auditing .claude/* may read sensitive policy — explicit opt-in required

**STANDARD_ALLOWLIST (v1 — fix now):**
Current list is too small. Before implementing, extend with:
```python
# common files
".editorconfig", ".prettierrc", ".prettierrc.json", ".eslintrc.json",
"tsconfig.json", "tsconfig.base.json", "pnpm-lock.yaml", "uv.lock",
"requirements.txt", "setup.py", "setup.cfg", "Cargo.toml", "go.mod",
"Dockerfile", "docker-compose.yml", ".env.example",
# common dirs
"src", "tests", "test", "scripts", "assets", "dist", "build",
"node_modules", ".venv", ".pytest_cache", "__pycache__",
```
Allowlist must distinguish files vs dirs (currently mixes both).

**project_checks default (v1 — fix now):**
Default must be `false`, not `true`. Opt-in per project via `project_checks: true` in docs-lint.yaml.
Rationale: changes behavior for all existing projects; validate on opt-in projects first.

**harvest.jsonl location (v5):**
- Must be per-project (in docs/superpowers/ of audited repo, not shared)
- Cross-project harvest-review needs explicit glob config, privacy boundary
- Provenance required: project_id, tool_version, config_version, template_version, human_confirmed

**Stale path regex (v4):**
Current regex misses backslashes, escaped paths, URLs, env-var paths.
Replace with: extract markdown link targets + inline code spans; check each against fs.
Cannot distinguish examples from required paths — needs heuristic (links in "Required:" sections only?).

---

## Testing Strategy

- Unit tests for each new lib module (root_structure, agent_instructions, harvest, plan_apply)
- Integration tests: `_collect_all_findings` returns project-layer findings
- LLM judge: mock structured output in tests, test routing logic (confidence threshold)
- plan --apply: tmp_path git repo, verify git mv executed and committed
- harvest-review: fixture harvest.jsonl with N>3 recurring pattern → verify proposal output
