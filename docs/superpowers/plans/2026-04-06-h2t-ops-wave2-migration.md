# h2t-ops Wave 2: Plugin Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Мигрировать скиллы gmail, notion, calendar, telegram, daily-brief из монолита `plugins/h2t/` в новый плагин `plugins/h2t-ops/` с трёхслойной архитектурой (L1: клиенты, L2: CLI через `lib/cli/main.py ingest`, L3: SKILL.md).

**Architecture:**
- **L1** — `lib/clients/{gmail,notion,calendar}.py` — классы-адаптеры (двунаправленные: ingest + publish), работают без LLM
- **L2** — `lib/cli/main.py ingest <source> <cmd>` — единая CLI точка входа, роутинг на L1, JSON/text stdout
- **L3** — `plugins/h2t-ops/skills/*/SKILL.md` — linear pipeline, Claude вызывает L2, интерпретирует результат

**Tech Stack:** Python 3.11+, google-api-python-client, notion-client, httpx, telethon, argparse

---

## Статус на 2026-04-06

### ✅ Уже реализовано (в этой сессии)

- `lib/clients/__init__.py` — пустой
- `lib/clients/gmail.py` — `GmailClient` (извлечён из `gmail_cli.py`)
- `lib/clients/notion.py` — `NotionClient` (извлечён из `notion_cli.py`)
- `lib/clients/calendar.py` — `CalendarClient` (создан из функций `calendar_cli.py`)
- `lib/cli/main.py` — добавлен subcommand `ingest` (gmail/notion/calendar)
- `plugins/h2t-ops/.claude-plugin/plugin.json`
- `plugins/h2t-ops/skills/{gmail,notion,calendar,telegram,daily-brief}/SKILL.md`
- `plugins/h2t-ops/skills/telegram/scripts/telegram_cli.py` (копия из монолита)
- `plugins/h2t-ops/scripts/update-plugin.sh`
- `.claude-plugin/marketplace.json` — добавлена запись h2t-ops

---

## Файловая карта

| Файл | Статус | Ответственность |
|------|--------|-----------------|
| `lib/clients/gmail.py` | ✅ создан | GmailClient — read/write Gmail |
| `lib/clients/notion.py` | ✅ создан | NotionClient — read/write Notion |
| `lib/clients/calendar.py` | ✅ создан | CalendarClient — read/write Calendar |
| `lib/cli/main.py` | ✅ обновлён | h2t ingest gmail/notion/calendar |
| `plugins/h2t-ops/.claude-plugin/plugin.json` | ✅ создан | Метаданные плагина v1.0.0 |
| `plugins/h2t-ops/skills/gmail/SKILL.md` | ✅ создан | L3: CLI pattern с CLAUDE_PLUGIN_ROOT |
| `plugins/h2t-ops/skills/notion/SKILL.md` | ✅ создан | L3: CLI pattern |
| `plugins/h2t-ops/skills/calendar/SKILL.md` | ✅ создан | L3: CLI pattern |
| `plugins/h2t-ops/skills/daily-brief/SKILL.md` | ✅ создан | L3: 4-step pipeline |
| `plugins/h2t-ops/skills/telegram/SKILL.md` | ✅ создан | L3: старый паттерн (script) |
| `plugins/h2t-ops/skills/telegram/scripts/telegram_cli.py` | ✅ скопирован | Сохраняет DOR_ROOT/Telethon зависимости |
| `plugins/h2t-ops/scripts/update-plugin.sh` | ✅ создан | Установка плагина + копирование lib/ |
| `.claude-plugin/marketplace.json` | ✅ обновлён | +h2t-ops entry |
| `tests/clients/test_gmail.py` | ❌ нет | Unit tests для GmailClient |
| `tests/clients/test_notion.py` | ❌ нет | Unit tests для NotionClient |
| `tests/clients/test_calendar.py` | ❌ нет | Unit tests для CalendarClient |
| `tests/cli/test_ingest.py` | ❌ нет | Integration tests для `h2t ingest` |

---

## Task 1: Установить плагин и проверить CLI

**Files:**
- Run: `plugins/h2t-ops/scripts/update-plugin.sh`

- [ ] **Step 1: Запустить update-plugin.sh**

```bash
bash plugins/h2t-ops/scripts/update-plugin.sh
```

