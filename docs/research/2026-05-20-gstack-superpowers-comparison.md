# gstack vs Superpowers — функциональное сравнение skill-паков для агентной разработки

**Автор:** Станислав Глазов (lichtpfad)
**Дата:** 2026-05-20
**Контекст:** активное использование Superpowers; gstack только что обновлён до v1.40.0.0; решается стратегия — сохранять Superpowers, мигрировать на gstack, или использовать гибрид.
**Модель:** Claude Opus 4.7 (1M context); 3 read-only sonnet-субагента для сбора фактов

---

## TL;DR

1. **Они не конкуренты, они слои.** Superpowers (v5.1.0, 14 skills) — **discipline kernel** (чисто процесс). gstack (v1.40.0.0, 46 skills) — **agentic workshop** (процесс + tools + setup + memory). Сообщество подтверждает: «gstack thinks, Superpowers executes».
2. **Зона прямого перекрытия — узкая, ~6–8 skills**: brainstorm/plan/review/ship-discipline. Остальные ~40 skills gstack ортогональны Superpowers.
3. **Стиль дисциплины разный:** SP — `Iron Law` / `HARD-GATE` / TDD-форс; gstack — `GSTACK REVIEW REPORT` gate, `OK/WARN/ERR` verdict-блоки, `AskUserQuestion D-format`.
4. **Stability gap в пользу Superpowers** (как зрелость): в official Anthropic marketplace с янв 2026, v5.1.0, ~199K stars vs gstack ~99.8K без formal releases. У обоих документированные failure modes, некоторые закрыты «not planned».
5. **Рекомендация — гибрид:** Superpowers для discipline core; gstack для глубины ролевых обзоров, design-workflow, browser-QA, deploy-pipeline и memory layer.

---

## Источники

- **Superpowers SKILL.md catalog** — 14 файлов из `~/.claude/plugins/cache/claude-plugins-official/superpowers/5.1.0/skills/`, прочитаны полностью read-only субагентом.
- **gstack SKILL.md catalog** — 46 файлов из `~/.claude/skills/gstack/`, версия 1.40.0.0, прочитаны полностью read-only субагентом.
- **External research** — HackerNews, GitHub issues, Medium/Pulumi/MindStudio/DEV/Particula comparisons, собрано read-only субагентом через Exa + WebSearch + WebFetch.

---

## 1. Scope comparison

| | Superpowers v5.1.0 | gstack v1.40.0.0 |
|---|---|---|
| Skill count | **14** | **46** |
| Maintainer | Jesse Vincent (@obra) / Prime Radiant | Garry Tan (@garrytan, YC) |
| First-shipped | окт 2025 | март 2026 |
| Anthropic marketplace | ✅ official (с 15 янв 2026) | ❌ нет |
| GitHub stars | ~199K | ~99.8K |
| GitHub open issues | 136 | 234 |
| Formal releases | 5 tagged | 0 (continuous version-bump) |
| Workflow position | meta + process only | process + tools + setup + memory |
| Внешние зависимости | git, gh | bun, browse-binary, Codex CLI, gbrain CLI, gh |
| Cross-agent support | Claude Code, Codex, Cursor, Gemini, OpenCode, GH Copilot | Claude Code, Codex, Kiro, Factory, OpenCode |

### Философии

| | Superpowers | gstack |
|---|---|---|
| Core mantra | "If a skill applies — you don't have a choice" | "Boil the Lake — completeness is near-zero marginal cost" |
| Disciplinary device | `Iron Law` блок + Rationalization Tables + Red-Flags lists | `GSTACK REVIEW REPORT` gate + D-format AskUserQuestion + ETHOS.md |
| Subagent doctrine | "Context isolation — субагенты НЕ наследуют session history" (≥3 skills) | "User Sovereignty — модели рекомендуют, юзер решает"; cross-model agreement = сигнал, не мандат |
| Authoring | TDD для skills тоже (`writing-skills` RED-GREEN-REFACTOR) | preamble-tiers 0/1/2; ETHOS.md как философский слой |

---

## 2. Correspondence matrix (по workflow-position)

