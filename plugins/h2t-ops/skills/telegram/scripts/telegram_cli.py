#!/usr/bin/env python3
"""
Telegram CLI — три pipeline для Telegram данных.

Использование:
  telegram_cli.py auth --phone +972...           # шаг 1: запросить SMS-код
  telegram_cli.py auth --phone +972... --code N  # шаг 2: ввести код
  telegram_cli.py auth --phone +972... --code N --password P  # шаг 3: 2FA (если нужно)
  telegram_cli.py saved [--all]     # Saved Messages → Obsidian MD
  telegram_cli.py digest [--all]    # образовательные каналы → Obsidian MD
  telegram_cli.py tasks [--all]     # рабочие чаты → Notion
  telegram_cli.py sync              # все три pipeline
"""

import os
import sys
import json
import subprocess
import argparse
from pathlib import Path
from datetime import datetime, timezone, timedelta

from telethon.sync import TelegramClient
from telethon.errors import SessionPasswordNeededError
from google import genai
from google.genai import types as genai_types

def _load_secret_env_files() -> None:
    """Load canonical then legacy h2t secrets files without overriding env."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    override = os.environ.get("H2T_SECRETS_FILE")
    paths = [Path(override)] if override else [
        Path.home() / '.dor' / 'secrets' / 'secrets.env',
        Path.home() / '.dor' / 'secrets.env',
    ]
    for path in paths:
        load_dotenv(path, override=False)


_load_secret_env_files()
DOR_ROOT = Path(os.environ.get('DOR_ROOT', Path.home() / 'Projects' / 'DOR'))
try:
    from dotenv import load_dotenv
    load_dotenv(DOR_ROOT / '.env', override=False)  # fallback
except ImportError:
    pass

# --- Пути ---
CONFIG_DIR = Path.home() / '.config' / 'telegram'
CONFIG_FILE = CONFIG_DIR / 'config.json'
SESSION_FILE = str(CONFIG_DIR / 'session')
LAST_SYNC_FILE = CONFIG_DIR / 'last_sync.json'
AUTH_STATE_FILE = CONFIG_DIR / 'auth_state.json'  # temp: phone_code_hash
CHATS_CONFIG_FILE = CONFIG_DIR / 'chats.yaml'
DIALOGS_BOOTSTRAP_FILE = CONFIG_DIR / 'dialogs_bootstrapped'  # timestamp of last full iter_dialogs
DIALOGS_REFRESH_DAYS = 7  # refresh entity cache weekly

CONTEXT_ROOT = DOR_ROOT / 'context' if DOR_ROOT.exists() else Path.home() / '.dor' / 'output'
TELEGRAM_DIR = CONTEXT_ROOT / 'telegram'

# --- LLM модели ---
GEMINI_MODEL_FAST  = "gemini-2.5-flash-lite"  # saved, digest
GEMINI_MODEL_SMART = "gemini-2.5-flash"        # tasks (нужен reasoning)

# --- Конфиг каналов и чатов (загружается из ~/.config/telegram/chats.yaml) ---
# DIGEST_CHANNELS и WORK_CHATS оставлены для обратной совместимости (не используются)
DIGEST_CHANNELS = {}
WORK_CHATS = {}


def load_chats_config() -> dict:
    """Load chats configuration from ~/.config/telegram/chats.yaml."""
    if not CHATS_CONFIG_FILE.exists():
        return {"work_chats": [], "student_groups": [], "own_channels": [], "ext_channels": []}
    try:
        import yaml
        data = yaml.safe_load(CHATS_CONFIG_FILE.read_text()) or {}
        return {
            "work_chats": data.get("work_chats") or [],
            "student_groups": data.get("student_groups") or [],
            "own_channels": data.get("own_channels") or [],
            "ext_channels": data.get("ext_channels") or [],
        }
    except (yaml.YAMLError, ImportError) as e:
        print(f"⚠️  Ошибка чтения chats.yaml: {e}", file=sys.stderr)
        return {"work_chats": [], "student_groups": [], "own_channels": [], "ext_channels": []}


def _ensure_entity_cache(client) -> dict | None:
    """
    Populate Telethon session DB with all dialog entities.

    First call (or after DIALOGS_REFRESH_DAYS): runs iter_dialogs(limit=None) — slow (30-120s).
    Subsequent calls within refresh window: returns None immediately (session DB already warm,
    int IDs passed to iter_messages will resolve without API calls).

    Returns entity_map {bare_id_str: entity} on bootstrap/refresh, None on cache hit.
    """
    import time
    try:
        ts = float(DIALOGS_BOOTSTRAP_FILE.read_text().strip())
        age_days = (time.time() - ts) / 86400
        if age_days < DIALOGS_REFRESH_DAYS:
            return None  # session DB is warm — callers can use int IDs directly
    except (FileNotFoundError, ValueError, OSError):
        pass

    print("⏳ Bootstrap: загружаю все диалоги в кэш (раз в 7 дней)...", file=sys.stderr)
    entity_map: dict = {}
    for dialog in client.iter_dialogs(limit=None):
        if hasattr(dialog.entity, 'id'):
            entity_map[str(dialog.entity.id)] = dialog.entity
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    import time as _time
    DIALOGS_BOOTSTRAP_FILE.write_text(str(_time.time()))
    print(f"   ✅ {len(entity_map)} диалогов закэшировано", file=sys.stderr)
    return entity_map


def cmd_bootstrap(args):
    """One-time bootstrap: load all dialogs into session cache, then run mentions."""
    with get_client() as client:
        # Force refresh regardless of existing timestamp
        DIALOGS_BOOTSTRAP_FILE.unlink(missing_ok=True)
        entity_map = _ensure_entity_cache(client)
        print(f"✅ Bootstrap завершён: {len(entity_map or {})} диалогов в сессии")
        print("Теперь ежедневный cron: telegram mentions --days 1", file=sys.stderr)


def load_config() -> dict:
    """Load Telegram API credentials from ~/.config/telegram/config.json."""
    if not CONFIG_FILE.exists():
        print(f"Error: {CONFIG_FILE} не найден.", file=sys.stderr)
        print('Создайте файл с {"api_id": 123, "api_hash": "abc"}', file=sys.stderr)
        sys.exit(1)
    return json.loads(CONFIG_FILE.read_text())


def get_client() -> TelegramClient:
    """Create Telethon client (not connected)."""
    cfg = load_config()
    return TelegramClient(SESSION_FILE, cfg['api_id'], cfg['api_hash'])


def get_last_sync(key: str) -> float:
    """Get last sync timestamp for given pipeline."""
    if LAST_SYNC_FILE.exists():
        data = json.loads(LAST_SYNC_FILE.read_text())
        return float(data.get(key, 0))
    return 0.0


def update_last_sync(key: str):
    """Update last sync timestamp for given pipeline."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    data = {}
    if LAST_SYNC_FILE.exists():
        data = json.loads(LAST_SYNC_FILE.read_text())
    data[key] = datetime.now(timezone.utc).timestamp()
    LAST_SYNC_FILE.write_text(json.dumps(data, indent=2))


