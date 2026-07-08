---
name: h2t-dev:docs-lint
description: >-
  Audit and maintain documentation/structure health in h2t-stack repos.
  Full pipeline: sniff → gate → analyze → plan → issues → fixes → validate.
  Scoped to repos using Claude Code + h2t standards.
compatibility: "Claude Code"
metadata:
  author: lichtpfad
  version: 2.0.0
---

# docs-lint v2

Scope: h2t-stack repos (Claude Code, `.claude/rules/`, `docs/superpowers/`, h2t standards).

## Variables

```bash
H2T_PYTHON="${H2T_PYTHON:-$HOME/.h2t/venv/Scripts/python.exe}"
[ ! -f "$H2T_PYTHON" ] && H2T_PYTHON="$HOME/.h2t/venv/bin/python"
LINT="${CLAUDE_PLUGIN_ROOT}/skills/docs-lint/scripts/lint.py"
ROOT="${1:-.}"
DRY_RUN="${2:-}"   # pass "--dry-run" to skip issue creation and commits
```

## Phase 1: Sniff (automatic)

Run in parallel:

```bash
git -C "$ROOT" ls-files --cached --others --exclude-standard 2>/dev/null | head -500
"$H2T_PYTHON" "$LINT" doctor --json --root "$ROOT" 2>/dev/null
cat "$ROOT/CLAUDE.md" 2>/dev/null | head -80
cat "$ROOT/.h2t/docs-lint.yaml" 2>/dev/null
ls "$ROOT/.claude/rules/" 2>/dev/null
```

Also read first 30 lines of `pyproject.toml` or `package.json` if present.

If a reference is missing from `references/`, skip that dimension and log:
`[dim-N] reference missing — skipped`.

**Autodetect project_type** (first match):
1. `.h2t/docs-lint.yaml` → `project_type`
2. `CLAUDE.md` first 50 lines — keyword scan
3. `pyproject.toml` + `plugins/` → `plugin-pack`
4. `pyproject.toml` only → `standalone-tool`
5. `package.json` → `frontend-tool`
6. Default → `unknown`

Output exactly 3 lines:
```
Тип: <project_type>, <organic-grow|structured|greenfield>
Состояние: <1-line summary>
Сигнал: <порядок|хаос|зрелый> → рекомендую (<stage>)
```

## Phase 2: Gate — ONE question

```
Стадия проекта:
(1) cleanup   — organic-grow, нужен полный аудит
(2) mature    — стабильная структура, maintenance lint
(3) greenfield — новый репо, setup-ориентированный аудит
(4) archived  — read-only, только анализ
```

---

## Branch: Maintenance (stage 2)

```bash
# Read last valid state (schema=1, handle corrupt lines)
LAST_STATE=$("$H2T_PYTHON" - <<'PYEOF'
import sys, json
from pathlib import Path
state_file = Path("$ROOT/.h2t/lint-state.jsonl")
if not state_file.exists():
    sys.exit(0)
for line in reversed(state_file.read_text().splitlines()):
    try:
        obj = json.loads(line)
        if obj.get("schema") == 1:
            print(json.dumps(obj))
            sys.exit(0)
    except Exception:
        pass
PYEOF
)

# If no valid state → fall back to full audit
if [ -z "$LAST_STATE" ]; then
  echo "No previous state — running full audit instead."
  # → continue as stage (1) cleanup
fi

# Capture current finding IDs via doctor --json
"$H2T_PYTHON" "$LINT" doctor --json --root "$ROOT" > /tmp/lint-current.json 2>/dev/null
CURRENT_IDS=$(jq '[.findings[].id]' /tmp/lint-current.json 2>/dev/null || echo "[]")
LAST_IDS=$(echo "$LAST_STATE" | jq '.finding_ids // []' 2>/dev/null || echo "[]")

# Delta = IDs in current but not in last
NEW_IDS=$(jq -n --argjson cur "$CURRENT_IDS" --argjson last "$LAST_IDS" '$cur - $last')

# Apply safe fixes automatically
"$H2T_PYTHON" "$LINT" fix-safe --root "$ROOT"

# Show only delta
jq -r '.[]' <<< "$NEW_IDS" | while read id; do echo "  [NEW] $id"; done
```

Append state:
```bash
mkdir -p "$ROOT/.h2t"
AFTER_IDS=$(jq '[.findings[].id]' /tmp/lint-current.json 2>/dev/null || echo "[]")
AFTER_COUNT=$(jq '.findings | length' /tmp/lint-current.json 2>/dev/null || echo 0)
jq -n \
  --arg ts "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --argjson after_count "$AFTER_COUNT" \
  --argjson new_ids "$NEW_IDS" \
  --argjson after_ids "$AFTER_IDS" \
  '{schema:1,ts:$ts,mode:"maintenance",findings_after:$after_count,new:$new_ids,finding_ids:$after_ids}' \
  >> "$ROOT/.h2t/lint-state.jsonl"
rm -f /tmp/lint-current.json
```