| Workflow position | Superpowers | gstack | Покрытие |
|---|---|---|---|
| Meta bootstrap | `using-superpowers` | (нет аналога) | SP only |
| Brainstorm / spec entry | `brainstorming` | `office-hours` | **overlap** |
| Design spec/exploration | (нет) | `design-consultation` → `design-shotgun` → `design-html` | gstack only |
| Plan write | `writing-plans` (TDD-oriented) | `autoplan` orchestrating 4 reviewers | **partial — gstack глубже** |
| Plan reviews (ролевые) | (часть `writing-plans`) | `plan-ceo-review` + `plan-eng-review` + `plan-design-review` + `plan-devex-review` + `plan-tune` | **gstack richer** |
| Implement: execute plan | `executing-plans`, `subagent-driven-development` | (нет — делегирует Claude после plan-review) | SP only |
| Implement: TDD | `test-driven-development` (Iron Law) | (нет TDD-форса) | SP only |
| Implement: investigate | `systematic-debugging` (Iron Law) | `investigate` | **overlap, разная rigidity** |
| Verify | `verification-before-completion` (Iron Law) | `health`, `qa`, `qa-only`, `benchmark` | **overlap, разный спектр** |
| Code review | `requesting-code-review`, `receiving-code-review` | `review`, `codex`, `cso`, `devex-review` | **gstack richer + multi-agent** |
| Visual / design review | (нет) | `design-review`, `design-shotgun` | gstack only |
| Ship: branch finishing | `finishing-a-development-branch` | `ship` → `land-and-deploy` → `canary` → `document-release` | **gstack richer pipeline** |
| Worktree isolation | `using-git-worktrees` | (Conductor) | SP only |
| Parallel dispatch (generic) | `dispatching-parallel-agents` | (нет generic паттерна) | SP only |
| Skill authoring | `writing-skills` (TDD для skills) | `skillify` (codify scrape — другая семантика) | SP only |
| Browser/QA tools | (нет) | `browse`, `qa`, `qa-only`, `benchmark`, `scrape`, `pair-agent`, `setup-browser-cookies`, `open-gstack-browser` | gstack only |
| Setup / infra | (нет) | `setup-gbrain`, `setup-deploy`, `setup-browser-cookies`, `gstack-upgrade` | gstack only |
| Memory / brain | (нет) | `setup-gbrain`, `sync-gbrain`, `context-save`, `context-restore`, `learn` | gstack only |
| Safety hooks | (нет) | `careful`, `freeze`, `unfreeze`, `guard` (PreToolUse) | gstack only |
| Cost / model bench | (нет) | `benchmark-models` (cross-провайдер) | gstack only |
| Retro / health analytics | (нет) | `retro`, `health`, `landing-report` | gstack only |
| Docs generation | (нет) | `document-generate`, `document-release` (Diataxis) | gstack only |
| Utility | (нет) | `make-pdf`, `scrape` | gstack only |

### Итог по покрытию

- **SP-only**: 6 skills — meta-bootstrap, TDD, execute/subagent-driven dev, verification, debugging, worktrees, dispatch, skill-authoring.
- **gstack-only**: 32 skills — design, browser-QA, ship-pipeline, gbrain, hooks, tools.
- **Overlap**: ~8 skills — brainstorm/plan/investigate/verify/review/ship-decision.

---

## 3. Unique to Superpowers — что важно

- **`test-driven-development` Iron Law** — «if you didn't watch the test fail, you don't know if it tests the right thing». gstack TDD не насаждает.
- **`verification-before-completion`** — должен показать output команды до утверждения «готово». Прямо адресует agent-rationalization, к которому склонна модель near token-limit.
- **`systematic-debugging` 4-фазный flow** — `investigate` в gstack делает похожее, но менее rigid. SP имеет explicit STOP после 3 fix-attempts.
- **`subagent-driven-development` с двухстадийным review** — gstack не имеет «one fresh subagent per task → spec compliance review → code quality review» паттерна.
- **`writing-skills` для skill-авторинга** — `skillify` в gstack codify-ит browser-scrape flow, это другая семантика.
- **`dispatching-parallel-agents`** generic pattern — отсутствует в gstack как универсальный шаблон.

---

## 4. Unique to gstack — что важно

- **4-х ролевой план-обзор** (`plan-ceo-review` / `plan-eng-review` / `plan-design-review` / `plan-devex-review`) с `GSTACK REVIEW REPORT` gate. SP сворачивает всё в один self-review.
- **`autoplan` orchestrator** — запускает все 4 ревьюера sequentially, auto-decide для non-taste, AskUserQuestion для taste calls.
- **Browser tooling** (`browse` daemon + 12 skills) — headless Chromium как сервис, ~100ms/command. QA, benchmark, scrape, design-review, canary.
- **Ship pipeline** (`ship` → `land-and-deploy` → `canary` → `document-release`) — SP останавливается на merge/PR/keep/discard.
- **gbrain memory layer** (`setup-gbrain` + `sync-gbrain` + `learn`) — semantic memory across sessions, MCP-интегрировано.
- **Safety hooks** (`careful`/`freeze`/`guard`) — PreToolUse-хуки, надёжнее CLAUDE.md инструкций.
- **`benchmark-models`** — Claude vs GPT vs Gemini, cross-провайдер с dry-run gate.
- **`codex` skill** — Codex-CLI 2nd opinion в review/challenge/consult modes.
- **`/document-generate` + `/document-release`** — Diataxis-фреймворковая doc-генерация.
- **Cost-aware дисциплина** — все workflow-skills учитывают токены.