def call_gemini(prompt: str, model: str = GEMINI_MODEL_FAST) -> str:
    """Call Gemini API. Returns plain text response."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not set in environment")
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=genai_types.GenerateContentConfig(
            response_mime_type="text/plain",
        ),
    )
    return response.text


def fetch_saved_messages(fetch_all: bool = False) -> list:
    """Fetch messages from Telegram Saved Messages (sent to self)."""
    since_ts = 0.0 if fetch_all else get_last_sync('saved')
    since_dt = datetime.fromtimestamp(since_ts, tz=timezone.utc) if since_ts else None

    print(f"📥 Читаю Saved Messages {'(всё)' if fetch_all else '(новые)'}...", file=sys.stderr)

    messages = []
    with get_client() as client:
        for msg in client.iter_messages('me', limit=500):
            if since_dt and msg.date < since_dt:
                break
            if not msg.text and not msg.entities:
                continue

            item = {
                'date': msg.date.isoformat(),
                'text': msg.text or '',
                'urls': [],
            }

            if msg.entities:
                from telethon.tl.types import MessageEntityUrl, MessageEntityTextUrl
                for ent in msg.entities:
                    if isinstance(ent, MessageEntityUrl):
                        item['urls'].append(msg.text[ent.offset:ent.offset + ent.length])
                    elif isinstance(ent, MessageEntityTextUrl):
                        item['urls'].append(ent.url)

            messages.append(item)

    print(f"  ✅ {len(messages)} сообщений", file=sys.stderr)
    return messages


def summarize_saved(messages: list) -> str:
    """Use Gemini to organize Saved Messages into themed Markdown digest."""
    if not messages:
        return "# Telegram Saved — нет новых сообщений\n"

    items = []
    for msg in messages[:200]:
        text = msg['text'][:300] if msg['text'] else ''
        urls = ', '.join(msg['urls'][:3])
        if text or urls:
            items.append(f"[{msg['date'][:10]}] {text} {f'URL: {urls}' if urls else ''}")

    input_text = '\n'.join(items)
    date_str = datetime.now().strftime('%Y-%m-%d')

    prompt = f"""Ты — система организации знаний. Проанализируй список сообщений из Telegram Saved Messages и создай структурированный дайджест.

Сообщения:
{input_text}

Задача:
1. Сгруппируй по тематике/домену (Art/Digital, Tech/AI, Личное, Разное и т.д.)
2. Для каждой ссылки или заметки — 1-строчная аннотация на русском
3. Выдели раздел "📌 To Read Later" — важное для глубокого изучения
4. Выдели раздел "✅ TODO" — если есть actionable items

Формат: Markdown. Заголовок: # Telegram Saved — {date_str}
Каждая секция: ## [Emoji] [Название]
Каждый элемент: - [описание/ссылка] — аннотация

