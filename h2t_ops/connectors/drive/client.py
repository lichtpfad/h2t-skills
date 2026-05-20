"""DriveClient — Google Drive adapter (re-wrapped, typed errors).

API logic mirrors plugins/h2t-ops/skills/drive/scripts/drive_cli.py for the
six pure-API verbs. The composite sync-meetings workflow is explicitly out of
scope for #133 and remains legacy debt tracked in #147.
"""
from __future__ import annotations

import io
import mimetypes
import socket
from pathlib import Path
from typing import Any, Dict, List, Optional

from h2t_ops.core.errors import (
    AuthError, ConfigError, H2TError, NetworkError, NotFoundError,
    ProviderError, UsageError,
)
from h2t_ops.core.google_auth import (
    build_google_service,
    resolve_google_credentials,
)

DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive"]

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
    s = str(e).lower()
    if "timeout" in s or "timed out" in s or "connection" in s or "network" in s:
        return NetworkError(f"Drive network error during {op}: {e}")
    return ProviderError(f"Failed to {op}: {e}")


def _escape_query_value(value: str) -> str:
    return value.replace("'", "\\'")


def _row(file: Dict[str, Any]) -> Dict[str, Any]:
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


class DriveClient:
    """Google Drive API client — parity scope #133."""

    def __init__(self) -> None:
        creds = resolve_google_credentials("drive", DRIVE_SCOPES)
        self.service = build_google_service("drive", "v3", creds)

    def _list_paginated(
        self,
        *,
        q: str,
        fields: str,
        page_size: int,
        order_by: Optional[str] = None,
        max_results: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        page_token = None
        while True:
            kwargs = {
                "q": q,
                "fields": fields,
                "pageSize": page_size,
                "pageToken": page_token,
            }
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

    def _resolve_folder_id(self, folder_name: str) -> tuple[Optional[str], str]:
        if not folder_name or folder_name == "root":
            return None, "root"
        safe = _escape_query_value(folder_name)
        resp = self.service.files().list(
            q=(
                f"name='{safe}' and "
                "mimeType='application/vnd.google-apps.folder' and trashed=false"
            ),
            fields="files(id, name)",
            pageSize=5,
        ).execute()
        folders = resp.get("files", [])
        if not folders:
            raise NotFoundError(f"folder not found: {folder_name}")
        if len(folders) > 1:
            raise UsageError(f"ambiguous folder: {folder_name}")
        return folders[0]["id"], folders[0].get("name", folder_name)

    def list_files(
        self,
        folder: Optional[str] = None,
        max_results: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        try:
            if folder:
                folder_id, _ = self._resolve_folder_id(folder)
                q = f"'{folder_id}' in parents and trashed=false"
            else:
                q = "'root' in parents and trashed=false"
            return self._list_paginated(
                q=q,
                fields="nextPageToken, files(id, name, mimeType, modifiedTime, size)",
                page_size=1000,
                order_by="modifiedTime desc",
                max_results=max_results,
            )
        except Exception as e:
            raise _map_http_error(e, op="list files") from e

    def search_files(
        self,
        query: str,
        mime_filter: Optional[str] = None,
        max_results: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
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
        parent: Optional[str] = None,
        max_results: int = 50,
    ) -> List[Dict[str, Any]]:
        try:
            if parent:
                parent_id, _ = self._resolve_folder_id(parent)
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
            )
        except Exception as e:
            raise _map_http_error(e, op="list folders") from e

    def download_file(self, file_id: str, dest: Optional[str | Path] = None) -> Dict[str, Any]:
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
            result: Dict[str, Any] = {
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
        fmt: Optional[str] = None,
        dest: Optional[str | Path] = None,
        to_stdout: bool = False,
    ) -> Dict[str, Any]:
        if to_stdout and fmt in {"docx", "xlsx", "pdf", "pptx"}:
            raise UsageError(f"drive export --print cannot use binary format: {fmt}")
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
            chosen = fmt or formats["default"]
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
                try:
                    import html2text
                except ImportError as e:
                    raise ConfigError(
                        "html2text is required for Drive markdown export.",
                        hint="Install html2text in the h2t-ops environment.",
                    ) from e
                h = html2text.HTML2Text()
                h.ignore_links = False
                h.body_width = 0
                html = content.decode("utf-8") if isinstance(content, bytes) else content
                content = h.handle(html).encode("utf-8")

            text = content.decode("utf-8") if isinstance(content, bytes) else content
            result: Dict[str, Any] = {
                "file_id": file_id,
                "name": name,
                "source_mime": source_mime,
                "export_mime": export_mime,
                "format": chosen,
            }
            if to_stdout:
                result["text"] = text
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
        folder: Optional[str],
        no_convert: bool = False,
    ) -> Dict[str, Any]:
        if not folder:
            raise UsageError("drive upload: --folder is required")
        src = Path(file_path)
        if not src.exists():
            raise NotFoundError(f"file not found: {src}")
        try:
            folder_id, folder_display = self._resolve_folder_id(folder)
            ext = src.suffix.lower()
            convert_info = None if no_convert else UPLOAD_CONVERT_MAP.get(ext)
            if convert_info:
                source_mime, target_mime = convert_info
                dest_name = src.stem
            else:
                source_mime = (
                    mimetypes.guess_type(str(src))[0] or "application/octet-stream"
                )
                target_mime = None
                dest_name = src.name
            metadata: Dict[str, Any] = {"name": dest_name}
            if folder_id:
                metadata["parents"] = [folder_id]
            if target_mime:
                metadata["mimeType"] = target_mime
            media = _media_file_upload()(str(src), mimetype=source_mime, resumable=True)
            res = self.service.files().create(
                body=metadata,
                media_body=media,
                fields="id, name, mimeType, webViewLink",
            ).execute()
            return {
                "file_id": res.get("id", ""),
                "name": res.get("name", ""),
                "mimeType": res.get("mimeType", ""),
                "web_view_link": res.get("webViewLink", ""),
                "folder_name": folder_display,
            }
        except Exception as e:
            raise _map_http_error(e, op=f"upload file {src}") from e
