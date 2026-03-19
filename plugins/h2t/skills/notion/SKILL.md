---
name: notion
description: "Reads and writes Notion pages and databases via API. Use for GTD tasks, creating pages, querying databases, updating properties. Triggers: 'notion', 'tasks', 'GTD', 'create page', 'query database'., 'h2t:notion'"
compatibility: "Requires NOTION_API_TOKEN in ~/.dor/secrets.env"
metadata:
  author: lichtpfad
  version: 1.0.0
---

# Notion Skill

Этот skill позволяет работать с Notion API - получать, создавать и управлять страницами и базами данных.

## Переменные

```bash
# Cross-platform h2t venv detection
H2T_PYTHON="${H2T_PYTHON:-}"
if [ -z "$H2T_PYTHON" ]; then
  [ -f "$HOME/.h2t/venv/bin/python" ] && H2T_PYTHON="$HOME/.h2t/venv/bin/python"
  [ -f "$HOME/.h2t/venv/Scripts/python.exe" ] && H2T_PYTHON="$HOME/.h2t/venv/Scripts/python.exe"
fi
[ -z "$H2T_PYTHON" ] && echo "ERROR: h2t venv not found. Run /h2t:setup" && exit 1

CLI="$H2T_PYTHON ${CLAUDE_SKILL_DIR}/scripts/notion_cli.py"
```

## Использование

### Получение содержимого страницы:
```bash
$CLI get <page-id>
$CLI get <page-id> --format markdown
```

### Получение блоков страницы:
```bash
$CLI blocks <page-id>
```

### Поиск в базе данных:
```bash
$CLI search <database-id>
$CLI search <database-id> --filter "Status=Done"
$CLI search <database-id> --filter-json '{"property":"Status","status":{"equals":"Done"}}'
```

### Найти задачи проекта:
```bash
$CLI find-project-tasks <project-page-id>
$CLI find-project-tasks <project-page-id> --database-id <tasks-db-id>
```

### Создание страницы:
```bash
$CLI create <parent-id> "Название страницы" --content "Текст содержимого"
```

### Обновление страницы:
```bash
$CLI update <page-id> --title "Новое название"
```

### Синхронизация Notion в Markdown:
```bash
$CLI sync <page-id> <output-file.md>
```

## Требования

- NOTION_API_TOKEN в `~/.dor/secrets.env` (или переменная окружения)
- Или токен в файле `~/.config/notion/token`

## Поддерживаемые типы блоков

Paragraph, Headings (1-3), Lists (bulleted/numbered), Quote, Code blocks, Images, Videos, Dividers, Callouts, Toggle lists, Bookmarks, Tables

## Устранение проблем

**Ошибка: "Unauthorized"**
- Убедитесь что `NOTION_API_TOKEN` установлен в `~/.dor/secrets.env`
- Проверьте что токен действителен

**Ошибка: "object_not_found"**
- Проверьте что страница/база данных существует
- Убедитесь что интеграция имеет доступ к странице