Ожидаемый output:
```json
{"status":"ok","version":"1.0.0","sha":"...","cache":"...","skills":5,"lib_in_cache":"true"}
```

- [ ] **Step 2: Проверить что lib/cli/main.py импортирует клиенты без ошибок**

```bash
cd ~/.claude/plugins/cache/lichtpfad/h2t-ops/1.0.0
$HOME/.h2t/venv/Scripts/python.exe lib/cli/main.py ingest --help
```

Ожидаемый output: список {gmail, notion, calendar}

- [ ] **Step 3: Проверить smoke test gmail (dry-run — только импорт)**

```bash
cd C:/dev/claude-agent-skills
$HOME/.h2t/venv/Scripts/python.exe -c "from lib.clients.gmail import GmailClient; print('OK')"
$HOME/.h2t/venv/Scripts/python.exe -c "from lib.clients.notion import NotionClient; print('OK')"
$HOME/.h2t/venv/Scripts/python.exe -c "from lib.clients.calendar import CalendarClient; print('OK')"
```

Ожидаемый output: три строки "OK"

- [ ] **Step 4: Commit**

```bash
git add lib/clients/ lib/cli/main.py plugins/h2t-ops/ .claude-plugin/marketplace.json
git commit -m "feat(h2t-ops): Wave 2 migration — gmail/notion/calendar/telegram/daily-brief to L1/L2/L3 (v1.0.0)"
```

---

## Task 2: Написать unit tests для клиентов

**Files:**
- Create: `tests/clients/__init__.py`
- Create: `tests/clients/test_gmail.py`
- Create: `tests/clients/test_notion.py`
- Create: `tests/clients/test_calendar.py`

- [ ] **Step 1: Создать test файлы**

`tests/clients/__init__.py` — пустой.

`tests/clients/test_gmail.py`:
```python
"""Unit tests for GmailClient helpers (no network calls)."""
import pytest
from lib.clients.gmail import format_message_list, format_message_detail


def test_format_message_list_empty():
    assert format_message_list([]) == "No messages found."


def test_format_message_list_single():
    msg = {
        "id": "abc123",
        "labelIds": ["UNREAD"],
        "subject": "Test Subject",
        "from": "test@example.com",
        "date": "Mon, 6 Apr 2026",
        "snippet": "Hello world",
    }
    result = format_message_list([msg])
    assert "Test Subject" in result
    assert "📩" in result  # unread marker
    assert "abc123" in result


def test_format_message_list_read():
    msg = {
        "id": "xyz",
        "labelIds": [],
        "subject": "Read Mail",
        "from": "a@b.com",
        "date": "Mon",
        "snippet": "body",
    }
    result = format_message_list([msg])
    assert "📩" not in result


def test_format_message_detail():
    msg = {
        "subject": "Subject",
        "from": "From",
        "to": "To",
        "date": "Date",
        "labelIds": ["INBOX"],
        "body": "Body text",
    }
    result = format_message_detail(msg)
    assert "# Subject" in result
    assert "Body text" in result
```

`tests/clients/test_notion.py`:
```python
"""Unit tests for NotionClient markdown helpers (no network calls)."""
import pytest
from lib.clients.notion import NotionClient


@pytest.fixture
def client():
    # Bypass auth — token won't be used in these tests
    c = object.__new__(NotionClient)
    c.token = "fake"
    return c


def test_rich_text_to_markdown_empty(client):
    assert client._rich_text_to_markdown([]) == ""


def test_rich_text_to_markdown_bold(client):
    rich = [{"type": "text", "text": {"content": "hello"}, "annotations": {"bold": True}}]
    assert client._rich_text_to_markdown(rich) == "**hello**"


def test_rich_text_to_markdown_code(client):
    rich = [{"type": "text", "text": {"content": "x"}, "annotations": {"code": True}}]
    assert client._rich_text_to_markdown(rich) == "`x`"


def test_block_heading(client):
    block = {"type": "heading_2", "heading_2": {"rich_text": [{"type": "text", "text": {"content": "Title"}, "annotations": {}}]}}
    assert client._block_to_markdown(block) == "## Title\n\n"


def test_block_divider(client):
    assert client._block_to_markdown({"type": "divider", "divider": {}}) == "---\n\n"


def test_parse_inline_bold(client):
    spans = client.parse_inline("**bold**")
    assert spans[0]["annotations"]["bold"] is True
    assert spans[0]["text"]["content"] == "bold"


def test_markdown_to_blocks_heading(client):
    blocks = client.markdown_to_blocks("# Hello")
    assert blocks[0]["type"] == "heading_1"
    assert blocks[0]["heading_1"]["rich_text"][0]["text"]["content"] == "Hello"
```

