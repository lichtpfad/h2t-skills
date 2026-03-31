# Briefing in Hook — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move briefing formatting from SKILL.md into the hook pipeline so Claude receives ready-to-display markdown instead of raw JSON. Includes pre-built session slug template. Fixes #19, #20, #15.

**Architecture:** New `briefing.py` takes gather JSON, returns markdown briefing + session slug template with deterministic components pre-filled. Hook calls gather.py → format_briefing → returns `BRIEFING:` + `GATHER_META:` (with slug template). SKILL.md becomes minimal: show briefing verbatim, fill in `{task}` in slug, enforce GATE.

**Tech Stack:** Python 3.11+, pytest, bash (hook handler)

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `plugins/h2t/lib/gather/briefing.py` | **Create** | Format gather JSON → markdown briefing + session slug template |
| `plugins/h2t/lib/gather/test_briefing.py` | **Create** | Tests for briefing formatter |
| `plugins/h2t/lib/gather/__init__.py` | **Modify** | Export `format_briefing` |
| `plugins/h2t/skills/dev-session-start/scripts/gather.py` | **Modify** | Add `--format-briefing` flag, call format_briefing when set |
| `plugins/h2t/hooks-handlers/gather-on-skill` | **Modify** | Pass `--format-briefing` for dev-session-start, return `BRIEFING:` + `GATHER_META:` |
| `plugins/h2t/skills/dev-session-start/SKILL.md` | **Modify** | Simplify: show BRIEFING verbatim, use slug template from GATHER_META, enforce GATE |

**Design decisions:**
- `format_briefing` lives in `lib/gather/` — pure data→text transform, reusable by other skills.
- Slug template is deterministic: `{project}-{milestone}-{task}-{date}-{time}`. Script fills project, milestone, date, time. LLM only fills `{task}` based on chosen issue.
- **Key constraint (feedback memory):** SKILL.md instructions get ignored by Claude — hooks are the only reliable injection point. All formatting MUST happen in the hook pipeline.

---

### Task 1: Create `briefing.py` — the formatter

**Files:**
- Create: `plugins/h2t/lib/gather/briefing.py`
- Create: `plugins/h2t/lib/gather/test_briefing.py`

- [ ] **Step 1: Write the failing test — minimal briefing**

```python
# plugins/h2t/lib/gather/test_briefing.py
"""Tests for briefing formatter."""

from gather.briefing import format_briefing


def test_minimal_briefing():
    """Project with git only, no GitHub, no sessions."""
    data = {
        "project": {"id": "my-project", "domain": "dev", "label": "My Project", "type": "git", "github": None},
        "user": {"core_path": "", "language": "ru"},
        "git": {"branch": "main", "status": "", "log": ["abc123 initial commit"], "stash": "", "remote": "", "owner_repo": ""},
        "github": {},
        "stack": {"name": "python", "commands": {"test": "pytest"}},
        "sessions": [],
        "machine": "automata",
    }
    briefing, meta = format_briefing(data)

    assert "## Сессия: my-project" in briefing
    assert "`main`" in briefing
    assert "python" in briefing
    # Slug template
    assert "slug_template" in meta
    assert meta["slug_template"].startswith("my-project-")
    assert "{task}" in meta["slug_template"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd C:/dev/claude-agent-skills && ~/.h2t/venv/Scripts/python.exe -m pytest plugins/h2t/lib/gather/test_briefing.py::test_minimal_briefing -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'gather.briefing'`

- [ ] **Step 3: Implement `format_briefing` — core function**

