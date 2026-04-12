# h2t-skills: Консолидация репо и дорожная карта

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Консолидировать две рабочие копии в одну, закрыть текущую fix-ветку, и выстроить порядок работ по 35 открытым issues.

**Architecture:** Один репо `C:/dev/h2t-skills` = единственная рабочая копия lichtpfad/h2t-skills. Все миграции идут через phases (milestones). Каждый phase = scaffold plugin → migrate skills → validate.

**Tech Stack:** Claude Code plugins, Python (stdlib + httpx для clients), h2t-graphs API, GitHub Issues/Milestones.

**Shell:** Все команды — bash (Claude Code использует bash на Windows). НЕ PowerShell.

**Preflight:**
```bash
gh auth status          # должен показать logged in
git -C C:/dev/h2t-skills remote -v  # origin = lichtpfad/h2t-skills
```

---

## Phase 0: Консолидац��я рабочих директорий

### Task 0.1: Синхронизировать h2t-skills с remote main

**Проблема:** Локальный `main` в `h2t-skills` отстаёт на ~52 коммита от remote. `claude-agent-skills` синхронизирован с remote main.

**Факты:**
- `h2t-skills` origin/main: `34d07e8` (после fetch — уже синхронизирован)
- fix-ветка `fix/session-start-double-skill-load`: 2 коммита (`74380c4`, `a22d31b`) — дубликаты того что уже в main (`4749108`, `ecb9072`), разные SHA из-за разных author email и squash
- `claude-agent-skills` uncommitted: `.claude/settings.local.json` + правки в plan md

**Files:**
- Modify: `C:/dev/h2t-skills` (git operations)

- [ ] **Step 1: Забрать uncommitted из claude-agent-skills**

```bash
# Сохранить uncommitted файлы
cp C:/dev/claude-agent-skills/.claude/settings.local.json C:/dev/h2t-skills/.claude/settings.local.json
cp C:/dev/claude-agent-skills/docs/superpowers/plans/2026-04-07-skill-graph-foundation.md C:/dev/h2t-skills/docs/superpowers/plans/2026-04-07-skill-graph-foundation.md
```

- [ ] **Step 2: Обновить h2t-skills main**

```bash
cd C:/dev/h2t-skills
git checkout main
git pull origin main
```

Expected: main = `34d07e8`, 213 коммитов.

- [ ] **Step 3: Проверить что всё на месте**

```bash
# Должны существовать:
ls lib/skill_graph/client.py
ls lib/skill_graph/gepa_batch.py
ls plugins/h2t-ops/.claude-plugin/plugin.json
ls docs/superpowers/specs/2026-04-06-skill-intelligence-graph-design.md
ls pyproject.toml
```

- [ ] **Step 4: Удалить fix-ветку (дубликат)**

```bash
git branch -d fix/session-start-double-skill-load
git push origin --delete fix/session-start-double-skill-load
```

Коммиты `a22d31b` и `74380c4` — дубликаты `ecb9072` и `4749108` (уже в main).

- [ ] **Step 5: Закрыть issue #63**

```bash
gh issue close 63 -R lichtpfad/h2t-skills -c "Fix-ветка содержала дубликаты коммитов, уже в main. Удалена."
```

- [ ] **Step 6: Верификация — diff с remote**

```bash
git diff origin/main  # должен быть пустой или только .claude/settings.local.json
```

- [ ] **Step 7: Commit settings + plan**

```bash
git add .claude/settings.local.json docs/superpowers/plans/2026-04-07-skill-graph-foundation.md docs/superpowers/plans/2026-04-12-repo-consolidation-and-roadmap.md
git commit -m "chore: consolidate from claude-agent-skills — settings + plans"
```

### Task 0.2: Удалить claude-agent-skills

**Prereq:** Task 0.1 завершён и верифицирован.

- [ ] **Step 1: Финальная проверка — нет ли чего забыли**

```bash
# Сравнить tracked файлы обоих клонов
git -C C:/dev/claude-agent-skills ls-files | sort > /tmp/cas-files.txt
git -C C:/dev/h2t-skills ls-files | sort > /tmp/hs-files.txt
diff /tmp/cas-files.txt /tmp/hs-files.txt
# Допустимо: creative-thinking/* (вынесен в standalone repo)
```

