---
name: gmail
description: "Reads and sends Gmail via OAuth. Use when user asks to check email, read messages, search inbox, send mail, or create drafts. Triggers: 'check email', 'show inbox', 'send message', 'draft', 'gmail', 'h2t:gmail'"
compatibility: "Requires Google OAuth token at ~/.config/google-calendar-mcp/tokens.json"
metadata:
  author: lichtpfad
  version: 1.0.0
---

# Gmail

## Переменные

```bash
H2T_PYTHON="${H2T_PYTHON:-}"
[ -z "$H2T_PYTHON" ] && [ -f "$HOME/.h2t/venv/Scripts/python.exe" ] && H2T_PYTHON="$HOME/.h2t/venv/Scripts/python.exe"
[ -z "$H2T_PYTHON" ] && [ -f "$HOME/.h2t/venv/bin/python" ] && H2T_PYTHON="$HOME/.h2t/venv/bin/python"
[ -z "$H2T_PYTHON" ] && echo "ERROR: h2t venv not found. Run /h2t-core:setup" && exit 1

CLI="$H2T_PYTHON ${CLAUDE_PLUGIN_ROOT}/lib/cli/main.py ingest gmail"
```

## Команды

### Список писем
```bash
$CLI list [--max N] [--unread] [--query "search"] [--json]
```

### Чтение письма
```bash
$CLI read <message-id> [--format plain|json]
```

### Поиск писем
```bash
$CLI search "<query>" [--max N] [--json]
```

Операторы поиска Gmail: `from:`, `to:`, `subject:`, `after:YYYY/MM/DD`, `before:`, `has:attachment`, `is:unread`, `is:important`

### Отправка письма
```bash
$CLI send <to> "<subject>" "<body>" [--attach file1 file2] [--draft]
```

Или с текстом из файла:
```bash
$CLI send <to> "<subject>" --file message.txt [--attach files...]
```

### Черновик
```bash
$CLI draft <to> "<subject>" "<body>" [--file ...] [--thread-id ID] [--reply-to MSG-ID]
```

### Labels
```bash
$CLI labels
$CLI label <message-id> [--add LABEL1 LABEL2] [--remove LABEL3]
```

Системные labels: INBOX, UNREAD, STARRED, IMPORTANT, TRASH, SPAM

## Workflow

1. Выполни команду через Bash tool
2. Покажи результат пользователю в читаемом формате
3. Для последовательных действий — выполни их один за другим

## Обработка ошибок

Если OAuth ошибка:
1. Проверь `~/.config/google-calendar-mcp/credentials.json`
2. Если токен истёк — удали `~/.config/google-calendar-mcp/tokens.json` и переавторизуйся

## Graph Integration

### Query (optional — if encountering OAuth errors or unexpected API behavior)

```bash
SKILL_GRAPH_DIR="${SKILL_GRAPH_DIR:-C:/dev/claude-agent-skills/lib}"
(cd "$SKILL_GRAPH_DIR" && $H2T_PYTHON -m skill_graph.cli query \
  --context "gmail: oauth error, api failure, unexpected behavior" \
  --skill "gmail") 2>/dev/null || true
```

If results contain relevant patterns or lessons, apply them before proceeding.

### Add Lesson (after resolving an error or unexpected behavior)

```bash
(cd "$SKILL_GRAPH_DIR" && $H2T_PYTHON -m skill_graph.cli add-lesson \
  --skill "gmail" \
  --trigger "<what broke — e.g. oauth token expired, api returned 403>" \
  --resolution "<what fixed it>" \
  --session-id "$SESSION_NAME") 2>/dev/null || true
```
