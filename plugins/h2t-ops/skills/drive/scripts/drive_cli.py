#!/usr/bin/env python3
"""
Google Drive CLI — list, search, download, export, upload.
"""

import argparse
import io
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path.home() / '.dor' / 'secrets.env', override=False)

try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
except ImportError:
    print("Error: google-api-python-client not installed", file=sys.stderr)
    sys.exit(1)

CONFIG_DIR = Path.home() / '.config' / 'google-calendar-mcp'
TOKEN_FILE = CONFIG_DIR / 'tokens.json'
CREDENTIALS_FILE = CONFIG_DIR / 'credentials.json'

def get_drive_service():
    """Build Drive API service from shared OAuth token."""
    if not TOKEN_FILE.exists():
        print(f"Token not found: {TOKEN_FILE}", file=sys.stderr)
        print("Re-authenticate: run gmail skill to trigger OAuth flow", file=sys.stderr)
        sys.exit(1)

    with open(TOKEN_FILE) as f:
        token_data = json.load(f)

    # tokens.json uses a flat structure with key 'token' (not 'access_token')
    # If it happens to be nested under 'normal', unwrap it
    if 'normal' in token_data:
        token_data = token_data['normal']

    # Merge client credentials from credentials.json if not already present
    if 'client_id' not in token_data:
        if not CREDENTIALS_FILE.exists():
            print(f"Credentials not found: {CREDENTIALS_FILE}", file=sys.stderr)
            print("Download OAuth credentials from Google Cloud Console", file=sys.stderr)
            sys.exit(1)
        with open(CREDENTIALS_FILE) as f:
            creds_data = json.load(f)
        installed = creds_data.get('installed', creds_data)
        token_data['client_id'] = installed.get('client_id')
        token_data['client_secret'] = installed.get('client_secret')
        token_data['token_uri'] = installed.get('token_uri', 'https://oauth2.googleapis.com/token')

    DRIVE_SCOPE = ['https://www.googleapis.com/auth/drive']
    existing_scopes = token_data.get('scopes', [])
    if isinstance(existing_scopes, str):
        existing_scopes = existing_scopes.split()

    creds = Credentials.from_authorized_user_info(
        token_data,
        scopes=existing_scopes or DRIVE_SCOPE,
    )

    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        # Write back the full credential state
        TOKEN_FILE.write_text(creds.to_json())

    return build('drive', 'v3', credentials=creds)


def list_files(folder_name=None, max_results=None):
    """List files in a Drive folder (default: root). Paginates through all results."""
    service = get_drive_service()

    if folder_name:
        safe_name = folder_name.replace("'", "\\'")
        resp = service.files().list(
            q=f"name='{safe_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false",
            fields='files(id, name)',
            pageSize=5,
        ).execute()
        folders = resp.get('files', [])
        if not folders:
            print(f"Папка '{folder_name}' не найдена. Запустите: drive list", file=sys.stderr)
            sys.exit(1)
        folder_id = folders[0]['id']
        query = f"'{folder_id}' in parents and trashed=false"
    else:
        query = "'root' in parents and trashed=false"

    files = []
    page_token = None
    while True:
        resp = service.files().list(
            q=query,
            fields='nextPageToken, files(id, name, mimeType, modifiedTime, size)',
            pageSize=1000,
            orderBy='modifiedTime desc',
            pageToken=page_token,
        ).execute()
        files.extend(resp.get('files', []))
        page_token = resp.get('nextPageToken')
        if not page_token or (max_results and len(files) >= max_results):
            break

    if max_results:
        files = files[:max_results]

    if not files:
        print("  (пусто)")
        return

    header = f"{'Имя':<50} {'Тип':<15} {'Изменён'}"
    print(f"\n{'Корень' if not folder_name else folder_name} ({len(files)} файлов):\n")
    print(header)
    print('-' * 80)
    for f in files:
        mime = f.get('mimeType', '').split('.')[-1][:14]
        modified = f.get('modifiedTime', '')[:10]
        print(f"  {f['name']:<48} {mime:<15} {modified}  [{f['id'][:12]}...]")


def search_files(query_str, mime_filter=None, max_results=None):
    """Full-text search across Drive. Paginates through all results."""
    service = get_drive_service()

    safe_query = query_str.replace("'", "\\'")
    q = f"fullText contains '{safe_query}' and trashed=false"
    if mime_filter == 'docx':
        q += " and mimeType='application/vnd.openxmlformats-officedocument.wordprocessingml.document'"
    elif mime_filter == 'folder':
        q += " and mimeType='application/vnd.google-apps.folder'"

    files = []
    page_token = None
    while True:
        try:
            resp = service.files().list(
                q=q,
                fields='nextPageToken, files(id, name, mimeType, modifiedTime, parents)',
                pageSize=1000,
                orderBy='modifiedTime desc',
                pageToken=page_token,
            ).execute()
        except Exception as e:
            print(f"Drive API error: {e}", file=sys.stderr)
            sys.exit(1)
        files.extend(resp.get('files', []))
        page_token = resp.get('nextPageToken')
        if not page_token or (max_results and len(files) >= max_results):
            break

    if max_results:
        files = files[:max_results]

    print(f"\nРезультаты для '{query_str}': {len(files)} файлов\n")
    for f in files:
        modified = f.get('modifiedTime', '')[:10]
        print(f"  {f['name']:<50} {modified}  {f['id']}")


