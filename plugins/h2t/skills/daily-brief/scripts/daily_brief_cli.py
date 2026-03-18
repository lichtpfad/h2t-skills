#!/usr/bin/env python3
"""
Daily Brief CLI — утренний брифинг из Calendar, Gmail и Notion.

Использование:
  python3 daily_brief_cli.py              # вывод в stdout (Markdown)
  python3 daily_brief_cli.py --json       # вывод JSON (для Claude)
  python3 daily_brief_cli.py --save       # сохранить в content/Meetings/
  python3 daily_brief_cli.py --days 2     # события на 2 дня вперёд
"""

import os
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
load_dotenv(Path.home() / '.dor' / 'secrets.env', override=False)

# Plugin layout: scripts/ -> daily-brief/ -> skills/
PLUGIN_SKILLS_ROOT = Path(__file__).parent.parent.parent
DOR_ROOT = Path(os.environ.get('DOR_ROOT', Path.home() / 'Projects' / 'DOR'))

# Sibling skill scripts (plugin layout)
sys.path.insert(0, str(PLUGIN_SKILLS_ROOT / 'gmail' / 'scripts'))
sys.path.insert(0, str(PLUGIN_SKILLS_ROOT / 'calendar' / 'scripts'))
sys.path.insert(0, str(PLUGIN_SKILLS_ROOT / 'notion' / 'scripts'))
# Fallback: DOR local skills layout
sys.path.insert(0, str(DOR_ROOT / '.claude' / 'skills' / 'gmail'))
sys.path.insert(0, str(DOR_ROOT / '.claude' / 'skills' / 'google-calendar'))
sys.path.insert(0, str(DOR_ROOT / '.claude' / 'skills' / 'notion'))

try:
    from gmail_cli import GmailClient
except ImportError as e:
    print(f"Error: cannot import GmailClient — {e}", file=sys.stderr)
    sys.exit(1)

try:
    from calendar_cli import get_calendar_service
except ImportError as e:
    print(f"Error: cannot import get_calendar_service — {e}", file=sys.stderr)
    sys.exit(1)

try:
    from notion_cli import NotionClient
except ImportError as e:
    print(f"Error: cannot import NotionClient — {e}", file=sys.stderr)
    sys.exit(1)

# Notion Tasks DB
TASKS_DB_ID = 'beabac7bf4314952a9327759c638d89f'


def get_calendar_events(days=1):
    """Get calendar events for next N days. Returns list of dicts."""
    service = get_calendar_service()

    # Use start-of-day (local time) to avoid capturing next-day all-day events
    local_today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    time_min = local_today.astimezone(timezone.utc).isoformat()
    time_max = (local_today + timedelta(days=days)).astimezone(timezone.utc).isoformat()

    result_raw = service.events().list(
        calendarId='primary',
        timeMin=time_min,
        timeMax=time_max,
        maxResults=20,
        singleEvents=True,
        orderBy='startTime'
    ).execute()

    events = []
    for event in result_raw.get('items', []):
        start = event['start'].get('dateTime', event['start'].get('date'))
        end = event['end'].get('dateTime', event['end'].get('date'))

        if 'T' in start:
            start_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
            end_dt = datetime.fromisoformat(end.replace('Z', '+00:00'))
            time_str = start_dt.strftime('%H:%M')
            duration_min = int((end_dt - start_dt).total_seconds() / 60)
            event_date = start_dt.strftime('%Y-%m-%d')
        else:
            time_str = 'весь день'
            duration_min = None
            event_date = start  # already "YYYY-MM-DD"

        events.append({
            'summary': event.get('summary', '(без названия)'),
            'date': event_date,
            'time': time_str,
            'duration_min': duration_min,
            'location': event.get('location', ''),
            'description': (event.get('description') or '')[:100],
        })

    return events


def get_gmail_important(max_results=10):
    """Get unread important emails. Returns list of dicts."""
    client = GmailClient()
    messages = client.list_messages(
        query='is:unread is:important',
        max_results=max_results
    )

    result = []
    for msg in messages:
        from_raw = msg.get('from', '')
        # Extract just the name part: "Name <email>" → "Name"
        from_name = from_raw.split('<')[0].strip() or from_raw
        result.append({
            'subject': msg.get('subject', '(без темы)'),
            'from': from_name,
            'from_email': from_raw,
            'date': msg.get('date', ''),
            'snippet': (msg.get('snippet') or '')[:120],
        })

    return result