Пиши на русском языке. Будь лаконичен."""

    return call_gemini(prompt)


def cmd_saved(args):
    """Pipeline: Saved Messages → Obsidian Markdown."""
    fetch_all = getattr(args, 'all', False)

    messages = fetch_saved_messages(fetch_all=fetch_all)
    if not messages:
        print("ℹ️  Нет новых Saved Messages с последнего запуска.")
        return

    date_str = datetime.now().strftime('%Y-%m-%d')
    TELEGRAM_DIR.mkdir(parents=True, exist_ok=True)
    output_file = TELEGRAM_DIR / f'saved-{date_str}.md'
    lines = [f'# Telegram Saved — {date_str}\n']
    for msg in messages:
        lines.append(f"**{msg['date'][:10]}:** {msg['text']}")
        for url in msg['urls']:
            lines.append(f"  - {url}")
        lines.append('')
    output_file.write_text('\n'.join(lines), encoding='utf-8')

    update_last_sync('saved')

    print(f"✅ Saved: {len(messages)} сообщений → {output_file}")


def fetch_channel_posts(fetch_all: bool = False) -> dict:
    """Fetch recent posts from ext_channels in chats.yaml."""
    cfg = load_chats_config()

    if not cfg.get('ext_channels'):
        print("⚠️  ext_channels пустой. Заполни ~/.config/telegram/chats.yaml", file=sys.stderr)
        return {}

    since_ts = 0.0 if fetch_all else get_last_sync('digest')
    cutoff = datetime.now(timezone.utc) - timedelta(days=7) if fetch_all else (
        datetime.fromtimestamp(since_ts, tz=timezone.utc) if since_ts
        else datetime.now(timezone.utc) - timedelta(hours=24)
    )

    result = {}
    with get_client() as client:
        for ch in cfg.get('ext_channels', []):
            username = ch.get('id')
            if not username:
                print(f"⚠️  Пропускаю ext_channel без поля 'id'", file=sys.stderr)
                continue
            display_name = ch.get('label', ch.get('id'))
            print(f"  📡 {display_name} ({username})...", file=sys.stderr)
            try:
                posts = []
                for msg in client.iter_messages(username, limit=50):
                    if msg.date < cutoff:
                        break
                    if msg.text:
                        posts.append({'date': msg.date.isoformat(), 'text': msg.text[:500]})
                result[display_name] = posts
                print(f"    ✅ {len(posts)} постов", file=sys.stderr)
            except Exception as e:
                print(f"    ❌ {e}", file=sys.stderr)
                result[display_name] = []
    return result


def summarize_digest(channel_posts: dict) -> str:
    """Summarize channel posts into Markdown digest via Gemini."""
    date_str = datetime.now().strftime('%Y-%m-%d')
    if not any(posts for posts in channel_posts.values()):
        return f"# Telegram Digest — {date_str}\n\nНет новых постов.\n"

    sections = []
    for name, posts in channel_posts.items():
        if posts:
            posts_text = '\n'.join(f"- {p['date'][:10]}: {p['text'][:200]}" for p in posts[:20])
            sections.append(f"=== {name} ===\n{posts_text}")

    input_text = '\n\n'.join(sections)
    prompt = f"""Проанализируй посты из Telegram-каналов и создай краткий дайджест.

{input_text}

Задача:
1. Для каждого канала — 3-5 bullet points с ключевыми идеями
2. В конце — раздел "## 💡 Top 3 insights дня" из всех каналов

Формат: Markdown.
Заголовок: # Telegram Digest — {date_str}
Секция канала: ## [название канала]
Финальная секция: ## 💡 Top 3 Insights дня

Пиши на русском языке. Будь лаконичен."""

    return call_gemini(prompt, model=GEMINI_MODEL_FAST)


def cmd_digest(args):
    """Pipeline: Channel posts → Obsidian Markdown."""
    fetch_all = getattr(args, 'all', False)
    print("📡 Читаю образовательные каналы...", file=sys.stderr)
    channel_posts = fetch_channel_posts(fetch_all=fetch_all)
    if not channel_posts:
        return

    date_str = datetime.now().strftime('%Y-%m-%d')
    TELEGRAM_DIR.mkdir(parents=True, exist_ok=True)
    output_file = TELEGRAM_DIR / f'digest-{date_str}.md'
    lines = [f'# Telegram Digest — {date_str}\n']
    for name, posts in channel_posts.items():
        if posts:
            lines.append(f'## {name}\n')
            for p in posts:
                lines.append(f"**{p['date'][:10]}:** {p['text']}\n")
    output_file.write_text('\n'.join(lines), encoding='utf-8')
    update_last_sync('digest')

    total = sum(len(p) for p in channel_posts.values())
    print(f"✅ Digest: {total} постов из {len(channel_posts)} каналов → {output_file}")


def fetch_chat_messages(fetch_all: bool = False) -> dict:
    """Fetch messages from work_chats in chats.yaml for task extraction."""
    cfg = load_chats_config()

    if not cfg.get('work_chats'):
        print("⚠️  work_chats пустой. Заполни ~/.config/telegram/chats.yaml", file=sys.stderr)
        return {}

    since_ts = 0.0 if fetch_all else get_last_sync('tasks')
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24) if not since_ts else \
        datetime.fromtimestamp(since_ts, tz=timezone.utc)

    result = {}
    with get_client() as client:
        me = client.get_me()
        my_id = me.id
        for ch in cfg.get('work_chats', []):
            chat_id = ch.get('id')
            if not chat_id:
                print(f"⚠️  Пропускаю work_chat без поля 'id'", file=sys.stderr)
                continue
            label = ch.get('label', ch.get('id'))
            print(f"  💬 {label} ({chat_id})...", file=sys.stderr)
            try:
                messages = []
                for msg in client.iter_messages(chat_id, limit=200):
                    if msg.date < cutoff:
                        break
                    if msg.text:
                        sender = getattr(msg.sender, 'first_name', 'Unknown')
                        is_me = getattr(msg.sender, 'id', None) == my_id
                        messages.append({
                            'date': msg.date.isoformat(),
                            'text': msg.text[:400],
                            'sender': 'Я' if is_me else sender,
                        })
                result[label] = messages
                print(f"    ✅ {len(messages)} сообщений", file=sys.stderr)
            except Exception as e:
                print(f"    ❌ {e}", file=sys.stderr)
                result[label] = []
    return result


def extract_tasks(chat_messages: dict) -> list:
    """Extract action items, promises, decisions from chat messages via Gemini JSON mode."""
    all_msgs = []
    for chat, msgs in chat_messages.items():
        for m in msgs:
            all_msgs.append(f"[{chat}][{m['sender']}]: {m['text'][:300]}")

    if not all_msgs:
        return []

    input_text = '\n'.join(all_msgs[:300])
    prompt = f"""Проанализируй переписку из рабочих Telegram-чатов. Найди:
1. action_item — задачи/поручения, адресованные "Я" или взятые "Я"
2. promise — обещания данные мне или мной
3. decision — важные решения и договорённости

Переписка:
{input_text}

