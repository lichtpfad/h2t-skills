# Пробы архитектуры пакета на macOS — 2026-10-17

Измерения для задач 9 (порог таймаута хука) и 14–16 (ветки `sync`). Машина: macOS (Darwin 25.5.0),
uv 0.9.13, Claude Code 2.1.301. Всё выполнено в изолированных каталогах: временные `HOME`,
`UV_TOOL_DIR`, `UV_TOOL_BIN_DIR`, `UV_PYTHON_INSTALL_DIR`, `UV_CACHE_DIR`, `CLAUDE_CONFIG_DIR`;
глобальные установки, `~/.claude`, `~/.h2t` не тронуты. Release на GitHub не создавался:
wheel и `constraints.txt` отдавал локальный `python3 -m http.server 8765` (после проб остановлен).

| проба | команда | что получено | вывод |
|---|---|---|---|
| 1. wheel по URL, холодный запуск | `uvx --isolated --python 3.12.11 --managed-python -c http://127.0.0.1:8765/constraints.txt --from "h2t-ops @ http://127.0.0.1:8765/h2t_ops-0.2.1-py3-none-any.whl" h2t-ops --version` (пустой кэш uv, Python 3.12.11 не скачан) | `h2t-ops 0.2.1`, 27.98 с (скачаны Python и 51 пакет) | `-c` по URL и `--from "имя @ URL"` работают; холодный бутстрап ≈ 28 с на этой сети |
| 1. то же, тёплый запуск | та же команда, кэш заполнен | `h2t-ops 0.2.1`, 0.13 с | тёплый запуск `uvx --isolated` укладывается в доли секунды |
| 2a. прерывание `--reinstall`, окно скачивания | `uv tool install --reinstall -c … --python 3.12.11 --managed-python "h2t-ops @ URL"`, пустой кэш, `kill -9` через 2 с (в логе: сборка pyaes, загрузка opencv) | код 137; каталог инструмента цел, `bin/h2t-ops --version` → `0.2.1`, код 0 | до фазы замены окружения прерывание безопасно: прежняя установка работает |
| 2b. прерывание `--reinstall`, окно распаковки | то же, тёплый кэш, `UV_LINK_MODE=copy` (расширяет фазу установки до ≈1.5 с), `kill -9` через 0.6 и 1 с | через 0.6 с и 1 с: в `bin/` нет `h2t-ops` (venv без исполняемого файла; в `site-packages` 45 и 102 записи против 106 в целом), `h2t-ops --version` → «No such file or directory», код 127. Через 0.3 с — цел; через 1.5 и 2 с процесс успел завершиться | **Установка ломается**, если процесс убит посреди замены окружения. Подтверждает `state=updating` как защиту (§7.3). Окно мало: на стандартном режиме (clone) вся замена ≈ 0.1 с, 8 попыток с 0.02 до 0.16 с его не поймали |
| 2c. восстановление | после 2b: `uv tool install …` (без `--reinstall`), затем отдельно ещё раз сломать и `uv tool install --reinstall …` | оба раза «Installed 9 executables», `h2t-ops --version` → `0.2.1`, код 0 | повторная установка (с `--reinstall` и без него) чинит сломанное окружение; `sync` может опираться на повтор |
| 3a. закреплённый marketplace | `CLAUDE_CONFIG_DIR=<tmp> claude plugin marketplace add 'lichtpfad/h2t-skills#v2.15.0'`, `plugin install h2t-core@lichtpfad --scope user`, `plugin disable h2t-core@lichtpfad` | `known_marketplaces.json`: `ref: v2.15.0`; установлен 3.2.3, scope `user`; после `disable` в `settings.json` `enabledPlugins: {"h2t-core@lichtpfad": false}` | закрепление на тег записывается в `known_marketplaces.json` и в `extraKnownMarketplaces` настроек |
| 3b. перезакрепление | `plugin marketplace remove lichtpfad` | «Also uninstalled 1 plugin: h2t-core@lichtpfad»; `installed_plugins.json` → `plugins: {}`; в `settings.json` `enabledPlugins: {}` и `extraKnownMarketplaces: {}` | `remove` удаляет плагин **и** запись о выключении — подтверждено, §7.3 п.5 верен |
| 3c. после `add` без ref | `plugin marketplace add lichtpfad/h2t-skills`, `plugin install h2t-core@lichtpfad --scope user`, `plugin list --json`; затем `plugin disable …` | `ref` в `known_marketplaces.json` нет; установлен 3.2.62 (голова main), scope `user`, `enabledPlugins: true` (включён); после `disable` — `false` | **Ни scope, ни disabled сами не сохраняются**: после `remove` → `add` → `install` плагин включён, и выключенное состояние надо записать заново. Scope сохраняется только потому, что передан `--scope user` явно. Восстановление из снимка (§7.3 п.3, п.5) необходимо |
| 4. полные обработчики 3.2.61 на окружении CLI | каждый файл из `~/.claude/plugins/cache/lichtpfad/h2t-core/3.2.61/hooks-handlers/` (21 файл), `echo '{}' \|`, `H2T_PYTHON=<python venv h2t-ops 0.2.1, 3.12.11>`, временный `HOME`; bash-скрипты через `bash`, `.py` и `on-stop`/`post-git-commit-docs-lint` (shebang `python3`) через python окружения | Код 0 и пустой stderr у 19 из 21 файла (у `bulk-precommit`, `layout-precommit`, `on-stop`, `post-git-commit-docs-lint` — после запуска в корректном окружении, см. ниже); `inject-h2t-context` печатает JSON `additionalContext` (1134 байта); `post_git_commit_docs_lint.py` — код 0, предупреждение `DeprecationWarning: datetime.utcnow()` (не traceback); `bulk-precommit` и `layout-precommit` — код 0 внутри git-репозитория (вне репозитория `git diff --cached` падал с кодом 129 — это поведение git, не обработчика); `on-stop` и `post-git-commit-docs-lint` — код 0 | Tracebackов нет ни у одного. В `HOME` ничего не записано. Старые обработчики работают с интерпретатором окружения CLI — §8 «Переход открытых сессий» подтверждён |

