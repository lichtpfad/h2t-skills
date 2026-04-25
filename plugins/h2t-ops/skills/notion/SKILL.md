---
name: notion
description: "Reads and writes Notion pages and databases via API. Use for GTD tasks, creating pages, querying databases, updating properties. Triggers: 'notion', 'tasks', 'GTD', 'create page', 'query database', 'h2t:notion'"
compatibility: "Requires NOTION_API_TOKEN in ~/.dor/secrets.env or ~/.config/notion/token"
metadata:
  author: lichtpfad
  version: 1.0.0
---

# Notion

## Переменные

```bash
# Notion API token — ищи в таком порядке:
#   1. ~/.config/notion/token  (основное место на всех машинах)
#   2. ~/.dor/secrets.env      (NOTION_API_TOKEN=...)
NOTION_TOKEN="${NOTION_API_TOKEN:-$(cat "$HOME/.config/notion/token" 2>/dev/null || echo "")}"
[ -z "$NOTION_TOKEN" ] && echo "ERROR: Notion token not found. Expected: ~/.config/notion/token" && exit 1

H2T_PYTHON="${H2T_PYTHON:-}"
[ -z "$H2T_PYTHON" ] && [ -f "$HOME/.h2t/venv/Scripts/python.exe" ] && H2T_PYTHON="$HOME/.h2t/venv/Scripts/python.exe"
[ -z "$H2T_PYTHON" ] && [ -f "$HOME/.h2t/venv/bin/python" ] && H2T_PYTHON="$HOME/.h2t/venv/bin/python"
[ -z "$H2T_PYTHON" ] && echo "ERROR: h2t venv not found. Run /h2t-core:setup" && exit 1

CLI="$H2T_PYTHON ${CLAUDE_PLUGIN_ROOT}/lib/cli/main.py ingest notion"
```

## Команды

### Получение страницы
```bash
$CLI get <page-id> [--format json|markdown]
```

### Блоки страницы
```bash
$CLI blocks <page-id> [--limit N] [--format json|markdown]
```

### Поиск в базе данных
```bash
$CLI search <database-id> [--filter "Status=Done"] [--filter-json '{"property":...}'] [--limit N] [--format json|markdown]
```

### Создание страницы
```bash
$CLI create <parent-id> "Название" [--content "Markdown текст"] [--file content.md] [--database]
```

### Обновление страницы
```bash
$CLI update <page-id> [--title "Новое название"] [--append "Markdown"] [--file content.md] [--replace]
```

### База данных
```bash
$CLI get-database <database-id> [--format json|markdown] [--limit N]
$CLI find-databases <page-id>
$CLI find-project-tasks <project-page-id> [--database-id <tasks-db-id>]
```

### Синхронизация в файл
```bash
$CLI sync <page-id> <output-file.md> [--preserve-metadata]
```

## Workflow

1. Выполни команду через Bash tool
2. Покажи результат в читаемом формате
3. Для модификаций — подтверди успех

## Поддерживаемые типы блоков

Paragraph, Headings (1-3), Lists (bulleted/numbered), Quote, Code, Images, Dividers, Callouts, Toggle, Bookmarks, Tables

## Обработка ошибок

- **Unauthorized**: проверь `NOTION_API_TOKEN` в `~/.dor/secrets.env`
- **object_not_found**: проверь что интеграция имеет доступ к странице
