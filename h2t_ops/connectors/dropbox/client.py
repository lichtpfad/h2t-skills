"""DropboxClient — HTTP API v2 adapter (#469).

Reaches files the desktop client cannot: an online-only placeholder has no bytes
on disk, so ffmpeg and plain reads fail on it while the API serves the content.

requests is imported lazily so registry/help paths stay lightweight.
"""
from __future__ import annotations

import gzip
import json
from pathlib import Path
from typing import Any

from h2t_ops.core import downloads, paths, secrets, store
from h2t_ops.core.errors import (
    AuthError,
    ConfigError,
    NetworkError,
    NotFoundError,
    ProviderError,
    UsageError,
)

RPC_BASE = "https://api.dropboxapi.com/2"
CONTENT_BASE = "https://content.dropboxapi.com/2"
UPLOAD_LIMIT = 150 * 1024 * 1024  # files/upload takes at most 150 MB in one request


def normalize_path(path: str) -> str:
    """Dropbox addresses the root as "" and everything else as "/a/b".

    The path is the one from the Dropbox root, never from a local drive:
    E:/DROPBOX/LichtPfad Dropbox/HOU2TOUCH/X is /HOU2TOUCH/X here.
    """
    p = (path or "").strip()
    if p in ("", "/"):
        return ""
    p = p.rstrip("/")
    return p if p.startswith("/") else f"/{p}"


_TOKEN_KEYS = ("DROPBOX_TOKEN", "DROPBOX_REFRESH_TOKEN", "DROPBOX_APP_KEY", "DROPBOX_APP_SECRET")


def _copy_stream(chunks: Any, dst: Any) -> int:
    written = 0
    for chunk in chunks:
        if chunk:
            dst.write(chunk)
            written += len(chunk)
    return written


def _token_config() -> dict[str, str]:
    """The access token and the refresh triple, each "" when unset (#548 §7.2: one reader)."""
    return {key: (secrets.get(key) or "").strip() for key in _TOKEN_KEYS}


def _raise_for_status(resp: Any, context: str) -> None:
    """Map a Dropbox HTTP status to a typed h2t_ops error. Raises if >= 400."""
    status = resp.status_code
    if status < 400:
        return
    body = (getattr(resp, "text", "") or "")[:300]
    if status == 401:
        if "missing_scope" in body:
            raise AuthError(
                f"DROPBOX_SCOPE_MISSING: the token lacks a required scope ({context})",
                hint=(
                    "Enable account_info.read, files.metadata.read and files.content.read "
                    "on the app, then generate a NEW token — a token issued before a scope "
                    "was added keeps the scopes it was born with. account_info.read is not "
                    "optional: every command resolves the team namespace through "
                    "users/get_current_account before it touches a file. Writes need more: "
                    "upload needs files.content.write, link needs sharing.write."
                ),
            )
        raise AuthError(
            f"DROPBOX_TOKEN invalid or expired (401 from {context})",
            hint="A dashboard-generated token lasts ~4 hours. Set DROPBOX_REFRESH_TOKEN "
                 "with DROPBOX_APP_KEY and DROPBOX_APP_SECRET for durable access.",
        )
    if status == 409:
        if "not_found" in body:
            raise NotFoundError(f"Not found: {context}")
        raise UsageError(f"Dropbox rejected the request ({context}): {body}")
    if status == 429:
        raise ProviderError(f"Dropbox rate limit exceeded ({context})")
    if status >= 500:
        raise ProviderError(f"Dropbox server error {status} ({context}): {body}")
    raise ProviderError(f"Dropbox error {status} ({context}): {body}")


