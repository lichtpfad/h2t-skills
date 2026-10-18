---
title: "Записи в репозиторий пользователя: замер (#548, Task 17)"
status: "active"
date: "2026-10-18"
---

# Записи в репозиторий пользователя: замер

Отчёт к Task 17 плана `docs/superpowers/plans/2026-10-17-storage-and-governance.md`.
Он сверяет таблицу «Список записей в `repo`» спеки (§7.1) с тем, что команды пишут на деле.

## Как мерили

Каждую команду запускали во временном git-репозитории на коде `c8170304`, до перевода на
`store.repo`. Сценарии — функции `REPO_SCENARIOS` в `tests/governance/sandbox_cases.py`,
аргументы взяты из тестов команд в `tests/tools`, `tests/lifecycle`, `tests/hooks`,
`tests/scaffold`. До и после прогона снимались два среза:

- `git status --porcelain --untracked-files=all`;
- sha256 каждого файла дерева и список каталогов, из `.git` — только `info/exclude`.

Второй срез нужен, потому что первый не видит игнорируемых файлов, пустых каталогов и
`.git/info/exclude`. Тот же срез повторяет `tests/governance/test_repo_writers.py`: он
сверяет каждый изменённый путь с `REPO_WRITERS[команда]`.

На коде до перевода у каждой из 18 команд были записи мимо `store`. `Recorder`, который
сторожит временный каталог, насчитал от 1 до 27 таких событий на команду.

## Команды и пути

Операции — это методы `RepoWriter`: `create` создаёт файл, если его нет; `replace`
заменяет атомарно; `append` дописывает строку; `rename` переносит файл (`git mv`, а для
неотслеживаемого файла — простой перенос); `mkdir` создаёт пустой каталог.

| Команда (ключ `REPO_WRITERS`) | Что пишет | Правило перезаписи |
|---|---|---|
| `h2t-scaffold-project` | `.gitignore`, `README.md`, `CLAUDE.md`, `docs/.artifacts/.gitkeep`, `.h2t/structure.yaml` | `create` — создать, если нет |
| | `.claude/settings.json` | `replace` — слияние с прежним содержимым |
| | `.h2t/project-setup-report.json` | `replace` |
| | `.git/info/exclude` (строка `.h2t/lifecycle/*.json`) | `append`, если строки нет. В worktree файл лежит в основном репозитории, путь называет `git rev-parse --git-path`, запись идёт через `store.append(..., dest=True)` |
| | корневые каталоги типа проекта: `src`, `tests`, `docs`, `scripts`, `data`, `deliverables`, `assets`, `exports` | `mkdir` |
| | всё, что пишет `h2t-docs-init` | дочерний процесс, правила `h2t-docs-init` |
| `h2t-docs-init` | `docs/<раздел>/.gitkeep`, `docs/README.md`, `.claude/rules/documentation.md`, `.claude/rules/docs-lint.yaml`, `.pymarkdown.yaml`, `.vale.ini`, `.h2t/lint-state.jsonl` | `create` |
| | `.gitignore` | `append` недостающих строк |
| `h2t-docs-lint fix-safe` | `docs/<раздел>/.gitkeep` | `create` |
| | каталоги шаблона из `docs-lint.yaml` и `create_dir` из плана | `mkdir` |
| | `docs/**/*.md` (недостающие поля frontmatter) | `replace` |
| | `.gitignore` (шаблоны временных файлов) | `replace` |
| | `docs/**` → `deliverables/**` (отслеживаемые html/pdf/…) | `rename` через `git mv` |
| | `.h2t/lint-apply-<ts>.json` (режим `--plan`) | `replace` |
| `h2t-docs-lint fix-index` | `docs/README.md` | `replace` между маркерами или дописать раздел |
| | `.h2t/lint-apply-<ts>.json` (режим `--plan`) | `replace` |
| `h2t-docs-lint retire` | `docs/superpowers/{plans,specs}/*` → `docs/archive/{plans,specs}/*` | `rename`, не поверх существующего |
| `h2t-docs-lint new` | `docs/superpowers/{plans,specs}/*.md`, `docs/adr/*.md` | `create`, существующий файл — ошибка |
| `docs-index` (`python -m h2t_ops.tools.docs.index --apply`) | `docs/README.md` | `replace` |
| `h2t-milestone-closure` | `.h2t/lifecycle/milestone-closure-<milestone>.json` | `replace` |
| `h2t-agent-profile` | `.claude/agent-profile.json`, `.claude/settings.json` | `replace`, `settings.json` — слияние |
| хук `plan-closer` | `docs/superpowers/{plans,specs}/*` (`status: "done"`, `pr: N`) | `replace` |
| хук `post-git-commit-docs-lint` | `.h2t/lifecycle/post-git-commit-docs-lint.json` | `replace` |
| `h2t-project-audit-report` | `projects.yaml` (по умолчанию `$H2T_DEV_ROOT/h2t-landings`) | `replace` |
| `init-project`, `h2t-project-register` | `.claude/project-id` | `create` (Task 15, R32) |