def download_file(file_id, dest_path=None):
    """Download a file from Drive by ID."""
    service = get_drive_service()

    try:
        meta = service.files().get(fileId=file_id, fields='name, mimeType, size').execute()
    except Exception as e:
        print(f"Drive API error: {e}", file=sys.stderr)
        sys.exit(1)

    filename = meta['name']
    dest = Path(dest_path) if dest_path else Path('.') / filename

    print(f"Скачиваю: {filename} -> {dest}")

    request = service.files().get_media(fileId=file_id)
    buf = io.BytesIO()
    downloader = MediaIoBaseDownload(buf, request)

    done = False
    try:
        while not done:
            status, done = downloader.next_chunk()
            if status:
                print(f"   {int(status.progress() * 100)}%", end='\r')
    except Exception as e:
        print(f"\n❌ Ошибка скачивания: {e}", file=sys.stderr)
        sys.exit(1)

    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(buf.getvalue())
    print(f"\nСохранено: {dest} ({dest.stat().st_size} bytes)")
    return dest


GOOGLE_EXPORT_FORMATS = {
    'application/vnd.google-apps.document': {
        'text': ('text/plain', '.txt'),
        'md':   ('text/html', '.md'),   # HTML → Markdown via html2text
        'docx': ('application/vnd.openxmlformats-officedocument.wordprocessingml.document', '.docx'),
        'pdf':  ('application/pdf', '.pdf'),
        'default': 'text',
    },
    'application/vnd.google-apps.spreadsheet': {
        'csv':  ('text/csv', '.csv'),
        'xlsx': ('application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', '.xlsx'),
        'pdf':  ('application/pdf', '.pdf'),
        'default': 'csv',
    },
    'application/vnd.google-apps.presentation': {
        'pdf':  ('application/pdf', '.pdf'),
        'pptx': ('application/vnd.openxmlformats-officedocument.presentationml.presentation', '.pptx'),
        'default': 'pdf',
    },
}


def export_file(file_id, dest_path=None, fmt=None, print_stdout=False):
    """Export a Google Docs editor file (Doc/Sheet/Slides) to local file or stdout."""
    service = get_drive_service()

    try:
        meta = service.files().get(fileId=file_id, fields='name, mimeType').execute()
    except Exception as e:
        print(f"Drive API error: {e}", file=sys.stderr)
        sys.exit(1)

    mime_type = meta['mimeType']
    name = meta['name']
    formats = GOOGLE_EXPORT_FORMATS.get(mime_type)

    if not formats:
        print(f"❌ Файл '{name}' (mimeType: {mime_type}) не является Google Docs editor файлом.", file=sys.stderr)
        print("   Используйте 'download' для бинарных файлов.", file=sys.stderr)
        sys.exit(1)

    chosen = fmt or formats['default']
    if chosen not in formats or chosen == 'default':
        print(f"❌ Формат '{chosen}' недоступен для {mime_type}.", file=sys.stderr)
        available = [k for k in formats if k != 'default']
        print(f"   Доступные форматы: {', '.join(available)}", file=sys.stderr)
        sys.exit(1)

    export_mime, ext = formats[chosen]

    try:
        content = service.files().export(fileId=file_id, mimeType=export_mime).execute()
    except Exception as e:
        print(f"❌ Ошибка экспорта: {e}", file=sys.stderr)
        sys.exit(1)

    # HTML → Markdown conversion for 'md' format
    if chosen == 'md':
        try:
            import html2text
            h = html2text.HTML2Text()
            h.ignore_links = False
            h.body_width = 0  # no line wrapping
            html_str = content.decode('utf-8') if isinstance(content, bytes) else content
            content = h.handle(html_str).encode('utf-8')
        except ImportError:
            print("❌ Установите html2text: pip install html2text", file=sys.stderr)
            sys.exit(1)

    if print_stdout:
        text = content.decode('utf-8') if isinstance(content, bytes) else content
        print(text)
        return

    if dest_path:
        dest = Path(dest_path)
    else:
        safe_name = name.replace('/', '-').replace(':', '-')
        dest = Path('.') / (safe_name + ext)

    dest.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, bytes):
        dest.write_bytes(content)
    else:
        dest.write_text(content, encoding='utf-8')

    print(f"✅ Экспортировано: {name}")
    print(f"   Формат: {chosen} ({export_mime})")
    print(f"   Сохранено: {dest} ({dest.stat().st_size} bytes)")
    return dest


