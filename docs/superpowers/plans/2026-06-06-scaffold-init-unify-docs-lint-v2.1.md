---
title: "Scaffold/Init Unify + docs-lint v2.1 Implementation Plan"
status: "draft"
date: "2026-06-06"
milestone: ""
---
# Scaffold/Init Unify + docs-lint v2.1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix scaffold-project for existing dirs, unify scaffold/init into one entry point, wire `detect_template()` to read v2 config path, add docs-sync-labels SKILL.md (skill existed without it).

**Architecture:** Four independent areas across two plugins. (A) `scaffold_project.py` gains `--merge` flag — idempotent on existing dirs, with safe commit handling. (B) scaffold-project SKILL.md gets state detection (new/existing-no-git/existing-git). (C) `detect_template()` in `project_types.py` learns the v2 `.h2t/docs-lint.yaml` path — used by scaffold-project to pick correct dirs; note that `lint.py` already reads both config paths via `load_config()` → `check_project_structure_typed()`, no lint.py changes needed. (D) `docs-sync-labels` gets a missing `SKILL.md` — scripts exist but the skill was never registered.

**Confirmed non-issues from Codex review:**
- Task 6 (original) was wrong — `_collect_all_findings()` already calls `check_project_structure_typed()` through `load_config()` which reads `.h2t/docs-lint.yaml` + normalizes `project_type` → `template`. Structure checks already work.
- `.h2t/docs-lint.yaml` priority + `project_type` normalization already implemented in `config.py:12-56` (v2 work).

**Tech Stack:** Python 3.11, pytest, h2t-core plugin (`plugins/h2t-core/`), h2t-dev plugin (`plugins/h2t-dev/`)

**Test runners:**
```bash
C:/dev/h2t-skills/.venv/Scripts/pytest plugins/h2t-core/skills/scaffold-project/scripts/ -v
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/ -v
```

---

## Part A — scaffold-project: --merge flag

### Task 1: Add `--merge` flag to scaffold_project.py

**Files:**
- Modify: `plugins/h2t-core/skills/scaffold-project/scripts/scaffold_project.py`
- Create: `plugins/h2t-core/skills/scaffold-project/scripts/test_scaffold.py`