---

## Branch: Full Audit (stages 1, 3, 4)

### Step A: Pre-flight

```bash
# Dirty worktree — warn on ANY uncommitted changes
DIRTY=$(git -C "$ROOT" status --porcelain 2>/dev/null | grep -v '^??' | head -1)
if [ -n "$DIRTY" ]; then
  BRANCH=$(git -C "$ROOT" branch --show-current 2>/dev/null)
  echo "WARNING: uncommitted changes on branch '$BRANCH'. Continue? (y/n)"
  # Wait for user input — do not proceed if 'n'
fi

# gh auth (skip issue creation if fails)
GH_AUTH_OK=0
gh auth status 2>/dev/null && GH_AUTH_OK=1 || echo "gh auth failed — issues will be skipped"

# Duplicate issue check
[ "$GH_AUTH_OK" = "1" ] && \
  gh issue list --label "type:docs-lint" --json number,title --limit 20 2>/dev/null || true
```

Dry-run mode (`$DRY_RUN` = `--dry-run`): skip commits and issue creation throughout.

### Step B: Capture before-state

```bash
mkdir -p "$ROOT/.h2t"
"$H2T_PYTHON" "$LINT" doctor --json --root "$ROOT" > "$ROOT/.h2t/lint-before.json" 2>/dev/null
BEFORE_COUNT=$(jq '.findings | length' "$ROOT/.h2t/lint-before.json" 2>/dev/null || echo 0)
```

### Step C: Multi-angle analysis

Load references on demand (skip with log if missing):
- `${CLAUDE_PLUGIN_ROOT}/skills/docs-lint/references/documentation-structure.md` — dims 1,2,6
- `${CLAUDE_PLUGIN_ROOT}/skills/docs-lint/references/code-organization.md` — dims 3,4
- `${CLAUDE_PLUGIN_ROOT}/skills/docs-lint/references/non-standard-resolution.md` — dim 8

| # | Dimension | Source |
|---|---|---|
| 1 | Docs structure | doctor --json type=orphan,structure + documentation-structure.md |
| 2 | Naming | type=naming + naming-conventions.md |
| 3 | Code organization | git ls-files + code-organization.md |
| 4 | Data storage | git ls-files root dirs |
| 5 | Agent accessibility | CLAUDE.md + .claude/rules/ |
| 6 | Frontmatter | type=frontmatter |
| 7 | Root hygiene | type=structure (root count) |
| 8 | Non-standard dirs | git ls-files vs template + non-standard-resolution.md |

Stage 4 (archived): collect findings, mark all destructive suggestions `[ANALYSIS ONLY]`.

### Step D: Report

```
## docs-lint audit — {project} — {date}

### Critical
- [dim-N] <path>: <message>

### Important
- [dim-N] <path>: <message>

### Low
- [dim-N] <path>: <message>

### Config warnings
- [stale-exception] ...
- [orphan-exception] ...
```

### Step E: Write plan file + commit

```bash
PLAN_FILE="$ROOT/docs/superpowers/plans/$(date +%Y-%m-%d)-docs-audit.md"
# Write findings to $PLAN_FILE

if [ "$DRY_RUN" != "--dry-run" ]; then
  git -C "$ROOT" add "$PLAN_FILE"
  git -C "$ROOT" commit -m "docs: docs-lint audit $(date +%Y-%m-%d)"
fi
```

### Step F: Create GitHub issues

Only if GH_AUTH_OK=1 AND stage ≠ 4 AND DRY_RUN is empty.

```bash
# Check for existing issue first
EXISTING=$(gh issue list --label "type:docs-lint" \
  --search "$ISSUE_TITLE" --json number,title 2>/dev/null | jq '.[0].number // empty')

if [ -n "$EXISTING" ]; then
  echo "Existing issue #$EXISTING. Update or create new? (u/n)"
else
  # Create labels if missing
  gh label create "type:docs-lint" --color "0075ca" \
    --description "docs-lint audit finding" 2>/dev/null || true
  gh label create "priority:p0" --color "b60205" 2>/dev/null || true
  gh label create "priority:p1" --color "d93f0b" 2>/dev/null || true

  # One issue per dimension with findings
  gh issue create \
    --title "$ISSUE_TITLE" \
    --body "$ISSUE_BODY" \
    --label "type:docs-lint" \
    --label "$PRIORITY_LABEL"
fi
```