def _extract_title(page):
    """Extract plain text title from Notion page properties."""
    for prop_data in page.get('properties', {}).values():
        if prop_data.get('type') == 'title':
            rich_text = prop_data.get('title', [])
            if rich_text:
                return rich_text[0].get('plain_text', '(без названия)')
    return '(без названия)'


def _extract_select(page, prop_name):
    """Extract select or status value from Notion page property."""
    prop = page.get('properties', {}).get(prop_name, {})
    prop_type = prop.get('type')
    if prop_type == 'select':
        sel = prop.get('select')
        if sel:
            return sel.get('name', '')
    elif prop_type == 'status':
        st = prop.get('status')
        if st:
            return st.get('name', '')
    return ''


def _extract_date(page, prop_name):
    """Extract date start from Notion page property."""
    prop = page.get('properties', {}).get(prop_name, {})
    if prop.get('type') == 'date':
        date_data = prop.get('date')
        if date_data:
            return date_data.get('start', '')
    return ''


def get_notion_tasks():
    """Get S/Action and S/Next Action tasks. Returns list of dicts."""
    client = NotionClient()

    # Filter: tasks not yet done (works for both 'status' and 'select' type)
    # Adjust values here when GTD statuses (S/Action, S/Next Action) are configured
    filter_dict = {
        "property": "Status",
        "status": {"does_not_equal": "Done"}
    }

    pages = client.query_database(TASKS_DB_ID, filter_dict=filter_dict, limit=30)

    result = []
    for page in pages:
        result.append({
            'title': _extract_title(page),
            'status': _extract_select(page, 'Status'),
            'due': _extract_date(page, 'Due Date'),
        })

    return result


def get_getcourse_support(max_age_days=30):
    """Get unanswered GetCourse tickets. Returns dict with counts and list."""
    # getcourse dependency tracked in issue #17 — requires DOR_ROOT/src/getcourse-export/
    getcourse_export_dir = DOR_ROOT / 'src' / 'getcourse-export'
    if not getcourse_export_dir.exists():
        raise ImportError(f"GetCourse export module not found at {getcourse_export_dir}. See issue #17.")
    sys.path.insert(0, str(getcourse_export_dir))
    from export_tickets import create_session, fetch_ticket_list, SPAM_DEPT_ID, PAGE_SIZE, DELAY_BETWEEN_REQUESTS
    import time
    import re

    STAFF_USER_IDS = {227178042, 244740225}

    session = create_session()
    all_tickets = []
    offset = 0

    while True:
        page = fetch_ticket_list(session, offset)
        models = page.get("models", [])
        if not models:
            break
        for t in models:
            if t.get("responsible_object_id") == SPAM_DEPT_ID:
                continue
            if t.get("status") == 0:
                all_tickets.append(t)
        left = page.get("leftCount", 0)
        if left <= 0:
            break
        offset = page.get("nextOffset", offset + PAGE_SIZE)
        time.sleep(DELAY_BETWEEN_REQUESTS)

    # Filter unanswered
    unanswered = []
    for t in all_tickets:
        conv = t.get("conversation", {})
        last_uid = conv.get("last_comment_user_id")
        if last_uid is None or last_uid not in STAFF_USER_IDS:
            # Calculate age
            last_at = conv.get("last_comment_at") or t.get("opened_at", "")
            age_hours = 0.0
            for fmt in ["%Y-%m-%d %H:%M:%S%z", "%Y-%m-%d %H:%M:%S"]:
                try:
                    dt = datetime.strptime(last_at, fmt)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    age_hours = (datetime.now(timezone.utc) - dt).total_seconds() / 3600
                    break
                except ValueError:
                    continue

            if age_hours > max_age_days * 24:
                continue

            preview = conv.get("text", "") or t.get("info", {}).get("comment", "")
            preview = re.sub(r"<[^>]+>", "", preview)
            if len(preview) > 120:
                preview = preview[:120] + "..."

            if age_hours < 1:
                age_str = f"{int(age_hours * 60)}m"
            elif age_hours < 24:
                age_str = f"{int(age_hours)}h"
            else:
                age_str = f"{int(age_hours / 24)}d"

            unanswered.append({
                "user": t.get("info", {}).get("title", ""),
                "age_str": age_str,
                "age_hours": round(age_hours, 1),
                "preview": preview,
            })

    unanswered.sort(key=lambda x: x["age_hours"], reverse=True)

    return {
        "total_open": len(all_tickets),
        "unanswered": len(unanswered),
        "tickets": unanswered[:10],
    }