Верни ТОЛЬКО JSON-массив:
[{{"type": "action_item", "text": "...", "from": "...", "chat": "...", "confidence": 0.9}}]

Правила:
- confidence: 0.0–1.0
- Включай только items с confidence >= 0.7
- text: конкретная формулировка задачи
- Пиши на русском языке
- Если нет задач — верни []"""

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not set in environment")
    client_ai = genai.Client(api_key=api_key)
    response = client_ai.models.generate_content(
        model=GEMINI_MODEL_SMART,
        contents=prompt,
        config=genai_types.GenerateContentConfig(response_mime_type="application/json"),
    )
    try:
        return json.loads(response.text)
    except Exception as e:
        print(f"⚠️  JSON parse error: {e}", file=sys.stderr)
        return []


def cmd_tasks(args):
    """Pipeline: Work chats → extracted tasks → Notion + MD log."""
    import importlib.util
    fetch_all = getattr(args, 'all', False)
    TASKS_DB_ID = 'beabac7bf4314952a9327759c638d89f'

    print("💬 Читаю рабочие чаты...", file=sys.stderr)
    chat_msgs = fetch_chat_messages(fetch_all=fetch_all)
    if not chat_msgs:
        return

    date_str = datetime.now().strftime('%Y-%m-%d')
    TELEGRAM_DIR.mkdir(parents=True, exist_ok=True)
    log_file = TELEGRAM_DIR / f'tasks-{date_str}.md'
    lines = [f'# Telegram Tasks — {date_str}\n']
    total = 0
    for chat, msgs in chat_msgs.items():
        if msgs:
            lines.append(f'## {chat}\n')
            for m in msgs:
                lines.append(f"**{m['date'][:10]} {m['sender']}:** {m['text']}\n")
            total += len(msgs)
    log_file.write_text('\n'.join(lines), encoding='utf-8')
    update_last_sync('tasks')

    print(f"✅ Tasks: {total} сообщений из {len(chat_msgs)} чатов → {log_file}")


def cmd_chat(args):
    """Read conversation with a specific user by username or numeric ID."""

    user_arg = args.user
    fetch_all = getattr(args, 'all', False)
    days = args.days
    limit = None if fetch_all else args.limit
    cutoff = None if fetch_all else datetime.now(timezone.utc) - timedelta(days=days)

    # Resolve entity: numeric ID or @username
    try:
        entity = int(user_arg)
    except ValueError:
        entity = user_arg  # @username or plain username

    if fetch_all:
        print(f"💬 Читаю полную историю чата с {user_arg}...", file=sys.stderr)
    else:
        print(f"💬 Читаю чат с {user_arg} за последние {days} дней...", file=sys.stderr)

    messages = []
    with get_client() as client:
        me = client.get_me()
        my_id = me.id
        my_name = me.first_name or 'Я'

        # If numeric ID, pre-populate entity cache by scanning recent dialogs
        if isinstance(entity, int):
            print("🔍 Ищу пользователя в диалогах...", file=sys.stderr)
            found = None
            for dialog in client.iter_dialogs(limit=200):
                if hasattr(dialog.entity, 'id') and dialog.entity.id == entity:
                    found = dialog.entity
                    break
            if found is None:
                print(f"❌ Пользователь {entity} не найден в последних 200 диалогах.", file=sys.stderr)
                print("Попробуйте указать @username вместо числового ID.", file=sys.stderr)
                return
            entity = found

        for msg in client.iter_messages(entity, limit=limit):
            if cutoff and msg.date < cutoff:
                break
            if not msg.text:
                continue

            sender_id = getattr(msg.sender, 'id', None)
            if sender_id == my_id:
                sender = my_name
            else:
                sender = getattr(msg.sender, 'first_name', None) or user_arg

            messages.append({
                'date': msg.date.strftime('%Y-%m-%d %H:%M'),
                'sender': sender,
                'text': msg.text,
            })

    if not messages:
        print(f"ℹ️  Нет сообщений с {user_arg} за последние {days} дней.")
        return

    # Print oldest first (iter_messages returns newest first)
    messages.reverse()
    if len(messages) == limit:
        print(f"⚠️  Показаны {limit} сообщений (лимит). Используйте --limit N для большего.", file=sys.stderr)

    print(f"\n{'─'*60}")
    print(f"Переписка с {user_arg} — последние {days} дней ({len(messages)} сообщений)")
    print(f"{'─'*60}\n")

    for msg in messages:
        print(f"[{msg['date']}] {msg['sender']}:")
        indented = msg['text'].replace('\n', '\n  ')
        print(f"  {indented}")
        print()


def _classify_batch_gemini(batch: list) -> list:
    """Use Gemini to suggest categories for a batch of chat names."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not set in environment")
    client = genai.Client(api_key=api_key)
    names = "\n".join(f"{i}. {d['name']} ({d['type']})" for i, d in enumerate(batch))
    prompt = f"""Categorize each Telegram chat into one of: work_chat, student_group, own_channel, ext_channel, noise.
work_chat = colleagues, partners, professional DMs
student_group = learning cohorts, student support groups
own_channel = user's own channels
ext_channel = news channels, tech channels, communities
noise = spam, bots, irrelevant

Chats:
{names}

Reply with exactly {len(batch)} lines, one category per line, same order. No explanations."""
    response = client.models.generate_content(
        model=GEMINI_MODEL_FAST,
        contents=prompt,
        config=genai_types.GenerateContentConfig(
            response_mime_type="text/plain",
        ),
    )
    valid_categories = {"work_chat", "student_group", "own_channel", "ext_channel", "noise", "skip"}
    lines = response.text.strip().splitlines()
    # Filter to only valid category lines (strip preamble/explanations Gemini may add)
    filtered = [ln.strip().split()[-1] if ln.strip().split() else "noise" for ln in lines]
    filtered = [ln if ln in valid_categories else "noise" for ln in filtered]
    # Pad if needed
    while len(filtered) < len(batch):
        filtered.append("noise")
    return filtered[:len(batch)]


