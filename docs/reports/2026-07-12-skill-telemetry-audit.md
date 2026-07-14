# Skill Telemetry Audit — map & gaps (2026-07-12)

Состояние телеметрии скиллов h2t-skills против контракта h2t-evals. Фаза 1: **карта + гэпы**
(без дизайна таксономии — он ниже по течению от контракта, делается отдельным проходом).
Продолжение #289 (h2t-evals задеплоен, простаивает). Связано с PR #304 (eval fallback degradation).

## 0) Scope-решение оператора (2026-07-12)

- **В фокусе:** script-backed скиллы (есть Python-вход → `SkillEval` встраивается напрямую).
- **Поток 2 / deferred:** prompt-only скиллы (creative, diagram-node, node-researcher, dev-overview,
  snap, github-issues, pre-merge-check, lesson-parser) — ценность телеметрии сейчас неочевидна,
  отложено. Механизм для них (hook-lifecycle / LLM-judge) проектируется позже, если понадобится.

## 1) Контракт h2t-evals (авторитетный источник, не изобретаем)

Из `C:/dev/h2t-evals/docs/client/integration-standard.md` (§5, §6, §7, §12) и
`skill-integration-plan.md` (§3.2, §4). Править контракт нельзя (repo-boundary) → issue в h2t-evals.

### 1.1 Обязательные поля сессии
Док-стандарт §5 заявляет: `repo, framework, source, host, branch, commit, run_env, eval_set_id`.
**Verify против реализации** (`h2t-evals/src/h2t_evals/constants.py:REQUIRED_SESSION_FIELDS`): фактически
ingest требует `repo, framework, source, host, run_env, eval_set_id, schema_version, sdk_version,
metric_set_version, client_event_at`. **`branch`/`commit` в required НЕ входят** — дрейф doc-vs-code
на стороне h2t-evals (док строже реализации). Поля `schema_version/sdk_version/metric_set_version/
client_event_at` SDK проставляет сам (`sdk.py:432-448`) → наш push проходит required-валидацию.

### 1.2 Обязательные `core.*` метрики по уровням
| Уровень | Метрика | Тип |
|---|---|---|
| unit | `core.tool_call_success_rate` | num |
| unit | `core.op_type_correct_rate` | num |
| integration | `core.task_success` | bool |
| integration | `core.time_to_first_valid_ms` | num (ms) |
| business | `core.deflection_rate` (или документированный эквивалент) | num |

### 1.3 Custom-метрики
- Именование `<repo>.<name>`; уровень + тип + агрегация + описание.
- **Регистрировать до первого использования** (no silent schema drift), без коллизий с `core.*`.

### 1.4 eval_set по классу скилла (план §3.2)
- gather (`session-start`, `handoff`, `init-project`) → `skills-gather-baseline-v1`
- integration scripts (connectors, transcripts, drawio, docs-*) → `skills-integration-baseline-v1`
- prompt-only → `skills-prompt-baseline-v1`

### 1.5 Repo-ассеты (стандарт §4, обязательные)
`evals/repo.toml`, `evals/unit_cases.jsonl`, `evals/integration_cases.jsonl`, `evals/business_kpi.toml`.
Опционально: `custom_metrics.toml`, `eval_notes.md`. Гейт: `h2t-evals validate-repo` (§10).

### 1.6 Prompt-only → LLM-as-Judge (стандарт §12) — механизм для потока 2, не SkillEval.

## 2) Наша сторона — текущее состояние

### 2.1 Что реально эмитит телеметрию (единственные прод-вызовы `SkillEval`)
| Точка | Файл | Эмитит |
|---|---|---|
| gather | `lib/cli/main.py:102` | `skills.gather_source_success_rate`, `skills.token_consumption` + core.* заглушки |
| handoff | `plugins/h2t-core/skills/handoff/scripts/writer.py` | через gather-путь |
| session-start | `plugins/h2t-core/skills/session-start/scripts/gather.py` | через gather-путь |

Живое покрытие ≈ **только gather-стек** (Wave 1 плана, частично).

### 2.2 Инвентарь по code-seam (script-backed — кандидаты потока 1)
| Класс (eval_set) | Скиллы с Python-входом | Инструментирован |
|---|---|---|
| gather | session-start, handoff, init-project | session-start, handoff |
| gather/core | scaffold-project, project-audit, setup, agent-profile, autonomous-run | ❌ |
| integration | connectors, drive, meetgeek, research, telegram (ops) | ❌ |
| integration | docs-lint, docs-init, docs-index, docs-cleanup, docs-sync-labels, milestone-closure | ❌ |
| integration | drawio (generate/export) | ❌ |
| integration | convert-meeting-transcript, process-transcripts, youtube-transcript (edu) | ❌ |
| legacy `h2t` plugin | calendar, daily-brief, gmail, notion, telegram | ❌ (мигрируют в ops) |

Нюанс измерения: у `research`/`connectors` код есть, но ценность в оркестрации (LLM), а не в CLI —
инструментирование скрипт-входа ловит лишь под-операцию, не полный скилл-инвокейшн.

## 3) Реестр гэпов (конкретные, верифицируемые)

