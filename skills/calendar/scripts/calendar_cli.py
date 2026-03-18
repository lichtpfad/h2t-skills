#!/usr/bin/env python3
"""
Прямой CLI доступ к Google Calendar используя существующие OAuth токены
"""

import os
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path.home() / '.dor' / 'secrets.env', override=False)

try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
except ImportError:
    print("❌ Ошибка: Требуется установить Google Calendar API библиотеку")
    print("Установите: pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client")
    sys.exit(1)

# Пути к credentials и tokens
CONFIG_DIR = Path.home() / ".config" / "google-calendar-mcp"
CREDENTIALS_FILE = CONFIG_DIR / "credentials.json"
TOKEN_FILE = CONFIG_DIR / "tokens.json"

def get_calendar_service():
    """Создает и возвращает Google Calendar API service"""

    if not TOKEN_FILE.exists():
        print(f"❌ Файл с токенами не найден: {TOKEN_FILE}")
        print("Запустите аутентификацию: запусти gmail skill для OAuth flow")
        sys.exit(1)

    with open(TOKEN_FILE) as f:
        token_data = json.load(f)

    # Поддержка legacy вложенного формата @cocal/google-calendar-mcp
    if 'normal' in token_data:
        token_data = token_data['normal']

    # Добавляем client_id/secret если их нет в токене (они есть в credentials.json)
    if 'client_id' not in token_data:
        if not CREDENTIALS_FILE.exists():
            print(f"❌ Файл credentials не найден: {CREDENTIALS_FILE}")
            sys.exit(1)
        with open(CREDENTIALS_FILE) as f:
            creds_data = json.load(f)
        installed = creds_data.get('installed', creds_data)
        token_data['client_id'] = installed.get('client_id')
        token_data['client_secret'] = installed.get('client_secret')
        token_data.setdefault('token_uri', installed.get('token_uri', 'https://oauth2.googleapis.com/token'))

    # Используем скопы из токена — не переопределяем, чтобы не было invalid_scope при refresh
    CALENDAR_SCOPE = ['https://www.googleapis.com/auth/calendar']
    effective_scopes = token_data.get('scopes') or CALENDAR_SCOPE
    if isinstance(effective_scopes, str):
        effective_scopes = effective_scopes.split()

    creds = Credentials.from_authorized_user_info(token_data, effective_scopes)

    # Обновляем токен если истек, сохраняем в плоском формате
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        TOKEN_FILE.write_text(creds.to_json())

    return build('calendar', 'v3', credentials=creds)

def list_events(days=1, max_results=10):
    """Список событий на указанное количество дней"""
    service = get_calendar_service()

    # Время: от сейчас до +days дней
    now = datetime.now(timezone.utc)
    time_min = now.isoformat()
    time_max = (now + timedelta(days=days)).isoformat()

    print(f"\n📅 События на {days} {'день' if days == 1 else 'дней'} (с {now.strftime('%d.%m.%Y %H:%M')}):\n")

    # Получаем события
    events_result = service.events().list(
        calendarId='primary',
        timeMin=time_min,
        timeMax=time_max,
        maxResults=max_results,
        singleEvents=True,
        orderBy='startTime'
    ).execute()

    events = events_result.get('items', [])

    if not events:
        print("  Нет событий на этот период")
        return

    # Группируем по датам
    events_by_date = {}
    for event in events:
        start = event['start'].get('dateTime', event['start'].get('date'))

        # Парсим дату
        if 'T' in start:
            dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
        else:
            dt = datetime.fromisoformat(start).replace(tzinfo=timezone.utc)

        date_key = dt.strftime('%Y-%m-%d')
        if date_key not in events_by_date:
            events_by_date[date_key] = []
        events_by_date[date_key].append((dt, event))

    # Выводим события по датам
    for date_key in sorted(events_by_date.keys()):
        dt = datetime.fromisoformat(date_key)
        print(f"  {dt.strftime('%d %B %Y (%A)')}:")

        for _, event in sorted(events_by_date[date_key], key=lambda x: x[0]):
            start = event['start'].get('dateTime', event['start'].get('date'))
            end = event['end'].get('dateTime', event['end'].get('date'))
            summary = event.get('summary', '(без названия)')

            # Форматируем время
            if 'T' in start:
                start_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
                end_dt = datetime.fromisoformat(end.replace('Z', '+00:00'))
                time_str = f"{start_dt.strftime('%H:%M')}-{end_dt.strftime('%H:%M')}"
            else:
                time_str = "весь день"

            print(f"    • {time_str}: {summary}")

            # Дополнительная информация
            if event.get('location'):
                print(f"      📍 {event['location']}")
            if event.get('description'):
                desc = event['description'][:100] + '...' if len(event['description']) > 100 else event['description']
                print(f"      📝 {desc}")

        print()

