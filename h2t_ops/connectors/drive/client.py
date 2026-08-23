"""DriveClient — Google Drive adapter (re-wrapped, typed errors).

API logic mirrors plugins/h2t-ops/skills/drive/scripts/drive_cli.py for the
six pure-API verbs. The composite sync-meetings workflow is explicitly out of
scope for #133 and remains legacy debt tracked in #147.
"""
from __future__ import annotations

import io
import mimetypes
import re
import socket
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Dict, List, Optional

from h2t_ops.core.errors import (
    AuthError,
    ConfigError,
    H2TError,
    NetworkError,
    NotFoundError,
    ProviderError,
    UsageError,
)
from h2t_ops.core.google_auth import (
    build_google_service,
    resolve_google_credentials,
)

DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive"]
FOLDER_MIME = "application/vnd.google-apps.folder"

GOOGLE_EXPORT_FORMATS = {
    "application/vnd.google-apps.document": {
        "text": ("text/plain", ".txt"),
        "md": ("text/html", ".md"),
        "docx": (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".docx",
        ),
        "pdf": ("application/pdf", ".pdf"),
        "default": "text",
    },
    "application/vnd.google-apps.spreadsheet": {
        "csv": ("text/csv", ".csv"),
        "xlsx": (
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ".xlsx",
        ),
        "pdf": ("application/pdf", ".pdf"),
        "default": "csv",
    },
    "application/vnd.google-apps.presentation": {
        "pdf": ("application/pdf", ".pdf"),
        "pptx": (
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            ".pptx",
        ),
        "default": "pdf",
    },
}

EXPORT_FORMAT_ALIASES = {
    "txt": "text",
    "markdown": "md",
}


def normalize_export_format(fmt: str | None) -> str | None:
    if fmt is None:
        return None
    return EXPORT_FORMAT_ALIASES.get(fmt, fmt)


class _MarkdownHTMLParser(HTMLParser):
    """Small stdlib fallback for Google Docs HTML export."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []
        self._href_stack: list[str | None] = []

    def _ensure_newline(self) -> None:
        if self._parts and not self._parts[-1].endswith("\n"):
            self._parts.append("\n")

    def _ensure_blank_line(self) -> None:
        self._ensure_newline()
        if len(self._parts) < 2 or not self._parts[-2].endswith("\n"):
            self._parts.append("\n")

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self._ensure_blank_line()
            level = int(tag[1])
            self._parts.append(f"{'#' * level} ")
        elif tag in {"p", "div", "section", "article"}:
            self._ensure_blank_line()
        elif tag == "br":
            self._ensure_newline()
        elif tag == "li":
            self._ensure_newline()
            self._parts.append("- ")
        elif tag == "a":
            href = dict(attrs).get("href")
            self._href_stack.append(href)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6", "p", "div", "li"}:
            self._ensure_newline()
        elif tag == "a":
            href = self._href_stack.pop() if self._href_stack else None
            if href:
                self._parts.append(f" ({href})")

    def handle_data(self, data: str) -> None:
        if data:
            self._parts.append(data)

    def markdown(self) -> str:
        text = "".join(self._parts)
        text = re.sub(r"[ \t]+\n", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip() + "\n"


def html_to_markdown(html: str) -> str:
    parser = _MarkdownHTMLParser()
    parser.feed(html)
    parser.close()
    return parser.markdown()


def convert_html_to_markdown(html: str) -> str:
    try:
        import html2text
    except ImportError:
        return html_to_markdown(html)
    h = html2text.HTML2Text()
    h.ignore_links = False
    h.body_width = 0
    return h.handle(html)

UPLOAD_CONVERT_MAP = {
    ".md": ("text/markdown", "application/vnd.google-apps.document"),
    ".txt": ("text/plain", "application/vnd.google-apps.document"),
    ".html": ("text/html", "application/vnd.google-apps.document"),
    ".docx": (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.google-apps.document",
    ),
    ".csv": ("text/csv", "application/vnd.google-apps.spreadsheet"),
    ".tsv": ("text/tab-separated-values", "application/vnd.google-apps.spreadsheet"),
    ".xlsx": (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.google-apps.spreadsheet",
    ),
}

EXTRA_MIME_TYPES = {
    ".css": "text/css",
    ".js": "text/javascript",
    ".mjs": "text/javascript",
    ".svg": "image/svg+xml",
    ".webp": "image/webp",
    ".mkv": "video/x-matroska",
}

PRINT_ALLOWED_FORMATS = frozenset({"text", "csv", "md"})


def _media_io_base_download():
    try:
        from googleapiclient.http import MediaIoBaseDownload
    except ImportError as e:
        raise ConfigError(
            "Google API libraries not installed.",
            hint="pip install google-api-python-client google-auth google-auth-oauthlib",
        ) from e
    return MediaIoBaseDownload


def _media_file_upload():
    try:
        from googleapiclient.http import MediaFileUpload
    except ImportError as e:
        raise ConfigError(
            "Google API libraries not installed.",
            hint="pip install google-api-python-client google-auth google-auth-oauthlib",
        ) from e
    return MediaFileUpload


def _map_http_error(e: Exception, *, op: str):
    """Map provider/network errors to typed h2t_ops errors."""
    if isinstance(e, H2TError):
        return e
    text = str(e)
    lowered = text.lower()
    if "service_disabled" in lowered:
        # Any Google API not enabled in the OAuth client's GCP project. This is a
        # setup/config problem, NOT auth — surface it as ConfigError (it would
        # otherwise fall through to the 403 → AuthError branch and mislead).
        m = re.search(r"([a-z0-9-]+\.googleapis\.com)", text)
        service = m.group(1) if m else "the required Google API"
        return ConfigError(
            f"Google API {service} is disabled for the current Google Cloud project.",
            hint=(f"Enable {service} for the active project in the Google Cloud "
                  "console, then retry (allow ~1-2 min to propagate)."),
        )
    status = getattr(getattr(e, "resp", None), "status", None)
    status = status or getattr(e, "status_code", 0)
    try:
        status = int(status)
    except (TypeError, ValueError):
        status = 0
    if status in (401, 403):
        return AuthError(f"Drive auth/permission denied (HTTP {status}) during {op}: {e}")
    if status == 404:
        return NotFoundError(f"Drive resource not found (HTTP {status}) during {op}: {e}")
    if status >= 500:
        return ProviderError(f"Drive server error (HTTP {status}) during {op}: {e}")
    if isinstance(e, (TimeoutError, socket.timeout)):
        return NetworkError(f"Drive network error during {op}: {e}")
    if "timeout" in lowered or "timed out" in lowered or "connection" in lowered or "network" in lowered:
        return NetworkError(f"Drive network error during {op}: {e}")
    return ProviderError(f"Failed to {op}: {e}")


def _escape_query_value(value: str) -> str:
    return value.replace("'", "\\'")


def _guess_mime(path: Path) -> str:
    return EXTRA_MIME_TYPES.get(
        path.suffix.lower(),
        mimetypes.guess_type(str(path))[0] or "application/octet-stream",
    )


def _row(file: dict[str, Any]) -> dict[str, Any]:
    row = {
        "id": file.get("id", ""),
        "name": file.get("name", ""),
        "mimeType": file.get("mimeType", ""),
        "modifiedTime": file.get("modifiedTime", ""),
    }
    if "size" in file:
        row["size"] = file["size"]
    if "parents" in file:
        row["parents"] = file["parents"]
    return row


_HEADING_NAMED_STYLE = {1: "HEADING_1", 2: "HEADING_2", 3: "HEADING_3"}

_INLINE_BOLD_RE = re.compile(r'\*\*(.+?)\*\*')
_INLINE_ITALIC_RE = re.compile(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)')


def _strip_inline(text: str) -> str:
    """Strip bold/italic markers, returning plain text for insertion."""
    text = _INLINE_BOLD_RE.sub(r'\1', text)
    text = _INLINE_ITALIC_RE.sub(r'\1', text)
    return text


def _inline_style_requests(
    plain_text: str,
    raw_text: str,
    base_index: int,
    tab_id: str,
) -> list[dict[str, Any]]:
    """Build updateTextStyle requests for bold/italic spans in raw_text.

    *plain_text* is the text after marker stripping (what was inserted).
    *raw_text* is the original markdown line text (before stripping).
    *base_index* is the document index at which plain_text starts.
    """
    requests: list[dict[str, Any]] = []
    plain_offset = 0
    raw_offset = 0
    while raw_offset < len(raw_text):
        # Try bold first (longer marker takes precedence)
        m_bold = _INLINE_BOLD_RE.match(raw_text, raw_offset)
        if m_bold:
            inner = m_bold.group(1)
            inner_plain = _INLINE_ITALIC_RE.sub(r'\1', inner)  # strip nested italic
            start = base_index + plain_offset
            end = start + len(inner_plain)
            requests.append({
                "updateTextStyle": {
                    "range": {"startIndex": start, "endIndex": end, "tabId": tab_id},
                    "textStyle": {"bold": True},
                    "fields": "bold",
                }
            })
            plain_offset += len(inner_plain)
            raw_offset = m_bold.end()
            continue
        # Try italic (single *)
        m_ital = _INLINE_ITALIC_RE.match(raw_text, raw_offset)
        if m_ital:
            inner = m_ital.group(1)
            start = base_index + plain_offset
            end = start + len(inner)
            requests.append({
                "updateTextStyle": {
                    "range": {"startIndex": start, "endIndex": end, "tabId": tab_id},
                    "textStyle": {"italic": True},
                    "fields": "italic",
                }
            })
            plain_offset += len(inner)
            raw_offset = m_ital.end()
            continue
        # Plain character
        plain_offset += 1
        raw_offset += 1
    return requests


def _utf16_len(text: str) -> int:
    """Return the number of UTF-16 code units in *text* (without BOM).

    Google Docs API indices are measured in UTF-16 code units, not Python
    code-points. Supplementary-plane characters (emoji, etc.) consume 2 units.
    """
    return len(text.encode("utf-16-le")) // 2


def _find_tab_end_index(doc: dict[str, Any], tab_id: str) -> int | None:
    """Return the endIndex of *tab_id*'s body, or None if the tab is not found."""
    for tab in doc.get("tabs", []):
        if tab.get("tabProperties", {}).get("tabId") == tab_id:
            content = tab.get("documentTab", {}).get("body", {}).get("content", [])
            if content:
                return content[-1].get("endIndex")
    return None


