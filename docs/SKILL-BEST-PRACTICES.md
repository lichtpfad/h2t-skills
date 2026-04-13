# Skill Best Practices — Knowledge Index

*Last updated: 2026-04-12 · Source: 12 experiments, March–April 2026*

---

## Ключевые эмпирические выводы

- **Linear pipeline = единственный способ гарантировать GATE execution.** Каждый шаг зависит от предыдущего — Claude не может перепрыгнуть. Hooks и systemMessage-инструкции GATE не обеспечивают.
- **Description = только trigger conditions, никогда workflow summary.** Description читается до загрузки SKILL.md и влияет на первоначальный паттерн. Workflow в description → Claude импровизирует по training data.
- **Hooks доставляют данные, но НЕ контролируют поведение.** `systemMessage` из Pre/PostToolUse hook надёжно инжектирует данные. Инструкции в том же systemMessage — игнорируются.
- **Конкретные bash-команды в SKILL.md подавляют импровизацию.** Gmail-style CLI pattern (`$CLI list`, `$GATHER --cwd`) даёт Claude "готовый способ" — manual gather не запускается. Работает даже если Claude не выполняет команду.
- **Запреты ("do NOT") игнорируются — работают только позитивные инструкции.** "НЕ запускай git", "НЕ дополняй данные" = ignored. Единственный обход: hookify block на harness-уровне.
- **Scripts работают только для того, что Claude не умеет нативно.** Внешние API (Gmail, Notion, OAuth) → Claude охотно запускает скрипт. Нативные capabilities (git, gh) → скрипт игнорируется, Claude делает по-своему.

---

## Артефакты в этом репо

| Файл | Что содержит |
|------|-------------|
| `docs/research/2026-03-31-hook-injection-vs-skill-instructions.md` | 12 экспериментов, сводная таблица, трёхслойная модель L1/L2/L3 |
| `docs/superpowers/specs/2026-03-30-skill-architecture-vision.md` | L1/L2/L3 архитектура, анализ 26 скиллов, hook как мост |
| `docs/superpowers/specs/2026-04-03-skills-v3-architecture-design.md` | Skills v3: eval-first, department split, activity stream, живой документ |
| `docs/superpowers/specs/2026-04-06-skill-intelligence-graph-design.md` | Skill Intelligence Graph: `skill-patterns` + `skill-lessons` sources, GEPA batch |

---

## Публичный gist

Резюме экспериментов и выводов (EN):
https://gist.github.com/lichtpfad/faae653dede9b61b85ae587c0bf3b669

---

## Внешние best practices (Anthropic plugins)

| Файл | Ключевые паттерны |
|------|------------------|
| `plugin-dev/skills/skill-development/SKILL.md` | Canonical skill anatomy, progressive disclosure, description optimization |
| `skill-creator/skills/skill-creator/SKILL.md` | TDD eval loop, description-first design, failing-test gate |
| `superpowers/skills/writing-skills/SKILL.md` | "No skill without failing test", CSO (Context → Steps → Output) format |

---

## Skill Knowledge Graph (live API)

| Компонент | Значение |
|-----------|---------|
| API | `https://graphs.lichtpfadstudio.com` |
| Sources | `skill-patterns` (best practices), `skill-lessons` (что сломалось + как починили) |
| Client | `lib/skill_graph/client.py` |
| GEPA batch | `lib/skill_graph/gepa_batch.py` |
| Tokens | `~/.dor/secrets.env` |

---

## DOR Handoff-ы

| Файл | Тема |
|------|------|
| `~/.dor/sessions/automata/claude-agent-skills/agent-skills-hook-research-2026-03-31.md` | Hook injection research — итоги 12 экспериментов |
| `~/.dor/sessions/automata/agent-skills/personal-os-agent-skills-skill-graph-2026-04-07.md` | Skill Intelligence Graph — дизайн и bootstrap |