### Путь, названный пользователем (R7)

Эти команды пишут по пути из своего аргумента, а не в репозиторий, в котором запущены.
Запись идёт через `store` с `dest=True`, а не через список `REPO_WRITERS`.

| Команда | Путь | Как |
|---|---|---|
| `h2t-drawio generate` | файл `.drawio` | `store.replace`; текст drawpyo берётся из `File.xml`, а не из `File.write()` |
| `h2t-drawio export` | выходной png/svg/pdf | `store.managed(library="drawio")`: файл пишет сам draw.io |
| `h2t-creative assemble` | `--out/{index.html,base.css,profile.css,fx.js}` | `store.replace` |
| `h2t-runbook new` | `dest` | `store.replace` |
| `h2t-docs-lint plan --save` | `FILE` | `store.replace` |
| `h2t-agent-profile catalog …` | файл каталога | `store.replace` |

## Расхождения с §7.1

| Строка §7.1 | Замер | Что сделано |
|---|---|---|
| `h2t-scaffold-project`: `.gitignore`, `README.md`, `CLAUDE.md`, `docs/.artifacts/.gitkeep`, `.claude/settings.json` | ещё `.h2t/structure.yaml` (создать), `.h2t/project-setup-report.json` (замена), `.git/info/exclude` (дописать), корневые каталоги типа проекта | строка в спеке дополнена |
| `h2t-agent-profile`: `.claude/settings*.json` | `.claude/settings.json` и `.claude/agent-profile.json` | строка в спеке уточнена |
| `h2t-docs-lint fix-safe/fix-index/retire`: `docs/**` | ещё `.gitignore`, `deliverables/**`, корневые каталоги шаблона и `.h2t/lint-apply-*.json`; `new` тоже пишет в `docs/**` | строка в спеке дополнена |
| `h2t-docs-init`: `docs/**` каркас, конфиг docs-lint | ещё `.claude/rules/documentation.md`, `.pymarkdown.yaml`, `.vale.ini`, `.h2t/lint-state.jsonl`, дописывание `.gitignore` | строка в спеке дополнена |
| — | хуки `plan-closer` и `post-git-commit-docs-lint`, `h2t-milestone-closure`, `docs-index`, `h2t-project-audit-report` | в таблице спеки их не было, добавлены строки |

Правило для `.claude/project-id` («создать, если нет», R32) замер не менял.

## Чего замер не видит

- Дочерние процессы. `git mv` внутри `RepoWriter.rename`, draw.io при экспорте и docs-init,
  который scaffold запускает отдельным процессом, `Recorder` не видит. Пути, которые они
  изменили, второе утверждение теста всё равно сверяет со списком.
- Настраиваемый `deliverables_dir` в `.claude/rules/docs-lint.yaml`. Список разрешает
  перенос только в `deliverables/**`. При другом значении `fix-safe` отказывает в переносе
  и печатает `FAILED: git mv …` с причиной, а не переносит молча.