def _md_to_docs_requests(markdown_text: str, tab_id: str) -> list[dict[str, Any]]:
    """Convert markdown to Docs API batchUpdate requests targeting *tab_id*.

    v1 scope: H1–H3 headings, paragraphs, unordered bullets (- or *).
    Inline bold (**text**) and italic (*text*) emit updateTextStyle ranges.

    All text is inserted at index 1 (start of an empty tab body) in one
    insertText request, followed by style/bullet requests with pre-computed
    stable indices.
    """
    paragraphs: list[dict[str, Any]] = []
    for line in markdown_text.splitlines():
        m = re.match(r'^(#{1,3})\s+(.*)', line)
        if m:
            raw = m.group(2)
            paragraphs.append({"type": f"heading{len(m.group(1))}", "text": _strip_inline(raw), "raw": raw})
            continue
        m = re.match(r'^[-*]\s+(.*)', line)
        if m:
            raw = m.group(1)
            paragraphs.append({"type": "bullet", "text": _strip_inline(raw), "raw": raw})
            continue
        paragraphs.append({"type": "paragraph", "text": _strip_inline(line), "raw": line})

    if not paragraphs:
        return []

    full_text = "".join(p["text"] + "\n" for p in paragraphs)
    requests: list[dict[str, Any]] = [{
        "insertText": {
            "location": {"index": 1, "tabId": tab_id},
            "text": full_text,
        }
    }]

    current = 1
    for p in paragraphs:
        plain = p["text"]
        raw = p.get("raw", plain)
        para_len = _utf16_len(plain) + 1  # +1 for \n (always BMP → 1 unit)
        start, end = current, current + para_len
        current = end

        ptype = p["type"]
        if ptype.startswith("heading"):
            level = int(ptype[-1])
            requests.append({
                "updateParagraphStyle": {
                    "range": {"startIndex": start, "endIndex": end, "tabId": tab_id},
                    "paragraphStyle": {"namedStyleType": _HEADING_NAMED_STYLE[level]},
                    "fields": "namedStyleType",
                }
            })
        elif ptype == "bullet":
            requests.append({
                "createParagraphBullets": {
                    "range": {"startIndex": start, "endIndex": end, "tabId": tab_id},
                    "bulletPreset": "BULLET_DISC_CIRCLE_SQUARE",
                }
            })

        # Inline styles (bold/italic)
        inline_reqs = _inline_style_requests(plain, raw, start, tab_id)
        requests.extend(inline_reqs)

    return requests