- [ ] **Step 2: Проверить что мы НЕ запущены из claude-agent-skills**

```bash
pwd  # должен быть C:/dev/h2t-skills, НЕ claude-agent-skills
```

- [ ] **Step 3: Переместить в карантин (с подтверждением пользователя)**

⚠️ **GATE:** Спросить пользователя перед удалением. Показать что будет удалено.

```bash
# Сначала — мягкое удаление (rename). Можно восстановить.
mv C:/dev/claude-agent-skills C:/dev/.trash-claude-agent-skills
echo "Перемещено в C:/dev/.trash-claude-agent-skills"
echo "Удалить окончательно после проверки h2t-skills (вручную или rm -rf)"
```

Окончательное удаление `C:/dev/.trash-claude-agent-skills` — ручной шаг пользователя после того как убедился что всё работает из `h2t-skills`.

- [ ] **Step 4: Обновить memory**

Обновить `reference_skill_best_practices.md` — убрать упоминание `claude-agent-skills`, оставить только `h2t-skills`.

### Task 0.3: Навести порядок в issues

- [ ] **Step 1: Привязать orphan issues к milestones**

| Issue | Milestone |
|-------|-----------|
| #47 (ceo-council) | Backlog — h2t-arch или отдельный creative-thinking milestone |
| #50 (project-audit) | Infra v0.2 |
| #62 (best-practices index) | Infra v0.2 |
| #63 (session-start fix) | закрыт в Task 0.1 |
| #54 (session→graph) | Infra v0.2 |
| #53 (gather CLI Mac) | Infra v0.2 |
| #5 (diagram-node Step 0) | Backlog — h2t-arch |

```bash
gh issue edit 50 -R lichtpfad/h2t-skills --milestone "Infra v0.2 — Gather CLI"
gh issue edit 62 -R lichtpfad/h2t-skills --milestone "Infra v0.2 — Gather CLI"
gh issue edit 54 -R lichtpfad/h2t-skills --milestone "Infra v0.2 — Gather CLI"
gh issue edit 53 -R lichtpfad/h2t-skills --milestone "Infra v0.2 — Gather CLI"
gh issue edit 5 -R lichtpfad/h2t-skills --milestone "Backlog — h2t-arch"
gh issue edit 47 -R lichtpfad/h2t-skills --milestone "Backlog — h2t-arch"
```

- [ ] **Step 2: Commit**

Нет файловых изменений — только GitHub metadata.

---

## Phase 1: Infra v0.2 — Gather CLI (milestone #2)

**Приоритет: HIGH. Не блокирует Phase 2–5 напрямую, но содержит фундаментальные улучшения (credential sync, session→graph) которые улучшают все последующие phases.**

Open: #13, #50, #53, #54, #62 (после привязки)

### Task 1.1: docs: skill best-practices knowledge index (#62)

**Files:**
- Create: `docs/SKILL-BEST-PRACTICES.md`

- [ ] **Step 1: Написать индекс**

Собрать все ссылки из issue #62 в один markdown файл. Структура:
- Эмпирические выводы (6 пунктов из research)
- Ссылки на docs/research/
- Ссылки на specs
- Внешние источники (Anthropic, superpowers)
- Как пользоваться skill-graph API

- [ ] **Step 2: Commit**

```bash
git add docs/SKILL-BEST-PRACTICES.md
git commit -m "docs: add skill best-practices knowledge index (#62)"
```

- [ ] **Step 3: Закрыть issue**

```bash
gh issue close 62 -R lichtpfad/h2t-skills
```

### Task 1.2: cross-machine credential sync (#13)

**Scope:** OAuth tokens (gmail, calendar, notion), Telegram session, h2t-graphs tokens.

- [ ] **Step 1: Исследовать текущее состояние** — какие файлы, где лежат, как используются
- [ ] **Step 2: Выбрать механизм** — варианты: Syncthing (уже есть?), git-crypt, sops, manual rsync
- [ ] **Step 3: Реализовать** — зависит от выбора
- [ ] **Step 4: Документировать** — `docs/credentials-sync.md`

