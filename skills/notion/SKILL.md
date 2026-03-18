---
name: notion
description: "Reads and writes Notion pages and databases via API. Use for GTD tasks, creating pages, querying databases, updating properties. Triggers: 'notion', 'tasks', 'GTD', 'create page', 'query database'."
compatibility: "Requires NOTION_API_TOKEN in ~/.dor/secrets.env"
metadata:
  author: lichtpfad
  version: 1.0.0
---

# Notion Skill

Этот skill позволяет работать с Notion API - получать, создавать и управлять страницами и базами данных.

## Базовый путь к скрипту

```bash
CLI="${CLAUDE_SKILL_DIR}/scripts/notion_cli.py"
```

## Использование

### Получение содержимого страницы:
```bash
python3 $CLI get <page-id>
python3 $CLI get <page-id> --format markdown
```

### Получение блоков страницы:
```bash
python3 $CLI blocks <page-id>
```

### Поиск в базе данных:
```bash
python3 $CLI search <database-id>
python3 $CLI search <database-id> --filter "Status=Done"
python3 $CLI search <database-id> --filter-json '{"property":"Status","status":{"equals":"Done"}}'
```

### Найти задачи проекта:
```bash
python3 $CLI find-project-tasks <project-page-id>
python3 $CLI find-project-tasks <project-page-id> --database-id <tasks-db-id>
```

### Создание страницы:
```bash
python3 $CLI create <parent-id> "Название страницы" --content "Текст содержимого"
```

### Обновление страницы:
```bash
python3 $CLI update <page-id> --title "Новое название"
```

### Синхронизация Notion в Markdown:
```bash
python3 $CLI sync <page-id> <output-file.md>
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