```python
# plugins/h2t/lib/gather/briefing.py
"""Format gather JSON into a ready-to-display markdown briefing."""

from datetime import datetime


def format_briefing(data: dict) -> tuple[str, dict]:
    """Convert gather data dict to markdown briefing + metadata.

    Returns:
        (briefing_markdown, meta_dict) where meta_dict contains:
        - slug_template: session name with {task} placeholder
        - project, user, sessions, machine (for SKILL.md interactive steps)
    """
    project = data.get("project", {})
    git = data.get("git", {})
    github = data.get("github", {})
    stack = data.get("stack", {})
    sessions = data.get("sessions", [])

    briefing = _format_briefing_md(project, git, github, stack, sessions, data)
    slug = _build_slug_template(project, github)

    meta = {
        "slug_template": slug,
        "project": project,
        "user": data.get("user", {}),
        "sessions": sessions,
        "machine": data.get("machine", ""),
        "session_id": data.get("session_id", ""),
    }

    return briefing, meta


def _format_briefing_md(
    project: dict, git: dict, github: dict,
    stack: dict, sessions: list, data: dict,
) -> str:
    """Build markdown briefing string."""
    lines = []

    # Header
    branch = git.get("branch", "")
    branch_str = f" (`{branch}`)" if branch else ""
    lines.append(f"## Сессия: {project.get('id', 'unknown')}{branch_str}")
    lines.append("")

    # Stack
    stack_name = stack.get("name", "none")
    if stack_name != "none":
        lines.append(f"**Stack:** {stack_name}")

    # Milestone
    milestone = github.get("current_milestone")
    if milestone:
        title = milestone.get("title", "")
        open_count = milestone.get("open", 0)
        closed = milestone.get("closed", 0)
        total = open_count + closed
        lines.append(f"**Milestone:** {title} — {open_count}/{total} issues open")

    lines.append("")

    # Open Tasks
    issues = github.get("issues", [])
    bugs = github.get("bugs", [])
    milestone_issues = github.get("milestone_issues", [])

    task_source = milestone_issues if milestone_issues else issues
    if task_source or bugs:
        lines.append("### Задачи")

        bug_numbers = {b.get("number") for b in bugs}
        for issue in task_source:
            num = issue.get("number", "")
            title = issue.get("title", "")
            labels = issue.get("labels", [])
            label_names = [l.get("name", "") if isinstance(l, dict) else str(l) for l in labels]

            prefix = ""
            if num in bug_numbers:
                prefix = "BUG "
            elif any("p0" in l.lower() for l in label_names):
                prefix = "P0 "
            elif any("p1" in l.lower() for l in label_names):
                prefix = "P1 "

            lines.append(f"- {prefix}#{num} {title}")

        # Bugs not in task_source
        task_numbers = {i.get("number") for i in task_source}
        extra_bugs = [b for b in bugs if b.get("number") not in task_numbers]
        for bug in extra_bugs:
            lines.append(f"- BUG #{bug.get('number', '')} {bug.get('title', '')}")

        lines.append("")

    # Uncommitted work
    status = git.get("status", "")
    if status:
        lines.append("### Незакоммиченное")
        lines.append(f"```\n{status}\n```")
        lines.append("")

    # Stash
    stash = git.get("stash", "")
    if stash:
        lines.append(f"**Stash:** {stash}")
        lines.append("")

    # PRs
    prs = github.get("prs", [])
    if prs:
        lines.append("### Открытые PR")
        for pr in prs:
            lines.append(f"- #{pr.get('number', '')} {pr.get('title', '')} (`{pr.get('headRefName', '')}`)")
        lines.append("")

    # Sessions
    if sessions:
        lines.append("### Контекст")
        lines.append(f"Handoff-файлы: {len(sessions)} (последние будут прочитаны)")
        lines.append("")

    # Hints
    hints = _build_hints(data)
    if hints:
        lines.append("### Hints")
        for hint in hints:
            lines.append(f"- {hint}")
        lines.append("")

    return "\n".join(lines)


def _build_slug_template(project: dict, github: dict) -> str:
    """Build session slug with deterministic parts filled, {task} as placeholder.

    Format: {project}-{milestone}-{task}-{date}-{time}
    If no milestone: {project}-{task}-{date}-{time}
    """
    now = datetime.now()
    proj = project.get("id", "unknown")
    # Short project name: strip common prefixes
    if proj.startswith("h2t-"):
        proj = proj  # keep as-is, already short
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H%M")

    milestone = github.get("current_milestone")
    if milestone:
        # Extract milestone short name: "Phase 5" → "p5", "v3.0" → "v3"
        ms_title = milestone.get("title", "")
        ms_short = _shorten_milestone(ms_title)
        return f"{proj}-{ms_short}-{{task}}-{date_str}-{time_str}"

    return f"{proj}-{{task}}-{date_str}-{time_str}"


def _shorten_milestone(title: str) -> str:
    """Shorten milestone title for slug: 'Phase 5' → 'p5', 'v3.0' → 'v3'."""
    t = title.strip().lower()
    # "Phase N" or "Фаза N"
    for prefix in ("phase ", "фаза "):
        if t.startswith(prefix):
            return "p" + t[len(prefix):].split()[0]
    # Already short like "v3.0", "m4"
    if len(t) <= 5:
        return t.split(".")[0]  # "v3.0" → "v3"
    # Fallback: first 6 chars, alphanumeric only
    return "".join(c for c in t if c.isalnum())[:6]


def _build_hints(data: dict) -> list[str]:
    """Generate actionable hints for missing/unusual data."""
    hints = []
    project = data.get("project", {})
    github = data.get("github", {})
    stack = data.get("stack", {})
    sessions = data.get("sessions", [])

    if project.get("type") == "workspace":
        children = project.get("children", [])
        names = ", ".join(c.get("id", "") for c in children[:8])
        hints.append(f"Workspace с {len(children)} проектами ({names}). Какой проект сегодня?")

    if project.get("id") == "unknown":
        hints.append("Repo не зарегистрирован. Запусти `/h2t:init-project` для регистрации.")

    if not github.get("issues") and project.get("github"):
        hints.append("Нет открытых issues. Создай через `/h2t:github-issues` или `gh issue create`.")

    if not sessions:
        hints.append("Нет предыдущих сессий. Свежий старт.")

    if stack.get("name") == "none":
        hints.append("Stack не определён. Добавь `pyproject.toml`, `package.json` или `Cargo.toml`.")

    return hints
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd C:/dev/claude-agent-skills && ~/.h2t/venv/Scripts/python.exe -m pytest plugins/h2t/lib/gather/test_briefing.py::test_minimal_briefing -v`
Expected: PASS

