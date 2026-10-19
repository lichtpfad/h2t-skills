---
title: "Storage acceptance — macbook-pro-3"
date: "2026-10-19"
status: "complete"
issue: "#556"
---

# Storage acceptance — macbook-pro-3

Журнал выкатки 4.0.0 на Mac (вариант A: локальный кандидат). Каждый шаг: время, команда, код выхода, вывод. Значения секретов не пишутся.

## 1. Кандидат 4.0.0

- 2026-10-19 03:55 IDT — worktree `.worktrees/rc-4.0.0`, detached на `7c9347ce` (origin/main).
- `scripts/release.py prepare 4.0.0` → exit 0, "release 4.0.0: 35 files, constraints.txt, release.json"; `@VERSION@` в plugins/, h2t_ops/, README.md: 0; не закоммичено.

## 2. Установка CLI: `uv run --project . h2t-setup dev-sync`

- exit 0. Вывод целиком:

```text
Using CPython 3.12.12
Creating virtual environment at: .venv
   Building h2t-ops @ file:///Users/stanislav_glazov/Projects/h2t-skills/.worktrees/rc-4.0.0
      Built h2t-ops @ file:///Users/stanislav_glazov/Projects/h2t-skills/.worktrees/rc-4.0.0
Installed 55 packages in 209ms
done: CLI h2t-ops 4.0.0: installed editable from /Users/stanislav_glazov/Projects/h2t-skills/.worktrees/rc-4.0.0; answers when run
Plugins: dev-sync does not touch the marketplace plugins. Load them from the checkout: claude --plugin-dir /Users/stanislav_glazov/Projects/h2t-skills/.worktrees/rc-4.0.0/plugins/<name> (or pwsh scripts/claude-dev.ps1). The checkout itself is not updated: git is yours to run.
```

Проверка по состоянию:

```text
h2t-ops v4.0.0
commands: 19
{"ok": true, "provider": "version", "result": {"ok": true, "version": "4.0.0", "reason": null, "hint": null}}

h2t-setup: /Users/stanislav_glazov/.local/bin/h2t-setup
layout.json: absent
```

Ошибок установки нет. Плагины маркетплейса не тронуты (3.2.62 в кэше); 4.0 грузятся через `--plugin-dir`.

## 3. Состояние до миграции

03:58

`env | grep -oE '^H2T_[A-Z_]+'` → exit 0:

```text
H2T_MACHINE_NAME
```

`h2t-ops doctor > SCRATCH/doctor-before.txt` → exit 0, 44 строки. Секция `storage`:

```text
storage: layout none, root ~/.h2t
storage: sync config = confirmed (.dropbox at /Users/stanislav_glazov), secrets.shared = confirmed (.dropbox at /Users/stanislav_glazov), secrets.local = confirmed (.dropbox at /Users/stanislav_glazov), records = confirmed (.dropbox at /Users/stanislav_glazov), data = confirmed (.dropbox at /Users/stanislav_glazov), state = confirmed (.dropbox at /Users/stanislav_glazov), logs = confirmed (.dropbox at /Users/stanislav_glazov)
storage: ERROR secret-tracked: ~/.h2t/config/domains.yaml holds a value for notion_db_id and is tracked by git
storage: ERROR secret-tracked: ~/.h2t/config/rules/skills.md holds a value for NOTION_API_TOKEN and is tracked by git
storage: ERROR local-in-sync: ~/.h2t/secrets/local lies inside a Dropbox folder (~/.dropbox)
storage: ERROR local-in-sync: ~/.h2t/state lies inside a Dropbox folder (~/.dropbox)
storage: ERROR local-in-sync: ~/.h2t/logs lies inside a Dropbox folder (~/.dropbox)
storage: ERROR local-in-sync: ~/.h2t/run/rollback lies inside a Dropbox folder (~/.dropbox)
storage: warn legacy-only: sessions are only in ~/.h2t/sessions, ~/.dor/sessions — h2t-setup sync moves them
storage: warn legacy-only: activity is only in ~/.h2t/activity — h2t-setup sync moves them
storage: warn legacy-only: evals are only in ~/.h2t/evals — h2t-setup sync moves them
storage: warn legacy-only: research is only in ~/.h2t/research — h2t-setup sync moves them
storage: warn legacy-only: the DOR registry is only in ~/.dor/registry.jsonl — h2t-setup sync moves them
storage: warn legacy-only: secrets are only in ~/.h2t/config/secrets, ~/.dor/secrets/secrets.env, ~/.dor/secrets.env, ~/.config/notion/token, ~/.config/google-calendar-mcp, ~/.config/gmail, ~/.dor/google-credentials.json, ~/.config/telegram — h2t-setup sync moves them
storage: warn unknown-root-entry: ~/.h2t/.DS_Store is not a place of the package
storage: warn unknown-root-entry: ~/.h2t/.gather-active is not a place of the package
storage: warn unknown-root-entry: ~/.h2t/deleted-branches-h2t-skills-2026-08-22.txt is not a place of the package
storage: warn unknown-root-entry: ~/.h2t/graphs is not a place of the package
storage: warn unknown-root-entry: ~/.h2t/h2t-skills-backup-20260827-144615.git is not a place of the package
storage: warn unknown-root-entry: ~/.h2t/pre-filter-repo-manifest-20260827-144557.txt is not a place of the package
storage: warn unknown-root-entry: ~/.h2t/tools is not a place of the package
storage: warn config-backup: ~/.h2t/config/domains.yaml.bak is a 3.x copy; copies now live in ~/.h2t/state/backups
storage: warn config-backup: ~/.h2t/config/domains.yaml.bak-desc is a 3.x copy; copies now live in ~/.h2t/state/backups
storage: warn config-backup: ~/.h2t/config/repo-mapping.yaml.bak is a 3.x copy; copies now live in ~/.h2t/state/backups
storage: info index-schema: ~/.h2t/state/index.sqlite is not built yet; the first session-start or h2t-ops index rebuild builds it
storage: info place-unset: lake is not set; the package uses ~/.h2t/data/lake — h2t-ops paths set lake <path>
storage: info place-unset: inbox is not set; the package uses ~/.h2t/data/inbox — h2t-ops paths set inbox <path>
```