def _scan_import_folders():
    """Import existing Telegram folder structure into chats.yaml."""
    import yaml
    from telethon.tl.functions.messages import GetDialogFiltersRequest
    with get_client() as client:
        filters = client(GetDialogFiltersRequest())
        existing = load_chats_config()
        # Compute existing_ids once before the loop to avoid O(n²) rebuilds
        existing_ids = {
            str(c.get('id'))
            for cat in existing.values()
            if isinstance(cat, list)
            for c in cat
            if c.get('id')
        }
        imported = 0
        for f in filters.filters:
            if not hasattr(f, 'title'):
                continue
            title_raw = getattr(f.title, 'text', None) or str(f.title)
            title = title_raw.lower()
            category = "work_chats"
            if any(x in title for x in ["student", "cohort", "учебн", "group"]):
                category = "student_groups"
            elif any(x in title for x in ["channel", "канал", "news"]):
                category = "ext_channels"
            for peer in getattr(f, 'include_peers', []):
                peer_id = str(
                    getattr(peer, 'channel_id',
                    getattr(peer, 'chat_id',
                    getattr(peer, 'user_id', '')))
                )
                if not peer_id:
                    continue
                if peer_id in existing_ids:
                    continue
                # domain defaults to "dev"; edit chats.yaml manually to set the correct domain per chat
                entry = {"id": peer_id, "label": title_raw, "domain": "dev"}
                existing[category].append(entry)
                existing_ids.add(peer_id)
                imported += 1
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        CHATS_CONFIG_FILE.write_text(yaml.dump(existing, allow_unicode=True, default_flow_style=False))
        print(f"Импортировано {imported} записей в {CHATS_CONFIG_FILE}")


def _scan_interactive(batch_size: int = 20):
    """Interactive batch categorization wizard."""
    import yaml
    existing = load_chats_config()
    existing_ids = {
        str(c.get('id'))
        for cat in existing.values()
        if isinstance(cat, list)
        for c in cat
        if c.get('id')
    }

    with get_client() as client:
        dialogs = []
        for d in client.iter_dialogs(limit=500):
            did = str(d.id)
            if did not in existing_ids:
                dialogs.append({"id": did, "name": d.name or str(d.id), "type": d.entity.__class__.__name__})

    print(f"Найдено {len(dialogs)} некатегоризированных чатов")
    categories = ["work_chat", "student_group", "own_channel", "ext_channel", "noise", "skip"]
    cat_to_key = {
        "work_chat": "work_chats",
        "student_group": "student_groups",
        "own_channel": "own_channels",
        "ext_channel": "ext_channels",
    }

    try:
        for i in range(0, len(dialogs), batch_size):
            batch = dialogs[i:i + batch_size]
            try:
                suggestions = _classify_batch_gemini(batch)
            except RuntimeError as e:
                print(f"Gemini недоступен: {e}. Используется 'noise' по умолчанию.", file=sys.stderr)
                suggestions = ["noise"] * len(batch)

            for j, (dialog, suggestion) in enumerate(zip(batch, suggestions)):
                suggestion = suggestion.strip()
                if suggestion not in categories:
                    suggestion = "noise"
                print(f"\n[{i+j+1}/{len(dialogs)}] {dialog['name']} ({dialog['type']})")
                print(f"  Предложение: {suggestion}")
                opts = " / ".join(f"{k}={v}" for k, v in enumerate(categories))
                print(f"  {opts}")
                choice = input("  Выбор (Enter=принять): ").strip()
                if choice.isdigit() and int(choice) < len(categories):
                    cat = categories[int(choice)]
                else:
                    cat = suggestion
                key = cat_to_key.get(cat)
                if key:
                    # domain defaults to "dev"; edit chats.yaml manually to set the correct domain per chat
                    existing.setdefault(key, []).append({"id": dialog["id"], "label": dialog["name"], "domain": "dev"})

            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            CHATS_CONFIG_FILE.write_text(yaml.dump(existing, allow_unicode=True, default_flow_style=False))
            print(f"\nСохранено {i + len(batch)}/{len(dialogs)}. Продолжить? (Enter / q)")
            if input().strip().lower() == 'q':
                break
    except KeyboardInterrupt:
        print("\n\n⚠️  Прервано. Прогресс сохранён.", file=sys.stderr)
    print(f"✅ chats.yaml обновлён: {CHATS_CONFIG_FILE}")


def cmd_scan_chats(args):
    """Categorize Telegram chats -> ~/.config/telegram/chats.yaml"""
    if args.import_folders:
        _scan_import_folders()
    else:
        _scan_interactive(batch_size=args.batch)