class DriveClient:
    """Google Drive API client — parity scope #133."""

    def __init__(self) -> None:
        creds = resolve_google_credentials("drive", DRIVE_SCOPES)
        self._creds = creds
        self.service = build_google_service("drive", "v3", creds)
        self._docs_service = None
        self._sheets_service = None

    def _docs(self):
        if self._docs_service is None:
            self._docs_service = build_google_service("docs", "v1", self._creds)
        return self._docs_service

    def _sheets(self):
        if self._sheets_service is None:
            self._sheets_service = build_google_service("sheets", "v4", self._creds)
        return self._sheets_service

    def sheets_read(self, sheet_id: str, *, cell_range: str) -> dict[str, Any]:
        """Read a cell range from a Google Sheet (values only)."""
        try:
            resp = self._sheets().spreadsheets().values().get(
                spreadsheetId=sheet_id, range=cell_range,
            ).execute()
        except Exception as e:
            raise _map_http_error(e, op=f"read sheet {sheet_id} range {cell_range}") from e
        return {
            "sheet_id": sheet_id,
            "range": resp.get("range", cell_range),
            "values": resp.get("values", []),
        }

    def sheets_update(
        self,
        sheet_id: str,
        *,
        cell_range: str,
        value: str | None = None,
        values_file: str | None = None,
    ) -> dict[str, Any]:
        """Write values into a range in place via Sheets ``values.update``.

        Values-only update (``valueInputOption=RAW``) — cell/column formatting,
        merges, and frozen rows are preserved (unlike a full-file re-upload).
        """
        import json
        if (value is None) == (not values_file):
            raise UsageError("sheets update: specify exactly one of --value or --values-file")
        if values_file:
            try:
                raw = Path(values_file).read_text(encoding="utf-8")
            except FileNotFoundError as e:
                raise UsageError(f"file not found: {values_file}") from e
            try:
                values = json.loads(raw)
            except json.JSONDecodeError as e:
                raise UsageError(f"values-file is not valid JSON: {e}") from e
            if not isinstance(values, list) or not all(isinstance(row, list) for row in values):
                raise UsageError('values-file must be a JSON 2D array, e.g. [["a","b"],["c","d"]]')
        else:
            values = [[value]]
        try:
            resp = self._sheets().spreadsheets().values().update(
                spreadsheetId=sheet_id,
                range=cell_range,
                valueInputOption="RAW",
                body={"values": values},
            ).execute()
        except Exception as e:
            raise _map_http_error(e, op=f"update sheet {sheet_id} range {cell_range}") from e
        return {
            "sheet_id": sheet_id,
            "updated_range": resp.get("updatedRange"),
            "updated_cells": resp.get("updatedCells"),
            "updated_rows": resp.get("updatedRows"),
            "updated_columns": resp.get("updatedColumns"),
        }

    def _list_paginated(
        self,
        *,
        q: str,
        fields: str,
        page_size: int,
        order_by: str | None = None,
        max_results: int | None = None,
        drive_id: str | None = None,
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        page_token = None
        while True:
            kwargs = {
                "q": q,
                "fields": fields,
                "pageSize": page_size,
                "pageToken": page_token,
                "supportsAllDrives": True,
                "includeItemsFromAllDrives": True,
            }
            if drive_id:
                kwargs["corpora"] = "drive"
                kwargs["driveId"] = drive_id
            if order_by:
                kwargs["orderBy"] = order_by
            resp = self.service.files().list(**kwargs).execute()
            rows.extend(resp.get("files", []))
            page_token = resp.get("nextPageToken")
            if not page_token or (max_results and len(rows) >= max_results):
                break
        if max_results:
            rows = rows[:max_results]
        return [_row(f) for f in rows]

    def _resolve_folder_id(self, folder_name: str) -> tuple[str | None, str, bool]:
        """Resolve folder name or ID to (folder_id, display_name, is_shared_drive).

        is_shared_drive=True means the ID is a Shared Drive root — listing requires
        corpora='drive' instead of a parent query.
        """
        if not folder_name or folder_name == "root":
            return None, "root", False
        # Drive IDs: regular folders ~33 chars, shared drive roots ~19 chars — no spaces
        if re.fullmatch(r"[A-Za-z0-9_\-]{15,}", folder_name):
            try:
                meta = self.service.files().get(
                    fileId=folder_name,
                    fields="id,name,mimeType",
                    supportsAllDrives=True,
                ).execute()
                if meta.get("mimeType") != FOLDER_MIME:
                    raise UsageError(f"target is not a Drive folder: {folder_name}")
                return meta["id"], meta.get("name", folder_name), False
            except Exception as e:
                mapped = _map_http_error(e, op=f"resolve folder id {folder_name}")
                if not isinstance(mapped, NotFoundError):
                    raise mapped from e
            # files().get() fails for Shared Drive roots — try drives().get()
            try:
                drive_meta = self.service.drives().get(
                    driveId=folder_name,
                    fields="id,name",
                ).execute()
                return drive_meta["id"], drive_meta.get("name", folder_name), True
            except Exception as e:
                mapped = _map_http_error(e, op=f"resolve shared drive id {folder_name}")
                if not isinstance(mapped, NotFoundError):
                    raise mapped from e
        safe = _escape_query_value(folder_name)
        resp = self.service.files().list(
            q=(
                f"name='{safe}' and "
                "mimeType='application/vnd.google-apps.folder' and trashed=false"
            ),
            fields="files(id, name)",
            pageSize=5,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        ).execute()
        folders = resp.get("files", [])
        if not folders:
            raise NotFoundError(f"folder not found: {folder_name}")
        if len(folders) > 1:
            raise UsageError(f"ambiguous folder: {folder_name}")
        return folders[0]["id"], folders[0].get("name", folder_name), False

    def _find_child_by_name(
        self,
        parent_id: str,
        name: str,
        *,
        folder: bool | None = None,
    ) -> dict[str, Any] | None:
        """Find a single direct child by name under a parent id.

        If duplicates exist for the requested kind, stop instead of guessing.
        """
        safe = _escape_query_value(name)
        q = f"name='{safe}' and '{parent_id}' in parents and trashed=false"
        resp = self.service.files().list(
            q=q,
            fields="files(id, name, mimeType, size, webViewLink)",
            pageSize=10,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        ).execute()
        rows = resp.get("files", [])
        if folder is True:
            rows = [r for r in rows if r.get("mimeType") == FOLDER_MIME]
        elif folder is False:
            rows = [r for r in rows if r.get("mimeType") != FOLDER_MIME]
        if not rows:
            return None
        if len(rows) > 1:
            kind = "folder" if folder else "file" if folder is False else "child"
            raise UsageError(f"ambiguous Drive {kind} under {parent_id}: {name}")
        return rows[0]

    @staticmethod
    def _is_virtual_parent(parent_id: str) -> bool:
        return parent_id.startswith("dry-run:")

    @staticmethod
    def _summary(entries: list[dict[str, Any]]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for entry in entries:
            action = str(entry.get("action", "unknown"))
            counts[action] = counts.get(action, 0) + 1
        counts["total"] = len(entries)
        return counts

    def _ensure_child_folder(
        self,
        parent_id: str,
        name: str,
        *,
        relative_path: str,
        dry_run: bool,
        entries: list[dict[str, Any]],
    ) -> str:
        if self._is_virtual_parent(parent_id):
            virtual_id = f"dry-run:{relative_path}"
            entries.append({
                "kind": "folder",
                "action": "folder_create",
                "relative_path": relative_path,
                "name": name,
                "parent_id": parent_id,
                "file_id": virtual_id,
                "mimeType": FOLDER_MIME,
                "dry_run": True,
            })
            return virtual_id

        existing = self._find_child_by_name(parent_id, name, folder=True)
        if existing:
            entries.append({
                "kind": "folder",
                "action": "folder_exists",
                "relative_path": relative_path,
                "name": name,
                "parent_id": parent_id,
                "file_id": existing.get("id", ""),
                "mimeType": existing.get("mimeType", FOLDER_MIME),
                "dry_run": dry_run,
            })
            return existing["id"]

        if dry_run:
            virtual_id = f"dry-run:{relative_path}"
            entries.append({
                "kind": "folder",
                "action": "folder_create",
                "relative_path": relative_path,
                "name": name,
                "parent_id": parent_id,
                "file_id": virtual_id,
                "mimeType": FOLDER_MIME,
                "dry_run": True,
            })
            return virtual_id

        res = self.service.files().create(
            body={"name": name, "mimeType": FOLDER_MIME, "parents": [parent_id]},
            fields="id, name, mimeType, webViewLink",
        ).execute()
        entries.append({
            "kind": "folder",
            "action": "folder_created",
            "relative_path": relative_path,
            "name": res.get("name", name),
            "parent_id": parent_id,
            "file_id": res.get("id", ""),
            "mimeType": res.get("mimeType", FOLDER_MIME),
            "web_view_link": res.get("webViewLink", ""),
            "dry_run": False,
        })
        return res["id"]

    def _upload_native_child_file(
        self,
        src: Path,
        parent_id: str,
        *,
        relative_path: str,
        dry_run: bool,
        update_existing: bool,
        entries: list[dict[str, Any]],
    ) -> None:
        source_mime = _guess_mime(src)
        size = src.stat().st_size
        existing = None
        if not self._is_virtual_parent(parent_id):
            existing = self._find_child_by_name(parent_id, src.name, folder=False)

        base = {
            "kind": "file",
            "relative_path": relative_path,
            "local_path": str(src),
            "name": src.name,
            "parent_id": parent_id,
            "mimeType": source_mime,
            "size": size,
            "dry_run": dry_run,
        }

        if existing and not update_existing:
            entries.append({
                **base,
                "action": "file_skipped",
                "file_id": existing.get("id", ""),
                "existing_mimeType": existing.get("mimeType", ""),
                "web_view_link": existing.get("webViewLink", ""),
            })
            return

        if dry_run:
            entries.append({
                **base,
                "action": "file_update" if existing and update_existing else "file_upload",
                "file_id": existing.get("id", "") if existing else "",
            })
            return

        media = _media_file_upload()(str(src), mimetype=source_mime, resumable=True)
        if existing and update_existing:
            res = self.service.files().update(
                fileId=existing["id"],
                media_body=media,
                fields="id, name, mimeType, webViewLink",
                supportsAllDrives=True,
            ).execute()
            action = "file_updated"
        else:
            res = self.service.files().create(
                body={"name": src.name, "parents": [parent_id]},
                media_body=media,
                fields="id, name, mimeType, webViewLink",
                supportsAllDrives=True,
            ).execute()
            action = "file_uploaded"
        entries.append({
            **base,
            "action": action,
            "file_id": res.get("id", ""),
            "mimeType": res.get("mimeType", source_mime),
            "web_view_link": res.get("webViewLink", ""),
        })

    def list_files(
        self,
        folder: str | None = None,
        max_results: int | None = None,
    ) -> list[dict[str, Any]]:
        try:
            drive_id = None
            if folder:
                folder_id, _, is_shared_drive = self._resolve_folder_id(folder)
                if is_shared_drive:
                    q = "trashed=false"
                    drive_id = folder_id
                else:
                    q = f"'{folder_id}' in parents and trashed=false"
            else:
                q = "'root' in parents and trashed=false"
            return self._list_paginated(
                q=q,
                fields="nextPageToken, files(id, name, mimeType, modifiedTime, size)",
                page_size=1000,
                order_by="modifiedTime desc",
                max_results=max_results,
                drive_id=drive_id,
            )
        except Exception as e:
            raise _map_http_error(e, op="list files") from e

    def search_files(
        self,
        query: str,
        mime_filter: str | None = None,
        max_results: int | None = None,
    ) -> list[dict[str, Any]]:
        safe = _escape_query_value(query)
        q = f"fullText contains '{safe}' and trashed=false"
        if mime_filter == "docx":
            q += (
                " and mimeType="
                "'application/vnd.openxmlformats-officedocument.wordprocessingml.document'"
            )
        elif mime_filter == "folder":
            q += " and mimeType='application/vnd.google-apps.folder'"
        try:
            return self._list_paginated(
                q=q,
                fields="nextPageToken, files(id, name, mimeType, modifiedTime, parents)",
                page_size=1000,
                order_by="modifiedTime desc",
                max_results=max_results,
            )
        except Exception as e:
            raise _map_http_error(e, op=f"search files {query!r}") from e

    def list_folders(
        self,
        parent: str | None = None,
        max_results: int = 50,
    ) -> list[dict[str, Any]]:
        try:
            drive_id = None
            if parent:
                parent_id, _, is_shared_drive = self._resolve_folder_id(parent)
                if is_shared_drive:
                    q = "mimeType='application/vnd.google-apps.folder' and trashed=false"
                    drive_id = parent_id
                else:
                    q = (
                        f"'{parent_id}' in parents and "
                        "mimeType='application/vnd.google-apps.folder' and trashed=false"
                    )
            else:
                q = (
                    "'root' in parents and "
                    "mimeType='application/vnd.google-apps.folder' and trashed=false"
                )
            return self._list_paginated(
                q=q,
                fields="files(id, name, mimeType, modifiedTime)",
                page_size=max_results,
                order_by="name",
                max_results=max_results,
                drive_id=drive_id,
            )
        except Exception as e:
            raise _map_http_error(e, op="list folders") from e

    def create_folder(
        self,
        name: str,
        *,
        parent: str | None = None,
    ) -> dict[str, Any]:
        if not name or not name.strip():
            raise UsageError("drive create-folder: name is required")
        try:
            parent_id = None
            parent_name = "root"
            if parent:
                parent_id, parent_name, _ = self._resolve_folder_id(parent)
            body: dict[str, Any] = {"name": name.strip(), "mimeType": FOLDER_MIME}
            if parent_id:
                body["parents"] = [parent_id]
            res = self.service.files().create(
                body=body,
                fields="id, name, mimeType, parents, webViewLink",
                supportsAllDrives=True,
            ).execute()
            return {
                "file_id": res.get("id", ""),
                "name": res.get("name", name.strip()),
                "mimeType": res.get("mimeType", FOLDER_MIME),
                "parents": res.get("parents", []),
                "web_view_link": res.get("webViewLink", ""),
                "parent_name": parent_name,
            }
        except Exception as e:
            raise _map_http_error(e, op=f"create folder {name.strip()!r}") from e

    def rename_file(self, file_id: str, new_name: str) -> dict[str, Any]:
        if not new_name or not new_name.strip():
            raise UsageError("drive rename: new name is required")
        clean_name = new_name.strip()
        try:
            res = self.service.files().update(
                fileId=file_id,
                body={"name": clean_name},
                fields="id, name, mimeType, webViewLink, modifiedTime",
                supportsAllDrives=True,
            ).execute()
            return {
                "file_id": res.get("id", file_id),
                "name": res.get("name", clean_name),
                "mimeType": res.get("mimeType", ""),
                "web_view_link": res.get("webViewLink", ""),
                "modifiedTime": res.get("modifiedTime", ""),
            }
        except Exception as e:
            raise _map_http_error(e, op=f"rename file {file_id}") from e

    def copy_file(
        self,
        file_id: str,
        *,
        new_name: str | None = None,
        folder: str | None = None,
    ) -> dict[str, Any]:
        try:
            body: dict[str, Any] = {}
            if new_name and new_name.strip():
                body["name"] = new_name.strip()
            if folder:
                folder_id, _, _ = self._resolve_folder_id(folder)
                if folder_id:
                    body["parents"] = [folder_id]
                else:
                    body["parents"] = ["root"]
            res = self.service.files().copy(
                fileId=file_id,
                body=body,
                fields="id, name, mimeType, parents, webViewLink",
                supportsAllDrives=True,
            ).execute()
            return {
                "file_id": res.get("id", ""),
                "source_file_id": file_id,
                "name": res.get("name", ""),
                "mimeType": res.get("mimeType", ""),
                "parents": res.get("parents", []),
                "web_view_link": res.get("webViewLink", ""),
            }
        except Exception as e:
            raise _map_http_error(e, op=f"copy file {file_id}") from e

    def move_file(self, file_id: str, *, destination_folder_id: str) -> dict[str, Any]:
        destination = destination_folder_id.strip() if destination_folder_id else ""
        if not destination:
            raise UsageError("drive move: destination folder is required")
        try:
            folder_id, _, is_shared_drive = self._resolve_folder_id(destination)
            add_parents = "root" if not folder_id else folder_id
            if folder_id and not is_shared_drive:
                folder_meta = self.service.files().get(
                    fileId=folder_id,
                    fields="id, name, mimeType",
                    supportsAllDrives=True,
                ).execute()
                if folder_meta.get("mimeType") != FOLDER_MIME:
                    raise UsageError(
                        f"destination {folder_meta.get('name', folder_id)!r} is not a Drive folder"
                    )

            file_meta = self.service.files().get(
                fileId=file_id,
                fields="id, name, mimeType, parents",
                supportsAllDrives=True,
            ).execute()
            remove_parents = ",".join(file_meta.get("parents", []) or [])

            res = self.service.files().update(
                fileId=file_id,
                addParents=add_parents,
                removeParents=remove_parents,
                fields="id, name, mimeType, parents, webViewLink",
                supportsAllDrives=True,
            ).execute()
            return {
                "file_id": res.get("id", file_id),
                "name": res.get("name", file_meta.get("name", "")),
                "mimeType": res.get("mimeType", file_meta.get("mimeType", "")),
                "parents": res.get("parents", []),
                "web_view_link": res.get("webViewLink", ""),
            }
        except Exception as e:
            raise _map_http_error(e, op=f"move file {file_id}") from e

    def list_document_tabs(self, document_id: str) -> dict[str, Any]:
        try:
            meta = self.service.files().get(
                fileId=document_id,
                fields="id, name, mimeType, webViewLink",
                supportsAllDrives=True,
            ).execute()
            mime = meta.get("mimeType", "")
            if mime != "application/vnd.google-apps.document":
                raise UsageError(
                    f"file {meta.get('name', document_id)!r} is not a Google Docs editor file"
                )
            doc = self._docs().documents().get(
                documentId=document_id, includeTabsContent=True,
            ).execute()
        except Exception as e:
            raise _map_http_error(e, op=f"list document tabs for {document_id}") from e

        def _flatten(tabs: list[dict[str, Any]]) -> list[dict[str, Any]]:
            rows: list[dict[str, Any]] = []
            for tab in tabs or []:
                props = tab.get("tabProperties", {}) or {}
                children = tab.get("childTabs", []) or []
                rows.append({
                    "tab_id": props.get("tabId", ""),
                    "title": props.get("title", ""),
                    "parent_tab_id": props.get("parentTabId", ""),
                    "index": props.get("index"),
                    "nesting_level": props.get("nestingLevel"),
                    "icon_emoji": props.get("iconEmoji", ""),
                    "has_children": bool(children),
                })
                rows.extend(_flatten(children))
            return rows

        tabs = _flatten(doc.get("tabs", []) or [])
        return {
            "kind": "google_docs_tabs/v1",
            "document_id": document_id,
            "title": doc.get("title") or meta.get("name", ""),
            "mimeType": meta.get("mimeType", ""),
            "web_view_link": meta.get("webViewLink", ""),
            "tabs": tabs,
            "count": len(tabs),
        }

    def add_document_tab(self, document_id: str, title: str) -> dict[str, Any]:
        try:
            meta = self.service.files().get(
                fileId=document_id,
                fields="id, name, mimeType",
                supportsAllDrives=True,
            ).execute()
            if meta.get("mimeType") != "application/vnd.google-apps.document":
                raise UsageError(
                    f"file {meta.get('name', document_id)!r} is not a Google Docs editor file"
                )
            response = self._docs().documents().batchUpdate(
                documentId=document_id,
                body={"requests": [{"addDocumentTab": {"tabProperties": {"title": title}}}]},
            ).execute()
        except Exception as e:
            raise _map_http_error(e, op=f"add tab to document {document_id}") from e
        props = (
            response.get("replies", [{}])[0]
            .get("addDocumentTab", {})
            .get("tabProperties", {})
        )
        return {
            "kind": "google_docs_tab/v1",
            "document_id": document_id,
            "tab_id": props.get("tabId", ""),
            "title": props.get("title", title),
            "index": props.get("index"),
            "nesting_level": props.get("nestingLevel"),
        }

    def write_document_tab(
        self,
        document_id: str,
        tab_id: str,
        markdown_text: str,
        *,
        clear_first: bool = False,
    ) -> dict[str, Any]:
        """Write markdown content to an existing Google Docs tab via batchUpdate.

        v1 scope: H1–H3 headings, paragraphs, unordered bullet lists.
        Inline bold (**text**) and italic (*text*) emit updateTextStyle ranges.
        When *clear_first* is True, existing tab content is deleted before writing.
        """
        try:
            meta = self.service.files().get(
                fileId=document_id,
                fields="id, name, mimeType",
                supportsAllDrives=True,
            ).execute()
            if meta.get("mimeType") != "application/vnd.google-apps.document":
                raise UsageError(
                    f"file {meta.get('name', document_id)!r} is not a Google Docs editor file"
                )

            all_reqs: list[dict[str, Any]] = []

            doc = self._docs().documents().get(
                documentId=document_id, includeTabsContent=True,
            ).execute()
            revision_id = doc.get("revisionId", "")

            if clear_first:
                # Fetch existing content to find the end index of the tab body
                tab_body = self._find_tab_body(doc, tab_id)
                if tab_body:
                    content = tab_body.get("content", [])
                    if content:
                        end_index = content[-1].get("endIndex", 1)
                        # A fresh tab holds one empty paragraph (endIndex=2): the delete
                        # range (1, end-1) would be empty and the Docs API rejects it, so
                        # skip the delete and just insert. Only clear real content (end>2).
                        if end_index > 2:
                            all_reqs.append({
                                "deleteContentRange": {
                                    "range": {
                                        "startIndex": 1,
                                        "endIndex": end_index - 1,
                                        "tabId": tab_id,
                                    }
                                }
                            })
            else:
                tab_end = _find_tab_end_index(doc, tab_id)
                if tab_end is None:
                    raise UsageError(
                        f"tab {tab_id!r} not found in document {document_id!r}"
                    )
                # Google creates a new tab with one empty paragraph (endIndex=2),
                # so treat endIndex <= 2 as a fresh/empty tab.
                if tab_end > 2:
                    raise UsageError(
                        f"tab {tab_id!r} in document {document_id!r} is not empty "
                        f"(endIndex={tab_end}); write_document_tab only writes to fresh tabs "
                        f"(use --clear-first to overwrite existing content)"
                    )

            reqs = _md_to_docs_requests(markdown_text, tab_id)
            all_reqs.extend(reqs)

            if not all_reqs:
                return {
                    "kind": "google_docs_tab_write/v1",
                    "document_id": document_id,
                    "tab_id": tab_id,
                    "requests_sent": 0,
                }
            response = self._docs().documents().batchUpdate(
                documentId=document_id,
                body={
                    "requests": all_reqs,
                    "writeControl": {"requiredRevisionId": revision_id},
                },
            ).execute()
        except Exception as e:
            raise _map_http_error(e, op=f"write tab {tab_id} in document {document_id}") from e
        return {
            "kind": "google_docs_tab_write/v1",
            "document_id": document_id,
            "tab_id": tab_id,
            "requests_sent": len(all_reqs),
            "revision_id": (response.get("writeControl") or {}).get("requiredRevisionId", ""),
        }

    @staticmethod
    def _find_tab_body(doc: dict[str, Any], tab_id: str) -> dict[str, Any] | None:
        """Recursively find a tab's documentTab.body by tab_id."""
        def _search(tabs: list[dict[str, Any]]) -> dict[str, Any] | None:
            for tab in tabs or []:
                props = tab.get("tabProperties", {}) or {}
                if props.get("tabId") == tab_id:
                    return (tab.get("documentTab") or {}).get("body")
                found = _search(tab.get("childTabs", []) or [])
                if found is not None:
                    return found
            return None
        return _search(doc.get("tabs", []) or [])

    def read_tab(self, document_id: str, tab_id: str) -> dict[str, Any]:
        """Read and return the plain text content of a specific Google Docs tab."""
        try:
            meta = self.service.files().get(
                fileId=document_id,
                fields="id, name, mimeType",
                supportsAllDrives=True,
            ).execute()
            if meta.get("mimeType") != "application/vnd.google-apps.document":
                raise UsageError(
                    f"file {meta.get('name', document_id)!r} is not a Google Docs editor file"
                )
            doc = self._docs().documents().get(
                documentId=document_id, includeTabsContent=True,
            ).execute()
        except Exception as e:
            raise _map_http_error(e, op=f"read tab {tab_id} in document {document_id}") from e

        body = self._find_tab_body(doc, tab_id)
        if body is None:
            from h2t_ops.core.errors import NotFoundError
            raise NotFoundError(f"tab {tab_id!r} not found in document {document_id}")

        text_parts: list[str] = []
        for block in body.get("content", []) or []:
            para = block.get("paragraph")
            if not para:
                continue
            for elem in para.get("elements", []) or []:
                run = elem.get("textRun")
                if run:
                    text_parts.append(run.get("content", ""))
        text = "".join(text_parts)

        return {
            "kind": "google_docs_tab_read/v1",
            "document_id": document_id,
            "tab_id": tab_id,
            "text": text,
        }

    def get_file(self, file_id: str) -> dict[str, Any]:
        """Get metadata for a Drive file by id."""
        try:
            return self.service.files().get(
                fileId=file_id,
                fields="id,name,mimeType,parents,webViewLink,modifiedTime,size,trashed",
                supportsAllDrives=True,
            ).execute()
        except Exception as e:
            raise _map_http_error(e, op=f"get file {file_id}") from e

    def _confirm_file_name(self, file_id: str, confirm_name: str) -> dict[str, Any]:
        """Fetch file metadata and verify the name matches confirm_name (case-insensitive)."""
        meta = self.get_file(file_id)
        actual = str(meta.get("name", "")).strip()
        if actual.lower() != confirm_name.strip().lower():
            raise UsageError(
                f'name mismatch — expected "{confirm_name}", got "{actual}"'
            )
        return meta

    def trash_file(self, file_id: str, *, confirm_name: str) -> dict[str, Any]:
        """Move a Drive file to trash after verifying the file name."""
        meta = self._confirm_file_name(file_id, confirm_name)
        try:
            updated = self.service.files().update(
                fileId=file_id,
                body={"trashed": True},
                fields="id,name,trashed",
                supportsAllDrives=True,
            ).execute()
        except Exception as e:
            raise _map_http_error(e, op=f"trash file {file_id}") from e
        return {
            "file_id": updated["id"],
            "name": updated["name"],
            "trashed": updated.get("trashed", True),
            "previous": meta,
        }

    def delete_file(self, file_id: str, *, confirm_name: str) -> dict[str, Any]:
        """Permanently delete a Drive file after verifying the file name."""
        meta = self._confirm_file_name(file_id, confirm_name)
        try:
            self.service.files().delete(fileId=file_id, supportsAllDrives=True).execute()
        except Exception as e:
            raise _map_http_error(e, op=f"delete file {file_id}") from e
        return {"file_id": file_id, "name": meta.get("name"), "deleted": True}

    def create_document(
        self,
        title: str,
        *,
        folder_id: str | None = None,
    ) -> dict[str, Any]:
        """Create a new Google Doc with the given title, optionally inside a folder."""
        body: dict[str, Any] = {
            "name": title,
            "mimeType": "application/vnd.google-apps.document",
        }
        if folder_id:
            body["parents"] = [folder_id]
        try:
            return self.service.files().create(
                body=body,
                fields="id,name,mimeType,webViewLink,parents",
                supportsAllDrives=True,
            ).execute()
        except Exception as e:
            raise _map_http_error(e, op=f"create document {title!r}") from e

    def download_file(self, file_id: str, dest: str | Path | None = None) -> dict[str, Any]:
        try:
            meta = self.service.files().get(
                fileId=file_id, fields="name, mimeType, size",
            ).execute()
            name = meta["name"]
            target = Path(dest) if dest else Path.cwd() / name
            request = self.service.files().get_media(fileId=file_id)
            buf = io.BytesIO()
            downloader = _media_io_base_download()(buf, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(buf.getvalue())
            result: dict[str, Any] = {
                "saved_path": str(target),
                "file_id": file_id,
                "name": name,
                "mimeType": meta.get("mimeType", ""),
            }
            if "size" in meta:
                result["size"] = meta["size"]
            return result
        except Exception as e:
            raise _map_http_error(e, op=f"download file {file_id}") from e

    def export_file(
        self,
        file_id: str,
        fmt: str | None = None,
        dest: str | Path | None = None,
        to_stdout: bool = False,
    ) -> dict[str, Any]:
        chosen_fmt = normalize_export_format(fmt)
        if to_stdout and chosen_fmt in {"docx", "xlsx", "pdf", "pptx"}:
            raise UsageError(f"drive export --print cannot use binary format: {chosen_fmt}")
        try:
            meta = self.service.files().get(
                fileId=file_id, fields="name, mimeType",
            ).execute()
            source_mime = meta["mimeType"]
            name = meta["name"]
            formats = GOOGLE_EXPORT_FORMATS.get(source_mime)
            if not formats:
                raise UsageError(
                    f"file {name!r} is not a Google Docs editor file; use download",
                )
            chosen = chosen_fmt or formats["default"]
            if chosen not in formats or chosen == "default":
                available = ", ".join(k for k in formats if k != "default")
                raise UsageError(
                    f"format {chosen!r} unavailable for {source_mime}; "
                    f"available: {available}",
                )
            export_mime, ext = formats[chosen]
            content = self.service.files().export(
                fileId=file_id, mimeType=export_mime,
            ).execute()
            if chosen == "md":
                html = content.decode("utf-8") if isinstance(content, bytes) else content
                content = convert_html_to_markdown(html).encode("utf-8")

            result: dict[str, Any] = {
                "file_id": file_id,
                "name": name,
                "source_mime": source_mime,
                "export_mime": export_mime,
                "format": chosen,
            }
            if to_stdout:
                # Binary formats are rejected for --print above, so any content
                # reaching here is text and safe to decode.
                result["text"] = (
                    content.decode("utf-8") if isinstance(content, bytes) else content
                )
                return result

            if dest:
                target = Path(dest)
            else:
                safe_name = name.replace("/", "-").replace(":", "-")
                target = Path.cwd() / f"{safe_name}{ext}"
            target.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(content, bytes):
                target.write_bytes(content)
            else:
                target.write_text(content, encoding="utf-8")
            result["saved_path"] = str(target)
            if target.exists():
                result["size"] = target.stat().st_size
            return result
        except Exception as e:
            raise _map_http_error(e, op=f"export file {file_id}") from e

    def upload_file(
        self,
        file_path: str | Path,
        folder: str | None,
        no_convert: bool = False,
        *,
        update_existing: bool = False,
        parent_id: str | None = None,
        title: str | None = None,
    ) -> dict[str, Any]:
        if not folder and not parent_id:
            raise UsageError("drive upload: --folder is required")
        src = Path(file_path)
        if not src.exists():
            raise NotFoundError(f"file not found: {src}")
        try:
            if parent_id:
                folder_id = parent_id
                folder_display = parent_id
            else:
                folder_id, folder_display, _ = self._resolve_folder_id(folder)
            ext = src.suffix.lower()
            convert_info = None if no_convert else UPLOAD_CONVERT_MAP.get(ext)
            if convert_info:
                source_mime, target_mime = convert_info
                dest_name = src.stem
            else:
                source_mime = _guess_mime(src)
                target_mime = None
                dest_name = src.name
            if title:
                dest_name = title

            existing = None
            if update_existing and folder_id and not self._is_virtual_parent(folder_id):
                existing = self._find_child_by_name(folder_id, dest_name, folder=False)

            metadata: dict[str, Any] = {"name": dest_name}
            if folder_id:
                metadata["parents"] = [folder_id]
            if target_mime:
                metadata["mimeType"] = target_mime
            media = _media_file_upload()(str(src), mimetype=source_mime, resumable=True)

            if existing and update_existing:
                res = self.service.files().update(
                    fileId=existing["id"],
                    media_body=media,
                    fields="id, name, mimeType, webViewLink",
                    supportsAllDrives=True,
                ).execute()
                action = "updated"
            else:
                res = self.service.files().create(
                    body=metadata,
                    media_body=media,
                    fields="id, name, mimeType, webViewLink",
                    supportsAllDrives=True,
                ).execute()
                action = "created"
            return {
                "file_id": res.get("id", ""),
                "name": res.get("name", ""),
                "mimeType": res.get("mimeType", ""),
                "web_view_link": res.get("webViewLink", ""),
                "folder_name": folder_display,
                "action": action,
            }
        except Exception as e:
            raise _map_http_error(e, op=f"upload file {src}") from e

    def share_file(
        self,
        file_id: str,
        *,
        email: str | None = None,
        role: str = "reader",
        anyone: bool = False,
        get_link: bool = False,
    ) -> dict[str, Any]:
        try:
            if not email and not anyone and not get_link:
                raise UsageError("share_file: one of email, anyone, or get_link is required")
            if get_link:
                meta = self.service.files().get(
                    fileId=file_id,
                    fields="webViewLink",
                    supportsAllDrives=True,
                ).execute()
                perms_resp = self.service.permissions().list(
                    fileId=file_id,
                    fields="permissions(type,role)",
                    supportsAllDrives=True,
                ).execute()
                permissions = perms_resp.get("permissions", [])
                has_anyone = any(p.get("type") == "anyone" for p in permissions)
                return {
                    "kind": "drive_share/v1",
                    "file_id": file_id,
                    "web_view_link": meta.get("webViewLink", ""),
                    "type": "get-link",
                    "has_anyone_permission": has_anyone,
                }
            perm_type = "user" if email else "anyone"
            perm_body: dict[str, Any] = {"type": perm_type, "role": role}
            if email:
                perm_body["emailAddress"] = email
            perm = self.service.permissions().create(
                fileId=file_id,
                body=perm_body,
                sendNotificationEmail=False,
                supportsAllDrives=True,
                fields="id",
            ).execute()
            # webViewLink fetch is best-effort; permission already granted above
            meta = self.service.files().get(
                fileId=file_id,
                fields="webViewLink",
                supportsAllDrives=True,
            ).execute()
            return {
                "kind": "drive_share/v1",
                "file_id": file_id,
                "web_view_link": meta.get("webViewLink", ""),
                "permission_id": perm.get("id", ""),
                "role": role,
                "type": perm_type,
                "granted_to": email if email else "anyone",
            }
        except Exception as e:
            raise _map_http_error(e, op=f"share file {file_id}") from e

    def upload_folder(
        self,
        local_dir: str | Path,
        *,
        parent_id: str,
        dry_run: bool = False,
        update_existing: bool = False,
    ) -> dict[str, Any]:
        """Recursively upload a local folder to Drive preserving relative paths.

        Folder upload is native by default: `.html`, `.txt`, `.md`, and other files
        are uploaded as files, not converted to Google editor documents. This keeps
        browser-relative paths usable for deploy/share folders.
        """
        root = Path(local_dir)
        if not parent_id:
            raise UsageError("drive upload-folder: --parent-id is required")
        if not root.exists():
            raise NotFoundError(f"folder not found: {root}")
        if not root.is_dir():
            raise UsageError(f"not a directory: {root}")

        try:
            entries: list[dict[str, Any]] = []
            folder_ids: dict[Path, str] = {Path("."): parent_id}

            all_paths = sorted(
                root.rglob("*"),
                key=lambda p: p.relative_to(root).as_posix().lower(),
            )
            for path in [p for p in all_paths if p.is_dir()]:
                rel = path.relative_to(root)
                parent_rel = rel.parent if rel.parent != Path("") else Path(".")
                parent_drive_id = folder_ids[parent_rel]
                folder_ids[rel] = self._ensure_child_folder(
                    parent_drive_id,
                    path.name,
                    relative_path=rel.as_posix(),
                    dry_run=dry_run,
                    entries=entries,
                )

            for path in [p for p in all_paths if p.is_file()]:
                rel = path.relative_to(root)
                parent_rel = rel.parent if rel.parent != Path("") else Path(".")
                parent_drive_id = folder_ids[parent_rel]
                self._upload_native_child_file(
                    path,
                    parent_drive_id,
                    relative_path=rel.as_posix(),
                    dry_run=dry_run,
                    update_existing=update_existing,
                    entries=entries,
                )

            return {
                "local_dir": str(root),
                "parent_id": parent_id,
                "dry_run": dry_run,
                "update_existing": update_existing,
                "entries": entries,
                "summary": self._summary(entries),
            }
        except Exception as e:
            raise _map_http_error(e, op=f"upload folder {root}") from e