Итого до: 6 ERROR, 17 warn.

Замечание к `local-in-sync` (предположение, проверено только `ls`): `~/.dropbox` — служебный каталог клиента Dropbox (`apex.sqlite3`, `dropbox.pid`, `host.db`, `info.json`), а не синхронизируемая папка. Сама папка Dropbox — `~/Dropbox -> ~/Your team Dropbox/Stanislav Glazov`. Детектор, судя по выводу, принимает `~/.dropbox` в `$HOME` за маркер и считает весь `~` синхронизируемым — тогда все 4 ERROR `local-in-sync` и все `confirmed` в строке `sync` ложные.

Манифест хэшей старых мест → `SCRATCH/manifest-before.txt`: 21850 строк.

## 4. Миграция: `h2t-setup layout migrate`

03:58 → exit 0. Вывод целиком (3 строки):

```text
done: layout 1
layout 1: activity: 1279 test rows skipped
layout 1: journal /Users/stanislav_glazov/.h2t/run/rollback/layout1-20261019T005847060440Z
```

На имени машины не остановилась: `H2T_MACHINE_NAME` задан в окружении, `--machine` не понадобился. Повторов и других флагов не было.

## 5. Проверка после миграции

### 5.1 `h2t-ops doctor`

04:01 → exit 0. Секция `storage`:

```text
storage: layout 1, root ~/.h2t
storage: sync config = confirmed (.dropbox at /Users/stanislav_glazov), secrets.shared = confirmed (.dropbox at /Users/stanislav_glazov), secrets.local = confirmed (.dropbox at /Users/stanislav_glazov), records = confirmed (.dropbox at /Users/stanislav_glazov), data = confirmed (.dropbox at /Users/stanislav_glazov), state = confirmed (.dropbox at /Users/stanislav_glazov), logs = confirmed (.dropbox at /Users/stanislav_glazov)
storage: ERROR secret-tracked: ~/.h2t/config/domains.yaml holds a value for notion_db_id and is tracked by git
storage: ERROR secret-tracked: ~/.h2t/config/rules/skills.md holds a value for NOTION_API_TOKEN and is tracked by git
storage: ERROR local-in-sync: ~/.h2t/secrets/local lies inside a Dropbox folder (~/.dropbox)
storage: ERROR local-in-sync: ~/.h2t/state lies inside a Dropbox folder (~/.dropbox)
storage: ERROR local-in-sync: ~/.h2t/logs lies inside a Dropbox folder (~/.dropbox)
storage: ERROR local-in-sync: ~/.h2t/run/rollback lies inside a Dropbox folder (~/.dropbox)
storage: warn unknown-root-entry: ~/.h2t/.DS_Store is not a place of the package
storage: warn unknown-root-entry: ~/.h2t/.gather-active is not a place of the package
storage: warn unknown-root-entry: ~/.h2t/deleted-branches-h2t-skills-2026-08-22.txt is not a place of the package
storage: warn unknown-root-entry: ~/.h2t/graphs is not a place of the package
storage: warn unknown-root-entry: ~/.h2t/h2t-skills-backup-20260827-144615.git is not a place of the package
storage: warn unknown-root-entry: ~/.h2t/pre-filter-repo-manifest-20260827-144557.txt is not a place of the package
storage: warn unknown-root-entry: ~/.h2t/tools is not a place of the package
```