### Task 1.3: h2t gather CLI на Mac (#53)

- [ ] **Step 1: Проверить `pyproject.toml` entry points**
- [ ] **Step 2: Написать инструкцию для `uv pip install -e .`**
- [ ] **Step 3: Протестировать на Mac** (ручной шаг)

### Task 1.4: Session → Graph mapping (#54)

- [ ] **Step 1: Дизайн** — какие данные из session пишем в h2t-graphs (source: `sessions`)
- [ ] **Step 2: Интеграция в handoff** — при `activity_log.py start/end` пишем node
- [ ] **Step 3: Тесты**

### Task 1.5: migrate project-audit (#50)

- [ ] **Step 1: Найти текущий project-audit в монолите**
- [ ] **Step 2: Перенести в `plugins/h2t-core/skills/project-audit/`**
- [ ] **Step 3: Обновить SKILL.md под v3 паттерн (pipeline)**
- [ ] **Step 4: Тесты**

---

## Phase 2: h2t-dev (milestone #3)

**Prereq:** Phase 0 done. Может идти параллельно с Phase 1 — миграции skills не зависят от infra improvements.

Open: #18, #26, #27, #28, #29, #30

### Task 2.0: scaffold h2t-dev plugin (#26)

**Files:**
- Create: `plugins/h2t-dev/.claude-plugin/plugin.json`
- Create: `plugins/h2t-dev/commands/` (pre-merge-check, github-issues, gh-memory, milestone-closure)
- Create: `plugins/h2t-dev/skills/` (dirs per skill)

