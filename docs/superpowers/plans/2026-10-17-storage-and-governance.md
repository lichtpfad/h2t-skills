---
title: "Storage and governance"
status: "draft"
date: "2026-10-17"
milestone: ""
issue: "548"
---

# Storage and governance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** у каждого класса данных один каталог под `~/.h2t`, у каждого провайдера один файл секрета. Путь знает `core/paths.py`, пишет `core/store.py`, секреты читает `core/secrets.py`. Тесты держат ноль обходов. `h2t-setup layout migrate` переносит данные машины копией с журналом и откатом, `h2t-setup sync` вызывает её после установки. Всё это выходит одним выпуском 4.0.0 вместе с подсистемой 1.

**Architecture:** порядок работы.

1. Сначала три модуля доступа к диску и сторожа: ratchet-тесты с замеренными потолками и тест песочницы с `sys.addaudithook`.
2. Затем вызывающие переводятся на модули группами: по провайдерам, по сессиям, по записям в репо, по установке. Каждая группа опускает потолки ratchet и добавляет свои случаи в песочницу.
3. Затем индекс сессий: производная SQLite из md с frontmatter.
4. Затем `doctor` и миграция `layout 1`: команда `h2t-setup layout migrate|rollback`, которая работает и на editable-установке; `h2t-setup sync` вызывает `migrate`.
5. Последними идут документация, живой перенос (по документу выкатки `docs/superpowers/plans/2026-10-18-storage-rollout.md`) и выпуск.

**Tech Stack:** Python ≥ 3.11 (CI 3.11, выпуск 3.12.11), PyYAML и ruamel.yaml (уже в зависимостях), `sqlite3` из стандартной библиотеки, `fcntl`/`msvcrt`, pytest, GitHub Actions (ubuntu + windows).

**Spec:** `docs/superpowers/specs/2026-10-17-storage-and-governance.md` (v6). Исполнитель читает спеку и план вместе; «§N» ниже — разделы спеки. Отправные данные плана — инвентарь `main` 70214177 (2026-10-17): 75 строк обращения к домашнему каталогу в 37 файлах, 53 строки `.dor`/`.config` в 15, 33 строки `H2T_*` путей в 19, 210 строк записи в 46. Замер исправленными шаблонами сканера (Task 2) на 09223a11, 2026-10-18: `home` 75, `legacy_roots` 50, `path_env` 26 (без `H2T_DEV_ROOT`), `dotenv` 4, `writes` 204 в 46 файлах, `sqlite` 1, `secret_readers` 17. С правилами R21 (docstring не считается, `legacy_roots` не ловит точку внутри имени) на 2ddd6db6, 2026-10-18: `home` 74, `legacy_roots` 40, `path_env` 20, `dotenv` 3, `writes` 203 в тех же 46 файлах, `sqlite` 1, `secret_readers` 17; ни одна строка кода (не docstring) из прежних 50 `legacy_roots` не выпала.

