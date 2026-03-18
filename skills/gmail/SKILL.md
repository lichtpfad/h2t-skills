---
name: gmail
description: "Reads and sends Gmail via OAuth. Use when user asks to check email, read messages, search inbox, send mail, or create drafts. Triggers: 'check email', 'show inbox', 'send message', 'draft', 'gmail'."
compatibility: "Requires Google OAuth token at ~/.config/google-calendar-mcp/tokens.json"
metadata:
  author: lichtpfad
  version: 1.0.0
---

# Инструкции

Когда skill вызывается, выполни соответствующую команду используя Python CLI:

## Базовый путь к скрипту

```bash
CLI="${CLAUDE_SKILL_DIR}/scripts/gmail_cli.py"
```

## Команды

### 1. Список писем
```bash
python3 $CLI list [--max N] [--unread] [--query "search"]
```

Примеры:
- `list` - последние 10 писем
- `list --max 50` - последние 50
- `list --unread` - только непрочитанные
- `list --query "is:important"` - с фильтром

### 2. Чтение письма
```bash
python3 $CLI read <message-id> [--format plain|json]
```

### 3. Поиск писем
```bash
python3 $CLI search "<query>" [--max N]
```

Gmail search operators:
- `from:user@example.com` - от кого
- `to:user@example.com` - кому
- `subject:text` - в теме
- `after:2026/02/01` - после даты
- `before:2026/02/28` - до даты
- `has:attachment` - с вложениями
- `is:unread` - непрочитанные
- `is:important` - важные

### 4. Отправка письма
```bash
python3 $CLI send <to> "<subject>" "<body>" [--attach file1 file2 ...]
```

Или с текстом из файла:
```bash
python3 $CLI send <to> "<subject>" --file message.txt [--attach files...]
```

### 5. Создание черновика
```bash
python3 $CLI draft <to> "<subject>" "<body>" [--attach files...]
```

### 6. Просмотр labels
```bash
python3 $CLI labels
```

### 7. Управление labels
```bash
python3 $CLI label <message-id> [--add LABEL1 LABEL2] [--remove LABEL3]
```

Системные labels: INBOX, UNREAD, STARRED, IMPORTANT, TRASH, SPAM

## Обработка ошибок

Если получена ошибка OAuth/credentials:
1. Проверь наличие `~/.config/google-calendar-mcp/credentials.json`
2. Если токен истёк, удали `~/.config/google-calendar-mcp/tokens.json` и попроси пользователя переавторизоваться

## Workflow

1. Выполни команду через Bash tool
2. Покажи результат пользователю в читаемом формате
3. Если нужны дополнительные действия - выполни их последовательно