- [ ] **Step 1: Создать plugin.json** — по образцу h2t-ops или h2t-core
- [ ] **Step 2: Создать пустую структуру commands/ и skills/**
- [ ] **Step 3: Commit**

```bash
git add plugins/h2t-dev/
git commit -m "feat(h2t-dev): scaffold plugin (#26)"
```

### Task 2.1–2.4: Миграция skills

Каждая миграция — одинаковый паттерн:

1. Найти текущий skill в монолите (`plugins/h2t/skills/<name>/`)
2. Скопировать в `plugins/h2t-dev/skills/<name>/`
3. Обновить SKILL.md: third-person description, v3 pipeline если применимо
4. Добавить command в `plugins/h2t-dev/commands/<name>.md`
5. Удалить из монолита
6. Commit + close issue

| Task | Skill | Issue | Сложность |
|------|-------|-------|-----------|
| 2.1 | pre-merge-check | #27 | low — чистый SKILL.md |
| 2.2 | github-issues | #28 | low |
| 2.3 | gh-memory | #29 | low |
| 2.4 | milestone-closure | #30 | low |

### Task 2.5: scaffold-project (#18)

Зависит от v3 architecture decisions. Может быть отложен.

---

## Phase 3: h2t-ops (milestone #4)

**Prereq:** Phase 0 done.
**Статус:** Plugin уже scaffolded и skills мигрированы в remote main (Wave 2, коммит `1e2a53c`). После Phase 0 всё будет в `h2t-skills`.

Open: #31, #32, #33, #34, #35, #36, #37

### Task 3.0: Верификация h2t-ops

- [ ] **Step 1: Проверить что scaffold и skills уже в main**

```bash
ls plugins/h2t-ops/.claude-plugin/plugin.json
ls plugins/h2t-ops/skills/gmail/SKILL.md
ls plugins/h2t-ops/skills/calendar/SKILL.md
ls plugins/h2t-ops/skills/notion/SKILL.md
ls plugins/h2t-ops/skills/telegram/SKILL.md
ls plugins/h2t-ops/skills/daily-brief/SKILL.md
```

- [ ] **Step 2: Если всё на месте — закрыть issues #31–#36**

```bash
gh issue close 31 -R lichtpfad/h2t-skills -c "Already in main (Wave 2 migration)"
gh issue close 32 -R lichtpfad/h2t-skills -c "Already in main (Wave 2 migration)"
gh issue close 33 -R lichtpfad/h2t-skills -c "Already in main (Wave 2 migration)"
gh issue close 34 -R lichtpfad/h2t-skills -c "Already in main (Wave 2 migration)"
gh issue close 35 -R lichtpfad/h2t-skills -c "Already in main (Wave 2 migration)"
gh issue close 36 -R lichtpfad/h2t-skills -c "Already in main (Wave 2 migration)"
```

### Task 3.1: migrate drive (#37)

- [ ] **Step 1: Найти drive skill в монолите**
- [ ] **Step 2: Перенести в `plugins/h2t-ops/skills/drive/`**
- [ ] **Step 3: Commit + close**

---

## Phase 4: h2t-edu (milestone #5)

Open: #38, #39, #40, #41, #42

### Task 4.0: scaffold h2t-edu plugin (#38)

Аналогично Task 2.0.

### Task 4.1–4.4: Миграция skills

| Task | Skill | Issue |
|------|-------|-------|
| 4.1 | process-transcripts | #39 |
| 4.2 | youtube-transcript | #40 |
| 4.3 | convert-meeting-transcript | #41 |
| 4.4 | lesson-parser | #42 |

---

## Phase 5: h2t-creative (milestone #6)

Open: #43, #44, #45, #46

### Task 5.0: scaffold h2t-creative plugin (#43)

### Task 5.1–5.3: Миграция skills

| Task | Skill | Issue |
|------|-------|-------|
| 5.1 | deck | #44 |
| 5.2 | design | #45 |
| 5.3 | landing | #46 |

---

## Backlog: h2t-arch (milestone #7)

Open: #5, #47, #48, #49, #51

Не блокирует phases. Делать по мере необходимости.

| Issue | Skill | Зависимости |
|-------|-------|-------------|
| #48 | drawio | — |
| #49 | diagram-node | — |
| #51 | node-researcher | — |
| #47 | ceo-council | creative-thinking standalone repo |
| #5 | diagram-node Step 0 | #49 |

---

## Backlog: h2t-tools (milestone #8)

Open: #52

| Issue | Skill |
|-------|-------|
| #52 | nlm (NotebookLM) |

---

## Порядок выполнения

```
Phase 0 (консолидация)          ← СЕЙЧАС, блокирует всё
  ↓
Phase 3.0 (верификация h2t-ops)  ← быстрая победа, только закрыть issues
  ↓
┌─────────────────────────────────────────────┐
│  Phase 1 (infra)  ←──→  Phase 2 (h2t-dev)  │  параллельно, независимы
│  Phase 1 улучшает инфру, Phase 2 мигрирует  │  друг от друга
│  skills — пересечений нет                   │
└─────────────────────────────────────────────┘
  ↓
Phase 4 (h2t-edu)
  ↓
Phase 5 (h2t-creative)
  ↓
Backlog (arch + tools)           ← по мере необходимости
```

**Правило запуска:** Phase 0 → обязательно первым. После него Phase 1 и Phase 2 могут идти в любом порядке или параллельно. Phase 4, 5 — последовательно (каждая scaffold + migrate). Backlog — без блокировок.

**Оценка:** Phase 0 + Phase 3.0 = одна сессия. Phase 2 = одна сессия (4 простых миграции). Phase 4–5 = по одной сессии каждая.

---

## Summary: 35 open issues

| Категория | Issues | Статус |
|-----------|--------|--------|
| Phase 0: консолидация | #63 | закрыть сейчас |
| Phase 1: infra | #13, #50, #53, #54, #62 | next |
| Phase 2: h2t-dev | #18, #26–#30 | scaffold + 4 миграции |
| Phase 3: h2t-ops | #31–#37 | 6 из 7 уже сделаны, закрыть |
| Phase 4: h2t-edu | #38–#42 | scaffold + 4 миграции |
| Phase 5: h2t-creative | #43–#46 | scaffold + 3 миграции |
| Backlog: arch | #5, #47–#49, #51 | 5 issues |
| Backlog: tools | #52 | 1 issue |
| Cross-cutting | #21 (master h2t-graphs) | ongoing |
