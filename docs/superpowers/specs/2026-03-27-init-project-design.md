# h2t:init-project — Design Spec

**Goal:** Zero-wizard skill that registers any directory as a project in the h2t ecosystem. Auto-detects everything possible, confirms with user, applies deterministically.

**Principle:** PreToolUse hook gathers context → LLM confirms with user → Bash applies. LLM does no detection, no YAML writing, no formatting.

---

## Architecture

```
PreToolUse hook → detect_project.py --cwd X → INIT_DATA: {json}
SKILL.md        → show confirm_message verbatim → wait for user
Bash            → apply_registration.py --params... → writes YAML, outputs result
```

Three scripts, one SKILL.md. All intelligence in scripts, LLM is just the confirm UI.

---

## Phase 1: Detection (`detect_project.py`)

Runs in PreToolUse hook. Receives `--cwd`. Returns JSON to stdout.

### Detection logic

**Project type:**
- Has `.git/` + remote → `git`
- Has `.git/` no remote → `git-local`
- No `.git/` → `directory`

**GitHub:**
- If git, parse remote for `owner/repo`
- Verify with `gh repo view owner/repo` (existence check)

**Stack:**
- Reuse existing `gather.stack.detect_stack()` → python/js/rust/go/none

**Domain (from path patterns):**

| Pattern | Domain | Confidence |
|---------|--------|------------|
| `C:/dev/h2t-*`, `C:/dev/hou2touch*` | hou2touch | high |
| `C:/dev/crypto-*` | crypto | high |
| `E:/DROPBOX/.../HOU2TOUCH/` | hou2touch | high |
| `C:/dev/*` | dev | medium |
| `~/Projects/DOR`, `~/Projects/newsengine` | personal-os | high |
| `~/Projects/crypto-*` | crypto | high |
| Art-related extensions (.toe, .hip) | art | medium |
| Everything else | unknown | low |

When `confidence != "high"` → `needs_input: true` for domain.

**Task tracker:**

Tracker depends on domain (for `notion_db_id` check), so it can only be fully resolved AFTER domain is known.

**Two-pass logic:**
1. If domain is known (high confidence) → resolve tracker now
2. If domain needs user input → defer tracker resolution. Set `task_tracker: null, tracker_confidence: "deferred"`. After user picks domain, SKILL.md re-evaluates tracker (or asks if ambiguous).

When domain IS known:

| Condition | Suggested tracker | Confidence |
|-----------|------------------|------------|
| GitHub remote exists + `gh` accessible, domain has NO `notion_db_id` | github | high |
| Domain has `notion_db_id` AND no GitHub remote | notion | high |
| Domain has `notion_db_id` AND GitHub remote exists | ambiguous | low → ask |
| No GitHub, domain has no `notion_db_id` | none | high |

When tracker confidence is low → `needs_input: true` for tracker.
When tracker confidence is "deferred" → resolved after domain selection in SKILL.md Step 2.

**Label:**
- From existing `domains.yaml` entry if project id matches → use stored label
- Otherwise: humanize repo name (`h2t-vision` → `H2T Vision`, `crypto-etl` → `Crypto ETL`)

### Output JSON

```json
{
  "detected": {
    "id": "h2t-vision",
    "type": "git",
    "github": "lichtpfad/h2t-vision",
    "stack": "python",
    "domain": "hou2touch",
    "domain_confidence": "high",
    "domain_reason": "path C:/dev/h2t-* matches hou2touch pattern",
    "label": "H2T Vision",
    "task_tracker": "github",
    "tracker_confidence": "high",
    "tracker_reason": "GitHub remote exists and accessible"
  },
  "already_registered": false,
  "needs_input": false,
  "input_fields": [],
  "confirm_message": "Регистрирую проект:\n\n- **ID:** h2t-vision\n- **Label:** H2T Vision\n- **Домен:** dev\n- **Тип:** git (GitHub: lichtpfad/h2t-vision)\n- **Stack:** python\n- **Task tracker:** github\n\nФайлы:\n- `~/.h2t/config/repo-mapping.yaml` → добавлю mapping\n- `~/.h2t/config/domains.yaml` → добавлю project entry\n\nВсё верно?"
}
```