class DropboxClient:
    """Dropbox adapter: account, meta, list, download; writes: upload, link."""

    def __init__(self) -> None:
        self._timeout = int(secrets.get("DROPBOX_TIMEOUT") or "60")
        self._path_root: str | None = None
        self._resolving_root = False
        token = _token_config()["DROPBOX_TOKEN"]
        if not token:
            token = self._refresh_access_token()
        if not token:
            raise ConfigError(
                "DROPBOX_TOKEN not set.",
                hint=(
                    f"Add DROPBOX_TOKEN to {secrets.provider_file('dropbox')}. A dashboard "
                    "token expires in ~4 hours; for "
                    "durable access set DROPBOX_APP_KEY, DROPBOX_APP_SECRET and "
                    "DROPBOX_REFRESH_TOKEN instead."
                ),
            )
        self._token = token

    # --- auth ---

    def _refresh_access_token(self) -> str:
        """Exchange a refresh token for a short-lived access token, if configured."""
        cfg = _token_config()
        refresh = cfg["DROPBOX_REFRESH_TOKEN"]
        app_key, app_secret = cfg["DROPBOX_APP_KEY"], cfg["DROPBOX_APP_SECRET"]
        if not (refresh and app_key and app_secret):
            return ""
        import requests as _r  # lazy — module-scope import forbidden

        try:
            resp = _r.post(
                "https://api.dropboxapi.com/oauth2/token",
                data={"grant_type": "refresh_token", "refresh_token": refresh},
                auth=(app_key, app_secret),
                timeout=self._timeout,
            )
        except _r.RequestException as exc:
            raise NetworkError(f"Dropbox token refresh failed: {exc}") from exc
        _raise_for_status(resp, "oauth2/token")
        return (resp.json() or {}).get("access_token", "")

    # --- transport ---

    def _headers(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        headers = {"Authorization": f"Bearer {self._token}"}
        # A Business account's team folders live outside the member's home namespace
        # and are unreachable without this header.
        root = "" if getattr(self, "_resolving_root", False) else self.path_root()
        if root:
            headers["Dropbox-API-Path-Root"] = json.dumps({".tag": "root", "root": root})
        headers.update(extra or {})
        return headers

    def path_root(self) -> str:
        # Assign only on success: a transient failure here used to leave "" cached,
        # and every later call then read the wrong namespace in silence.
        if self._path_root is None:
            self._path_root = self._resolve_path_root()
        return self._path_root

    def _resolve_path_root(self) -> str:
        self._resolving_root = True  # the resolving call itself carries no root header
        try:
            account = self.account()
        finally:
            self._resolving_root = False
        root_info = account.get("root_info") or {}
        root = str(root_info.get("root_namespace_id", "") or "")
        home = str(root_info.get("home_namespace_id", "") or "")
        return root if root and root != home else ""

    def _can_refresh(self) -> bool:
        cfg = _token_config()
        return all(cfg[key] for key in ("DROPBOX_REFRESH_TOKEN", "DROPBOX_APP_KEY", "DROPBOX_APP_SECRET"))

    def _should_refresh(self, resp: Any, retried: bool) -> bool:
        """A 401 on a refreshable account means the ~4h access token aged out.

        missing_scope is excluded: a new access token carries the same scopes, so
        retrying would only spend a round trip to fail identically.
        """
        if retried or resp.status_code != 401:
            return False
        if "missing_scope" in (getattr(resp, "text", "") or ""):
            return False
        return self._can_refresh()

    def _rpc(self, endpoint: str, arg: Any, _retried: bool = False) -> Any:
        import requests as _r  # lazy — module-scope import forbidden

        try:
            resp = _r.post(
                f"{RPC_BASE}/{endpoint}",
                # A no-argument endpoint still needs a JSON body: `null`, not an empty one,
                # which users/get_current_account answers with a 500.
                data=json.dumps(arg).encode("utf-8"),
                headers=self._headers({"Content-Type": "application/json"}),
                timeout=self._timeout,
            )
        except _r.RequestException as exc:
            raise NetworkError(f"Dropbox request to {endpoint} failed: {exc}") from exc
        if self._should_refresh(resp, _retried):
            self._token = self._refresh_access_token()
            return self._rpc(endpoint, arg, _retried=True)
        _raise_for_status(resp, endpoint)
        return resp.json() if resp.text else {}

    # --- verbs ---

    def account(self) -> dict[str, Any]:
        return self._rpc("users/get_current_account", None) or {}

    def meta(self, path: str) -> dict[str, Any]:
        return self._rpc("files/get_metadata", {"path": normalize_path(path)})

    def list_folder(
        self, path: str, *, recursive: bool = False, limit: int | None = None
    ) -> list[dict[str, Any]]:
        arg = {"path": normalize_path(path), "recursive": bool(recursive)}
        page = self._rpc("files/list_folder", arg)
        entries = list(page.get("entries", []))
        while page.get("has_more") and (limit is None or len(entries) < limit):
            page = self._rpc("files/list_folder/continue", {"cursor": page["cursor"]})
            entries.extend(page.get("entries", []))
        return entries[:limit] if limit is not None else entries

    def _download_response(self, api_path: str) -> Any:
        import requests as _r  # lazy — module-scope import forbidden

        for retried in (False, True):
            try:
                resp = _r.post(
                    f"{CONTENT_BASE}/files/download",
                    headers=self._headers({"Dropbox-API-Arg": json.dumps({"path": api_path})}),
                    stream=True,
                    timeout=self._timeout,
                )
            except _r.RequestException as exc:
                raise NetworkError(f"Dropbox download of {api_path} failed: {exc}") from exc
            if not self._should_refresh(resp, retried):
                break
            self._token = self._refresh_access_token()
        _raise_for_status(resp, f"download {api_path}")
        return resp

    def download(
        self, path: str, dest: str | None = None, *, gunzip: bool = False
    ) -> dict[str, Any]:
        """dest: a file or directory the user named, replaced. None: a new file in the
        inbox under the Dropbox name, never over a file already there (§6 п. 1, R47).

        The bytes stream into a store.writer handle (R29): a mid-stream failure leaves no
        file, and whatever was at the destination stays as it was.
        """
        import requests as _r  # lazy — module-scope import forbidden

        api_path = normalize_path(path)
        if not api_path:
            raise UsageError("dropbox download: a file path is required")
        name = downloads.last_segment(api_path)
        written = 0

        def write(fh) -> None:
            nonlocal written
            resp = self._download_response(api_path)
            try:
                if not gunzip:
                    written = _copy_stream(resp.iter_content(chunk_size=1 << 20), fh)
                    return
                # gzip needs the whole file to sniff and decompress: raw bytes in scratch,
                # the plain ones into the handle.
                with store.scratch("h2t-dropbox-") as d:
                    raw = d / "raw"
                    with store.writer(raw, place="tmp") as out:
                        _copy_stream(resp.iter_content(chunk_size=1 << 20), out)
                    written = self._gunzip_into(raw, fh, name)
            except _r.RequestException as exc:
                raise NetworkError(
                    f"Dropbox download of {api_path} failed mid-stream: {exc}"
                ) from exc

        if dest is None:
            target, defaulted = downloads.save_default(name, write)
        else:
            target, defaulted = paths.expand_user_dest(dest), False
            if target.is_dir():
                target = target / name
            with store.writer(target, place="inbox", dest=True) as fh:
                write(fh)
        return {"path": api_path, "saved_to": str(target), "defaulted": defaulted,
                "bytes": written}

    def upload(self, local: str, dest: str, *, _retried: bool = False) -> dict[str, Any]:
        """Send one local file to `dest`. Never overwrites: an existing path is reported
        as "exists" and left alone. The stored size is read back from the answer."""
        import requests as _r  # lazy — module-scope import forbidden

        src = Path(local)
        if not src.is_file():
            raise UsageError(f"dropbox upload: not a file: {local}")
        api_path = normalize_path(dest)
        if not api_path:
            raise UsageError("dropbox upload: a destination path is required")
        size = src.stat().st_size
        if size > UPLOAD_LIMIT:
            raise UsageError(
                f"dropbox upload: {src.name} is {size} bytes, over the 150 MB single-request "
                "limit; upload sessions are not implemented"
            )
        # The header must be ASCII: json.dumps escapes non-ASCII names as \uXXXX.
        arg = json.dumps({"path": api_path, "mode": "add", "autorename": False, "mute": True})
        try:
            with open(src, "rb") as fh:
                resp = _r.post(
                    f"{CONTENT_BASE}/files/upload",
                    data=fh,
                    headers=self._headers({"Content-Type": "application/octet-stream",
                                           "Dropbox-API-Arg": arg}),
                    timeout=self._timeout,
                )
        except _r.RequestException as exc:
            raise NetworkError(f"Dropbox upload of {api_path} failed: {exc}") from exc
        if self._should_refresh(resp, _retried):
            self._token = self._refresh_access_token()
            return self.upload(local, dest, _retried=True)
        # only the path conflict means "something is already there"; any other 409 is an error
        if resp.status_code == 409 and "path/conflict" in (getattr(resp, "text", "") or ""):
            return {"path": api_path, "bytes": None, "status": "exists"}
        _raise_for_status(resp, f"upload {api_path}")
        stored = (resp.json() or {}).get("size")
        if stored != size:
            raise ProviderError(f"Dropbox stored {stored} bytes for {api_path}, sent {size}")
        return {"path": api_path, "bytes": size, "status": "uploaded"}

    def link(self, path: str) -> dict[str, Any]:
        """The path's existing shared link, or a new public one."""
        api_path = normalize_path(path)
        if not api_path:
            raise UsageError("dropbox link: a path is required")
        links = self._rpc("sharing/list_shared_links",
                          {"path": api_path, "direct_only": True}).get("links") or []
        if links:
            found = links[0]
            visibility = ((found.get("link_permissions") or {})
                          .get("resolved_visibility") or {}).get(".tag", "")
            return {"path": api_path, "url": found["url"], "created": False,
                    "visibility": visibility}
        made = self._rpc("sharing/create_shared_link_with_settings",
                         {"path": api_path, "settings": {"requested_visibility": "public"}})
        return {"path": api_path, "url": made["url"], "created": True, "visibility": "public"}

    @staticmethod
    def _gunzip_into(raw: Path, dst: Any, name: str) -> int:
        """.prproj and friends are gzip under a non-gz name; a non-gzip file goes as it is.

        Decompressed in chunks against a ceiling, because the compression ratio is
        the uploader's choice: a few MB of gzip expands to as much as it likes.
        """
        with open(raw, "rb") as probe:
            gz = probe.read(2) == b"\x1f\x8b"
        if not gz:
            with open(raw, "rb") as src:
                return _copy_stream(iter(lambda: src.read(1 << 20), b""), dst)
        cap = int(secrets.get("DROPBOX_MAX_GUNZIP_BYTES") or str(512 << 20))
        written = 0
        with gzip.open(raw, "rb") as src:
            while True:
                chunk = src.read(1 << 20)
                if not chunk:
                    break
                written += len(chunk)
                if written > cap:
                    raise ProviderError(
                        f"{name}: gunzip exceeded the {cap} byte cap. "
                        "Raise DROPBOX_MAX_GUNZIP_BYTES or download without --gunzip."
                    )
                dst.write(chunk)
        return written