# Auto-conversion map: file extension → (source_mime, target_google_mime)
UPLOAD_CONVERT_MAP = {
    '.md':   ('text/markdown', 'application/vnd.google-apps.document'),
    '.txt':  ('text/plain', 'application/vnd.google-apps.document'),
    '.html': ('text/html', 'application/vnd.google-apps.document'),
    '.docx': ('application/vnd.openxmlformats-officedocument.wordprocessingml.document',
              'application/vnd.google-apps.document'),
    '.csv':  ('text/csv', 'application/vnd.google-apps.spreadsheet'),
    '.tsv':  ('text/tab-separated-values', 'application/vnd.google-apps.spreadsheet'),
    '.xlsx': ('application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
              'application/vnd.google-apps.spreadsheet'),
}


def _resolve_folder_id(service, folder_name):
    """Return (folder_id, folder_display_name) for a given folder name, or (None, 'root')."""
    if not folder_name or folder_name == 'root':
        return None, 'root'
    safe_name = folder_name.replace("'", "\\'")
    resp = service.files().list(
        q=f"name='{safe_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false",
        fields='files(id, name)',
        pageSize=5,
    ).execute()
    folders = resp.get('files', [])
    if not folders:
        print(f"❌ Папка '{folder_name}' не найдена на Drive", file=sys.stderr)
        print("   Список папок: drive folders", file=sys.stderr)
        sys.exit(1)
    return folders[0]['id'], folders[0]['name']


def list_folders_cmd(parent_name=None, max_results=50):
    """List folders at root or inside a specific folder."""
    service = get_drive_service()

    if parent_name:
        parent_id, display = _resolve_folder_id(service, parent_name)
        query = f"'{parent_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
        header = f"Папки внутри '{display}':"
    else:
        query = "'root' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
        header = "Папки в корне Drive:"

    resp = service.files().list(
        q=query,
        fields='files(id, name, modifiedTime)',
        pageSize=max_results,
        orderBy='name',
    ).execute()

    folders = resp.get('files', [])
    print(f"\n{header}\n")
    if not folders:
        print("  (нет папок)")
        return

    for i, f in enumerate(folders, 1):
        modified = f.get('modifiedTime', '')[:10]
        print(f"  {i:>2}. {f['name']:<45} {modified}  {f['id']}")
    print()


def upload_file(file_path, folder_name=None, no_convert=False):
    """Upload a file to Drive. Auto-converts .md/.txt/.docx to Google Doc, .csv/.xlsx to Sheets."""
    import mimetypes

    service = get_drive_service()

    src = Path(file_path)
    if not src.exists():
        print(f"❌ Файл не найден: {file_path}", file=sys.stderr)
        sys.exit(1)

    # --- Determine destination folder ---
    if folder_name:
        folder_id, folder_display = _resolve_folder_id(service, folder_name)
    else:
        # Interactive: list root folders and ask
        resp = service.files().list(
            q="'root' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false",
            fields='files(id, name)',
            pageSize=50,
            orderBy='name',
        ).execute()
        folders = resp.get('files', [])

        print("\nКуда загрузить?\n")
        print("   0. [Корень Drive]")
        for i, f in enumerate(folders, 1):
            print(f"  {i:>2}. {f['name']}")
        print()

        choice = input("Выберите папку (номер): ").strip()
        try:
            idx = int(choice)
            if idx == 0:
                folder_id, folder_display = None, 'root'
            elif 1 <= idx <= len(folders):
                folder_id = folders[idx - 1]['id']
                folder_display = folders[idx - 1]['name']
            else:
                print("❌ Неверный выбор", file=sys.stderr)
                sys.exit(1)
        except ValueError:
            print("❌ Введите число", file=sys.stderr)
            sys.exit(1)

    # --- Determine MIME types ---
    ext = src.suffix.lower()
    convert_info = None if no_convert else UPLOAD_CONVERT_MAP.get(ext)

    if convert_info:
        source_mime, target_mime = convert_info
        type_label = 'Google Doc' if 'document' in target_mime else 'Google Sheet'
        dest_name = src.stem  # Google editor files have no extension
        print(f"\nЗагружаю: {src.name} → {type_label}")
    else:
        source_mime = mimetypes.guess_type(str(src))[0] or 'application/octet-stream'
        target_mime = None
        dest_name = src.name
        print(f"\nЗагружаю: {src.name} (без конвертации, {source_mime})")

    print(f"Папка:    {folder_display}")

    # --- Build metadata ---
    metadata = {'name': dest_name}
    if folder_id:
        metadata['parents'] = [folder_id]
    if target_mime:
        metadata['mimeType'] = target_mime

    # --- Upload ---
    media = MediaFileUpload(str(src), mimetype=source_mime, resumable=True)
    try:
        result = service.files().create(
            body=metadata,
            media_body=media,
            fields='id, name, mimeType, webViewLink',
        ).execute()
    except Exception as e:
        print(f"❌ Ошибка загрузки: {e}", file=sys.stderr)
        sys.exit(1)

    print("\n✅ Загружено:")
    print(f"   Имя:    {result['name']}")
    print(f"   ID:     {result['id']}")
    print(f"   Ссылка: {result.get('webViewLink', 'N/A')}")
    return result