def create_event(summary, date, time, duration=60, description=None, attendees=None, timezone='Asia/Jerusalem'):
    """Создание нового события"""
    service = get_calendar_service()

    # Парсим дату и время
    start_dt = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
    end_dt = start_dt + timedelta(minutes=duration)

    event = {
        'summary': summary,
        'start': {
            'dateTime': start_dt.isoformat(),
            'timeZone': timezone,
        },
        'end': {
            'dateTime': end_dt.isoformat(),
            'timeZone': timezone,
        },
    }

    if description:
        event['description'] = description

    if attendees:
        event['attendees'] = [{'email': e.strip()} for e in attendees.split(',')]

    send_updates = 'all' if attendees else 'none'
    created_event = service.events().insert(
        calendarId='primary', body=event, sendUpdates=send_updates
    ).execute()

    print(f"\n✅ Событие создано:")
    print(f"   Название: {summary}")
    print(f"   Дата: {start_dt.strftime('%d.%m.%Y %H:%M')} - {end_dt.strftime('%H:%M')} ({timezone})")
    print(f"   ID: {created_event['id']}")
    print(f"   Ссылка: {created_event.get('htmlLink', 'N/A')}")
    if attendees:
        print(f"   Приглашения отправлены: {attendees}")
    print()

def delete_event(event_id, confirm=False):
    """Удаление события по ID"""
    service = get_calendar_service()

    if not confirm:
        # Показываем детали события перед удалением
        try:
            event = service.events().get(calendarId='primary', eventId=event_id).execute()
            summary = event.get('summary', '(без названия)')
            start = event['start'].get('dateTime', event['start'].get('date'))
            if 'T' in start:
                dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
                time_str = dt.strftime('%d.%m.%Y %H:%M')
            else:
                dt = datetime.fromisoformat(start)
                time_str = dt.strftime('%d.%m.%Y') + ' (весь день)'
            print(f"\n⚠️  Событие для удаления:")
            print(f"   Название: {summary}")
            print(f"   Время: {time_str}")
            print(f"\nДобавьте --confirm для подтверждения удаления")
        except Exception as e:
            print(f"❌ Событие не найдено: {e}")
        return

    service.events().delete(calendarId='primary', eventId=event_id).execute()
    print(f"\n✅ Событие удалено: {event_id}\n")


def search_events(query, max_results=10):
    """Поиск событий по запросу"""
    service = get_calendar_service()

    print(f"\n🔍 Поиск событий: '{query}'\n")

    # Ищем события
    events_result = service.events().list(
        calendarId='primary',
        q=query,
        maxResults=max_results,
        singleEvents=True,
        orderBy='startTime'
    ).execute()

    events = events_result.get('items', [])

    if not events:
        print("  Ничего не найдено")
        return

    for event in events:
        start = event['start'].get('dateTime', event['start'].get('date'))
        summary = event.get('summary', '(без названия)')

        if 'T' in start:
            dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
            print(f"  • {summary}")
            print(f"    {dt.strftime('%d.%m.%Y %H:%M')}")
        else:
            dt = datetime.fromisoformat(start)
            print(f"  • {summary}")
            print(f"    {dt.strftime('%d.%m.%Y')} (весь день)")

        if event.get('id'):
            print(f"    ID: {event['id']}")
        print()

def main():
    """Main CLI"""
    if len(sys.argv) < 2:
        print("Использование:")
        print("  python calendar_cli.py list [days]")
        print("  python calendar_cli.py search <query>")
        print("  python calendar_cli.py create <summary> <date> <time> [duration] [description]")
        print("  python calendar_cli.py delete <event_id> [--confirm]")
        print("\nПримеры:")
        print("  python calendar_cli.py list")
        print("  python calendar_cli.py list 7")
        print("  python calendar_cli.py search 'встреча'")
        print("  python calendar_cli.py create 'Встреча' 2026-02-20 14:00 60 'Важная встреча'")
        print("  python calendar_cli.py delete abc123def456 --confirm")
        sys.exit(1)

    command = sys.argv[1]

    try:
        if command == 'list':
            days = int(sys.argv[2]) if len(sys.argv) > 2 else 1
            list_events(days=days)

        elif command == 'search':
            if len(sys.argv) < 3:
                print("❌ Укажите поисковый запрос")
                sys.exit(1)
            query = ' '.join(sys.argv[2:])
            search_events(query)

        elif command == 'delete':
            if len(sys.argv) < 3:
                print("❌ Укажите ID события")
                print("Использование: delete <event_id> [--confirm]")
                sys.exit(1)
            event_id = sys.argv[2]
            confirm = '--confirm' in sys.argv
            delete_event(event_id, confirm=confirm)

        elif command == 'create':
            if len(sys.argv) < 5:
                print("❌ Недостаточно аргументов")
                print("Использование: create <summary> <date> <time> [duration] [description] [--attendees emails] [--tz timezone]")
                sys.exit(1)

            summary = sys.argv[2]
            date = sys.argv[3]
            time = sys.argv[4]

            # Parse remaining positional args and flags
            remaining = sys.argv[5:]
            duration = 60
            description = None
            attendees = None
            timezone = 'Asia/Jerusalem'

            i = 0
            positional = 0
            while i < len(remaining):
                if remaining[i] == '--attendees' and i + 1 < len(remaining):
                    attendees = remaining[i + 1]
                    i += 2
                elif remaining[i] == '--tz' and i + 1 < len(remaining):
                    timezone = remaining[i + 1]
                    i += 2
                else:
                    if positional == 0:
                        duration = int(remaining[i])
                    elif positional == 1:
                        description = remaining[i]
                    positional += 1
                    i += 1

            create_event(summary, date, time, duration, description, attendees, timezone)

        else:
            print(f"❌ Неизвестная команда: {command}")
            sys.exit(1)

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()