- [ ] **Step 5: Write tests for GitHub-rich project and slug generation**

```python
# append to plugins/h2t/lib/gather/test_briefing.py
from unittest.mock import patch
from datetime import datetime


def test_full_briefing_with_github():
    """Project with milestones, issues, bugs, PRs."""
    data = {
        "project": {"id": "agent-skills", "domain": "dev", "label": "Claude Agent Skills", "type": "git", "github": "lichtpfad/claude-agent-skills"},
        "user": {"core_path": "/home/user/.h2t/config/about-me/core.md", "language": "ru"},
        "git": {"branch": "feat/briefing", "status": "M  lib/gather/briefing.py\n?? test.py", "log": ["abc fix something"], "stash": "stash@{0}: WIP", "remote": "", "owner_repo": "lichtpfad/claude-agent-skills"},
        "github": {
            "milestones": [{"title": "v3.0", "open": 5, "closed": 10}],
            "current_milestone": {"title": "v3.0", "open": 5, "closed": 10},
            "milestone_issues": [
                {"number": 19, "title": "format briefing in hook", "labels": [{"name": "priority:p0"}]},
                {"number": 20, "title": "session naming GATE lost", "labels": [{"name": "priority:p0"}, {"name": "bug"}]},
            ],
            "issues": [{"number": 19, "title": "format briefing in hook", "labels": []}],
            "bugs": [{"number": 20, "title": "session naming GATE lost"}],
            "prs": [{"number": 25, "title": "feat: briefing formatter", "headRefName": "feat/briefing"}],
        },
        "stack": {"name": "python", "commands": {"test": "pytest"}},
        "sessions": ["/home/user/.dor/sessions/automata/agent-skills/session-2026-03-25.md"],
        "machine": "automata",
    }
    briefing, meta = format_briefing(data)

    assert "agent-skills" in briefing
    assert "`feat/briefing`" in briefing
    assert "v3.0" in briefing
    assert "5/15" in briefing
    assert "P0 #19" in briefing
    assert "BUG #20" in briefing
    assert "#25" in briefing
    assert "feat/briefing" in briefing
    assert "Stash" in briefing
    assert "Незакоммиченное" in briefing
    assert "Контекст" in briefing
    # Slug has milestone
    assert "agent-skills-v3-{task}-" in meta["slug_template"]


@patch("gather.briefing.datetime")
def test_slug_template_with_milestone(mock_dt):
    """Slug includes milestone short name."""
    mock_dt.now.return_value = datetime(2026, 3, 26, 14, 30)
    mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

    data = {
        "project": {"id": "crypto", "type": "git"},
        "github": {"current_milestone": {"title": "Phase 5", "open": 3, "closed": 7}},
        "git": {}, "user": {}, "stack": {"name": "none", "commands": {}},
        "sessions": [], "machine": "automata",
    }
    _, meta = format_briefing(data)
    assert meta["slug_template"] == "crypto-p5-{task}-2026-03-26-1430"


@patch("gather.briefing.datetime")
def test_slug_template_without_milestone(mock_dt):
    """Slug omits milestone when none exists."""
    mock_dt.now.return_value = datetime(2026, 3, 26, 10, 15)
    mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

    data = {
        "project": {"id": "art-project", "type": "git"},
        "github": {},
        "git": {}, "user": {}, "stack": {"name": "none", "commands": {}},
        "sessions": [], "machine": "automata",
    }
    _, meta = format_briefing(data)
    assert meta["slug_template"] == "art-project-{task}-2026-03-26-1015"


def test_workspace_hint():
    """Workspace project shows children list."""
    data = {
        "project": {"id": "workspace", "type": "workspace", "domain": "dev", "label": "Workspace",
                     "children": [{"id": "h2t-ai", "domain": "dev"}, {"id": "agent-skills", "domain": "dev"}]},
        "user": {"core_path": "", "language": "ru"},
        "git": {}, "github": {}, "stack": {"name": "none", "commands": {}},
        "sessions": [], "machine": "automata",
    }
    briefing, _ = format_briefing(data)
    assert "Workspace" in briefing
    assert "h2t-ai" in briefing
    assert "agent-skills" in briefing
    assert "Какой проект сегодня?" in briefing


def test_unknown_project_hint():
    """Unknown project suggests init-project."""
    data = {
        "project": {"id": "unknown", "type": "git", "domain": "dev", "label": "unknown", "github": None},
        "user": {"core_path": "", "language": "ru"},
        "git": {"branch": "main", "status": "", "log": [], "stash": "", "remote": "", "owner_repo": ""},
        "github": {}, "stack": {"name": "none", "commands": {}},
        "sessions": [], "machine": "automata",
    }
    briefing, _ = format_briefing(data)
    assert "init-project" in briefing


def test_empty_github_no_crash():
    """Empty github dict doesn't crash."""
    data = {
        "project": {"id": "art-project", "type": "git", "domain": "art", "label": "Art", "github": None},
        "user": {"core_path": "", "language": "ru"},
        "git": {"branch": "main", "status": "", "log": [], "stash": "", "remote": "", "owner_repo": ""},
        "github": {}, "stack": {"name": "none", "commands": {}},
        "sessions": [], "machine": "automata",
    }
    briefing, _ = format_briefing(data)
    assert "art-project" in briefing
    assert "Задачи" not in briefing  # no tasks section when empty
```

