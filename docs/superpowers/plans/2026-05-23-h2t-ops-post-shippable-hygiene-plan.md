---
title: "H2T-ops Post-Shareable Hygiene Runbook"
status: "draft"
date: "2026-05-23"
milestone: ""
---
# H2T-ops Post-Shareable Hygiene Runbook

**Date:** 2026-05-23  
**Owner:** h2t-skills  
**Scope:** закрытие #148 и подготовка к #85 после завершения shareability-гейта.

## Цель

Закрыть два обязательных стабилизирующих пункта после PASS:

1. **#148 Security / Dev Hygiene**
2. **#85 CI / platform assumptions hygiene**

Ключевая рамка: ничего не делаем в `h2t-ops` как "новые функции" до того, пока runtime не стабилен в чистой установке.

## Acceptance Criteria (критично)

- Известно и зафиксировано, где хранятся machine-local конфиги, и они не являются repo policy.
- Никаких новых `@latest` runtime-запусков без явного pin/замены.
- Нет "тупых" зависимостей от конкретного пути пользователя в tests/runtime.
- CLI/smoke команды выполняются одинаково по смыслу на Windows/macOS (Windows-специфичные пути — явно оговорены как skip).
- После каждого шага остаётся runnable rollback и чистый re-run без ручного редактирования репозиторных файлов.

## Текущий статус

- Shareability для #161 уже закрыт.
- Осталось выполнить:
  - #148 (security/dev hygiene),
  - затем #85 (CI/platform assumptions).

## Шаг 1 — #148 (Security / Dev Hygiene) execution

### 1.1 Что аудируем (локально, readonly)

- Проверить использование `@latest` в tooling/скриптах:
  - `h2t_ops/*`
  - `scripts/*`
  - `.claude-plugin/*`
- Проверить tracked конфиги на локальные следы:
  - `**/.claude/settings*.json`
  - `**/.claude-plugin/*.json`
  - `**/permissions*.json`
- Проверить наличие machine-local файлов в репо: токены, сессии, `.env`, `latest.json` с персональными абсолютными путями.
- Проверить destructive-команды:
  - какие из них в skill-docs требуют confirm;
  - где есть default-поведение без guard.

### 1.2 Что фиксим

- Вынести/ограничить не-репозиторный state как local/не trackable.
- Оставить только repo-policy конфиги и явные allow/deny для плагина.
- Везде где есть `npx ...@latest` — либо pin, либо explicit justification и follow-up.
- Обновить docs: где именно нужны ручные пермишены и почему.

### 1.3 Command proof (обязательный)

На clean runtime (Windows + macOS if available):

- `uv.exe run pytest tests/connectors tests/core -q`
- `uv.exe run pytest tests/core/test_setup.py -q`
- `uv.exe run pytest tests/h2t_dev/...` (если релевантно в вашем контексте)
- `h2t-ops --help`
- `h2t-core:setup doctor --json`
- `h2t-core:setup connectors-check --json`
- `h2t-ops connectors list --json`

Задача для этого шага: доказать PASS без локальных ручных настроек.

## Шаг 2 — #85 (CI / Unit-test hygiene) execution

### 2.1 Что очищаем

- Скрытые зависимости на конкретный shell/venv/путь:
  - `bash` assumptions в Windows,
  - `python`/`uv` hardcoded paths,
  - `poetry`/`pip` без изоляции.
- Непосредственно в tests:
  - явные skips с причинами,
  - явные XFAIL-сеты,
  - отсутствие неочевидных side-effects.
- Единый matrix для smoke/CI:
  - Windows,
  - macOS,
  - локальная clean-установка.

### 2.2 Проверка после правок

- `uv.exe run pytest tests/core tests/connectors tests/plugin -q`
- Проверка на macOS через тот же smoke matrix (#166 style).
- Обновить evidence для CI assumptions: что работает always, что skip'ится по OS, что требует ручного входа.

## Шаг 3 — Evidence lock & roadmap lock

По завершении:

- Обновить:
  - `docs/reports/2026-05-23-h2t-ops-shippable-evidence.md`
  - `docs/h2t-ops-roadmap.md`
- Проставить:
  - #148: Done/blocked + blocker root causes,
  - #85: Done/blocked + blocker root causes,
  - переход в maintenance mode или новый backlog.

## Риск register

- Перерывные failures локальных Python/uv runtimes (сейчас уже ловили в одной clean-сессии).
- Path-based assumptions (Windows-only env vars) в тестах и setup.
- Неполное разграничение repo policy vs machine-local.

## Что считаем success

- После PASS этих двух шагов:
  - #148 и #85 либо закрыты;
  - либо зафиксированы как follow-up blockers с конкретными issue links и командами-ремедициями.
  - и не блокируют дальнейшую продуктивную работу с #82/#145/#146/#81.
