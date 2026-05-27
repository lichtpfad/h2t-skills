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
    if "service_disabled" in lowered and "docs.googleapis.com" in lowered:
        return ConfigError(
            "Google Docs API is disabled for the current Google project.",
            hint="Enable docs.googleapis.com for the active project, then retry.",
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


_HEADING_NAMED_STYLE = {1: "HEADING_1", 2: "HEADING_2", 3: "HEADING_3"}


def _md_to_docs_requests(markdown_text: str, tab_id: str) -> List[Dict[str, Any]]:
    """Convert markdown to Docs API batchUpdate requests targeting *tab_id*.

    v1 scope: H1–H3 headings, paragraphs, unordered bullets (- or *).
    Inline bold/italic not supported in v1.

    All text is inserted at index 1 (start of an empty tab body) in one
    insertText request, followed by style/bullet requests with pre-computed
    stable indices.
    """
    paragraphs: List[Dict[str, Any]] = []
    for line in markdown_text.splitlines():
        m = re.match(r'^(#{1,3})\s+(.*)', line)
        if m:
            paragraphs.append({"type": f"heading{len(m.group(1))}", "text": m.group(2)})
            continue
        m = re.match(r'^[-*]\s+(.*)', line)
        if m:
            paragraphs.append({"type": "bullet", "text": m.group(1)})
            continue
        paragraphs.append({"type": "paragraph", "text": line})

    if not paragraphs:
        return []

    full_text = "".join(p["text"] + "\n" for p in paragraphs)
    requests: List[Dict[str, Any]] = [{
        "insertText": {
            "location": {"index": 1, "tabId": tab_id},
            "text": full_text,
        }
    }]

    current = 1
    for p in paragraphs:
        para_len = len(p["text"]) + 1  # +1 for \n
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

    return requests


class DriveClient:
    """Google Drive API client — parity scope #133."""

    def __init__(self) -> None:
        creds = resolve_google_credentials("drive", DRIVE_SCOPES)
        self._creds = creds
        self.service = build_google_service("drive", "v3", creds)
        self._docs_service = None

    def _docs(self):
        if self._docs_service is None:
            self._docs_service = build_google_service("docs", "v1", self._creds)
        return self._docs_service

    def _list_paginated(
        self,
        *,
        q: str,
        fields: str,
        page_size: int,
        order_by: Optional[str] = None,
        max_results: Optional[int] = None,
        drive_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
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

    def _resolve_folder_id(self, folder_name: str) -> tuple[Optional[str], str, bool]:
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
        folder: Optional[bool] = None,
    ) -> Optional[Dict[str, Any]]:
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
    def _summary(entries: list[Dict[str, Any]]) -> Dict[str, int]:
        counts: Dict[str, int] = {}
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
        entries: list[Dict[str, Any]],
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
        entries: list[Dict[str, Any]],
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
            ).execute()
            action = "file_updated"
        else:
            res = self.service.files().create(
                body={"name": src.name, "parents": [parent_id]},
                media_body=media,
                fields="id, name, mimeType, webViewLink",
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
        folder: Optional[str] = None,
        max_results: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
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
        parent: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not name or not name.strip():
            raise UsageError("drive create-folder: name is required")
        try:
            parent_id = None
            parent_name = "root"
            if parent:
                parent_id, parent_name, _ = self._resolve_folder_id(parent)
            body: Dict[str, Any] = {"name": name.strip(), "mimeType": FOLDER_MIME}
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

    def rename_file(self, file_id: str, new_name: str) -> Dict[str, Any]:
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
        new_name: Optional[str] = None,
        folder: Optional[str] = None,
    ) -> Dict[str, Any]:
        try:
            body: Dict[str, Any] = {}
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

    def move_file(self, file_id: str, *, destination_folder_id: str) -> Dict[str, Any]:
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

    def list_document_tabs(self, document_id: str) -> Dict[str, Any]:
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

        def _flatten(tabs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
            rows: List[Dict[str, Any]] = []
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

    def add_document_tab(self, document_id: str, title: str) -> Dict[str, Any]:
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
    ) -> Dict[str, Any]:
        """Write markdown content to an existing Google Docs tab via batchUpdate.

        v1 scope: H1–H3 headings, paragraphs, unordered bullet lists.
        Appends to the beginning of the tab body (index 1). Does not clear
        existing content — call on a freshly created (empty) tab.
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
            reqs = _md_to_docs_requests(markdown_text, tab_id)
            if not reqs:
                return {
                    "kind": "google_docs_tab_write/v1",
                    "document_id": document_id,
                    "tab_id": tab_id,
                    "requests_sent": 0,
                }
            response = self._docs().documents().batchUpdate(
                documentId=document_id,
                body={"requests": reqs},
            ).execute()
        except Exception as e:
            raise _map_http_error(e, op=f"write tab {tab_id} in document {document_id}") from e
        return {
            "kind": "google_docs_tab_write/v1",
            "document_id": document_id,
            "tab_id": tab_id,
            "requests_sent": len(reqs),
            "revision_id": (response.get("writeControl") or {}).get("requiredRevisionId", ""),
        }

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

    def share_file(
        self,
        file_id: str,
        *,
        email: Optional[str] = None,
        role: str = "reader",
        anyone: bool = False,
        get_link: bool = False,
    ) -> Dict[str, Any]:
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
            perm_body: Dict[str, Any] = {"type": perm_type, "role": role}
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
    ) -> Dict[str, Any]:
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
            entries: list[Dict[str, Any]] = []
            folder_ids: Dict[Path, str] = {Path("."): parent_id}

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