def get_telegram_mentions(max_age_hours=168):
    """Read Telegram @mentions from cache file. Returns None if unavailable."""
    cache_file = Path.home() / '.config' / 'telegram' / 'mentions_cache.json'
    if not cache_file.exists():
        return None
    try:
        data = json.loads(cache_file.read_text())
        mentions = [m for m in data.get('mentions', []) if m.get('age_hours', 0) <= max_age_hours]
        return {"total": data.get("total", 0), "mentions": mentions}
    except Exception:
        return None


def format_markdown(events, emails, tasks, date_str, tomorrow_events=None, support=None, mentions=None):
    """Format collected data as Markdown daily brief."""
    lines = [f"# Daily Brief — {date_str}", ""]

    # Calendar — today
    lines.append(f"## 📅 Сегодня ({len(events)} событий)")
    if events:
        for e in events:
            dur = f" ({e['duration_min']}min)" if e['duration_min'] else ""
            loc = f" @ {e['location']}" if e['location'] else ""
            lines.append(f"- {e['time']}: **{e['summary']}**{dur}{loc}")
    else:
        lines.append("- Событий нет")
    lines.append("")

    # Calendar — tomorrow
    if tomorrow_events is not None:
        lines.append(f"## 🔭 Завтра ({len(tomorrow_events)} событий)")
        if tomorrow_events:
            for e in tomorrow_events:
                dur = f" ({e['duration_min']}min)" if e['duration_min'] else ""
                loc = f" @ {e['location']}" if e['location'] else ""
                lines.append(f"- {e['time']}: **{e['summary']}**{dur}{loc}")
        else:
            lines.append("- Событий нет")
        lines.append("")

    # Gmail
    lines.append(f"## 📧 Gmail (unread important: {len(emails)})")
    if emails:
        for msg in emails:
            lines.append(f"- [{msg['subject']}] — {msg['from']}")
    else:
        lines.append("- Нет важных непрочитанных")
    lines.append("")

    # Notion Tasks
    lines.append(f"## ✅ Tasks ({len(tasks)} активных)")
    if tasks:
        for t in tasks[:15]:
            due = f" `{t['due']}`" if t['due'] else ""
            status = f" [{t['status']}]" if t['status'] else ""
            lines.append(f"- {t['title']}{status}{due}")
        if len(tasks) > 15:
            lines.append(f"- _...и ещё {len(tasks) - 15}_")
    else:
        lines.append("- Нет активных задач")
    lines.append("")

    # Mentions
    if mentions:
        lines.append(f"## 📣 Mentions ({len(mentions['mentions'])} unread)")
        if mentions['mentions']:
            for m in mentions['mentions'][:5]:
                age_str = f"{m.get('age_hours', 0):.0f}h"
                chat = m.get('chat', '')
                sender = m.get('sender', '')
                text = (m.get('text') or '')[:100]
                lines.append(f"- **{chat}** | {sender}: {text} — {age_str}")
        else:
            lines.append("- нет упоминаний")
        lines.append("")

    # GetCourse Support
    if support:
        lines.append(f"## 🎫 Support (открытых: {support['total_open']}, неотвеченных: {support['unanswered']})")
        if support['tickets']:
            for t in support['tickets']:
                lines.append(f"- [{t['age_str']:>4}] {t['user']}: {t['preview'][:70]}")
        elif support['unanswered'] == 0:
            lines.append("- Все тикеты отвечены")
        lines.append("")

    # Telegram (читаем готовые MD-файлы, Telethon не запускаем)
    telegram_dir = REPO_ROOT / 'content' / 'learning' / 'telegram'
    digest_file = telegram_dir / f'digest-{date_str}.md'
    saved_file = telegram_dir / f'saved-{date_str}.md'
    if digest_file.exists() or saved_file.exists():
        lines.append("## 📱 Telegram")
        if digest_file.exists():
            content = digest_file.read_text(encoding='utf-8')
            if '💡 Top' in content:
                idx = content.find('## 💡')
                lines.append(content[idx:idx + 400].strip())
            lines.append(f"\n→ [Полный дайджест](content/learning/telegram/digest-{date_str}.md)")
        if saved_file.exists():
            lines.append(f"→ [Saved Messages](content/learning/telegram/saved-{date_str}.md)")
        lines.append("")

    # Metrics
    lines.append("## 📊 Metrics")
    support_str = f" | Unanswered tickets: {support['unanswered']}" if support else ""
    lines.append(
        f"Events: {len(events)} | "
        f"Unread important: {len(emails)} | "
        f"Tasks: {len(tasks)}"
        f"{support_str}"
    )
    lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description='Daily Brief — morning briefing from Calendar, Gmail, Notion'
    )
    parser.add_argument('--save', action='store_true',
                        help='Save brief to content/Meetings/daily-brief-YYYY-MM-DD.md')
    parser.add_argument('--json', action='store_true', dest='json_output',
                        help='Output raw JSON (for Claude to format by domain)')
    parser.add_argument('--days', type=int, default=1,
                        help='Days ahead for calendar (default: 1)')
    args = parser.parse_args()

    date_str = datetime.now().strftime('%Y-%m-%d')

    print("⏳ Собираю данные...", file=sys.stderr)

    events, tomorrow_events, emails, tasks, support, mentions, errors = [], [], [], [], None, None, []

    try:
        all_events = get_calendar_events(days=2)
        tomorrow_str = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
        events = [e for e in all_events if e['date'] == date_str]
        tomorrow_events = [e for e in all_events if e['date'] == tomorrow_str]
        print(f"  ✅ Calendar: {len(events)} сегодня, {len(tomorrow_events)} завтра", file=sys.stderr)
    except Exception as e:
        errors.append(f"Calendar: {e}")
        print(f"  ❌ Calendar: {e}", file=sys.stderr)

    try:
        emails = get_gmail_important()
        print(f"  ✅ Gmail: {len(emails)} писем", file=sys.stderr)
    except Exception as e:
        errors.append(f"Gmail: {e}")
        print(f"  ❌ Gmail: {e}", file=sys.stderr)

    try:
        tasks = get_notion_tasks()
        print(f"  ✅ Notion: {len(tasks)} задач", file=sys.stderr)
    except Exception as e:
        errors.append(f"Notion: {e}")
        print(f"  ❌ Notion: {e}", file=sys.stderr)

    try:
        support = get_getcourse_support(max_age_days=30)
        print(f"  ✅ GetCourse: {support['unanswered']} неотвеченных из {support['total_open']} открытых", file=sys.stderr)
    except Exception as e:
        errors.append(f"GetCourse: {e}")
        print(f"  ❌ GetCourse: {e}", file=sys.stderr)

    try:
        mentions = get_telegram_mentions()
        if mentions:
            print(f"  ✅ Telegram mentions: {len(mentions['mentions'])} unread", file=sys.stderr)
        else:
            mentions = None
    except Exception as e:
        mentions = None
        print(f"  ⚠️  Telegram mentions: {e}", file=sys.stderr)

    if args.json_output:
        print(json.dumps({
            'date': date_str,
            'events': events,
            'tomorrow_events': tomorrow_events,
            'emails': emails,
            'tasks': tasks,
            'support': support,
            'errors': errors,
        }, ensure_ascii=False, indent=2))
        if args.save:
            brief = format_markdown(events, emails, tasks, date_str, tomorrow_events, support, mentions=mentions)
            daily_dir = REPO_ROOT / 'content' / 'Daily'
            daily_dir.mkdir(parents=True, exist_ok=True)
            output_file = daily_dir / f'{date_str}.md'
            output_file.write_text(brief, encoding='utf-8')
            print(f"\n💾 Сохранено: {output_file}", file=sys.stderr)
        return

    brief = format_markdown(events, emails, tasks, date_str, tomorrow_events, support, mentions=mentions)
    print(brief)

    if args.save:
        daily_dir = REPO_ROOT / 'content' / 'Daily'
        daily_dir.mkdir(parents=True, exist_ok=True)
        output_file = daily_dir / f'{date_str}.md'
        output_file.write_text(brief, encoding='utf-8')
        print(f"\n💾 Сохранено: {output_file}", file=sys.stderr)


if __name__ == '__main__':
    main()
