---
title: "Текст issue в rejuve: ключи из secrets/shared после h2t 4.0"
status: "draft"
date: "2026-10-18"
---

Черновик issue для репо rejuve (spec #548 §9; план R26). Этот репо issue не заводит:
заведение — Task 26, шаг владельца. Правка — сторона rejuve
(`.claude/rules/repo-boundary.md`).

**Заголовок:** `rejuve: Read provider keys through h2t-ops paths get secret:<provider>`

---

## Что меняется

С h2t-skills 4.0 (lichtpfad/h2t-skills#548) ключи лежат по одному файлу на провайдера:
`~/.h2t/secrets/shared/<провайдер>.env` (`notion.env`, `exa.env`, …). Ключ внутри называется
`<ПРОВАЙДЕР>_<ЧТО>`. Файлы других программ (`getcourse.env` и т.п.) миграция переносит туда же
под их именами и не читает.

Путь к файлу даёт команда, а не литерал:

```bash
h2t-ops paths get secret:notion      # …/.h2t/secrets/shared/notion.env
```

Так путь останется верным при следующем переносе.

Старые файлы `~/.h2t/config/secrets/*.env` остаются нетронутыми копиями до 4.1. Пакет читает
их как запасные, но не пишет в них: ключ, изменённый после миграции, есть только в новом
файле.

## Просьба

Читать ключи из файла, который печатает `h2t-ops paths get secret:<провайдер>`, до выхода 4.1.