| # | Гэп | Факт / место | Severity |
|---|---|---|---|
| G1 | `branch`/`commit` не шлются в push | `session.py:197-205` — `EvalSession(...)` без полей → шлётся `None`. Ingest **НЕ** отвергает (не в `REQUIRED_SESSION_FIELDS`), но git-провенанс NULL → нельзя коррелировать сигнал с версией кода | P3 (data quality, не блокер) |
| G2 | `core.*` кроме `task_success` захардкожены | `session.py:210-213` — `time_to_first_valid_ms=0.0`, `op_type_correct_rate=1.0`, `tool_call_success_rate=1.0/0.0` | P2 (мусорный сигнал) |
| G3 | `repo` устарел | `evals/repo.toml:1` `repo="claude-agent-skills"`, framework уже `h2t-skills` | P2 |
| G4 | Нет case-файлов | нет `unit_cases.jsonl` / `integration_cases.jsonl` / `business_kpi.toml`; `evals/manifests/` пуст → `validate-repo` не пройдёт | P2 |
| G5 | Объявлена, не эмитится | `skills.checklist_compliance` в repo.toml — нет кода-эмиттера | P3 |
| G6 | Дрейф eval_set | код: единый `skills-session-baseline-v1`; план §3.2: по классу | P2 (решить до масштабирования) |
| G7 | Custom-метрики не зарегистрированы централизованно | `skills.*` эмитятся; регистрация через `/v1/admin/metric-defs` (§7) не подтверждена | P2 |
| G8 | 3-way дрейф repo-identity | `repo.toml`+CI(`evals.yml:55`)=`claude-agent-skills` (устарел); runtime push `repo=self.project`=`agent-skills` (`main.py:73,102`→`session.py:197`); GitHub=`h2t-skills`. Runtime **не читает** repo.toml. **Живая регистрация в central DB = `agent-skills`** (токен + metric-defs, #289 2026-07-11). Решение: ре-бренд → `h2t-skills` (§4.3), с переоформлением на VPS | P2 |
| G9 | Легаси `record_eval` вестижиал ×3 | `lib/gather/eval.py` (+ plugins/h2t, plugins/h2t-core) хардкодит `repo="claude-agent-skills"` + namespace `claude-agent-skills.*`; экспортируется в `gather/__init__.py`, но **живого вызова в проде нет** (вытеснено `SkillEval`). Наследие gather-framework 2026-03-25 | P3 (cleanup) |
| G10 | Устаревший `SKILL_GRAPH_DIR` | несколько SKILL.md (session-start:161, handoff:219, github-issues:112) указывают на `C:/dev/claude-agent-skills/lib` — путь не существует (репо теперь `C:/dev/h2t-skills`) | P3 (отдельный баг, не телеметрия) |

### 3.1 Различение по advisor: «не измерить здесь» vs «не реализовано»
- `time_to_first_valid_ms`, `tool_call_success_rate` — **session/harness-факты**; один Python-CLI-вызов
  (gather) их физически не наблюдает. Их место — hook-уровень, не `SkillEval` внутри скрипта.
  → не «дозаполнить заглушку», а «другой слой инструментирования».
- `op_type_correct_rate` (валидность выходной схемы) — **измеримо в коде** (JSON parseable / ключи есть)
  → это «не реализовано», можно наполнить в script-backed.

## 4) Решения оператора (2026-07-12)

1. **eval_set:** ✅ **по-классу** (`skills-gather/integration/prompt-baseline-v1`) — план §3.2. Требует правки кода (сейчас единый `skills-session-baseline-v1`) + repo.toml.
2. **Слой измерения:** ✅ **три слоя разведены** (не одно):
   - Слой 1 — `SkillEval`(script): детерминизм скрипта (успех/фейл, длительность, schema-валидность, **стоимость** своих API-вызовов, source success). Операционный сигнал.
   - Слой 2 — harness-hook (PreToolUse/PostToolUse/Stop на `Skill`): session-факты (`tool_call_success_rate`, `time_to_first_valid_ms`, последовательность tool-call). Сюда переезжают захардкоженные `core.*` (G2, часть «не измерить в скрипте»).
   - Слой 3 — LLM-judge над `*_cases.jsonl`: **качество работы модели**. Пассивная телеметрия качество не меряет — только judge. Отдельный workstream, точечно.
3. **repo identity:** ✅ **переименовать в `h2t-skills`** — осознанный ре-бренд (матч с GitHub-репо). ⚠ **НЕ дёшево** (первая оценка «пусто» опровергнута primary-source): память #289 / спайк 2026-07-11 — на проде **уже** выданы токены (`agent-skills`-scoped `5825074f…` + wildcard-writer `0f28fa99…`) и зарегистрированы metric-defs `owner=agent-skills`. Runtime сейчас шлёт `repo=agent-skills` (=project.id), что **совпадает** с этой регистрацией; `claude-agent-skills` в repo.toml/CI — устаревший выброс. Ре-бренд в `h2t-skills` → переоформить токен + metric-defs на VPS (h2t-evals-платформа, issue туда), осиротить `agent-skills`, декуплить runtime `repo` от project.id. Отдельная TDD-задача, §6. (`canonical_lineage`→h2t-skills — про session-lineage practice-harvest, НЕ evals-ключ; не путать.)
4. **Поток 2 (prompt-only):** отложено. Механизм — judge (слой 3), не телеметрия. Активировать точечно, если появится нужда + эталонные кейсы.

## 5) Открытый вопрос для следующей фазы (таксономия)

«Какие метрики кроме success» — отвечать парами **metric → consumer** (CI-gate / judge / prioritization),
не плоским списком. Метрика без решения, которое она питает, = шум. Кандидаты-потребители из контракта:
CI-гейты (§10, unit/integration thresholds), judge-скоринг (§12), business-KPI (non-blocking, §10).
Реконсиляция: `research` уже рекламирует «transparent telemetry + cost logging» — проверить, где cost
логируется сегодня (может быть второй сигнал мимо `SkillEval`, точка стыковки, а не greenfield).

## 6) Следующие шаги
- [x] Чек-ин с оператором по развилкам §4 (решения зафиксированы 2026-07-12).
- [ ] **Rename-задача (TDD)** repo-identity → `h2t-skills`, когерентно по поверхностям: `evals/repo.toml`, `.github/workflows/evals.yml:55`, runtime push-источник (декуплить evals-`repo` от `project.id`: SkillEval получает явный `repo="h2t-skills"`, project.id `agent-skills` НЕ трогать — он завязан на session/handoff/activity registry), легаси `record_eval` ×3 (G9 — переименовать или удалить вестижиал).
  - **VPS-предусловие (h2t-evals-платформа, issue туда / оператор):** переоформить токен + metric-defs с `owner=agent-skills` на `h2t-skills`; ретайр `agent-skills`-токены (`5825074f…`, `0f28fa99…`). БЕЗ этого push под `h2t-skills` → `403 E_REPO_TOKEN_MISMATCH` / `400 E_METRIC_NOT_REGISTERED`.
- [ ] Фаза 2: таксономия метрик (metric→consumer) + eval_set-по-классу + модель синка. Развести слой 1 (SkillEval) / слой 2 (hook) / слой 3 (judge-cases).
- [ ] Repo-ассеты (G4): `unit_cases.jsonl`, `integration_cases.jsonl`, `business_kpi.toml` → `validate-repo` зелёный.
- [x] Issue(s) в h2t-skills на G2–G10 (2026-07-12): **#305** (identity G3+G7+G8), **#306** (core.* G2), **#307** (repo-ассеты G4), **#308** (checklist_compliance G5), **#309** (eval_set по-классу G6), **#310** (record_eval cleanup G9), **#311** (SKILL_GRAPH_DIR G10). Все дети #289.
- [ ] Issue в h2t-evals (repo-boundary): дрейф doc-vs-code §1.1 (branch/commit заявлены обязательными, но не в `REQUIRED_SESSION_FIELDS`) — НЕ заведён, на усмотрение оператора.

## 7) Локальная конфигурация push (gate 3, #321)

`SkillEval` резолвит креды из `~/.dor/secrets.env` (env-переменные процесса выигрывают
над файлом; `_load_secrets`, обе копии `session.py` — parity-guard
`tests/core/test_eval_session_parity.py`). Один merged-env кормит и `resolve_mode()`,
и `_send_central`. Чтобы включить локальный push, добавь в `~/.dor/secrets.env`:

```
H2T_EVALS_ENABLED=1                                  # рычаг активации — ставить последним (после #321+#99+gate 4)
H2T_EVALS_SERVICE_URL=https://evals.lichtpfadstudio.com   # confirmed live (evals.h2t.ai / evals.hou2touch.ai = DNS-fail, миграция не завершена)
H2T_EVALS_TOKEN=<h2t-skills-scoped token>            # доставлен локально (в GH-secret бесполезен рантайму); токен ротирован evals-стороной
```

Опционально: `H2T_EVALS_SPOOL`, `H2T_EVALS_RUN_ENV` (любой `H2T_EVALS_*` ключ подхватывается по префиксу).
Статус: `h2t-ops evals status` (дефолтный view мержит файл — покажет `push`, когда креды на месте).

**Всё ещё блокирует live push:** h2t-evals#99 (в лёгком venv `~/.h2t/venv`
`import h2t_evals.sdk` → `ModuleNotFoundError: psycopg`; `_send_central` глотает ImportError → no-push).
Фикс — h2t-evals PR #109 (lazy-load через PEP 562); go-live = мердж #109 (editable-pth venv, reinstall не нужен).
Config-wiring (эта секция) тестируется без live-SDK и от #99 не зависит.

**Go-live порядок:** #321 (этот PR) → мердж h2t-evals#109 → gate 4 (потребитель данных) → флип `H2T_EVALS_ENABLED=1`.

- **Gate-4 consumer (phase 1):** `h2t-ops evals report` — local per-skill health
  (success/fallback/error/duration + regression + coverage-gap). Spec/plan:
  `docs/superpowers/{specs,plans}/2026-07-14-evals-telemetry-consumer-phase1.md`.