**Key design decisions:**
- `--merge` mode: create missing dirs/files only, skip existing ones
- Git: init only if no `.git`; in merge mode only `git add` the files we just created (not `git add .`), so pre-existing user files are not swept into the initial commit
- `install_hooks()`: wrap `json.loads` in try/except (existing corrupt settings.json would crash merge mode)
- File named same as expected dir (e.g., `src` as file): `check_project_structure_typed()` already handles this — skip in scaffold too (log to actions, don't crash)

- [ ] **Step 1: Write failing tests**

Create `plugins/h2t-core/skills/scaffold-project/scripts/test_scaffold.py`:

```python
import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).parent / "scaffold_project.py"
PY = sys.executable


def _run(*args):
    r = subprocess.run([PY, str(SCRIPT), *args], capture_output=True, text=True)
    return json.loads(r.stdout)


def test_create_new_dir(tmp_path):
    result = _run("create", "--id", "myproj", "--type", "code-local",
                  "--stack", "python", "--dir", str(tmp_path))
    assert result["status"] == "ok"
    assert (tmp_path / "myproj" / "src").exists()
    assert (tmp_path / "myproj" / "README.md").exists()


def test_existing_dir_without_merge_returns_exists(tmp_path):
    (tmp_path / "myproj").mkdir()
    result = _run("create", "--id", "myproj", "--type", "code-local",
                  "--stack", "python", "--dir", str(tmp_path))
    assert result["status"] == "exists"


def test_merge_on_existing_dir(tmp_path):
    (tmp_path / "myproj").mkdir()
    (tmp_path / "myproj" / "docs").mkdir()
    result = _run("create", "--id", "myproj", "--type", "code-local",
                  "--stack", "python", "--dir", str(tmp_path), "--merge")
    assert result["status"] == "merged"
    assert (tmp_path / "myproj" / "src").exists()
    assert (tmp_path / "myproj" / "docs").exists()


def test_merge_does_not_overwrite_existing_readme(tmp_path):
    proj = tmp_path / "myproj"
    proj.mkdir()
    (proj / "README.md").write_text("# MY CUSTOM README", encoding="utf-8")
    _run("create", "--id", "myproj", "--type", "code-local",
         "--stack", "python", "--dir", str(tmp_path), "--merge")
    assert (proj / "README.md").read_text(encoding="utf-8") == "# MY CUSTOM README"


def test_dry_run_merge_shows_merge_flag(tmp_path):
    (tmp_path / "myproj").mkdir()
    result = _run("create", "--id", "myproj", "--type", "code-local",
                  "--stack", "python", "--dir", str(tmp_path), "--merge", "--dry-run")
    assert result["status"] == "dry-run"
    assert result.get("merge") is True


def test_merge_does_not_commit_preexisting_files(tmp_path):
    """In merge mode: only newly scaffolded files are committed, not pre-existing ones."""
    proj = tmp_path / "myproj"
    proj.mkdir()
    secret = proj / "secret.txt"
    secret.write_text("do not commit", encoding="utf-8")
    _run("create", "--id", "myproj", "--type", "code-local",
         "--stack", "python", "--dir", str(tmp_path), "--merge")
    # git should not exist (code-local with pre-existing dir has no git init in merge)
    # OR if git init ran, secret.txt must not be in HEAD
    git_dir = proj / ".git"
    if git_dir.exists():
        import subprocess as sp
        r = sp.run(["git", "-C", str(proj), "show", "--name-only", "HEAD"],
                   capture_output=True, text=True)
        assert "secret.txt" not in r.stdout


def test_merge_skips_dir_that_is_a_file(tmp_path):
    """If expected dir exists as a file, merge logs it and continues instead of crashing."""
    proj = tmp_path / "myproj"
    proj.mkdir()
    (proj / "src").write_text("I am a file", encoding="utf-8")
    result = _run("create", "--id", "myproj", "--type", "code-local",
                  "--stack", "python", "--dir", str(tmp_path), "--merge")
    assert result["status"] == "merged"
    assert any("src" in a and "file" in a.lower() for a in result["actions"])
```

- [ ] **Step 2: Run tests — verify they fail**

```
C:/dev/h2t-skills/.venv/Scripts/pytest plugins/h2t-core/skills/scaffold-project/scripts/test_scaffold.py -v
```
Expected: `test_merge_*` fail (no `--merge` arg yet), `test_create_new_dir` may pass.

- [ ] **Step 3: Implement `--merge` flag**

In `plugins/h2t-core/skills/scaffold-project/scripts/scaffold_project.py`:

**3a. Add `--merge` to argparse** (in `main()`, `p_create` block):

```python
p_create.add_argument("--merge", action="store_true",
                      help="Supplement existing directory — idempotent, skip existing files")
```

**3b. Replace `cmd_create` body** with merge-aware version:

```python
def cmd_create(args: argparse.Namespace) -> dict:
    base = Path(args.dir).expanduser().resolve()
    project_dir = base / args.id
    type_base = args.type.split("-")[0]
    template = template_for_type(args.type)
    if _PROJECT_TYPES_AVAILABLE:
        dirs = PROJECT_TYPES.get(template, {}).get("root_dirs", [])
    else:
        dirs = _DIR_STRUCTURE_FALLBACK.get(type_base, [])
    is_git = args.type in ("code-github", "code-local")

    if args.dry_run:
        items = [f"mkdir {project_dir}"] if not project_dir.exists() else []
        for d in dirs:
            if not (project_dir / d).exists():
                items.append(f"mkdir {project_dir / d}")
        for fname in (".gitignore", "README.md", "CLAUDE.md"):
            if not (project_dir / fname).exists():
                items.append(f"write {project_dir / fname}")
        if is_git and not (project_dir / ".git").exists():
            items.append(f"git init {project_dir}")
            items.append("initial commit (chore: initial scaffold) — new files only")
        return {
            "status": "dry-run",
            "merge": project_dir.exists(),
            "path": str(project_dir),
            "would_create": items,
        }

    if project_dir.exists() and not args.merge:
        return {"status": "exists", "path": str(project_dir),
                "message": f"Directory {project_dir} already exists"}

    is_merge = project_dir.exists()
    if not is_merge:
        project_dir.mkdir(parents=True)
        actions = [f"Created {project_dir}"]
        status_key = "ok"
    else:
        actions = [f"Merging into existing {project_dir}"]
        status_key = "merged"

    # Track files created so we commit only those in merge mode
    created_files: list[str] = []

    for d in dirs:
        dp = project_dir / d
        if dp.is_dir():
            continue
        if dp.exists():
            # Path exists as a file — log and skip
            actions.append(f"Skipped {d}/ — path exists as file, not dir")
            continue
        dp.mkdir(exist_ok=True)
        actions.append(f"Created {project_dir / d}")

    # .gitignore — skip if exists
    gi_path = project_dir / ".gitignore"
    if not gi_path.exists():
        gi_content = DCC_GITIGNORE if type_base == "dcc" else GITIGNORE_TEMPLATES.get(
            args.stack or "none", GITIGNORE_TEMPLATES["none"]
        )
        gi_path.write_text(gi_content, encoding="utf-8")
        actions.append("Created .gitignore")
        created_files.append(".gitignore")

    # README.md — skip if exists
    desc = args.description or "TODO"
    readme_path = project_dir / "README.md"
    if not readme_path.exists():
        readme_path.write_text(README_TEMPLATE.format(id=args.id, description=desc), encoding="utf-8")
        actions.append("Created README.md")
        created_files.append("README.md")

    # CLAUDE.md — skip if exists
    claude_path = project_dir / "CLAUDE.md"
    if not claude_path.exists():
        stack_display = args.stack if (args.stack and args.stack != "none") else "N/A"
        claude_path.write_text(
            CLAUDE_MD_TEMPLATE.format(id=args.id, description=desc, stack_display=stack_display),
            encoding="utf-8",
        )
        actions.append("Created CLAUDE.md")
        created_files.append("CLAUDE.md")

    # git init + commit
    if is_git:
        needs_init = not (project_dir / ".git").exists()
        if needs_init:
            r = _run(["git", "init"], cwd=str(project_dir))
            if r.returncode != 0:
                return {"status": "error", "error": f"git init failed: {r.stderr.strip()}"}
            actions.append("git init")

        if is_merge:
            # Only add/commit the files we just created — never sweep pre-existing content
            if created_files:
                _run(["git", "add", "--"] + created_files, cwd=str(project_dir))
                r2 = _run(["git", "commit", "-m", "chore: scaffold merge — add missing files"],
                          cwd=str(project_dir))
                if r2.returncode == 0:
                    actions.append("Committed scaffold files (merge — new files only)")
                else:
                    actions.append(f"Commit skipped: {r2.stderr.strip()}")
            else:
                actions.append("No new files — commit skipped")
        else:
            _run(["git", "add", "."], cwd=str(project_dir))
            r2 = _run(["git", "commit", "-m", "chore: initial scaffold"], cwd=str(project_dir))
            if r2.returncode == 0:
                actions.append("Initial commit: chore: initial scaffold")
            else:
                actions.append(f"Initial commit skipped: {r2.stderr.strip()}")

    di = run_docs_init(args.id, project_dir, template=template)
    actions.append(f"docs-init: {di['status']}")
    if di["status"] == "error":
        return {"status": "error", "error": f"docs-init failed: {di['error']}"}

    if is_git:
        ih = install_hooks(project_dir)
        actions.append(f"install-hooks: {ih['status']}")

    write_setup_report(
        project_dir=project_dir,
        project_id=args.id,
        template=template,
        status=status_key,
        actions=actions,
    )

    return {"status": status_key, "path": str(project_dir), "actions": actions}
```

**3c. Fix `install_hooks()` — guard json.loads:**

Find the line `data = json.loads(settings_path.read_text(encoding="utf-8"))` in `install_hooks()` and wrap it:

```python
    if settings_path.exists():
        try:
            data = json.loads(settings_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            data = {}
    else:
        data = {}
```

- [ ] **Step 4: Run tests — verify they pass**

```
C:/dev/h2t-skills/.venv/Scripts/pytest plugins/h2t-core/skills/scaffold-project/scripts/test_scaffold.py -v
```
Expected: all 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add plugins/h2t-core/skills/scaffold-project/scripts/scaffold_project.py
git add plugins/h2t-core/skills/scaffold-project/scripts/test_scaffold.py
git commit -m "feat(scaffold): --merge flag, safe commit, file-collision guard, hooks json guard"
```

---

### Task 2: Update scaffold-project SKILL.md — unified state detection

**Files:**
- Modify: `plugins/h2t-core/skills/scaffold-project/SKILL.md`

- [ ] **Step 1: Replace Variables block — fix `$CLAUDE_PLUGIN_ROOT`**

Replace the existing `## Variables` block:

```markdown
## Variables

```bash
H2T_PYTHON="${H2T_PYTHON:-}"
[ -z "$H2T_PYTHON" ] && [ -f "$HOME/.h2t/venv/Scripts/python.exe" ] && H2T_PYTHON="$HOME/.h2t/venv/Scripts/python.exe"
[ -z "$H2T_PYTHON" ] && [ -f "$HOME/.h2t/venv/bin/python" ] && H2T_PYTHON="$HOME/.h2t/venv/bin/python"

# Resolve h2t-core plugin root — $CLAUDE_PLUGIN_ROOT is not always exported to bash
if [ -n "${CLAUDE_PLUGIN_ROOT:-}" ]; then
    _CORE_ROOT="$CLAUDE_PLUGIN_ROOT"
else
    _CORE_ROOT=$(ls -dt "$HOME/.claude/plugins/cache/lichtpfad/h2t-core"/[0-9]* 2>/dev/null | head -1)
fi
SCAFFOLD="$_CORE_ROOT/skills/scaffold-project/scripts/scaffold_project.py"
APPLY_REG="$_CORE_ROOT/skills/init-project/scripts/apply_registration.py"
CONFIG_ROOT="$HOME/.h2t/config"
```
```

- [ ] **Step 2: Replace Step 2 with state detection**

Replace the existing `## Step 2: Confirm Base Directory` section:

```markdown
## Step 2: Confirm Base Directory + Detect State

Ask: "Где создать/дополнить директорию? (по умолчанию: C:/dev/{id})"

Accept:
- Enter / `.` / `да` → use `C:/dev/{id}`
- A path → use that path exactly

Resolve `project_dir` = `{base_dir}/{id}` (prepend `C:/dev/` if relative).

Run state detection:

```bash
[ -d "{project_dir}" ] && echo "EXISTS" || echo "NEW"
git -C "{project_dir}" rev-parse --git-dir 2>/dev/null && echo "HAS_GIT" || echo "NO_GIT"
```

| State | Meaning | Next |
|-------|---------|------|
| NEW | Directory doesn't exist | Step 3: dry-run without --merge |
| EXISTS + NO_GIT | Existing dir, no git | Step 3: dry-run with --merge |
| EXISTS + HAS_GIT | Already a git repo | Skip to Step 5 (registration only) |

Show detected state in one line, e.g. `Состояние: EXISTS+NO_GIT → дополняем`.
```

- [ ] **Step 3: Update Step 3 (dry-run) to pass `--merge` conditionally**

Replace `## Step 3: Dry-Run Preview (GATE)`:

```markdown
## Step 3: Dry-Run Preview (GATE)

```bash
$H2T_PYTHON "$SCAFFOLD" create \
  --id "{id}" --type "{type}" --stack "{stack}" \
  --dir "{base_dir}" --description "{description}" \
  [--merge]   # only if state is EXISTS+NO_GIT
  --dry-run
```

Show the `would_create` list as bullet list.
If `"merge": true` in output → note: "Существующие файлы не будут перезаписаны. Только новые файлы войдут в коммит."

Ask: "Создаём? (y / да / .)" — **Do NOT proceed until confirmed.**
```

- [ ] **Step 4: Update Step 4 (create) to pass `--merge` conditionally**

Replace `## Step 4: Create Structure`:

```markdown
## Step 4: Create / Supplement Structure

```bash
$H2T_PYTHON "$SCAFFOLD" create \
  --id "{id}" --type "{type}" --stack "{stack}" \
  --dir "{base_dir}" --description "{description}" \
  [--merge]   # only if state is EXISTS+NO_GIT
```

Parse JSON. If `"status": "error"` — show error and stop.
Show `actions` list as checkmarks. Note `"path"` — this is the project root.
```

- [ ] **Step 5: Update description frontmatter (lines 9-10)**

Change:
```
  NOT for registering existing repos (use
  /h2t-core:init-project for that).
```
to:
```
  Handles all states: new repo, existing dir without git (--merge), existing git repo
  (registration only). init-project is for automated session-start hook use only.
```

- [ ] **Step 6: Commit**

```bash
git add plugins/h2t-core/skills/scaffold-project/SKILL.md
git commit -m "feat(scaffold): unified state detection new/exists-no-git/exists-git"
```

---

### Task 3: Update init-project SKILL.md — routing note

**Files:**
- Modify: `plugins/h2t-core/skills/init-project/SKILL.md`

- [ ] **Step 1: Add routing note after `# Instructions`**

```markdown
> **Manual project setup?** Use `/h2t-core:scaffold-project` — it handles new repos, existing dirs, and registration in one wizard. This skill (`init-project`) is for **automated** registration triggered by `session-start` when a project is discovered but not yet registered.
```

- [ ] **Step 2: Commit**

```bash
git add plugins/h2t-core/skills/init-project/SKILL.md
git commit -m "docs(init-project): clarify automated-only scope"
```

---

### Task 4: Bump h2t-core to 3.2.8 + deploy cache

**Files:**
- Modify: `plugins/h2t-core/.claude-plugin/plugin.json`

- [ ] **Step 1: Bump version**

Change `"version": "3.2.7"` → `"version": "3.2.8"`.

- [ ] **Step 2: Deploy cache**

```bash
bash plugins/h2t-core/scripts/update-plugin.sh
```
Expected: `{"status":"ok","version":"3.2.8",...}`

- [ ] **Step 3: Commit**

```bash
git add plugins/h2t-core/.claude-plugin/plugin.json
git commit -m "chore(h2t-core): bump to 3.2.8"
```

---

## Part B — detect_template() v2 path (scaffold-project only)

### Task 5: Update `detect_template()` — read `.h2t/docs-lint.yaml`

**Context:** `detect_template()` is called by `scaffold_project.py` to determine which template dirs to create. It currently only reads `.claude/rules/docs-lint.yaml` with `template:` field. It should also read `.h2t/docs-lint.yaml` with `project_type:` field (written by our v2 config). `lint.py` does NOT call `detect_template()` — it uses `load_config()` which already handles both paths. This task is scaffold-project–only.

**Files:**
- Modify: `plugins/h2t-dev/lib/docs/project_types.py`
- Create: `tests/docs/test_project_types.py`

- [ ] **Step 1: Write failing tests**

Create `tests/docs/test_project_types.py`:

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[2] / "plugins/h2t-dev/lib"))