def cmd_mentions(args):
    """Scan work chats + student groups for @mentions. No LLM."""
    cfg = load_chats_config()
    chats = cfg.get('work_chats', []) + cfg.get('student_groups', [])

    if not chats:
        print("⚠️  Нет чатов в work_chats/student_groups. Запусти scan-chats.", file=sys.stderr)
        return

    days = args.days
    since_ts = get_last_sync('mentions')
    cutoff = datetime.fromtimestamp(since_ts, tz=timezone.utc) if since_ts else \
        datetime.now(timezone.utc) - timedelta(days=days)
    mentions = []

    with get_client() as client:
        entity_map = _ensure_entity_cache(client)  # None = session DB already warm

        for chat in chats:
            chat_id = chat.get('id')
            if not chat_id:
                continue
            label = chat.get('label', str(chat_id))
            # Resolve entity: from fresh entity_map (bootstrap run) or session DB (incremental)
            if entity_map is not None:
                entity = entity_map.get(str(chat_id))
                if entity is None:
                    print(f"   ⚠️  {label} ({chat_id}) не в кэше, пропускаю", file=sys.stderr)
                    continue
            else:
                entity = int(chat_id)  # session DB handles resolution, no API calls
            try:
                for msg in client.iter_messages(entity, limit=500):
                    if msg.date < cutoff:
                        break
                    if not msg.mentioned:
                        continue
                    sender = (
                        getattr(msg.sender, 'first_name', None)
                        or getattr(msg.sender, 'username', None)
                        or str(msg.sender_id)
                    )
                    chat_id_str = str(chat_id)
                    url = (
                        f"https://t.me/c/{chat_id_str.lstrip('-100')}/{msg.id}"
                        if chat_id_str.startswith('-100')
                        else None
                    )
                    mentions.append({
                        "id": msg.id,
                        "chat": label,
                        "chat_id": chat_id_str,
                        "sender": sender,
                        "text": (msg.text or '')[:200],
                        "date": msg.date.isoformat(),
                        "age_hours": round(
                            (datetime.now(timezone.utc) - msg.date).total_seconds() / 3600, 1
                        ),
                        "url": url,
                    })
            except Exception as e:
                print(f"⚠️  Ошибка в {label}: {e}", file=sys.stderr)

    mentions.sort(key=lambda x: x['age_hours'])
    cache = {
        "total": len(mentions),
        "mentions": mentions,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }
    cache_file = CONFIG_DIR / 'mentions_cache.json'
    cache_file.write_text(json.dumps(cache, ensure_ascii=False, indent=2))
    update_last_sync('mentions')

    elapsed_days = (datetime.now(timezone.utc) - cutoff).days
    print(f"📣 Найдено {len(mentions)} упоминаний за {elapsed_days} дней")
    for m in mentions:
        print(f"  [{m['chat']}] {m['sender']}: {m['text'][:80]}")

    return cache


def _research_gemini(items: list) -> str:
    """Use Gemini to extract insights from own_channels + Saved Messages."""
    count = len(items)
    cutoff_date = min(i['date'] for i in items)[:10] if items else 'N/A'
    date_str = datetime.now().strftime('%Y-%m-%d')

    formatted_items = '\n'.join(
        f"[{it['date'][:10]}][{it['source']}][{it['domain']}] {it['text'][:300]}"
        for it in items[:300]
    )

    prompt = f"""You are a knowledge curator. From the following Telegram messages, extract valuable insights.
Group by domain (dev / learning / art / hou2touch / other). For each item write:
- **[topic]** (tags: tag1, tag2)
  Insight in 1-2 sentences.

Messages ({count} total, since {cutoff_date}):
{formatted_items}

Output clean Markdown with ## sections per domain. Start with a header:
# Research Digest — {date_str} ({count} items)

Skip noise/spam messages. Write in Russian when source is Russian, English otherwise."""

    return call_gemini(prompt, model=GEMINI_MODEL_FAST)


def cmd_research(args):
    """own_channels + Saved Messages → vault/600 Learning via Gemini."""
    cfg = load_chats_config()
    channels = cfg.get('own_channels', [])
    fetch_all = getattr(args, 'all', False)
    since_ts = 0.0 if fetch_all else get_last_sync('research')
    cutoff = datetime.fromtimestamp(since_ts, tz=timezone.utc)

    all_items = []
    with get_client() as client:
        # Saved Messages
        for msg in client.iter_messages('me', limit=500):
            if msg.date < cutoff:
                break
            if msg.text:
                all_items.append({
                    "source": "saved",
                    "domain": "learning",
                    "text": msg.text,
                    "date": msg.date.isoformat(),
                })

        # Own channels
        for ch in channels:
            ch_id = ch.get('id')
            if not ch_id:
                continue
            for msg in client.iter_messages(ch_id, limit=200):
                if msg.date < cutoff:
                    break
                if msg.text:
                    all_items.append({
                        "source": ch.get('label', str(ch_id)),
                        "domain": ch.get('domain', 'learning'),
                        "text": msg.text,
                        "date": msg.date.isoformat(),
                    })

    if not all_items:
        print("ℹ️  Нет новых материалов для research.")
        return

    date_str = datetime.now().strftime('%Y-%m-%d')
    TELEGRAM_DIR.mkdir(parents=True, exist_ok=True)
    output_file = TELEGRAM_DIR / f'research-{date_str}.md'
    lines = [f'# Telegram Research — {date_str}\n']
    for item in all_items:
        lines.append(f"**{item['date'][:10]} [{item['source']}]:** {item['text']}\n")
    output_file.write_text('\n'.join(lines), encoding='utf-8')
    update_last_sync('research')
    print(f"✅ Research: {len(all_items)} сообщений → {output_file}")


def _students_gemini(messages: list) -> list:
    """Use Gemini to extract student support items from group messages."""
    formatted = '\n'.join(
        f"[{m['group']}][{m['sender']}][{m['date'][:10]}]: {m['text']}"
        for m in messages[:300]
    )

    prompt = f"""Extract student support items from these Telegram messages.
For each relevant message, output a JSON object with:
- question: what they're asking (string)
- urgency: "urgent" (no access/payment issue) | "normal" (technical question) | "fyi" (feedback)
- topic: "access" | "billing" | "technical" | "feedback" | "other"
- student: sender name
- group: group name

Return a JSON array. Skip greetings, off-topic, administrative messages.

Messages:
{formatted}"""

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not set in environment")
    client_ai = genai.Client(api_key=api_key)
    response = client_ai.models.generate_content(
        model=GEMINI_MODEL_SMART,
        contents=prompt,
        config=genai_types.GenerateContentConfig(response_mime_type="application/json"),
    )
    raw = response.text.strip()
    # Strip ```json ... ``` wrapper if present
    if raw.startswith('```'):
        raw = raw.split('\n', 1)[-1]
        if raw.endswith('```'):
            raw = raw.rsplit('```', 1)[0]
    try:
        return json.loads(raw)
    except Exception as e:
        print(f"⚠️  JSON parse error: {e}", file=sys.stderr)
        return []