When input needed:

```json
{
  "detected": {
    "id": "steuer-docs",
    "type": "directory",
    "github": null,
    "stack": "none",
    "domain": null,
    "domain_confidence": "low",
    "domain_reason": "path E:/DROPBOX/Steuer/ — no pattern match",
    "label": "Steuer Docs",
    "task_tracker": "none",
    "tracker_confidence": "high",
    "tracker_reason": "no git, no notion_db_id for domain"
  },
  "needs_input": true,
  "input_fields": ["domain"],
  "confirm_message": "Регистрирую проект:\n\n- **ID:** steuer-docs\n- **Label:** Steuer Docs\n- **Тип:** directory (не git)\n- **Task tracker:** определится после выбора домена\n\nНе могу определить домен. Варианты:\n1. admin\n2. personal-os\n3. hou2touch\n4. dev\n5. другой\n\nКакой домен?"
}
```

When already registered:

```json
{
  "already_registered": true,
  "current": {
    "id": "agent-skills",
    "domain": "personal-os",
    "label": "Agent Skills"
  },
  "confirm_message": "Проект agent-skills уже зарегистрирован:\n- Домен: personal-os\n- Label: Agent Skills\n\nХочешь обновить настройки?"
}
```

### Already-registered check

`identify_project()` always returns a result (falls back to `id: "unknown"` with `type: "default"`). To reliably detect "already registered":

- Check `repo-mapping.yaml` directly for an explicit mapping entry matching the cwd or repo name
- If found → `already_registered: true`, populate `current` from the mapping + domains.yaml entry
- If not found (even if `identify_project()` returns something) → `already_registered: false`

Do NOT rely on `identify_project()` return value for this — its fallback makes it impossible to distinguish "registered" from "default guess".

### Dependencies

- `gather.stack.detect_stack()` — reuse for stack detection
- `repo-mapping.yaml` — read directly for already-registered check + existing mappings
- `domains.yaml` — read for domain list, notion_db_id, and existing project entries
- `gh` CLI — optional, for GitHub existence check

---

## Phase 2: SKILL.md (~30 lines)

Minimal orchestration:

```
Step 1: Read INIT_DATA from system messages (injected by PreToolUse hook)
        If INIT_ERROR: — show error, stop

Step 2: Show confirm_message VERBATIM
        If needs_input — collect missing fields from user
        If already_registered — ask if user wants to update
        If tracker_confidence == "deferred" — after user picks domain,
          check if domain has notion_db_id AND github exists → ask tracker
          otherwise resolve automatically (github/notion/none)
        Otherwise — wait for "ок" or corrections

Step 3: Call apply_registration.py with confirmed parameters
        $H2T_PYTHON apply_registration.py \
          --id {id} --domain {domain} --type {type} \
          --label {label} --task-tracker {tracker} \
          [--github owner/repo] [--stack python] [--cwd /path]
        Show result to user.
```

**LLM responsibilities:** ONLY show confirm message, collect user input for missing fields, pass confirmed params to apply script. No detection, no YAML writing, no formatting.

---

## Phase 3: Apply (`apply_registration.py`)

Receives confirmed parameters via CLI args. Writes YAML files. Returns JSON result.

### CLI interface

```bash
apply_registration.py \
  --id my-project \
  --domain dev \
  --type git \
  --label "My Project" \
  --task-tracker github \
  [--github lichtpfad/my-project] \
  [--stack python] \
  [--cwd C:/dev/my-project]
```

### Actions

1. **repo-mapping.yaml** — add mapping entry:
   - git repo → `mappings:` section: `my-project: dev/my-project`
   - non-git directory → `cwd_patterns:` section: `C:/dev/my-project: dev/my-project`

2. **domains.yaml** — add project entry under domain:
   ```yaml
   - id: my-project
     label: "My Project"
     description: ""  # empty, user fills later
     task_tracker: github  # or notion or none
   ```
   If project entry already exists under this domain, update only changed fields.