## Windows — 2026-10-17

Ноутбук владельца: Windows, Git Bash (bash 5.2.37), uv 0.11.2. Обёртка `hooks/run` и CLI 4.0 —
с ветки `feat/pkg-arch-5-release`, установка в `~/h2t-probe` (`UV_TOOL_DIR`, `UV_TOOL_BIN_DIR`);
подложные `HOME` и `USERPROFILE`. Глобальный h2t-ops 0.2.1 не тронут, `~/h2t-probe` удалён.
Шаги W1 и W4 выполнены дважды: через `claude -p "привет"` и руками в интерактивной сессии
(Claude Code 2.1.302, запущен из PowerShell); результаты совпали.

| проба | команда | что получено | вывод |
|---|---|---|---|
| W1. оболочка хуков | хук `UserPromptSubmit` печатает `$0`, `$SHELL`, `$BASH_VERSION`, `ps -p $$`; второй раз — из PowerShell с PATH без записей `Git` (`Get-Command bash` пуст) | оба раза `0=/usr/bin/bash`, `BASH=5.2.37(1)-release`, `HOME=/c/Users/<user>`, `USERPROFILE=C:\Users\<user>`, ошибок нет | Claude Code находит Git Bash сам, не по PATH; внутри хука `/usr/bin` на PATH (`ps` отработал), значит `bash "…/hooks/run"` находится |
| W2. обёртка без Python | `bash run grade-guard 9` (Stop) и `bash run gather-on-prompt 29` (UserPromptSubmit «привет»), подделка `h2t-hook`, 20 прогонов, три худших | Stop 0.152 / 0.152 / 0.158 с; UserPromptSubmit 0.056 / 0.057 / 0.062 с; вывод пуст, код 0 | бюджет 50 мс на Windows не держится: путь — один `cat` и одно сравнение, остальное — старт bash в Git Bash. Порог Windows 80 мс |
| W3. полная цепочка | то же, `H2T_HOOK` → `h2t-hook.exe` 4.0, `grade-guard` на Stop | холодно (без перезагрузки) 0.313 / 0.212 / 0.214 с; тепло, три худших из 20: 0.199 / 0.205 / 0.229 с; `hooks.jsonl` нет | Stop укладывается с запасом; порог Windows 400 мс (вместо предварительных 600) |
| W4. PATH открытой сессии | `[Environment]::GetEnvironmentVariable('Path','User')`; в сессии Claude Code `echo $PATH`, `command -v` | `~/.local/bin` есть в реестре пользователя и в PATH сессии; `h2t-ops`, `h2t-hook`, `uv` находятся там | если каталог уже на PATH, новые команды видны без перезапуска. Первый `uv tool update-shell` на чистой машине не проверен — для него подсказка `version_check.py` «перезапусти харнесс» |
| W5. раскладка `uv tool dir` | `uv tool dir`, `uv tool dir --bin`, `ls -la`, `cmp`, `uv-receipt.toml` | tool dir `%APPDATA%\uv\tools`, bin `~\.local\bin`; в bin — копии `.exe` (47104 байт), не ссылки, побайтно равны `Scripts/`; в receipt `install-path` — `bin/*.exe` | подтверждает исправление C1: `version --expect` принимает совпадение PATH с записанной точкой входа |
| W6. HOME и USERPROFILE | Git Bash, PowerShell, `Path.home()`, `expanduser('~')`, `cygpath` | везде `C:\Users\<user>`; `~/.h2t` и `$(cygpath -u $USERPROFILE)/.h2t` — одна папка | обёртка (`$HOME`) и Python (`Path.home()`) читают один `~/.h2t` |