- [ ] **Step 6: Run all briefing tests**

Run: `cd C:/dev/claude-agent-skills && ~/.h2t/venv/Scripts/python.exe -m pytest plugins/h2t/lib/gather/test_briefing.py -v`
Expected: ALL PASS

- [ ] **Step 7: Commit**

```bash
git add plugins/h2t/lib/gather/briefing.py plugins/h2t/lib/gather/test_briefing.py
git commit -m "feat: add format_briefing() — markdown briefing + slug template (#19)"
```

---

### Task 2: Wire `format_briefing` into gather.py

**Files:**
- Modify: `plugins/h2t/skills/dev-session-start/scripts/gather.py`
- Modify: `plugins/h2t/lib/gather/__init__.py`

- [ ] **Step 1: Update `__init__.py` to export `format_briefing`**

Add to `plugins/h2t/lib/gather/__init__.py`:

```python
from .briefing import format_briefing
```

Add `"format_briefing"` to the `__all__` list.

- [ ] **Step 2: Add `--format-briefing` flag to gather.py**

In `plugins/h2t/skills/dev-session-start/scripts/gather.py`, add:

1. New argument: `parser.add_argument("--format-briefing", action="store_true")`
2. After `result` dict is built (before eval recording), if `args.format_briefing`:

```python
from gather.briefing import format_briefing as fmt_briefing

if args.format_briefing:
    briefing_md, briefing_meta = fmt_briefing(result)
    result["_briefing"] = briefing_md
    result["_meta"] = briefing_meta
```

The raw data stays in the JSON for eval tracking. `_briefing` is the pre-formatted markdown string, `_meta` contains slug_template and interactive-step data.

- [ ] **Step 3: Run existing tests to verify no regressions**

Run: `cd C:/dev/claude-agent-skills && ~/.h2t/venv/Scripts/python.exe -m pytest plugins/h2t/lib/gather/ -v`
Expected: ALL PASS

- [ ] **Step 4: Commit**

```bash
git add plugins/h2t/skills/dev-session-start/scripts/gather.py plugins/h2t/lib/gather/__init__.py
git commit -m "feat: gather.py --format-briefing adds _briefing and _meta to output"
```

---

### Task 3: Update hook to return `BRIEFING:` + `GATHER_META:`