**Ветка исполнения** начинается от `main` не раньше c5484f73 (#555: `tmp.chmod(0o600)` в `google_auth.py`), иначе тесты Task 8 о правах токена не на что опереть.

## Global Constraints

- Не меняется контракт установки из спеки 4.0: `~/.h2t/run/install.json`, `install.env` (LF, `STATE=` первой строкой), чтение `$HOME/.h2t/run` в `plugins/h2t-core/hooks/run`. `paths.run_dir()` не зависит от `H2T_PATH_ROOT`.
- Старые места (`~/.dor/**` кроме `~/.dor/lake` и `~/.dor/vault`, когда они объявлены местами, `~/.config/{google-calendar-mcp,gmail,notion,telegram}/**`, `~/.h2t/{sessions,activity,evals,research,creative}`, `~/.h2t/config/secrets/**`) в 4.0.x пакет **не меняет и не удаляет**. Исключения ровно два: зеркало токена Google при записи главной копии (`store.replace(..., compat=True)`, §9) и `MOVED-TO.txt` во время миграции.
- Значения секретов никогда не печатаются, не логируются и не попадают в `logs/writes.jsonl`. Отчёты выводят путь, имя ключа, длину и `sha256[:12]`. В тестах только фиктивные значения вида `fake-<имя>`.
- Права на macOS и Linux: 0600 на файлы `secrets/**` (в том числе `local/telegram.session` и `local/google.token.json`), 0700 на каталоги `secrets/`, `secrets/shared`, `secrets/local`, `run/rollback/<id>`. Тесты на биты прав помечены `skipif(sys.platform == "win32")`. На Windows пакет права не ставит и не проверяет, `doctor` и сверка миграции о них молчат: `os.chmod(0o600)` там без эффекта, файл наследует ACL профиля — владелец, Administratoren, SYSTEM (проба §11.3).
- Токен Google — у каждой машины свой, `secrets/local/google.token.json`; клиент — `secrets/shared/google.client.json` (§4, решение владельца по пробе §11.4).
- Имена секретов: `<провайдер>.(env|client.json|token.json|session|auth-state.json)`, ключи `<ПРОВАЙДЕР>_<ЧТО>`. Явные исключения: `other.env`, `*.from-*`, чужие `.env`.
- Переменных путей **две** (§6 п. 5): `H2T_PATH_ROOT` (весь `~/.h2t`, кроме `run/`) и `H2T_PATH_VAULT` (vault, общий с POS, по умолчанию `~/.dor/vault`). Переменных на класс или место нет, внешние места — только в `paths.yaml`. Старые имена `H2T_LAKE_ROOT`, `H2T_SESSION_ROOT`, `H2T_ACTIVITY_SPOOL`, `H2T_EVALS_ROOT`, `H2T_EVALS_SPOOL`, `H2T_CONFIG_ROOT`, `H2T_SECRETS_FILE` пакет **не читает**; знает их только `paths.OLD_ENV`, чтобы миграция и `doctor` о них сказали. `H2T_KB_ROOT` (читает `llm-kb-engine`) и `H2T_DEV_ROOT` (где лежит код соседних репо) — не места хранения, их код не меняется.
- Access-токен Google не хранится в местах пакета (§4): файлы токена пишутся только при входе и новом refresh-токене. Единственное исключение — зеркало `tokens.json` в формате 3.x (`token` и `expiry` того момента), которое §9 требует для POS и которое пишется в те же моменты.
- Имя машины — `H2T_MACHINE_NAME` → `DOR_MACHINE_NAME` → hostname; файла с именем нет (§5).
- Никаких новых зависимостей.
- Коды выхода коннекторов: 0 ok, 1 provider, 2 usage, 3 config, 4 auth, 5 not found, 6 network. `doctor` всегда выходит с 0.
- Репо-правила.
  - Тест засчитывается только после красного прогона; красный — с прочитанным текстом падения.
  - Красный прогон делается на нарочно испорченном дереве. Порча откатывается до коммита.
  - Ruff: `uvx ruff@0.16.4 check plugins/ lib/ h2t_ops/ tests/ scripts/`.
  - Полный прогон тестов на маке: `.venv/bin/pytest tests/ -q` и `.venv/bin/pytest lib/ -q`.
  - В `git add` только явные пути. Heredoc в Bash не использовать.
  - Commit делается на каждом шаге «Commit». Push, PR, merge, tag, release и любые сообщения наружу (issues в чужие репо, Telegram) — только на шагах **[владелец]**.
- Каждая задача фазы C, которая переносит вызовы:
  - в конце запускает `.venv/bin/python scripts/storage_map.py --check` и вписывает новые потолки в `tests/governance/test_storage_ratchets.py`;
  - добавляет свои строки в `tests/governance/sandbox_cases.py`;
  - в шаге commit называет оба файла в `git add` вместе со своими путями.
- Задачи фазы D (20–23) тоже прогоняют `--check`: их новые модули не должны добавлять обходов. Если потолки не сдвинулись, файл потолков не меняется.
- `os.chmod` вызывается только под `os.name != "nt"`, в том числе для обычных файлов и каталога отката.

## Review Focus

1. **`paths.yaml`, где место указано через `~`, относительно или через симлинк внутрь `~/.h2t`.** Ожидается отказ с `ConfigError` и именем места, а не тихая запись в `~/.h2t`. Тест — Task 3, `test_place_through_symlink_into_root_is_rejected`.
2. **Миграция, прерванная между фазами (kill), и повторный запуск.** Ожидается продолжение с первой незавершённой фазы, без новых `*.from-*` и без второго экземпляра файла. Тест — Task 21, `test_interrupted_migration_resumes_without_duplicates`.
3. **md сессии с испорченным frontmatter** (пользователь правил руками, конфликт синхронизации). Ожидается, что индекс пропускает файл, записывает его в `problems`, `session-start` показывает остальные. Тест — Task 14, `test_broken_frontmatter_is_skipped_and_reported`.
4. **`USERPROFILE` с пробелом и кириллицей на Windows** (`C:/Users/Лидия Иванова`). Ожидается, что `store.append` под блокировкой и `paths.*` дают корректные пути. Тест — Task 4, `test_append_under_unicode_home` (идёт в CI на windows-latest).
5. **Файл секретов с BOM, CRLF, кавычками, строками `export KEY=…`.** Ожидается разбор 3.x (CRLF, комментарии, кавычки, пробелы вокруг `=`) плюс два расширения: BOM в начале файла и префикс `export ` распознаются (в 3.x они давали ключи `\ufeffA` и `export B`, которых никто не читал). Одинаково при чтении и при миграции. Тест — Task 6, `test_env_parse_matches_3x_on_awkward_files`.

## Решения, принятые при написании плана

Спека v6 — авторитет; ниже — то, о чём она молчит, и решения владельца 2026-10-18 (Q1–Q9), уже внесённые в спеку. Цена ошибки указана, чтобы владелец мог развернуть решение до исполнения.

| # | Решение | Почему | Цена, если неверно |
|---|---|---|---|
| R1 | Удаление — пятая операция `store.remove`/`remove_tree`, только в `run`, `state`, `logs`, `tmp`, `harness`; в `records`, `secrets` — только откатом по журналу (`journal=True`, одно место импорта — `setup/layout/rollback.py`) | спека называет четыре операции, но откат миграции и `sync` (кэш плагинов, `claude-pending.json`) удаляют | одна функция и один тест |
| R2 | Миграция создаёт `config/paths.yaml`, если его нет, и вписывает только то, что есть: `lake` — значение `H2T_LAKE_ROOT`, если задано, иначе `~/.dor/lake`, если существует; `inbox: ~/Downloads`, если существует (там 3.x клал вложения Telegram). Vault в `paths.yaml` не пишется: он из `H2T_PATH_VAULT` (R12). Существующий файл не трогает | иначе у автора `meetgeek`/`granola` молча начнут писать в `~/.h2t/data/lake` | правка одного шага миграции |
| R3 | Выбор синхронизации в `paths.yaml` — ключ `sync:` с картой `id места → инструмент` (`syncthing`, `git`, `none` или любое имя). `doctor` по нему отвечает «объявлено» | §3 называет «выбор синхронизации», формат не задан | формат одного ключа |
| R4 | Имя машины не хранится в файле (владелец, Q7): `paths.machine_name()` = `H2T_MACHINE_NAME` → `DOR_MACHINE_NAME` → hostname. `--machine` у миграции закрепляет имя через существующий `setup.legacy.ensure_machine_name(name=…)` (ADR 0003); если в настройках уже закреплено другое имя, миграция останавливается, а не переписывает его | все читатели имени работают внутри Claude Code; второй источник дал бы вопрос «кто главнее» | одна функция |
| R5 | Переменных путей две, `H2T_PATH_ROOT` и `H2T_PATH_VAULT`; старые имена не читаются, `paths.OLD_ENV` нужен только миграции и `doctor` (владелец, Q2, Q8). Корневой `conftest.py` изолирует набор тестов через `HOME`, а не через старые переменные (Task 7) | два набора переменных дают вопрос «кто главнее» и разорванное хранилище при забытой переменной 3.x | правило в `paths` и `conftest.py` |
| R6 | Чужой `.env` из старого каталога (`getcourse.env`, `anysite.env` — имя не провайдер пакета) переносится целиком под своим именем; ключи провайдеров пакета из него ещё и участвуют в лестнице; прочие его ключи в `other.env` не идут | сегодня лестница читает все `*.env`, поэтому ключ `EXA_*` из такого файла работает; после переноса пакет чужие файлы не читает | правка таблицы источников |
| R7 | `drawio` и `creative assemble` пишут в путь, названный пользователем, как в `--dest` (`dest=True`), а не через список `repo` | путь задаёт пользователь, и он не обязан быть внутри репо | — |
| R8 | `h2t-setup layout rollback` требует флаг `--sync-paused` | §7.5 требует паузы; пакет не может проверить Syncthing | один флаг |
| R9 | Миграция переносит ещё `~/.h2t/research` → `data/research` и `~/.h2t/creative/profiles` → `data/creative/profiles` | §3 их называет, §8 забыл | две строки фазы |
| R10 | `latest.json` перестаёт писаться в Task 16, вместе с переходом gather на индекс; до тех пор handoff пишет его рядом с md в `records/sessions/…`, и gather читает его там (Task 13). Ключ `latest` в ответе `h2t-handoff` = путь к md, `latest_session` в `GATHER_META` строится из индекса | §5; если перестать писать раньше, полный круг handoff → gather краснеет между Task 13 и 16 | правка скиллов handoff/session-start |
| R11 | Access-токен Google не хранится (владелец, Q6, вариант C): рефреш в памяти, файлы токена пишутся только при входе и новом refresh-токене; зеркало `tokens.json` — в формате 3.x в эти моменты. До выпуска — живая проверка POS с протухшим `expiry` (Task 26); если POS падает, запасной вариант B: `mirror_legacy` вызывается и на каждом рефреше | §4; меньше файлов с секретом и записей | одна строка в `resolve_google_credentials` |
| R12 | Vault — `paths.vault()` из `H2T_PATH_VAULT`, по умолчанию `~/.dor/vault`; в `paths.yaml` ключ `vault` — ошибка с подсказкой; `vault.dor` убран из старых мест; issue в POS (текст — Task 25, заведение — Task 26) | владелец: адрес vault — договор двух программ, POS не читает `paths.yaml` | одна функция |
| R13 | Миграция — подкоманда `h2t-setup layout {migrate,rollback}` (владелец, Q1). Она не вызывает `ensure_executor` и не проверяет editable-установку, а работает в том интерпретаторе, который её запустил; `sync` вызывает `migrate` после шага 7 (подключение — Task 23, когда есть все фазы, R24). Task 26 идёт через `dev-sync` + `layout migrate`, поэтому её можно закончить до Task 27 | `sync` отказывает editable-установке (`setup/cli.py:38-49`) и перезапускает опубликованный выпуск, где миграции ещё нет | одна подкоманда |
| R14 | Копии `config/*.yaml` перед правкой — `state/backups/<имя>.<YYYYmmdd-HHMMSS>`, последние 10 на файл; миграция переносит `config/*.yaml.bak*` туда и удаляет из `config/` (владелец, Q9) | `config/` синхронизируется, копии рядом конфликтовали бы | одна функция |
| R15 | Миграция activity отбрасывает строки тестов (#441, владелец, Q4): `session_id` из `PYTEST_SESSION_IDS` или `project` из `PYTEST_PROJECTS` (оба списка — в `phases.py`, взяты из `tests/core/test_session_identity_roundtrip.py` и `test_handoff_identity_from_cwd.py`). У автора 1279 строк из 1445 | иначе мусор уезжает в синхронизируемый `records/` | список в одном модуле |
| R16 | `H2T_DEV_ROOT` не место хранения; шаблон `path_env` сканера его не считает (владелец, Q3) | это адрес кода соседних репо | одно исключение в шаблоне |
| R17 | `store` переживает испорченный `paths.yaml`: места пакета классифицируются и пишутся как обычно, отказ — только для записи вне `~/.h2t` (§7.2) | иначе одна опечатка в строке `lake` останавливает handoff, activity, логи хуков и сам `paths set` (`gates.md`) | одна ветка в `_check` |
| R18 | `sqlite3.connect` вызывается только в `store.py`: `store.connect_sqlite(path, *, place)` открывает базу внутри `managed`, `store.sqlite_copy(src, dest, *, place)` копирует базу через `backup` | иначе потолок `sqlite = 0` недостижим: индекс и Telegram открывают базы сами | две функции |
| R19 | Токен Google — `secrets/local/google.token.json`, у каждой машины свой; `google.client.json` — в `shared`. Логики «главная копия новее/старее» нет: зеркало в `tokens.json` пишется при каждой записи токена этой машины, пока старый файл существует | проба §11.4: refresh-токены мака и ноутбука разные (`ffadbd08aa1f` ≠ `4ac3fa1e3925`), решение владельца 2026-10-18 | одна строка в `secrets._JSON` |
| R20 | `store.create` публикует только через `os.link` (атомарно, без перезаписи). Если жёстких ссылок нет (FAT, exFAT, часть сетевых дисков), `create` бросает `ConfigError` с именем каталога и ничего не пишет; запасной записи прямо в конечный путь нет | §7.2: `create` атомарен; прямая запись при обрыве оставляет половину файла, которую коннектор потом не признаёт своей | `lake`/`inbox` на таком диске не принимают новые файлы, пока не появится переименование без перезаписи (`renameat2`/`renamex_np` вне stdlib) |
| R21 | Сканер не считает строки docstring (модуля, класса, функции; по `ast`), а `legacy_roots` не считает `.dor`/`.config/` после буквы, цифры, `_` или точки: `"secrets.dor"` — имя ключа `LEGACY`, а не путь. `".dor"`, `"~/.dor/…"`, `/ ".config"` по-прежнему ловятся; контроль — строки-приманки в обе стороны (Task 2) | иначе ноль Task 24 недостижим: ключи `LEGACY`, docstring секретов и миграции — законный код плана | путь, написанный в docstring, не считается (docstring не исполняется; прозу ловит Task 24 Step 5) |
| R22 | Старые имена переменных пишутся только в `paths.py`. Вызывающие берут значения через `paths.old_env_by_use(use) -> dict[str, Path]` (`"lake"`, `"secrets-source"`, `"evals-spool-source"`) или проверяют `k in paths.OLD_ENV`. `OLD_ENV["H2T_EVALS_SPOOL"] = "evals-spool-source"`: спул из этой переменной (или того же ключа в старом файле секретов) миграция копирует | GC «знает их только `paths.OLD_ENV`»; в 3.x путь спула мог прийти и из файла секретов (`eval/session.py:299-303`) | одна функция |
| R23 | Блокировка gather переезжает из `tmp` в `state/locks/gather-<ключ>.lock` (`store.replace(place="state")`) | §7.1: в `tmp` только через `store.scratch()`, а каталог `scratch` удаляется на выходе и не держит блокировку между процессами | файлы блокировок копятся в `state/locks` (по одному на скилл × репо, десятки байт) |
| R24 | Фазы миграции находит `engine._phase_funcs()` — явная таблица импортов. Владельцы: `engine.py` — `snapshot`, `config_backups`, `markers`; `secrets_phase.py` — `secrets`; `verify.py` — `verify`; `phases.py` — остальные. `migrate` до первой записи проверяет, что у каждого имени `PHASES` есть функция, иначе `report.failed`. `sync` вызывает `migrate` только с Task 23 | Task 21 идёт раньше фаз 22–23; `sync`, подключённый в Task 21, падал бы на каждой машине | порядок двух задач |
| R25 | (пересмотрено, решение контроллера, раунд 2 гейта) `phase_verify` = `verify_secrets` + `verify_copies` (строка `created` с `source_path`: хэш источника = хэш цели) + `verify_transformed` (R37). Сессия Telegram (Task 22) и спул evals (Task 23) — **байтовые** копии, как требует §8 п. 6, сверяются по `sha256`. Перед копией каждой базы — `engine.quiet_sqlite_bytes(src, read=…)` (Task 21; для сессии `read=secrets.read_secret_bytes`, R38): рядом с источником нет `-wal`/`-journal`/`-shm`, и `stat` источника (`st_size`, `st_mtime_ns`) одинаков до и после чтения байтов; иначе фаза останавливается `ConfigError` «закройте Telegram / процесс evals и запустите `h2t-setup layout migrate` снова». `store.sqlite_copy` остаётся только для копии сессии адаптером Task 9 вне миграции | спека §8 п. 6: сессия Telegram и evals — байтовые копии со сверкой хэша; живая база с открытым журналом могла бы дать рваную копию, поэтому её копировать не начинают | миграция у пользователя, у которого Telegram или evals держат базу открытой, останавливается до закрытия процесса |
| R26 | Task 25 пишет тексты issues в репо: `docs/reports/<дата>-storage-issue-pos-google.md`, `…-storage-issue-pos-vault.md`, `…-storage-issue-rejuve.md` (коммитятся). Результат живой проверки POS вписывается и issues заводятся в Task 26 **[владелец]** | Task 25 автономна, issues в чужие репо — сообщения наружу (GC), а результат POS появляется только в Task 26 | три небольших файла в `docs/reports` |
| R27 | Полнота песочницы — по наблюдению: `Recorder.writers` собирает модули `h2t_ops`, которые записали на диск (через дверь или нет); список модулей-писателей базы — файл `tests/governance/writers_baseline.txt`, выход сканера в Task 2 | префикс id случая не доказывает, что модуль исполнялся (один `research.*` закрывал шесть модулей) | одно поле `Recorder` и один файл |
| R28 | Место записи коннектора — по происхождению пути: место задано в `paths.yaml` → `place="lake"`/`"inbox"`; не задано, путь по умолчанию `data/<место>` → `place="data"`; путь дал пользователь (`--to`, `--out`, `root=`) → `dest=True`, а если его `realpath` равен заданному или умолчанию — как они. `ConnectorDir` и `place_or_default` вызывающих хранят это происхождение | `store` классифицирует по `realpath`: `data/lake` — это `data`, а не `lake`, и `place="lake"` там отказ | одно поле |
| R29 | Потоковая запись — `store.writer(path, *, place, mode=None, dest=False)`: контекст-менеджер отдаёт дескриптор временного файла рядом, на чистом выходе `fsync` и `os.replace`, при исключении временный файл удаляется. Для загрузок MeetGeek, Dropbox, Drive | записи `dest.open("wb")` с `iter_content` и `MediaIoBaseDownload` иначе остаются обходом, а читать сотни МБ в память ради `replace` нельзя | одна функция |
| R30 | `Case.setup(sb, mp)` — подготовка случая песочницы (старая сессия, фиктивный токен) до включения `Recorder` | `guarded` включает старые корни и `tmp`; подготовка внутри `active()` была бы нарушением | одно поле |
| R31 | Каталог миграции — `run/rollback/layout1-<UTC>/` с `journal.jsonl`; `Journal.latest()` и чистка через 30 дней смотрят только каталоги с `journal.jsonl`. Снимки `sync` (`run/rollback/<UTC>/`) и `claude-pending.json` не трогаются. Строки журнала: `{"op": "baseline", "key", "sha256"}` по строке на пару, `{"op": "winner", "target", "key", "sha256"}`, `{"op": "created", "path", "place", "source", "sha256", "source_path"?}`, `{"op": "replaced", "path", "place", "prev_sha", "new_sha", "prev"}`, `{"op": "removed", "path", "place", "prev_sha", "prev"}`, `{"op": "phase_done", "phase"}` | `sync` уже пишет в `run/rollback` (`setup/sync.py:257-266`) | префикс имени каталога |
| R32 | `.claude/project-id` — только `create` (§7.1 «создать, если нет»): `REPO_WRITERS` даёт обеим командам регистрации одну операцию `create`; существующий файл остаётся как есть, `AlreadyExists` — не ошибка | спека; так же ведёт себя 3.x (`apply_registration.py:143`) | перерегистрация с другим id не переписывает файл, как и сегодня |
| R33 | `eval/session._load_secrets` и `_DEFAULT_SECRETS` удаляются; `SkillEval` (`:118`) и `status.get_status` (`:44`) зовут `secrets.evals_env(env_file=None)` | один читатель секретов (§7.2) | две строки вызова |
| R34 | `paths.validate_config(doc: dict, *, source: Path) -> PathsConfig` — проверка документа в памяти; `paths_config()` = чтение файла + `validate_config` | `paths set` проверяет **новый** документ, пока старый испорчен | одна функция |
| R35 | `ingest_write`: тест держит «вне `h2t_ops/ingest/` мест импорта нет». «Ровно одно» включает подсистема 4, когда модуль ингеста появится; красный контроль — подложенный неотслеживаемый файл | §10: ингест — отдельная подсистема, импортировать здесь некому. Решение контроллера, подтверждение владельца — в отчёте прогона | одна строка теста |
| R36 | `store.mkdir(path, *, place, mode=None)`: `mode` ставится только на POSIX; каталог отката `run/rollback/<id>` — `mode=0o700` | `chmod` вне `store` — запись мимо двери для песочницы | один параметр |
| R37 | Старый `tokens.json` (и `gmail/token.json`) → `secrets/local/google.token.json` — **преобразованная** копия (§4, §8 п. 6 «преобразованные — по правилу»): `google_auth.durable_token(data)` снимает обёртку `normal` и `scope` → `scopes` так же, как `_load_credentials` 3.x (`core/google_auth.py:145-156`), и оставляет только `refresh_token`, `client_id`, `client_secret`, `token_uri`, `scopes` (те, что есть; это поля, которые новый читатель передаёт в `Credentials.from_authorized_user_info`); `token`, `access_token`, `expiry`, `expiry_date`, `id_token` отбрасываются. Сверка по правилу `verify.verify_transformed`: каждое долгоживущее поле источника после нормализации равно полю цели по `sha256(json.dumps(v, sort_keys=True))`, и в цели нет ни одного отброшенного поля. Проигравший источник — `google.token.json.from-<источник>` тем же преобразованием | §4: access-токен нигде не хранится; байтовая копия перенесла бы его в `local` | одна функция в `google_auth` |
| R38 | Миграция читает секреты только через `core/secrets.py`: `secrets.migration_sources()`, `secrets.shared_env_values()`, `secrets.read_secret_bytes(path)`, `secrets.notion_legacy_token()`, `secrets.telegram_legacy_config()` (Task 6). `secrets_phase.py` и `verify.py` не открывают файлов секретов сами | §7.2: `secrets.py` — единственный читатель секретов, миграция не исключение | пять функций в `secrets.py` |
| R39 | Строка манифеста коннектора сериализуется одной функцией `lake.manifest_line(row) -> str` = `json.dumps(row, sort_keys=True, ensure_ascii=False, separators=(",", ":"))` и только потом идёт в `store.append` (он принимает `str`) | детерминированные строки: сравнение манифеста не зависит от порядка ключей | одна функция |
| R40 | `secrets skeleton` пишет по файлу на провайдера: `secrets_skeleton(registry, *, secrets_dir: Path \| None = None, home: Path \| None = None) -> dict` группирует недостающие ключи по `providers.provider_of_key` (ключ без провайдера → `other.env`), дописывает в каждый `<провайдер>.env` строки `KEY=` только для отсутствующих ключей, существующие строки и комментарии не трогает (текст файла читается `secrets.read_secret_bytes(path, root=secrets_dir)` при заданном каталоге, иначе без `root`; дописанный пишется `store.replace(place="secrets.shared")`, для `secrets_dir` — с `dest=True`); `secrets_dir` задан — файлы под ним (`dest=True`), иначе `paths.secrets_shared()`. Ответ: `{"kind": …, "files": {имя: {"path": путь, "added": [ключи]}}, "skipped": [ключи, которые уже разрешаются]}` | `setup/legacy.py:630` писал один `secrets.env`; §4: файл на провайдера | форма ответа одной команды |
| R41 | Запись секрета журналирует **имена ключей**, которые передаёт `core.secrets`: у `store.replace`/`create` параметр `keys: tuple[str, ...]`, в `logs/writes.jsonl` — `"keys": [...]` и `"sha256": null` для каждой записи с `keys` (и `dest=True`, и зеркало `compat`), а для мест `secrets.*` `sha256` — `null` всегда; `write_env` передаёт имена ключей, `write_json` — имена полей, `put` миграции — имена ключей env-файла. Имя файла в `key` больше не пишется | §7.2: «для секретов только имя ключа» | один параметр |
| R42 | Явно названный каталог — единственный корень чтения секрета вне `secrets/` и старых мест: `secrets.read_secret_bytes(path, *, root=…)`, `secrets.read_json_at(path, *, root)`, `secrets.telegram_legacy_config(config_dir=…)`. Ветка `config_dir=` Telegram (Task 9) и `secrets_dir` у `secrets skeleton` (Task 10) читают только так | §7.2: один читатель секретов во всех ветках, включая тестовые | три параметра/функции |
| R43 | Явный `config_root` регистрации пишется `store.replace(place="config", dest=True)`; `config_root`, равный `paths.config_dir()`, — обычный `place="config"` | каталог вызывающего классифицируется как `tmp`/`elsewhere`; `place="config"` без `dest` его отверг бы (`tests/lifecycle/test_apply_registration.py:41-49`) | одна ветка |
| R44 | `layout.json` миграции журналируется как любой файл: нет — `created`, есть — `replaced` с прежними байтами; откат возвращает его общим правилом, снимка в `snapshot` нет | §7.5: откат возвращает прежний `layout.json`; у снимка не было ни строки журнала, ни метода | — |

---

## Фаза P — пробы и сторожа

### Task 1: Пробы на машинах автора — вынесено

Пробы спеки §11 проведены 2026-10-17, их выводы уже в спеке v6: на Windows права не ставятся и
не проверяются (проверки только на POSIX), `append` на Windows использует `msvcrt.locking`,
токен Google у каждой машины свой в `local`, индекс пересобирается по `stat`. Сами замеры,
состав машин и оставшаяся Syncthing-проба — в документе выкатки `docs/superpowers/plans/2026-10-18-storage-rollout.md`.

**Files:** —

**Interfaces:** Produces — решения, которые читают Task 4 (блокировка на Windows: `msvcrt`), Task 6 (права на Windows: не ставятся), Task 8 и Task 22 (токен Google в `local`).

### Task 2: Сканер обходов и ratchet-тесты

**Files:**
- Create: `scripts/storage_map.py`
- Create: `tests/governance/__init__.py`
- Create: `tests/governance/test_storage_ratchets.py`
- Create: `tests/governance/writers_baseline.txt` (выход `storage_map.py --files writes`, R27)

**Interfaces:**
- Produces: `storage_map.hits(root: Path, name: str) -> list[str]` (строки `path:line`), `storage_map.files(root: Path, name: str) -> list[str]` (файлы с попаданиями, без `h2t_ops/`), `storage_map.PATTERNS: dict[str, str]`, `storage_map.ALLOWED: dict[str, set[str]]`, `storage_map.docstring_lines(text: str) -> set[int]`, CLI `python scripts/storage_map.py [--check] [--files <name>]`: печатает `name count` по строке, при `--check` сверяет с потолками теста, при `--files <name>` печатает только файлы шаблона.
- Produces: `tests/governance/writers_baseline.txt` — 46 модулей, которые писали на диск на ветке до перевода; читают его этот тест и Task 24.
- Каждая задача фазы C вызывает `--check` и правит потолки.

- [ ] **Step 1: Сканер.**

```python
# scripts/storage_map.py
"""Measure the paths and writes that bypass core/paths, core/store, core/secrets (#548 §7.3).

Partial by design: it matches known spellings, it does not prove there is no bypass —
the sandbox test in tests/governance does that. Counts are lines of tracked
h2t_ops/**/*.py, comment-only lines and docstrings skipped (plan R21): neither runs, so
the numbers move with the code and nothing else.
"""
from __future__ import annotations

import ast
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PATTERNS: dict[str, str] = {
    "home": r"Path\.home\(\)|expanduser\(|[\"']~/|os\.environ\[.HOME.\]|os\.environ\.get\(.HOME|USERPROFILE",
    # Not after a word character or a dot: "secrets.dor" is a LEGACY key, ".dor" and
    # "~/.dor/x" are paths (plan R21).
    "legacy_roots": r"(?<![\w.])\.dor\b|(?<![\w.])\.config/|[\"']\.config[\"']",
    # H2T_DEV_ROOT is where sibling repositories live, not a storage place (plan R16).
    "path_env": r"H2T_(?!DEV_ROOT\b)[A-Z_]*(ROOT|SPOOL|FILE|DIR)\b|H2T_PATH_|H2T_CONFIG_SECRETS",
    "dotenv": r"load_dotenv\(",
    # A line that reads a secret file rarely names it (`path.read_text()`), so a spelling
    # pattern measures nothing. These are the 3.x readers by name; each task that moves one
    # to core.secrets takes its name off the tree.
    "secret_readers": (r"\b_read_env_file\b|\bPROVIDER_ENV_FILE\b|\b_DEFAULT_SECRETS\b"
                       r"|\b_candidate_paths\b|\b_candidate_secret_files\b|\b_resolve_secret_value\b"),
    # File handles opened for writing are caught at the open(); json.dump and fh.write are not
    # writes of their own. tempfile.gettempdir() only names a directory.
    "writes": (r"write_text\(|write_bytes\(|os\.replace\(|os\.rename\(|\b(tmp|src)\w*\.(replace|rename)\("
               r"|shutil\.(copy|copy2|copyfile|copytree|move|rmtree)\b|\.unlink\(|os\.remove\(|rmdir\("
               r"|tempfile\.(mkstemp|mkdtemp|NamedTemporaryFile|TemporaryDirectory|SpooledTemporaryFile)\b"
               r"|FileHandler|\.mkdir\(|os\.fdopen\(|\.touch\(|tree\.write\("
               r"|\.open\([\"'](w|a|x)|(?:^|[^_.\w])open\([^)]*,\s*[\"'](w|a|x)[bt+]*[\"']"),
    "sqlite": r"sqlite3\.connect\(",
}
ALLOWED: dict[str, set[str]] = {
    "home": {"h2t_ops/core/paths.py"},
    "legacy_roots": {"h2t_ops/core/paths.py"},
    "path_env": {"h2t_ops/core/paths.py"},
    "dotenv": set(),
    "secret_readers": {"h2t_ops/core/secrets.py"},
    "writes": {"h2t_ops/core/store.py"},
    "sqlite": {"h2t_ops/core/store.py"},
}


def _tracked(root: Path) -> list[str]:
    # --others: a new module that is not staged yet must count too, or the ratchet stays
    # green until the commit.
    out = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard", "h2t_ops/"],
                         cwd=root, capture_output=True, text=True, check=True).stdout
    return sorted({p for p in out.splitlines() if p.endswith(".py")})


def docstring_lines(text: str) -> set[int]:
    """Line numbers of module, class and function docstrings; none if the file does not parse."""
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return set()
    out: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                    and isinstance(body[0].value.value, str):
                out.update(range(body[0].lineno, body[0].end_lineno + 1))
    return out


def hits(root: Path, name: str) -> list[str]:
    rx = re.compile(PATTERNS[name])
    found = []
    for rel in _tracked(root):
        if rel in ALLOWED[name]:
            continue
        try:
            text = (root / rel).read_text(encoding="utf-8")
        except (UnicodeDecodeError, FileNotFoundError):
            continue
        skip = docstring_lines(text)
        for n, line in enumerate(text.splitlines(), 1):
            if line.lstrip().startswith("#") or n in skip:
                continue
            if rx.search(line):
                found.append(f"{rel}:{n}")
    return found


def files(root: Path, name: str) -> list[str]:
    return sorted({h.rsplit(":", 1)[0].removeprefix("h2t_ops/") for h in hits(root, name)})


def main(argv: list[str]) -> int:
    if "--files" in argv:
        print("\n".join(files(ROOT, argv[argv.index("--files") + 1])))
        return 0
    counts = {name: len(hits(ROOT, name)) for name in PATTERNS}
    for name, count in counts.items():
        print(f"{name} {count}")
    if "--check" in argv:
        sys.path.insert(0, str(ROOT / "tests" / "governance"))
        from test_storage_ratchets import CEILINGS  # noqa: E402
        drift = {k: (CEILINGS[k], v) for k, v in counts.items() if CEILINGS.get(k) != v}
        for k, (was, now) in drift.items():
            print(f"ceiling {k}: {was} -> {now}")
        return 1 if drift else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
```

- [ ] **Step 2: Тест с потолками.** Потолок **равен** факту: уменьшил — впиши новое число, иначе тест красный. Так ratchet не ослабевает молча.

```python
# tests/governance/test_storage_ratchets.py
"""Ratchets for #548 §7.3: paths, writes and secret reads outside the three modules.

A ceiling equals the measured count. Going up is a regression; going down means you
removed a bypass — write the new number here so it cannot come back. Target: 0.
"""
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("storage_map", ROOT / "scripts" / "storage_map.py")
storage_map = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(storage_map)

CEILINGS = {  # measured <дата> on <sha>; Task 2 Step 3 fills these in
    "home": 0, "legacy_roots": 0, "path_env": 0, "dotenv": 0,
    "secret_readers": 0, "writes": 0, "sqlite": 0,
}


@pytest.mark.parametrize("name", sorted(storage_map.PATTERNS))
def test_ratchet_equals_measured(name):
    found = storage_map.hits(ROOT, name)
    assert len(found) == CEILINGS[name], (
        f"{name}: {len(found)} found, ceiling {CEILINGS[name]}. Up = a new bypass "
        f"(route it through core/paths, core/store or core/secrets); down = write the "
        f"new number into CEILINGS.\n" + "\n".join(found[:40]))


def test_scanner_sees_a_planted_bypass(tmp_path):
    """Control: the scanner must report a known-positive line (verification.md)."""
    (tmp_path / "h2t_ops").mkdir()
    (tmp_path / "h2t_ops" / "x.py").write_text(
        'p = Path.home() / ".dor"\nopen(p, "w")\nos.environ.get("H2T_DEV_ROOT")\n'
        'os.environ.get("H2T_LAKE_ROOT")\n')
    import subprocess
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    # Not staged on purpose: an untracked module counts as well.
    assert storage_map.hits(tmp_path, "home") == ["h2t_ops/x.py:1"]
    assert storage_map.hits(tmp_path, "legacy_roots") == ["h2t_ops/x.py:1"]
    assert storage_map.hits(tmp_path, "writes") == ["h2t_ops/x.py:2"]   # open() at column 0
    assert storage_map.hits(tmp_path, "path_env") == ["h2t_ops/x.py:4"]  # not H2T_DEV_ROOT


def test_scanner_skips_docstrings_and_dotted_names_but_not_paths(tmp_path):
    """R21 both ways: what it stops counting, and that real spellings still count."""
    (tmp_path / "h2t_ops").mkdir()
    (tmp_path / "h2t_ops" / "y.py").write_text(
        '"""Reads ~/.dor/secrets.env and H2T_LAKE_ROOT, once."""\n'   # 1 docstring
        'def f():\n'
        '    """H2T_SECRETS_FILE is not read; ~/.config/telegram is a fallback."""\n'  # 3 docstring
        '    return legacy("secrets.dor"), legacy("lake.dor")\n'      # 4 dotted keys
        'A = home / ".dor" / "x"\n'                                   # 5 path
        'B = "~/.dor/vault"\n'                                        # 6 path
        'C = home / ".config" / "gmail"\n'                            # 7 path
        'D = "x/.config/y"\n')                                        # 8 path
    import subprocess
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    assert storage_map.hits(tmp_path, "legacy_roots") == [f"h2t_ops/y.py:{n}" for n in (5, 6, 7, 8)]
    assert storage_map.hits(tmp_path, "path_env") == []
    assert storage_map.hits(tmp_path, "home") == ["h2t_ops/y.py:6"]


BASELINE = Path(__file__).with_name("writers_baseline.txt")


def test_no_new_module_writes_outside_store():
    """A count can stay equal while one module stops writing and another starts (R27)."""
    baseline = set(BASELINE.read_text(encoding="utf-8").split())
    assert set(storage_map.files(ROOT, "writes")) <= baseline
```

- [ ] **Step 3: Замерить и вписать.** Run: `.venv/bin/python scripts/storage_map.py`. Вписать числа в `CEILINGS` и строку `# measured 2026-MM-DD on <git rev-parse --short HEAD>`. Сверка с замером этих же шаблонов на 2ddd6db6 (2026-10-18, раздел «Spec» выше, правила R21): `home` 74, `legacy_roots` 40, `path_env` 20, `dotenv` 3, `secret_readers` 17, `writes` 203, `sqlite` 1. Расхождение больше 10 % на ветке от `main` — разобраться, прежде чем вписывать. Затем `.venv/bin/python scripts/storage_map.py --files writes > tests/governance/writers_baseline.txt` — ожидается 46 строк.

- [ ] **Step 4: Красный прогон.** Добавить в любой файл `h2t_ops/` строку `x = Path.home()` (без `git add`: сканер видит и неиндексированное), выполнить `.venv/bin/pytest tests/governance/test_storage_ratchets.py -q`. Expected: FAIL `home: N+1 found, ceiling N`. Откатить строку, повторить: PASS. Второй контроль: новый неотслеживаемый файл `h2t_ops/zz_probe.py` со строкой `open(p, "w")` → `test_no_new_module_writes_outside_store` FAIL, в тексте падения `zz_probe.py` (ratchet `writes` краснеет тоже — это ожидаемо). Удалить файл. Третий контроль: в шаблоне `legacy_roots` убрать `(?<![\w.])` → `test_scanner_skips_docstrings_and_dotted_names_but_not_paths` FAIL (строка 4 попадает); в `hits` убрать `or n in skip` → FAIL (строки 1, 3). Вернуть.

- [ ] **Step 5: Commit** — `git add scripts/storage_map.py tests/governance/__init__.py tests/governance/test_storage_ratchets.py tests/governance/writers_baseline.txt`; `test(governance): storage ratchets with measured ceilings (#548)`.

## Фаза F — три модуля

### Task 3: `core/paths.py` — места, две переменные, `paths.yaml`, старые места

**Files:**
- Create: `h2t_ops/core/paths.py`
- Create: `tests/governance/test_places_table.py`
- Create: `tests/core/test_paths.py`
- Modify: `h2t_ops/lifecycle/gather/sessions.py:148-159` (Step 6)
- Modify: `tests/governance/test_storage_ratchets.py` (потолки, Step 7)
- Modify: `docs/superpowers/specs/2026-10-17-storage-and-governance.md` — только если блок `yaml places` разошёлся с кодом (в v6 строка `layout` уже есть)

**Interfaces:**
- Produces:
  - `Place(id, kind, cls, sync)`, `PLACES: tuple[Place, ...]`, `EXTERNAL = ("lake", "inbox", "vault", "kb")`, `YAML_PLACES = ("lake", "inbox", "kb")`, `OLD_ENV: dict[str, str]` (старое имя → что с ним делает миграция: id внешнего места, `"secrets-source"`, `"evals-spool-source"` или `"remove"`, R22), `old_env_by_use(use: str) -> dict[str, Path]` (заданные старые переменные с этим назначением — вызывающие вне `paths.py` старых имён не пишут);
  - `validate_config(doc: dict, *, source: Path) -> PathsConfig` (проверки `paths.yaml` над документом в памяти; читает Task 19 `paths set`, R34);
  - `home() -> Path`, `root() -> Path`, `run_dir() -> Path`, `vault() -> Path`, `dir_of(place_id: str) -> Path`, `place(name: str) -> Path | None`, `place_or_default(name: str) -> tuple[Path, bool]`;
  - `secrets_shared()`, `secrets_local()`, `state_dir()`, `logs_dir()`, `data_dir()`, `config_dir()`, `records(kind: str, machine: str | None = None) -> Path`, `layout_file() -> Path`, `paths_yaml() -> Path`, `backups_dir() -> Path` (`state/backups`);
  - `activity_file(machine: str) -> Path`, `evals_spool() -> Path` (`state/evals-spool.sqlite`, всегда);
  - `paths_config() -> PathsConfig` (`places: dict[str, Path]`, `vault_rules: Path | None`, `sync: dict[str, str]`);
  - `legacy(name: str) -> Path`, `LEGACY: dict[str, tuple[str, ...]]`, `LEGACY_FILES`, `legacy_roots() -> list[Path]`, `legacy_dir(name) -> Path`;
  - `expand_user_dest(value: str) -> Path`, `machine_name() -> str`, `old_env(name: str) -> Path | None` (значение старой переменной — только для миграции и `doctor`), `old_env_in_use() -> list[str]`.

- [ ] **Step 1: Тест таблицы мест (красный: модуля нет).**

```python
# tests/governance/test_places_table.py
"""The `yaml places` block of the spec and paths.PLACES agree both ways (§3, §7.6)."""
import re
from pathlib import Path

import yaml

from h2t_ops.core import paths

SPEC = Path(__file__).resolve().parents[2] / "docs/superpowers/specs/2026-10-17-storage-and-governance.md"


def _spec_places():
    text = SPEC.read_text(encoding="utf-8")
    block = re.search(r"```yaml places\n(.*?)```", text, re.S).group(1)
    return [{"id": r["id"], "kind": r["kind"], "class": r["class"], "sync": r["sync"]}
            for r in yaml.safe_load(block)]


def test_places_table_matches_spec_both_ways():
    code = [{"id": p.id, "kind": p.kind, "class": p.cls, "sync": p.sync} for p in paths.PLACES]
    assert code == _spec_places()
```

Run: `.venv/bin/pytest tests/governance/test_places_table.py -q` → FAIL `ModuleNotFoundError: h2t_ops.core.paths`.

- [ ] **Step 2: Тесты поведения.**

```python
# tests/core/test_paths.py
import os
import sys

import pytest

from h2t_ops.core import paths
from h2t_ops.core.errors import ConfigError


@pytest.fixture
def home(tmp_path, monkeypatch):
    h = tmp_path / "home"
    h.mkdir()
    monkeypatch.setenv("HOME", str(h))
    monkeypatch.setenv("USERPROFILE", str(h))
    for k in list(os.environ):
        if k.startswith("H2T_PATH_") or k in paths.OLD_ENV \
                or k in ("H2T_MACHINE_NAME", "DOR_MACHINE_NAME", "CLAUDE_CONFIG_DIR"):
            monkeypatch.delenv(k, raising=False)
    return h


def _yaml(home, text):
    p = home / ".h2t" / "config" / "paths.yaml"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def test_classes_live_under_root(home):
    assert paths.dir_of("secrets.shared") == home / ".h2t" / "secrets" / "shared"
    assert paths.records("sessions", "mac") == home / ".h2t" / "records" / "sessions" / "mac"
    assert paths.run_dir() == home / ".h2t" / "run"


def test_root_override_moves_everything_but_run(home, monkeypatch, tmp_path):
    monkeypatch.setenv("H2T_PATH_ROOT", str(tmp_path / "r"))
    assert paths.dir_of("state") == tmp_path / "r" / "state"
    assert paths.dir_of("layout") == tmp_path / "r" / "layout.json" == paths.layout_file()
    assert paths.run_dir() == home / ".h2t" / "run"


def test_old_env_names_are_reported_not_read(home, monkeypatch, tmp_path):
    monkeypatch.setenv("H2T_SESSION_ROOT", str(tmp_path / "old-sessions"))
    monkeypatch.setenv("H2T_ACTIVITY_SPOOL", str(tmp_path / "a" / "spool.jsonl"))
    monkeypatch.setenv("H2T_LAKE_ROOT", str(tmp_path / "old-lake"))
    monkeypatch.setenv("H2T_PATH_RECORDS", str(tmp_path / "rec"))  # never existed in 4.0
    assert paths.dir_of("records.sessions") == home / ".h2t" / "records" / "sessions"
    assert paths.activity_file("mac") == home / ".h2t" / "records" / "activity" / "mac.jsonl"
    assert paths.records("evals") == home / ".h2t" / "records" / "evals"
    assert paths.place("lake") is None
    assert paths.old_env_in_use() == ["H2T_ACTIVITY_SPOOL", "H2T_LAKE_ROOT", "H2T_SESSION_ROOT"]
    assert paths.old_env("H2T_LAKE_ROOT") == tmp_path / "old-lake"


def test_external_place_from_yaml(home, tmp_path):
    _yaml(home, f"version: 1\nplaces:\n  lake: {tmp_path / 'lake'}\n")
    assert paths.place("lake") == tmp_path / "lake"
    assert paths.place("inbox") is None
    assert paths.place_or_default("inbox") == (home / ".h2t" / "data" / "inbox", True)


def test_vault_from_env_with_pos_default(home, monkeypatch, tmp_path):
    assert paths.vault() == paths.place("vault") == home / ".dor" / "vault"
    monkeypatch.setenv("H2T_PATH_VAULT", str(tmp_path / "v"))
    assert paths.place("vault") == tmp_path / "v"


def test_vault_in_paths_yaml_is_rejected(home, tmp_path):
    _yaml(home, f"version: 1\nplaces:\n  vault: {tmp_path / 'v'}\n")
    with pytest.raises(ConfigError, match="H2T_PATH_VAULT"):
        paths.place("lake")


def test_legacy_root_equal_to_a_declared_place_is_not_legacy(home):
    _yaml(home, "version: 1\nplaces:\n  lake: ~/.dor/lake\n")
    roots = paths.legacy_roots()
    assert home / ".dor" / "lake" not in roots
    assert home / ".dor" in roots          # dir of the file-valued entries (secrets.env, …)
    assert home / ".dor" / "vault" not in roots


def test_tilde_in_yaml_expands(home):
    _yaml(home, "version: 1\nplaces:\n  kb: ~/kb\n")
    assert paths.place("kb") == home / "kb"


def test_overlapping_places_are_rejected(home, monkeypatch, tmp_path):
    monkeypatch.setenv("H2T_PATH_VAULT", str(tmp_path / "v"))
    _yaml(home, f"version: 1\nplaces:\n  inbox: {tmp_path / 'v' / 'in'}\n")
    with pytest.raises(ConfigError, match="vault.*inbox|inbox.*vault"):
        paths.place("lake")


def test_place_inside_root_is_rejected(home):
    _yaml(home, f"version: 1\nplaces:\n  lake: {home / '.h2t' / 'lake'}\n")
    with pytest.raises(ConfigError, match="lake"):
        paths.place("lake")


@pytest.mark.skipif(sys.platform == "win32", reason="symlink needs privilege on Windows")
def test_place_through_symlink_into_root_is_rejected(home, tmp_path):
    (home / ".h2t" / "data").mkdir(parents=True)
    link = tmp_path / "innocent"
    link.symlink_to(home / ".h2t" / "data")
    _yaml(home, f"version: 1\nplaces:\n  inbox: {link}\n")
    with pytest.raises(ConfigError, match="inbox"):
        paths.place("inbox")


def test_relative_place_is_rejected(home):
    _yaml(home, "version: 1\nplaces:\n  lake: relative/lake\n")
    with pytest.raises(ConfigError, match="absolute"):
        paths.place("lake")


def test_machine_name_order(home, monkeypatch):
    monkeypatch.setattr(paths.platform, "node", lambda: "Host-X.local")
    assert paths.machine_name() == "host-x"
    monkeypatch.setenv("DOR_MACHINE_NAME", "dor")
    assert paths.machine_name() == "dor"
    monkeypatch.setenv("H2T_MACHINE_NAME", "h2t")
    assert paths.machine_name() == "h2t"
    assert not (home / ".h2t" / "state").exists()   # no file pins the name (plan R4)


def test_legacy_places_are_home_relative_and_ignore_root(home, monkeypatch, tmp_path):
    monkeypatch.setenv("H2T_PATH_ROOT", str(tmp_path / "r"))
    assert paths.legacy("google.store") == home / ".config" / "google-calendar-mcp"
    assert paths.legacy("sessions.dor") == home / ".dor" / "sessions"
```

Run: `.venv/bin/pytest tests/core/test_paths.py -q` → FAIL, импорт.

- [ ] **Step 3: Реализация.**

```python
# h2t_ops/core/paths.py
"""Where every class of data lives — the only module that knows (#548 §3, §6, §7.2).

Nothing else in h2t_ops calls Path.home() or expanduser, reads H2T_PATH_ROOT, H2T_PATH_VAULT
or the 3.x variable names, or spells ~/.dor or ~/.config/<program>. tests/governance holds
the ratchet.
"""
from __future__ import annotations

import os
import platform
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from h2t_ops.core.errors import ConfigError


@dataclass(frozen=True)
class Place:
    id: str
    kind: str   # fixed | class | place | file
    cls: str    # run | config | secrets | records | data | state | logs | external | root
    sync: str   # never | user | owner


PLACES: tuple[Place, ...] = (
    Place("run", "fixed", "run", "never"),
    Place("config", "class", "config", "user"),
    Place("secrets.shared", "class", "secrets", "user"),
    Place("secrets.local", "class", "secrets", "never"),
    Place("records.sessions", "class", "records", "user"),
    Place("records.activity", "class", "records", "user"),
    Place("records.evals", "class", "records", "user"),
    Place("records.imports", "class", "records", "user"),
    Place("data", "class", "data", "user"),
    Place("state", "class", "state", "never"),
    Place("logs", "class", "logs", "never"),
    Place("lake", "place", "external", "owner"),
    Place("inbox", "place", "external", "owner"),
    Place("vault", "place", "external", "owner"),
    Place("kb", "place", "external", "owner"),
    Place("repo", "place", "external", "owner"),
    Place("harness", "place", "external", "owner"),
    Place("tmp", "place", "external", "never"),
    Place("layout", "file", "root", "never"),
)
_BY_ID = {p.id: p for p in PLACES}
EXTERNAL = ("lake", "inbox", "vault", "kb")
YAML_PLACES = ("lake", "inbox", "kb")   # vault comes from H2T_PATH_VAULT (§6 п. 5)

# 3.x variable names. 4.0 does not read them for paths (§6 п. 5); migration and doctor do,
# to say what became of each: an external place the migration writes into paths.yaml, one
# more secrets source for the migration, or a variable to remove.
OLD_ENV: dict[str, str] = {
    "H2T_LAKE_ROOT": "lake",
    "H2T_SECRETS_FILE": "secrets-source",
    "H2T_CONFIG_ROOT": "remove",
    "H2T_SESSION_ROOT": "remove",
    "H2T_ACTIVITY_SPOOL": "remove",
    "H2T_EVALS_ROOT": "remove",
    "H2T_EVALS_SPOOL": "evals-spool-source",   # the migration copies that spool (plan R22)
}

# Where 3.x kept things. Read for migration and fallback in 4.0.x; never written except
# the Google mirror and MOVED-TO.txt (§7.3). ~/.dor/vault is not here: it is the vault's
# default address, shared with POS (plan R12).
LEGACY: dict[str, tuple[str, ...]] = {
    "secrets.h2t": (".h2t", "config", "secrets"),
    "secrets.dor": (".dor", "secrets", "secrets.env"),
    "secrets.dor_old": (".dor", "secrets.env"),
    "notion.token": (".config", "notion", "token"),
    "google.store": (".config", "google-calendar-mcp"),
    "google.gmail": (".config", "gmail"),
    "google.dor": (".dor", "google-credentials.json"),
    "telegram": (".config", "telegram"),
    "sessions.h2t": (".h2t", "sessions"),
    "sessions.dor": (".dor", "sessions"),
    "activity": (".h2t", "activity"),
    "evals": (".h2t", "evals"),
    "research": (".h2t", "research"),
    "creative": (".h2t", "creative", "profiles"),
    "registry.dor": (".dor", "registry.jsonl"),
    "lake.dor": (".dor", "lake"),
    "downloads": ("Downloads",),
}


def home() -> Path:
    return Path.home()


def _env(name: str) -> Path | None:
    value = os.environ.get(name)
    return Path(value).expanduser() if value else None


def root() -> Path:
    return _env("H2T_PATH_ROOT") or home() / ".h2t"


def run_dir() -> Path:
    """Fixed by the 4.0 install contract: hooks/run reads $HOME/.h2t/run in bash."""
    return home() / ".h2t" / "run"


def vault() -> Path:
    """The vault POS owns; its address is a contract between the two programs (plan R12)."""
    return _env("H2T_PATH_VAULT") or home() / ".dor" / "vault"


def dir_of(place_id: str) -> Path:
    p = _BY_ID[place_id]
    if p.kind == "fixed":
        return run_dir()
    if p.kind == "file":
        return layout_file()
    if p.kind == "class":
        cls, _, sub = place_id.partition(".")
        return root() / cls / sub if sub else root() / cls
    if place_id == "vault":
        return vault()
    if place_id == "harness":
        return _env("CLAUDE_CONFIG_DIR") or home() / ".claude"
    if place_id == "tmp":
        return Path(tempfile.gettempdir())
    if place_id == "repo":
        raise ValueError("repo has no fixed directory; pass the repository root to store.repo()")
    found = place(place_id)
    if found is None:
        raise ConfigError(f"place {place_id!r} is not set",
                          hint=f"h2t-ops paths set {place_id} <path>")
    return found


def config_dir() -> Path:
    return dir_of("config")


def secrets_shared() -> Path:
    return dir_of("secrets.shared")


def secrets_local() -> Path:
    return dir_of("secrets.local")


def state_dir() -> Path:
    return dir_of("state")


def logs_dir() -> Path:
    return dir_of("logs")


def data_dir() -> Path:
    return dir_of("data")


def layout_file() -> Path:
    return root() / "layout.json"


def paths_yaml() -> Path:
    return config_dir() / "paths.yaml"


def backups_dir() -> Path:
    return state_dir() / "backups"


def records(kind: str, machine: str | None = None) -> Path:
    base = dir_of(f"records.{kind}")
    return base / machine if machine else base


def activity_file(machine: str) -> Path:
    return records("activity") / f"{machine}.jsonl"


def evals_spool() -> Path:
    return state_dir() / "evals-spool.sqlite"


def old_env(name: str) -> Path | None:
    """A 3.x variable's value, for the migration and doctor only — never a path to use."""
    if name not in OLD_ENV:
        raise KeyError(name)
    return _env(name)


def old_env_in_use() -> list[str]:
    return sorted(n for n in OLD_ENV if os.environ.get(n))


def old_env_by_use(use: str) -> dict[str, Path]:
    """Set 3.x variables with this OLD_ENV use: callers never spell the old names (plan R22)."""
    return {n: _env(n) for n in old_env_in_use() if OLD_ENV[n] == use}


@dataclass
class PathsConfig:
    places: dict[str, Path] = field(default_factory=dict)
    vault_rules: Path | None = None
    sync: dict[str, str] = field(default_factory=dict)


def _inside(a: Path, b: Path) -> bool:
    return a == b or b in a.parents


def paths_config() -> PathsConfig:
    f = paths_yaml()
    if not f.is_file():
        return PathsConfig()
    try:
        doc = yaml.safe_load(f.read_bytes().decode("utf-8-sig")) or {}
    except yaml.YAMLError as exc:
        raise ConfigError(f"{f} is not valid YAML: {exc}", hint="fix the file or remove it") from exc
    return validate_config(doc, source=f)


def validate_config(doc: dict, *, source: Path) -> PathsConfig:
    """Every paths.yaml check, on a document in memory: `paths set` validates the new
    document while the file on disk may still be broken (plan R34)."""
    f = source
    if not isinstance(doc, dict):
        raise ConfigError(f"{f}: expected a mapping at the top", hint="version: 1 and a places: mapping")
    if doc.get("version", 1) != 1:
        raise ConfigError(f"{f}: version {doc.get('version')!r} is not supported", hint="version: 1")
    places: dict[str, Path] = {}
    for name, raw in (doc.get("places") or {}).items():
        if name == "vault":
            raise ConfigError(f"{f}: vault is not set here; it comes from H2T_PATH_VAULT",
                              hint="vault is shared with POS: set H2T_PATH_VAULT (default ~/.dor/vault)")
        if name not in YAML_PLACES:
            raise ConfigError(f"{f}: unknown place {name!r}", hint=f"places are {', '.join(YAML_PLACES)}")
        value = Path(str(raw)).expanduser()
        if not value.is_absolute():
            raise ConfigError(f"{f}: place {name!r} must be an absolute path, got {raw!r}",
                              hint="use ~/… or a full path")
        places[name] = value
    real = {k: Path(os.path.realpath(v)) for k, v in {**places, "vault": vault()}.items()}
    h2t = Path(os.path.realpath(root()))
    for name, p in real.items():
        if _inside(p, h2t) or _inside(h2t, p):
            raise ConfigError(f"{f}: place {name!r} ({p}) overlaps the h2t root {h2t}",
                              hint="external places live outside ~/.h2t")
    names = list(real)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            if _inside(real[a], real[b]) or _inside(real[b], real[a]):
                raise ConfigError(f"{f}: places {a!r} and {b!r} overlap ({real[a]}, {real[b]})",
                                  hint="no place may lie inside another")
    rules = doc.get("vault_rules")
    return PathsConfig(places=places,
                       vault_rules=Path(str(rules)).expanduser() if rules else None,
                       sync={str(k): str(v) for k, v in (doc.get("sync") or {}).items()})


def place(name: str) -> Path | None:
    if name == "vault":
        return vault()
    return paths_config().places.get(name)


def place_or_default(name: str) -> tuple[Path, bool]:
    found = place(name)
    return (found, False) if found is not None else (data_dir() / name, True)


def legacy(name: str) -> Path:
    return home().joinpath(*LEGACY[name])


LEGACY_FILES = frozenset({"secrets.dor", "secrets.dor_old", "notion.token", "google.dor", "registry.dor"})


def legacy_dir(name: str) -> Path:
    """The directory a legacy entry lives in: itself, or its parent for a file entry."""
    p = legacy(name)
    return p.parent if name in LEGACY_FILES else p


def _declared() -> set[Path]:
    """Real paths of the external places, tolerant of a broken paths.yaml (plan R17)."""
    try:
        found = list(paths_config().places.values())
    except ConfigError:
        found = []
    return {Path(os.path.realpath(p)) for p in (*found, vault())}


def legacy_roots() -> list[Path]:
    """Roots that classify a write as legacy. For a file entry the root is its directory, so
    MOVED-TO.txt next to ~/.dor/secrets.env classifies as legacy too. A legacy root that is
    also a declared place (lake: ~/.dor/lake by R2) is that place, not legacy — decided here,
    not by the sort order in store._roots."""
    declared = _declared()
    out: list[Path] = []
    for n in LEGACY:
        if n == "downloads":
            continue
        d = legacy_dir(n)
        if Path(os.path.realpath(d)) not in declared and d not in out:
            out.append(d)
    return out


def expand_user_dest(value: str) -> Path:
    return Path(value).expanduser().absolute()


def machine_name() -> str:
    """H2T_MACHINE_NAME (pinned in Claude settings by setup, ADR 0003) → DOR_MACHINE_NAME →
    hostname. No file pins it (plan R4)."""
    name = os.environ.get("H2T_MACHINE_NAME") or os.environ.get("DOR_MACHINE_NAME", "")
    return name or platform.node().lower().split(".")[0]
```

`legacy("downloads")` не входит в `legacy_roots()`: `~/Downloads` — это `inbox` по R2, а не старое место пакета. `~/.dor` попадает в `legacy_roots()` как каталог файловых записей; `~/.dor/lake` и `~/.dor/vault` внутри него классифицируются как свои места, потому что `store._roots` сортирует корни по глубине, а сами они в список старых не входят.

- [ ] **Step 4: Зелёный прогон.** `.venv/bin/pytest tests/core/test_paths.py tests/governance/test_places_table.py -q` → PASS.

- [ ] **Step 5: Красный контроль таблицы.** Временно удалить `Place("tmp", …)` из `PLACES`. Тест таблицы мест → FAIL, в diff видно `tmp`. Вернуть строку.

- [ ] **Step 6: `get_machine_name` идёт через paths.** В `h2t_ops/lifecycle/gather/sessions.py:148-159` тело заменить на `from h2t_ops.core import paths` + `return paths.machine_name()`, имя функции сохранить (её импортируют handoff и activity). Run: `.venv/bin/pytest tests/core/test_machine_name.py tests/lifecycle -q` → PASS.

Дополнение к Step 2 (пишется вместе с ним, до реализации, и тоже видится красным). Тест для R22 в `tests/core/test_paths.py`: при заданных `H2T_LAKE_ROOT` и `H2T_SESSION_ROOT` `paths.old_env_by_use("lake") == {"H2T_LAKE_ROOT": <путь>}`, `paths.old_env_by_use("remove") == {"H2T_SESSION_ROOT": <путь>}`. Тест для R34: `paths.validate_config({"version": 1, "places": {"lake": "relative"}}, source=Path("x"))` → `ConfigError` с `absolute`, файл на диске не читается (его нет).

- [ ] **Step 7: Ratchet и commit.** `.venv/bin/python scripts/storage_map.py --check` → вписать новые потолки. `git add h2t_ops/core/paths.py h2t_ops/lifecycle/gather/sessions.py tests/core/test_paths.py tests/governance/test_places_table.py tests/governance/test_storage_ratchets.py`; `feat(core): paths.py — the one place that knows where data lives (#548)`.

### Task 4: `core/store.py` — классификация, `replace`, `create`, `append`, `remove`, журнал

**Files:**
- Create: `h2t_ops/core/store.py`
- Create: `tests/core/test_store.py`
- Create: `tests/core/test_store_lock.py`

**Interfaces:**
- Consumes: `paths.dir_of`, `paths.place`, `paths.vault`, `paths.paths_config`, `paths.legacy_roots`, `paths.EXTERNAL`, `paths.YAML_PLACES`, `paths.activity_file`.
- Produces:
  - `WriteRefused(ConfigError)`, `AlreadyExists(FileExistsError)`. Оба — подклассы `H2TError` или `OSError` соответственно: вызывающие, которые раньше ловили только `OSError`, после перехода на `store` ловят ещё `H2TError` (Task 13, Task 18);
  - `classify(path) -> str` (id места, `"legacy"` или `"elsewhere"`);
  - `replace(path, data: str | bytes, *, place: str, mode: int | None = None, compat: bool = False, dest: bool = False, keys: tuple[str, ...] = ()) -> Path`;
  - `create(path, data, *, place, mode=None, dest=False, keys=()) -> Path` (бросает `AlreadyExists`; без жёстких ссылок — `ConfigError`, R20);
  - `keys` — имена ключей секрета, которые передаёт `core.secrets` (§7.2: «для секретов только имя ключа»); запись с непустым `keys` — запись секрета, куда бы она ни легла (`secrets.*`, `dest=True` в каталог пользователя, зеркало `compat`): строка `logs/writes.jsonl` несёт `"keys": [отсортированные имена]` и `"sha256": null`; для мест `secrets.*` `sha256` — `null` всегда; значений нет никогда (R41);
  - `append(path, line: str, *, place, dest=False) -> None`;
  - `remove(path, *, place, journal=False) -> None`, `remove_tree(path, *, place) -> None`;
  - `scratch(prefix="h2t-") -> ContextManager[Path]`;
  - `mkdir(path, *, place, mode: int | None = None, dest: bool = False) -> Path` (`mode` — только на POSIX, R36; `dest` — как у записей, для `--markdown-dir` handoff, Task 13);
  - `sha256(data: bytes) -> str`.

- [ ] **Step 1: Тесты (красные: модуля нет).**

```python
# tests/core/test_store.py
import json
import os
import stat
import sys
import tempfile

import pytest

from h2t_ops.core import paths, store


@pytest.fixture
def home(tmp_path, monkeypatch):
    h = tmp_path / "home"
    h.mkdir()
    monkeypatch.setenv("HOME", str(h))
    monkeypatch.setenv("USERPROFILE", str(h))
    for k in list(os.environ):
        if k.startswith("H2T_PATH_") or k in paths.OLD_ENV:
            monkeypatch.delenv(k, raising=False)
    return h


def test_replace_writes_atomically_and_logs(home):
    target = paths.state_dir() / "x.json"
    store.replace(target, '{"a": 1}', place="state")
    assert target.read_text() == '{"a": 1}'
    row = json.loads((paths.logs_dir() / "writes.jsonl").read_text().splitlines()[-1])
    assert row["op"] == "replace" and row["place"] == "state" and row["path"] == str(target)
    assert row["caller"].startswith("tests.core.test_store") or "test_store" in row["caller"]


def test_write_is_classified_by_real_path_not_by_name(home):
    with pytest.raises(store.WriteRefused, match="secrets.shared"):
        store.replace(paths.secrets_shared() / "x.env", "K=v", place="state")


@pytest.mark.skipif(sys.platform == "win32", reason="symlink needs privilege on Windows")
def test_symlink_does_not_launder_a_write(home, tmp_path):
    paths.secrets_shared().mkdir(parents=True)
    link = paths.state_dir() / "sneaky"
    link.parent.mkdir(parents=True)
    link.symlink_to(paths.secrets_shared())
    with pytest.raises(store.WriteRefused):
        store.replace(link / "exa.env", "EXA_API_KEY=fake", place="state")


def test_vault_write_refused_outside_ingest(home, tmp_path, monkeypatch):
    vault = tmp_path / "vault"
    monkeypatch.setenv("H2T_PATH_VAULT", str(vault))
    with pytest.raises(store.WriteRefused, match="ingest"):
        store.replace(vault / "n.md", "x", place="vault")
    with pytest.raises(store.WriteRefused):
        store.replace(vault / "n.md", "x", place="elsewhere", dest=True)


def test_default_vault_under_dor_is_vault_not_legacy(home):
    with pytest.raises(store.WriteRefused, match="ingest"):
        store.replace(home / ".dor" / "vault" / "n.md", "x", place="vault")


def test_lake_at_the_old_dor_path_classifies_as_lake(home):
    (home / ".h2t" / "config").mkdir(parents=True)
    (home / ".h2t" / "config" / "paths.yaml").write_text("version: 1\nplaces:\n  lake: ~/.dor/lake\n")
    assert store.classify(home / ".dor" / "lake" / "granola" / "n.md") == "lake"
    assert store.classify(home / ".dor" / "secrets.env") == "legacy"


def test_legacy_write_refused_without_compat(home):
    with pytest.raises(store.WriteRefused, match="legacy"):
        store.replace(paths.legacy("telegram") / "config.json", "{}", place="legacy")


def test_broken_paths_yaml_still_allows_package_writes(home, tmp_path, monkeypatch):
    # tmp_path lies under the system temp dir, so every path here would classify as "tmp";
    # move the temp dir aside so a path outside ~/.h2t is really "elsewhere".
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path / "systmp"))
    (home / ".h2t" / "config").mkdir(parents=True)
    (home / ".h2t" / "config" / "paths.yaml").write_text("version: 1\nplaces:\n  lake: [broken\n")
    p = paths.records("sessions", "m") / "proj" / "s.md"
    store.replace(p, "work survives", place="records.sessions")
    assert p.read_text() == "work survives"
    store.append(paths.activity_file("m"), "x", place="records.activity")
    with pytest.raises(store.WriteRefused, match="paths.yaml"):
        store.replace(home / "Documents" / "f.txt", "x", place="elsewhere", dest=True)


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permission bits")
def test_secret_files_are_0600_and_dirs_0700(home):
    p = store.replace(paths.secrets_shared() / "exa.env", "EXA_API_KEY=fake-exa\n",
                      place="secrets.shared")
    assert stat.S_IMODE(p.stat().st_mode) == 0o600
    assert stat.S_IMODE(p.parent.stat().st_mode) == 0o700
    assert stat.S_IMODE(p.parent.parent.stat().st_mode) == 0o700
    log = (paths.logs_dir() / "writes.jsonl").read_text()
    assert "fake-exa" not in log and '"sha256": null' in log


def test_secret_write_logs_key_names_never_values(home):
    store.replace(paths.secrets_shared() / "exa.env", "EXA_API_KEY=fake-exa\nEXA_X=fake-x\n",
                  place="secrets.shared", keys=("EXA_X", "EXA_API_KEY"))
    row = json.loads((paths.logs_dir() / "writes.jsonl").read_text().splitlines()[-1])
    assert row["keys"] == ["EXA_API_KEY", "EXA_X"] and row["sha256"] is None
    assert "fake" not in json.dumps(row)


def test_secret_written_to_a_user_path_is_logged_as_a_secret(home, tmp_path):
    """dest=True classifies elsewhere/tmp; keys still mark the write secret (no file hash)."""
    store.replace(tmp_path / "mine" / "auth.json", '{"k": "fake"}', place="secrets.local",
                  dest=True, keys=("k",))
    row = json.loads((paths.logs_dir() / "writes.jsonl").read_text().splitlines()[-1])
    assert row["sha256"] is None and row["keys"] == ["k"]


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permission bits")
def test_non_secret_files_follow_umask(home):
    old = os.umask(0o022)
    try:
        p = store.replace(paths.state_dir() / "a.json", "{}", place="state")
    finally:
        os.umask(old)
    assert stat.S_IMODE(p.stat().st_mode) == 0o644


def test_create_never_overwrites(home):
    p = paths.records("sessions", "m") / "proj" / "s.md"
    store.create(p, "one", place="records.sessions")
    with pytest.raises(store.AlreadyExists):
        store.create(p, "two", place="records.sessions")
    assert p.read_text() == "one"
    assert [x.name for x in p.parent.iterdir()] == ["s.md"]  # no temp file left behind


def test_create_without_hard_links_writes_nothing(home, monkeypatch):
    """R20: no fallback that writes the final path directly."""
    def no_links(src, dst, **kw):
        raise OSError(1, "Operation not permitted")
    monkeypatch.setattr(store.os, "link", no_links)
    p = paths.records("sessions", "m") / "proj" / "s.md"
    with pytest.raises(store.ConfigError, match="hard link"):
        store.create(p, "one", place="records.sessions")
    assert not p.exists()
    assert list(p.parent.iterdir()) == []                   # the temp file is gone too


def test_append_one_line_per_call(home):
    p = paths.activity_file("m")
    store.append(p, '{"a":1}', place="records.activity")
    store.append(p, '{"a":2}\n', place="records.activity")
    assert p.read_text().splitlines() == ['{"a":1}', '{"a":2}']


def test_append_under_unicode_home(tmp_path, monkeypatch):
    h = tmp_path / "Лидия Иванова"
    h.mkdir()
    monkeypatch.setenv("HOME", str(h))
    monkeypatch.setenv("USERPROFILE", str(h))
    for k in list(os.environ):
        if k.startswith("H2T_PATH_") or k in paths.OLD_ENV:
            monkeypatch.delenv(k, raising=False)
    p = paths.activity_file("m")
    store.append(p, "x", place="records.activity")
    assert p.read_text(encoding="utf-8") == "x\n"


def test_remove_only_in_package_places(home, tmp_path):
    p = store.replace(paths.state_dir() / "t", "x", place="state")
    store.remove(p, place="state")
    assert not p.exists()
    s = store.replace(paths.records("sessions", "m") / "a.md", "x", place="records.sessions")
    with pytest.raises(store.WriteRefused, match="remove"):
        store.remove(s, place="records.sessions")


def test_writes_log_rotates(home, monkeypatch):
    monkeypatch.setattr(store, "_LOG_LIMIT", 200)
    for i in range(40):
        store.replace(paths.state_dir() / f"f{i}", "x", place="state")
    names = sorted(p.name for p in paths.logs_dir().iterdir())
    assert "writes.jsonl" in names and "writes.1.jsonl" in names
    assert len([n for n in names if n.startswith("writes")]) <= 6


def test_dest_allows_explicit_user_path_but_not_package_places(home, tmp_path):
    out = tmp_path / "anywhere" / "f.txt"
    store.replace(out, "x", place="elsewhere", dest=True)
    assert out.read_text() == "x"
    with pytest.raises(store.WriteRefused):
        store.replace(paths.secrets_shared() / "a.env", "x", place="elsewhere", dest=True)
```

```python
# tests/core/test_store_lock.py
"""Mutual exclusion of store.append, deterministic (§7.3 «Тест блокировки»)."""
import subprocess
import sys
import time

from h2t_ops.core import store

HOLDER = r"""
import os, sys, time
from h2t_ops.core import store
fd = os.open(sys.argv[1], os.O_WRONLY | os.O_APPEND | os.O_CREAT | getattr(os, "O_BINARY", 0), 0o644)
with store._lock(fd):
    print("locked", flush=True)
    time.sleep(1.0)
    os.write(fd, b"A\n")
os.close(fd)
"""


def test_append_waits_for_the_holder(tmp_path, monkeypatch):
    monkeypatch.setenv("H2T_PATH_ROOT", str(tmp_path / "root"))
    target = tmp_path / "root" / "records" / "activity" / "m.jsonl"
    target.parent.mkdir(parents=True)
    holder = subprocess.Popen([sys.executable, "-c", HOLDER, str(target)],
                              stdout=subprocess.PIPE, text=True)
    assert holder.stdout.readline().strip() == "locked"
    t0 = time.monotonic()
    store.append(target, "B", place="records.activity")
    waited = time.monotonic() - t0
    holder.wait(timeout=10)
    assert waited >= 0.7, f"append did not wait for the lock ({waited:.2f}s)"
    assert target.read_text().splitlines() == ["A", "B"]


def test_two_writers_1000_lines_each_stay_whole(tmp_path, monkeypatch):
    monkeypatch.setenv("H2T_PATH_ROOT", str(tmp_path / "root"))
    target = tmp_path / "root" / "records" / "activity" / "m.jsonl"
    code = ("import sys\nfrom h2t_ops.core import store\n"
            "for i in range(1000): store.append(sys.argv[1], sys.argv[2] + str(i) + 'x' * 200, "
            "place='records.activity')\n")
    env = {**__import__("os").environ, "H2T_PATH_ROOT": str(tmp_path / "root")}
    ps = [subprocess.Popen([sys.executable, "-c", code, str(target), tag], env=env) for tag in "PQ"]
    for p in ps:
        assert p.wait(timeout=120) == 0
    lines = target.read_text().splitlines()
    assert len(lines) == 2000
    assert all(len(line) >= 201 and line[0] in "PQ" and line.endswith("x") for line in lines)
```

Run: `.venv/bin/pytest tests/core/test_store.py tests/core/test_store_lock.py -q` → FAIL, импорт.

Тесты блокировки задают `H2T_PATH_ROOT` и ничего больше: старые `H2T_ACTIVITY_SPOOL` и `H2T_SESSION_ROOT`, которые корневой `conftest.py` ставит до Task 7, пакет 4.0 не читает (R5), поэтому `records.activity` остаётся под `H2T_PATH_ROOT` и в тесте, и в дочерних процессах.

- [ ] **Step 2: Реализация.** Ветка Windows в `_lock` — `msvcrt.locking`: проба 11.5 подтвердила взаимное исключение между процессами (B ждал 2,48 с при удержании 3 с). Блокируется байт далеко за концом файла, а не байт 0: блокировка `msvcrt` обязательная, и на байте 0 читатель файла получал бы `PermissionError`.

```python
# h2t_ops/core/store.py
"""The only writer (#548 §7.2): create, append, replace, managed, remove.

Every write is classified by the realpath of its target against every place's root,
whatever place the caller named and wherever the path came from (--dest, a symlink).
A write into vault that does not come through ingest_write is refused. Each write is
logged to logs/writes.jsonl — for doctor and for a person; correctness never rests on it.
"""
from __future__ import annotations

import contextlib
import contextvars
import hashlib
import json
import os
import shutil
import sys
import tempfile
import time
from collections.abc import Iterator
from pathlib import Path

from h2t_ops.core import paths
from h2t_ops.core.errors import ConfigError


class WriteRefused(ConfigError):
    """A write the ownership table (§7.1) does not allow."""


class AlreadyExists(FileExistsError):
    """create() found a file at the target; nothing was written."""


_PACKAGE = ("run", "config", "secrets.shared", "secrets.local", "records.sessions",
            "records.activity", "records.evals", "records.imports", "data", "state", "logs",
            "layout")   # layout.json: a file place, classified by its exact path
_REMOVABLE = {"run", "state", "logs", "tmp", "harness"}
_SECRET = {"secrets.shared", "secrets.local"}
_DEST_FORBIDDEN = {*_PACKAGE, "vault", "legacy", "harness"}
_LOG_LIMIT = 10 * 1024 * 1024
_LOG_KEEP = 5

_INGEST: contextvars.ContextVar[bool] = contextvars.ContextVar("h2t_ingest", default=False)
_MIGRATING: contextvars.ContextVar[bool] = contextvars.ContextVar("h2t_migrating", default=False)
_DELEGATED: dict[str, str] = {}


def _real(p) -> Path:
    return Path(os.path.realpath(p))


def _roots() -> tuple[list[tuple[str, Path]], ConfigError | None]:
    """Every place's real root, deepest first, and the paths.yaml error if there is one.

    A broken paths.yaml must not stop writes inside ~/.h2t (plan R17, gates.md): the package
    places are still classified; only the places it would have declared are unknown.
    """
    out = [(pid, _real(paths.dir_of(pid))) for pid in (*_PACKAGE, "harness", "tmp")]
    broken: ConfigError | None = None
    try:
        declared = {pid: paths.place(pid) for pid in paths.YAML_PLACES}
    except ConfigError as exc:
        declared, broken = {}, exc
    declared["vault"] = paths.vault()
    out += [(pid, _real(p)) for pid, p in declared.items() if p is not None]
    out += [("legacy", _real(p)) for p in paths.legacy_roots()]
    return sorted(out, key=lambda kv: len(kv[1].parts), reverse=True), broken


def _classify(path) -> tuple[str, ConfigError | None]:
    real = _real(path)
    roots, broken = _roots()
    for pid, r in roots:
        if real == r or r in real.parents:
            return pid, broken
    return "elsewhere", broken


def classify(path) -> str:
    return _classify(path)[0]


def _compat_allowed(path: Path) -> bool:
    real = _real(path)
    if real == _real(paths.legacy("google.store") / "tokens.json"):
        return True
    return _MIGRATING.get() and path.name == "MOVED-TO.txt"


def _check(path: Path, place: str, *, dest: bool = False, compat: bool = False) -> str:
    got, broken = _classify(path)
    if broken is not None and got == "elsewhere":
        raise WriteRefused(f"{path}: cannot tell whose place this is while paths.yaml is broken ({broken})",
                           hint="fix it: h2t-ops paths set <place> <path>, or edit the file")
    if got == "vault" and not _INGEST.get():
        raise WriteRefused(f"{path} is inside vault; only ingest writes there",
                           hint="vault is POS's; the package writes raw material to lake (§6)")
    if got == "legacy":
        if compat and _compat_allowed(path):
            return got
        raise WriteRefused(f"{path} is a legacy 3.x location; 4.0 does not write there",
                           hint="write the new place from core.paths; legacy files stay as copies")
    if dest:
        if got in _DEST_FORBIDDEN:
            raise WriteRefused(f"--dest {path} points into {got}", hint="choose a path outside ~/.h2t")
        return got
    if got != place:
        raise WriteRefused(f"{path} is in {got}, not {place}",
                           hint="name the place the path really belongs to")
    return got


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _default_mode(place: str) -> int:
    if place in _SECRET:
        return 0o600
    um = os.umask(0)
    os.umask(um)
    return 0o666 & ~um


def _ensure_dir(directory: Path, place: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    if place in _SECRET and os.name != "nt":
        top = paths.dir_of(place)
        for d in (paths.root() / "secrets", top, directory):
            if d.exists() and (d == top or top in d.parents or d == paths.root() / "secrets"):
                os.chmod(d, 0o700)


def _caller() -> str:
    f = sys._getframe(1)
    here = __file__
    while f is not None and f.f_code.co_filename == here:
        f = f.f_back
    return f"{f.f_globals.get('__name__', '?')}:{f.f_lineno}" if f else "?"


def _rotate(log: Path) -> None:
    try:
        if log.stat().st_size < _LOG_LIMIT:
            return
    except FileNotFoundError:
        return
    for i in range(_LOG_KEEP - 1, 0, -1):
        older = log.with_name(f"writes.{i}.jsonl")
        if older.exists():
            os.replace(older, log.with_name(f"writes.{i + 1}.jsonl"))
    os.replace(log, log.with_name("writes.1.jsonl"))


def _log(op: str, place: str, path: Path, data: bytes | None, *, key: str | None = None,
         keys: tuple[str, ...] = ()) -> None:
    """key: a library or source label; keys: secret key NAMES from core.secrets (§7.2, R41)."""
    row = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "op": op, "place": place, "path": str(path),
           "sha256": None if (data is None or place in _SECRET) else sha256(data),
           "caller": _caller()}
    if key:
        row["key"] = key
    # A write is a secret write if it lands in secrets/* or if core.secrets named its keys:
    # dest=True into a user directory and the Google compat mirror classify elsewhere, yet
    # carry a secret (self-check, round 3).
    if keys:
        row["keys"] = sorted(keys)
        row["sha256"] = None
    log = paths.logs_dir() / "writes.jsonl"
    try:
        log.parent.mkdir(parents=True, exist_ok=True)
        _rotate(log)
        fd = os.open(log, os.O_WRONLY | os.O_APPEND | os.O_CREAT | getattr(os, "O_BINARY", 0), 0o644)
        try:
            with _lock(fd):
                os.write(fd, (json.dumps(row, ensure_ascii=False) + "\n").encode("utf-8"))
        finally:
            os.close(fd)
    except OSError:
        pass  # the journal is for people; a write must not fail because its log row did


_LOCK_OFFSET = 2 ** 40   # far past any real EOF: msvcrt locks are mandatory, and a lock on
                         # byte 0 would make a reader of the file (gather, doctor) fail


@contextlib.contextmanager
def _lock(fd: int) -> Iterator[None]:
    if os.name == "nt":
        import msvcrt
        os.lseek(fd, _LOCK_OFFSET, os.SEEK_SET)
        while True:
            try:
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                break
            except OSError:
                time.sleep(0.02)
        try:
            yield               # O_APPEND writes land at EOF whatever the file position
        finally:
            os.lseek(fd, _LOCK_OFFSET, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
    else:
        import fcntl
        fcntl.flock(fd, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)


def _bytes(data: str | bytes) -> bytes:
    return data.encode("utf-8") if isinstance(data, str) else data


def _tmp_beside(path: Path, payload: bytes, mode: int) -> str:
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix="." + path.name + ".")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(payload)
            fh.flush()
            os.fsync(fh.fileno())
        if os.name != "nt":             # no effect on Windows; the profile ACL protects (§11.3)
            os.chmod(tmp, mode)
    except BaseException:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(tmp)
        raise
    return tmp


def replace(path, data: str | bytes, *, place: str, mode: int | None = None,
            compat: bool = False, dest: bool = False, keys: tuple[str, ...] = ()) -> Path:
    path = Path(path)
    got = _check(path, place, dest=dest, compat=compat)
    payload = _bytes(data)
    _ensure_dir(path.parent, place)
    tmp = _tmp_beside(path, payload, _default_mode(place) if mode is None else mode)
    try:
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(tmp)
        raise
    _log("replace", got, path, payload, keys=keys)
    return path


def create(path, data: str | bytes, *, place: str, mode: int | None = None,
           dest: bool = False, keys: tuple[str, ...] = ()) -> Path:
    path = Path(path)
    got = _check(path, place, dest=dest)
    payload = _bytes(data)
    _ensure_dir(path.parent, place)
    mode = _default_mode(place) if mode is None else mode
    tmp = _tmp_beside(path, payload, mode)
    try:
        try:
            os.link(tmp, path)          # atomic and never overwrites
        except FileExistsError:
            raise AlreadyExists(str(path)) from None
        except OSError as exc:          # no hard links here (FAT, exFAT, some network shares)
            # No fallback into the final path: an interrupted direct write would leave half a
            # file that no manifest owns (§7.2, plan R20).
            raise ConfigError(f"{path.parent}: this filesystem has no hard links, so create "
                              f"cannot publish {path.name} atomically ({exc})",
                              hint="move this place to a local disk: h2t-ops paths set <place> <path>") from exc
    finally:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(tmp)
    _log("create", got, path, payload, keys=keys)
    return path


def append(path, line: str, *, place: str, dest: bool = False) -> None:
    path = Path(path)
    got = _check(path, place, dest=dest)
    payload = (line if line.endswith("\n") else line + "\n").encode("utf-8")
    _ensure_dir(path.parent, place)
    fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT | getattr(os, "O_BINARY", 0),
                 _default_mode(place))
    try:
        with _lock(fd):
            os.write(fd, payload)       # one write() under the lock: one whole line
    finally:
        os.close(fd)
    _log("append", got, path, payload)


def mkdir(path, *, place: str, mode: int | None = None, dest: bool = False) -> Path:
    path = Path(path)
    _check(path, place, dest=dest)
    _ensure_dir(path, place)
    if mode is not None and os.name != "nt":
        os.chmod(path, mode)            # run/rollback/<id> is 0700 (plan R36)
    return path


def _old_config_backup(path: Path, place: str) -> bool:
    """3.x left *.yaml.bak copies in config/; the migration moves them to state/backups (R14)."""
    return place == "config" and _MIGRATING.get() and ".yaml.bak" in path.name


def remove(path, *, place: str, journal: bool = False) -> None:
    path = Path(path)
    got = _check(path, place, compat=journal)
    if place not in _REMOVABLE and not journal and not _old_config_backup(path, place):
        raise WriteRefused(f"remove is not allowed in {place}", hint="only run, state, logs, tmp, harness")
    with contextlib.suppress(FileNotFoundError):
        path.unlink()
    _log("remove", got, path, None)


def remove_tree(path, *, place: str) -> None:
    path = Path(path)
    got = _check(path, place)
    if place not in _REMOVABLE:
        raise WriteRefused(f"remove_tree is not allowed in {place}", hint="only run, state, logs, tmp, harness")
    shutil.rmtree(path, ignore_errors=True)
    _log("remove_tree", got, path, None)


@contextlib.contextmanager
def scratch(prefix: str = "h2t-") -> Iterator[Path]:
    d = Path(tempfile.mkdtemp(prefix=prefix))
    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)
```

- [ ] **Step 3: Зелёный прогон.** `.venv/bin/pytest tests/core/test_store.py tests/core/test_store_lock.py -q` → PASS.

- [ ] **Step 4: Красный контроль блокировки.** В `_lock` заменить тело ветки POSIX на `yield` (без `flock`). `test_append_waits_for_the_holder` → FAIL `append did not wait for the lock` (или порядок `["B","A"]`). Вернуть.

- [ ] **Step 5: Красный контроль классификации.** В `_classify` временно заменить `real = _real(path)` на `real = Path(path).absolute()`. `test_symlink_does_not_launder_a_write` → FAIL. Вернуть. Второй контроль: в `_roots` убрать `try/except ConfigError` → `test_broken_paths_yaml_still_allows_package_writes` FAIL с `ConfigError`. Вернуть. Третий контроль (R20): в ветке `except OSError` у `create` вместо `raise ConfigError` записать `path.write_bytes(payload)` → `test_create_without_hard_links_writes_nothing` FAIL (`DID NOT RAISE`). Вернуть. Четвёртый (R41): в `_log` убрать ветку `if keys:` → `test_secret_write_logs_key_names_never_values` и `test_secret_written_to_a_user_path_is_logged_as_a_secret` FAIL. Вернуть.

- [ ] **Step 6: Commit** — `.venv/bin/python scripts/storage_map.py --check` (новый `store.py` в `ALLOWED` для `writes`/`sqlite`, потолки не должны сдвинуться; сдвинулись — вписать); `git add h2t_ops/core/store.py tests/core/test_store.py tests/core/test_store_lock.py tests/governance/test_storage_ratchets.py`; `feat(core): store.py — the one writer (#548)`.

### Task 5: `store.managed`, `store.repo`, `store.ingest_write`, режим миграции

**Files:**
- Modify: `h2t_ops/core/store.py`
- Create: `h2t_ops/core/repo_writers.py`
- Create: `tests/core/test_store_managed_repo.py`
- Create: `tests/governance/test_single_doors.py`

**Interfaces:**
- Produces:
  - `managed(path, *, place, library: str, dest=False) -> ContextManager[Path]` (регистрирует делегирование на путь и боковые файлы `-journal`, `-wal`, `-shm`; после выхода ставит права места);
  - `delegated(path) -> str | None`;
  - `repo(root: Path, command: str) -> RepoWriter` с методами `create(rel, data)`, `replace(rel, data)`, `append(rel, line)`, `rename(src_rel, dst_rel, *, git: bool)`;
  - `ingest_write(path, data) -> Path`;
  - `migrating() -> ContextManager[None]`;
  - `connect_sqlite(path, *, place, library="sqlite3", dest=False) -> ContextManager[sqlite3.Connection]` — открывает базу внутри `managed(..., dest=dest)` и закрывает на выходе (R18; `dest=True` — база по пути пользователя, например `TelegramClientAdapter(config_dir=…)`, Task 9);
  - `sqlite_copy(src, dest, *, place) -> Path` — копия базы через `sqlite3.Connection.backup`: источник открыт только на чтение (`file:…?mode=ro`), назначение — внутри `managed`, права места (R18; сессия Telegram, Task 9);
  - `writer(path, *, place, mode=None, dest=False) -> ContextManager[BinaryIO]` — потоковая запись через временный файл рядом и `os.replace` (R29; загрузки MeetGeek — Task 11, Dropbox и Drive — Task 12);
  - `repo_writers.REPO_WRITERS: dict[str, dict[str, tuple[str, ...]]]`.

- [ ] **Step 1: Тесты (красные).**

```python
# tests/core/test_store_managed_repo.py
import os
import sqlite3
import stat
import sys

import pytest

from h2t_ops.core import paths, store


@pytest.fixture
def home(tmp_path, monkeypatch):
    h = tmp_path / "home"
    h.mkdir()
    monkeypatch.setenv("HOME", str(h))
    monkeypatch.setenv("USERPROFILE", str(h))
    for k in list(os.environ):
        if k.startswith("H2T_PATH_") or k in paths.OLD_ENV:
            monkeypatch.delenv(k, raising=False)
    return h


def test_managed_registers_delegation_only_while_open(home):
    db = paths.state_dir() / "index.sqlite"
    with store.managed(db, place="state", library="sqlite3") as p:
        assert store.delegated(p) == "sqlite3"
        assert store.delegated(str(p) + "-journal") == "sqlite3"
    assert store.delegated(db) is None


def test_connect_sqlite_opens_inside_the_delegation(home):
    db = paths.state_dir() / "index.sqlite"
    with store.connect_sqlite(db, place="state") as conn:
        assert store.delegated(db) == "sqlite3"
        conn.execute("CREATE TABLE t(x)")
    assert store.delegated(db) is None
    assert sqlite3.connect(db).execute("SELECT name FROM sqlite_master").fetchall() == [("t",)]


def test_connect_sqlite_takes_a_user_path_with_dest(home, tmp_path):
    db = tmp_path / "custom" / "session.session"          # outside every package place
    with pytest.raises(store.WriteRefused):
        with store.connect_sqlite(db, place="secrets.local"):
            pass
    with store.connect_sqlite(db, place="secrets.local", dest=True) as conn:
        conn.execute("CREATE TABLE t(x)")
    assert db.is_file()


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permission bits")
def test_sqlite_copy_is_whole_and_0600_in_secrets(home, tmp_path):
    src = tmp_path / "old.session"
    with sqlite3.connect(src) as c:
        c.execute("CREATE TABLE s(k)")
        c.execute("INSERT INTO s VALUES ('fake')")
    dest = paths.secrets_local() / "telegram.session"
    store.sqlite_copy(src, dest, place="secrets.local")
    assert sqlite3.connect(dest).execute("SELECT k FROM s").fetchall() == [("fake",)]
    assert stat.S_IMODE(dest.stat().st_mode) == 0o600


def test_old_config_backup_removable_only_while_migrating(home):
    bak = paths.config_dir() / "domains.yaml.bak"
    store.replace(bak, "x", place="config")
    with pytest.raises(store.WriteRefused):
        store.remove(bak, place="config")
    with store.migrating():
        store.remove(bak, place="config")
    assert not bak.exists()


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permission bits")
def test_managed_secret_gets_0600(home):
    sess = paths.secrets_local() / "telegram.session"
    with store.managed(sess, place="secrets.local", library="telethon") as p:
        p.write_bytes(b"x")  # stands in for the library
    assert stat.S_IMODE(sess.stat().st_mode) == 0o600


def test_repo_writer_honours_allow_list(home, tmp_path):
    # `home` matters: create() logs to logs/writes.jsonl and parses paths.yaml, and without
    # it both are the developer's real ~/.h2t until Task 7 isolates the suite.
    repo = tmp_path / "r"
    repo.mkdir()
    w = store.repo(repo, "init-project")
    w.create(".claude/project-id", "dev/x\n")
    assert (repo / ".claude" / "project-id").read_text() == "dev/x\n"
    with pytest.raises(store.WriteRefused, match="init-project"):
        w.replace(".claude/project-id", "dev/y\n")   # create if absent only (§7.1, R32)
    with pytest.raises(store.WriteRefused, match="init-project"):
        w.replace("README.md", "x")
    with pytest.raises(store.WriteRefused, match="outside"):
        w.create("../escape", "x")


def test_unknown_command_is_refused(home, tmp_path):
    with pytest.raises(store.WriteRefused, match="not in the repo allow-list"):
        store.repo(tmp_path, "h2t-something-new")


def test_ingest_is_the_vault_door(home, tmp_path, monkeypatch):
    vault = tmp_path / "vault"
    monkeypatch.setenv("H2T_PATH_VAULT", str(vault))
    store.ingest_write(vault / "n.md", "note")
    assert (vault / "n.md").read_text() == "note"


def test_moved_marker_only_while_migrating(home):
    legacy = paths.legacy("sessions.h2t")
    legacy.mkdir(parents=True)
    with pytest.raises(store.WriteRefused):
        store.replace(legacy / "MOVED-TO.txt", "x", place="legacy", compat=True)
    with store.migrating():
        store.replace(legacy / "MOVED-TO.txt", "x", place="legacy", compat=True)
    assert (legacy / "MOVED-TO.txt").exists()


def test_writer_streams_and_replaces_atomically(home):
    p = paths.state_dir() / "big.bin"
    with store.writer(p, place="state") as fh:
        for _ in range(3):
            fh.write(b"x" * 10)
        assert not p.exists()                     # nothing at the final path until exit
    assert p.read_bytes() == b"x" * 30
    with pytest.raises(RuntimeError):
        with store.writer(p, place="state") as fh:
            fh.write(b"half")
            raise RuntimeError("network dropped")
    assert p.read_bytes() == b"x" * 30            # the old file survives an interrupted stream
    assert [x.name for x in p.parent.iterdir()] == ["big.bin"]
```

```python
# tests/governance/test_single_doors.py
"""ingest_write and remove(journal=True) have no import site outside their one module
(§7.2, plan R1, R35). Until subsystem 4 adds h2t_ops/ingest/, "exactly one" cannot hold;
it becomes `==` there."""
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _sites(rx):
    # --others: a planted, unstaged file must count, or the red control cannot go red.
    files = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard", "h2t_ops/"],
                           cwd=ROOT, capture_output=True, text=True, check=True).stdout.split()
    return [f for f in files if f.endswith(".py") and f != "h2t_ops/core/store.py"
            and (ROOT / f).is_file() and re.search(rx, (ROOT / f).read_text(encoding="utf-8"))]


def test_ingest_write_only_in_the_ingest_module():
    assert [s for s in _sites(r"\bingest_write\b") if not s.startswith("h2t_ops/ingest/")] == []


def test_journal_remove_only_in_rollback():
    assert set(_sites(r"journal\s*=\s*True")) <= {"h2t_ops/setup/layout/rollback.py"}
```

- [ ] **Step 2: Реализация.** В импорты `store.py` добавить `import sqlite3` (по алфавиту, после `shutil`) и `BinaryIO` в `from typing import BinaryIO`, затем дописать:

```python
def delegated(path) -> str | None:
    real = str(_real(path))
    for key, lib in _DELEGATED.items():
        if real == key or real.startswith(key + "-"):
            return lib
    return None


@contextlib.contextmanager
def managed(path, *, place: str, library: str, dest: bool = False) -> Iterator[Path]:
    """Resolve and check the path, then hand the file to a library that opens it itself."""
    path = Path(path)
    got = _check(path, place, dest=dest)
    _ensure_dir(path.parent, place)
    key = str(_real(path))
    _DELEGATED[key] = library
    try:
        yield path
    finally:
        _DELEGATED.pop(key, None)
        if os.name != "nt":             # Windows: the profile ACL protects (§11.3)
            mode = _default_mode(place)
            for side in (path, *(path.with_name(path.name + s) for s in ("-journal", "-wal", "-shm"))):
                if side.exists():
                    with contextlib.suppress(OSError):
                        os.chmod(side, mode)
        _log("managed", got, path, None, key=library)


@contextlib.contextmanager
def writer(path, *, place: str, mode: int | None = None, dest: bool = False) -> Iterator[BinaryIO]:
    """A stream into a temp file beside the target, published by os.replace on a clean exit
    (plan R29). An exception leaves the old file, if any, untouched."""
    path = Path(path)
    got = _check(path, place, dest=dest)
    _ensure_dir(path.parent, place)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix="." + path.name + ".")
    try:
        with os.fdopen(fd, "wb") as fh:
            yield fh
            fh.flush()
            os.fsync(fh.fileno())
        if os.name != "nt":
            os.chmod(tmp, _default_mode(place) if mode is None else mode)
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(tmp)
        raise
    _log("replace", got, path, None)


@contextlib.contextmanager
def connect_sqlite(path, *, place: str, library: str = "sqlite3",
                   dest: bool = False) -> Iterator[sqlite3.Connection]:
    """The one sqlite3.connect in the package (plan R18)."""
    with managed(path, place=place, library=library, dest=dest) as p:
        conn = sqlite3.connect(p)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()


def sqlite_copy(src, dest, *, place: str) -> Path:
    """Copy a live SQLite file whole: backup() reads a consistent snapshot even if another
    process has the source open, where a byte copy can tear it (plan R18, Task 9)."""
    src = Path(src)
    source = sqlite3.connect(f"file:{src.as_posix()}?mode=ro", uri=True)
    try:
        with connect_sqlite(dest, place=place, library="sqlite-backup") as target:
            source.backup(target)
    finally:
        source.close()
    return Path(dest)


def ingest_write(path, data: str | bytes) -> Path:
    """The vault's single door (§7.2). One import site: the ingest module (subsystem 4)."""
    token = _INGEST.set(True)
    try:
        return replace(path, data, place="vault")
    finally:
        _INGEST.reset(token)


@contextlib.contextmanager
def migrating() -> Iterator[None]:
    token = _MIGRATING.set(True)
    try:
        yield
    finally:
        _MIGRATING.reset(token)


class RepoWriter:
    def __init__(self, root: Path, command: str, rules: dict[str, tuple[str, ...]]):
        self.root, self.command, self.rules = _real(root), command, rules

    def _target(self, op: str, rel: str) -> Path:
        import fnmatch
        target = _real(self.root / rel)
        if target != self.root and self.root not in target.parents:
            raise WriteRefused(f"{rel} is outside the repository {self.root}", hint="")
        posix = target.relative_to(self.root).as_posix()
        if not any(fnmatch.fnmatchcase(posix, g) for g in self.rules.get(op, ())):
            raise WriteRefused(f"{self.command} may not {op} {posix}",
                               hint="h2t_ops/core/repo_writers.py lists what each command writes")
        if classify(target) not in ("elsewhere", "tmp", "repo"):
            raise WriteRefused(f"{target} is a package or external place, not a repository", hint="")
        return target

    def create(self, rel: str, data) -> Path:
        t = self._target("create", rel)
        return create(t, data, place="repo", dest=True)

    def replace(self, rel: str, data) -> Path:
        t = self._target("replace", rel)
        return replace(t, data, place="repo", dest=True)

    def append(self, rel: str, line: str) -> None:
        t = self._target("append", rel)
        append(t, line, place="repo", dest=True)

    def rename(self, src_rel: str, dst_rel: str, *, git: bool) -> Path:
        src, dst = self._target("rename", src_rel), self._target("rename", dst_rel)
        dst.parent.mkdir(parents=True, exist_ok=True)
        if git:
            import subprocess
            subprocess.run(["git", "mv", str(src), str(dst)], cwd=self.root, check=True,
                           capture_output=True)
        else:
            os.replace(src, dst)
        _log("rename", "repo", dst, None, key=str(src))
        return dst


def repo(root, command: str) -> RepoWriter:
    from h2t_ops.core.repo_writers import REPO_WRITERS
    if command not in REPO_WRITERS:
        raise WriteRefused(f"{command!r} is not in the repo allow-list",
                           hint="add it to h2t_ops/core/repo_writers.py with what it writes")
    return RepoWriter(Path(root), command, REPO_WRITERS[command])
```

`_DEST_FORBIDDEN` не содержит `"repo"` и `"tmp"`, поэтому `dest=True` пропускает запись внутри репо, лежащего во временном каталоге теста.

```python
# h2t_ops/core/repo_writers.py
"""What each command may write into the user's repository (#548 §7.1, table «repo»).

Globs are fnmatch on the POSIX path relative to the repository root; `*` crosses `/`.
Task 17 replaces the starting set below with the measured one and pins it with a test that
runs every command in a scratch repository.
"""
REPO_WRITERS: dict[str, dict[str, tuple[str, ...]]] = {
    # §7.1: .claude/project-id — "create if absent"; an existing file is kept (plan R32).
    "init-project": {"create": (".claude/project-id",)},
    "h2t-project-register": {"create": (".claude/project-id",)},
}
```

- [ ] **Step 3: Зелёный и красный прогоны.** `.venv/bin/pytest tests/core/test_store_managed_repo.py tests/governance/test_single_doors.py -q` → PASS. Контроли, каждый с возвратом:
  - в `RepoWriter._target` убрать проверку `fnmatch` → `test_repo_writer_honours_allow_list` FAIL;
  - в `writer` вместо временного файла открыть сам `path` (`open(path, "wb")`, без `os.replace`) → `test_writer_streams_and_replaces_atomically` FAIL на `assert not p.exists()`;
  - подложить неотслеживаемый `h2t_ops/zz_probe.py` с `from h2t_ops.core.store import ingest_write` и строкой `store.remove(p, place="x", journal=True)` → оба теста `test_single_doors.py` FAIL с `zz_probe.py`. Удалить файл.

`RepoWriter._target` отказывает репо, которое лежит внутри места пакета. У автора `~/.h2t/config` — git-репо; `docs-lint` и `init-project`, запущенные в нём как в репо, получат отказ. Это намеренно: `config/` правится через `store.replace(place="config")`, а не через список `repo`.

- [ ] **Step 4: Commit** — `git add h2t_ops/core/store.py h2t_ops/core/repo_writers.py tests/core/test_store_managed_repo.py tests/governance/test_single_doors.py`; `feat(core): store.managed, sqlite doors, repo allow-list, ingest door (#548)`.

### Task 6: `core/providers.py` и новый `core/secrets.py`

**Files:**
- Create: `h2t_ops/core/providers.py`
- Modify: `h2t_ops/core/secrets.py` (переписать целиком, сохранив публичные имена `load_secrets`, `resolve_notion_token`, `candidate_secret_files`)
- Create: `tests/core/test_secrets_v4.py`
- Create: `tests/governance/test_secret_names.py`
- Modify: `tests/core/test_secrets.py`, `tests/core/test_secrets_precedence.py`, `tests/test_secrets_path_parity.py` (под новый порядок; старый порядок остаётся как запасной)
- Modify: `tests/connectors/research/test_client.py:72-74,83-85` и `tests/test_setup_doctor_checks.py:84-86` — они патчат удаляемые `H2T_CONFIG_SECRETS`/`DEFAULT_SECRETS`/`LEGACY_SECRETS` с `raising=True` и падают с `AttributeError`; перевести на запись файлов по `paths.legacy(...)` под временным `HOME`
- Modify: `tests/connectors/conftest.py:23` — строка с `H2T_SECRETS_FILE` удаляется: новый `secrets.py` разрешает пути при вызове, а не при импорте, и переменную не читает (R5); `HOME`/`USERPROFILE` той же фикстуры достаточно

**Interfaces:**
- Produces:
  - `providers.CONNECTOR_PROVIDERS: dict[str, tuple[str, ...]]`, `providers.KEY_PREFIX: dict[str, str]`, `providers.provider_of_key(key: str) -> str | None`, `providers.is_package_provider(stem: str) -> bool`, `providers.FILE_NAME = re.compile(...)`;
  - `secrets.parse_env(text: str) -> dict[str, str]` (разбор 3.x плюс BOM и `export `, Review Focus 5);
  - `secrets.get(key: str) -> str | None`;
  - `secrets.load_secrets(env_file: Path | None = None) -> None`;
  - `secrets.candidate_secret_files(env_file=None) -> list[Path]` — файлы провайдеров пакета и `other.env` в `shared`, затем старая лестница; чужие `.env` (`getcourse.env` и т.п.) не возвращаются (§4);
  - `secrets.provider_file(provider: str, *, local=False) -> Path`;
  - `secrets.json_path(name: str) -> Path`;
  - `secrets.read_json(name: str) -> tuple[dict | None, Path | None]` для `google.client`, `google.token`, `telegram.auth-state`;
  - `secrets.telegram_legacy_config(config_dir: Path | None = None) -> dict | None` — `config.json` старого каталога Telegram (или `<config_dir>/config.json`, R42) через `core/jsonfile.read_json_config` (BOM и номер строки в ошибке, как в 3.x; `tests/connectors/test_config_bom.py:30-35` держит `"line 1"`);
  - `secrets.write_json(name: str, data: dict) -> Path`;
  - `secrets.write_env(provider: str, values: dict[str, str], *, local: bool = False) -> Path`;
  - `secrets.legacy_sources() -> list[tuple[str, Path]]`;
  - `secrets.resolve_notion_token() -> str`;
  - читатели для миграции (R38; потребители — Task 22, Task 23, `verify.py`, Task 10 `secrets skeleton`):
    - `secrets.migration_sources() -> list[tuple[str, Path, dict[str, str]]]` — старшим первым: файл из `paths.old_env_by_use("secrets-source")` (источник `secretsfile`), затем `legacy_sources()`; только существующие файлы, файл, встретившийся дважды (по `realpath`), — один раз на старшем месте; третий элемент — `parse_env` файла;
    - `secrets.shared_env_values() -> dict[str, dict[str, str]]` — имя → разбор для каждого `*.env` и `*.env.from-*` в `secrets/shared`; нет каталога — `{}`;
    - `secrets.read_secret_bytes(path: Path, *, root: Path | None = None) -> bytes` — байты файла под `secrets/` или под старым местом секретов (`secret_dirs` Task 7: `secrets.h2t`, `secrets.dor`, `secrets.dor_old`, `notion.token`, `google.store`, `google.gmail`, `google.dor`, `telegram`); с `root` — только внутри этого явно названного каталога (`config_dir=` Telegram, `secrets_dir` skeleton, R42); другой путь → `ConfigError`;
    - `secrets.read_json_at(path: Path, *, root: Path) -> dict | None` — JSON секрета в явно названном каталоге (auth-state Telegram при `config_dir=`, R42);
    - `secrets.notion_legacy_token() -> str | None` — содержимое `~/.config/notion/token` без пробелов, пустое — `None` (его же зовёт `resolve_notion_token`).

- [ ] **Step 1: Реестр провайдеров.**

```python
# h2t_ops/core/providers.py
"""Connector → providers, and the key prefix each provider owns (#548 §4).

A provider is the external service, not the connector: research talks to exa and jina.
"""
from __future__ import annotations

import re

CONNECTOR_PROVIDERS: dict[str, tuple[str, ...]] = {
    "notion": ("notion",), "gmail": ("google",), "calendar": ("google",), "drive": ("google",),
    "google": ("google",), "telegram": ("telegram",), "meetgeek": ("meetgeek",),
    "granola": ("granola",), "dropbox": ("dropbox",), "research": ("exa", "jina"),
    "evals": ("h2t-evals",),
}
KEY_PREFIX: dict[str, str] = {
    "notion": "NOTION_", "telegram": "TELEGRAM_", "meetgeek": "MEETGEEK_", "granola": "GRANOLA_",
    "dropbox": "DROPBOX_", "exa": "EXA_", "jina": "JINA_", "h2t-evals": "H2T_EVALS_",
}
PROVIDERS = frozenset(p for ps in CONNECTOR_PROVIDERS.values() for p in ps)
FILE_NAME = re.compile(r"^(?P<provider>[a-z0-9-]+)\.(env|client\.json|token\.json|session|auth-state\.json)$")
EXEMPT = re.compile(r"^other\.env$|\.from-[A-Za-z0-9_-]+(\.[a-z.]+)?$")


def provider_of_key(key: str) -> str | None:
    best = None
    for provider, prefix in KEY_PREFIX.items():
        if key.startswith(prefix) and (best is None or len(prefix) > len(KEY_PREFIX[best])):
            best = provider
    return best


def is_package_provider(stem: str) -> bool:
    return stem in PROVIDERS
```

- [ ] **Step 2: Тесты (красные).**

```python
# tests/core/test_secrets_v4.py
import os

import pytest

from h2t_ops.core import paths, secrets


@pytest.fixture
def home(tmp_path, monkeypatch):
    h = tmp_path / "home"
    h.mkdir()
    monkeypatch.setenv("HOME", str(h))
    monkeypatch.setenv("USERPROFILE", str(h))
    for k in list(os.environ):
        if k.startswith(("H2T_PATH_", "EXA_", "JINA_", "NOTION_", "MEETGEEK_", "GRANOLA_",
                         "DROPBOX_", "TELEGRAM_", "H2T_EVALS_")) or k in paths.OLD_ENV:
            monkeypatch.delenv(k, raising=False)
    return h


def _w(p, text):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def test_new_provider_file_wins_and_legacy_is_not_read_for_that_provider(home):
    _w(paths.secrets_shared() / "exa.env", "EXA_API_KEY=fake-new\n")
    _w(paths.legacy("secrets.dor_old"), "EXA_API_KEY=fake-old\nNOTION_API_TOKEN=fake-notion\n")
    assert secrets.get("EXA_API_KEY") == "fake-new"
    assert secrets.get("NOTION_API_TOKEN") == "fake-notion"  # no notion.env yet: fallback


def test_environment_beats_files(home, monkeypatch):
    _w(paths.secrets_shared() / "exa.env", "EXA_API_KEY=fake-file\n")
    monkeypatch.setenv("EXA_API_KEY", "fake-env")
    assert secrets.get("EXA_API_KEY") == "fake-env"


def test_legacy_ladder_order_is_3x_order(home):
    _w(paths.legacy("secrets.h2t") / "secrets.env", "MEETGEEK_API_KEY=fake-a\n")
    _w(paths.legacy("secrets.dor"), "MEETGEEK_API_KEY=fake-b\nGRANOLA_API_KEY=fake-g\n")
    assert secrets.get("MEETGEEK_API_KEY") == "fake-a"
    assert secrets.get("GRANOLA_API_KEY") == "fake-g"


def test_secrets_file_variable_is_not_read(home, monkeypatch, tmp_path):
    only = tmp_path / "only.env"
    _w(only, "GRANOLA_API_KEY=fake-only\n")
    _w(paths.legacy("secrets.dor"), "GRANOLA_API_KEY=fake-b\nMEETGEEK_API_KEY=fake-m\n")
    monkeypatch.setenv("H2T_SECRETS_FILE", str(only))      # 3.x name; 4.0 ignores it (R5)
    assert secrets.get("GRANOLA_API_KEY") == "fake-b"
    assert secrets.get("MEETGEEK_API_KEY") == "fake-m"
    assert only not in secrets.candidate_secret_files()


def test_foreign_env_files_are_not_candidates(home):
    _w(paths.secrets_shared() / "exa.env", "EXA_API_KEY=fake\n")
    _w(paths.secrets_shared() / "other.env", "ZZZ=fake\n")
    _w(paths.secrets_shared() / "getcourse.env", "EXA_API_KEY=fake-foreign\n")
    names = [p.name for p in secrets.candidate_secret_files()]
    assert "exa.env" in names and "other.env" in names and "getcourse.env" not in names


def test_env_parse_matches_3x_on_awkward_files():
    text = '\ufeffA=1\r\n# c\r\nexport B="two"\nC=\'three\'\n D = four \nbad line\n'
    assert secrets.parse_env(text) == {"A": "1", "B": "two", "C": "three", "D": "four"}


def test_load_secrets_merges_without_override(home, monkeypatch):
    _w(paths.secrets_shared() / "granola.env", "GRANOLA_API_KEY=fake-g\n")
    monkeypatch.setenv("GRANOLA_API_KEY", "fake-env")
    secrets.load_secrets()
    assert os.environ["GRANOLA_API_KEY"] == "fake-env"


def test_google_json_new_then_legacy(home):
    _w(paths.legacy("google.store") / "tokens.json", '{"refresh_token": "fake-old"}')
    data, where = secrets.read_json("google.token")
    assert data == {"refresh_token": "fake-old"} and where.name == "tokens.json"
    secrets.write_json("google.token", {"refresh_token": "fake-new"})
    data, where = secrets.read_json("google.token")
    assert data == {"refresh_token": "fake-new"} and where == paths.secrets_local() / "google.token.json"


def test_notion_token_file_is_last_resort(home):
    _w(paths.legacy("notion.token"), "fake-file-token\n")
    assert secrets.resolve_notion_token() == "fake-file-token"
    _w(paths.secrets_shared() / "notion.env", "NOTION_API_TOKEN=fake-env-file\n")
    assert secrets.resolve_notion_token() == "fake-env-file"
```

Имя `parse_env` в 3.x не существовало: разбор жил внутри `load_secrets` (`core/secrets.py:64-71`). Первым шагом вынести его как есть, без изменения поведения. Кавычки срезаются `strip('"').strip("'")`, BOM и `export ` в 3.x **не** обрабатывались. Тест фиксирует новое поведение: BOM и `export ` распознаются. Это расширение, а не изменение: строка `export B=…` в 3.x давала ключ `export B`, который никто не читал.

```python
# tests/governance/test_secret_names.py
"""Every file the package writes into secrets/ matches the naming contract (§4, §7.3)."""
from h2t_ops.core import providers


def test_package_names_match():
    for name in ("notion.env", "exa.env", "google.client.json", "google.token.json",
                 "telegram.session", "telegram.auth-state.json", "h2t-evals.env"):
        m = providers.FILE_NAME.match(name)
        assert m and providers.is_package_provider(m["provider"]), name


def test_exemptions_and_rejections():
    assert providers.EXEMPT.search("other.env")
    assert providers.EXEMPT.search("exa.env.from-dor")
    assert not providers.FILE_NAME.match("google-calendar-mcp.json")
    assert not providers.is_package_provider("calendar")


def test_every_secret_write_uses_a_package_name(tmp_path, monkeypatch):
    """Every writer secrets.py has, for every name it accepts, recorded at store.replace —
    the one call that lands a file in secrets/. A new provider or _JSON entry with a
    non-contract name turns this red without anyone listing it here."""
    import os

    from h2t_ops.core import paths, secrets, store
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    for k in list(os.environ):
        if k.startswith("H2T_PATH_"):
            monkeypatch.delenv(k)
    seen: list[tuple[str, str]] = []
    real = store.replace

    def recording(path, data, *, place, **kw):
        seen.append((place, os.path.basename(path)))
        return real(path, data, place=place, **kw)

    monkeypatch.setattr(store, "replace", recording)
    for provider in sorted(providers.PROVIDERS):
        secrets.write_env(provider, {"X": "fake"})
        secrets.write_env(provider, {"X": "fake"}, local=True)
    for name in sorted(secrets._JSON):
        secrets.write_json(name, {"k": "fake"})
    secret_writes = [n for place, n in seen if place in ("secrets.shared", "secrets.local")]
    assert len(secret_writes) == 2 * len(providers.PROVIDERS) + len(secrets._JSON)
    for name in secret_writes:
        m = providers.FILE_NAME.match(name)
        assert m and providers.is_package_provider(m["provider"]), name
```

Красный контроль этого теста: в `secrets._JSON` имя файла `telegram.auth-state.json` заменить на `telegram_auth_state.json` → FAIL с этим именем. Вернуть.

- [ ] **Step 3: Реализация `secrets.py`.**

```python
# h2t_ops/core/secrets.py
"""The only reader of secrets (#548 §4, §7.2).

New places: ~/.h2t/secrets/shared/<provider>.env and provider-format files, and
secrets/local for what must not leave the machine. Through 4.0.x the 3.x ladder is read as
a fallback — but only for a provider that has no new file yet, so a stale legacy value can
never shadow a migrated one. 4.1 deletes the fallback.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from h2t_ops.core import paths, providers, store
from h2t_ops.core.errors import ConfigError

_JSON = {"google.client": ("secrets.shared", "google.client.json"),
         "google.token": ("secrets.local", "google.token.json"),   # per machine (R19)
         "telegram.auth-state": ("secrets.local", "telegram.auth-state.json")}


def parse_env(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for raw in text.lstrip("\ufeff").splitlines():   # escaped: a literal BOM vanishes in copy-paste
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        if key.startswith("export "):
            key = key[len("export "):].strip()
        if key and key not in out:
            out[key] = val.strip().strip('"').strip("'")
    return out


def _read_env(path: Path) -> dict[str, str]:
    try:
        return parse_env(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, UnicodeDecodeError):
        return {}


def provider_file(provider: str, *, local: bool = False) -> Path:
    base = paths.secrets_local() if local else paths.secrets_shared()
    return base / f"{provider}.env"


def legacy_sources() -> list[tuple[str, Path]]:
    """The 3.x ladder, in its order (core/secrets.py of 3.3.0 — #432, #483).

    H2T_SECRETS_FILE is not read any more (plan R5); the migration takes its file as one more
    source through paths.old_env_by_use("secrets-source") (Task 22)."""
    d = paths.legacy("secrets.h2t")
    out = [("h2t-config", d / "secrets.env")]
    if d.is_dir():
        out += [(f"h2t-config-{p.stem}", p) for p in sorted(d.glob("*.env"), key=lambda p: p.name)
                if p.name != "secrets.env"]
    return out + [("dor-secrets", paths.legacy("secrets.dor")), ("dor", paths.legacy("secrets.dor_old"))]


def candidate_secret_files(env_file: Path | None = None) -> list[Path]:
    """Files the package reads keys from: its providers' files and other.env, then the 3.x
    ladder. Foreign files in shared (getcourse.env, …) are not the package's to read (§4)."""
    if env_file is not None:
        return [env_file]
    shared = paths.secrets_shared()
    new = [shared / f"{p}.env" for p in sorted(providers.PROVIDERS)] + [shared / "other.env"]
    return [*(p for p in new if p.is_file()), *(p for _, p in legacy_sources())]


def _new_values() -> dict[str, str]:
    out: dict[str, str] = {}
    shared = paths.secrets_shared()
    for provider in sorted(providers.PROVIDERS) + ["other"]:
        for key, val in _read_env(shared / f"{provider}.env").items():
            out.setdefault(key, val)
    return out


def _migrated(provider: str | None) -> bool:
    name = f"{provider}.env" if provider else "other.env"
    return (paths.secrets_shared() / name).is_file()


def get(key: str) -> str | None:
    if os.environ.get(key):
        return os.environ[key]
    new = _new_values()
    if key in new:
        return new[key]
    if _migrated(providers.provider_of_key(key)):
        return None
    for _, path in legacy_sources():
        val = _read_env(path).get(key)
        if val is not None:
            return val
    return None


def load_secrets(env_file: Path | None = None) -> None:
    """Merge every known key into os.environ without overriding (3.x contract kept)."""
    if env_file is not None:
        merged = _read_env(env_file)
    else:
        merged = dict(_new_values())
        for _, path in legacy_sources():
            for key, val in _read_env(path).items():
                if key not in merged and not _migrated(providers.provider_of_key(key)):
                    merged[key] = val
    for key, val in merged.items():
        if key and key not in os.environ:
            os.environ[key] = val


def _legacy_json(name: str) -> list[Path]:
    if name == "google.client":
        return [paths.legacy("google.store") / "credentials.json",
                paths.legacy("google.gmail") / "credentials.json", paths.legacy("google.dor")]
    if name == "google.token":
        return [paths.legacy("google.store") / "tokens.json", paths.legacy("google.gmail") / "token.json"]
    if name == "telegram.auth-state":
        return [paths.legacy("telegram") / "auth_state.json"]
    raise KeyError(name)


def json_path(name: str) -> Path:
    place, file = _JSON[name]
    return paths.dir_of(place) / file


def read_json(name: str) -> tuple[dict | None, Path | None]:
    for path in (json_path(name), *_legacy_json(name)):
        if path.is_file():
            try:
                return json.loads(path.read_bytes().decode("utf-8-sig")), path
            except (ValueError, UnicodeDecodeError) as exc:
                raise ConfigError(f"{path} is not valid JSON: {exc}", hint="re-save it as UTF-8 JSON") from exc
    return None, None


def telegram_legacy_config(config_dir: Path | None = None) -> dict | None:
    """api_id/api_hash from the 3.x ~/.config/telegram/config.json (fallback in 4.0.x), or from
    <config_dir>/config.json when the caller names its own directory (Task 9, R42).

    Read with jsonfile.read_json_config, as 3.x did: BOM-tolerant, line numbers in errors."""
    from h2t_ops.core.jsonfile import read_json_config
    path = (Path(config_dir) if config_dir is not None else paths.legacy("telegram")) / "config.json"
    return read_json_config(path) if path.is_file() else None


def read_json_at(path: Path, *, root: Path) -> dict | None:
    """A secret JSON file in a directory the caller names explicitly (config_dir=); None if absent."""
    if not Path(path).is_file():
        return None
    raw = read_secret_bytes(path, root=root)
    try:
        return json.loads(raw.decode("utf-8-sig"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise ConfigError(f"{path} is not valid JSON: {exc}", hint="re-save it as UTF-8 JSON") from exc


def write_json(name: str, data: dict) -> Path:
    place, _ = _JSON[name]
    return store.replace(json_path(name), json.dumps(data, ensure_ascii=False, indent=2), place=place,
                         keys=tuple(data))       # field names only (R41)


def write_env(provider: str, values: dict[str, str], *, local: bool = False) -> Path:
    body = "".join(f"{k}={v}\n" for k, v in values.items())
    return store.replace(provider_file(provider, local=local), body,
                         place="secrets.local" if local else "secrets.shared", keys=tuple(values))


def notion_legacy_token() -> str | None:
    cfg = paths.legacy("notion.token")
    if not cfg.is_file():
        return None
    return cfg.read_text(encoding="utf-8").strip() or None


def resolve_notion_token() -> str:
    tok = get("NOTION_API_TOKEN")
    if tok:
        return tok
    if not _migrated("notion"):
        text = notion_legacy_token()
        if text:
            return text
    raise ConfigError("Notion API token not found.",
                      hint=f"Set NOTION_API_TOKEN in {provider_file('notion')}")


# --- readers for the migration (plan R38): it reads secrets only through these -------------

_SECRET_LEGACY = ("secrets.h2t", "secrets.dor", "secrets.dor_old", "notion.token",
                  "google.store", "google.gmail", "google.dor", "telegram")


def migration_sources() -> list[tuple[str, Path, dict[str, str]]]:
    """Senior first: the 3.x H2T_SECRETS_FILE file once, then the 3.x ladder. A file that
    appears twice (the variable pointing at a ladder file) counts once, at its senior place."""
    out = [("secretsfile", p) for p in paths.old_env_by_use("secrets-source").values()]
    out += legacy_sources()
    seen: set[str] = set()
    result = []
    for name, p in out:
        real = os.path.realpath(p)
        if p.is_file() and real not in seen:
            seen.add(real)
            result.append((name, p, _read_env(p)))
    return result


def shared_env_values() -> dict[str, dict[str, str]]:
    shared = paths.secrets_shared()
    if not shared.is_dir():
        return {}
    return {p.name: _read_env(p) for p in sorted(shared.iterdir())
            if p.name.endswith(".env") or ".env.from-" in p.name}


def read_secret_bytes(path: Path, *, root: Path | None = None) -> bytes:
    """root: a directory the user named explicitly (--secrets-dir, config_dir=) — the only
    other place a secret may be read from; without it, secrets/ and the 3.x secret places."""
    real = Path(os.path.realpath(path))
    roots = ([Path(root)] if root is not None
             else [paths.root() / "secrets", *(paths.legacy(n) for n in _SECRET_LEGACY)])
    if not any(real == Path(os.path.realpath(r)) or Path(os.path.realpath(r)) in real.parents
               for r in roots):
        raise ConfigError(f"{path} is not a secrets location", hint="read it through its own module")
    return real.read_bytes()
```

Тест читателей миграции — в `tests/core/test_secrets_v4.py`: `migration_sources()` с заданной старой переменной на файл лестницы даёт его один раз, первым (`secretsfile`); `shared_env_values()` без каталога — `{}`; `read_secret_bytes(home / "notes.txt")` → `ConfigError`. Красный контроль: убрать проверку корня в `read_secret_bytes` → последний тест FAIL.

- [ ] **Step 4: Старые тесты секретов.** `tests/core/test_secrets.py` патчит удалённые константы `DEFAULT_SECRETS`, `LEGACY_SECRETS`, `H2T_CONFIG_SECRETS`. Перевести их на `HOME`/`USERPROFILE` во временный каталог и запись файлов по `paths.legacy(...)`. Утверждения о порядке 3.x сохранить: он теперь запасной. `tests/core/test_secrets_precedence.py` (дочерний интерпретатор) оставить, добавить случай «новый файл провайдера старше всех старых». `tests/test_secrets_path_parity.py` перевести на `secrets.candidate_secret_files()`. Утверждения о `H2T_SECRETS_FILE` во всех трёх файлах переписать на «переменная не читается» (R5). `tests/connectors/research/test_client.py` и `tests/test_setup_doctor_checks.py` — по списку Files.

Run: `.venv/bin/pytest tests/core/test_secrets_v4.py tests/core/test_secrets.py tests/core/test_secrets_precedence.py tests/test_secrets_path_parity.py tests/test_setup_doctor_checks.py tests/governance/test_secret_names.py tests/connectors -q` → PASS.

- [ ] **Step 5: Права на Windows — ветка «ACL профиля закрыт» (проба 11.3).** `os.chmod(0o600)` на Windows без эффекта, а файл наследует ACL профиля: владелец, Administratoren, SYSTEM. Поэтому в `store` для Windows ничего не добавляется (`_ensure_dir` уже пропускает `chmod` при `os.name == "nt"`), `icacls` не вызывается. Тесты прав остаются под `skipif(sys.platform == "win32")`; `doctor` (Task 20) и сверка миграции (Task 22) на Windows о правах молчат — ни ошибки, ни строки «не проверяется».

- [ ] **Step 6: Красный контроль запасного чтения.** В `get` удалить строку `if _migrated(...): return None`. `test_new_provider_file_wins_and_legacy_is_not_read_for_that_provider` по-прежнему зелёный (новое значение и так первое), поэтому добавить контрольный тест:

```python
def test_migrated_provider_never_falls_back(home):
    _w(paths.secrets_shared() / "exa.env", "EXA_OTHER=fake\n")
    _w(paths.legacy("secrets.dor_old"), "EXA_API_KEY=fake-old\n")
    assert secrets.get("EXA_API_KEY") is None
```
С удалённой строкой → FAIL `'fake-old' is not None`. Вернуть строку → PASS.

- [ ] **Step 7: Ratchet и commit.** `--check`, потолки. `git add h2t_ops/core/providers.py h2t_ops/core/secrets.py tests/core/test_secrets_v4.py tests/core/test_secrets.py tests/core/test_secrets_precedence.py tests/test_secrets_path_parity.py tests/connectors/research/test_client.py tests/test_setup_doctor_checks.py tests/connectors/conftest.py tests/governance/test_secret_names.py tests/governance/test_storage_ratchets.py`; `feat(core): one secrets reader over secrets/{shared,local} with a 4.0.x fallback (#548)`.

### Task 7: Песочница — аудит, фикстура, изоляция набора тестов

**Files:**
- Create: `tests/governance/audit.py`
- Create: `tests/governance/sandbox_cases.py`
- Create: `tests/governance/test_sandbox.py`
- Create: `tests/governance/test_suite_isolation.py`
- Modify: `conftest.py` (корень)

**Interfaces:**
- Produces:
  - `audit.Recorder(guarded: list[Path], secret_dirs: list[Path], legacy: list[Path], twins: dict[Path, Path])` с `active() -> ContextManager`, `violations: list[str]`, `legacy_writes: list[Path]` (любая запись под старыми корнями, через дверь или нет), `writers: set[str]` (модули `h2t_ops`, относительно `h2t_ops/`, которые стоят в стеке записи вне `store.py`/`secrets.py`; читает Task 24, R27), `popen: list[list[str]]` (дочерние процессы, которых аудит не видит; печатаются в тексте падения теста случая);
  - `test_sandbox.build_sandbox(tmp_path, monkeypatch) -> ContextManager[SimpleNamespace]` и фикстура `sandbox` поверх него → `SimpleNamespace(home, lake, inbox, vault, recorder)` (Task 24 строит песочницу на каждый случай сам);
  - `test_sandbox.compat_allowed(path: Path, home: Path, compat: tuple[str, ...]) -> bool` — запись старого места разрешена, если это сам файл из `compat`, его каталог (событие `os.mkdir` с `exist_ok`) или временный файл `store` рядом (`.<имя>.*`);
  - `sandbox_cases.CASES: list[Case]`, где `Case(id: str, run: Callable[[SimpleNamespace, MonkeyPatch], None], compat: tuple[str, ...] = (), setup: Callable[[SimpleNamespace, MonkeyPatch], None] | None = None)`. `compat` — пути старых файлов относительно `HOME`, которые случай вправе записать через `compat`; тест проверяет `compat_allowed` для каждой `legacy_writes`. `setup` готовит исходное состояние до включения `Recorder` (R30). Каждая задача фазы C дописывает сюда свои случаи.

- [ ] **Step 1: Аудит.**

```python
# tests/governance/audit.py
"""Who touched a file (#548 §7.3). Python-level only: C extensions that make their own
syscalls and child processes after Popen are invisible here — the directory permissions of
the sandbox are the guarantee there, and the verdict is «no bypass through Python found».

Also invisible: os.open(name, dir_fd=…) — the "open" audit event carries no dir_fd, so a
relative name is resolved against cwd. The fd-relative os.* events below are resolved."""
from __future__ import annotations

import contextlib
import os
import sys
import threading
from pathlib import Path

_DOORS = ("h2t_ops/core/store.py", "h2t_ops/core/secrets.py")
# One active recorder for the whole process: events raised in worker threads (the meetgeek
# webhook ThreadingHTTPServer, executors) must reach it. Only the re-entrancy guard is
# per-thread.
_ACTIVE: list = [None]
_GUARD = threading.local()
_WRITE_FLAGS = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_APPEND | os.O_TRUNC
_UNRESOLVED = "<fd-relative path not resolved>"


def _fd_path(fd: int) -> str | None:
    """The directory an open fd points at: F_GETPATH on macOS, /proc on Linux."""
    try:
        if sys.platform == "darwin":
            import fcntl
            return os.fsdecode(fcntl.fcntl(fd, fcntl.F_GETPATH, b"\0" * 1024).rstrip(b"\0"))
        if sys.platform.startswith("linux"):
            return os.readlink(f"/proc/self/fd/{fd}")
    except OSError:
        return None
    return None


def _join(path, dir_fd) -> str:
    p = os.fsdecode(path)
    if dir_fd in (None, -1) or os.path.isabs(p):
        return p
    base = _fd_path(dir_fd)
    return os.path.join(base, p) if base else _UNRESOLVED


def _stack_has_door() -> bool:
    f = sys._getframe(2)
    while f is not None:
        name = f.f_code.co_filename.replace("\\", "/")
        if name.endswith(_DOORS):
            return True
        f = f.f_back
    return False


def _writer_modules() -> set[str]:
    """Every h2t_ops module on the stack of this write, outside the doors: a connector that
    writes through a helper (core/lake.py) counts as a writer too (plan R27)."""
    out: set[str] = set()
    f = sys._getframe(2)
    while f is not None:
        name = f.f_code.co_filename.replace("\\", "/")
        if "/h2t_ops/" in name and not name.endswith(_DOORS):
            out.add(name.rsplit("/h2t_ops/", 1)[1])
        f = f.f_back
    return out


def _paths(event: str, args: tuple) -> list[tuple[str, bool]]:
    """(path, is_write) pairs an event touches."""
    if event == "open":
        path, mode, flags = args
        if not isinstance(path, (str, bytes, os.PathLike)):
            return []
        write = bool(mode and any(c in str(mode) for c in "wax+")) or bool(flags & _WRITE_FLAGS)
        return [(os.fsdecode(path), write)]
    if event == "os.rename":                       # (src, dst, src_dir_fd, dst_dir_fd)
        return [(_join(args[0], args[2]), True), (_join(args[1], args[3]), True)]
    if event == "os.link":                         # (src, dst, src_dir_fd, dst_dir_fd)
        return [(_join(args[0], args[2]), True), (_join(args[1], args[3]), True)]
    if event in ("os.remove", "os.rmdir"):         # (path, dir_fd)
        return [(_join(args[0], args[1]), True)] if isinstance(args[0], (str, bytes, os.PathLike)) else []
    if event in ("os.mkdir", "os.chmod"):          # (path, mode, dir_fd)
        return [(_join(args[0], args[2]), True)] if isinstance(args[0], (str, bytes, os.PathLike)) else []
    if event == "shutil.rmtree":                   # (path, dir_fd)
        return [(_join(args[0], args[1]), True)]
    if event in ("shutil.copyfile", "shutil.copytree", "shutil.move"):
        return [(os.fsdecode(args[0]), False), (os.fsdecode(args[1]), True)]
    if event == "sqlite3.connect":
        return [(os.fsdecode(args[0]), True)] if args and args[0] not in (":memory:", "") else []
    return []


class Recorder:
    def __init__(self, guarded: list[Path], secret_dirs: list[Path], legacy: list[Path],
                 twins: dict[Path, Path]):
        """twins: legacy secret file → its one new counterpart (§7.3: reading the old one
        while the new one exists is red, whoever reads — secrets.py included)."""
        self.guarded = [Path(os.path.realpath(p)) for p in guarded]
        self.secret_dirs = [Path(os.path.realpath(p)) for p in secret_dirs]
        self.legacy = [Path(os.path.realpath(p)) for p in legacy]
        self.twins = {Path(os.path.realpath(k)): Path(v) for k, v in twins.items()}
        self.violations: list[str] = []
        self.legacy_writes: list[Path] = []
        self.writers: set[str] = set()
        self.popen: list[list[str]] = []

    def _under(self, real: Path, roots: list[Path]) -> bool:
        return any(real == r or r in real.parents for r in roots)

    def check(self, event: str, args: tuple) -> None:
        if event == "subprocess.Popen":
            self.popen.append([os.fsdecode(a) for a in (args[1] or [])])
            return
        from h2t_ops.core import store
        for raw, write in _paths(event, args):
            if raw == _UNRESOLVED:
                self.violations.append(f"{event} {_UNRESOLVED}")
                continue
            real = Path(os.path.realpath(raw))
            if write:
                self.writers |= _writer_modules()
            if write and self._under(real, self.legacy):
                self.legacy_writes.append(real)
            twin = self.twins.get(real)
            if not write and twin is not None and twin.exists():
                self.violations.append(f"{event} read {real} while {twin} exists")
                continue
            secret = self._under(real, self.secret_dirs)
            if not (write or secret) or not self._under(real, self.guarded):
                continue
            if _stack_has_door() or store.delegated(real):
                continue
            self.violations.append(f"{event} {'write' if write else 'read'} {real}")

    @contextlib.contextmanager
    def active(self):
        _ACTIVE[0] = self
        try:
            yield self
        finally:
            _ACTIVE[0] = None


def _hook(event: str, args: tuple) -> None:
    rec = _ACTIVE[0]
    if rec is None or getattr(_GUARD, "inside", False):
        return
    _GUARD.inside = True
    try:
        rec.check(event, args)
    finally:
        _GUARD.inside = False


sys.addaudithook(_hook)  # cannot be removed; it is inert unless a Recorder is active
```

- [ ] **Step 2: Фикстура и случаи.**

```python
# tests/governance/sandbox_cases.py
"""Every command that writes to disk, run under a temporary HOME (#548 §7.3).

Phase-C tasks append their cases here. A case gets the sandbox and monkeypatch, fakes its
provider exactly as that connector's own tests do, and runs the command in-process.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class Case:
    id: str
    run: Callable
    compat: tuple[str, ...] = ()  # legacy files this case may write via store compat
    setup: Callable | None = None  # writes the starting state before the recorder is on (R30)


def _store_replace_state(sb, mp):
    from h2t_ops.core import paths, store
    store.replace(paths.state_dir() / "probe.json", "{}", place="state")


CASES: list[Case] = [Case("store.replace.state", _store_replace_state)]
```

```python
# tests/governance/test_sandbox.py
import contextlib
import os
import stat
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from h2t_ops.core import paths
from tests.governance import audit
from tests.governance.sandbox_cases import CASES


def compat_allowed(p: Path, home: Path, compat: tuple[str, ...]) -> bool:
    """A compat write touches the file, its directory (os.mkdir with exist_ok raises the
    event) and store's temp file beside it (.<name>.XXXX, store._tmp_beside)."""
    for rel in compat:
        target = Path(os.path.realpath(home / rel))
        if p in (target, target.parent):
            return True
        if p.parent == target.parent and p.name.startswith("." + target.name + "."):
            return True
    return False


@contextlib.contextmanager
def build_sandbox(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    for k in list(os.environ):
        if k.startswith("H2T_PATH_") or k in paths.OLD_ENV:
            monkeypatch.delenv(k, raising=False)
    lake, inbox, vault = (tmp_path / n for n in ("lake", "inbox", "vault"))
    for d in (lake, inbox, vault):
        d.mkdir()
    monkeypatch.setenv("H2T_PATH_VAULT", str(vault))
    cfg = home / ".h2t" / "config"
    cfg.mkdir(parents=True)
    (cfg / "paths.yaml").write_text(
        f"version: 1\nplaces:\n  lake: {lake}\n  inbox: {inbox}\n", encoding="utf-8")
    dirs = {paths.legacy_dir(n) for n in paths.LEGACY if n != "downloads"}
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
    closed = [d for d in dirs if d != home and paths.root() not in (d, *d.parents)
              and d != paths.legacy("google.store")]   # the one compat mirror (§9)
    if sys.platform != "win32":
        for d in closed:
            os.chmod(d, stat.S_IRUSR | stat.S_IXUSR)
    # tmp (§7.1: only through store.scratch) and harness (only h2t-setup) are places too.
    guarded = [paths.root(), lake, inbox, vault, paths.dir_of("tmp"), paths.dir_of("harness"),
               *paths.legacy_roots()]
    secret_dirs = [paths.root() / "secrets", *(paths.legacy(n) for n in
                   ("secrets.h2t", "secrets.dor", "secrets.dor_old", "notion.token",
                    "google.store", "google.gmail", "google.dor", "telegram"))]
    shared, local = paths.secrets_shared(), paths.secrets_local()
    twins = {paths.legacy("google.store") / "tokens.json": local / "google.token.json",
             paths.legacy("google.gmail") / "token.json": local / "google.token.json",
             paths.legacy("google.store") / "credentials.json": shared / "google.client.json",
             paths.legacy("google.gmail") / "credentials.json": shared / "google.client.json",
             paths.legacy("google.dor"): shared / "google.client.json",
             paths.legacy("notion.token"): shared / "notion.env",
             paths.legacy("telegram") / "auth_state.json": local / "telegram.auth-state.json",
             paths.legacy("telegram") / "session.session": local / "telegram.session"}
    try:
        yield SimpleNamespace(home=home, lake=lake, inbox=inbox, vault=vault,
                              recorder=audit.Recorder(guarded, secret_dirs, paths.legacy_roots(), twins))
    finally:
        if sys.platform != "win32":
            for d in closed:
                os.chmod(d, stat.S_IRWXU)


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    with build_sandbox(tmp_path, monkeypatch) as sb:
        yield sb


def run_case(case, sb, monkeypatch) -> None:
    if case.setup is not None:
        case.setup(sb, monkeypatch)            # starting state, recorder off (R30)
    with sb.recorder.active():
        case.run(sb, monkeypatch)


@pytest.mark.parametrize("case", CASES, ids=[c.id for c in CASES])
def test_command_touches_only_through_the_doors(case, sandbox, monkeypatch):
    run_case(case, sandbox, monkeypatch)
    rec = sandbox.recorder
    unseen = f"\nchild processes the audit cannot see: {rec.popen}" if rec.popen else ""
    assert rec.violations == [], "\n".join(rec.violations) + unseen
    stray = {p for p in rec.legacy_writes if not compat_allowed(p, sandbox.home, case.compat)}
    assert stray == set(), f"legacy writes outside compat: {sorted(map(str, stray))}{unseen}"


def test_worker_thread_events_reach_the_recorder(sandbox):
    import threading
    f = sandbox.lake / "t.md"
    with sandbox.recorder.active():
        t = threading.Thread(target=lambda: f.write_text("x"))
        t.start()
        t.join()
    assert any("t.md" in v for v in sandbox.recorder.violations)


@pytest.mark.skipif(sys.platform == "win32", reason="rmtree on Windows takes no dir_fd path")
def test_fd_relative_remove_is_attributed(sandbox):
    (sandbox.lake / "sub").mkdir()
    (sandbox.lake / "sub" / "a.md").write_text("x")
    import shutil
    with sandbox.recorder.active():
        shutil.rmtree(sandbox.lake / "sub")   # members go through os.remove(name, dir_fd=…)
    assert any("a.md" in v for v in sandbox.recorder.violations)


def test_legacy_read_while_the_new_twin_exists_is_caught_even_from_secrets(sandbox):
    from h2t_ops.core import secrets
    legacy = paths.legacy("google.store") / "tokens.json"
    legacy.write_text('{"refresh_token": "fake-old"}')
    with sandbox.recorder.active():
        secrets.read_json("google.token")      # no new file yet: the legacy read is fine
    assert sandbox.recorder.violations == []
    new = paths.secrets_local() / "google.token.json"
    new.parent.mkdir(parents=True)
    new.write_text('{"refresh_token": "fake-new"}')
    with sandbox.recorder.active():
        legacy.read_text()
    assert any("while" in v for v in sandbox.recorder.violations)


def test_direct_secret_read_is_caught(sandbox):
    target = paths.secrets_shared() / "exa.env"
    target.parent.mkdir(parents=True)
    target.write_text("EXA_API_KEY=fake")
    with sandbox.recorder.active():
        target.read_text()
    assert sandbox.recorder.violations and "read" in sandbox.recorder.violations[0]


@pytest.mark.parametrize("op", ["write", "rename", "remove"])
def test_direct_mutation_inside_lake_is_caught(sandbox, op):
    f = sandbox.lake / "a.md"
    f.write_text("x")
    with sandbox.recorder.active():
        if op == "write":
            f.write_text("y")
        elif op == "rename":
            os.rename(f, sandbox.lake / "b.md")
        else:
            os.remove(f)
    assert sandbox.recorder.violations


def test_sqlite_without_delegation_is_caught(sandbox):
    import sqlite3
    db = paths.state_dir() / "x.sqlite"
    db.parent.mkdir(parents=True)
    with sandbox.recorder.active():
        sqlite3.connect(db).close()
    assert any("sqlite3.connect" in v for v in sandbox.recorder.violations)


def test_compat_write_allowed_only_for_the_google_mirror(sandbox):
    from h2t_ops.core import store
    with sandbox.recorder.active():
        store.replace(paths.legacy("google.store") / "tokens.json", "{}", place="legacy", compat=True)
        with pytest.raises(store.WriteRefused):
            store.replace(paths.legacy("telegram") / "x.json", "{}", place="legacy", compat=True)
    assert sandbox.recorder.violations == []
    compat = (".config/google-calendar-mcp/tokens.json",)
    # the mirror's own events (dir, temp beside, target) pass; nothing else was written
    assert sandbox.recorder.legacy_writes
    assert all(compat_allowed(p, sandbox.home, compat) for p in sandbox.recorder.legacy_writes)
    assert not compat_allowed(paths.legacy("telegram") / "x.json", sandbox.home, compat)


def test_writers_are_recorded_by_module(sandbox, tmp_path):
    """Positive control for R27: a module whose file lies under an h2t_ops/ directory and
    writes through store is named; the test's own frames are not."""
    import importlib.util
    mod_file = tmp_path / "pkg" / "h2t_ops" / "zz_writer.py"
    mod_file.parent.mkdir(parents=True)
    mod_file.write_text("from h2t_ops.core import paths, store\n"
                        "def go():\n"
                        "    store.replace(paths.state_dir() / 'w.json', '{}', place='state')\n")
    spec = importlib.util.spec_from_file_location("zz_writer", mod_file)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    with sandbox.recorder.active():
        mod.go()
    assert sandbox.recorder.writers == {"zz_writer.py"}


def test_direct_write_into_tmp_is_caught(sandbox):
    """§7.1: tmp only through store.scratch()."""
    import tempfile

    from h2t_ops.core import store
    with sandbox.recorder.active():
        with store.scratch() as d:
            store.replace(d / "in.json", "{}", place="tmp")
    assert sandbox.recorder.violations == []
    with sandbox.recorder.active():
        (Path(tempfile.gettempdir()) / "h2t-direct-probe.txt").write_text("x")
    assert any("h2t-direct-probe" in v for v in sandbox.recorder.violations)
    (Path(tempfile.gettempdir()) / "h2t-direct-probe.txt").unlink()
```

На POSIX старые каталоги закрыты на запись, кроме `google.store`: это единственное место зеркала `compat` (§9). Каталоги внутри `~/.h2t` (`secrets.h2t` и прочие) фикстура оставляет открытыми, потому что там лежат новые места.

`guarded` включает `tmp` и `harness` (§7.1): весь `tmp_path` песочницы лежит в системном временном каталоге, поэтому любая прямая запись случая — нарушение. Исходное состояние случая (старая сессия, фиктивный токен) пишет `Case.setup` до `active()`, R30.

- [ ] **Step 3: Прогон и контроль.** `.venv/bin/pytest tests/governance -q` → PASS. Контроли, каждый с возвратом:
  - в `audit._stack_has_door` вернуть всегда `True` → все отрицательные тесты FAIL;
  - в `Recorder.active` писать в `threading.local()` вместо `_ACTIVE` → `test_worker_thread_events_reach_the_recorder` FAIL;
  - в `_join` всегда возвращать `os.fsdecode(path)` → `test_fd_relative_remove_is_attributed` FAIL (на macOS и Linux);
  - в `Recorder.check` убрать ветку `twins` → `test_legacy_read_while_the_new_twin_exists_is_caught_even_from_secrets` FAIL;
  - в `compat_allowed` убрать строку про временный файл рядом → `test_compat_write_allowed_only_for_the_google_mirror` FAIL на `all(...)` (в `legacy_writes` есть `.tokens.json.XXXX`);
  - в `Recorder.check` убрать `self.writers |= …` → `test_writers_are_recorded_by_module` FAIL;
  - из `guarded` убрать `paths.dir_of("tmp")` → новый тест `test_direct_write_into_tmp_is_caught` FAIL (тест: `tempfile.gettempdir()/<имя>` пишется `write_text` под `active()` → нарушение; через `store.scratch()` и `store.replace(place="tmp")` внутри него → нарушений нет).

- [ ] **Step 4: Изоляция всего набора — через `HOME`.** `H2T_PATH_ROOT` старые места не изолирует: они от домашнего каталога по замыслу (`test_legacy_places_are_home_relative_and_ignore_root`). Тест, который вызывает `secrets.get` без своего `HOME`, читал бы настоящие `~/.dor/secrets.env`, `~/.h2t/config/secrets/*.env` и `~/.config/google-calendar-mcp/tokens.json`; с evals это возвращает риск #321 — настоящие отправки в прод из модульных тестов. Поэтому в `conftest.py`, в `_isolate_home_writes`:
  - убрать `H2T_ACTIVITY_SPOOL` и `H2T_SESSION_ROOT` (пакет их больше не читает, R5);
  - `monkeypatch.setenv("HOME", str(root / "home"))` и `monkeypatch.setenv("USERPROFILE", str(root / "home"))` — тот же приём, что `tests/connectors/conftest.py` делает с 2026-10-14;
  - `monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(root / "gitconfig"))` с файлом `[user]\n name = test\n email = test@example.invalid\n`: тесты, которые коммитят во временных репо, без настоящего `~/.gitconfig` иначе падают на имени автора;
  - `monkeypatch.delenv(k)` для всех `paths.OLD_ENV` и `H2T_PATH_*` — их может держать окружение разработчика.

  В `_real_home_artifacts().watched` добавить реальные пути: `~/.h2t/records`, `~/.h2t/secrets`, `~/.h2t/state`, `~/.h2t/data`, `~/.h2t/layout.json`, `~/.config/google-calendar-mcp/tokens.json`. `pytest_sessionstart` выполняется до фикстур, поэтому `Path.home()` там ещё настоящий. Пути строить в самом `conftest.py`: он вне `h2t_ops/`, ratchet его не считает. `~/.h2t/logs` добавляет Task 18, когда логи хуков переедут.

Тест изоляции — `tests/governance/test_suite_isolation.py`: `conftest.py` при импорте (до любых фикстур) запоминает `REAL_HOME = Path.home()`, тест утверждает `Path.home() != conftest.REAL_HOME` и что `secrets.legacy_sources()` целиком лежит под текущим `Path.home()`. Красный контроль: убрать `setenv("HOME", …)` из `_isolate_home_writes` → FAIL. Вернуть. Настоящие файлы секретов в контроле не участвуют и не открываются.

Run: `.venv/bin/pytest tests/ -q` → PASS, без строки `ERROR: the suite wrote into the real home`. Тест, которому нужен настоящий домашний каталог (например, вызов `uv` с его кэшем), получает его явным `monkeypatch.setenv("HOME", …)` в себе; список таких тестов — в сообщении коммита.

- [ ] **Step 5: Commit** — `git add tests/governance/audit.py tests/governance/sandbox_cases.py tests/governance/test_sandbox.py tests/governance/test_suite_isolation.py conftest.py`; `test(governance): sandbox with an audit hook; the suite runs under its own HOME (#548)`.


## Фаза C — перевод вызывающих

Общий порядок каждой задачи фазы:

1. Написать тест поведения на новое место. Увидеть его красным на текущем коде.
2. Перевести вызовы на `paths`, `store` и `secrets`.
3. Добавить случаи в `tests/governance/sandbox_cases.py`.
4. Запустить `--check` и вписать потолки.
5. Прогнать затронутые каталоги тестов и `tests/governance`.
6. Сделать commit.

Шаги 4–6 одинаковы во всех задачах фазы и в каждой задаче названы одной строкой.

### Task 8: Google — токен машины в `local`, access-токен в памяти, зеркало

**Files:**
- Modify: `h2t_ops/core/google_auth.py` (`_oauth_store_dir` `:20-31`, `_load_dotenv` `:58-64`, `_candidate_paths` `:103-123` — удалить, `_load_credentials` `:126-172`, refresh `:211-224`, `bootstrap_google_token` `:233-259`)
- Modify: `h2t_ops/cli.py:61` (`google_auth._candidate_paths("gmail")` → `secrets.read_json("google.token")[1] is not None`; иначе `h2t-ops doctor` ломается на удалённой функции)
- Modify: `h2t_ops/connectors/meetgeek/recovery.py:36-38,266` (свой `DRIVE_CONFIG_DIR` → `google_auth.resolve_google_credentials("drive", …)`)
- Modify: `tests/core/test_google_auth.py` (патчи `Path.home` → `HOME`/`USERPROFILE`)
- Modify: `tests/connectors/google/test_commands.py` (`:85-91` подсказка называет `secrets.json_path("google.client")`, а не `credentials.json`; `:94-106` после `auth` токен лежит в `local/google.token.json` с `0600`, а `tokens.json` пишется зеркалом, только если существовал; фейковый поток получает словарь клиента из `from_client_config`, а не путь)
- Modify: `tests/connectors/meetgeek/test_script_cases.py:814-822` (`test_drive_service_raises_when_token_missing` патчит `recovery.DRIVE_TOKEN_FILE` с `raising=True`, а константа удаляется: патчить `recovery.google_auth.resolve_google_credentials` на `raise ConfigError("Google token not found", hint=…)` и ждать `ConfigError` либо `RecoveryError`, который его оборачивает; утверждение о тексте — `"google"` в сообщении)
- Проверить (правка, только если тест краснеет): `tests/connectors/calendar/test_commands.py:239` и `tests/connectors/drive/test_client.py:1047` кладут токен в старый `~/.config/google-calendar-mcp/tokens.json` под патчем `Path.home` — запасное чтение 4.0.x его находит; если тест утверждает перезапись файла при рефреше, перевести на R11 (рефреш ничего не пишет)
- Тест `test_durable_token_drops_short_lived_fields` в `tests/core/test_google_auth.py`: обёртка `normal` с `token`, `expiry_date`, `scope` строкой → только `_DURABLE`, `scopes` списком
- Modify: `tests/connectors/gmail/test_client.py:77-104` (`test_refresh_failure_raises_autherror` не кладёт файла токена, а новый поток сначала читает его через `secrets.read_json("google.token")`: записать фиктивный `local/google.token.json` под временным `HOME`/`USERPROFILE` вместо `Path.home`-патча, иначе вместо `AuthError` придёт `ConfigError`)
- Modify: `tests/governance/sandbox_cases.py`, `tests/governance/test_storage_ratchets.py`

**Interfaces:**
- Consumes: `secrets.read_json("google.client" | "google.token")`, `secrets.write_json`, `secrets.json_path`, `store.replace(..., compat=True)`.
- Produces: `google_auth.resolve_google_credentials(service_name, required_scopes)` (сигнатура прежняя), `google_auth.bootstrap_google_token(*, force, open_browser)` (прежняя), `google_auth.mirror_legacy(creds_json: dict) -> str` (`"written"|"absent"`), `google_auth.durable_token(data: dict) -> dict` (нормализация 3.x — обёртка `normal`, `scope` → `scopes` списком, как `_load_credentials` `:145-156`, — и только поля `_DURABLE`; его же зовут `_save_login` и миграция Task 22, R37).

Правила (§4, §9, R11, R19):

1. Чтение. Клиент — `secrets.read_json("google.client")`: `shared/google.client.json`, затем старые места 4.0.x. Токен — `secrets.read_json("google.token")`: `local/google.token.json` **этой машины**, затем её старые `tokens.json`/`token.json`. У каждой машины свой вход (проба §11.4), поэтому правила «чья копия новее» нет.
2. **Access-токен нигде не хранится.** Истёкший `Credentials` обновляется `creds.refresh(_request())` в памяти; после рефреша на диск не пишется ничего, если refresh-токен не сменился.
3. Файл `local/google.token.json` пишется при входе (`bootstrap_google_token`) и когда Google выдал **новый** refresh-токен (сравнение по `sha256`, не по значению). В нём только долгоживущие поля: `refresh_token`, `scopes`, `client_id`, `client_secret`, `token_uri`. Если токен пришёл из старого места, а `local` ещё нет (машина не мигрировала), новый refresh-токен всё равно пишется в `local`: иначе он потерялся бы, а `secrets.read_json` дальше читает `local` первым.
4. После каждой записи токена — зеркало `mirror_legacy(json.loads(creds.to_json()))` в `paths.legacy("google.store")/"tokens.json"` той же машины, в формате 3.x: `token` и `expiry` того момента плюс долгоживущие поля. Пишется, пока этот файл существует, через `store.replace(..., place="legacy", compat=True, mode=0o600)`; файла нет → `"absent"`. Старый файл не читается: писатель у обеих копий один — пакет этой машины.
5. `_load_dotenv` удаляется. Ключей Google в env-файлах нет, а `H2T_*` загружает `secrets.load_secrets`.
6. `gmail` больше не ищет `~/.config/gmail` сам. Это запасной путь `secrets.read_json`.
7. Запасной вариант B (R11): если живая проверка POS (документ выкатки, Step 3) покажет 401 на протухшем `expiry`, в ветку рефреша добавляется одна строка — `mirror_legacy(json.loads(creds.to_json()))` при каждом рефреше. Тест `test_refresh_writes_nothing` тогда меняется на «рефреш пишет только зеркало».

- [ ] **Step 1: Тесты (красные).**

```python
# tests/core/test_google_auth.py — добавить
import json
import os
import stat
import sys
from types import SimpleNamespace

import pytest

from h2t_ops.core import google_auth as mod
from h2t_ops.core import paths


def _home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    for k in list(os.environ):
        if k.startswith("H2T_PATH_"):
            monkeypatch.delenv(k)


def _fake(refresh_token="fake-r1"):
    state = {"refresh_token": refresh_token, "client_id": "fake-id", "client_secret": "fake-cs",
             "token_uri": "https://oauth2.googleapis.com/token",
             "scopes": ["https://www.googleapis.com/auth/calendar"]}
    return SimpleNamespace(valid=False, expired=True, refresh_token=refresh_token,
                           scopes=state["scopes"], refresh=lambda req: None,
                           to_json=lambda: json.dumps({"token": "fake-access",
                                                       "expiry": "2099-01-01T00:00:00Z", **state}))


def _files(root):
    return sorted(str(p.relative_to(root)) for p in root.rglob("*") if p.is_file())


def test_refresh_writes_nothing(tmp_path, monkeypatch):
    _home(tmp_path, monkeypatch)
    token = paths.secrets_local() / "google.token.json"
    token.parent.mkdir(parents=True)
    token.write_text('{"refresh_token": "fake-r1"}')
    before = (_files(tmp_path), token.stat().st_mtime_ns)
    monkeypatch.setattr(mod, "_load_credentials", lambda data, client: _fake())
    monkeypatch.setattr(mod, "_request", lambda: None)
    mod.resolve_google_credentials("calendar", ["https://www.googleapis.com/auth/calendar"])
    assert (_files(tmp_path), token.stat().st_mtime_ns) == before   # no cache, no rewrite


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permission bits")
def test_new_refresh_token_rewrites_local_and_mirrors(tmp_path, monkeypatch):
    _home(tmp_path, monkeypatch)
    token = paths.secrets_local() / "google.token.json"
    token.parent.mkdir(parents=True)
    token.write_text('{"refresh_token": "fake-r1"}')
    legacy = paths.legacy("google.store") / "tokens.json"
    legacy.parent.mkdir(parents=True)
    legacy.write_text('{"refresh_token": "fake-r1"}')
    monkeypatch.setattr(mod, "_load_credentials", lambda data, client: _fake("fake-r2"))
    monkeypatch.setattr(mod, "_request", lambda: None)
    mod.resolve_google_credentials("calendar", ["https://www.googleapis.com/auth/calendar"])
    main = json.loads(token.read_text())
    assert main["refresh_token"] == "fake-r2" and "token" not in main
    mirror = json.loads(legacy.read_text())
    assert mirror["refresh_token"] == "fake-r2" and mirror["token"] == "fake-access"   # 3.x shape
    assert stat.S_IMODE(token.stat().st_mode) == 0o600
    assert stat.S_IMODE(legacy.stat().st_mode) == 0o600
    assert not (paths.secrets_shared() / "google.token.json").exists()   # never shared (R19)


def test_new_refresh_token_on_an_unmigrated_machine_lands_in_local(tmp_path, monkeypatch):
    _home(tmp_path, monkeypatch)
    legacy = paths.legacy("google.store") / "tokens.json"
    legacy.parent.mkdir(parents=True)
    legacy.write_text('{"refresh_token": "fake-r1"}')
    monkeypatch.setattr(mod, "_load_credentials", lambda data, client: _fake("fake-r2"))
    monkeypatch.setattr(mod, "_request", lambda: None)
    mod.resolve_google_credentials("calendar", ["https://www.googleapis.com/auth/calendar"])
    assert json.loads((paths.secrets_local() / "google.token.json").read_text())["refresh_token"] == "fake-r2"


def test_mirror_without_the_legacy_file_creates_nothing(tmp_path, monkeypatch):
    _home(tmp_path, monkeypatch)
    assert mod.mirror_legacy({"refresh_token": "fake-r2"}) == "absent"
    assert not (paths.legacy("google.store") / "tokens.json").exists()
```

`_load_credentials` меняет сигнатуру. Было `(token_path, creds_path)`, стало `(token_data: dict, client_data: dict | None)`: файлы читает `secrets`, функция только нормализует. Старые тесты, которые подставляли пути, перевести на словари. `test_refresh_rewrites_token_as_owner_only` (#555, c5484f73 на `main`) описывает поведение 3.x — рефреш переписывает файл с `0600`. По R11 рефреш больше ничего не пишет: тест заменяется на `test_refresh_writes_nothing`, а утверждение про `0600` переходит в `test_new_refresh_token_rewrites_local_and_mirrors`.

- [ ] **Step 2: Реализация.** Ключевые места:

```python
_DURABLE = ("refresh_token", "scopes", "client_id", "client_secret", "token_uri")


def durable_token(data: dict) -> dict:
    """The long-lived part of a token in any 3.x shape; no access token, no expiry (§4, R37)."""
    d = dict(data.get("normal", data))
    if "scope" in d and "scopes" not in d:
        d["scopes"] = d.pop("scope")
    if isinstance(d.get("scopes"), str):
        d["scopes"] = d["scopes"].split()
    return {k: d[k] for k in _DURABLE if k in d}


def _refresh_sha(data: dict | None) -> str:
    return store.sha256(((data or {}).get("refresh_token") or "").encode())


def mirror_legacy(creds_json: dict) -> str:
    """One-way copy of this machine's token to the 3.x path POS reads (§9), in the 3.x shape.
    Removed in 4.1. Both copies belong to this machine, so there is nothing to compare."""
    legacy = paths.legacy("google.store") / "tokens.json"
    if not legacy.is_file():
        return "absent"
    store.replace(legacy, json.dumps(creds_json, ensure_ascii=False, indent=2),
                  place="legacy", compat=True, mode=0o600, keys=tuple(creds_json))
    return "written"


def _save_login(creds) -> None:
    new = json.loads(creds.to_json())
    secrets.write_json("google.token", durable_token(new))
    mirror_legacy(new)
```

Рефреш внутри `resolve_google_credentials`:

```python
if not creds.valid:
    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(_request())          # in memory; nothing is cached on disk (R11)
        except Exception as e:
            raise AuthError(f"Google OAuth token refresh failed: {e}", hint=...) from e
        if _refresh_sha(json.loads(creds.to_json())) != _refresh_sha(token_data):
            _save_login(creds)                 # Google rotated the refresh token
```

`bootstrap_google_token`: клиент берётся через `secrets.read_json("google.client")` и передаётся `_install_app_flow().from_client_config(data, GOOGLE_SCOPES)` — словарём, чтобы библиотека не открывала файл секрета сама. Подсказка `_CLIENT_HINT` называет `secrets.json_path("google.client")`. Токен пишется через `_save_login(creds)`.

- [ ] **Step 3: Случаи песочницы** — `google.refresh` (подставные `_load_credentials`/`_request` как в Step 1, вызов `resolve_google_credentials`; записей нет) и `google.refresh.new-token` с `compat=(".config/google-calendar-mcp/tokens.json",)`. Фиктивные `local/google.token.json` и старый `tokens.json` оба случая пишут в `setup` (R30). `compat_allowed` пропускает каталог зеркала и временный файл `store` рядом (Task 7), поэтому случай зелёный на правильном коде.

- [ ] **Step 4: Красные контроли.** В рефреше вызвать `_save_login(creds)` безусловно → `test_refresh_writes_nothing` FAIL. Вернуть. В `secrets._JSON` вернуть `google.token` в `secrets.shared` → `test_new_refresh_token_rewrites_local_and_mirrors` FAIL на последней строке. Вернуть.

- [ ] **Step 5: Ratchet, прогон, commit.** `.venv/bin/pytest tests/core/test_google_auth.py tests/connectors/calendar tests/connectors/gmail tests/connectors/drive tests/connectors/google tests/connectors/meetgeek tests/cli tests/governance -q`; `git add h2t_ops/core/google_auth.py h2t_ops/cli.py h2t_ops/connectors/meetgeek/recovery.py tests/core/test_google_auth.py tests/connectors/google/test_commands.py tests/connectors/meetgeek/test_script_cases.py tests/connectors/gmail/test_client.py tests/governance/sandbox_cases.py tests/governance/test_storage_ratchets.py` (+ `tests/connectors/calendar/test_commands.py`, `tests/connectors/drive/test_client.py`, если правились); `feat(google): per-machine token in secrets/local, access token only in memory, one-way mirror (#548)`.

### Task 9: Telegram — три части

**Files:**
- Modify: `h2t_ops/connectors/telegram/client.py` (`DEFAULT_CONFIG_DIR` `:17`, `__init__` `:225-237`, `_load_config` `:240-262`, `sqlite3.connect` `:140`, `_client` `:316`, `_save_auth_state` `:373-376`, чтение `:385,:455`, `dialogs_bootstrapped` `:817`, download-media `:714`)
- Modify: `h2t_ops/connectors/telegram/commands.py:122` (help «default: ~/Downloads» → «default: the inbox place»)
- Modify: `tests/connectors/telegram/test_client.py`, `test_auth_flows.py`, `test_commands.py`
- Modify: `tests/governance/sandbox_cases.py`, `tests/governance/test_storage_ratchets.py`

**Interfaces:**
- Consumes: `secrets.get("TELEGRAM_API_ID")`, `secrets.get("TELEGRAM_API_HASH")`, `secrets.telegram_legacy_config(config_dir=None)`, `secrets.read_json_at(path, *, root)` (ветка `config_dir=`, R42), `secrets.read_json/write_json("telegram.auth-state")`, `store.managed(place="secrets.local", library="telethon", dest=…)`, `store.connect_sqlite(..., dest=…)`, `store.replace(..., dest=True, keys=…)`, `store.sqlite_copy`, `paths.place_or_default("inbox")`, `paths.state_dir()`.
- Produces: `TelegramClientAdapter(config_dir: Path | None = None)` — параметр остаётся для тестов. Если он задан, все пути строятся от него, как в 3.x, и пишутся с `dest=True`; читаются тоже только через `core.secrets` (R42): `config.json` — `secrets.telegram_legacy_config(config_dir)` (`client.py:253`), auth-state — `secrets.read_json_at(<config_dir>/auth_state.json, root=config_dir)` (`:385`, `:455`), запись auth-state — `store.replace(..., place="secrets.local", dest=True, keys=tuple(state))`. Прямых `read_text`/`read_json_config` в коннекторе не остаётся ни в одной ветке. Если нет, раскладка такая:

| Что | Где | Операция |
|---|---|---|
| `api_id`, `api_hash` | `secrets.get("TELEGRAM_API_ID"/"TELEGRAM_API_HASH")`; запасной путь 4.0.x — `config.json` старого каталога через `secrets.telegram_legacy_config()` (Task 6): тот же `jsonfile.read_json_config`, что в 3.x. `tests/connectors/test_config_bom.py:30-35` (`"line 1"` в ошибке) остаётся зелёным без правки, но через ветку `config_dir=` (она читает `config.json` как в 3.x), а не через `telegram_legacy_config`; поведение без `config_dir` с BOM держит отдельный тест этой задачи `test_legacy_config_with_bom_reports_line` | — |
| сессия | `secrets_local()/"telegram.session"`; Telethon получает базу без `.session` | `store.managed(..., library="telethon")` вокруг каждого `_client()`; `sqlite3.connect` в `_input_peer_from_sqlite` (`:140`) → `store.connect_sqlite(..., place="secrets.local", library="telethon")` (R18); при `config_dir=` — `store.managed(..., dest=True)` и `store.connect_sqlite(..., dest=True)` (база по пути пользователя) |
| состояние входа | `secrets.write_json("telegram.auth-state", …)` | `replace`, 0600 |
| `dialogs_bootstrapped` | `state_dir()/"telegram"/"dialogs_bootstrapped"` | `replace(place="state")` |
| вложения | `--out` или `place_or_default("inbox")`; при умолчании напечатать `saved to <путь> (inbox not set: h2t-ops paths set inbox <path>)` | по R28: `inbox` задан → `replace(place="inbox")`; не задан (`defaulted=True`, путь `data/inbox`) → `replace(place="data")`; `--out` → `dest=True` |

Запасное чтение сессии в 4.0.x идёт из `paths.legacy("telegram")/"session.session"`. Пишет Telethon в файл, который открыл. Поэтому до миграции адаптер передаёт ему старый путь в `store.managed(..., place="legacy")`, а это `_check` отвергает. Решение: до миграции Telethon работает с **копией**. Если нового файла нет, а старый есть, адаптер копирует старый в `secrets_local()/"telegram.session"` через `store.sqlite_copy(old, new, place="secrets.local")` (0600) и печатает одну строку `telegram: session copied to <новый путь>; the old one is left as is`. Копия идёт через `sqlite3` `backup`, а не побайтно: если старую сессию держит открытой процесс 3.x, побайтная копия может оказаться рваной базой, а `backup` читает согласованный снимок. Две живые копии одного ключа на одной машине не используются одновременно: старый путь пакет больше не открывает. Так проверка «пишется только новое место» соблюдается и без миграции.

- [ ] **Step 1: Тесты (красные).** Тест `test_session_lives_in_secrets_local_with_0600`: адаптер без `config_dir`, подставной `client_cls` пишет байты в переданный путь + `.session`. Проверить, что файл лежит в `secrets_local()`, права `0600` (`skipif win32`). Тест `test_legacy_session_is_copied_once`: в старом каталоге лежит `session.session`. Старая сессия — настоящая база SQLite с одной таблицей и фиктивной строкой. Первый вызов копирует, второй не копирует (сравнить `st_mtime_ns` копии), старый файл побайтно цел, строка в копии читается. Тест `test_download_media_defaults_to_inbox`: с `inbox` в `paths.yaml` файл там; без `paths.yaml` — в `~/.h2t/data/inbox`, без `WriteRefused` (R28). Тест `test_api_keys_from_secrets_env`: `telegram.env` с `TELEGRAM_API_ID=1`, `TELEGRAM_API_HASH=fake`. Тест `test_legacy_config_with_bom_reports_line`: адаптер без `config_dir`, в `paths.legacy("telegram")/config.json` BOM и испорченный JSON → `ConfigError` с `line 1`.

- [ ] **Step 2: Реализация** по таблице. `int(api_id)`: в env-файле значение строковое, а Telethon ждёт `int`. Ошибка разбора → `ConfigError(f"TELEGRAM_API_ID in {secrets.provider_file('telegram')} is not a number")`.

- [ ] **Step 3: Случаи песочницы** — `telegram.auth-request-code` (подставной клиент, `auth request-code --phone +100`; подкоманды `auth` — `status|request-code|complete|qr|resend`, `connectors/telegram/commands.py:29-60`, `auth start` нет), `telegram.download-media.inbox`, `telegram.session.copy-from-legacy`, `telegram.messages` (подставная сессия SQLite, доходит до `_input_peer_from_sqlite`).

- [ ] **Step 4: Красный контроль.** В `_input_peer_from_sqlite` заменить `store.connect_sqlite(...)` обратно на прямой `sqlite3.connect`. Случай песочницы `telegram.messages` → FAIL с `sqlite3.connect`, ratchet `sqlite` → +1. Вернуть.

- [ ] **Step 5: Ratchet, прогон** (`tests/connectors/telegram tests/connectors/test_config_bom.py tests/governance`), **commit** — `git add h2t_ops/connectors/telegram/client.py h2t_ops/connectors/telegram/commands.py tests/connectors/telegram/test_client.py tests/connectors/telegram/test_auth_flows.py tests/connectors/telegram/test_commands.py tests/governance/sandbox_cases.py tests/governance/test_storage_ratchets.py`; `feat(telegram): keys in telegram.env, session in secrets/local, marker in state (#548)`.

### Task 10: Ключи остальных провайдеров через `secrets`

**Files:**
- Modify: `h2t_ops/connectors/research/client.py:67-110` (свой `_read_env_file`, `resolve_secret` → `secrets.get`), `research/fetch.py:634` (`JINA_API_KEY` из окружения → `secrets.get`), `research/provider_routing.py` (строка с `H2T_SECRETS_FILE` → подсказка через `secrets.provider_file`)
- Modify: `h2t_ops/connectors/dropbox/client.py:31,47-57,99-100` (`PROVIDER_ENV_FILE`, `_load_provider_env` → удалить; `secrets.get`)
- Modify: `h2t_ops/connectors/meetgeek/client.py:43`, `meetgeek/pipeline.py:366-372`, `granola/client.py:55`, `notion` (ничего, если уже через `resolve_notion_token`)
- Modify: `h2t_ops/core/secrets.py` (новая функция `evals_env`, Produces ниже)
- Modify: `h2t_ops/lifecycle/eval/session.py:28-55` (`_DEFAULT_SECRETS` и `_load_secrets` удалить, R33; `:118` `self._env = _load_secrets(secrets_path)` → `secrets.evals_env(env_file=secrets_path)`; запасной порядок для evals — сначала `paths.legacy("secrets.dor_old")`, как в 3.x), `:299-303` (путь спула из файла секретов `H2T_EVALS_SPOOL` больше не берётся: `paths.evals_spool()`, Q8), `lifecycle/eval/status.py:44` (`sess._load_secrets()` → `secrets.evals_env()`)
- Modify: `h2t_ops/connectors/evals/commands.py:16-18` (`H2T_EVALS_ROOT` → `paths.records("evals")`, переменная не читается). Второе её чтение в `h2t_ops/` — `connectors/research/exa.py:1147`, его переводит Task 12 (grep на 2ddd6db6: ровно эти два)
- Create: `tests/governance/test_one_secret_reader.py`
- Modify: `tests/lifecycle/eval/test_status.py:33` (патчит `_DEFAULT_SECRETS` с `raising=True`: перевести на `shared/h2t-evals.env` под временным `HOME`)
- Modify: `tests/connectors/evals/test_report_cli.py:19,30,39` (`setenv("H2T_EVALS_ROOT", …)` больше ничего не значит: класть записи в `paths.records("evals")` под временным `HOME` из корневого `conftest.py`)
- Modify: `h2t_ops/setup/legacy.py` — вся своя лестница секретов 3.x переходит на `core.secrets`, иначе `h2t-ops setup doctor`/`connectors-check` отвечает MISSING на ключи, которые есть только в `secrets/shared` (каждый новый пользователь), и не видит `google.token.json`:
  - `_candidate_secret_files` `:222-246` → удалить, вызовы → `secrets.candidate_secret_files()`;
  - `_secret_present` `:249-272` → `secrets.get(key) is not None`;
  - `_resolve_secret_value` `:677-697` → `secrets.get(key)`;
  - `_google_oauth_status` `:438` → `secrets.read_json("google.client")`/`("google.token")`;
  - `secrets skeleton` (`secrets_skeleton` `:630-672`, вызов `:837-839`) — новый контракт R40:
    - сигнатура `secrets_skeleton(registry: dict[str, dict[str, str]], *, secrets_dir: Path | None = None, home: Path | None = None) -> dict`; вызов `:839` → `secrets_skeleton(registry)`, строка `:837` с `~/.dor/secrets/secrets.env` удаляется;
    - ключ реестра «недостаёт», если `secrets.get(key) is None` (окружение, новые файлы, лестница 4.0.x — как `#524` требовал от `_resolve_secret_value`); такие ключи группируются по `providers.provider_of_key(key)`, без провайдера — `other`;
    - для каждой группы файл `secrets_dir / f"{провайдер}.env"` (по умолчанию `secrets_dir = paths.secrets_shared()`): текст читается `secrets.read_secret_bytes(path)`, а при заданном `secrets_dir` — `secrets.read_secret_bytes(path, root=secrets_dir)`: явно названный каталог — единственный разрешённый корень вне `secrets/` (R42); нет файла — пусто. В конец дописываются блоки `# описание`, `# Get at: url`, `KEY=` только для недостающих ключей, существующие строки и комментарии не меняются; запись `store.replace(path, text, place="secrets.shared", keys=<добавленные имена>)`, при заданном `secrets_dir` — ещё `dest=True` (каталог внутри места пакета `dest` отклоняет). Файл без новых строк не переписывается;
    - ответ `{"kind": KIND_SECRETS_SKELETON, "path": str(secrets_dir), "files": {"<провайдер>.env": {"path": …, "added": [ключи]}}, "added": [все добавленные], "skipped": [разрешённые]}` — `added`/`skipped`/`kind` прежние, `path` теперь каталог;
    - тесты `tests/test_setup_secrets.py:45-110` переводятся на `secrets_dir=tmp_path/…`; новый `test_skeleton_writes_one_file_per_provider`: реестр с `EXA_API_KEY`, `NOTION_API_TOKEN`, `ZZZ_KEY` → три файла `exa.env`, `notion.env`, `other.env`, повторный вызов ничего не добавляет; ключ, который уже есть в старом `~/.dor/secrets.env`, идёт в `skipped`. Красный контроль: писать всё в один файл → тест FAIL;
  - запись секретов `:639-668` → `secrets.write_env`.
- Modify: `tests/test_secrets_path_parity.py` (`:48`, `:115`) — держит шов `setup/legacy.py` ↔ `core.secrets`: после правки утверждает, что `setup` и коннекторы видят одно и то же на `shared/<провайдер>.env` и на старой лестнице
- Modify: `conftest.py` — удалить `_neutralize_eval_secrets`: константы `_DEFAULT_SECRETS` больше нет, а настоящий `~/.dor/secrets.env` тестам недоступен, потому что Task 7 изолировал `HOME` (риск #321 закрыт там)
- Modify: подсказки коннекторов, где названы файлы (`meetgeek` hint про `~/.h2t/config/secrets/meetgeek.md`, `research` hint со списком файлов): называть `secrets.provider_file(<провайдер>)`
- Modify: тесты этих коннекторов, где патчатся удалённые константы

**Interfaces:**
- Consumes: `secrets.get`, `secrets.provider_file`, `secrets.write_env`, `providers.CONNECTOR_PROVIDERS`.
- Produces: `secrets.evals_env(env_file: Path | None = None) -> dict[str, str]` — все ключи с префиксом `H2T_EVALS_`, кроме имён из `paths.OLD_ENV` (путевые `H2T_EVALS_SPOOL`/`H2T_EVALS_ROOT` пакет не читает, Q8; их имена в `secrets.py` не пишутся, R22). `env_file` задан — читается только он и окружение, как `secrets_path` в 3.x. Контракт 3.x сохранён: по префиксу, без зашитого списка ключей (`eval/session.py:34-37`). Порядок, по ключу: окружение → `shared/h2t-evals.env` → `~/.dor/secrets.env` → остальная лестница (§8, строка `H2T_EVALS_*`); для уже мигрированного `h2t-evals` старые места не читаются.

- [ ] **Step 1: Тест паритета (красный).** `tests/governance/test_one_secret_reader.py` проходит по `providers.CONNECTOR_PROVIDERS` и для каждого провайдера кладёт фиктивный ключ только в `shared/<провайдер>.env`. Затем вызывает функцию, которой коннектор берёт ключ: `research.client.resolve_secret("EXA_API_KEY")`, `research.fetch._jina_key()` (выделить из `:634`), `dropbox.client._token_config()` (функции сейчас нет: создать её, вынеся чтение `DROPBOX_*` из `__init__` `:98-112`), `meetgeek.client._api_key()`, `granola.client._api_key()`, `secrets.resolve_notion_token()`, `secrets.evals_env()["H2T_EVALS_TOKEN"]` и `eval.status.get_status()["token_present"] is True` (оба потребителя evals, R33), `setup.legacy._secret_present("EXA_API_KEY", home)`, `telegram` (Task 9). Утверждение: каждая видит значение. На текущем коде FAIL у research (чтение файлов мимо `secrets`), dropbox (свой файл), jina (только окружение) и evals (`evals_env` нет — `AttributeError`; `get_status` читает только `~/.dor`). (`token_present` — ключ ответа `status.py:58`.)

- [ ] **Step 2: Реализация.** Функции-обёртки `_api_key()` выделить там, где ключ сегодня читается строкой в `__init__`. Это одна строка `return secrets.get("MEETGEEK_API_KEY")`. Сообщения об отсутствии ключа сохранить, путь в них взять из `secrets.provider_file(...)`.

- [ ] **Step 3: Случаи песочницы** — `research.resolve`, `dropbox.init`, `evals.load` (каждый только читает ключ).

- [ ] **Step 4: Ratchet, прогон** (`tests/connectors tests/lifecycle/eval tests/test_setup_secrets.py tests/test_setup_doctor_checks.py tests/test_secrets_path_parity.py tests/governance`), **commit** — `git add` явными путями: все `h2t_ops/…` из Files этой задачи, `h2t_ops/core/secrets.py`, `conftest.py`, `tests/governance/test_one_secret_reader.py`, `tests/lifecycle/eval/test_status.py`, `tests/connectors/evals/test_report_cli.py`, `tests/test_secrets_path_parity.py`, `tests/connectors/dropbox/test_client.py` (патчит `PROVIDER_ENV_FILE` `:71,84`), `tests/connectors/research/test_client.py`, `tests/test_setup_secrets.py`, `tests/test_setup_doctor_checks.py` (если правились — сверить `git status --short`, и любой ещё изменённый путь назвать явно), `tests/governance/sandbox_cases.py`, `tests/governance/test_storage_ratchets.py`; `refactor(secrets): every connector and setup reads keys through core.secrets (#548)`. После этой задачи `secret_readers` в ratchet = 0.

### Task 11: Lake — Granola и MeetGeek

**Files:**
- Create: `h2t_ops/core/lake.py`
- Modify: `h2t_ops/connectors/granola/sync.py` (`CURSOR_PATH_DEFAULT` `:23`, `lake = Path(to)…` `:88-89`, `manifest_path` `:100`, `_write_pair` `:61-65`, дозапись `:144-147`, курсор `:159-160`)
- Modify: `h2t_ops/connectors/granola/commands.py` (`--to` становится необязательным; по умолчанию `lake/granola`)
- Modify: `h2t_ops/connectors/meetgeek/recovery.py:97-105` (`lake_root`), `meetgeek/pipeline.py:26-28` (курсор), `meetgeek/commands.py:294,302` (`--out` вебхуков), записи `recovery.py`, `pipeline.py` (18 строк по сканеру на 2ddd6db6)
- Modify: `h2t_ops/connectors/meetgeek/client.py:261,266` (загрузка: `dest.parent.mkdir` + `dest.open("wb")` с `iter_content` → `store.writer(dest, place=…)` по R28/R29)
- Create: `tests/core/test_lake_manifest.py`
- Modify: `tests/connectors/test_script_verbs_in_cli.py:432-435` (фикстура `meetgeek_env` ставит `H2T_LAKE_ROOT`, который больше не читается: писать `paths.yaml` с `lake: <tmp_path>/lake` под временным `HOME` — `meetgeek/recovery.py:104` перестаёт читать переменную в этой задаче)
- Modify: `tests/connectors/granola/*`, `tests/connectors/meetgeek/*`
- Modify: `tests/governance/sandbox_cases.py`, `tests/governance/test_storage_ratchets.py`

**Interfaces:**
- Consumes: `paths.place_or_default("lake")`, `paths.state_dir()`, `store.create/replace/append`, `store.writer`.
- Produces:

```python
# h2t_ops/core/lake.py
class ConnectorDir:
    def __init__(self, provider: str, root: Path | None = None): ...
    root: Path                           # <lake>/<provider>, or the explicit root
    manifest: Path                       # <root>/manifest.jsonl
    place: str                           # "lake" (set in paths.yaml) | "data" (default data/lake) (R28)
    dest: bool                           # True for an explicit root that is neither of those
    def owned(self) -> dict[str, str]    # rel path → sha256 from the last committed row per path
    def committed_rows(self) -> list[dict]   # every committed row, with the connector's own fields
    def publish(self, files: dict[str, bytes], *, op_id: str, meta: dict | None = None) -> list[str]
                                         # protocol §7.1; meta goes into the committed row as is
    def recover(self) -> list[str]       # pending rows without committed: own only hash-matched files
def cursor_path(provider: str) -> Path   # state/cursors/<provider>.json
def write_cursor(provider: str, data: dict) -> Path
def manifest_line(row: dict) -> str     # json.dumps(row, sort_keys=True, ensure_ascii=False,
                                         #            separators=(",", ":")) — R39
```

Происхождение корня (R28): `root=None` и `lake` задан в `paths.yaml` → `place="lake"`, `dest=False`; `root=None` и `lake` не задан (`place_or_default` вернул `defaulted=True`, корень `data/lake/<провайдер>`) → `place="data"`; `root` задан явно — если его `realpath` равен одному из этих двух корней, берётся их `place`, иначе `dest=True`. Каждая запись ниже идёт с `place=self.place, dest=self.dest`. До миграции у автора `--to ~/.dor/lake/granola` без `lake` в `paths.yaml` — старое место 3.x, запись отклоняется с подсказкой `h2t-ops paths set lake ~/.dor/lake` (GC: старые места не пишутся); после миграции `paths.yaml` её содержит (R2).

Протокол `publish` (§7.1):

1. Посчитать хэши.
2. `store.append(manifest, manifest_line({"op": op_id, "state": "pending", "files": {rel: {"sha256": h, "owned_before": rel in owned}}}), place=…)` — `store.append` принимает строку, сериализация одна и детерминированная (R39).
3. Для каждого файла: если он уже свой, `store.replace(...)`. Если новый, `store.create(...)` (место — по происхождению корня выше). `AlreadyExists` на новом пути: файл чужой. Ничего не писать, запомнить отказ.
4. `store.append(manifest, manifest_line({"op": op_id, "state": "committed", "files": {rel: sha256 итогового файла}, "refused": [...], **meta}), place=…)`.
5. Вернуть список отказов. Курсор сдвигает вызывающий, только после возврата.

**Манифест Granola — ещё и её состояние инкрементальной синхронизации.** `_synced_versions` (`granola/sync.py:35-58`) ключует по `note_id@updated_at` и полю `include`. Поэтому Granola передаёт в `publish` `meta={"note_id", "title", "created_at", "updated_at", "include", "synced_at"}` — ровно поля строки 3.x (`:131-138`), и `_synced_versions` читает `ConnectorDir.committed_rows()`. Без этого после первой синхронизации 4.0 ни одна заметка не считалась бы синхронизированной, и каждый прогон заново скачивал бы и заменял всё.

**Строки 3.x** (без поля `state`) считаются `committed`. Поля `path` в них нет, поэтому `owned()` выводит пути из `note_id` и `include`: для каждой части `p` из `include` (нет `include` — обе, `VALID_INCLUDE`) свои файлы — `<p>/<note_id>.md` и `<p>/<note_id>.json`, где `p` — `summaries` или `transcripts` (`_write_pair(lake / "summaries" | "transcripts", …)`, `:119-124`). Хэша у таких строк нет: файл считается своим без сверки хэша. Это записано в docstring. Манифест 3.x лежит в `<--to>/manifest.jsonl`; у автора `--to` — `~/.dor/lake/granola`, совпадает с корнем `ConnectorDir("granola")`, если `lake: ~/.dor/lake` (R2). Если `--to` был другим, миграция манифест не переносит, и первая синхронизация 4.0 видит свои старые файлы как чужие (`publish` их не трогает, `doctor` показывает) — сказать об этом в CHANGELOG.

- [ ] **Step 1: Тесты протокола (красные).**

```python
# tests/core/test_lake_manifest.py
import json
import os

import pytest

from h2t_ops.core import lake, paths, store


@pytest.fixture
def lk(tmp_path, monkeypatch):
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    for k in list(os.environ):
        if k.startswith("H2T_PATH_") or k in paths.OLD_ENV:
            monkeypatch.delenv(k, raising=False)
    (home / ".h2t" / "config").mkdir(parents=True)
    (home / ".h2t" / "config" / "paths.yaml").write_text(
        f"version: 1\nplaces:\n  lake: {tmp_path / 'lake'}\n", encoding="utf-8")
    return lake.ConnectorDir("granola")


def _rows(d):
    return [json.loads(x) for x in d.manifest.read_text().splitlines()]


def test_publish_new_then_replace_own(lk):
    assert lk.publish({"n1.md": b"v1"}, op_id="a") == []
    assert lk.publish({"n1.md": b"v2"}, op_id="b") == []
    assert (lk.root / "n1.md").read_bytes() == b"v2"
    assert [r["state"] for r in _rows(lk)] == ["pending", "committed", "pending", "committed"]


def test_foreign_file_on_a_new_path_is_refused_and_untouched(lk):
    (lk.root).mkdir(parents=True)
    (lk.root / "n1.md").write_bytes(b"hand-made")
    assert lk.publish({"n1.md": b"v1"}, op_id="a") == ["n1.md"]
    assert (lk.root / "n1.md").read_bytes() == b"hand-made"


@pytest.mark.parametrize("stop_after", ["pending", "files"])
def test_interrupted_publish_recovers_only_hash_matched(lk, monkeypatch, stop_after):
    real_create = store.create
    calls = []

    def boom(*a, **kw):
        calls.append(1)
        if stop_after == "pending":
            raise KeyboardInterrupt
        real_create(*a, **kw)
        raise KeyboardInterrupt

    monkeypatch.setattr(store, "create", boom)
    with pytest.raises(KeyboardInterrupt):
        lk.publish({"n1.md": b"v1"}, op_id="a")
    monkeypatch.setattr(store, "create", real_create)
    assert lk.recover() == (["n1.md"] if stop_after == "files" else [])
    assert ("n1.md" in lk.owned()) == (stop_after == "files")


def test_pending_does_not_own_a_file_with_another_hash(lk, monkeypatch):
    monkeypatch.setattr(store, "create", lambda *a, **kw: (_ for _ in ()).throw(KeyboardInterrupt))
    with pytest.raises(KeyboardInterrupt):
        lk.publish({"n1.md": b"v1"}, op_id="a")
    (lk.root / "n1.md").write_bytes(b"someone else")   # appears during the outage
    assert lk.recover() == []
    assert "n1.md" not in lk.owned()


def test_legacy_granola_rows_count_as_committed(lk):
    lk.root.mkdir(parents=True)
    row = {"note_id": "n1", "title": "t", "updated_at": "2026-10-01T00:00:00Z",
           "include": ["summaries"], "synced_at": "2026-10-01T00:00:01Z"}   # 3.x shape, sync.py:131-138
    lk.manifest.write_text(json.dumps(row) + "\n")
    assert set(lk.owned()) == {"summaries/n1.md", "summaries/n1.json"}


def test_committed_rows_carry_granola_version_fields(lk):
    meta = {"note_id": "n1", "updated_at": "2026-10-01T00:00:00Z", "include": ["transcripts"]}
    lk.publish({"transcripts/n1.md": b"t", "transcripts/n1.json": b"{}"}, op_id="a", meta=meta)
    from h2t_ops.connectors.granola import sync
    assert "transcripts" in sync._synced_versions(lk.manifest)["n1@2026-10-01T00:00:00Z"]


def test_manifest_lines_are_deterministic_json(lk):
    """R39: one serialization, sorted keys, no spaces, non-ASCII kept as is."""
    lk.publish({"n1.md": b"v1"}, op_id="a", meta={"title": "Заметка", "b": 1, "a": 2})
    raw = lk.manifest.read_text(encoding="utf-8").splitlines()
    assert raw[1] == lake.manifest_line(json.loads(raw[1]))
    assert "Заметка" in raw[1] and ", " not in raw[1] and raw[1].index('"a"') < raw[1].index('"b"')


def test_summary_and_transcript_of_one_note_do_not_collide(lk):
    lk.publish({"summaries/n1.md": b"s", "transcripts/n1.md": b"t"}, op_id="a")
    assert (lk.root / "summaries" / "n1.md").read_bytes() == b"s"
    assert (lk.root / "transcripts" / "n1.md").read_bytes() == b"t"


def test_place_follows_the_origin_of_the_root(lk, tmp_path):
    """R28: configured lake -> "lake"; no paths.yaml -> data/lake as "data"; elsewhere -> dest."""
    assert (lk.place, lk.dest) == ("lake", False)
    (paths.paths_yaml()).unlink()
    d = lake.ConnectorDir("granola")
    assert d.root == paths.data_dir() / "lake" / "granola" and (d.place, d.dest) == ("data", False)
    assert d.publish({"n1.md": b"v1"}, op_id="a") == []          # no WriteRefused
    out = lake.ConnectorDir("granola", root=tmp_path / "mine")
    assert out.dest is True
    assert out.publish({"n1.md": b"v1"}, op_id="a") == []
```

Имена полей строки 3.x взяты из `granola/sync.py:131-138` (проверено 2026-10-18): `note_id`, `title`, `created_at`, `updated_at`, `include`, `synced_at`.

- [ ] **Step 2: Реализация** `core/lake.py` по протоколу. Затем Granola: `_write_pair(folder, …)` → `ConnectorDir.publish({f"{part}/{note_id}.md": …, f"{part}/{note_id}.json": …}, op_id=…, meta=<поля строки 3.x>)`, где `part` — `summaries` или `transcripts`, как сегодня решает `missing`; `_synced_versions` читает `committed_rows()`; курсор → `lake.write_cursor("granola", …)` после `publish`. Затем MeetGeek: `lake_root()` → `paths.place_or_default("lake")[0] / "meetgeek"`; `uploads_staging_root` и `staging_dir` остаются под ним; курсор → `lake.cursor_path("meetgeek")`; `--out` вебхуков по умолчанию → `lake/meetgeek/webhooks`. Записи загрузок MeetGeek (журнал загрузок по машинам, `recovery.py`) — через `ConnectorDir("meetgeek").publish` для файлов и `store.append(…, lake.manifest_line(row), …)` для журнала (R39).

Курсоры 3.x лежат в `~/.dor/lake/_cursors`. Если `state/cursors/<провайдер>.json` нет, а старый есть, коннектор читает старый (запасное чтение 4.0.x), а пишет новый.

- [ ] **Step 3: Случаи песочницы** — `granola.sync` (подставной клиент из `tests/connectors/granola`), `granola.sync.foreign-file` (чужой файл кладёт `setup`), `granola.sync.default-lake` (без `lake` в `paths.yaml`: запись в `data/lake`), `meetgeek.download` (через `store.writer`), `meetgeek.webhooks.write`.

- [ ] **Step 4: Красный контроль.** В `publish` поменять порядок шагов 3 и 2 (сначала файлы, потом `pending`). `test_interrupted_publish_recovers_only_hash_matched[files]` → FAIL. Вернуть. Второй: в `ConnectorDir.__init__` всегда ставить `place="lake"` → `test_place_follows_the_origin_of_the_root` FAIL с `WriteRefused … is in data, not lake`. Вернуть. Третий: в `manifest_line` убрать `sort_keys=True` → `test_manifest_lines_are_deterministic_json` FAIL. Вернуть.

- [ ] **Step 5: Ratchet, прогон** (`tests/core/test_lake_manifest.py tests/connectors/granola tests/connectors/meetgeek tests/governance`), **commit** — `git add h2t_ops/core/lake.py h2t_ops/connectors/granola/sync.py h2t_ops/connectors/granola/commands.py h2t_ops/connectors/meetgeek/recovery.py h2t_ops/connectors/meetgeek/pipeline.py h2t_ops/connectors/meetgeek/commands.py h2t_ops/connectors/meetgeek/client.py tests/core/test_lake_manifest.py tests/connectors/test_script_verbs_in_cli.py tests/governance/sandbox_cases.py tests/governance/test_storage_ratchets.py` и каждый правленый файл `tests/connectors/granola/…`, `tests/connectors/meetgeek/…` по имени; `feat(lake): connector manifest protocol, lake place default, cursors in state (#548)`.

### Task 12: Вложения и выводы — Drive, Gmail, Notion, Dropbox, research, evals, creative

**Files:**
- Modify: `h2t_ops/connectors/drive/client.py:1357,1433` (`Path.cwd()/name` → `place_or_default("inbox")`), `drive/commands.py:229-232`
- Modify: `h2t_ops/connectors/gmail/client.py` (2 записи по инвентарю), `notion/commands.py` (4), `dropbox/client.py` (8; потоковые `:259` и `:350` → `store.writer`, R29). Загрузка Drive через `MediaIoBaseDownload` пишет в дескриптор из `store.writer`
- Modify: `h2t_ops/connectors/research/client.py:31,177-192` (`DEFAULT_OUTPUT_DIR` → `data_dir()/"research"`; запасное чтение `paths.legacy("research")` для `research list/maintenance`), `research/store.py` (6), `research/visual_ocr.py` (4, `shutil.copy2` `:273`), `research/fetch.py` (2), `research/maintenance.py` (1), `research/exa.py:1147`
- Modify: `h2t_ops/lifecycle/eval/session.py:266-288` (`_write_local` → `records("evals", machine)/<skill>/<run>.json` через `store.create`), `:299-315` (спул → `store.managed(paths.evals_spool(), place="state", library="h2t_evals")`: путь всегда `state/evals-spool.sqlite`), `lifecycle/eval/status.py:48` (читатель обходит `records/evals/<машина>/<скилл>/*.json` по всем машинам, а не `<root>/<skill>/sessions/*.json`)
- Modify: `h2t_ops/tools/creative/cli.py:20-21` (`~/.h2t/creative/profiles` → `data_dir()/"creative"/"profiles"`, запасное чтение старого), `setup/sync.py:677`
- Modify: соответствующие тесты, в том числе `tests/connectors/research/test_exa_script_cases.py:595,620,642,653,667` (`setenv("H2T_EVALS_ROOT", …)` для `research/exa.py:1147`, которое здесь перестаёт читать переменную: записи искать в `paths.records("evals", <машина>)` под временным `HOME`)
- Modify: `tests/governance/sandbox_cases.py`, `tests/governance/test_storage_ratchets.py`

**Interfaces:**
- Consumes: `paths.place_or_default`, `paths.expand_user_dest`, `paths.records`, `paths.evals_spool`, `store.*`, `store.writer`.
- Produces: правило для всех команд с `--dest`/`--out`/позиционным `DEST`. Путь пользователя проходит через `paths.expand_user_dest`, запись идёт с `dest=True`. Без пути: `place_or_default(<место>)` и строка `saved to <путь>` в человеческом выводе; место записи по R28 — `place="inbox"`, если `inbox` задан, и `place="data"`, если путь по умолчанию (`defaulted=True`); `data/research` и `data/creative/profiles` — всегда `place="data"`. В `--json` то же самое — поле `path` и поле `defaulted`: `true`, когда место не задано в `paths.yaml` и файл ушёл в `data/<место>`; `false`, когда место задано (или путь дал пользователь).

Где какое место по умолчанию (§6 п. 1):

| Команда | Место |
|---|---|
| `drive download`, `drive export`, `gmail` вложения, `telegram download-media`, `dropbox download`, `notion` экспорт | `inbox` |
| `research` | `data/research` |
| `granola`, `meetgeek` | `lake/<провайдер>` (Task 11) |

`drive download` в 3.x без пути писал в текущий каталог. Это меняется на `inbox`. В CHANGELOG (Task 25) вписать строку «без пути — в inbox, а не в текущий каталог; `--dest .` возвращает прежнее».

- [ ] **Step 1: Тесты (красные)** — по одному на команду. Без пути файл оказывается в `inbox` из `paths.yaml`, а в выводе есть `"defaulted": false`. Без `paths.yaml` файл оказывается в `~/.h2t/data/inbox` и `"defaulted": true`. `--dest` внутрь `~/.h2t/secrets` даёт `WriteRefused`, код выхода 3. Для evals: запись сессии создаёт `records/evals/<машина>/<скилл>/<прогон>.json`, где `<прогон>` — имя файла 3.x без расширения, `<prefix>-<stamp>-<uuid8>` (`eval/session.py:273-275`). Если файл с таким именем уже есть (`AlreadyExists`), пишется `<прогон>-2.json`, затем `-3` и т.д. Повтор не перезаписывает: `records` пишется через `create`.

- [ ] **Step 2: Реализация.**

- [ ] **Step 3: Случаи песочницы** — `drive.download.default`, `drive.download.dest`, `gmail.attachment.default`, `notion.export.default`, `dropbox.download.default`, `research.save`, `research.fetch.save`, `research.maintenance`, `research.visual-ocr`, `evals.write-local`, `evals.spool` (подставной `EvalClient`, который открывает SQLite по переданному пути), `creative.profiles-dir`. Подставные провайдеры — как в тестах этих коннекторов; модули `research/store.py`, `fetch.py`, `maintenance.py`, `visual_ocr.py` должен исполнить хотя бы один случай (Task 24 проверяет это по `Recorder.writers`, R27).

- [ ] **Step 4: Ratchet, прогон** (`tests/connectors tests/lifecycle/eval tests/tools/creative tests/governance`), **commit** — `git add h2t_ops/connectors/drive/client.py h2t_ops/connectors/drive/commands.py h2t_ops/connectors/gmail/client.py h2t_ops/connectors/notion/commands.py h2t_ops/connectors/dropbox/client.py h2t_ops/connectors/research/client.py h2t_ops/connectors/research/store.py h2t_ops/connectors/research/visual_ocr.py h2t_ops/connectors/research/fetch.py h2t_ops/connectors/research/maintenance.py h2t_ops/connectors/research/exa.py h2t_ops/lifecycle/eval/session.py h2t_ops/lifecycle/eval/status.py h2t_ops/tools/creative/cli.py h2t_ops/setup/sync.py tests/connectors/research/test_exa_script_cases.py`, каждый другой правленый тест по имени, `tests/governance/sandbox_cases.py`, `tests/governance/test_storage_ratchets.py`; `feat(storage): default places for downloads, research, evals, creative profiles (#548)`.

### Task 13: Сессии и activity

**Files:**
- Modify: `h2t_ops/lifecycle/handoff.py` (`default_markdown_dir` `:57-61`, `write_handoff` `:184-284`, шаблон `:229-244`; все четыре защитные ветки — `:221` (каталог md), `:260` (`latest.json`), `:269` (md), `:276` (дозапись `markdown_path`) — ловят ещё `H2TError`)
- Modify: `h2t_ops/lifecycle/gather/sessions.py:13-14` (`_session_root` → `paths.records("sessions")`; остальное чтение — до Task 16 как есть)
- Modify: `h2t_ops/lifecycle/activity/writer.py:62-90` (`_spool_path`, запись)
- Create: `h2t_ops/lifecycle/session_record.py`
- Create: `tests/lifecycle/test_session_record.py`
- Modify: `tests/governance/sandbox_cases.py`, `tests/governance/test_storage_ratchets.py`
- Modify: `tests/lifecycle/test_handoff_writer.py`, `tests/lifecycle/test_handoff_gather_round_trip.py`, `tests/lifecycle/activity/test_writer.py`, `tests/core/test_session_identity_roundtrip.py`, `tests/core/test_handoff_identity_from_cwd.py`
- Modify: тесты, которые задают `H2T_SESSION_ROOT`/`H2T_ACTIVITY_SPOOL` (в этой задаче обе переменные перестают читаться, R5); каждый переводится на раскладку под временным `HOME`/`USERPROFILE` (`paths.records("sessions", m)`, `paths.activity_file(m)`):
  - `tests/core/test_machine_name.py:36-37` (фикстура `renamed_host`: `HOME` = `tmp_path`, спул читать из `paths.activity_file("mac")`);
  - `tests/core/test_gather_single_implementation.py:55` (дочерний процесс получает `HOME`/`USERPROFILE` = `root.parent`, сессии — под `records/sessions/test-machine/…`);
  - `tests/core/test_entrypoint_exit_codes.py:19-20` (`_env`: `HOME`/`USERPROFILE` во временном каталоге вместо двух переменных);
  - `tests/lifecycle/gather/test_sessions_lookup.py:30,44,59` (каталоги машин — под `paths.records("sessions")`; `latest.json` в них остаётся до Task 16).
  Сверено `grep -rn "H2T_SESSION_ROOT\|H2T_ACTIVITY_SPOOL" tests/ lib/` на 2ddd6db6: кроме этих четырёх и файлов строкой выше — только списки `delenv`/фильтры (`tests/hooks/hook_cases.py:31`, `tests/hooks/test_budgets.py:69`), правки не нужны

**Interfaces:**
- Produces:

```python
# h2t_ops/lifecycle/session_record.py
FIELDS = ("session_id", "machine", "project", "domain", "date", "updated_at", "branch",
          "commits", "done", "remains", "artifacts", "migrated_from")

def render(meta: dict, body: bytes) -> bytes        # b"---\n" + yaml + b"---\n" + body
def parse(raw: bytes) -> tuple[dict, bytes]          # raises ValueError on a broken header
def session_path(machine: str, project: str, session_id: str) -> Path
```

- `write_handoff(...)` → прежний словарь. md пишется через `store.replace(place="records.sessions")`: повторный handoff той же сессии обновляет её запись (§5). При `--markdown-dir` md пишется по этому пути с `dest=True`.
- **`latest.json` пока пишется** (R10): рядом с md, в `records/sessions/<машина>/<проект>/latest.json`, через `store.replace(place="records.sessions")` вместо `_write_json_atomic` (`:157-160` удалить); при `--markdown-dir` — по тому же каталогу с `dest=True`, как md. gather в этой же задаче читает `paths.records("sessions")` вместо `~/.h2t/sessions`, поэтому полный круг handoff → gather (`tests/lifecycle/test_handoff_gather_round_trip.py`) остаётся зелёным между Task 13 и Task 16. Task 16 переводит gather на индекс и перестаёт писать `latest.json`.
- `writer.log_session_start/end` → `store.append(paths.activity_file(machine), …, place="records.activity")`. `H2T_ACTIVITY_SPOOL` не читается (R5).
- Защитные ветки handoff ловят `OSError` (`handoff.py:221,260,269,276`); `store` бросает и `WriteRefused` (подкласс `ConfigError`): при `--markdown-dir` внутрь места пакета или при отказе записи вне `~/.h2t`, пока испорчен `paths.yaml` (R17). Ловить во всех четырёх `(OSError, H2TError)`: исключение после записи спула нарушало бы инвариант #391 (`gates.md`). Каталог md создаётся `store.mkdir(md_dir, place="records.sessions", dest=markdown_dir is not None)` — первая операция над этим путём, поэтому отказ `--markdown-dir` внутрь места пакета приходит в ветку `:221`.

- [ ] **Step 1: Тесты (красные).**

```python
# tests/lifecycle/test_session_record.py
import pytest

from h2t_ops.lifecycle import session_record as sr


def test_round_trip_keeps_body_bytes():
    body = "# Session: s\r\n\nтело\n".encode()
    meta = {"session_id": "s", "machine": "m", "project": "p", "done": "a\nb"}
    raw = sr.render(meta, body)
    got, got_body = sr.parse(raw)
    assert got_body == body and got["done"] == "a\nb" and got["machine"] == "m"


@pytest.mark.parametrize("raw", [b"---\nsession_id: [\n---\nx", b"---\nno end", b"plain md"])
def test_broken_header_raises(raw):
    with pytest.raises(ValueError):
        sr.parse(raw)
```

В `tests/lifecycle/test_handoff_writer.py` нужны пять тестов (шестой — в Step 4):

- `default_markdown_dir("repo")` равен `paths.records("sessions", "test-machine") / "repo"`;
- handoff пишет md с frontmatter, где `machine`, `project`, `domain`, `updated_at` и `branch` заполнены, и `latest.json` рядом с ним (до Task 16);
- повторный handoff с тем же `session_id` оставляет один md с новым `done`;
- `H2T_SESSION_ROOT` больше не читается: при заданной переменной md всё равно в `records/sessions/…` (R5);
- отказ записи md (`--markdown-dir` внутрь `paths.secrets_shared()`) даёт деградированный ответ `_degraded`, а не исключение, и строка спула уже записана.

В `tests/lifecycle/activity/test_writer.py`: запись попадает в `records/activity/<машина>.jsonl`, а заданный `H2T_ACTIVITY_SPOOL` ничего не меняет.

- [ ] **Step 2: Реализация.**
  - `branch`: `git rev-parse --abbrev-ref HEAD` в cwd.
  - `commits`: `git log -5 --format=%h`, через `gather.runner._run_one`, таймаут 5 с. Ошибка git даёт пустые поля, handoff не роняет (правило gates.md).
  - `updated_at`: UTC ISO с `Z`.
  - Тело md — прежний шаблон `:229-244`, чтобы читатель-человек видел то же, что в 3.x.

- [ ] **Step 3: Случаи песочницы** — `handoff.write`, `handoff.write.again`, `activity.start`.

- [ ] **Step 4: Красный контроль защиты.** В ветке каталога md (бывшая `:221`) вернуть `except OSError` → тест про отказ записи md FAIL с `WriteRefused`. Вернуть. Ветки md и `latest.json` проверяет второй контроль: подставить `store.replace`, который бросает `WriteRefused` только для имени `latest.json` (каталог проходит), и вернуть `except OSError` в ветке `latest.json` → тот же тест с этой подстановкой FAIL; вернуть. Тест с подстановкой — шестой в `test_handoff_writer.py`: `test_refused_latest_json_degrades_after_the_spool_row`.

- [ ] **Step 5: Ratchet, прогон** (`tests/lifecycle tests/core tests/governance`), **commit** — `git add h2t_ops/lifecycle/handoff.py h2t_ops/lifecycle/gather/sessions.py h2t_ops/lifecycle/activity/writer.py h2t_ops/lifecycle/session_record.py tests/lifecycle/test_session_record.py tests/lifecycle/test_handoff_writer.py tests/lifecycle/test_handoff_gather_round_trip.py tests/lifecycle/activity/test_writer.py tests/core/test_session_identity_roundtrip.py tests/core/test_handoff_identity_from_cwd.py tests/core/test_machine_name.py tests/core/test_gather_single_implementation.py tests/core/test_entrypoint_exit_codes.py tests/lifecycle/gather/test_sessions_lookup.py tests/governance/sandbox_cases.py tests/governance/test_storage_ratchets.py`; `feat(sessions): handoff writes a self-describing md under records/, activity per machine (#548)`.

### Task 14: Индекс `state/index.sqlite`

**Files:**
- Create: `h2t_ops/lifecycle/index/__init__.py`, `schema.py`, `build.py`, `query.py`
- Create: `tests/lifecycle/index/__init__.py` (пустой, как во всех каталогах `tests/`), `tests/lifecycle/index/test_index.py`
- Modify: `tests/governance/sandbox_cases.py`, `tests/governance/test_storage_ratchets.py`

**Interfaces:**
- Consumes: `session_record.parse`, `paths.records`, `paths.config_dir`, `paths.state_dir`, `store.connect_sqlite`, `store.remove`.
- Produces:

```python
SCHEMA_VERSION = 1
@contextmanager
def connect(*, refresh: bool = True) -> Iterator[sqlite3.Connection]
def rebuild() -> dict                                  # {"sessions": n, "projects": n, "problems": n}
def latest_sessions(project_ids: list[str], limit: int = 5) -> list[dict]
def ontology() -> tuple[dict, dict]                     # (repo_mapping_doc, domains_doc)
def problems() -> list[dict]                            # [{"path", "error"}]
# build.py
def load_ontology(config_root: Path) -> tuple[dict, dict]   # parse the two YAML directly, no index (Task 15)
```

Схема (`schema.py`):

```sql
CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE stamps(path TEXT PRIMARY KEY, mtime_ns INTEGER, size INTEGER);
CREATE TABLE projects(id TEXT PRIMARY KEY, domain TEXT, label TEXT, type TEXT, github TEXT);
CREATE TABLE repos(pattern TEXT, kind TEXT, project TEXT, domain TEXT);
CREATE TABLE sessions(path TEXT PRIMARY KEY, dir TEXT, session_id TEXT, machine TEXT,
                      project TEXT, domain TEXT, date TEXT, updated_at TEXT, branch TEXT,
                      last_commit TEXT, done TEXT, remains TEXT, artifacts TEXT, conflict INTEGER);
CREATE INDEX sessions_project ON sessions(project, updated_at);
CREATE TABLE registry_history(line INTEGER PRIMARY KEY, ts TEXT, machine TEXT, project TEXT,
                              status TEXT, raw TEXT);
CREATE TABLE problems(path TEXT PRIMARY KEY, error TEXT);
```

`meta` хранит `schema_version`, а также `repo_mapping` и `domains` как JSON, разобранный из YAML. YAML разбирает только `build.py` (§5). Колонка `last_commit` — первый элемент поля `commits` frontmatter (`git log -5`, новые первыми; Task 13), пустая строка, если поля нет.

Обновление перед запросом (`connect(refresh=True)`):

1. Взять `stat` (`st_mtime_ns`, `st_size`) каждого файла онтологии: `domains.yaml`, `repo-mapping.yaml`. Изменился — перечитать оба.
2. Взять `stat` каждого листового каталога `records/sessions/<машина>/<проект>/`. Изменился или новый — перечитать все `*.md` в нём, кроме `*.from-*`. Файл `*.sync-conflict-*` индексировать с `conflict=1`. Исчезнувший каталог — удалить его строки.
3. Взять `stat` файла `records/imports/dor-registry.jsonl`. Изменился — перечитать.
4. md, который не разбирается, попадает в `problems`, а не в `sessions`.

Если версия схемы не совпала или `sqlite3.DatabaseError`: закрыть, `store.remove(place="state")` для базы и её `-journal`, собрать заново. Открывать только через `store.connect_sqlite(index_path, place="state")` (R18): так `sqlite3.connect` остаётся в одном `store.py`. md, отредактированный на месте редактором без переименования, меняет `stat` файла, но не каталога, и до следующего изменения каталога индексом не увидится; это согласуется с §5 (смотрится `stat` листового каталога) и названо здесь, чтобы не считаться дефектом.

- [ ] **Step 1: Тесты (красные).**
  - `test_rebuild_reads_frontmatter_of_every_machine`.
  - `test_new_file_from_another_machine_is_seen_on_next_connect`: создать каталог `records/sessions/laptop/p/` после первой сборки.
  - `test_yaml_edit_in_place_is_seen`: переписать `domains.yaml` тем же размером другим содержимым и выставить новый mtime через `os.utime`. Индекс видит правку.
  - `test_broken_frontmatter_is_skipped_and_reported`: Review Focus 3.
  - `test_schema_mismatch_rebuilds`: записать в `meta` `schema_version=0`.
  - `test_corrupt_db_rebuilds`: записать в файл базы мусор.
  - `test_sync_conflict_file_is_flagged`.
  - `test_latest_sessions_orders_across_machines_by_updated_at`.
  - Контроль: тест на время. Индекс по 320 сгенерированным md строится быстрее 3 с (бюджет §11.2), повторный `connect` без изменений — быстрее 0,1 с. Пометить `@pytest.mark.slow`.

- [ ] **Step 2: Реализация.**

- [ ] **Step 3: Красный контроль.** В шаге 1 обновления смотреть mtime каталога `config/` вместо файлов → `test_yaml_edit_in_place_is_seen` FAIL. Вернуть.

- [ ] **Step 4: Случаи песочницы** — `index.rebuild`, `index.connect.refresh`.

- [ ] **Step 5: Ratchet, прогон** (`tests/lifecycle/index tests/governance`), **commit** — `git add h2t_ops/lifecycle/index/__init__.py h2t_ops/lifecycle/index/schema.py h2t_ops/lifecycle/index/build.py h2t_ops/lifecycle/index/query.py tests/lifecycle/index/__init__.py tests/lifecycle/index/test_index.py tests/governance/sandbox_cases.py tests/governance/test_storage_ratchets.py`; `feat(index): derived SQLite index over session md and ontology (#548)`.

### Task 15: Онтология через индекс

**Files:**
- Modify: `h2t_ops/lifecycle/gather/project.py:17-29` (`_get_config_root`, `_load_yaml` → `index.ontology()`)
- Modify: `h2t_ops/lifecycle/detect_project.py:185-194,260-267` (то же)
- Modify: `h2t_ops/lifecycle/apply_registration.py:25,42-148` (`_backup` через `shutil.copy2` в `<файл>.bak` рядом → копия в `paths.backups_dir() / f"{path.name}.{YYYYmmdd-HHMMSS}"` через `store.create(place="state")`, затем из копий этого файла остаются последние 10, лишние — `store.remove(place="state")` (R14); запись YAML → строка из ruamel в `store.replace(place="config")`, а при явном `config_root` (каталог, который назвал вызывающий: тесты `tests/lifecycle/test_apply_registration.py:41-49`, `--config-root`) — `store.replace(path, text, place="config", dest=True)`: такой каталог классифицируется как `tmp`/`elsewhere`, а не `config`, и без `dest` был бы отказ (R43); `config_root` внутри места пакета, кроме самого `paths.config_dir()`, `dest` отклоняет; `config_root`, равный `paths.config_dir()` по `realpath`, пишется как обычный `place="config"`; `.claude/project-id` (`:139-149`) → `store.repo(cwd, "h2t-project-register").create(...)`, `AlreadyExists` — не ошибка, файл остаётся (§7.1 «создать, если нет», R32; так же, как проверка `if not pid_file.exists()` в 3.x)
- Modify: `h2t_ops/lifecycle/scaffold_project.py` — только регистрация (остальное в Task 17)
- Modify: `h2t_ops/tools/docs/common.py:88-94` (свой `yaml.safe_load` `repo-mapping.yaml` под `Path.home()` → `index.ontology()[0]`; любая ошибка — `H2TError`, `OSError`, `sqlite3.Error` — даёт прежний запасной `_BUNDLED_MANIFEST`)
- Create: `tests/governance/test_one_ontology_parser.py`
- `H2T_CONFIG_ROOT` в этой задаче перестаёт читаться (R5, `OLD_ENV` → `remove`): `gather/project.py:19`, `detect_project.py:264`, `apply_registration.py:29-36`; явный `--config-root`/`config_root=` остаётся (через `build.load_ontology`). Тесты, которые задают переменную, — `tests/lifecycle/gather/test_project.py:81,101,115,128,142,153` и `tests/core/test_init_project_registration.py:83-88` — переводятся на `config/` под временным `HOME` или на явный `config_root`; `tests/hooks/test_init_data_freshness.py:20` только удаляет переменную, правки не нужно
- Modify: `tests/lifecycle/test_apply_registration.py`, `test_detect_project.py`, `tests/lifecycle/gather/test_project.py`, `tests/core/test_init_project_registration.py`, тесты `tools/docs`, которые подкладывают `repo-mapping.yaml` для `common.py` (найти `grep -rln "repo-mapping" tests/tools`)
- Modify: `tests/governance/sandbox_cases.py`, `tests/governance/test_storage_ratchets.py`

**Interfaces:**
- Consumes: `index.ontology()`, `store.replace(place="config")`, `store.repo`.
- Produces: прежние сигнатуры `identify_project(cwd)`, `detect_project(cwd, config_root=None)`, `apply_registration(...)`. Явный `config_root` читается **напрямую** через `build.load_ontology(config_root)` — функцию сборщика без индекса. Только явный: так тесты и `--config-root` работают на чужом каталоге без пересборки базы машины.

- [ ] **Step 1: Тест единственного читателя (красный).** `tests/governance/test_one_ontology_parser.py`: `grep` по `h2t_ops/` для `yaml.safe_load|YAML\(\)` в связке с `domains.yaml|repo-mapping.yaml`. Разрешены только `lifecycle/index/build.py` (разбор) и `apply_registration.py` (запись через ruamel). Связка ищется по файлу целиком, а не по строке: в `common.py` имя файла (`:88`) и `safe_load` (`:94`) — на разных строках. Сейчас FAIL: `gather/project.py`, `detect_project.py`, `tools/docs/common.py`.

- [ ] **Step 2: Реализация.** Регистрация: после записи YAML через `store` индекс сам увидит изменение по `stat` при следующем `connect`. Отдельный вызов не нужен, но тест `test_registration_is_visible_to_identify_project_at_once` это проверяет: регистрация, затем сразу `identify_project`. Существующие тесты с `config_root=str(tmp_path)` (`test_apply_registration.py:41-49` и соседние) — проверка R43: красный контроль — убрать `dest=True` для явного корня → они FAIL с `WriteRefused … is in tmp, not config`; вернуть. Тест `test_backup_goes_to_state_and_keeps_ten`: 12 регистраций подряд (время подставлено) → в `config/` нет ни одного `*.bak`, в `state/backups/` ровно 10 копий `domains.yaml.*`, самые новые.

- [ ] **Step 3: Случаи песочницы** — `register.apply` (временный репо и `config`), `detect.project`.

- [ ] **Step 4: Ratchet, прогон** (`tests/lifecycle tests/core/test_init_project_registration.py tests/tools/docs tests/governance`), **commit** — `git add h2t_ops/lifecycle/gather/project.py h2t_ops/lifecycle/detect_project.py h2t_ops/lifecycle/apply_registration.py h2t_ops/lifecycle/scaffold_project.py h2t_ops/tools/docs/common.py tests/governance/test_one_ontology_parser.py tests/lifecycle/test_apply_registration.py tests/lifecycle/test_detect_project.py tests/lifecycle/gather/test_project.py tests/core/test_init_project_registration.py tests/governance/sandbox_cases.py tests/governance/test_storage_ratchets.py` и правленые тесты `tests/tools/docs/…` по имени; `refactor(ontology): one parser in the index builder; registration writes through store (#548)`.

### Task 16: `session-start` — последняя сессия проекта со всех машин

**Files:**
- Modify: `h2t_ops/lifecycle/gather/sessions.py:13-136` (`_session_root`, `_legacy_session_root`, `find_session_files`, `find_latest_session_index` → индекс)
- Create: `h2t_ops/lifecycle/gather/sessions_legacy.py` (запасное чтение 3.x, ниже)
- Modify: `tests/governance/sandbox_cases.py`, `tests/governance/test_storage_ratchets.py`
- Modify: `h2t_ops/lifecycle/session_start.py:105-106`
- Modify: `h2t_ops/lifecycle/gather/briefing.py:117,149-193`
- Modify: `h2t_ops/lifecycle/handoff.py` (запись `latest.json`, оставленная Task 13, удаляется; ключ `latest` в ответе = путь md, R10)
- Modify: `plugins/h2t-core/skills/handoff/SKILL.md` (шаги 6–7: `latest.json` → путь md), `plugins/h2t-core/skills/session-start/SKILL.md` (если упоминает `latest.json`)
- Modify: `tests/lifecycle/gather/test_sessions.py`, `test_sessions_lookup.py`, `test_briefing_previous_session.py`, `tests/lifecycle/test_handoff_gather_round_trip.py`, `tests/lifecycle/test_handoff_writer.py` (`latest.json` больше не появляется)
- Modify: `tests/core/test_entrypoint_exit_codes.py:87-104` (`payload["latest"]` теперь путь md, R10: утверждать `is_file()` для md; тест про каталог `latest.json.tmp` переписать на отказ записи md — ту же деградацию `_degraded` при уже записанной строке спула)
- Modify: `tests/core/test_gather_single_implementation.py:49-67` (фикстура кладёт `latest.json`: заменить на md с frontmatter `session_record.render(...)` под `records/sessions/test-machine/<проект>/`, блок брифинга строится из индекса)
- `lib/practice_harvest/collect.py:39` только пропускает файл с именем `latest.json` — правки не нужно

**Interfaces:**
- Produces: `find_latest_session_index(*repo_names) -> dict | None`. Ключи прежние (`summary_short`, `next_actions`, `artifacts`, `updated_at`, `markdown_path`, `truncated`) плюс `machine`, `branch`, `last_commit`, `here: dict | None` (последняя сессия этой машины, если последняя вообще была на другой). `find_session_files` возвращает пути md из индекса в прежнем порядке «новые первыми».

Брифинг (§5):

```text
### Previous Session  (automata, 2 дня назад)
ветка feat/x, последний коммит a1b2c3d
- Summary: …
- Next: …
⚠ на automata работали позже, чем здесь (macbook-pro-3, 5 дней назад) — git fetch
```

Строка `⚠` выводится, только если `machine != paths.machine_name()` **и** на этой машине есть сессия того же проекта старше. Возраст: «сегодня», «вчера», «N дн. назад» по `updated_at`. Лимит 1800 символов и маркер обрезки сохраняются.

Запасное чтение 4.0.x: если в индексе нет ни одной сессии проекта, а старые каталоги (`paths.legacy("sessions.h2t")`, `paths.legacy("sessions.dor")`) существуют, работает прежняя логика 3.x чтения `latest.json` и md — она переезжает в `gather/sessions_legacy.py`. Тогда брифинг получает строку `ℹ сессии ещё в старом месте — h2t-setup sync перенесёт их`.

- [ ] **Step 1: Тесты (красные).**
  - `test_previous_session_names_machine_and_age`.
  - `test_warning_only_when_other_machine_is_newer`.
  - `test_other_projects_never_appear`.
  - `test_legacy_fallback_before_migration`.
  - Тест полного круга `handoff` → `gather`: `test_handoff_gather_round_trip.py`, дочерний процесс с `HOME`/`USERPROFILE` во временном каталоге. Брифинг содержит `done` только что записанной сессии и имя машины.

- [ ] **Step 2: Реализация.**

- [ ] **Step 3: Скиллы и `latest.json`.** Только теперь, когда gather читает индекс, handoff перестаёт писать `latest.json` (R10).
  - `handoff/SKILL.md` Step 7 печатает строку `✓ Latest index: {latest_path}`. Заменить её на `✓ Запись: {markdown_path}` и убрать абзац про `index_truncated`.
  - Найти остальные упоминания: `grep -rn "latest.json" plugins/`.
  - После правки `tests/core/test_skill_*` прогнать отдельно.

- [ ] **Step 4: Случаи песочницы** — `gather.session-start` (индекс с одной сессией другой машины, вызов брифинга; запись — только индекс в `state` через `store.connect_sqlite`), `gather.session-start.legacy` (`setup` кладёт старые `latest.json` и md в `paths.legacy("sessions.h2t")`; брифинг читает их, ничего не пишет в старое место), `handoff.write.no-latest-json` (после Step 3 рядом с md нет `latest.json`).

- [ ] **Step 5: Ratchet, прогон** (`tests/lifecycle tests/core tests/hooks tests/governance`), **commit** — `git add h2t_ops/lifecycle/gather/sessions.py h2t_ops/lifecycle/gather/sessions_legacy.py h2t_ops/lifecycle/session_start.py h2t_ops/lifecycle/gather/briefing.py h2t_ops/lifecycle/handoff.py plugins/h2t-core/skills/handoff/SKILL.md tests/lifecycle/gather/test_sessions.py tests/lifecycle/gather/test_sessions_lookup.py tests/lifecycle/gather/test_briefing_previous_session.py tests/lifecycle/test_handoff_gather_round_trip.py tests/lifecycle/test_handoff_writer.py tests/core/test_entrypoint_exit_codes.py tests/core/test_gather_single_implementation.py tests/governance/sandbox_cases.py tests/governance/test_storage_ratchets.py` (и `plugins/h2t-core/skills/session-start/SKILL.md` и прочие найденные `grep` скиллы — если правились, по имени); `feat(session-start): latest session of this project from any machine (#548)`.

### Task 17: Запись в репо

**Files:**
- Modify: `h2t_ops/core/repo_writers.py` (полный список)
- Modify: `h2t_ops/lifecycle/scaffold_project.py` (15 строк записи), `tools/docs/docs_init.py` (11), `tools/docs/lint.py` (11), `tools/docs/gitignore_hygiene.py` (3), `tools/docs/index_builder.py` (4), `tools/docs/index.py` (1), `tools/docs/retire.py` (2), `tools/docs/new_doc.py` (2), `tools/docs/common.py` (2), `tools/docs/closure.py` (3), `tools/agent_profile/apply_agent_profile.py` (3), `tools/runbook/new_runbook.py` (2), `hooks/plan_closer.py` (1), `hooks/post_git_commit_docs_lint.py` (3), `tools/drawio/generate.py` (2), `tools/drawio/export.py` (1), `tools/creative/assembler.py` (10), `lifecycle/project_audit_report.py` (1) — числа `storage_map.hits(…, "writes")` по файлам на 2ddd6db6 с правилами R21
- Create: `tests/governance/test_repo_writers.py`
- Create: `docs/reports/2026-MM-DD-storage-repo-writers.md` (отчёт замера Step 1; frontmatter `title`/`status`/`date`, как у `docs/reports/2026-10-17-exec-map.md`)
- Modify: `docs/superpowers/specs/2026-10-17-storage-and-governance.md` §7.1, таблица «Список записей в `repo`» — только строки, где замер разошёлся с таблицей (спека сама называет её «отправной точкой» инвентаря)
- Modify: `tests/governance/sandbox_cases.py`, `tests/governance/test_storage_ratchets.py`

**Interfaces:**
- Consumes: `store.repo(root, command)`; `store.replace(..., dest=True)` для drawio и creative (R7).
- Produces: `REPO_WRITERS` с ключами-командами. Список шаблонов замеряется, а не угадывается.

- [ ] **Step 1: Замер.** Для каждой команды из таблицы §7.1 и каждой строки из списка файлов выше: запустить её во временном git-репо (команды и аргументы — из её тестов в `tests/tools`, `tests/lifecycle`, `tests/hooks`) и собрать `git status --porcelain --untracked-files=all` до и после. Итог — таблица `команда → пути`. Вписать её в отчёт `docs/reports/2026-MM-DD-storage-repo-writers.md`: команда, что пишет, правило перезаписи. Отчёт сверяет таблицу §7.1 с фактом. Расхождения вписать в §7.1 спеки. Правило перезаписи `.claude/project-id` — «создать, если нет» (R32) — при этом не меняется; замер, который показывает перезапись, — дефект кода, а не повод править таблицу. Расширение `REPO_WRITERS` должно сохранить ключи `init-project` и `h2t-project-register` (их уже использует Task 15).

- [ ] **Step 2: Тест (красный).** `tests/governance/test_repo_writers.py` параметризован по таблице Step 1. Каждая команда идёт во временном репо, под `Recorder` из Task 7: `audit.Recorder([repo], [], [], {})`. Утверждения:
  - нарушений аудита нет: все записи шли через `store`;
  - каждый изменённый путь подходит под шаблоны `REPO_WRITERS[команда]`.

  На текущем коде FAIL по первому утверждению.

- [ ] **Step 3: Реализация.** Каждая запись → `store.repo(<корень>, "<команда>").<операция>(...)`. Ключевые случаи:

  | Команда | Корень | Особенность |
  |---|---|---|
  | `scaffold_project` | `project_dir` | `.git/info/exclude` (`:490`) — операция `append` для шаблона `.git/info/exclude`; путь брать из `git rev-parse --git-path info/exclude`: в worktree `.git` — файл, а не каталог. Если путь лежит внутри `project_dir` — `RepoWriter.append`; если вне (worktree: общий `info/exclude` основного репо) — `store.append(path, line, place="repo", dest=True)`, путь дал git этого же репо, а не пользователь; `RepoWriter._target` такой путь отверг бы как «outside the repository» |
  | `docs-lint` `git mv` (`lint.py:980,1063`, `retire.py:170`) | репо | `RepoWriter.rename(..., git=True)`; запасной `src.rename(dst)` (`retire.py:176`, когда `git mv` не прошёл) → `RepoWriter.rename(..., git=False)` |
  | `lint.py:888` | — | `--save <файл>` пишет по пути пользователя: `dest=True` |
  | отчёты `lint.py:1021,1147` | репо, `docs/.artifacts/**` или где укажет замер | — |
  | `post_git_commit_docs_lint.py` | репо, из `git rev-parse --show-toplevel` | хук |
  | `plan_closer` | репо, `docs/superpowers/**` | хук |

  Важно: `plan_closer` сегодня ставит `status: done` спеке при каждом merge, и это неверно до выпуска 4.0.0 (память сессии). Поведение не менять, только маршрут записи.

- [ ] **Step 4: Случаи песочницы.** По случаю на каждую команду таблицы Step 1, id — `repo.<команда>` (`repo.scaffold`, `repo.docs-init`, `repo.docs-lint.fix-safe`, `repo.docs-lint.retire`, `repo.docs-lint.save`, `repo.agent-profile`, `repo.runbook`, `repo.plan-closer`, `repo.post-commit-docs-lint`, `repo.project-audit`); `setup` создаёт временный git-репо внутри `tmp_path` и кладёт исходные файлы. Плюс `drawio.generate.dest`, `drawio.export.dest`, `creative.assemble.dest` (R7, `dest=True`). Вместе эти случаи исполняют все модули из списка Files (Task 24 проверяет по `Recorder.writers`).

- [ ] **Step 5: Ratchet, прогон** (`tests/tools tests/lifecycle tests/hooks tests/scaffold tests/governance`), **commit** — `git add h2t_ops/core/repo_writers.py` + каждый `h2t_ops/…` файл из списка Files по полному пути + `tests/governance/test_repo_writers.py docs/reports/2026-MM-DD-storage-repo-writers.md tests/governance/sandbox_cases.py tests/governance/test_storage_ratchets.py` (+ спека, если правилась); `refactor(repo): every write into a user repository goes through the allow-list (#548)`.

### Task 18: Установка, хуки, логи, временные файлы

**Files:**
- Modify: `h2t_ops/setup/state.py` (`run_dir` → `paths.run_dir`; `_atomic_write` → `store.replace(place="run")`)
- Modify: `h2t_ops/setup/sync.py:264-277` (снимок → `store.replace(place="run")` и `store.replace(…place="run")` вместо `shutil.copyfile`), `:499-596` (`claude-pending.json` → `store.replace/remove(place="run")`), `:618-677` (кэш плагинов `_remove_tree` → `store.remove_tree(place="harness")`), `:830` (constraints)
- Modify: `h2t_ops/setup/legacy.py:424-434` (`settings.json` Claude → `store.replace(place="harness")`), `:818-826` (`versions_file`)
- Modify: `h2t_ops/hook_entry.py:48-57`, `hooks/grade_guard.py:34,74-82`, `hooks/plain_guard.py:35,104-114` (логи → `store.append(paths.logs_dir()/…, place="logs")`). Защитные ветки ловят только `OSError` (`hook_entry.py:57`, `grade_guard.py:41,84`, `plain_guard.py:114`); через `store` прилетает ещё `WriteRefused` — ловить `(OSError, H2TError)`, иначе хук падает вместо тихого пропуска записи лога
- Modify: `h2t_ops/hooks/gather.py:65-81` (`_lock_file` → `paths.state_dir() / "locks" / f"gather-{key}.lock"`, `_write_lock` → `store.replace(place="state")`, ловит `(OSError, H2TError)`; R23: в `tmp` пакет пишет только через `store.scratch()`, а `scratch` удаляется на выходе и блокировку между вызовами хука не держит)
- Modify: `h2t_ops/deploy/executor.py:229-231` (`tempfile.TemporaryDirectory` → `store.scratch()`, запись входа → `store.replace(place="tmp")`)
- Modify: места, которые сканер на 09223a11 находит вне задач 8–17 (иначе Task 24 не дойдёт до нуля):
  - `h2t_ops/deploy/profiles.py:20`, `deploy/registry.py:25` (`Path.home() / ".h2t/config/deploy/…"` → `paths.config_dir() / "deploy" / …`);
  - `h2t_ops/lifecycle/gather/user.py:25` (`Path.home() / ".h2t" / "config"` → `paths.config_dir()`);
  - `h2t_ops/lifecycle/rule_scan.py:74` (`scan(…, Path.home())` → `paths.home()`);
  - `h2t_ops/setup/harness_claude.py:42,47` (`Path.home()`, `Path.home() / ".claude"` → `paths.home()`, `paths.dir_of("harness")`);
  - `h2t_ops/setup/legacy.py` — пути, которые не ушли в Task 10: `:80`, `:142`, `:300`, `:397`, `:418` (сверить по `storage_map.hits`, переводить на `paths.*`).
- Modify: `conftest.py` (в наблюдаемые пути добавить `~/.h2t/logs`)
- Create: `tests/setup/test_bootstrap_round_trip.py`
- Modify: `tests/hooks/test_budgets.py:169` (ищет `h2t_gather_*.lock` во временном каталоге → `state/locks/gather-*.lock`)
- Modify: `tests/governance/sandbox_cases.py`, `tests/governance/test_storage_ratchets.py`

**Interfaces:**
- Consumes: `paths.run_dir`, `paths.dir_of("harness")`, `store.*`.
- Produces: тест полного круга бутстрапа (§7.3). `hooks/run` запускается против `install.env`, который записал `state.commit` через `paths.run_dir()`.

- [ ] **Step 1: Тест полного круга (красный по замыслу — на текущем коде он зелёный, поэтому красный прогон делается порчей).**

```python
# tests/setup/test_bootstrap_round_trip.py
import os
import subprocess
import sys
from pathlib import Path

import pytest

from h2t_ops.setup import state

RUN = Path(__file__).resolve().parents[2] / "plugins" / "h2t-core" / "hooks" / "run"


@pytest.mark.skipif(sys.platform == "win32", reason="covered by tests/hooks/test_hooks_run.py on Git Bash")
def test_hooks_run_reads_what_state_wrote(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("H2T_PATH_ROOT", str(tmp_path / "elsewhere"))  # must not move run/
    hook = tmp_path / "bin" / "h2t-hook"
    hook.parent.mkdir()
    hook.write_text("#!/bin/sh\necho HOOK-RAN \"$@\"\n")
    hook.chmod(0o755)
    version = (RUN.parent.parent / "release.env").read_text().split("VERSION=")[1].split()[0]
    state.commit(state.Install(version=version, generation="g1", tool_root=str(tmp_path),
                               entrypoints={"h2t-hook": str(hook)}))
    env = {**os.environ, "CLAUDE_PLUGIN_ROOT": str(RUN.parent.parent)}
    out = subprocess.run(["bash", str(RUN), "session-start"], input="{}", text=True,
                         capture_output=True, env=env, timeout=30)
    assert "HOOK-RAN session-start" in out.stdout, out.stderr
```

Имя хука и аргументы `hooks/run` сверить с `tests/hooks/test_hooks_run.py:80`. Порча для красного прогона: в `paths.run_dir()` вернуть `root() / "run"`. Тест → FAIL: `install.env` ушёл в `H2T_PATH_ROOT`, а bash читает `$HOME/.h2t/run`. Вернуть.

- [ ] **Step 2: Реализация.**

- [ ] **Step 3: Случаи песочницы** — `setup.state.commit`, `setup.sync.snapshot` (подставные `uv` и `claude` из `tests/setup/test_sync_converges.py`), `hook.log-failure`, `hook.gather.lock`, `deploy.executor.input`.

- [ ] **Step 4: Ratchet, прогон** (`tests/setup tests/hooks tests/deploy tests/core tests/governance`), **commit** — `git add h2t_ops/setup/state.py h2t_ops/setup/sync.py h2t_ops/setup/legacy.py h2t_ops/hook_entry.py h2t_ops/hooks/grade_guard.py h2t_ops/hooks/plain_guard.py h2t_ops/hooks/gather.py h2t_ops/deploy/executor.py h2t_ops/deploy/profiles.py h2t_ops/deploy/registry.py h2t_ops/lifecycle/gather/user.py h2t_ops/lifecycle/rule_scan.py h2t_ops/setup/harness_claude.py conftest.py tests/setup/test_bootstrap_round_trip.py tests/hooks/test_budgets.py tests/governance/sandbox_cases.py tests/governance/test_storage_ratchets.py` и правленые тесты хуков/установки по имени; `refactor(setup,hooks): install state, snapshots, logs and temp files through store (#548)`.

### Task 19: `h2t-ops paths` и `h2t-ops index`

**Files:**
- Create: `h2t_ops/core/paths_cli.py`
- Modify: `h2t_ops/cli.py:20-29` (`sub.add_parser("paths")`, `sub.add_parser("index")`), `dispatch` (`:166`; новые ветки — до ветки `_MIGRATED` на `:281`)
- Create: `tests/cli/test_paths_cli.py`
- Modify: `tests/governance/sandbox_cases.py`, `tests/governance/test_storage_ratchets.py`

**Interfaces:**
- Consumes: `paths.PLACES`, `paths.dir_of`, `paths.validate_config` (R34), `paths.old_env_in_use`, `paths.OLD_ENV`, `secrets.provider_file`, `secrets.json_path`, `index.rebuild`, `index.latest_sessions`, `store.replace(place="config")`, `store.create(place="state")` (копия в `state/backups`).
- Produces:
  - `h2t-ops paths list [--json]`. По строке на место: `id`, путь, `kind`, `sync`, существует ли и источник (`H2T_PATH_ROOT`/`H2T_PATH_VAULT`, `paths.yaml`, `default`). У `repo` фиксированного пути нет (`dir_of("repo")` бросает `ValueError`): путь `null` в `--json`, `—` в человеческом выводе, источник `cwd or --repo-root of each command`; не задан `lake`/`inbox`/`kb` — путь по умолчанию (`data/<место>`) с источником `default (not set)`. Отдельной строкой — заданные старые переменные (`paths.old_env_in_use()`) с пометкой «не читается».
  - `h2t-ops paths get <id>`. `paths get repo` → код 2, подсказка «у repo нет одного пути: это каталог, где вызвана команда». Принимает id места, `secret:<провайдер>` (путь `shared/<провайдер>.env`; `secret:google.token` → `local/google.token.json` этой машины, `secret:google.client` → `shared/google.client.json`) или `data:<имя>`. Печатает только путь.
  - `h2t-ops paths set <место> <путь>`. Только `lake`, `inbox`, `kb`; `vault` → код 2 и подсказка «vault задаётся `H2T_PATH_VAULT`, общей с POS». Проверка — `paths.validate_config(<новый документ>, source=paths.paths_yaml())` (R34): разбирается **новый** документ (старый может быть испорчен — так `paths set` его и чинит; запись в `config/` проходит и при испорченном файле, R17). Запись через ruamel с сохранением комментариев, `store.replace(place="config")`.
  - `h2t-ops index rebuild [--json]`, `h2t-ops index query --project <id> [--json]`.
  - Коды выхода: ошибка разбора аргументов — 2, неизвестное место — 2, пересечение мест — 3.

- [ ] **Step 1: Тесты (красные)** — по команде. В `paths set` пересечение не меняет файл (сравнить байты до и после). Комментарий пользователя в `paths.yaml` сохраняется. `test_paths_set_repairs_a_broken_file`: в `paths.yaml` синтаксическая ошибка, `paths set lake <путь>` переписывает файл, после чего `paths_config()` разбирает его. Если старый документ не разбирается вовсе, `set` пишет новый документ из одного ключа и печатает, что прежнее содержимое сохранено в `state/backups/paths.yaml.<метка>` (R14).

- [ ] **Step 2: Реализация.**

- [ ] **Step 3: Случаи песочницы** — `paths.set`, `paths.set.repair` (`setup` кладёт испорченный `paths.yaml`), `index.rebuild`.

- [ ] **Step 4: Красный контроль.** В `paths set` проверять старый документ (`paths.paths_config()`) вместо нового → `test_paths_set_repairs_a_broken_file` FAIL с `ConfigError … not valid YAML`. Вернуть.

- [ ] **Step 5: Ratchet, прогон** (`tests/cli tests/governance`), **commit** — `git add h2t_ops/core/paths_cli.py h2t_ops/cli.py tests/cli/test_paths_cli.py tests/governance/sandbox_cases.py tests/governance/test_storage_ratchets.py`; `feat(cli): h2t-ops paths and index (#548)`.


## Фаза D — `doctor` и миграция

### Task 20: `doctor` — проверка состояния хранения

**Files:**
- Create: `h2t_ops/setup/storage_doctor.py`
- Modify: `h2t_ops/cli.py:34` (`_doctor` печатает блок `storage:` после `secrets:`)
- Create: `tests/setup/test_storage_doctor.py`

**Interfaces:**
- Produces: `Finding(level: str, code: str, text: str)`, где `level` — `"error"|"warn"|"info"`; `check() -> list[Finding]`; `sync_status(place_id: str) -> tuple[str, str]`, где статус — `"confirmed"|"declared"|"unknown"`, а вторая строка — признак.

Проверки §7.4, по коду:

| code | level | Как проверяется |
|---|---|---|
| `secret-tracked` | error | `git -C <config> ls-files` → любой путь под `secrets/`; затем по каждому отслеживаемому файлу `git show :<путь>` → строки `KEY=непусто`, где `providers.provider_of_key(KEY)` не `None`. Печатаются путь и имя ключа |
| `local-in-sync` | error | для `secrets.local`, `state`, `logs`, `run/rollback` — `realpath`, затем вверх по дереву `.stfolder`/`.dropbox` или объявление в `paths.yaml: sync:` |
| `legacy-only` | warn | данные есть в `paths.legacy(...)`, а в новом месте нет: по одному на класс |
| `sync-conflict` | warn | `*.sync-conflict-*` в `records/`, `secrets/`, `config/` |
| `unknown-root-entry` | warn | имя в корне `~/.h2t`, которого нет среди мест, `layout.json` и старых каталогов 3.x внутри `~/.h2t` (`sessions`, `activity`, `evals`, `research`, `creative`, `config/secrets` — их называет `legacy-only`, не эта проверка) |
| `index-schema` | warn | версия схемы в `meta` ≠ `SCHEMA_VERSION` |
| `old-env-name` | warn | `paths.old_env_in_use()`; по каждому имени подсказка из `paths.OLD_ENV`: «значение перенесено в `paths.yaml` (lake)», «файл прочитан миграцией как источник секретов», «спул скопирован миграцией в `state/evals-spool.sqlite`» или «пакет её не читает — удалить» |
| `place-missing` | warn | место из `paths.yaml` или vault (`paths.vault()`) не существует |
| `place-unset` | info | `lake`, `inbox` не заданы |
| `config-backup` | warn | `*.yaml.bak*` в `config/`: копии 3.x, их место — `state/backups/` (R14) |
| `from-copies` | info | файлы `*.from-*` во **всех** местах, куда пишет миграция, рекурсивно: `secrets/shared`, `secrets/local`, `records/**` (в том числе `records/sessions/<машина>/<проект>/<stem>.md.from-dor`, Task 23), `state/**`, `data/**`, `config/` (§8: «сохраняются оба, и `doctor` их показывает»). Для `*.env.from-*` — путь, имена ключей и `sha256[:12]` значений (через `secrets.shared_env_values()`); для остальных — путь и `sha256[:12]` файла (байты секретов — через `secrets.read_secret_bytes`). Значения не печатаются |
| `perms` | error | только на POSIX: файл в `secrets/**` не `0600` или каталог не `0700`. На Windows проверка не выполняется и строки не печатает (проба 11.3) |

`sync_status` отвечает «подтверждено» (найден маркер), «объявлено» (только `paths.yaml`) или «неизвестно». Строки вывода:

```text
storage: layout 1, root ~/.h2t
storage: sync records = confirmed (.stfolder at ~/.h2t/records), secrets.shared = declared (syncthing), secrets.local = unknown
storage: ERROR local-in-sync: ~/.h2t/state lies inside a Syncthing folder (~/.h2t/.stfolder)
storage: warn legacy-only: sessions are only in ~/.dor/sessions — h2t-setup sync moves them
```

- [ ] **Step 1: Тесты (красные)** — по одному на `code`. Каждый строит минимальное состояние во временном `HOME`, включая git-репо `config` с отслеживаемым `secrets/x.env` и ключом `EXA_API_KEY=fake`. Тест `from-copies` — `test_from_copies_are_found_in_every_destination`: по одной копии в `secrets/shared`, `secrets/local`, `records/sessions/m/p/s.md.from-dor`, `state/cursors`, `data/research` → пять строк; красный контроль — искать только в `secrets/shared` → FAIL. Отдельный тест `test_report_never_prints_a_value`: значение `fake-SECRET-VALUE-123` из всех файлов не встречается в выводе.

- [ ] **Step 2: Реализация.** `doctor` по-прежнему выходит с 0 (#451).

- [ ] **Step 3: Красные контроли** — по одному на `code`, каждый с возвратом: ветку проверки в `check()` заменить на `pass` → её тест FAIL, текст падения прочитан. Для `test_report_never_prints_a_value`: в выводе `secret-tracked` печатать строку целиком вместо имени ключа → FAIL. Для `perms` контроль только на POSIX.

- [ ] **Step 4: Прогон** (`tests/setup tests/test_setup_doctor_checks.py tests/cli tests/governance`), `--check` (потолки не должны вырасти), **commit** — `git add h2t_ops/setup/storage_doctor.py h2t_ops/cli.py tests/setup/test_storage_doctor.py` (+ `tests/governance/test_storage_ratchets.py`, если потолки сдвинулись); `feat(doctor): storage checks — tracked secrets, sync placement, legacy data, conflicts (#548)`.

### Task 21: Движок миграции — команда `h2t-setup layout`, журнал, фазы, откат

**Files:**
- Create: `h2t_ops/setup/layout/__init__.py`, `journal.py`, `engine.py`, `rollback.py`
- Modify: `h2t_ops/setup/cli.py:21-106` — подкоманда `layout` (R13):
  - `h2t-setup layout migrate [--machine NAME] [--json]` и `h2t-setup layout rollback --sync-paused [--json]`;
  - в `main` ветка `layout` идёт **до** `_editable_stop`, `_consent_stop` и `sync.ensure_executor`: команда работает в том интерпретаторе, который её запустил, в том числе на editable-установке из чекаута; `MODES` остаётся `("sync", "update", "dev-sync")`, `layout` — отдельный подпарсер;
  - `--machine` и `--sync-paused` живут только на `layout`, у `sync`/`dev-sync` их нет.
- Подключение к `h2t-setup sync` в этой задаче **не** делается: фаз 22–23 ещё нет, и `sync` падал бы на каждой машине. Оно — Task 23 Step 4 (R24).
- Create: `tests/setup/layout/__init__.py` (пустой), `tests/setup/layout/test_engine.py`, `tests/setup/layout/test_cli.py`
- Modify: `tests/governance/test_single_doors.py` (`test_journal_remove_only_in_rollback`: `<=` → `==` — `rollback.py` теперь есть, R35)

**Interfaces:**
- Produces:

```python
# journal.py — rows as in plan R31, one JSON object per line
class Journal:
    def __init__(self, run_id: str): ...        # run/rollback/<run_id>/journal.jsonl; run_id = "layout1-<UTC>";
                                                 # dir via store.mkdir(place="run", mode=0o700) (R36)
    def created(self, path: Path, place: str, source: str, sha256: str,
                source_path: Path | None = None, rule: str | None = None) -> None
                                                 # source_path: copies, read by verify (R25);
                                                 # rule: "google-durable" for the transformed token (R37)
    def save_prev(self, prev: bytes) -> str      # writes run/rollback/<id>/prev/<n> via
                                                 # store.create(place="run", mode=0o600), fsynced, BEFORE the
                                                 # change; returns "prev/<n>" (n = next free number)
    def replaced(self, path: Path, place: str, prev: bytes, new_sha: str) -> str
                                                 # save_prev(prev), then row {op, path, place, prev_sha, new_sha,
                                                 # prev: "prev/<n>"}; returns the ref
    def removed(self, path: Path, place: str, prev: bytes) -> str
                                                 # the same: save_prev, row {op, path, place, prev_sha, prev}
    def prev_bytes(self, ref: str) -> bytes      # rollback reads the saved bytes back by the row's ref
    def winner(self, target: str, key: str, sha256: str) -> None       # Task 22; row {op, target, key, sha256}
    def baseline(self, pairs: set[tuple[str, str]]) -> None             # Task 22; one row {op, key, sha256} per pair
    def phase_done(self, phase: str) -> None
    def done_phases(self) -> set[str]
    def finished(self) -> bool                   # "markers" is in done_phases()
    def entries(self) -> list[dict]
    @staticmethod
    def latest() -> "Journal | None"             # only run/rollback/*/ that hold journal.jsonl: sync's
                                                 # <UTC>/ snapshots and claude-pending.json are not journals (R31);
                                                 # unfinished first, else the newest finished

# engine.py
PHASES: tuple[str, ...] = ("snapshot", "secrets", "sessions", "telegram", "evals", "activity",
                           "cursors", "registry", "data", "config_backups", "paths_yaml", "index",
                           "verify", "markers")

@dataclass
class PhaseContext:
    journal: Journal
    machine: str                                # --machine if given, else paths.machine_name()
    machine_explicit: bool                      # True only when --machine was given: phase_snapshot
                                                 # pins the name and checks the Claude setting only then
    report: object                              # setup.sync.Report: notes, failed
    baseline: set[tuple[str, str]] | None = None   # filled by phase_secrets (Task 22)

def quiet_sqlite_bytes(src: Path, *, read: Callable[[Path], bytes] = Path.read_bytes) -> bytes
    # R25: ConfigError if src-wal / src-journal / src-shm exists, or if (st_size, st_mtime_ns)
    # differs before and after read(src); the hint names the program to close and the re-run

def phase_snapshot(ctx: PhaseContext) -> None       # this task
def phase_config_backups(ctx: PhaseContext) -> None # this task
def phase_markers(ctx: PhaseContext) -> None        # this task
def _phase_funcs() -> dict[str, Callable[[PhaseContext], None]]
    # explicit table (R24): this task lists its three phases; Task 22 adds
    # secrets_phase.phase_secrets and verify.phase_verify; Task 23 adds phases.phase_*.
def migrate(report, *, machine: str | None = None,
            funcs: dict[str, Callable] | None = None) -> None   # funcs: test override
class PhaseFailed(H2TError):                    # a phase stops with a hint; engine -> report.failed
    ...
def put(journal: Journal, target: Path, data: bytes, *, place: str, source: str,
        from_name: str | None = None,
        source_path: Path | None = None,
        rule: str | None = None,
        keys: tuple[str, ...] = ()) -> Path      # create, or keep both on a different hash;
                                                 # keys: env key names, passed to store.create (R41)
                                                 # source_path/rule go into the created row (R25, R37)
def put_union(journal: Journal, target: Path, data: bytes, *, place: str) -> Path
                                                 # replace an existing file, journalled as `replaced`

# rollback.py
def rollback(*, sync_paused: bool) -> dict        # {"removed": [...], "restored": [...], "kept": [...]}; layout.json is one of them (R44)
```

Правила движка:

- `migrate` ничего не делает, если `layout.json` уже `1` и незавершённого журнала нет. Тогда в отчёт идёт `notes += ["layout 1: already"]`.
- Незавершённый журнал продолжается с первой фазы, которой нет в `done_phases()`.
- До первой записи `migrate` сверяет `PHASES` с таблицей функций (`funcs` или `_phase_funcs()`): имени без функции → `report.failed.append(("layout 1: <фаза> is not implemented", …))`, журнал не создаётся, ничего не пишется (R24).
- Каждая фаза — функция `phase_<имя>(ctx: PhaseContext)`. Ошибка фазы → `report.failed.append(("layout 1: <фаза>", <подсказка>))`, остальные фазы не идут, журнал остаётся незавершённым.
- Каждая строка журнала несёт `place` — откат передаёт его в `store.remove(..., place=row["place"], journal=True)`; классифицировать путь заново при откате не нужно.
- `put(...)` реализует правило «тот же хэш — тот же файл, другой — сохраняются оба»:
  - цели нет: `store.create`, затем `journal.created(...)`;
  - цель есть, хэш тот же: ничего;
  - хэш другой: `store.create(target.with_name(f"{target.name}.from-{source}"))`, затем `journal.created`; если и такой файл уже есть с тем же хэшем — ничего. Имя копии везде одно: `<имя целиком>.from-<источник>` (`google.token.json.from-dor`, `s.md.from-dor`).
- `put_union(...)` — для файла провайдера, который уже существует и которому миграция добавляет ключи (Task 22 п. 4): прежние байты сохраняет `journal.replaced(path, place, prev=<прежние байты>, new_sha=…)` — до записи: `save_prev` кладёт их в `run/rollback/<id>/prev/<n>` (0600, `store.create(place="run")`) и пишет в строку ссылку `prev`; только затем `store.replace`. Без этого откат не мог бы вернуть дополненный файл.
- Фаза `snapshot` проверяет свободное место (`shutil.disk_usage(paths.root().parent).free` больше суммы размеров источников × 2) и имя машины (§5, R4):
  - имя на этот прогон — `ctx.machine` (`--machine`, если задан, иначе `paths.machine_name()`); задан ли флаг — `ctx.machine_explicit`, его ставит `migrate(machine=…)` (`machine is not None`);
  - в `sessions.h2t` или `sessions.dor` есть подпапки, но нет подпапки с этим именем, и `ctx.machine_explicit` ложно → фаза падает с подсказкой `h2t-setup layout migrate --machine <имя>` и списком подпапок;
  - `ctx.machine_explicit` истинно: если `H2T_MACHINE_NAME` не закреплена — закрепить через `setup.legacy.ensure_machine_name(name=…)` (настройки Claude, ADR 0003); если закреплена другим значением — фаза падает с подсказкой «в настройках Claude закреплено `<имя>`; поправьте его там или запустите без `--machine`». Файла с именем машины нет.
  - `layout.json` здесь не трогается: его запись журналирует фаза `markers` обычными строками `created`/`replaced`, и откат возвращает его тем же общим правилом (R44).
- Фаза `config_backups` (R14): каждый `config/*.yaml.bak*` копируется `put` в `paths.backups_dir() / f"{name}.{YYYYmmdd-HHMMSS mtime}"`, затем под `store.migrating()` удаляется из `config/` (`store.remove(place="config")` разрешает это только для `*.yaml.bak*` во время миграции) с записью `journal.removed(path, place="config", prev=<байты копии>)` до удаления. У автора это `domains.yaml.bak`, `repo-mapping.yaml.bak` и созданный руками `domains.yaml.bak-desc`.
- Фаза `verify` — `verify.phase_verify`, Task 22 (R25).
- Фаза `markers` пишет `MOVED-TO.txt` под `store.migrating()` в каждый старый каталог, из которого что-то перенесено и который `store.classify` по-прежнему считает `legacy` (каталог, который стал объявленным местом — `~/.dor/lake/_cursors` при `lake: ~/.dor/lake`, R2, — классифицируется как `lake`, и маркер туда не пишется: это место пользователя) (текст: новое место и дата), и журналирует каждый как `created`. Для файловых записей (`~/.dor/secrets.env` и т.п.) маркер ложится в их каталог: `paths.legacy_roots()` считает этот каталог старым корнем (Task 3). Затем `layout.json = {"layout": 1, "machine": …, "migrated_at": …, "journal": run_id}` (R44): файла нет → `store.create(paths.layout_file(), …, place="layout")` и `journal.created(path, "layout", "migration", sha256)`; файл есть (прежняя раскладка) → `journal.replaced(path, "layout", prev=<его байты>, new_sha=…)` до записи, затем `store.replace(..., place="layout")`. Отдельного снимка `layout.json` нет. Место `layout` вида `file` уже есть с Task 3 (`dir_of("layout")` → `layout_file()`, `store._PACKAGE` его содержит), строка `- {id: layout, kind: file, class: root, sync: never}` — в спеке v6.
- Каталоги `run/rollback/layout1-*` с `journal.jsonl` завершённых миграций (`finished()`) старше 30 дней `migrate` удаляет при следующем запуске: `store.remove_tree(place="run")`. Незавершённые не трогаются никогда (§7.5). Каталоги без `journal.jsonl` (снимки `sync`, `setup/sync.py:263-266`) и `claude-pending.json` чистка не трогает (R31).
- `rollback` выполняется внутри `store.migrating()`: только так `remove(..., journal=True)` проходит для `MOVED-TO.txt` в старых каталогах.
- `rollback(sync_paused=False)` → `UsageError` с текстом §7.5 про паузу синхронизации. При `True`, по журналу в обратном порядке:
  - `created`: текущий хэш совпал → `store.remove(path, place=row["place"], journal=True)`, иначе путь идёт в `kept`;
  - `replaced`: текущий хэш равен `new_sha` → прежние байты `journal.prev_bytes(row["prev"])` возвращаются `store.replace`, путь идёт в `restored`; иначе — в `kept`;
  - `removed`: файла нет → прежние байты `journal.prev_bytes(row["prev"])` возвращаются `store.create`, путь — в `restored`;
  - `layout.json` отдельно не обрабатывается: его строка `created` (файла не было — откат его удаляет) или `replaced` (прежние байты возвращаются) идёт тем же правилом, что любой файл журнала (R44).

- [ ] **Step 1: Тесты движка (красные)**, на подставных фазах:
  - `test_phases_run_in_order_and_mark_done`.
  - `test_interrupted_migration_resumes_without_duplicates` (Review Focus 2): подставная фаза `sessions` падает с `KeyboardInterrupt` после первого `put`; второй `migrate` начинает с `sessions`, файлов `*.from-*` нет.
  - `test_put_keeps_both_on_different_hash`.
  - `test_rollback_removes_only_unchanged_journal_files`: файл из журнала изменён после миграции → остаётся; сессия, записанная после миграции, остаётся (§12).
  - `test_rollback_restores_a_file_the_migration_extended`: `put_union` дописал ключ в существующий `exa.env`; откат возвращает его прежние байты.
  - `test_rollback_returns_removed_config_backups`.
  - `test_rollback_requires_sync_paused`.
  - `test_rollback_restores_layout_json_through_the_journal` (R44): без прежнего `layout.json` откат его удаляет; с прежним (`{"layout": 0}`) — возвращает побайтно; в журнале для него строка `created` или `replaced`, отдельного снимка нет. Красный контроль: писать `layout.json` без строки журнала → FAIL.
  - `test_machine_name_ambiguity_stops`: подпапки `automata` и `macbook-pro-3`, hostname `other` → фаза падает и называет обе подпапки в подсказке.
  - `test_machine_flag_pins_the_name_once`: `--machine m` при незакреплённой переменной вызывает `ensure_machine_name(name="m")` (подставной); при закреплённой другой — фаза падает, настройки не меняются.
  - `test_rollback_dir_is_0700` (`skipif win32`).
  - `test_old_finished_rollback_dirs_are_pruned_after_30_days`: незавершённый журнал того же возраста остаётся; снимок `sync` `run/rollback/20260901T000000Z/` (без `journal.jsonl`) того же возраста и `run/rollback/claude-pending.json` тоже остаются (R31).
  - `test_latest_ignores_sync_snapshots`: в `run/rollback/` снимок `sync` новее журнала миграции → `Journal.latest()` возвращает журнал.
  - `test_missing_phase_function_fails_before_any_write`: `funcs` без `"secrets"` → `report.failed` называет `secrets`, `run/rollback/` не создан, `layout.json` нет (R24).
  - `test_engine_owned_phases_are_in_the_table`: `_phase_funcs()` содержит `snapshot`, `config_backups`, `markers` (Task 22–23 дописывают сюда свои имена).
  - `test_journal_rows_have_the_r31_shape`: `winner`, `baseline`, `created(source_path=…, rule=…)` дают строки с полями R31; `baseline` из двух пар — две строки.
  - `test_replaced_and_removed_persist_previous_bytes`: `replaced(prev=b"old")` и `removed(prev=b"gone")` возвращают разные ссылки `prev/<n>`, файлы с этими байтами лежат в каталоге отката (права 0600 — `skipif win32`), `prev_bytes(ref)` возвращает их; строки журнала несут `prev`.
  - `test_machine_explicit_is_carried`: `migrate(machine="m")` даёт фазам `machine_explicit=True`; `migrate()` при `paths.machine_name() == "m"` — `False`, и `ensure_machine_name` не вызывается.
  - `test_quiet_sqlite_bytes_stops_on_sidecar_and_on_change` (R25): `-wal` рядом → `ConfigError`; подставной `read`, который меняет `st_mtime_ns` источника (`os.utime`), → `ConfigError`; спокойный файл → его байты.
- `tests/setup/layout/test_cli.py`:
  - `test_layout_runs_on_an_editable_install`: `state.read()` подставлен с `editable="<чекаут>"`, `sync.ensure_executor` подставлен на `pytest.fail` → `h2t-setup layout migrate` выходит с 0 и вызывает `engine.migrate`;
  - `test_sync_still_refuses_editable`: тот же подставной `state` → `h2t-setup sync` выходит с кодом 3 и `reason: editable`.

- [ ] **Step 2: Реализация.**

- [ ] **Step 3: Красные контроли.** Каждый с возвратом: в `migrate` убрать проверку полноты таблицы → `test_missing_phase_function_fails_before_any_write` FAIL (журнал создан); в `Journal.latest()` убрать фильтр по `journal.jsonl` → `test_latest_ignores_sync_snapshots` FAIL; в `put` при другом хэше вызвать `store.replace` по самой цели → `test_put_keeps_both_on_different_hash` FAIL; в `rollback` удалять `created` без сверки хэша → `test_rollback_removes_only_unchanged_journal_files` FAIL; в `replaced` писать строку без `save_prev` → `test_replaced_and_removed_persist_previous_bytes` FAIL; в `quiet_sqlite_bytes` убрать сравнение `stat` → `test_quiet_sqlite_bytes_stops_on_sidecar_and_on_change` FAIL.

  Подключение к `sync` — Task 23 Step 4, не здесь (R24).

- [ ] **Step 4: Прогон** (`tests/setup tests/governance`), `--check`, **commit** — `git add h2t_ops/setup/layout/__init__.py h2t_ops/setup/layout/journal.py h2t_ops/setup/layout/engine.py h2t_ops/setup/layout/rollback.py h2t_ops/setup/cli.py tests/setup/layout/__init__.py tests/setup/layout/test_engine.py tests/setup/layout/test_cli.py tests/governance/test_single_doors.py` (+ `tests/governance/test_storage_ratchets.py`, если потолки сдвинулись); `feat(setup): h2t-setup layout — migration engine with a journal, resume and rollback (#548)`.

### Task 22: Фаза секретов и сверка

**Files:**
- Create: `h2t_ops/setup/layout/secrets_phase.py`, `h2t_ops/setup/layout/verify.py`
- Modify: `h2t_ops/setup/layout/engine.py` (`_phase_funcs()` += `secrets`, `verify`, R24)
- Create: `tests/setup/layout/test_secrets_phase.py`, `tests/setup/layout/test_verify.py`

**Interfaces:**
- Consumes: `secrets.migration_sources`, `secrets.shared_env_values`, `secrets.read_secret_bytes`, `secrets.notion_legacy_token`, `secrets.telegram_legacy_config`, `secrets.parse_env` (Task 6, R38 — других чтений секретов у миграции нет), `google_auth.durable_token` (Task 8, R37), `providers.*`, `engine.put`, `engine.put_union`, `engine.PhaseContext`, `engine.PhaseFailed`, `engine.quiet_sqlite_bytes` (R25), `Journal.winner/baseline/created/entries`, `paths.legacy`.
- Produces:
  - `secrets_phase.phase_secrets(ctx)`, `secrets_phase.ladder() -> list[tuple[str, Path]]`, `secrets_phase.evals_ladder(lad)`, `secrets_phase.translated_extras() -> list[tuple[str, dict[str, str]]]` (источники `notion-token` и `telegram-config` с ключами в новых именах), `secrets_phase.plan_env()`;
  - `verify.pairs(env)`, `verify.baseline() -> set[tuple[str, str]]`, `verify.verify_secrets(journal) -> list[str]`, `verify.verify_copies(journal) -> list[str]` (строки `created` с `source_path`: хэш источника и цели равны записанному), `verify.verify_transformed(journal) -> list[str]` (строки `created` с `rule: "google-durable"`, R37), `verify.phase_verify(ctx)` — все три сверки; непустой список → `PhaseFailed` с первыми пятью строками, фаза не отмечается сделанной (R25). Пустой список — сверка прошла.

Источники и старшинство (§8 п. 2, R6):

```python
# secrets_phase.py
def ladder() -> list[tuple[str, Path]]:
    """Senior first; the list and its dedup live in secrets.migration_sources (plan R38)."""
    return [(name, p) for name, p, _ in secrets.migration_sources()]


def evals_ladder(lad):
    """H2T_EVALS_*: ~/.dor/secrets.env first — the only file evals read in 3.x."""
    return sorted(lad, key=lambda kv: kv[0] != "dor")


def translated_extras() -> list[tuple[str, dict[str, str]]]:
    """Sources that are not env files, under their new key names, junior to every env file
    (§8 п. 2): the notion token file and the telegram config.json."""
    out: list[tuple[str, dict[str, str]]] = []
    tok = secrets.notion_legacy_token()
    if tok:
        out.append(("notion-token", {"NOTION_API_TOKEN": tok}))
    cfg = secrets.telegram_legacy_config()
    if cfg:
        vals = {k: str(cfg[s]) for k, s in (("TELEGRAM_API_ID", "api_id"), ("TELEGRAM_API_HASH", "api_hash"))
                if cfg.get(s) not in (None, "")}
        if vals:
            out.append(("telegram-config", vals))
    return out


def plan_env() -> tuple[dict[str, dict[str, str]], dict[str, dict[str, dict[str, str]]], list[Path]]:
    """-> (winners per target file, losers per target file per source, foreign files to copy)."""
    winners: dict[str, dict[str, str]] = {}
    losers: dict[str, dict[str, dict[str, str]]] = {}
    foreign: list[Path] = []
    existing = {name: vals for name, vals in secrets.shared_env_values().items() if name.endswith(".env")}
    srcs = secrets.migration_sources()
    lad = [(name, p) for name, p, _ in srcs]
    for src, path in lad:
        stem = path.stem
        if path.parent == paths.legacy("secrets.h2t") and stem != "secrets" \
                and not providers.is_package_provider(stem):
            foreign.append(path)
    def target_of(key):
        prov = providers.provider_of_key(key)
        return f"{prov}.env" if prov else "other.env"
    sources = {name: vals for name, _, vals in srcs}
    extras = translated_extras()
    sources.update(dict(extras))
    order_all = [*lad, *((src, None) for src, _ in extras)]   # extras are the most junior
    foreign_srcs = {src for src, p in lad if p in foreign}
    keys = {k for vals in sources.values() for k in vals}
    for key in sorted(keys):
        tgt = target_of(key)
        order = evals_ladder(order_all) if key.startswith("H2T_EVALS_") else order_all
        candidates = [(src, sources[src][key]) for src, _ in order if key in sources[src]]
        if tgt == "other.env":
            candidates = [c for c in candidates if c[0] not in foreign_srcs]
            if not candidates:
                continue
        if key in existing.get(tgt, {}):
            win_src, win_val = "existing", existing[tgt][key]
        else:
            win_src, win_val = candidates[0]
        winners.setdefault(tgt, {})[key] = win_val
        for src, val in candidates:
            if src != win_src and val != win_val:
                losers.setdefault(tgt, {}).setdefault(src, {})[key] = val
    return winners, losers, foreign
```

Дальше фаза делает следующее.

1. Notion. `secrets.notion_legacy_token()` даёт кандидата `NOTION_API_TOKEN` с источником `notion-token`, младшего всех env-файлов (`translated_extras`, код выше).
2. Telegram. `config.json` → `TELEGRAM_API_ID`, `TELEGRAM_API_HASH` в `telegram.env`, источник `telegram-config` (`translated_extras`; младше env-файлов, где эти ключи уже есть). Сессия → `local/telegram.session` — **байтовая** копия (§8 п. 6, R25): `data = engine.quiet_sqlite_bytes(src, read=secrets.read_secret_bytes)`, затем `put(..., source_path=src)`; рядом с `session.session` есть `-wal`/`-journal`/`-shm` или `stat` источника изменился за время чтения → `ConfigError` «Telegram держит сессию открытой: закройте его и запустите `h2t-setup layout migrate` снова», ничего не записано. auth-state → `local/telegram.auth-state.json` — байтовая копия через `put(..., source_path=…)`; права 0600. Старая сессия идёт через `put` **всегда**, и когда `local/telegram.session` уже есть (его мог создать адаптер Task 9, а Telethon — изменить): байты равны — ничего; различаются — `local/telegram.session.from-telegram` рядом, оба сохранены (§8, правило `put`), `doctor` покажет копию (`from-copies`, Task 20).
3. Google (R19, R37). Клиент → `shared/google.client.json`: `google.store/credentials.json` > `google.gmail/credentials.json` > `google.dor`; проигравшие — `google.client.json.from-<источник>`; байтовые копии через `put(..., source_path=…)`. Токен → **`local/google.token.json` этой машины**: `google.store/tokens.json` > `google.gmail/token.json` той же машины — **преобразованная** копия: `put(journal, target, json.dumps(durable_token(json.loads(secrets.read_secret_bytes(src)))).encode(), place="secrets.local", source=<источник>, source_path=src, rule="google-durable")` — один вызов; строку `created` с `rule` и `source_path` пишет сам `put`, отдельной строки журнала нет; проигравший — `google.token.json.from-<источник>` тем же преобразованием. Access-токен и `expiry` в `local` не попадают (§4). Права 0600. Конфликта между машинами нет: каждая переносит свой токен в свой `local`, который не синхронизируется.
4. **До любой записи** фаза вычисляет `plan_env()` и пишет в журнал `journal.winner(target, key, sha256(значение))` по каждому победителю и `journal.baseline(baseline())` — пары `(ключ, sha256)`, значения туда не попадают. Затем победители пишутся в файл провайдера. Если файла нет, `put` создаёт его. Если файл есть, но в нём не хватает ключей (новые ключи из старых мест), он пишется через `put_union` (Task 21): прежние байты сохраняются в каталоге отката, строка `replaced` — в журнал. Существующие значения не трогаются: они старшие.
5. Проигравшие пишутся в `<цель>.from-<источник>` через `put`.
6. Чужие файлы копируются `put(..., source_path=…)` под своим именем; байты — `secrets.read_secret_bytes`.

Сверка (`verify.py`, фаза `verify`, §8 п. 6):

```python
def pairs(env: dict[str, str]) -> set[tuple[str, str]]:
    return {(k, hashlib.sha256(v.encode()).hexdigest()) for k, v in env.items()}


def _new_pairs() -> set[tuple[str, str]]:
    out: set[tuple[str, str]] = set()
    for vals in secrets.shared_env_values().values():    # {} when there is no shared dir
        out |= pairs(vals)
    return out


def baseline() -> set[tuple[str, str]]:
    """Taken BEFORE any write: every old source under translated names, plus existing new
    files and their .from- copies."""
    out: set[tuple[str, str]] = set()
    for _, _, vals in secrets.migration_sources():
        out |= pairs(vals)
    for _, vals in secrets_phase.translated_extras():  # notion token, telegram api_id/hash
        out |= pairs(vals)
    return out | _new_pairs()


def verify_secrets(journal) -> list[str]:
    """Both sets come from the journal written before any write — never recomputed from the
    files the migration has just written (plan_env() would see them as "existing" winners and
    compare them with themselves). A new user has no secrets: both sets are empty."""
    before = {(r["key"], r["sha256"]) for r in journal.entries() if r["op"] == "baseline"}
    after = _new_pairs()
    problems = [f"lost {k} (sha256 {h[:12]})" for k, h in sorted(before - after)]
    problems += [f"appeared {k} (sha256 {h[:12]})" for k, h in sorted(after - before)]
    shared = secrets.shared_env_values()
    for r in (r for r in journal.entries() if r["op"] == "winner"):
        if r["target"] not in shared:
            problems.append(f"{r['target']}: missing, {r['key']} expected")
            continue
        got = shared[r["target"]]
        if hashlib.sha256(got.get(r["key"], "").encode()).hexdigest() != r["sha256"]:
            problems.append(f"{r['target']}: {r['key']} is not the senior value")
    return problems


def _sha(path: Path, secret: bool) -> str | None:
    if not path.is_file():
        return None
    data = secrets.read_secret_bytes(path) if secret else path.read_bytes()
    return hashlib.sha256(data).hexdigest()


def verify_copies(journal) -> list[str]:
    """Byte copies (Google client, telegram session and auth-state, evals json and spool,
    cursors, registry, data, foreign env files): the journal row's hash, the target's and the
    source's agree. Secret files are read through core.secrets (R38)."""
    problems = []
    for r in (r for r in journal.entries()
              if r["op"] == "created" and r.get("source_path") and not r.get("rule")):
        secret = r["place"] in ("secrets.shared", "secrets.local")
        for label, p in (("copy", Path(r["path"])), ("source", Path(r["source_path"]))):
            if _sha(p, secret) != r["sha256"]:
                problems.append(f"{label} {p} does not match its journal hash")
    return problems


_DROPPED = ("token", "access_token", "expiry", "expiry_date", "id_token")


def _field_hashes(d: dict) -> dict[str, str]:
    return {k: hashlib.sha256(json.dumps(v, sort_keys=True).encode()).hexdigest() for k, v in d.items()}


def verify_transformed(journal) -> list[str]:
    """Transformed copies by rule (§8 п. 6, R37): the Google token keeps every durable field
    of its source, by hash, and none of the dropped ones."""
    problems = []
    for r in (r for r in journal.entries() if r["op"] == "created" and r.get("rule") == "google-durable"):
        src = google_auth.durable_token(json.loads(secrets.read_secret_bytes(Path(r["source_path"]))))
        dst = json.loads(secrets.read_secret_bytes(Path(r["path"])))
        if any(k in dst for k in _DROPPED):
            problems.append(f"{r['path']}: holds a short-lived field")
        if _field_hashes(src) != _field_hashes({k: dst[k] for k in src if k in dst}):
            problems.append(f"{r['path']}: a durable field differs from {r['source_path']}")
    return problems


def phase_verify(ctx) -> None:
    problems = verify_secrets(ctx.journal) + verify_copies(ctx.journal) + verify_transformed(ctx.journal)
    if problems:
        raise PhaseFailed("; ".join(problems[:5]),
                          hint="nothing was removed; see run/rollback/<id>/journal.jsonl")
```

`PhaseFailed(H2TError)` — исключение `engine.py` (Task 21): движок ловит его, кладёт `("layout 1: <фаза>", hint)` в `report.failed` и не отмечает фазу. В отчёт идут имена ключей и `sha256[:12]`, не значения.

`baseline()` и победители пишутся в журнал фазой `secrets` до первой записи; при продолжении прерванной миграции они берутся только из журнала, повторно не снимаются — иначе в базу попали бы наполовину перенесённые файлы. Байтовые копии (клиент Google, сессия и auth-state Telegram, чужие `.env`) пишутся `put(..., source_path=<источник>)` и сверяются `verify_copies` по `sha256`; токен Google — преобразованная копия, `verify_transformed` (R37). `secrets_phase.py` и `verify.py` не открывают файлов секретов сами: только читатели Task 6 (R38).

- [ ] **Step 1: Тесты (красные).**
  - `test_full_precedence_order`: один и тот же ключ `MEETGEEK_API_KEY` в семи источниках с разными значениями; победитель — по порядку §8 п. 2; шесть проигравших — в `meetgeek.env.from-*`.
  - `test_evals_prefers_dor_secrets_env`.
  - `test_existing_new_file_wins_on_rerun`: пользователь поменял ключ в новом файле, в старых источниках этого значения нет. Повторный `migrate` значение не трогает, а сверка проходит.
  - `test_secrets_file_override_is_one_more_source`: при заданном `H2T_SECRETS_FILE` остальные места всё равно обойдены; если переменная указывает на файл лестницы, он учитывается один раз.
  - `test_unknown_keys_go_to_other_env`.
  - `test_foreign_env_is_copied_whole_and_feeds_provider_keys` (R6).
  - `test_telegram_and_notion_are_translated`.
  - `test_verify_catches_a_lost_value`: порча — после фазы удалить строку из `exa.env`; `verify_secrets` возвращает `lost EXA_API_KEY`.
  - `test_verify_catches_a_junior_value_written`: порча — после фазы заменить значение `MEETGEEK_API_KEY` в `meetgeek.env` на значение младшего источника (оно есть в базе, поэтому `lost`/`appeared` молчат); `verify_secrets` возвращает `is not the senior value`. Версия, которая пересчитывает `plan_env()` по уже записанным файлам, видит в них «существующее» значение, сравнивает файл сам с собой и проблемы не находит — на ней этот тест красный.
  - `test_resume_takes_the_baseline_from_the_journal`: прерывание после первого `put`, затем повторный `migrate`; база в журнале одна и снята до записи.
  - `test_google_token_goes_to_local_per_machine` (R19): `tokens.json` → `local/google.token.json`, `credentials.json` → `shared/google.client.json`; в `shared` токена нет.
  - `test_google_token_keeps_durable_fields_only` (R37): источник в обёртке `normal` с `token`, `expiry_date`, `scope` строкой → в `local/google.token.json` есть `refresh_token`, `client_id`, `client_secret`, `token_uri`, `scopes` списком, нет `token`/`expiry`/`expiry_date`; `verify_transformed` → `[]`. Порча: дописать в цель `"token": "fake-access"` → `holds a short-lived field`; заменить `refresh_token` → `a durable field differs`.
  - `test_google_client_byte_copy_verified_by_hash`: после фазы дописать байт в `shared/google.client.json` → `verify_copies` возвращает строку про `copy …google.client.json`.
  - `test_telegram_session_is_a_byte_copy_verified_by_hash`: копия побайтно равна источнику, строка журнала с `source_path`; дописать байт в копию → `verify_copies` ловит.
  - `test_existing_local_session_keeps_both`: `local/telegram.session` уже есть с другими байтами (копия Task 9, изменённая Telethon) → после фазы он нетронут и рядом `telegram.session.from-telegram` с байтами старой сессии; с теми же байтами — ничего нового. Красный контроль: вернуть «есть — пропустить» → FAIL (нет `.from-telegram`).
  - `test_telegram_session_with_a_sidecar_stops` (R25): рядом с `session.session` лежит `session.session-journal` → `ConfigError` с `close Telegram`/«закройте Telegram», `local/telegram.session` не создан, журнал без `created` для сессии.
  - `test_telegram_session_changed_during_copy_stops` (R25): подставной `read`, который после чтения дописывает байт в источник (или меняет `st_mtime_ns` через `os.utime`) → `ConfigError`, ничего не записано.
  - `test_migration_reads_secrets_only_through_core_secrets` (R38): прогон фазы под `Recorder` Task 7 c `secret_dirs` песочницы → нарушений нет (чтения идут через `secrets.py`).
  - `test_empty_home_verifies_clean` (`tests/setup/layout/test_verify.py`): `HOME` без старых мест и без `secrets/` → `verify_secrets`, `verify_copies`, `verify_transformed` возвращают `[]`, исключения нет (каталога `shared` нет).
  - `test_notion_token_is_the_most_junior` и `test_telegram_config_feeds_telegram_env`: проверяют `plan_env()` с `translated_extras` (§8 п. 2).
  - `test_no_value_in_journal_or_report`: значение `fake-SECRET-xyz` не встречается в `journal.jsonl`, в `report.as_dict()` и в `logs/writes.jsonl`.

- [ ] **Step 2: Реализация.** `_phase_funcs()` в `engine.py` получает `"secrets": secrets_phase.phase_secrets` и `"verify": verify.phase_verify`.

- [ ] **Step 3: Красный контроль сверки.** Каждый с возвратом:
  - в `verify_secrets` удалить строку `problems = [f"lost …"]` → `test_verify_catches_a_lost_value` FAIL;
  - цикл по строкам `winner` заменить пересчётом `plan_env()` по записанным файлам → `test_verify_catches_a_junior_value_written` FAIL;
  - в `secrets.shared_env_values` убрать `if not shared.is_dir(): return {}` → `test_empty_home_verifies_clean` FAIL с `FileNotFoundError`;
  - убрать `sources.update(dict(extras))` → `test_notion_token_is_the_most_junior` FAIL;
  - токен Google копировать байтами (`put(data=raw, source_path=src)`) → `test_google_token_keeps_durable_fields_only` FAIL на `token`;
  - в `quiet_sqlite_bytes` убрать проверку боковых файлов → `test_telegram_session_with_a_sidecar_stops` FAIL; убрать сравнение `stat` → `test_telegram_session_changed_during_copy_stops` FAIL;
  - в `verify_copies` читать байты `p.read_bytes()` вместо `secrets.read_secret_bytes` → `test_migration_reads_secrets_only_through_core_secrets` FAIL.

- [ ] **Step 4: Прогон** (`tests/setup/layout tests/governance`), `--check` (новые модули не добавляют `legacy_roots`/`path_env`: ключи `LEGACY` с точкой и docstring не считаются, имена старых переменных не пишутся — R21, R22), **commit** — `git add h2t_ops/setup/layout/secrets_phase.py h2t_ops/setup/layout/verify.py h2t_ops/setup/layout/engine.py tests/setup/layout/test_secrets_phase.py tests/setup/layout/test_verify.py` (+ `tests/governance/test_storage_ratchets.py`, если потолки сдвинулись); `feat(setup): layout 1 secrets phase with full precedence and value-set verification (#548)`.

### Task 23: Остальные фазы `layout 1`

**Files:**
- Create: `h2t_ops/setup/layout/phases.py`
- Modify: `h2t_ops/setup/layout/engine.py` (`_phase_funcs()` += девять фаз ниже; таблица полна, R24)
- Modify: `h2t_ops/setup/sync.py:879-951` (`run`: после шага 7, если `cli_ok`, вызов `layout.engine.migrate(report, machine=None)`; `dev_sync` миграцию **не** вызывает — на машинах автора её запускают явно `h2t-setup layout migrate`). Перенесено из Task 21 (R24)
- Create: `tests/setup/layout/test_phases.py`
- Modify: `tests/setup/test_sync_converges.py` (тест подключения, Step 4)

**Interfaces:**
- Consumes: `engine.put`, `engine.PhaseContext`, `engine.PhaseFailed`, `session_record.render/parse`, `index.rebuild`, `engine.quiet_sqlite_bytes` (R25), `secrets.migration_sources` (R38), `secrets_phase.evals_ladder`, `paths.old_env_by_use("lake")`, `paths.old_env_by_use("evals-spool-source")` (R22), `paths.*`.
- Produces: `phase_sessions`, `phase_telegram` (только `dialogs_bootstrapped` → `state/telegram/`; сессия и auth-state ушли в фазу секретов), `phase_evals`, `phase_activity`, `phase_cursors`, `phase_registry`, `phase_data`, `phase_paths_yaml`, `phase_index`, `PYTEST_SESSION_IDS`, `PYTEST_PROJECTS`. `phase_config_backups` — в `engine.py` (Task 21, R24). Байтовые копии фаз пишутся `put(..., source_path=<источник>)`: их сверяет `verify.phase_verify` (Task 22).

| Фаза | Источник | Куда | Проверка |
|---|---|---|---|
| `sessions` | `legacy("sessions.h2t")/<машина>/**/*.md`, `legacy("sessions.dor")/<машина>/**/*.md`; других машин — **нет** | `records/sessions/<машина>/<проект>/<stem>.md` | тело после frontmatter побайтно равно источнику; `migrated_from: <путь>@<sha256>` |
| `telegram` | `legacy("telegram")/dialogs_bootstrapped` | `state/telegram/dialogs_bootstrapped` | хэш |
| `evals` | `legacy("evals")/<скилл>/sessions/*.json`; спул — порядок 3.x (`eval/session.py:299-303`, где `self._env` = окружение поверх файла секретов): `paths.old_env_by_use("evals-spool-source")` (окружение) → тот же ключ в значениях `secrets.migration_sources()` в порядке `secrets_phase.evals_ladder` (`~/.dor/secrets.env` первым; файлы читает только `secrets.py`, R38; имя ключа берётся как `[n for n, u in paths.OLD_ENV.items() if u == "evals-spool-source"]`, литерал не пишется, R22) → `legacy("evals")/.h2t_evals_spool.db`; **байтовая** копия (§8 п. 6, R25): `data = engine.quiet_sqlite_bytes(src)` — рядом `-wal`/`-journal`/`-shm` или `stat` изменился за чтение → `ConfigError` «закройте процесс evals (сессию Claude с включёнными evals) и запустите `h2t-setup layout migrate` снова»; затем `put(..., place="state", source_path=src)` | `records/evals/<машина>/<скилл>/<файл>`; `state/evals-spool.sqlite` | хэш для json и для спула (`verify_copies`) |
| `activity` | `legacy("activity")/spool.jsonl` **без строк тестов** (R15): строка пропускается, если её `session_id` в `PYTEST_SESSION_IDS` или `project` в `PYTEST_PROJECTS` | `records/activity/<машина>.jsonl` | копия равна источнику без пропущенных строк (сверка по строкам); число пропущенных — в отчёт (`notes`) |
| `cursors` | `legacy("lake.dor")/_cursors/{granola,meetgeek}.json` | `state/cursors/<провайдер>.json` | хэш |
| `registry` | `legacy("registry.dor")` | `records/imports/dor-registry.jsonl` | хэш |
| `data` | `legacy("research")/**`, `legacy("creative")/**` (R9) | `data/research/**`, `data/creative/profiles/**` | хэш |
| `paths_yaml` | — (R2) | `config/paths.yaml`, только если его нет: `lake` — значение из `paths.old_env_by_use("lake")`, если задано, иначе `legacy("lake.dor")`, если существует; `inbox` — `legacy("downloads")`, если существует. `vault` не пишется (R12) | `paths_config()` разбирает файл без ошибки |
| `index` | — | `index.rebuild()` | число сессий в индексе = числу всех md под `records/sessions/*/*/`, которые индекс берёт (без `*.from-*`; `*.sync-conflict-*` считаются) и которые разбираются, а `problems` — остальным. Так в счёт входят и записи Task 13 этой машины, и md других машин, уже приехавшие синхронизацией |

Frontmatter перенесённой сессии собирается так.

1. `session_id` = `stem`; `project` = имя каталога; `machine` = `ctx.machine`.
2. Из `latest.json` того же каталога, только если его `session_id == stem`, берутся `summary_short` → `done`, `next_actions` → `remains`, `updated_at`, `artifacts`.
3. Из заголовка md (`**Date:**`, `**Domain:**`, `**Project:**`) берутся `date`, `domain`. При расхождении с каталогом `project` берётся из каталога.
4. Если `updated_at` нет, он равен `date` + `T00:00:00Z`, а если нет и даты — mtime файла.

Один и тот же md может лежать и в `~/.h2t/sessions`, и в `~/.dor/sessions`. Сравнивать надо **тела**, а не собранные файлы: во frontmatter стоит `migrated_from: <путь>@<sha>` с разными путями, и хэши собранных файлов различались бы всегда. Поэтому `phase_sessions` перед `put` сравнивает `sha256` тела источника с телом уже перенесённого файла (`session_record.parse(...)[1]`): тела равны — это тот же файл, ничего не пишется; разные — `put` создаёт `<stem>.md.from-dor` (имя по общему правилу Task 21; индекс пропускает `*.from-*`), и `doctor` показывает его как `from-copies`.

Списки строк тестов для фазы `activity` (R15) зашиты в `phases.py` с комментарием-ссылкой на файлы тестов, откуда они взяты:

```python
# The suite's fixture values that leaked into the author's spool (#441, conftest.py docstring).
# tests/core/test_session_identity_roundtrip.py, tests/core/test_handoff_identity_from_cwd.py
PYTEST_SESSION_IDS = frozenset({
    "personal-os-h2t-skills-topic-2026-08-22", "personal-os-h2t-skills-new-2026-08-22",
    "personal-os-dor-core-topic-2026-08-22", "dev-docgraph-topic-2026-08-22",
    "some-session-2026-08-23",
})
PYTEST_PROJECTS = frozenset({"explicit-id", "derived-id", "unmapped-checkout"})
```

Замер на маке автора 2026-10-18: из 1445 строк `~/.h2t/activity/spool.jsonl` под эти правила попадают 1279.

- [ ] **Step 1: Тесты (красные)** — по фазе. Сквозной `test_layout1_end_to_end_on_a_3x_home`:
  - фикстура строит `HOME` с раскладкой 3.x по описанию §1: две машины в `~/.dor/sessions`, одна в `~/.h2t/sessions`, Telegram, Google, evals, activity, курсоры, registry, research, creative;
  - `migrate` с `machine="macbook-pro-3"`;
  - сессии `automata` не скопированы;
  - `layout.json == 1`;
  - `doctor` без `error`;
  - `MOVED-TO.txt` лежит в каждом старом каталоге с данными;
  - старые файлы побайтно целы: хэши до и после совпадают;
  - откат удаляет всё созданное, и хэши старых файлов снова совпадают.

  По фазам дополнительно: `test_activity_drops_pytest_rows_and_counts_them` (5 настоящих строк и 3 строки с id из `PYTEST_SESSION_IDS` → в копии 5, в `notes` «3 test rows skipped»); `test_same_body_in_both_session_dirs_is_one_file` (тела равны, пути разные → один md, без `.from-dor`); `test_paths_yaml_takes_lake_from_old_variable_and_never_writes_vault`.

  Контрольный тест (§12) — `test_old_dirs_renamed_connectors_still_work`. После миграции старые каталоги переименовываются в `*.gone`. Затем `secrets.get` для каждого провайдера, `google_auth.resolve_google_credentials` (на подставном рефреше) и `TelegramClientAdapter()._load_config()` по-прежнему находят значения.

  Ещё: `test_evals_spool_path_from_the_old_secrets_file` (`H2T_EVALS_SPOOL=<путь>` только в `~/.dor/secrets.env`, переменной окружения нет → копируется спул по этому пути, R22); `test_index_count_includes_sessions_already_in_records` (md Task 13 этой машины и md другой машины лежат в `records/sessions` до миграции → проверка фазы `index` проходит); `test_empty_home_migrates_to_layout_1` (пустой `HOME`: `layout.json` создан, нет `~/.dor`, нет `~/.config/<программа>`, `report.failed == []` — сценарий §12 «новый пользователь», который Task 26 повторяет вживую); `test_every_phase_has_a_function` (`set(_phase_funcs()) == set(PHASES)`); `test_evals_spool_is_a_byte_copy_verified_by_hash` (копия побайтно равна источнику, строка журнала с `source_path`; байт, дописанный в копию, ловит `verify_copies`); `test_evals_spool_with_a_sidecar_stops` (рядом `.h2t_evals_spool.db-wal` → `ConfigError`, `state/evals-spool.sqlite` не создан); `test_evals_spool_changed_during_copy_stops` (`stat` источника меняется между двумя снимками → `ConfigError`, ничего не записано).

- [ ] **Step 2: Реализация.** `_phase_funcs()` получает девять фаз этой задачи.

- [ ] **Step 3: Красные контроли.** Каждый с возвратом: в фазе `activity` не фильтровать строки → `test_activity_drops_pytest_rows_and_counts_them` FAIL; в `phase_sessions` сравнивать хэши собранных файлов вместо тел → `test_same_body_in_both_session_dirs_is_one_file` FAIL (появился `.from-dor`); в фазе `index` сравнивать с числом md фазы `sessions` → `test_index_count_includes_sessions_already_in_records` FAIL; спул брать только из окружения → `test_evals_spool_path_from_the_old_secrets_file` FAIL; в фазе `evals` не звать `quiet_sqlite_bytes` (читать `src.read_bytes()`) → `test_evals_spool_with_a_sidecar_stops` и `test_evals_spool_changed_during_copy_stops` FAIL.

- [ ] **Step 4: Подключение к `sync`** (перенесено из Task 21, R24). В `sync.run` после шага 7: если `cli_ok`, вызвать `layout.engine.migrate(report, machine=None)`; если фаза имени машины остановилась, подсказка в отчёте — `h2t-setup layout migrate --machine <имя>`. Тест в `tests/setup/test_sync_converges.py`: прогон `sync.run` на подставных `uv`/`claude` создаёт `layout.json`, а повторный прогон оставляет `notes` с `layout 1: already`. Красный контроль: убрать вызов → тест FAIL (`layout.json` нет). Вернуть.

- [ ] **Step 5: Прогон** (`tests/setup tests/governance tests/lifecycle`), `--check`, **commit** — `git add h2t_ops/setup/layout/phases.py h2t_ops/setup/layout/engine.py h2t_ops/setup/sync.py tests/setup/layout/test_phases.py tests/setup/test_sync_converges.py` (+ `tests/governance/test_storage_ratchets.py`, если потолки сдвинулись); `feat(setup): layout 1 phases — sessions, telegram, evals, activity, cursors, registry, data; sync runs the migration (#548)`.

### Task 24: Сторожа на ноль

**Files:**
- Modify: `tests/governance/test_storage_ratchets.py` (все потолки 0)
- Modify: `tests/governance/sandbox_cases.py` (полнота)
- Create: `tests/governance/test_sandbox_covers_every_writer.py` (читает `tests/governance/writers_baseline.txt` из Task 2 и `build_sandbox`/`run_case` из Task 7)
- Modify: `tests/release/test_ratchets.py:17` (`AUTHOR_LITERAL_CEILING = 7` → 0) и файлы, где лежат эти семь литералов (§7.3, строка «литералы автора 7 → 0»)

**Interfaces:** —

- [ ] **Step 1: Потолки.** `.venv/bin/python scripts/storage_map.py`. Каждая строка, которая ещё не равна 0: найти по `hits(...)` и перевести на `paths`/`store`/`secrets`. Места, которые на 09223a11 не попадали ни в одну задачу 8–19, теперь распределены (Task 10 — лестница секретов `setup/legacy.py`; Task 18 — `deploy/profiles.py`, `deploy/registry.py`, `gather/user.py`, `rule_scan.py`, `harness_claude.py`, пути `setup/legacy.py`); `json.dump` в stdout (`gather/runner.py:52`) и `tempfile.gettempdir()` шаблон `writes` больше не считает; `H2T_DEV_ROOT` (`tools/docs/common.py`, `tools/docs/docs_init.py`, `tools/docs/lint.py`, `lifecycle/project_audit_report.py`, `lifecycle/project_audit_scan.py`) шаблон `path_env` не считает по R16. Если остаток всё же есть, это пропуск одной из задач — довести его там, а не здесь. Docstring и ключи `LEGACY` с точкой (`"secrets.dor"`) сканер с Task 2 не считает (R21), имена старых переменных вне `paths.py` не пишутся (R22) — поэтому законный код плана (`secrets.legacy_sources`, `_legacy_json`, `ladder`, фазы миграции, `evals_env`) ноль не держит. Если ложное срабатывание всё же осталось, это повод сузить шаблон в `storage_map.py` с тестом-контролем на ложное срабатывание и на прежнее настоящее, а не перефразировать текст, чтобы сканер его не видел. Добавлять файлы в `ALLOWED` нельзя.

- [ ] **Step 2: Литералы автора → 0.** `.venv/bin/pytest tests/release/test_ratchets.py -q` с потолком 0 печатает семь мест (`exec_map.literal_hits`). Каждое — значение автора в коде (id базы Notion, часовой пояс и т.п. из `AUTHOR_LITERALS`): перенести в конфиг пользователя (`config/` или ключ в `secrets`) с подсказкой при отсутствии, либо удалить, если это мёртвый код. Вписать `AUTHOR_LITERAL_CEILING = 0`. Красный контроль: вернуть один литерал → FAIL. Вернуть.

- [ ] **Step 3: Полнота песочницы (красный).** Список модулей-писателей — `tests/governance/writers_baseline.txt`: выход сканера (`storage_map.py --files writes`) в Task 2, 46 модулей на 2ddd6db6, а не литерал, набранный здесь (R27). Тест прогоняет **каждый** случай `CASES` в своей песочнице и объединяет `Recorder.writers` — модули `h2t_ops`, которые реально стояли в стеке записи. Каждый модуль базы должен в этом объединении быть: случай с подходящим именем, который до модуля не дошёл, не засчитывается. Запуск сразу красный, если какой-то модуль ни один случай не исполнил; дописать недостающие случаи в задаче, которой модуль принадлежит, или здесь.

```python
# tests/governance/test_sandbox_covers_every_writer.py
"""Every module that wrote to disk before 4.0 is exercised by a sandbox case (#548 §7.3, R27).

Observed, not named: a case counts for a module only if the module was on the stack of a
write while the case ran."""
from pathlib import Path

import pytest

from tests.governance.sandbox_cases import CASES
from tests.governance.test_sandbox import build_sandbox, run_case

BASELINE = sorted(Path(__file__).with_name("writers_baseline.txt").read_text(encoding="utf-8").split())


@pytest.fixture(scope="module")
def observed(tmp_path_factory):
    seen: set[str] = set()
    for i, case in enumerate(CASES):
        with pytest.MonkeyPatch.context() as mp, \
                build_sandbox(tmp_path_factory.mktemp(f"case{i}"), mp) as sb:
            run_case(case, sb, mp)
            seen |= sb.recorder.writers
    return seen


def test_baseline_is_the_scanner_output():
    assert len(BASELINE) == 46 and all(m.endswith(".py") for m in BASELINE)


@pytest.mark.parametrize("module", BASELINE)
def test_every_writer_is_exercised(module, observed):
    assert module in observed, f"{module}: no sandbox case reached a write in it"
```

`test_baseline_is_the_scanner_output` сверяет файл с числом замера Task 2 (46), а не сам с собой: если файл перезаписали после переводов (а сканер к Task 24 видит 0 писателей), он станет короче и тест покраснеет.

- [ ] **Step 4: Полный прогон.** `.venv/bin/pytest tests/ -q`, `.venv/bin/pytest lib/ -q`, `uvx ruff@0.16.4 check plugins/ lib/ h2t_ops/ tests/ scripts/`, `.venv/bin/pytest -m slow tests/lifecycle/index -q`. Всё зелёное. Строки `ERROR: the suite wrote into the real home` нет.

- [ ] **Step 5: Вопрос «что сторож не видит»** (verification.md). Четыре `grep` по всему дереву, не только по `h2t_ops/`:
  - `grep -rn "Path.home()\|expanduser" plugins/ lib/ scripts/ --include=*.py`;
  - `grep -rn "\.dor/\|\.config/" plugins/ --include=*.md`;
  - `grep -rn "open(" h2t_ops/ --include=*.py | grep -v "store.py\|secrets.py"`.

  - `grep -rn "\.dor/\|\.config/\|H2T_[A-Z_]*\(ROOT\|SPOOL\|FILE\)" h2t_ops/ --include=*.py` — то, что сканер теперь не считает по R21 (docstring): устаревшие пути в прозе кода.

  Найденное разобрать: исправить или записать причину в отчёт задачи 25.

- [ ] **Step 6: Commit** — `git add tests/governance/test_storage_ratchets.py tests/governance/sandbox_cases.py tests/governance/test_sandbox_covers_every_writer.py tests/release/test_ratchets.py` и каждый файл, правленый в Step 1–2 (по имени из `git status --short`); `test(governance): ratchets at zero, author literals at zero, sandbox covers every writer (#548)`.

## Фаза R — документация, перенос, выпуск

### Task 25: Документация и тексты issues в POS и rejuve

Задача автономная: она пишет только файлы этого репо. Заведение issues в чужих репо и результат живой проверки POS — Task 26 **[владелец]** (R26).

**Files:**
- Modify: `README.md:119-124` (раздел «Known Limitations» → «Где хранятся данные»: дерево §3, `paths.yaml`, `h2t-setup sync`, откат)
- Modify: `CHANGELOG.md:85-88` (раздел 4.0.0: строка про #548 → описание раскладки и миграции `h2t-setup layout migrate`; строка про `drive download` по умолчанию в `inbox`; про `latest.json`; **старые переменные путей больше не читаются** — список из `paths.OLD_ENV` и что делать с каждой; две новые — `H2T_PATH_ROOT`, `H2T_PATH_VAULT`; access-токен Google больше не пишется на диск, токен — у каждой машины свой в `secrets/local`; манифест Granola из `--to`, отличного от `lake/granola`, не переносится)
- Modify: `plugins/**/SKILL.md` и `references/*.md` — упоминания старых мест (`grep -rn "latest.json\|secrets.env\|\.config/telegram\|google-calendar-mcp" plugins/ --include=*.md`: 18 строк на 2ddd6db6; число на ветке к этой задаче замерить заново, Task 16 часть уже убрала) и всё найденное в Task 24 Step 5
- Modify: `.claude/rules/external-dependencies.md` (строка «Environment variables that gate behaviour»: `H2T_SESSION_ROOT`, `H2T_ACTIVITY_SPOOL`, `H2T_SECRETS_FILE` → `H2T_PATH_ROOT`, `H2T_PATH_VAULT`; `H2T_KB_ROOT` остаётся — её читает `llm-kb-engine`, не пакет)
- Create: `tests/governance/test_skills_name_no_legacy_paths.py` (Step 2)
- Create: тексты issues в репо (R26), дата — день выполнения, frontmatter `title`/`status: "draft"`/`date`, как у `docs/reports/2026-10-17-exec-map.md`:
  - `docs/reports/2026-MM-DD-storage-issue-pos-google.md` (токен Google, `mentions_cache.json`);
  - `docs/reports/2026-MM-DD-storage-issue-pos-vault.md` (`H2T_PATH_VAULT`);
  - `docs/reports/2026-MM-DD-storage-issue-rejuve.md`.
- Modify: `CLAUDE.md` (строка про `~/.h2t/config/secrets` в описании контекста, если есть)

- [ ] **Step 1: Тексты.** Каждое упоминание старого места в скилле заменяется командой `h2t-ops paths get <id>`, а не новым путём. Так текст не устареет при следующем переносе.

- [ ] **Step 2: Тест ссылок на старые места в скиллах.** `tests/governance/test_skills_name_no_legacy_paths.py`: `grep` по `plugins/**/*.md` для `~/.dor/`, `~/.config/(google-calendar-mcp|gmail|notion|telegram)`, `~/.h2t/sessions`, `~/.h2t/config/secrets` даёт 0. Исключение — строки, которые описывают миграцию: они содержат слово `legacy` или `3.x`.

- [ ] **Step 3: Issues — тексты** (только файлы, без отправки). Для POS, `…-storage-issue-pos-google.md`: таблица §9, ещё три пункта.
  - `mentions_cache.json` с #403 никто не пишет; упоминания брать из `h2t-ops telegram mentions --json`.
  - С 4.0 пакет нигде не хранит access-токен Google. `tokens.json` (путь из `GOOGLE_TOKEN_FILE` в plist) пишется только при входе и новом refresh-токене, поэтому `token`/`expiry` в нём протухают через час. POS должен получать новый access-токен по `refresh_token` сам; google-auth делает это, увидев истёкший `expiry`. На месте результата живой проверки — строка-заполнитель `<!-- POS live check: filled in Task 26 -->`: проверка идёт в Task 26, а не здесь.
  - Токен Google теперь у каждой машины свой: `~/.h2t/secrets/local/google.token.json`. Контракт: `h2t-ops paths get secret:google.token`; старый путь пакет зеркалит до 4.1.

  Для POS, `…-storage-issue-pos-vault.md`: vault — общий договор двух программ. Пакет берёт его из `H2T_PATH_VAULT` (по умолчанию `~/.dor/vault`); POS держит `~/.dor/vault` зашитым (`src/pos_ingest/config.py:4-6`, `src/pos_meetings/config.py:7,44`, `src/pos_meetings/routing_review.py:50`). Просьба: читать vault из `H2T_PATH_VAULT` с тем же умолчанием и добавить переменную в plist POS API, если vault когда-нибудь переедет. Правку в POS этот репо не делает (`.claude/rules/repo-boundary.md`).

  Для rejuve, `…-storage-issue-rejuve.md`: ключи — в `~/.h2t/secrets/shared/<провайдер>.env`, путь даёт `h2t-ops paths get secret:<провайдер>`; `~/.h2t/config/secrets/*.env` остаются копиями до 4.1.

  Заведение issues — Task 26 Step 3 (R26).

- [ ] **Step 4: Красный контроль** теста Step 2: вернуть в один `SKILL.md` строку `~/.dor/secrets.env` без слов `legacy`/`3.x` → FAIL с путём файла. Вернуть.

- [ ] **Step 5: Commit** — `git add README.md CHANGELOG.md .claude/rules/external-dependencies.md tests/governance/test_skills_name_no_legacy_paths.py docs/reports/2026-MM-DD-storage-issue-pos-google.md docs/reports/2026-MM-DD-storage-issue-pos-vault.md docs/reports/2026-MM-DD-storage-issue-rejuve.md` и каждый правленый `plugins/…/SKILL.md`, `plugins/…/references/*.md` по имени (+ `CLAUDE.md`, если правился); `docs(storage): layout, migration and contracts in README, CHANGELOG and skills (#548)`.

### Task 26: Живой перенос и приёмка **[владелец]**

Перенос на машинах автора ведётся по документу выкатки `docs/superpowers/plans/2026-10-18-storage-rollout.md`: порядок машин, проверка
POS с протухшим access-токеном (спека §11.6, R11), приёмка на каждой машине. Миграция
запускается командой `h2t-setup layout migrate` на editable-установке из ветки (R13), поэтому
задача выполняется **до** выпуска 4.0.0 (Task 27).

Здесь остаются проверки приёмки §12, которые от машин не зависят:

- [ ] **Step 1: Выкатка** — все шаги `docs/superpowers/plans/2026-10-18-storage-rollout.md` отмечены, отчёт приёмки записан.
- [ ] **Step 2: Общая приёмка §12** — по пункту, с выводом:
  - [ ] сторожа §7.3 зелёные на CI (ubuntu и windows).
  - [ ] откат на тестовом `HOME` (не на живом): `HOME=$SP/home h2t-setup layout migrate` на 3.x-раскладке из фикстуры Task 23, затем сессия после миграции, затем `HOME=$SP/home h2t-setup layout rollback --sync-paused` — сессия осталась. `layout` не ставит пакет через `uv`, поэтому поддельный `HOME` ничего не устанавливает.
  - [ ] новый пользователь: `HOME=$SP/empty h2t-setup layout migrate` → `layout.json` создан, нет `~/.dor`, нет `~/.config/<программа>` (тот же сценарий в наборе — `test_empty_home_migrates_to_layout_1`, Task 23).
- [ ] **Step 3: [владелец] Issues в POS и rejuve** (перенесено из Task 25, R26).
  - Вписать результат живой проверки POS с протухшим `expiry` (документ выкатки) в `docs/reports/…-storage-issue-pos-google.md` вместо строки `<!-- POS live check: filled in Task 26 -->`; если POS упал — сначала запасной вариант B (R11), и issue говорит о нём.
  - Показать владельцу три текста. По его «да» выполнить `gh issue create --repo lichtpfad/POS --title "pos: Read the Google token through h2t-ops paths" --body-file docs/reports/…-storage-issue-pos-google.md`, `gh issue create --repo lichtpfad/POS --title "pos: Read the vault location from H2T_PATH_VAULT" --body-file docs/reports/…-storage-issue-pos-vault.md` и то же для rejuve с `…-storage-issue-rejuve.md` (точный slug репо rejuve спросить у владельца). Перед этим `gh issue list --search` на дубликаты; метки и поля — по формам репо (скилл `h2t-dev:github-issues`).
  - В каждый из трёх файлов вписать ссылку на заведённый issue и `status: "done"`; `git add` этих трёх путей; `docs(storage): issue links for POS and rejuve (#548)`.

### Task 27: Выпуск 4.0.0 **[владелец]**

Выпуск — задачи 18–19 плана подсистемы 1 (`docs/superpowers/plans/2026-10-16-package-architecture.md`). Этот план добавляет к ним одно условие: Task 26 завершена. Цикла нет: Task 26 идёт на editable-установке через `h2t-setup layout migrate` и опубликованного выпуска не требует (R13).

- [ ] **Step 1: PR этой подсистемы → `main`.** Ветка от `main`, все коммиты задач 2–25. Описание PR — список задач и вывод Task 24 Step 4. Merge — по слову владельца. Предупреждение из памяти: хук `plan_closer` после merge поставит этому плану и спеке `status: done` — откатить, пока 4.0.0 не выпущен.
- [ ] **Step 2: Задача 18 плана подсистемы 1** (`release.py prepare 4.0.0` → PR → merge → tag `v4.0.0` → workflow выпуска). После выпуска `h2t-setup sync` у пользователей вызывает ту же миграцию (Task 23 Step 4).
- [ ] **Step 3: Задача 19 плана подсистемы 1** (живая приёмка выпуска) + обновить трекер #541 и закрыть #548 (`gh issue close 548 --comment "Fixed in <sha>"`).
