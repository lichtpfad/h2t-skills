# h2t-ops Shippable + Shareability Plan

**Date:** 2026-05-23  
**Owner:** h2t-skills  
**Scope:** финальная стадия закрытия connector migration и переход к shareable setup  
**Issue context:** #161 закрыт (PR #165), #148/#85 как стабилизирующие follow-up

## Цель

Сделать этап **shippable** подтверждённым для нового пользователя (Windows + macOS путь, если доступен
Claude Code), зафиксировать минимальный shareability pack и зафиксировать его в отчёте.

Ни в коем случае не меняем бизнес-границы:
- `h2t-ops` остается провайдерным слоем;
- POS/DOR/canonical state остаются вне `h2t-ops`;
- `h2t-ops:research` и `h2t-ops:daily-brief` остаются отдельными скиллами.

## Definition of Done

- Clean-install/shippable gate пройден в отдельном чистом окружении (Windows + Mac, если доступен Claude Code), и:
  - `h2t-ops` доступен через установленный плагин без ручной донастройки файлов репозитория;
  - в `/context` присутствуют ровно эти `h2t-ops`-скиллы:
    - `h2t-ops:connectors`
    - `h2t-ops:research`
    - `h2t-ops:daily-brief`
  - `h2t-core:setup doctor` и `h2t-core:setup connectors-check` проходят без ошибок;
  - `uv` + CLI `h2t-ops` запускаются и отдают ожидаемый output без ручного редактирования путей;
  - в evidence записаны все команды с exit code и timestamps.
- Есть reproducible evidence-пакет (timestamps, raw output path, exit codes, observed signal) в
  `docs/reports/2026-05-23-h2t-ops-shippable-evidence.md`;
- Есть rollback-path и инструкции по shareability в отдельном отчёте.

#### DoD-acceptance (не двусмысленно)

- PASS только если все пункты выше выполнены в каждом из средовых сценариев (Windows и доступный macOS).
- Любой FAIL блокирует переход к следующему этапу плана.

### Hard-fail conditions (не допускаются)

- Любой из шагов acceptance gate вернул exit code != 0 или невалидный JSON при `--json` командах.
- `/context` содержит отдельные скиллы `calendar`, `gmail`, `notion`, `telegram`, `drive`, `meetgeek`
  или отсутствует хотя бы один из целевых `h2t-ops:*`.
- `h2t-core:setup doctor` / `h2t-core:setup connectors-check` возвращают статус `degraded`, `failed`, `error`.
- Отсутствуют timestamp/log/raw output в evidence после прогона.
- `h2t-ops`/`uv` запускаются только из локального repo-редакционного окружения, но не как самостоятельный install.

### Acceptance policy

- Проваливается первый неуспешный этап — дальнейший прогон остановлен.
- Повторный проход запускается после устранения причины (issue или fix), все артефакты прогона перезаписываются.

---

## 0) Evidence contract (обязателен)

Нужно создавать единый evidence-файл в конце каждой прогона:

- `docs/reports/2026-05-23-h2t-ops-shippable-evidence.md`

Минимальный формат записи:

```markdown
- run_id: "YYYYMMDD-HHMM-<os>"
- environment:
  - os: Windows|macOS
  - machine: ...
  - claude_user: ...
- command_runs:
  - command: "..."
    expected_exit: 0
    exit_code: 0
    started_at: "ISO8601"
    finished_at: "ISO8601"
    output_path: "path/to/raw/output.log"
    expected_signal: "json.kind=... / text pattern"
    observed_signal: "..."
    status: PASS|FAIL
    failure_root_cause: ""   # только если FAIL
- context_inventory:
  - timestamp: "ISO8601"
  - observed_h2t_ops_skills:
    - "h2t-ops:connectors"
    - "h2t-ops:research"
    - "h2t-ops:daily-brief"
  - has_only_target_ops_skills: true|false
- result: PASS|FAIL
- notes:
  - follow_up_issue: "#..."
```

Любой fail фиксируется отдельным item-ом с root cause и follow-up #.

---

## 1) Текущее подтверждение baseline (в репозитории)

**Файлы/состояние:**

- `plugins/h2t-ops/.claude-plugin/plugin.json` (`version: 1.2.5`)
- `plugins/h2t-core/.claude-plugin/plugin.json` (`version: 3.1.10`)
- `plugins/h2t-ops/skills/` сейчас:
  - `connectors`
  - `daily-brief`
  - `drive`
  - `meetgeek`
  - `research`
  - `telegram`

- [ ] Зафиксировать это baseline в локальном отчёте перед началом этапа.
- [ ] Зафиксировать статус legacy-папок в `plugins/h2t-ops/skills`:
  - `drive`, `telegram`, `meetgeek` могут оставаться только artifact dirs без `SKILL.md`;
  - если любой из них снова получает `SKILL.md`, это blocker до решения последствий `#161`.

Команда для фикса:

```powershell
Get-ChildItem -Path "plugins/h2t-ops/skills" -Directory | Select-Object -ExpandProperty Name
Get-Content plugins/h2t-ops/.claude-plugin/plugin.json
Get-Content plugins/h2t-core/.claude-plugin/plugin.json
```

---

## 2) Re-Run shippable smoke for installed surface (чистая проверка)

### 2.1 Acceptance matrix

