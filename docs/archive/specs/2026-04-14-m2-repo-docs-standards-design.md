---
title: "Repo & Docs Standards — Full Design"
status: "draft"
owner: "lichtpfad"
date: "2026-04-14"
milestone: "M2"
---

# Repo & Docs Standards — Full Design

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Зафиксировать полный стандарт структуры репо и документации для всей h2t-* экосистемы, обновить enforcement скиллы, провести клинап Tier-A репо.

**Scope:** 3 standards файла в `C:/dev/docs/standards/` + обновление h2t-dev скиллов + клинап 6 Tier-A репо.

**Research:** 2026-04-14, два агента — docs lifecycle best practices + repo file structure conventions.

---

## Part 1: Repo Root Standard (`repo-structure.md`)

### MUST (обязательно в каждом репо)

```
README.md          # Обзор репо, quickstart
CLAUDE.md          # Инструкции для AI-агентов (см. шаблон ниже)
pyproject.toml     # Единая точка конфигурации (не setup.py, не requirements.txt)
.gitignore
```

### SHOULD (стандартные директории — если нет, нужна причина)

```
src/               # Importable library/application code (src-layout)
tests/             # Automated tests
docs/              # Human-readable documentation
scripts/           # Maintenance, migration, operational scripts (не importable)
```

**`src/` vs `scripts/`:**
- `src/` = всё что проходит `import` и тесты
- `scripts/` = тонкие entrypoints, оркестрирующие код из `src/`; одноразовые операции
- Скрипты с бизнес-логикой → рефактор в `src/`, оставить тонкий entrypoint

### MAY (условные — только если применимо)

```
data/              # Machine-readable: JSON реестры, ML датасеты, ground truth, eval inputs
assets/            # Human-facing static: диаграммы, скриншоты, UI-иконки, презентации
tools/             # Dev utilities для разработчиков репо (annotators, viewers, codegen)
knowledge/         # Curated agent context: reference docs, domain patterns, expertise
evals/             # Eval registration для h2t-evals системы (repo.toml + baselines)
landing/           # Marketing/static web site (лёгкий HTML/CSS/JS лендинг)
frontend/          # Full web application (SPA, React и т.п.)
config/            # Versioned non-secret configuration (yaml/toml, env overlays)
deploy/            # Deployment manifests, compose, infra glue
migrations/        # DB/schema migrations
hooks/             # Repo/dev automation hooks (НЕ application hooks)
examples/          # Minimal reproducible usage examples, demo configs, sample apps
```

### Root-level files: разрешены

Governance:
- `README.md`, `CLAUDE.md`, `CHANGELOG.md`, `CONTRIBUTING.md`, `LICENSE`, `SECURITY.md`

Repo/tooling config:
- `Dockerfile`, `compose.yaml`, `Makefile`, `.env.example`
- `pytest.ini`, `ruff.toml`, `mypy.ini`, `mkdocs.yml`, `uv.lock`, `pyproject.toml`
- `llms.txt` — рекомендован для service repos / agent-facing repos

### MUST NOT (запрещено в корне)

```
*.png, *.jpg, *.pdf     → assets/diagrams/ или assets/screenshots/
*.py скрипты            → scripts/ (если одноразовые) или src/ (если importable)
*.db                    → gitignored; никогда не коммитить
setup.py                → использовать только pyproject.toml
Floating domain docs:
  STRATEGY.md, roadmap.md, API_specification.md, HANDOFF.md,
  DATA_SOURCES.md, service-one-pager.md, vps-architecture.md
backup*, temp*, old*    → удалить
```

### .gitignore defaults (добавить во все репо)

```gitignore
# Python
.venv/
venv/
__pycache__/
*.pyc
*.pyo
dist/
build/

# Runtime artifacts
*.db
*.log
logs/
backups/
artifacts/
.cache/
.artifacts/

# ML
data/models/
data/bench/*.jpg
data/bench/*.png

# Generated
dist/
*.egg-info/
```

---

## Part 2: assets/ vs data/ — граница