def sync_meetings(dry_run=False, folder_name='MeetGeek Files'):
    """Retired legacy Drive-owned meeting backfill workflow."""
    _ = (dry_run, folder_name)
    print(
        "drive sync-meetings is retired: meeting backfill is a POS/coordinator "
        "workflow, not a Drive provider capability. Use h2t-ops drive export "
        "for individual Drive files and h2t-ops meetgeek for MeetGeek API "
        "artifacts. Future batch backfill belongs to POS meeting intake.",
        file=sys.stderr,
    )
    sys.exit(2)


def main():
    parser = argparse.ArgumentParser(description='Google Drive CLI (read-only)')
    subparsers = parser.add_subparsers(dest='command')

    # list
    p_list = subparsers.add_parser('list', help='List files in folder')
    p_list.add_argument('folder', nargs='?', default=None, help='Folder name (default: root)')
    p_list.add_argument('--max', type=int, default=None, help='Maximum number of results (default: all)')

    # search
    p_search = subparsers.add_parser('search', help='Search files')
    p_search.add_argument('query', help='Search query')
    p_search.add_argument('--type', choices=['docx', 'folder'], dest='mime_filter')
    p_search.add_argument('--max', type=int, default=None, help='Maximum number of results (default: all)')

    # download
    p_dl = subparsers.add_parser('download', help='Download file by ID')
    p_dl.add_argument('file_id', help='Drive file ID')
    p_dl.add_argument('dest', nargs='?', default=None, help='Destination path')

    # export (Google Docs/Sheets/Slides)
    p_exp = subparsers.add_parser('export', help='Export Google Doc/Sheet/Slides to file or stdout')
    p_exp.add_argument('file_id', help='Drive file ID')
    p_exp.add_argument('dest', nargs='?', default=None, help='Destination path (optional)')
    p_exp.add_argument('--format', dest='fmt', default=None,
                       help='Export format: text|docx|pdf (Doc), csv|xlsx|pdf (Sheet), pdf|pptx (Slides). Default: text for Docs, csv for Sheets, pdf for Slides')
    p_exp.add_argument('--print', dest='print_stdout', action='store_true',
                       help='Print content to stdout instead of saving to file')

    # folders — list Drive folders
    p_folders = subparsers.add_parser('folders', help='List folders in Drive (root or inside a folder)')
    p_folders.add_argument('parent', nargs='?', default=None, help='Parent folder name (default: root)')

    # upload — upload file to Drive
    p_up = subparsers.add_parser('upload', help='Upload file to Drive (auto-converts .md/.txt/.docx → Google Doc, .csv/.xlsx → Google Sheet)')
    p_up.add_argument('file', help='Local file path to upload')
    p_up.add_argument('--folder', default=None,
                      help='Destination folder name on Drive (omit for interactive selection)')
    p_up.add_argument('--no-convert', action='store_true',
                      help='Disable auto-conversion to Google Doc/Sheet')

    # sync-meetings — retired compatibility stub
    p_sync = subparsers.add_parser(
        'sync-meetings',
        help='Retired: meeting backfill moved out of Drive',
    )
    p_sync.add_argument('--dry-run', action='store_true', help=argparse.SUPPRESS)
    p_sync.add_argument('--folder', default='MeetGeek Files', help=argparse.SUPPRESS)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == 'list':
        list_files(folder_name=args.folder, max_results=args.max)
    elif args.command == 'search':
        search_files(args.query, mime_filter=args.mime_filter, max_results=args.max)
    elif args.command == 'download':
        download_file(args.file_id, dest_path=args.dest)
    elif args.command == 'export':
        export_file(args.file_id, dest_path=args.dest, fmt=args.fmt, print_stdout=args.print_stdout)
    elif args.command == 'folders':
        list_folders_cmd(parent_name=args.parent)
    elif args.command == 'upload':
        upload_file(args.file, folder_name=args.folder, no_convert=args.no_convert)
    elif args.command == 'sync-meetings':
        sync_meetings(dry_run=args.dry_run, folder_name=args.folder)


if __name__ == '__main__':
    main()