Dry-run: print issue titles/bodies to stdout instead.

### Step G: Apply fixes

Safe (automatic):
```bash
"$H2T_PYTHON" "$LINT" fix-safe --root "$ROOT"
"$H2T_PYTHON" "$LINT" fix-index --root "$ROOT" --apply
```

Destructive (confirm each before running):
- rename: show `git mv <old> <new>` and wait for "y"
- move: run MOVE pre-checks from non-standard-resolution.md, then confirm
- delete: show `git rm <path>` and wait for "y"

Stage 4: skip all fixes.

### Step H: Validation gate

```bash
"$H2T_PYTHON" "$LINT" doctor --json --root "$ROOT" > "$ROOT/.h2t/lint-after.json" 2>/dev/null

DELTA=$(jq -n \
  --slurpfile before "$ROOT/.h2t/lint-before.json" \
  --slurpfile after "$ROOT/.h2t/lint-after.json" \
  '($before[0].findings | map(.id)) as $b_ids |
   ($after[0].findings | map(.id)) as $a_ids |
   {
     fixed:     ($b_ids - $a_ids | length),
     remaining: ($after[0].findings | length),
     new:       ($a_ids - $b_ids),
     pass:      (($a_ids - $b_ids | length) == 0)
   }')

FIXED=$(echo "$DELTA" | jq '.fixed')
AFTER_COUNT=$(jq '.findings | length' "$ROOT/.h2t/lint-after.json")
NEW_IDS=$(echo "$DELTA" | jq '.new')
PASS=$(echo "$DELTA" | jq '.pass')
AFTER_IDS=$(jq '[.findings[].id]' "$ROOT/.h2t/lint-after.json")
PROJECT_TYPE=$(jq -r '(.project_type // .template // "unknown")' \
  "$ROOT/.h2t/docs-lint.yaml" 2>/dev/null || echo "unknown")

echo "findings_before: $BEFORE_COUNT  findings_after: $AFTER_COUNT  fixed: $FIXED  new: $NEW_IDS  $([ "$PASS" = "true" ] && echo PASS || echo FAIL)"

rm -f "$ROOT/.h2t/lint-before.json" "$ROOT/.h2t/lint-after.json"
```

### Step I: Append state

```bash
jq -n \
  --arg ts "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --arg pt "$PROJECT_TYPE" \
  --argjson before_count "$BEFORE_COUNT" \
  --argjson after_count "$AFTER_COUNT" \
  --argjson fixed "$FIXED" \
  --argjson new_ids "$NEW_IDS" \
  --argjson pass_val "$PASS" \
  --argjson after_ids "$AFTER_IDS" \
  '{schema:1,ts:$ts,mode:"full",project_type:$pt,
    findings_before:$before_count,findings_after:$after_count,
    fixed:$fixed,new:$new_ids,pass:$pass_val,finding_ids:$after_ids}' \
  >> "$ROOT/.h2t/lint-state.jsonl"
```

---

## Creating plan/spec/adr files — `new`

Generate a correctly-named file with required frontmatter (fields sourced from
`FRONTMATTER_RULES`, so the output never drifts from the validator). Prefer this
over hand-writing — hand-written files trigger frontmatter findings.

```bash
"$H2T_PYTHON" "$LINT" new plan <slug> --root . [--milestone M3] [--title "..."]
"$H2T_PYTHON" "$LINT" new spec <slug> --root . [--milestone M3]
"$H2T_PYTHON" "$LINT" new adr  <slug> --root .
```

- `plan`/`spec` → `docs/superpowers/{plans,specs}/YYYY-MM-DD-<slug>.md` (date = today)
- `adr` → `docs/adr/NNNN-<slug>.md` (next 4-digit number, `status: proposed`)
- Never overwrites an existing file (exit 1). Reactive backfill for legacy files:
  `fix-safe --only=frontmatter`.

## Legacy sub-commands (still work)

```bash
"$H2T_PYTHON" "$LINT" audit --root .
"$H2T_PYTHON" "$LINT" plan --root .
"$H2T_PYTHON" "$LINT" fix-safe --root .
"$H2T_PYTHON" "$LINT" fix-index --root .
"$H2T_PYTHON" "$LINT" doctor --json --root .
```

## References

Load on demand:
- `${CLAUDE_PLUGIN_ROOT}/skills/docs-lint/references/documentation-structure.md`
- `${CLAUDE_PLUGIN_ROOT}/skills/docs-lint/references/naming-conventions.md`
- `${CLAUDE_PLUGIN_ROOT}/skills/docs-lint/references/code-organization.md`
- `${CLAUDE_PLUGIN_ROOT}/skills/docs-lint/references/non-standard-resolution.md`