| Критерий | `assets/` | `data/` |
|----------|-----------|---------|
| Кто читает | Люди, UI, браузер | Код, пайплайн, агенты |
| Формат | PNG, SVG, PDF, HTML | JSON, YAML, JSONL, CSV |
| Цель | Отображение, презентация | Runtime input, eval, ML |
| Меняется | Редко, вручную | Может генерироваться |

**Примеры:**
- `icons/` используется приложением → `assets/icons/`
- `icons/` — датасет для ML анализа → `data/icons/`
- `registry/` JSON операторов читает код → `data/registry/`
- `diagram-arch.png` для README → `assets/diagrams/`
- `ground_truth/*.json` для eval → `data/ground_truth/`
- `models/*.safetensors` → `data/models/` + gitignored

### Рекомендованная структура assets/

```
assets/
  diagrams/        # Архитектурные диаграммы, flow charts
  screenshots/     # UI screenshots, editor states
  presentations/   # Slide decks, PDF
```

### Рекомендованная структура data/

```
data/
  registry/        # Operator/entity registries (JSON)
  ground_truth/    # Eval ground truth labels
  models/          # ML model weights (gitignored)
  bench/           # Benchmark datasets (images gitignored)
  knowledge/       # Curated reference data (если не в knowledge/ top-level)
```

---

## Part 3: Hooks — три класса

| Класс | Место | Что туда идёт |
|-------|-------|---------------|
| Repo/dev automation | root `hooks/` | git hooks, dev workflow automation |
| Claude Code | `.claude/` | settings.json, commands/, rules/ |
| Application/runtime | `src/.../hooks/` | callback handlers, event hooks в коде |

**MUST NOT:** `hooks-handlers/` как имя директории → переименовать в `hooks/`  
**MUST NOT:** Application hooks в root `hooks/`

### `.claude/` structure (если репо использует Claude Code)

```
.claude/
  settings.json      # или settings.local.json
  commands/          # Custom slash commands
  rules/             # Domain rules для Claude
    documentation.md
    coding.md
```

---

## Part 4: knowledge/ directory

Для репо с curated domain knowledge (как h2t-ai с Houdini/TD экспертизой):

```
knowledge/
  references/      # External API docs, patterns, recipes
  expertise/       # Distilled domain expertise
  patterns/        # Code patterns, network recipes
  glossary/        # Domain terminology
```

**Граница с docs/:**
- `docs/` = документация о репо (как он устроен, как его использовать)
- `knowledge/` = предметное знание (Houdini операторы, TD паттерны, domain expertise)

---

## Part 5: Prompts и Fixtures

### LLM Prompts

| Где используется | Куда |
|-----------------|------|
| Кодом во время runtime | `src/.../prompts/` |
| Скриптами вручную | `scripts/prompts/` |
| Как reference/example | `docs/guides/prompts.md` |
| **Никогда:** | `docs/prompts/` |

### Test fixtures и script inputs

```
tests/fixtures/    # Тестовые входные данные
scripts/fixtures/  # Входные данные для скриптов
data/              # Датасеты для pipeline/eval
```

**MUST NOT:** PNG/MD тест-данные вперемешку со скриптами в `scripts/`

---

## Part 6: Frontend

| Тип | Директория |
|-----|-----------|
| Marketing/static лендинг | `landing/` |
| Full SPA/web app | `frontend/` |
| Backend API | `src/` |

`landing/` содержит HTML, CSS, JS, PNG для marketing page.  
`frontend/` содержит полноценный React/Vue/etc проект.

---

## Part 7: Cross-repo docs

- **Local explanatory copy** (объяснение соседних сервисов для понимания текущего) → `docs/architecture/ecosystem/`
- **Canonical cross-repo SSOT** → только в `h2t-infra` (`C:/dev/docs/`)
- **Запрещено:** `docs/concepts/` как имя → переименовать в `docs/architecture/`

---

## Part 8: `llms.txt`

Рекомендован для:
- Service repos с HTTP API (h2t-graphs, h2t-evals)
- Agent-facing repos (h2t-skills, h2t-ai)