## Заметки

- Проба 1: «холодный» включает скачивание управляемого Python 3.12.11 и 51 пакета (в том числе
  onnxruntime, opencv, numpy). Для порога таймаута (Task 9) важен тёплый запуск: 0.13 с для
  `uvx --isolated`; холодный бутстрап в хук не помещается и должен идти через `sync`.
- Проба 2: чтобы получить поломку, понадобился `UV_LINK_MODE=copy`. Это сознательное растягивание
  окна, а не типичные условия; на clone-режиме по умолчанию окно ≈ 0.1 с. Состояние после
  прерывания: каталог `bin/` окружения без `h2t-ops`, симлинки в `UV_TOOL_BIN_DIR` висят. Признак
  для `sync`: запуск `--version` падает с кодом 127 либо `state=updating`.
- Проба 3: версии 3.2.3 (закрепление `v2.15.0`) и 3.2.62 (main) совпадают с пробой 2026-10-16.
- Проба 4: проверена только совместимость исполнения (код выхода, traceback). Содержимое решений
  хуков на реальных данных сессии не сравнивалось. Обработчики с shebang `python3` запускались
  интерпретатором окружения CLI напрямую, а не через `H2T_PYTHON` внутри скрипта.
- `ruff` и 15 путей pytest из CI не запускались: коммит меняет только документы.
- `lint.py doctor`: см. раздел ниже.

## doctor

`lint.py doctor` (код выхода 1 и до отчёта, и после — выходит с 1 при любой находке в репозитории).
База: 9 orphan, 21 naming, 4 structure, 0 metadata, 9 project. С отчётом: 10 orphan, остальное
без изменений. Добавленная находка — один orphan: отчёт не слинкован из `docs/README.md`
(как и прочие отчёты в `docs/reports/`). Ссылку на отчёт добавит `fix-index` или правка индекса;
в рамках этой задачи индекс не менялся.
