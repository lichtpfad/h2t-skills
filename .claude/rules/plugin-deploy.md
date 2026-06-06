# Plugin Deploy Rules

## Деплой изменений в h2t-core / h2t-dev

⛔ НИКОГДА не использовать `update-plugin.sh` как финальный деплой — пишет только в локальный кеш, следующий `/plugin marketplace update` сотрёт всё.

**Правильная последовательность:**
1. Закоммитить изменения
2. `git push origin main` — изменения должны быть на GitHub
3. `/plugin marketplace update lichtpfad`
4. `/reload-plugins`

**Why:** локальный кеш (`~/.claude/plugins/cache/`) перезаписывается при каждом marketplace update. Любая работа, не запушенная в репо, будет потеряна.