Структура: краткое описание репо, production URL, auth, key endpoints, repo layout.

---

## Part 9: `CLAUDE.md` template

Обязательные секции в каждом `CLAUDE.md`:

```markdown
# {Repo Name}

## Purpose
One paragraph: что делает репо, место в экосистеме.

## Setup
Как запустить: venv, зависимости, конфиги.

## Key Commands
Команды для разработки: тесты, lint, run.

## Architecture
2-3 предложения об устройстве + ключевые директории.

## Conventions
Что важно знать агенту: naming, паттерны, ограничения.

## Do / Don't
Явные правила: что можно, что нельзя делать в этом репо.

## Important Files
Ключевые файлы с путями и пояснениями.
```

---

## Part 10: docs/ structure (обновление documentation-structure.md)

### MUST (всегда)

```
docs/
  README.md                  # Navigation index (Quick Links на директории)
  superpowers/
    specs/                   # Design specs: YYYY-MM-DD-mN-kebab-design.md
    plans/                   # Impl plans: YYYY-MM-DD-mN-kebab.md
  adr/                       # NNNN-kebab.md + index.md
  reports/                   # mN-topic-report.md (immutable)
  archive/
    plans/                   # Completed plans (git mv, не git rm)
    specs/                   # Completed specs со status: implemented
```

### MAY (conditional)

```
  product/                   # projects.yaml.docs.positioning = true
  client/                    # Repo exposes public API
  architecture/              # Complex internal architecture
    mockups/                 # UI wireframes (frontend projects)
    diagrams/                # System diagrams (если не в assets/)
    ecosystem/               # Cross-repo explanatory docs
  guides/                    # External users / onboarding
  research/                  # YYYY-MM-DD-topic.md (exploratory)
  marketing/                 # projects.yaml.docs.marketing_docs = true
  ops/                       # Operational runbooks (h2t-evals, h2t-graphs)
  contracts/                 # Service contracts (h2t-evals)
  methodology/               # Domain methodology (h2t-transcription)
  diagrams/                  # Pipeline diagrams (h2t-transcription)
  presentation/              # Presentation materials (h2t-vision)
  .artifacts/                # Ephemeral operational data (gitignored)
```

### Floating files в docs/: куда переносить

| Файл | Куда |
|------|------|
| STRATEGY.md | `docs/product/strategy.md` |
| roadmap.md | `docs/product/roadmap.md` |
| API_specification.md | `docs/client/api-spec.md` |
| service-one-pager.md | `docs/product/one-pager.md` |
| vps-architecture.md | `docs/architecture/vps.md` |
| audit-*.md (не ADR) | `docs/reports/` |
| DROPBOX_ASSET_INVENTORY.md | `docs/product/` |
| FULL_TREE.md | удалить (generated) |
| TOOLKIT_FOR_EXTERNAL_AGENTS.md | `docs/guides/agent-toolkit.md` |
| *.backup | удалить немедленно |

### MUST NOT в docs/

```
docs/plans/        → legacy, migrate to docs/superpowers/plans/ или archive
docs/specs/        → legacy, migrate to docs/superpowers/specs/
docs/handoff/      → stale, git rm (handoffs теперь в .dor/)
docs/eval/         → moved to h2t-evals, git rm из h2t-ai
docs/scripts/      → move to root scripts/
docs/prompts/      → move to src/.../prompts/ или docs/guides/
docs/concepts/     → rename to docs/architecture/
*.html             → move to landing/ (root)
*.pdf              → move to assets/ (root)
backup files       → удалить немедленно
```

---

## Part 11: Naming conventions update

| Тип файла | Формат | Пример |
|-----------|--------|--------|
| Specs | `YYYY-MM-DD-mN-kebab-design.md` | `2026-04-14-m2-graph-query-design.md` |
| Plans | `YYYY-MM-DD-mN-kebab.md` | `2026-04-14-m2-graph-query.md` |
| ADR | `NNNN-kebab-case.md` | `0003-use-sqlite.md` |
| Reports | `mN-topic-report.md` | `m8-ground-truth-report.md` |
| Research | `YYYY-MM-DD-topic.md` | `2026-03-19-graph-db-analysis.md` |
| Product docs | `kebab-case.md` | `positioning.md`, `roadmap.md` |