from docs.project_types import detect_template, PROJECT_TYPES


def test_detect_from_h2t_docs_lint_yaml_project_type(tmp_path):
    """v2 path: .h2t/docs-lint.yaml with project_type field."""
    h2t = tmp_path / ".h2t"
    h2t.mkdir()
    (h2t / "docs-lint.yaml").write_text("project_type: research_project\n", encoding="utf-8")
    assert detect_template(tmp_path) == "research_project"


def test_detect_from_claude_rules_docs_lint_yaml_template(tmp_path):
    """Legacy path: .claude/rules/docs-lint.yaml with template field."""
    rules = tmp_path / ".claude" / "rules"
    rules.mkdir(parents=True)
    (rules / "docs-lint.yaml").write_text("template: creative_project\n", encoding="utf-8")
    assert detect_template(tmp_path) == "creative_project"


def test_h2t_path_takes_priority_over_claude_rules(tmp_path):
    (tmp_path / ".h2t").mkdir()
    (tmp_path / ".h2t" / "docs-lint.yaml").write_text(
        "project_type: research_project\n", encoding="utf-8"
    )
    rules = tmp_path / ".claude" / "rules"
    rules.mkdir(parents=True)
    (rules / "docs-lint.yaml").write_text("template: creative_project\n", encoding="utf-8")
    assert detect_template(tmp_path) == "research_project"