def _create_notion_tasks(items):
    """Create urgent student support tasks in Notion."""
    notion_cli = REPO_ROOT / '.claude' / 'skills' / 'notion' / 'notion_cli.py'
    python = REPO_ROOT / '.venv' / 'bin' / 'python3'
    for item in items:
        title = f"[H2T] {item.get('topic', 'support').title()}: {item.get('question', '')[:60]}"
        summary = f"Student: {item.get('student', '?')} | Group: {item.get('group', '?')} | {item.get('question', '')}"
        cmd = [
            str(python), str(notion_cli), 'create-task',
            '--title', title,
            '--status', 'Not started',
            '--tags', 'hou2touch',
            '--priority', 'P0',
            '--summary', summary,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"  ✅ Notion task: {title[:50]}")
        else:
            print(f"  ⚠️  Notion error: {result.stderr[:100]}", file=sys.stderr)


def cmd_students(args):
    """student_groups → Gemini extraction → Notion urgent tasks."""
    cfg = load_chats_config()
    groups = cfg.get('student_groups', [])

    if not groups:
        print("⚠️  Нет групп в student_groups. Запусти scan-chats.", file=sys.stderr)
        return

    fetch_all = getattr(args, 'all', False)
    since_ts = 0.0 if fetch_all else get_last_sync('students')
    cutoff = datetime.fromtimestamp(since_ts, tz=timezone.utc)
    messages = []

    with get_client() as client:
        for group in groups:
            group_id = group.get('id')
            if not group_id:
                continue
            label = group.get('label', str(group_id))
            try:
                for msg in client.iter_messages(group_id, limit=300):
                    if msg.date < cutoff:
                        break
                    if msg.text:
                        sender = (
                            getattr(msg.sender, 'first_name', None)
                            or getattr(msg.sender, 'username', None)
                            or str(msg.sender_id)
                        )
                        messages.append({
                            "group": label,
                            "sender": sender,
                            "text": msg.text[:300],
                            "date": msg.date.isoformat(),
                        })
            except Exception as e:
                print(f"⚠️  Ошибка в {label}: {e}", file=sys.stderr)

    if not messages:
        print("ℹ️  Нет новых сообщений в студенческих группах.")
        return

    date_str = datetime.now().strftime('%Y-%m-%d')
    TELEGRAM_DIR.mkdir(parents=True, exist_ok=True)
    output_file = TELEGRAM_DIR / f'students-{date_str}.md'
    lines = [f'# Telegram Students — {date_str}\n']
    by_group: dict = {}
    for m in messages:
        by_group.setdefault(m['group'], []).append(m)
    for group, msgs in by_group.items():
        lines.append(f'## {group}\n')
        for m in msgs:
            lines.append(f"**{m['date'][:10]} {m['sender']}:** {m['text']}\n")
    output_file.write_text('\n'.join(lines), encoding='utf-8')
    update_last_sync('students')

    print(f"✅ Students: {len(messages)} сообщений из {len(by_group)} групп → {output_file}")