ERROR (6): `secret-tracked` ×2 (domains.yaml / notion_db_id; rules/skills.md / NOTION_API_TOKEN); `local-in-sync` ×4 (secrets/local, state, logs, run/rollback) — см. замечание в §3 о `~/.dropbox`.
WARN (7): все `unknown-root-entry` (.DS_Store, .gather-active, deleted-branches-…txt, graphs, h2t-skills-backup-…git, pre-filter-repo-manifest-…txt, tools).
Ушли по сравнению с «до»: 6 `legacy-only`, 3 `config-backup`, 3 `info`. Вне секции storage строк ERROR/WARN нет.

### 5.2 `h2t-ops paths list`

exit 0:

```text
run               /Users/stanislav_glazov/.h2t/run  [fixed, sync never, exists]  default (the install contract; H2T_PATH_ROOT does not move it)
config            /Users/stanislav_glazov/.h2t/config  [class, sync user, exists]  default
secrets.shared    /Users/stanislav_glazov/.h2t/secrets/shared  [class, sync user, exists]  default
secrets.local     /Users/stanislav_glazov/.h2t/secrets/local  [class, sync never, exists]  default
records.sessions  /Users/stanislav_glazov/.h2t/records/sessions  [class, sync user, exists]  default
records.activity  /Users/stanislav_glazov/.h2t/records/activity  [class, sync user, exists]  default
records.evals     /Users/stanislav_glazov/.h2t/records/evals  [class, sync user, exists]  default
records.imports   /Users/stanislav_glazov/.h2t/records/imports  [class, sync user, exists]  default
data              /Users/stanislav_glazov/.h2t/data  [class, sync user, exists]  default
state             /Users/stanislav_glazov/.h2t/state  [class, sync never, exists]  default
logs              /Users/stanislav_glazov/.h2t/logs  [class, sync never, exists]  default
lake              /Users/stanislav_glazov/.dor/lake  [place, sync owner, exists]  paths.yaml
inbox             /Users/stanislav_glazov/Downloads  [place, sync owner, exists]  paths.yaml
vault             /Users/stanislav_glazov/.dor/vault  [place, sync owner, exists]  default
kb                /Users/stanislav_glazov/.h2t/data/kb  [place, sync owner, missing]  default (not set)
repo              —  [place, sync owner, missing]  cwd or --repo-root of each command
harness           /Users/stanislav_glazov/.claude  [place, sync owner, exists]  default
tmp               /var/folders/p8/lyzrdnys2x1043v70tx1j67w0000gn/T  [place, sync never, exists]  default
layout            /Users/stanislav_glazov/.h2t/layout.json  [file, sync never, exists]  default
```

### 5.3 `h2t-ops index query --project h2t-skills`

exit 0, **1 строка** (с `--limit 50` тоже 1):

```text
2026-08-20T12:54:14.092297+00:00  macbook-pro-3  personal-os-h2t-skills-plugin-delivery-2026-08-20  /Users/stanislav_glazov/.h2t/records/sessions/macbook-pro-3/h2t-skills/personal-os-h2t-skills-plugin-delivery-2026-08-20.md
```

Сверка по диску: в `~/.h2t/records/sessions/macbook-pro-3/h2t-skills/` ровно 1 файл — индекс совпадает с тем, что перенесено. Почему markdown-записей по h2t-skills на этой машине одна, не проверялось.

### 5.4 Секреты: `ls -la ~/.h2t/secrets/local/ ~/.h2t/secrets/shared/` (имена и режимы)

```text
local/   drwx------
  -rw------- google.token.json
  -rw------- telegram.auth-state.json
  -rw------- telegram.session
shared/  drwx------
  -rw------- aim-lms.env  coinapi.env  exa.env  getcourse.env  google.client.json
  -rw------- granola.env  h2t-evals.env  meetgeek.env  notion.env  other.env
  -rw------- paypal.env  santiment.env  simplybook.env  stripe.env  telegram.env
  -rw------- typeform.env  vimeo.env
```