**Files:**
- Modify: `plugins/h2t/hooks-handlers/gather-on-skill`

- [ ] **Step 1: Add `--format-briefing` flag conditionally**

After the current `RESULT=$("$H2T_PYTHON" "$GATHER_PY" --cwd "$cwd" ...)` line, change to:

```bash
# Build gather args — format-briefing only for dev-session-start
GATHER_ARGS="--cwd $cwd"
if [ "$SKILL_NAME" = "dev-session-start" ]; then
  GATHER_ARGS="$GATHER_ARGS --format-briefing"
fi
RESULT=$("$H2T_PYTHON" "$GATHER_PY" $GATHER_ARGS 2>/dev/null) || true
```

- [ ] **Step 2: Replace the dev-session-start output branch**

Replace the `else` branch (lines 92-100) that currently returns raw `GATHER_DATA:` with:

```bash
# dev-session-start: return pre-formatted briefing + meta
"$H2T_PYTHON" -c "
import sys, json
raw = sys.stdin.read().strip()
data = json.loads(raw)
briefing = data.pop('_briefing', '')
meta = data.pop('_meta', {})
if briefing:
    msg = 'BRIEFING:\n' + briefing + '\nGATHER_META: ' + json.dumps(meta, ensure_ascii=False)
    output = {'systemMessage': msg}
else:
    output = {'systemMessage': 'GATHER_DATA: ' + raw}
print(json.dumps(output, ensure_ascii=False))
" <<< "$RESULT"
```

Key changes vs old version:
- Returns `BRIEFING:\n{markdown}\nGATHER_META: {json}` instead of `GATHER_DATA: {raw_json}`
- `GATHER_META` contains only what SKILL.md needs for interactive steps: `slug_template`, `project`, `user`, `sessions`, `machine`, `session_id`
- Falls back to `GATHER_DATA:` if `_briefing` is missing (defensive)

- [ ] **Step 3: Verify handoff branch unchanged**

The handoff branch (lines 58-91) is NOT modified — it still returns `GATHER_DATA:` with `_handoff` injection. No regression.

- [ ] **Step 4: Test hook manually — dev-session-start**

```bash
echo '{"tool_input":{"skill":"h2t:dev-session-start"},"cwd":"C:/dev/claude-agent-skills"}' | bash plugins/h2t/hooks-handlers/gather-on-skill
```

Expected output contains:
- `BRIEFING:` with `## Сессия: agent-skills`
- `GATHER_META:` with `slug_template` containing `agent-skills-{task}-2026-03-26-HHMM`
- NO `GATHER_DATA:` prefix

- [ ] **Step 5: Test hook manually — handoff (regression check)**

```bash
echo '{"tool_input":{"skill":"h2t:handoff"},"cwd":"C:/dev/claude-agent-skills"}' | bash plugins/h2t/hooks-handlers/gather-on-skill
```

Expected: `GATHER_DATA:` with `_handoff` object — unchanged behavior.

- [ ] **Step 6: Commit**

```bash
git add plugins/h2t/hooks-handlers/gather-on-skill
git commit -m "feat: hook returns BRIEFING: + GATHER_META: for dev-session-start (#19)"
```

---

### Task 4: Simplify SKILL.md — show briefing verbatim, use slug template, enforce GATE

**Files:**
- Modify: `plugins/h2t/skills/dev-session-start/SKILL.md`

- [ ] **Step 1: Rewrite Steps 1-2 into Step 1: Show Briefing**

Replace current Steps 1-2 (lines 30-84) with:

```markdown
### Step 1: Show Briefing

The PreToolUse hook already formatted the briefing. Look for `BRIEFING:` in hook output or system messages.

**Show it VERBATIM.** Do not modify, supplement, or re-gather any data. Do not run git, gh, or any other commands.

If `BRIEFING:` is missing, look for `GATHER_DATA:` (fallback) and format manually.
If `GATHER_ERROR:` — show the error and stop.

Also read (if paths are present in GATHER_META):
- Session handoff files from `sessions[]` (max 2 most recent, key decisions only)
- User context from `user.core_path`
- `<memory_dir>/MEMORY.md` for stable lessons

Append context from handoff/memory after the briefing under "### Контекст прошлых сессий".
Do NOT show this section if there is nothing relevant.
```

- [ ] **Step 2: Rewrite Step 3 → Step 2: Name Session + Choose Direction with slug template**

Replace current Step 3 (lines 86-114) with:

```markdown
### Step 2: Name Session + Choose Direction

⛔ **MANDATORY GATE** — You MUST complete this step. Do NOT ask "Что хочешь делать?" without proposing a session name. Do NOT proceed to coding without a confirmed name.

The hook provided `slug_template` in GATHER_META with deterministic parts pre-filled:
```
{slug_template}   ← project, milestone, date, time already set
```

You fill `{task}` based on the top-priority issue or user's stated direction. Use 2-4 words, kebab-case.

Examples:
- `agent-skills-{task}-2026-03-26-1430` → `agent-skills-briefing-in-hook-2026-03-26-1430`
- `crypto-p5-{task}-2026-03-26-1015` → `crypto-p5-annotation-layer-2026-03-26-1015`

**Your message MUST contain:**
1. Proposed session name (slug_template with {task} filled in)
2. Which issue(s) you suggest working on and why
3. "Корректируй если нужно."

Wait for user response. Store confirmed name as `SESSION_NAME`.
```

- [ ] **Step 3: Renumber Step 4 → Step 3: Post GitHub Comment + Register**

Current Step 4 (lines 116-147) becomes Step 3. Content stays the same — GitHub comment + registry.py calls.

- [ ] **Step 4: Update metadata version to 2.10.0**

Change frontmatter `version: 2.8.0` → `version: 2.10.0`.

- [ ] **Step 5: Update Common Mistakes table**

Remove rows that no longer apply (manual gather, ignoring GATHER_DATA). Replace with:

```markdown
## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Modifying or supplementing the BRIEFING | Show it verbatim. All data is pre-formatted by the hook |
| Asking "Что хочешь делать?" without session name | Step 2 is a GATE — always propose name first |
| Ignoring slug_template from GATHER_META | Use it — only fill {task}, don't rebuild the slug |
| Start coding without naming session | Name first — handoff path depends on it |
| Trust handoff "What Remains" as task list | Use GitHub open issues — handoff is a stale snapshot |
```

- [ ] **Step 6: Commit**

```bash
git add plugins/h2t/skills/dev-session-start/SKILL.md
git commit -m "feat: SKILL.md shows BRIEFING verbatim, uses slug template, enforces GATE (#19, #20)"
```

---

### Task 5: Integration test + version bump + close issues

**Files:**
- Modify: `plugins/h2t/.claude-plugin/plugin.json`

- [ ] **Step 1: Run all gather tests**

Run: `cd C:/dev/claude-agent-skills && ~/.h2t/venv/Scripts/python.exe -m pytest plugins/h2t/lib/gather/ -v`
Expected: ALL PASS

- [ ] **Step 2: Test hook end-to-end — dev-session-start**

```bash
echo '{"tool_input":{"skill":"h2t:dev-session-start"},"cwd":"C:/dev/claude-agent-skills"}' | bash plugins/h2t/hooks-handlers/gather-on-skill
```

Verify:
- Output contains `BRIEFING:\n## Сессия: agent-skills`
- Output contains `GATHER_META:` with `slug_template` field
- `slug_template` has format `agent-skills-{task}-YYYY-MM-DD-HHMM`
- No `GATHER_DATA:` in output (replaced by `BRIEFING:`)

- [ ] **Step 3: Test hook end-to-end — handoff (regression)**

```bash
echo '{"tool_input":{"skill":"h2t:handoff"},"cwd":"C:/dev/claude-agent-skills"}' | bash plugins/h2t/hooks-handlers/gather-on-skill
```

Verify:
- Output contains `GATHER_DATA:` (NOT `BRIEFING:`) — handoff unchanged
- `_handoff.session_dir` is present

- [ ] **Step 4: Bump version to 2.10.0**

In `plugins/h2t/.claude-plugin/plugin.json`, change `"version": "2.9.1"` → `"version": "2.10.0"`.

- [ ] **Step 5: Commit**

```bash
git add plugins/h2t/.claude-plugin/plugin.json
git commit -m "chore: bump to 2.10.0 — briefing + slug in hook (closes #19, #20, #15)"
```

- [ ] **Step 6: Close GitHub issues**

```bash
gh issue close 19 --comment "Fixed in v2.10.0 — briefing formatted in hook via format_briefing.py, slug template pre-built"
gh issue close 20 --comment "Fixed in v2.10.0 — SKILL.md simplified to 3 steps, GATE enforced with slug template"
gh issue close 15 --comment "Fixed in v2.10.0 — Claude receives pre-formatted BRIEFING, nothing to supplement"
```