def test_unknown_project_type_falls_through_to_heuristics(tmp_path):
    (tmp_path / ".h2t").mkdir()
    (tmp_path / ".h2t" / "docs-lint.yaml").write_text(
        "project_type: totally_unknown_type\n", encoding="utf-8"
    )
    assert detect_template(tmp_path) == "code_repo"  # heuristic default


def test_detect_falls_back_to_pyproject(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    assert detect_template(tmp_path) == "code_repo"
```

Run to verify fail:
```
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/test_project_types.py::test_detect_from_h2t_docs_lint_yaml_project_type -v
```
Expected: FAIL.

- [ ] **Step 2: Update `detect_template()` in `project_types.py`**

Replace the existing `detect_template` function (lines 63–90):

```python
def detect_template(repo_root: Path) -> str:
    """Detect project template name for an existing repo.

    Priority:
    1. .h2t/docs-lint.yaml  project_type field  (v2 — written by scaffold-project)
    2. .claude/rules/docs-lint.yaml  template field  (legacy — written by docs-init)
    3. File-presence heuristics
    4. Default: code_repo
    """
    def _parse_yaml_field(path: Path, field: str) -> str | None:
        if not path.exists():
            return None
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith(f"{field}:"):
                val = line.split(":", 1)[1].strip().split("#")[0].strip().strip('"\'')
                return val if val in PROJECT_TYPES else None
        return None

    result = _parse_yaml_field(repo_root / ".h2t" / "docs-lint.yaml", "project_type")
    if result:
        return result

    result = _parse_yaml_field(repo_root / ".claude" / "rules" / "docs-lint.yaml", "template")
    if result:
        return result

    if (repo_root / "pyproject.toml").exists() or (repo_root / "setup.py").exists():
        return "code_repo"
    if (repo_root / "package.json").exists():
        return "code_repo"
    if (repo_root / "deliverables").exists():
        return "client_project"
    if (repo_root / "assets").exists() and (repo_root / "scripts").exists():
        return "creative_project"

    return "code_repo"
```

- [ ] **Step 3: Run tests**

```
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/test_project_types.py -v
```
Expected: all 5 PASS.

Full suite:
```
C:/dev/h2t-skills/.venv/Scripts/pytest tests/docs/ -v
```
Expected: all green (no regressions).

- [ ] **Step 4: Commit**

```bash
git add plugins/h2t-dev/lib/docs/project_types.py
git add tests/docs/test_project_types.py
git commit -m "feat(project_types): detect_template reads .h2t/docs-lint.yaml project_type"
```

---

## Part C — docs-sync-labels SKILL.md (missing)

### Task 6: Create docs-sync-labels SKILL.md

**Context:** `plugins/h2t-dev/skills/docs-sync-labels/` has `scripts/sync_labels.py` and `data/labels.json` but NO `SKILL.md`. Without it the skill is invisible to Claude Code. The script already works — scaffold-project calls it via `run_sync_labels()`.

**Files:**
- Create: `plugins/h2t-dev/skills/docs-sync-labels/SKILL.md`

- [ ] **Step 1: Read existing script to understand interface**

```bash
head -40 plugins/h2t-dev/skills/docs-sync-labels/scripts/sync_labels.py
```

Parse: expected args, what it does, exit codes.

- [ ] **Step 2: Create SKILL.md**

Create `plugins/h2t-dev/skills/docs-sync-labels/SKILL.md`:

```markdown
---
name: h2t-dev:docs-sync-labels
description: >
  Sync canonical GitHub labels from ~/.h2t/config/docs/standards/ or
  plugins/h2t-dev/skills/docs-sync-labels/data/labels.json to a GitHub repo.
  Triggers on "/docs-sync-labels", "sync labels", "apply labels".
compatibility: "Claude Code"
metadata:
  author: lichtpfad
  version: 1.0.0
---

# Instructions

Sync canonical h2t labels to the current (or specified) GitHub repo.

## Variables

```bash
H2T_PYTHON="${H2T_PYTHON:-}"
[ -z "$H2T_PYTHON" ] && [ -f "$HOME/.h2t/venv/Scripts/python.exe" ] && H2T_PYTHON="$HOME/.h2t/venv/Scripts/python.exe"
[ -z "$H2T_PYTHON" ] && [ -f "$HOME/.h2t/venv/bin/python" ] && H2T_PYTHON="$HOME/.h2t/venv/bin/python"

if [ -n "${CLAUDE_PLUGIN_ROOT:-}" ]; then
    _DEV_ROOT="$CLAUDE_PLUGIN_ROOT"
else
    _DEV_ROOT=$(ls -dt "$HOME/.claude/plugins/cache/lichtpfad/h2t-dev"/[0-9]* 2>/dev/null | head -1)
fi
SYNC_LABELS="$_DEV_ROOT/skills/docs-sync-labels/scripts/sync_labels.py"
```

## Step 1: Identify target repo

Detect from git remote or ask:

```bash
git remote get-url origin 2>/dev/null | sed 's|.*github.com[:/]||;s|\.git$||'
```

If not a GitHub remote, ask: "GitHub repo (owner/name)?"

## Step 2: Dry-run preview

```bash
$H2T_PYTHON "$SYNC_LABELS" "{repo_name}" --dry-run
```

Show what would be created/updated/deleted. Ask: "Применить? (y / да / .)"

## Step 3: Apply

```bash
$H2T_PYTHON "$SYNC_LABELS" "{repo_name}" --apply
```

Show summary. Done.

## Error Handling

| Situation | Action |
|-----------|--------|
| `gh` not authenticated | Show: "Run `gh auth login` first" |
| Script not found | Show path, suggest `/h2t-core:setup` |
| No GitHub remote | Ask for repo name manually |
```

(Note: adapt the step content after reading the actual script interface in Step 1.)

- [ ] **Step 3: Commit**

```bash
git add plugins/h2t-dev/skills/docs-sync-labels/SKILL.md
git commit -m "feat(docs-sync-labels): add missing SKILL.md — skill was invisible without it"
```

---

### Task 7: Bump h2t-dev to 1.0.18 + reload

**Files:**
- Modify: `plugins/h2t-dev/plugin.json`

- [ ] **Step 1: Bump**

```bash
python scripts/bump_plugin.py h2t-dev 1.0.18
```

- [ ] **Step 2: Commit**

```bash
git add plugins/h2t-dev/plugin.json plugins/h2t-dev/CHANGELOG.md
git commit -m "chore(h2t-dev): bump to 1.0.18 — detect_template v2 path, docs-sync-labels SKILL.md"
```

- [ ] **Step 3: Deploy + reload**

```
/plugin marketplace update lichtpfad
/reload-plugins
```

After reload, verify `/h2t-dev:docs-sync-labels` appears in skill list.

---

## Self-Review Checklist

- [x] Task 1: `--merge` — 7 tests including safe commit (no pre-existing files), file-collision guard, hooks json guard
- [x] Task 2: SKILL.md — $CLAUDE_PLUGIN_ROOT fix, state table, --merge conditional
- [x] Task 3: init-project routing note
- [x] Task 4: h2t-core 3.2.8 + cache deploy
- [x] Task 5: `detect_template()` — both paths, priority, unknown-value passthrough, 5 tests; lint.py unchanged (already works via load_config)
- [x] Task 6: docs-sync-labels SKILL.md created — skill now visible
- [x] Task 7: h2t-dev 1.0.18 + reload
- [x] No placeholders
- [x] Codex P1 fixes: merge commit safety, Task 6 (structure dim) removed (already exists), config paths (already in config.py), h2t-dev deploy added
- [x] Codex P2 fixes: install_hooks json guard, file-as-dir collision, correct test files