**Frontmatter required:**
- Specs: `title`, `status`, `owner`, `date`, `milestone`
- Plans: `title`, `status`, `date`, `milestone`
- ADR: `title`, `status`, `date`

**Docs lifecycle:**
- Completed plans → `git mv docs/superpowers/plans/X docs/archive/plans/X`
- Completed specs → добавить `status: implemented` в frontmatter, оставить на месте
- `git rm` без перемещения → **запрещено** (потеря контекста)

---

## Part 12: Skills — что реализовать

### Обновить: `documentation-structure.md`
- Убрать grandfathered исключения h2t-ai
- Добавить `archive/plans/`, `archive/specs/`
- Добавить lifecycle правила
- Добавить conditional dirs list (ops, contracts, methodology, etc.)

### Создать: `repo-structure.md`
- Весь Part 1 этого документа в нормативном стиле MUST/SHOULD/MAY/MUST NOT

### Обновить: `naming-conventions.md`
- Добавить `mN` в форматы specs и plans

### Обновить: `docs-lint` skill
- Детектировать legacy dirs (plans/, specs/, handoff/, eval/, concepts/, prompts/, scripts/ в docs/)
- Проверять naming: specs имеют `YYYY-MM-DD-mN-` prefix
- Проверять корень репо: запрещённые floating files

### Обновить: `docs-cleanup` skill
- `--legacy-dirs`: `git mv docs/plans/ → docs/archive/plans/`, `docs/specs/ → docs/superpowers/specs/`
- `--migrate-data`: `git mv docs/registry/ → data/registry/` и подобное

### Переписать: `docs-index` skill
- Navigation template (Quick Links на директории)
- ADR table ниже
- Не инвентарь файлов

### Создать: `repo-audit` skill
- Аудит root: floating files, запрещённые папки, gitignore
- Аудит data/ vs docs/ misplacement
- `--fix`: предлагает git mv команды

---

## Part 13: Per-repo cleanup plan (Tier-A)

### h2t-ai (самый грязный)

```bash
# docs/ → data/
git mv docs/registry/ data/registry/
git mv docs/hou-api/ data/hou-api/
git mv docs/td-api/ data/td-api/
git mv docs/td-operator-params/ data/td-operator-params/

# stale docs/
git rm -r docs/handoff/      # → .dor/sessions/
git rm -r docs/eval/         # → moved to h2t-evals
git rm -r docs/context7-cache/  # → .cache/ или gitignore

# legacy docs/
git mv docs/plans/ docs/archive/plans/
git mv docs/specs/ docs/superpowers/specs/

# floating docs/
git mv docs/graph/extension-field-contract.md docs/architecture/
git mv docs/integration/h2t-graphs-integration.md docs/architecture/

# root
git rm eval.db               # → gitignored
git rm hou2touch_ai_platform_concept.md  # → docs/product/ или удалить
git rm DOMAINS.md            # → docs/architecture/ или README

# references/ + expertise/ → knowledge/
git mv references/ knowledge/references/
git mv expertise/ knowledge/expertise/
```

### h2t-transcription

```bash
# 28 PNG в корне → assets/
mkdir -p assets/screenshots assets/diagrams
git mv deck-*.png assets/presentations/
git mv editor-*.png assets/screenshots/
git mv studio-*.png assets/screenshots/
git mv landing-*.png assets/screenshots/
git mv final-cards.png assets/screenshots/
git mv *.pdf assets/presentations/
git mv snap_studio.py scripts/

# docs/ legacy
git mv docs/plans/ docs/archive/plans/
git mv docs/specs/ docs/superpowers/specs/
git mv docs/mockups/ docs/architecture/mockups/
git mv docs/prompts/ docs/guides/prompts/  # или src/prompts/

# floating docs/
git mv docs/STRATEGY.md docs/product/strategy.md
git mv docs/roadmap.md docs/product/roadmap.md
git mv docs/DROPBOX_ASSET_INVENTORY.md docs/product/
git rm docs/FULL_TREE.md     # generated file
git mv docs/audit-combined-2026-03-17.md docs/reports/
```