`tests/clients/test_calendar.py`:
```python
"""Unit tests for CalendarClient helpers (no network calls)."""
import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch


def test_normalize_event_timed():
    """_normalize_event converts a timed event to flat dict."""
    from lib.clients.calendar import CalendarClient

    client = object.__new__(CalendarClient)
    event = {
        "id": "evt1",
        "summary": "Meeting",
        "start": {"dateTime": "2026-04-06T14:00:00+03:00"},
        "end": {"dateTime": "2026-04-06T15:00:00+03:00"},
        "htmlLink": "https://cal.google.com/...",
    }
    result = client._normalize_event(event)
    assert result["summary"] == "Meeting"
    assert result["time"] == "14:00"
    assert result["duration_min"] == 60
    assert result["date"] == "2026-04-06"


def test_normalize_event_all_day():
    """_normalize_event handles all-day events."""
    from lib.clients.calendar import CalendarClient

    client = object.__new__(CalendarClient)
    event = {
        "id": "evt2",
        "summary": "Holiday",
        "start": {"date": "2026-04-07"},
        "end": {"date": "2026-04-08"},
    }
    result = client._normalize_event(event)
    assert result["time"] == "весь день"
    assert result["duration_min"] is None
    assert result["date"] == "2026-04-07"
```

- [ ] **Step 2: Запустить тесты**

```bash
cd C:/dev/claude-agent-skills
$HOME/.h2t/venv/Scripts/python.exe -m pytest tests/clients/ -v
```

Ожидаемый output: все тесты PASSED (14+ тестов)

- [ ] **Step 3: Commit**

```bash
git add tests/clients/
git commit -m "test(clients): unit tests for gmail/notion/calendar client helpers"
```

---

## Task 3: Написать integration tests для `h2t ingest` CLI

**Files:**
- Create: `tests/cli/__init__.py`
- Create: `tests/cli/test_ingest_cli.py`

- [ ] **Step 1: Создать test файл**

`tests/cli/__init__.py` — пустой.

`tests/cli/test_ingest_cli.py`:
```python
"""Integration tests for h2t ingest CLI (no network calls — mocked clients)."""
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure lib is on path
_lib = Path(__file__).parent.parent.parent / "lib"
sys.path.insert(0, str(_lib))


def run_cli(*args):
    """Run lib/cli/main.py with given args, capture stdout."""
    import io
    from contextlib import redirect_stdout

    from cli.main import main

    old_argv = sys.argv
    sys.argv = ["h2t"] + list(args)
    captured = io.StringIO()
    try:
        with redirect_stdout(captured):
            try:
                main()
            except SystemExit:
                pass
    finally:
        sys.argv = old_argv
    return captured.getvalue()


def test_ingest_help():
    output = run_cli("ingest", "--help")
    assert "gmail" in output
    assert "notion" in output
    assert "calendar" in output


def test_ingest_gmail_list_json(monkeypatch):
    mock_messages = [
        {"id": "1", "labelIds": ["UNREAD"], "subject": "Test", "from": "a@b.com",
         "to": "me", "date": "Mon", "snippet": "Hi", "body": ""}
    ]
    mock_client = MagicMock()
    mock_client.list_messages.return_value = mock_messages

    with patch("clients.gmail.GmailClient", return_value=mock_client):
        output = run_cli("ingest", "gmail", "list", "--max", "5", "--json")

    data = json.loads(output)
    assert isinstance(data, list)
    assert data[0]["id"] == "1"


def test_ingest_gmail_labels(monkeypatch):
    mock_client = MagicMock()
    mock_client.list_labels.return_value = [{"name": "INBOX", "id": "INBOX"}]

    with patch("clients.gmail.GmailClient", return_value=mock_client):
        output = run_cli("ingest", "gmail", "labels")

    assert "INBOX" in output


def test_ingest_calendar_list_json(monkeypatch):
    mock_events = [
        {"id": "e1", "summary": "Meeting", "date": "2026-04-06",
         "time": "10:00", "duration_min": 60, "location": "", "description": "", "html_link": ""}
    ]
    mock_client = MagicMock()
    mock_client.list_events.return_value = mock_events

    with patch("clients.calendar.CalendarClient", return_value=mock_client):
        output = run_cli("ingest", "calendar", "list", "--json")

    data = json.loads(output)
    assert data[0]["summary"] == "Meeting"


def test_ingest_notion_no_cmd():
    output = run_cli("ingest", "notion")
    assert "error" in output.lower() or output == ""
```