| # | Command | Environment | Expected exit | Evidence signal |
|---|---------|-------------|--------------|-----------------|
| 1 | `h2t-core:setup doctor --json` | Claude CLI | `0` | JSON ключ `kind=h2t_setup_v1` + `h2t-core.status=ready` |
| 2 | `h2t-core:setup connectors-check --json` | Claude CLI | `0` | JSON с каждым коннектором в `ready`/`live-check skipped` |
| 3 | `h2t-core:setup doctor` | Claude CLI | `0` | итоговая выдача без traceback/ошибок |
| 4 | `h2t-ops --help` (`uv.exe run h2t-ops --help` в terminal) | terminal | `0` | вывод содержит `usage` |
| 5 | `h2t-ops connectors --help` (`uv.exe run h2t-ops connectors --help`) | terminal | `0` | вывод содержит `connector` subcommands |
| 6 | `h2t-ops connectors list --json` | terminal | `0` | JSON parseable, list non-empty |
| 7 | `h2t-ops research preflight --json` | terminal | `0` | JSON содержит readiness-флаг для research provider |
| 8 | `h2t-ops daily-brief --help` | terminal | `0` | usage text without traceback |

Если `--json` команда возвращает exit 0, но ожидаемый signal отсутствует/невалиден — статус FAIL.

### 2.2 Минимальная проверка inventory (hard requirement)

- [ ] `/context` показывает только целевые скиллы `h2t-ops:*`:
  - `h2t-ops:connectors`
  - `h2t-ops:research`
  - `h2t-ops:daily-brief`
- [ ] В `/context` отсутствуют отдельные legacy-скиллы `calendar`, `gmail`, `notion`, `telegram`, `drive`, `meetgeek`.
- [ ] `/context` output сохранен в evidence с timestamp и raw path.

---

## 3) Clean-install validation for a new user (shareability pack gate)

Это **обязательный** шаг перед закрытием shippable:

- [ ] На другом ПК/чистой сессии убрать локальные версии и кэш/вендорные артефакты для h2t.
- [ ] Установить только публичный путь поставки:
  - `/plugin marketplace update`
  - `/plugin uninstall h2t-core@lichtpfad` (если установлен как локальный pinned)
  - `/plugin uninstall h2t-ops@lichtpfad` (если установлен legacy)
  - `/plugin install h2t-core@lichtpfad`
  - `/plugin install h2t-ops@lichtpfad`
  - `/reload-plugins`
- [ ] Прогнать п.2 acceptance matrix полностью.
- [ ] Зафиксировать, что базовый доступ работает без ручных изменений в проектах/репозитории.

Windows clean-install command set:

- [ ] `h2t-core:setup doctor --json` — pass
- [ ] `h2t-core:setup connectors-check --json` — pass
- [ ] `uv.exe run h2t-ops --help` — pass
- [ ] `uv.exe run h2t-ops connectors list --json` — pass
- [ ] `uv.exe run h2t-ops research preflight --json` — pass
- [ ] `/context` показывает только 3 h2t-ops skills
- [ ] `/context` output archived как `context_inventory_windows_...`

macOS clean-install set (если есть `h2t`/Claude CLI на mac):

- [ ] повторить те же шаги с командным форматом без `.exe`:
  - `h2t-ops --help`
  - `h2t-ops connectors list --json`
  - `h2t-ops research preflight --json`
- [ ] зафиксировать, что `/context` inventory совпадает с Windows профилем.
- [ ] зафиксировать отсутствие Windows-only зависимости путей.

### 3.1 Shareability evidence output

- [ ] В `docs/reports/2026-05-23-h2t-ops-shippable-evidence.md` добавить секцию с `PASS/FAIL` для каждого запущенного шага.
- [ ] Для любого FAIL добавить `failure_root_cause` и привязку к follow-up.

---

## 4) Создать Shareability Pack report (шаг сразу после gate)

- [ ] Обновить/создать отдельный `shareability` инструктаж (`docs/reports/2026-05-23-h2t-ops-shippable-shareability-report.md`):
  - Windows + macOS quickstart
  - что входит/не входит в install (credentials, POS state, vault, etc.)
  - concrete assumptions по версиям плагинов и зависимостей
  - rollback path (что удалять при clean переустановке)
  - commands smoke + ожидаемые выходы и коды выхода + evidence_path
  - known external dependencies (creds/session files, paid checks)

---

## 5) Завершение roadmap + коммуникация

- [ ] Обновить `docs/h2t-ops-roadmap.md`:
  - connector migration закрыта (статус: `done`),
  - новый статус: `shippable-shareability next gate`.
- [ ] Прописать в issue/отчёте:
  - что #161 закрыт через PR #165
  - что дальше в порядке: `#148 -> #85 -> research backlog`.

## 6) Критический путь после этого эпика

1. Если clean install gate пройден — закрыть shippable и дать POS handoff.
2. Далее только стабилизирующие задачи:
   - `#148` (security/dev hygiene) — если новые риски обнаружены,
   - `#85` (CI/platform assumptions),
   - затем research/product backlog по приоритету.

## Примечание по исполнению

Для этого этапа использовать:
- `superpowers:writing-plans` для планирования
- `superpowers:subagent-driven-development` для верификационных подзадач (по одному подзадачному шагу)