3. **`.claude/project-id`** (optional) — create in cwd if `--cwd` provided:
   ```
   my-project
   ```
   Only if the file doesn't exist yet.

### Output JSON

```json
{
  "status": "ok",
  "actions": [
    "Added my-project to repo-mapping.yaml mappings",
    "Added my-project to domains.yaml under dev",
    "Created .claude/project-id"
  ],
  "next_steps": [
    "Next /session-start will recognize this project",
    "Run /h2t:scaffold-project for full setup (CLAUDE.md, milestones, issues)"
  ]
}
```

### YAML safety

- **`ruamel.yaml` is required** — these are shared SSOT configs with comments, ordering, and style that must be preserved. `pyyaml` would silently destroy them.
- If `ruamel.yaml` is not installed → abort with error: `"ruamel.yaml required. Install: pip install ruamel.yaml into ~/.h2t/venv"`
- Always read → modify → write (never append raw text)
- Backup original file before writing (`.bak`)

---

## Hook Integration

The current `gather-on-skill` hook hardcodes the path `skills/${SKILL_NAME}/scripts/gather.py`. For init-project the entry script is `detect_project.py`, not `gather.py`.

**Solution:** Generalize the hook to support per-skill script names. Add a lookup:

```bash
# Resolve entry script per skill
case "$SKILL_NAME" in
  init-project)  SCRIPT_NAME="detect_project.py" ;;
  *)             SCRIPT_NAME="gather.py" ;;
esac

GATHER_PY="${CLAUDE_PLUGIN_ROOT}/skills/${SKILL_NAME}/scripts/${SCRIPT_NAME}"
```

The hook also needs a new output branch for init-project:

```bash
elif [ "$SKILL_NAME" = "init-project" ]; then
  # Return as INIT_DATA: (not GATHER_DATA: or BRIEFING:)
  "$H2T_PYTHON" -c "
import sys, json
raw = sys.stdin.read().strip()
output = {'systemMessage': 'INIT_DATA: ' + raw}
print(json.dumps(output, ensure_ascii=False))
" <<< "$RESULT"
```

This keeps each skill's message prefix distinct: `BRIEFING:` for session-start, `GATHER_DATA:` for handoff, `INIT_DATA:` for init-project.

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `plugins/h2t/skills/init-project/SKILL.md` | Create | 3-step orchestration (~30 lines) |
| `plugins/h2t/skills/init-project/scripts/detect_project.py` | Create | Detection + confirm message generation |
| `plugins/h2t/skills/init-project/scripts/apply_registration.py` | Create | YAML writing |
| `plugins/h2t/skills/init-project/scripts/test_detect.py` | Create | Detection tests |
| `plugins/h2t/skills/init-project/scripts/test_apply.py` | Create | Apply tests (temp YAML files) |
| `plugins/h2t/hooks-handlers/gather-on-skill` | Modify | Add init-project branch |

---

## What's NOT in scope

- GitHub repo creation → #18 (scaffold-project)
- CLAUDE.md generation → #18 or separate skill
- Milestones / issues / labels → #18
- Notion DB creation → future
- Cross-machine sync of config → #13

---

## Edge cases

| Case | Behavior |
|------|----------|
| Already registered project | Show current config, ask if update needed |
| Workspace directory (C:/dev/) | Reject: "This is a workspace, not a project. cd into a specific project." |
| No git, no markers at all | Register as `directory` type with `task_tracker: none` |
| GitHub remote exists but `gh` not authenticated | Detect as git, set `github: null`, warn in confirm |
| Domain has notion_db_id AND GitHub exists | Ask user which tracker to use |
| ruamel.yaml not installed | Abort with error, require install into ~/.h2t/venv |

---

## Future: How other skills use `task_tracker`

Once init-project saves `task_tracker` per project, gather can route accordingly:

- `task_tracker: github` → `gather_github()` (current behavior)
- `task_tracker: notion` → `gather_notion()` (future, reads from notion_db_id)
- `task_tracker: none` → skip task gathering

This is NOT implemented now — just the field is saved. Gather routing is a separate issue.