### h2t-graphs

```bash
# root PNG → assets/
mkdir -p assets/diagrams
git mv diagram-*.png assets/diagrams/
git mv landing-*.png assets/screenshots/
git rm HANDOFF.md             # stale
git mv DATA_SOURCES.md docs/architecture/data-sources.md
git rm setup.py              # pyproject.toml достаточно

# build/ → rename
git mv build/ scripts/build/  # или влить в scripts/

# artifacts/ → gitignore
echo "artifacts/" >> .gitignore
# (если нужно хранить → data/artifacts/ и gitignore большие файлы)

# docs/
git mv docs/scripts/ scripts/gh-tools/
git mv docs/concepts/ docs/architecture/
git mv docs/API_specification.md docs/client/api-spec.md
git mv docs/implementation-roadmap.md docs/product/roadmap.md
git mv docs/service-one-pager.md docs/product/one-pager.md
git mv docs/vps-architecture.md docs/architecture/vps.md
git rm docs/landing.html      # → landing/ root или удалить
```

### h2t-evals

```bash
# root
git rm -r backups/           # → gitignored
echo "backups/" >> .gitignore
git rm -r logs/              # → gitignored
echo "logs/" >> .gitignore
git rm -r nimbalyst-local/   # 0 файлов, мусор

# docs/ floating
git mv docs/service-one-pager.md docs/product/one-pager.md
```

### h2t-vision

```bash
# root data/
mkdir -p data
git mv ground_truth/ data/ground_truth/
git mv icons/ data/icons/      # ML датасет, не UI assets
# models/ → gitignored (ML weights)
echo "data/models/" >> .gitignore
# bench/ images → gitignored
echo "data/bench/*.jpg" >> .gitignore

# docs/ legacy
git mv docs/handoff/ docs/archive/handoff/  # или git rm
git mv docs/plans/ docs/archive/plans/
git mv docs/specs/ docs/superpowers/specs/

# docs/ floating
git mv docs/mvp_blueprint_v1.md docs/product/
git mv docs/TOOLKIT_FOR_EXTERNAL_AGENTS.md docs/guides/agent-toolkit.md
git mv docs/EXTERNAL_AGENT_GUIDE.md docs/guides/
git mv docs/usage-vision-cli.md docs/client/
git rm docs/factory.txt      # что это?
git mv docs/setup-ndi.md docs/guides/
```

### h2t-skills

```bash
# root
git rm requirements.txt      # → pyproject.toml

# docs/ floating
git rm docs/CLAUDE.md.backup-2026-04-05   # немедленно
git mv docs/article-gather-framework.md docs/research/
git mv docs/briefing-for-evals-agent.md docs/guides/
git mv docs/gather-agent-instructions.md docs/guides/
git mv docs/SKILL-BEST-PRACTICES.md docs/guides/
git mv docs/plans/2026-03-25-gather-framework.md docs/archive/plans/

# hooks-handlers/ → rename
git mv hooks-handlers/ hooks/
```

---

## Приоритет реализации

| Приоритет | Задача |
|-----------|--------|
| P0 | Создать `repo-structure.md` (новый стандарт) |
| P0 | Обновить `documentation-structure.md` (убрать ошибки) |
| P0 | Обновить `naming-conventions.md` (mN prefix) |
| P1 | `docs-lint`: добавить legacy dirs + naming checks |
| P1 | `docs-cleanup`: добавить `--legacy-dirs` + `--migrate-data` |
| P1 | `docs-index`: переписать под navigation template |
| P2 | `repo-audit`: новый скилл |
| P3 | Клинап h2t-ai (самый приоритетный из репо) |
| P3 | Клинап остальных Tier-A по плану выше |