- [ ] **Step 2: Запустить тесты**

```bash
cd C:/dev/claude-agent-skills
$HOME/.h2t/venv/Scripts/python.exe -m pytest tests/cli/test_ingest_cli.py -v
```

Ожидаемый output: все тесты PASSED

- [ ] **Step 3: Commit**

```bash
git add tests/cli/
git commit -m "test(cli): integration tests for h2t ingest subcommand"
```

---

## Task 4: Установить h2t-ops через marketplace и проверить скиллы

**Files:**
- Run: `plugins/h2t-ops/scripts/update-plugin.sh`
- Verify: `~/.claude/plugins/installed_plugins.json`

- [ ] **Step 1: Установить плагин**

```bash
bash plugins/h2t-ops/scripts/update-plugin.sh
```

Ожидаемый output (JSON):
```json
{"status":"ok","version":"1.0.0","skills":5,"lib_in_cache":"true"}
```

- [ ] **Step 2: Проверить installed_plugins.json**

```bash
python -c "
import json; d = json.load(open('$HOME/.claude/plugins/installed_plugins.json'))
print('h2t-ops' in str(d))
"
```

Ожидаемый output: `True`

- [ ] **Step 3: Проверить что CLAUDE_PLUGIN_ROOT будет правильно указывать**

В кэше `~/.claude/plugins/cache/lichtpfad/h2t-ops/1.0.0/` должны быть:
```
lib/cli/main.py
lib/clients/gmail.py
lib/clients/notion.py
lib/clients/calendar.py
skills/gmail/SKILL.md
skills/notion/SKILL.md
skills/calendar/SKILL.md
skills/daily-brief/SKILL.md
skills/telegram/SKILL.md
```

```bash
ls ~/.claude/plugins/cache/lichtpfad/h2t-ops/1.0.0/lib/clients/
```

Ожидаемый output: `__init__.py  calendar.py  gmail.py  notion.py`

- [ ] **Step 4: Финальный commit с тегом версии**

```bash
git add -A
git commit -m "feat(h2t-ops): complete Wave 2 migration — tests + install verified (v1.0.0)"
```

---

## Task 5: Обновить marketplace.json версию h2t-ops

Marketplace.json содержит статическую версию. После установки обновить до актуальной.

**Files:**
- Modify: `.claude-plugin/marketplace.json`

- [ ] **Step 1: Проверить что версии совпадают**

```bash
python -c "
import json
mp = json.load(open('.claude-plugin/marketplace.json'))
ops = next(p for p in mp['plugins'] if p['name'] == 'h2t-ops')
pj = json.load(open('plugins/h2t-ops/.claude-plugin/plugin.json'))
print('match:', ops['version'] == pj['version'])
"
```

Ожидаемый output: `match: True`

- [ ] **Step 2: Если версии расходятся — обновить marketplace.json**

В `.claude-plugin/marketplace.json` установить `"version"` для h2t-ops равной версии из `plugin.json`.

- [ ] **Step 3: Commit**

```bash
git add .claude-plugin/marketplace.json
git commit -m "chore: sync h2t-ops marketplace version"
```

---

## Backlog (не в scope этой сессии)

| # | Задача |
|---|--------|
| 1 | `h2t ingest telegram` — рефакторинг TelegramClient в `lib/clients/telegram.py` (сейчас скрипт в skills/) |
| 2 | `h2t brief today` — subcommand в `lib/cli/main.py` для агрегации daily-brief без SKILL.md |
| 3 | Eval Level 0 — activity logging при вызове ingest CLI (после определения схемы) |
| 4 | VPS mode — `GET /api/brief/today` в daily-brief SKILL.md с local fallback |
| 5 | Удалить скиллы из монолита `plugins/h2t/` после стабилизации h2t-ops |
| 6 | Protocol/ABC для клиентов — добавить в Phase 3 когда появится третий runtime |