`google.token.json` — в `local/`, в `shared/` его нет. Все файлы 0600, каталоги 0700.

### 5.5 `cat ~/.h2t/layout.json`

```json
{
  "layout": 1,
  "machine": "macbook-pro-3",
  "migrated_at": "2026-10-19T01:01:26Z",
  "journal": "layout1-20261019T005847060440Z"
}
```

### 5.6 Манифест после

04:01. `SCRATCH/manifest-after.txt`: 21862 строки (до — 21850).
`diff manifest-before.txt manifest-after.txt | wc -l` → **24**, не 0: 12 добавленных строк + 12 строк-заголовков хунков. Удалённых и изменённых строк нет — ни один старый файл не изменён. Все 12 добавленных — новые `MOVED-TO.txt`:

```text
~/.config/gmail/MOVED-TO.txt
~/.config/google-calendar-mcp/MOVED-TO.txt
~/.config/notion/MOVED-TO.txt
~/.config/telegram/MOVED-TO.txt
~/.dor/MOVED-TO.txt
~/.dor/secrets/MOVED-TO.txt
~/.dor/sessions/MOVED-TO.txt
~/.h2t/activity/MOVED-TO.txt
~/.h2t/config/secrets/MOVED-TO.txt
~/.h2t/evals/MOVED-TO.txt
~/.h2t/research/MOVED-TO.txt
~/.h2t/sessions/MOVED-TO.txt
```

Строк, кроме `MOVED-TO.txt`: 0.

## 6. `~/.h2t/config/user.yaml`

04:02. До записи: `ls -la ~/.h2t/config/user.yaml` → exit 1, `No such file or directory`. Создан ровно с содержимым:

```yaml
timezone: Asia/Jerusalem
notion:
  tasks_database_id: beabac7bf4314952a9327759c638d89f
domain_patterns:
  - pattern: "Projects/DOR|Projects/newsengine"
    domain: personal-os
```

`h2t-ops calendar list --json` → exit 0, stderr пуст, `ok: true`:

- `tz_source`: `user.yaml` (не `system`);
- событий: 5.

Повторный `h2t-ops doctor`: ERROR+warn в storage — 13, как в §5.1; про user.yaml строк нет. В git-репозитории `~/.h2t/config` файл не отслеживается (`?? user.yaml`) — не коммитился.

## Итог Mac

04:03.

**Прошло (проверено командами выше):**

- `h2t-setup layout migrate` → exit 0, `done: layout 1`, journal `layout1-20261019T005847060440Z`; 1279 тестовых строк activity пропущены.
- `layout.json`: `layout 1`, `machine macbook-pro-3`.
- `paths list`: все классы `exists`; `secrets.local`, `state`, `logs`, `run` — `sync never`.
- Секреты: `google.token.json` в `local/`, не в `shared/`; файлы 0600, каталоги 0700.
- Старые места не изменены: в diff манифестов только 12 новых `MOVED-TO.txt`.
- Индекс: 1 строка по h2t-skills — совпадает с одним файлом на диске.
- `user.yaml` создан, `calendar list` → `tz_source: user.yaml`, 5 событий.
- Из doctor ушли все `legacy-only`, `config-backup` и `info`.

**ERROR (6) и WARN (7) в doctor после миграции:**

- ERROR `secret-tracked`: `~/.h2t/config/domains.yaml` (`notion_db_id`) и `~/.h2t/config/rules/skills.md` (`NOTION_API_TOKEN`) отслеживаются git'ом в `~/.h2t/config`. Миграция их не трогает. Для токена решение по правилу ротации (`.claude/rules/secrets.md`): сначала ротация, потом убирать из файла и истории.
- ERROR `local-in-sync` ×4 (`secrets/local`, `state`, `logs`, `run/rollback`): скорее всего ложные — см. §3. `~/.dropbox` это служебный каталог клиента Dropbox, а не синхронизируемая папка. Поэтому же все `confirmed` в строке `sync` ничего не говорят о Syncthing. Это кандидат на баг в детекторе doctor, issue не заводился.
- WARN `unknown-root-entry` ×7: `.DS_Store`, `.gather-active`, `deleted-branches-h2t-skills-2026-08-22.txt`, `graphs`, `h2t-skills-backup-20260827-144615.git`, `pre-filter-repo-manifest-20260827-144557.txt`, `tools`. Это чужие файлы в `~/.h2t`; их судьбу решает владелец.