def cmd_cleanup(args):
    """Find and optionally archive dead/deleted Telegram chats."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=365)
    dead = []
    with get_client() as client:
        for dialog in client.iter_dialogs(limit=1000):
            entity = dialog.entity
            is_deleted = getattr(entity, 'deleted', False)
            is_old = dialog.date and dialog.date < cutoff
            is_broadcast = getattr(entity, 'broadcast', False)
            if is_deleted or (is_old and not is_broadcast):
                dead.append({
                    "name": dialog.name or "Deleted",
                    "id": dialog.id,
                    "last": str(dialog.date)[:10] if dialog.date else "unknown",
                    "deleted": is_deleted,
                })

    print(f"🗑️  Найдено {len(dead)} мёртвых диалогов:")
    for d in dead[:50]:
        flag = "🚫 deleted" if d['deleted'] else f"💤 last: {d['last']}"
        print(f"  {d['name']} [{flag}]")
    if len(dead) > 50:
        print(f"  ... и ещё {len(dead) - 50}")

    if args.archive:
        try:
            confirm = input(f"\nАрхивировать {len(dead)} диалогов? (yes/no): ").strip()
        except KeyboardInterrupt:
            print("\nОтменено.", file=sys.stderr)
            return
        if confirm == 'yes':
            with get_client() as client:
                for d in dead:
                    try:
                        client.edit_folder(d['id'], folder=1)  # folder=1 = Archive
                    except Exception as e:
                        print(f"  ⚠️  {d['name']}: {e}", file=sys.stderr)
            print("✅ Архивировано")
        else:
            print("Отменено.")


def cmd_sync(args):
    """Run all three pipelines sequentially."""
    import types
    no_all = types.SimpleNamespace(all=False)
    print("🔄 Запускаю все Telegram pipeline...\n", file=sys.stderr)
    print("=== 1/3 Saved Messages ===", file=sys.stderr)
    cmd_saved(no_all)
    print("\n=== 2/3 Channel Digest ===", file=sys.stderr)
    cmd_digest(no_all)
    print("\n=== 3/3 Work Chat Tasks ===", file=sys.stderr)
    cmd_tasks(no_all)
    print("\n✅ Telegram sync завершён.")


def cmd_auth(args):
    """Two-phase authentication with Telegram.

    Phase 1: --phone only → sends SMS code, saves phone_code_hash
    Phase 2: --phone + --code → signs in using saved hash
    Phase 2b: --phone + --code + --password → 2FA
    """
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    client = get_client()
    client.connect()

    try:
        if args.code is None and args.password is None:
            # Phase 1: request SMS code
            sent = client.send_code_request(args.phone)
            AUTH_STATE_FILE.write_text(json.dumps({
                'phone': args.phone,
                'phone_code_hash': sent.phone_code_hash,
            }))
            print(f"📱 Код отправлен на {args.phone}")
            print(f"Теперь запустите:")
            print(f"  telegram auth --phone {args.phone} --code <КОД>")
        elif args.password and args.code is None:
            # Phase 2b (retry): only password — code already accepted in session
            client.sign_in(password=args.password)
            me = client.get_me()
            AUTH_STATE_FILE.unlink(missing_ok=True)
            print(f"✅ Вошли как: {me.first_name} {me.last_name or ''} (@{me.username})")
        else:
            # Phase 2: sign in with code
            if not AUTH_STATE_FILE.exists():
                print("Error: сначала запустите auth --phone <номер>", file=sys.stderr)
                sys.exit(1)
            state = json.loads(AUTH_STATE_FILE.read_text())
            phone_code_hash = state['phone_code_hash']

            try:
                client.sign_in(args.phone, args.code, phone_code_hash=phone_code_hash)
            except SessionPasswordNeededError:
                if args.password is None:
                    print("🔑 Требуется пароль 2FA. Запустите:")
                    print(f"  telegram auth --phone {args.phone} --password <ПАРОЛЬ>")
                    sys.exit(0)
                client.sign_in(password=args.password)

            me = client.get_me()
            AUTH_STATE_FILE.unlink(missing_ok=True)
            print(f"✅ Вошли как: {me.first_name} {me.last_name or ''} (@{me.username})")
    finally:
        client.disconnect()


def main():
    parser = argparse.ArgumentParser(description='Telegram CLI — три pipeline')
    sub = parser.add_subparsers(dest='command')

    auth_p = sub.add_parser('auth', help='Аутентификация (двухфазная)')
    auth_p.add_argument('--phone', required=True, help='Номер телефона (+972...)')
    auth_p.add_argument('--code', help='SMS-код (шаг 2)')
    auth_p.add_argument('--password', help='Пароль 2FA (если включён)')

    saved_p = sub.add_parser('saved', help='Saved Messages → Obsidian MD')
    saved_p.add_argument('--all', action='store_true', help='Все сообщения (не только новые)')

    digest_p = sub.add_parser('digest', help='Образовательные каналы → Obsidian MD')
    digest_p.add_argument('--all', action='store_true')

    tasks_p = sub.add_parser('tasks', help='Рабочие чаты → Notion')
    tasks_p.add_argument('--all', action='store_true')

    chat_p = sub.add_parser('chat', help='Прочитать переписку с конкретным пользователем')
    chat_p.add_argument('--user', required=True, help='@username или числовой ID')
    chat_p.add_argument('--days', type=int, default=7, help='За сколько дней (default: 7)')
    chat_p.add_argument('--limit', type=int, default=200, help='Макс. кол-во сообщений (default: 200)')
    chat_p.add_argument('--all', action='store_true', help='Полная история без ограничений по дате и лимиту')

    sub.add_parser('sync', help='Все три pipeline последовательно')

    scan_p = sub.add_parser('scan-chats', help='Категоризировать чаты -> chats.yaml')
    scan_p.add_argument('--import-folders', action='store_true', help='Импортировать Telegram папки')
    scan_p.add_argument('--batch', type=int, default=20, help='Размер батча (default: 20)')
    scan_p.set_defaults(func=cmd_scan_chats)

    mentions_p = sub.add_parser('mentions', help='Найти @упоминания в рабочих чатах')
    mentions_p.add_argument('--days', type=int, default=7, help='За сколько дней (default: 7)')
    mentions_p.set_defaults(func=cmd_mentions)

    research_p = sub.add_parser('research', help='own_channels + Saved → vault/Learning')
    research_p.add_argument('--all', action='store_true', help='Полная история')
    research_p.set_defaults(func=cmd_research)

    students_p = sub.add_parser('students', help='Студенческие группы → Notion urgent tasks')
    students_p.add_argument('--all', action='store_true', help='Полная история')
    students_p.set_defaults(func=cmd_students)

    cleanup_p = sub.add_parser('cleanup', help='Найти мёртвые/удалённые чаты')
    cleanup_p.add_argument('--archive', action='store_true', help='Архивировать найденные')
    cleanup_p.set_defaults(func=cmd_cleanup)

    sub.add_parser('bootstrap', help='Загрузить все диалоги в кэш (один раз, потом 7-дневный TTL)').set_defaults(func=cmd_bootstrap)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    dispatch = {
        'auth': cmd_auth,
        'saved': cmd_saved,
        'digest': cmd_digest,
        'tasks': cmd_tasks,
        'chat': cmd_chat,
        'sync': cmd_sync,
        'scan-chats': cmd_scan_chats,
        'mentions': cmd_mentions,
        'research': cmd_research,
        'students': cmd_students,
        'cleanup': cmd_cleanup,
        'bootstrap': cmd_bootstrap,
    }

    if args.command in dispatch:
        dispatch[args.command](args)
    else:
        print(f"Command '{args.command}' — в разработке", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