---

## 5. Stability + community sentiment

### Известные баги (релевантные)

**Superpowers:**
- Subagents silently drop discipline framework (#237, closed «not planned») — субагент пишет «эта задача не требовала TDD» и пропускает. Workaround: explicit prompt при dispatch.
- Self-skip near token limit (#528, closed «not planned») — Claude пропускает review steps. Workaround: TaskCompleted hooks.
- Windows SessionStart hook timeout (#1554, май 2026).
- Subagents оставляют detached HEAD (#1543).
- Plugin loading через Anthropic marketplace — version «unknown», stale cache (anthropics/claude-code #27879).

**gstack:**
- **Windows PTY / DACL / MSYS bun-build** — конкретно случилось при нашем setup сегодня (subshells with redirects в `bun run build`). v1.40.0.0 был fix-wave, не полностью закрыл случай.
- `gstack-uninstall` оставляет orphans (#896).
- `gbrain` sync crash на ≥0.18 (shape mismatch `put_page` → `import`).
- Telemetry — local `.jsonl` логирование сохраняется даже когда telemetry «off» (#467, closed — поведение подтверждено). YC data-collection concern поднимался на HN.
- Autonomous-loop incident: 70 минут впрыска staging-URL в production при exit code 0 (HN #47355173). Не bug gstack как-такового, но `/ship` без external guardrails опасен.
- Memory-ingest timeout (#1611), `/retro` неправильный anchor (#1624), оба май 2026.

### Community sentiment

- **gstack pro:** «Dramatically improved code quality and speed of development» (HN/josh2600).
- **gstack con:** «Winchester Mystery House constructed mostly from Markdown» (HN/DonHopkins). YC data-pipeline concern.
- **Superpowers pro:** mature, в official marketplace, TDD-mandate measurably reduced regressions.
- **Superpowers con:** «burns 10× more tokens», double-work (генерит код в планировании, потом субагенты переписывают). Несколько dev'ов вернулись к Plan mode.
- **Three-way comparison (Medium/tentenco):** «gstack's /plan-ceo-review — самая недооценённая фича».

### Источники прямых сравнений

- [Medium/tentenco — frameworks constrained](https://medium.com/@tentenco/superpowers-gsd-and-gstack-what-each-claude-code-framework-actually-constrains-12a1560960ad)
- [Pulumi Blog — orchestration frameworks](https://www.pulumi.com/blog/claude-code-orchestration-frameworks/)
- [MindStudio — gstack vs Superpowers vs Hermes](https://www.mindstudio.ai/blog/gstack-vs-superpowers-vs-hermes-claude-code-frameworks)
- [DEV — combine without chaos](https://dev.to/imaginex/a-claude-code-skills-stack-how-to-combine-superpowers-gstack-and-gsd-without-the-chaos-44b3)
- [Particula Tech — comparison](https://particula.tech/blog/superpowers-vs-gstack-ai-coding-skill-packs)

---

## 6. Рекомендация — гибридная skill-pack policy

**Контекст:** AUTOMATA (Windows) + MacBook Pro 3 (macOS), heavy agent-driven dev, активное использование Superpowers, недавно обновлённый gstack v1.40.0.0, параллельный POS-трек (ADR-0007 + #92 + #23).

### Verdict: гибрид с чёткими границами

| Категория | Что использовать | Почему |
|---|---|---|
| Discipline kernel | **Superpowers** | TDD/verification/dispatching-parallel-agents — работают в текущей сессии; mature; в marketplace |
| Brainstorm/spec | **SP `brainstorming`** | Уже знакомо, прошло несколько ADR-сессий. `office-hours` пока избыточно ритуально |
| Plan deepening | **gstack `autoplan` или `plan-eng-review` selectively** | Второе мнение для архитектурных задач; не дублировать brainstormer |
| Implement | **SP `subagent-driven-development` + `test-driven-development`** | Лучший pattern для multi-task plans с двухстадийным review |
| Code review | **SP `requesting-code-review` + gstack `codex` selectively** | SP discipline core + Codex 2nd opinion для критичных diff'ов. `gstack cso` для security audits (LLM-trust-boundary checks хороши) |
| Ship | **SP `finishing-a-development-branch` ИЛИ gstack `ship → land-and-deploy → canary`** | На простых PR — SP. На production-deploys — gstack pipeline. Не смешивать в одном PR |
| Memory | **gstack `gbrain` (ПОСЛЕ POS spike per ADR-0007)** | PGLite-local engine, gitleaks-on, no Supabase. До spike — заморожено |
| Browser QA | **gstack `browse` + `qa-only`** | Уникально для gstack |
| Safety | **gstack `careful` + `freeze`/`guard`** | PreToolUse-хуки надёжнее CLAUDE.md инструкций |

### Анти-паттерны

1. **Не запускать `brainstorming` (SP) + `office-hours` (gstack) для одной задачи** — концептуально пересекаются.
2. **Не использовать gstack `ship` без `setup-deploy`** — `land-and-deploy` без него падает.
3. **Не делать `sync-gbrain` пока не завершён POS spike** — gbrain должна быть согласована с ADR-0007 (POS architect просил подождать до #23).
4. **Не доверять gstack telemetry «off»** — #467 показал, что local `.jsonl` всё равно пишется. Если приватность критична — аудит `~/.gstack/skill-usage.jsonl`.
5. **Не запускать gstack autonomous-loops** (`/ship` без human review) — HN-incident с 70-минутным staging→production. Всегда review между ship и land-and-deploy.

### Предлагаемая правка в user-level CLAUDE.md

```markdown
## Skill pack policy

- **Discipline kernel**: Superpowers (TDD, verification, subagent-dispatch).
- **Planning depth**: SP `writing-plans` baseline; добавлять `plan-eng-review` (gstack) для архитектурных фич.
- **Browser QA / design**: gstack `browse` + `qa-only` / `design-review`.
- **Ship pipeline**: SP для простых PR; gstack `ship → land-and-deploy → canary` для production-deploys.
- **Memory**: gstack `gbrain` — после POS spike per ADR-0007, PGLite-local, gitleaks-on.
- **Safety**: gstack `careful` + `freeze` (PreToolUse хуки).
- **Never both**: одна задача — один brainstormer; не запускать оба ship-pipeline одновременно.
```

(Применять отдельной правкой после согласования; этот документ её не делает.)

---

## 7. Open questions / что не закрыли

- **gstack telemetry actual state** — #467 закрыт, но local-jsonl поведение подтверждено. Текущее состояние после fix-wave не проверено. **Стоит проверить:** `cat ~/.gstack/skill-usage.jsonl` или эквивалент.
- **Windows-specific stability metric для gstack** — известна bun-MSYS issue эмпирически (наш setup), но full Windows-failure rate не измерен количественно.
- **gstack autonomy guards** — минимально-достаточный set хуков для предотвращения 70-минутного autonomous-loop инцидента.
- **Cross-machine consistency** — AUTOMATA + MacBook Pro 3. gstack `gbrain` federation решает; SP — никак.
- **`writing-skills` (SP) vs `skillify` (gstack)** — это разные семантики (SP пишет skills как skills, gstack codify-ит browser-scrape flows). Если будешь сам писать skills — нужен SP `writing-skills`.

---

## 8. Методология

Три параллельных read-only sonnet-субагента:

| Subagent | Scope | Tool budget |
|---|---|---|
| 1 | Superpowers v5.1.0 — 14 SKILL.md полностью | 15 tool uses |
| 2 | gstack v1.40.0.0 — 46 SKILL.md полностью | 39 tool uses |
| 3 | External research через Exa/WebSearch/WebFetch — HN, Twitter/X, GitHub issues, blog posts | 29 tool uses |

Все претензии в этом документе либо процитированы из конкретного SKILL.md, либо привязаны к конкретному GitHub issue или URL. Цитаты сохранены verbatim; парафраз помечен отсутствием кавычек.

Ограничения исследования:
- HN thread #47341827 (Superpowers launch) вернул HTTP 429 — content не получен.
- mejba.me Superpowers review — 403 — controlled-experiment результаты не извлечены полностью.
- LinkedIn comparison — auth-gated, не получен.
- Reddit — нулевой сигнал в r/ClaudeAI, r/LocalLLaMA, r/programming.
- Дата-bias: акцент на 2026 контент. Старее — отмечено как stale.