**Осталось владельцу:**

1. Syncthing: добавить `~/.h2t/secrets/shared` и `~/.h2t/records` (план, Step 4). Пока детектор принимает `~/.dropbox` за синхронизацию, строка `sync` в doctor не подтвердит Syncthing.
2. `session-start` в интерактивной сессии на плагинах 4.0 (`--plugin-dir` из `.worktrees/rc-4.0.0/plugins/<name>`). Маркетплейс по-прежнему на 3.2.62.
3. Проверка POS с протухшим access-токеном — `docs/superpowers/plans/2026-10-18-storage-rollout.md` Step 3. Этот файл есть только в `.worktrees/rc-4.0.0`, в основном checkout его нет. Через час после последнего входа вызвать календарный endpoint POS: 200 → R11 остаётся, записать в `issue-pos.md`; 401 → вариант B (`mirror_legacy`).
4. Решить по двум `secret-tracked` и по 7 посторонним записям в `~/.h2t`.
5. Откат при необходимости — `h2t-setup layout rollback` (не запускался).

## Проверка контролёра (04:05)

Сверено по состоянию, не по отчёту сессии `claude -p`.

- `~/.h2t/layout.json`: layout 1, machine macbook-pro-3, journal layout1-20261019T005847060440Z.
- Сессии: 172 md в `records/sessions/macbook-pro-3` против 173 в старых местах этой машины; 146 md automata не копировались (каждая машина переносит свои).
- Activity: в старом журнале 1447 строк, в новом 168. 1279 отброшены как тестовые (R15: точные session_id/проекты фикстур). Все отброшенные строки от 2026-08-22 до 2026-08-27, до 11 строк в секунду: это записи тестов того времени. Оставленные: 2026-04-05 … 2026-10-19.
- `doctor`: 6 ERROR, все ложные, это баги doctor:
  - secret-tracked `domains.yaml`: ключ `domains/hou2touch/notion_db_id` (id базы Notion, 36 символов) принят за секрет;
  - secret-tracked `rules/skills.md:81`: в примере `NOTION_API_TOKEN=` стоит заглушка из 3 символов, это не значение;
  - local-in-sync ×4: маркер `.dropbox` найден в `~/.dropbox` (это служебный каталог приложения Dropbox, а не синхронизируемая папка); `~/Dropbox/.dropbox` нет.
- `doctor` WARN ×7 unknown-root-entry: настоящие посторонние записи в `~/.h2t` (.DS_Store, .gather-active, graphs/, tools/, бэкап `.git` и манифесты от переписывания истории 2026-08-27). Решает владелец.

- Сессии 172 против 173: ни одна не потеряна. Файлы `art-works/…корпус-и-план-2026-08-24.md` и `external-schools/…aim-s26-lecture-2026-08-26.md` лежали и в `~/.h2t/sessions`, и в `~/.dor/sessions`; после миграции каждый стал одним.
- `doctor`: ложные ERROR исправлены в PR #559; открытые пункты и вопросы — комментарий в #556.

## Повтор после #559 (2026-10-19 04:49 IDT)

- #559 (79ef4546) и #565 (c1c67532) слиты в main.
- Кандидат пересобран: `git reset --hard origin/main` в `.worktrees/rc-4.0.0` (c1c67532), `release.py prepare 4.0.0` → 35 files, `@VERSION@`: 0; `dev-sync` → done; `h2t-ops version --expect 4.0.0` → ok.
- `h2t-ops doctor` → exit 0, **storage ERROR: 0**. WARN: 7 × unknown-root-entry (те же записи, решает владелец).
- Приёмка Mac по коду закрыта. Шаги владельца: Syncthing (`secrets/shared`, `records`), `session-start` на плагинах 4.0, проверка POS (rollout Step 3).

## Повтор после #567 (2026-10-19 18:05 IDT)

- #567 (2cc8eb5d, фиксы #560–#564) слит в main; issues закрыты.
- Кандидат пересобран: `git reset --hard origin/main` в `.worktrees/rc-4.0.0` (2cc8eb5d), `release.py prepare 4.0.0` → 35 files, `@VERSION@`: 0; `dev-sync` → done; `h2t-ops version --expect 4.0.0` → ok. Установленный `h2t_ops.core.paths` — из кандидата, `VaultUnresolvable` есть.
- `h2t-ops doctor` → exit 0, 26 строк, **ERROR: 0**. WARN: 7 × unknown-root-entry (те же записи). Строка `sync`: все места `unknown` — Syncthing ещё не настроен.
