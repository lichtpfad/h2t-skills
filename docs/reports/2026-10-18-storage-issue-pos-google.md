---
title: "Текст issue в POS: токен Google и mentions_cache.json после h2t 4.0"
status: "draft"
date: "2026-10-18"
---

Черновик issue для репо POS (spec #548 §9, план R26). Этот репо issue не заводит: заведение
и живая проверка POS — Task 26, шаг владельца. Правка — сторона POS
(`.claude/rules/repo-boundary.md`).

**Заголовок:** `pos: Read the Google token through the h2t 4.0 contract and drop mentions_cache.json`

---

## Что меняется в h2t 4.0

h2t-skills 4.0 переносит свои данные в один корень `~/.h2t` (lichtpfad/h2t-skills#548). Три
места, которые читает POS, затронуты.

| Читатель | Что читает | В 4.0.x | Контракт |
|---|---|---|---|
| POS API (calendar, gmail, main, docker-compose, plist) — только чтение | `~/.config/google-calendar-mcp/tokens.json` (путь из `GOOGLE_TOKEN_FILE`) | POS продолжает читать этот файл. Пакет пишет токен машины `local/google.token.json` только при входе и новом refresh-токене и после каждой такой записи зеркалит его в старый файл той же машины, пока тот существует, в формате 3.x. Access-токен в старом файле через час протухает и больше не обновляется. | `h2t-ops paths get secret:google.token` |
| POS (`pos_ingest`, `pos_meetings`) | vault, зашитый `~/.dor/vault` | пакет берёт vault из `H2T_PATH_VAULT` с тем же умолчанием | `H2T_PATH_VAULT` — отдельный issue |
| POS API (telegram_service) | `~/.config/telegram/mentions_cache.json` | пакет файл не пишет с #403 и не трогает; миграция его не переносит | нет |
| rejuve, `POS/CLAUDE.md` | `~/.h2t/config/secrets/*.env` | старые файлы остаются копиями до 4.1 | `h2t-ops paths get secret:<провайдер>` |

## Что нужно от POS

1. **`mentions_cache.json` осиротел.** С lichtpfad/h2t-skills#403 его никто не пишет:
   содержимое застыло на дате последней записи. Упоминания брать из
   `h2t-ops telegram mentions --json`.

2. **Access-токен Google больше нигде не хранится.** С 4.0 пакет получает его по
   refresh-токену в памяти на каждую команду и на диск не пишет. `tokens.json` (путь из
   `GOOGLE_TOKEN_FILE` в plist) пишется только при входе и при новом refresh-токене, поэтому
   `token` и `expiry` в нём протухают через час и дальше не обновляются. POS должен получать
   новый access-токен по `refresh_token` сам. По коду google-auth делает это, увидев истёкший
   `expiry`; вживую это не проверено.

   <!-- POS live check: filled in Task 26 -->

3. **Токен Google теперь у каждой машины свой:** `~/.h2t/secrets/local/google.token.json`.
   Каждая машина входит сама, файл не синхронизируется. Контракт —
   `h2t-ops paths get secret:google.token`: команда печатает путь, и он останется верным при
   следующем переносе. Старый путь (`~/.config/google-calendar-mcp/tokens.json`) пакет
   зеркалит до 4.1, потом зеркало удаляется.

Предлагаемый порядок: перевести `GOOGLE_TOKEN_FILE` на путь из
`h2t-ops paths get secret:google.token` до 4.1; убрать чтение `mentions_cache.json`.
