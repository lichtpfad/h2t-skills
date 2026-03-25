# ADR-001: Context Assembly Framework (lib/gather)

**Status:** Accepted
**Date:** 2026-03-25
**Author:** Станислав Глазов + Claude
**Issues:** #7, #8, #9, #10, #11
**Milestone:** Gather Framework v0.1

## Decision

Создаём `plugins/h2t/lib/gather/` — Python-пакет для параллельного сбора контекста из произвольных источников. Скиллы вызывают один скрипт (`gather.py`) вместо 10+ отдельных bash-команд.

## Context

### Проблема 1: Производительность
Скилл `dev-session-start` делает 10-12 отдельных tool calls (git × 4, gh × 4-5, ls sessions, stack detection). Каждый tool call — 2-5 секунд roundtrip. Общее время: 20-60 секунд на сбор контекста.

### Проблема 2: Не только git
Не все проекты — git-репозитории. Dropbox-папки (HOU2TOUCH), Obsidian vaults — тоже рабочие директории. Gather должен идентифицировать проект из **любой** директории через `repo-mapping.yaml` + `cwd_patterns`.

### Проблема 3: Отсутствие eval
creative-thinking имеет hook-based eval для graph queries, но нет общего паттерна для оценки эффективности скиллов. Gather — естественная точка для автоматического трекинга.

### Проблема 4: Рост источников
Сегодня: git, GitHub, session files. Завтра: Notion, Calendar, Linear, Obsidian. Нужна модульная архитектура.

## Architecture

### Progressive Disclosure — 4 слоя

```
Layer 0 — Identity (always, instant)
  Who: user context (about-me/core.md)
  What: project identity (domain, type, github remote)
  Where: machine name
  Source: ~/.h2t/config/ (repo-mapping.yaml, domains.yaml, about-me/)

Layer 1 — State (fast, local)
  Git: branch, status, log, stash
  Stack: detected from marker files (package.json, pyproject.toml, etc.)
  Source: local subprocess (git, filesystem)

Layer 2 — Work Context (API calls, parallel)
  GitHub: issues, milestones, PRs, bugs
  Sessions: handoff file paths across machines
  Source: gh CLI, ~/.dor/sessions/

Layer 3 — Deep Context (on demand, pluggable)
  Session content: actual handoff file contents
  User context: psychology.md, strategy.md (domain-dependent)
  Registry: active sessions across machines
  Future: Notion tasks, Google Calendar, Obsidian search
  Source: file reads, external APIs
```

Скилл декларирует нужные слои:
```python
gather(layers=[0, 1, 2], deep=["sessions", "about_me"], skill_name="dev-session-start")
```

### Module Structure

```
plugins/h2t/lib/gather/
  __init__.py           ← gather(layers=, deep=) main API
  runner.py             ← ThreadPoolExecutor parallel runner
  project.py            ← Layer 0: identify_project(cwd) via registry resolve
  user.py               ← Layer 0: user context (about-me/)
  git.py                ← Layer 1: git info
  stack.py              ← Layer 1: stack detection
  github.py             ← Layer 2: issues, milestones, PRs
  sessions.py           ← Layer 2: session file discovery
  eval.py               ← Auto-tracking: duration, sources, errors
  sources/              ← Layer 3: pluggable deep context
    __init__.py
    about_me.py
    session_content.py
    registry.py
    # future: notion.py, calendar.py, obsidian.py
```

### Per-Skill Gatherers

```
skills/{skill-name}/gather.py  ← thin script composing lib modules
```

Each skill's gather.py:
1. Imports from `lib/gather/`
2. Declares which layers + deep sources it needs
3. Outputs JSON to stdout
4. One `$H2T_PYTHON gather.py` call replaces all context collection

### Eval Integration

Two levels:
- **Level 1 (automatic):** `gather()` records duration, sources used/failed, context size → `~/.h2t/evals/{skill}/`
- **Level 2 (skill-specific):** skill declares custom metrics (step6_completed, etc.)

Unified storage: `~/.h2t/evals/{skill_name}/sessions/{id}.json`

### Registry Backend Abstraction

```python
class RegistryBackend:
    def append(self, record: dict) -> None: ...
    def query(self, **filters) -> list[dict]: ...
    def update(self, id: str, **fields) -> None: ...
```

Today: `JsonlBackend` (file on disk, synced via Syncthing)
Future: `SqliteBackend` → `PostgresBackend` (when VPS)

### Domain-Aware Context Routing

Project domain determines which deep sources are auto-loaded:
- `personal-os` → about_me, psychology, strategy
- `hou2touch` → about_me, courses, notion
- `crypto` → about_me, strategy
- `default` → about_me

## Alternatives Considered

### 1. Bash script instead of Python
Rejected. JSON assembly in bash is fragile, `jq` not always on Windows, no parallelism, no cross-platform.

### 2. Single monolithic gather script
Rejected. Different skills need different subsets of context. Modular > monolithic.

### 3. Each skill gathers its own context inline
Current state. Rejected — massive duplication, no shared optimization, no eval tracking.

### 4. MCP server for context
Considered for future. Too heavy for v0.1 — simple subprocess + JSON is sufficient. Could wrap gather as MCP tool later.

## Constraints

- **Python 3.10+ stdlib only** — no external dependencies in lib/gather/
- **Cross-platform** — Windows (git-bash) + macOS
- **H2T venv** — executed via `$H2T_PYTHON` (already installed on both machines)
- **One tool call** — gather.py must complete in a single subprocess invocation
- **Backward compatible** — existing SKILL.md structure preserved, gather is additive

## Consequences

### Positive
- 10× fewer tool calls per skill invocation
- Consistent project identity from any directory
- Eval tracking comes free with gather
- New context sources added as modules, not rewrites
- Cross-platform by design

### Negative
- Python dependency (but h2t venv already exists)
- registry.py coupling (project.py depends on it)
- Need to maintain lib/gather/ as shared code

### Risks
- `gh` CLI auth may fail silently → mitigated by sources_failed tracking
- registry.py API may change → mitigated by subprocess call (not import)
- Large context from Layer 3 may bloat prompts → mitigated by progressive disclosure

## Implementation Plan

See: `docs/plans/2026-03-25-gather-framework.md`

Milestone: Gather Framework v0.1
Issues: #7 (runner), #8 (modules), #9 (project+user), #10 (eval), #11 (dev-session-start)
