---
title: "Storage rollout"
status: "draft"
date: "2026-10-18"
milestone: ""
issue: "548"
---

# Storage rollout

Выкатка подсистемы 2 (#548) на машины автора. Сюда вынесено всё, что относится к конкретным
машинам: их состав, результаты проб и живой перенос. Как устроено хранение и как мигрирует
любая машина, описывают спека `docs/superpowers/specs/2026-10-17-storage-and-governance.md`
и план `docs/superpowers/plans/2026-10-17-storage-and-governance.md`. Этот документ
опирается на них и решений не меняет.

## Машины

Состав подтвердил владелец 2026-10-18.

| Машина | ОС | Имя машины | Что известно |
|---|---|---|---|
| MacBook | macOS | `macbook-pro-3` | имя закреплено в настройках Claude (ADR 0003); hostname сейчас `MacBook-Pro-4`, `HostName` не задан; сессии в `~/.h2t/sessions/macbook-pro-3` и `~/.dor/sessions/macbook-pro-3` |
| Десктоп | Windows | `automata` | 148 md в `~/.dor/sessions/automata`, последняя запись 2026-05-22; hostname, закрепление имени, Syncthing и токен Google не проверены |
| Ноутбук | Windows | `computer` | hostname `Computer`; в `~/.h2t/sessions/computer` один md; `H2T_SESSION_ROOT` не задан; Syncthing не установлен |

## Результаты проб

Пробы ноутбука пришли 2026-10-17 23:35 UTC, сообщение 1582 в Telegram-чате `3dwalker`.
Выводы для устройства пакета уже внесены в спеку (§4, §7.2, §11). Здесь лежат сами замеры.

| Проба (спека §11) | Факт | Вывод |
|---|---|---|
| 11.1 Syncthing: даёт ли одинаковый файл, созданный на двух машинах, `*.sync-conflict-*` | **не проведена**: на ноутбуке Syncthing не установлен | действует безопасный порядок ниже: машина без `secrets/shared` мигрирует только после того, как он к ней приехал; пробу провести на десктопе или на ноутбуке, когда там появится Syncthing (Step 0) |
| 11.3 права Windows: `os.chmod(f, 0o600)` и `icacls` до и после | режим читается `0o666`, chmod без эффекта; ACL наследуется от профиля: владелец, Administratoren, SYSTEM | на Windows права не ставятся и не проверяются, проверки только на POSIX |
| 11.4 Google: `sha256[:12]` поля `refresh_token` | ноутбук `4ac3fa1e3925`, мак `ffadbd08aa1f`: входы разные | токен у каждой машины свой в `local/google.token.json`, клиент общий в `shared` |
| 11.5 `msvcrt`: A держит блокировку 3 с, B пытается дописать | B ждал 2,48 с | `append` на Windows использует `msvcrt.locking` |
| 11.2 индекс (мак) | полная сборка SQLite по 318 md — 15–66 мс; проход `stat` по 49 каталогам и 2 файлам онтологии — 0,3–0,7 мс | индекс пересобирается по `stat`; холодный кэш и Windows не замерены |

## Порядок

Миграция запускается командой `h2t-setup layout migrate` на editable-установке из ветки
(план, R13). Поэтому весь перенос выполняется **до** выпуска 4.0.0 (план, Task 27). До своего
шага каждая Windows-машина работает на старых запасных местах.

1. Мак: `h2t-setup dev-sync`, затем `h2t-setup layout migrate`, затем в Syncthing папки
   `~/.h2t/secrets/shared` и `~/.h2t/records`.
2. Десктоп: то же самое. Его сессии после 2026-05-22 приезжают на мак.
3. Ноутбук: сначала установить Syncthing, затем то же самое.
4. Все три машины: `doctor` и `session-start` в одном репо.

Команды на Windows-машины уходят через Telegram-чат `3dwalker`:
`h2t-ops telegram send 3dwalker --message "…"`, ответ читается
`h2t-ops telegram messages 3dwalker --limit 20 --json`. У `send` флага `--confirm-send` нет,
он есть только у `send-file` (`connectors/telegram/commands.py:75-80`).

## Шаги

- [ ] **Step 0: Syncthing-проба (спека §11.1).** На машине, где Syncthing есть и синхронизирует
  `~/.dor` (десктоп, если там он стоит; иначе ноутбук после установки). Не блокирует задачи
  плана 2–25. Обе машины при выключенной синхронизации независимо создают одинаковый файл; на
  маке:

  ```bash
  mkdir -p ~/.dor/_h2t-probe
  printf 'same content 2026-10-17\n' > ~/.dor/_h2t-probe/same.txt
  shasum -a 256 ~/.dor/_h2t-probe/same.txt
  ```

  Затем ответ в чат «мак: файл создан». После ответа Windows-машины включить синхронизацию,
  на маке `ls -la ~/.dor/_h2t-probe/`, затем `rm -rf ~/.dor/_h2t-probe`. Если конфликт
  появился, порядок выше остаётся обязательным; если нет, в спеке §11.1 закрыть строкой
  «порядок не важен» и закоммитить: `docs(storage): syncthing probe result (#548)`.

- [ ] **Step 1: Мак, перед переносом.** `h2t-ops doctor` → сохранить вывод. Хэш-манифест старых
  мест: `find ~/.dor ~/.config/{google-calendar-mcp,gmail,notion,telegram} ~/.h2t/{sessions,activity,evals,research,creative,config/secrets} -type f -exec shasum -a 256 {} +`,
  вывод только в scratchpad, значения файлов не печатаются.

- [ ] **Step 2: Мак, перенос.** `h2t-setup dev-sync` (editable из ветки), затем
  `h2t-setup layout migrate`. Если фаза имени машины остановилась —
  `h2t-setup layout migrate --machine macbook-pro-3` (имя в настройках Claude должно
  совпадать, ADR 0003). Проверка:
  - `h2t-ops doctor` без `ERROR`;
  - `h2t-ops paths list`;
  - `h2t-ops index query --project h2t-skills`;
  - `~/.h2t/secrets/local/google.token.json` есть, `~/.h2t/secrets/shared/google.token.json` нет (план, R19);
  - хэш-манифест старых мест не изменился (сравнить `diff` двух файлов манифеста, без вывода значений).

- [ ] **Step 3: POS с протухшим access-токеном (спека §11.6, план R11) [владелец].** После Step 2
  пакет больше не обновляет `token` в `~/.config/google-calendar-mcp/tokens.json`; через час
  после последнего входа он истекает сам, ничего копировать и править не нужно. Владелец
  вызывает у POS API одну команду календаря (тот endpoint, которым POS пользуется каждый день)
  и смотрит код ответа. 200 — R11 остаётся, результат вписать в `issue-pos.md` (план, Task 25).
  401 — включить запасной вариант B (план, Task 8, правило 7: `mirror_legacy` на каждом
  рефреше), прогнать `tests/core/test_google_auth.py`, повторить проверку. Значения токена в
  выводе не печатаются.

- [ ] **Step 4: Мак, Syncthing [владелец].** Владелец добавляет в Syncthing папки
  `~/.h2t/secrets/shared` и `~/.h2t/records`. `doctor` → синхронизация `records`,
  `secrets.shared` = `confirmed`.

- [ ] **Step 5: Десктоп `automata` [владелец].** Сначала проба: `hostname`, установлен ли
  Syncthing и синхронизирует ли `~/.dor` (если да — Step 0 проводится здесь), задан ли
  `H2T_MACHINE_NAME` в настройках Claude, сколько md в `~/.h2t/sessions/*` и
  `~/.dor/sessions/automata`. Дождаться, пока `~/.h2t/secrets/shared` с мака приехал. Затем
  Step 1 и Step 2 на десктопе с `--machine automata`, чтобы 148 сессий из
  `~/.dor/sessions/automata` остались под своим именем. Если hostname десктопа уже не
  `automata` и в `~/.h2t/sessions` есть папка под другим именем, её md миграция переносит в
  `records/sessions/automata/` (тот же случай, что #491 на маке). Сессии десктопа приезжают
  на мак: `h2t-ops index query --project <id>` на маке показывает `automata`.

- [ ] **Step 6: Ноутбук `computer` [владелец].** Сначала установить Syncthing и, если Step 0 ещё
  не сделан, провести его здесь. Дождаться, пока `~/.h2t/secrets/shared` с мака приехал. Затем
  Step 1 и Step 2 на ноутбуке с `--machine computer`. Сессии ноутбука приезжают на мак.

- [ ] **Step 7: Приёмка (спека §12)** — по пункту, с выводом:
  - [ ] `session-start` в одном репо на всех трёх машинах показывает последнюю сессию проекта с
    именем машины, чужих проектов нет, предупреждение — при расхождении.
  - [ ] `doctor` чистый на всех трёх, синхронизация «подтверждено» или «объявлено».
  - [ ] каждый коннектор: `h2t-ops <коннектор> --help` и одна безопасная команда чтения
    (`notion search`, `calendar list --days 1`, `gmail search --limit 1`,
    `telegram dialogs --limit 1`, `granola list --limit 1`, `meetgeek list --limit 1`,
    `research` — `doctor`), ключи сверены по хэшу с манифестом Step 1. Имена подкоманд сверены
    по коду: `calendar list` (`connectors/calendar/commands.py:91`), `meetgeek list`
    (`connectors/meetgeek/commands.py:167`); `calendar events` и `meetgeek meetings` не
    существуют.
  - [ ] контроль: старые каталоги переименованы (`mv ~/.config/telegram ~/.config/telegram.gone`
    и т.д.) — коннекторы работают; вернуть имена.
  - [ ] POS отвечает с протухшим access-токеном (Step 3) или включён вариант B.

- [ ] **Step 8: Отчёт** — `docs/reports/2026-MM-DD-storage-acceptance.md`; commit.
