"""DropboxClient — HTTP API v2 adapter (#469).

Reaches files the desktop client cannot: an online-only placeholder has no bytes
on disk, so ffmpeg and plain reads fail on it while the API serves the content.

requests is imported lazily so registry/help paths stay lightweight.
"""
from __future__ import annotations

import gzip
import json
import os
from pathlib import Path
from typing import Any

from h2t_ops.core.errors import (
    AuthError,
    ConfigError,
    NetworkError,
    NotFoundError,
    ProviderError,
    UsageError,
)
from h2t_ops.core.secrets import load_secrets

RPC_BASE = "https://api.dropboxapi.com/2"
CONTENT_BASE = "https://content.dropboxapi.com/2"
# The path the issue named. load_secrets only reads secrets.env, so a token written
# here would otherwise be read by nothing at all.
PROVIDER_ENV_FILE = Path.home() / ".h2t" / "config" / "secrets" / "dropbox.env"


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


def _load_provider_env() -> None:
    if not PROVIDER_ENV_FILE.is_file():
        return
    for raw in PROVIDER_ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        if key and key not in os.environ:
            os.environ[key] = val.strip().strip('"').strip("'")


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
                    "Enable files.metadata.read and files.content.read on the app, then "
                    "generate a NEW token — a token issued before the scope was added "
                    "keeps the scopes it was born with."
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
    """Read-only Dropbox adapter: account, meta, list, download."""

    def __init__(self) -> None:
        load_secrets()
        _load_provider_env()
        self._timeout = int(os.environ.get("DROPBOX_TIMEOUT", "60"))
        self._path_root: str | None = None
        self._resolving_root = False
        token = os.environ.get("DROPBOX_TOKEN", "").strip()
        if not token:
            token = self._refresh_access_token()
        if not token:
            raise ConfigError(
                "DROPBOX_TOKEN not set.",
                hint=(
                    "Add DROPBOX_TOKEN to ~/.h2t/config/secrets/secrets.env (or to "
                    f"{PROVIDER_ENV_FILE}). A dashboard token expires in ~4 hours; for "
                    "durable access set DROPBOX_APP_KEY, DROPBOX_APP_SECRET and "
                    "DROPBOX_REFRESH_TOKEN instead."
                ),
            )
        self._token = token

    # --- auth ---

    def _refresh_access_token(self) -> str:
        """Exchange a refresh token for a short-lived access token, if configured."""
        refresh = os.environ.get("DROPBOX_REFRESH_TOKEN", "").strip()
        app_key = os.environ.get("DROPBOX_APP_KEY", "").strip()
        app_secret = os.environ.get("DROPBOX_APP_SECRET", "").strip()
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
        return all(
            os.environ.get(key, "").strip()
            for key in ("DROPBOX_REFRESH_TOKEN", "DROPBOX_APP_KEY", "DROPBOX_APP_SECRET")
        )

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
                data=json.dumps(arg).encode("utf-8") if arg is not None else None,
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

    def download(
        self, path: str, dest: str, *, gunzip: bool = False, _retried: bool = False
    ) -> dict[str, Any]:
        import requests as _r  # lazy — module-scope import forbidden

        api_path = normalize_path(path)
        if not api_path:
            raise UsageError("dropbox download: a file path is required")
        target = Path(dest)
        if target.is_dir():
            target = target / api_path.rsplit("/", 1)[-1]
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            resp = _r.post(
                f"{CONTENT_BASE}/files/download",
                headers=self._headers({"Dropbox-API-Arg": json.dumps({"path": api_path})}),
                stream=True,
                timeout=self._timeout,
            )
        except _r.RequestException as exc:
            raise NetworkError(f"Dropbox download of {api_path} failed: {exc}") from exc
        if self._should_refresh(resp, _retried):
            self._token = self._refresh_access_token()
            return self.download(path, dest, gunzip=gunzip, _retried=True)
        _raise_for_status(resp, f"download {api_path}")
        # Stream into a sibling and rename at the end: a mid-stream failure used to
        # leave a truncated file at the destination, on top of whatever was there.
        part = target.with_name(target.name + ".part")
        written = 0
        try:
            with open(part, "wb") as fh:
                for chunk in resp.iter_content(chunk_size=1 << 20):
                    if chunk:
                        fh.write(chunk)
                        written += len(chunk)
            if gunzip:
                written = self._gunzip_in_place(part)
            os.replace(part, target)
        except _r.RequestException as exc:
            part.unlink(missing_ok=True)
            raise NetworkError(
                f"Dropbox download of {api_path} failed mid-stream: {exc}"
            ) from exc
        except BaseException:
            part.unlink(missing_ok=True)
            raise
        return {"path": api_path, "saved_to": str(target), "bytes": written}

    @staticmethod
    def _gunzip_in_place(target: Path) -> int:
        """.prproj and friends are gzip under a non-gz name; leave a non-gzip file alone.

        Decompressed in chunks against a ceiling, because the compression ratio is
        the uploader's choice: a few MB of gzip expands to as much as it likes.
        """
        with open(target, "rb") as probe:
            if probe.read(2) != b"\x1f\x8b":
                return target.stat().st_size
        cap = int(os.environ.get("DROPBOX_MAX_GUNZIP_BYTES", str(512 << 20)))
        plain = target.with_name(target.name + ".gunzip")
        written = 0
        try:
            with gzip.open(target, "rb") as src, open(plain, "wb") as dst:
                while True:
                    chunk = src.read(1 << 20)
                    if not chunk:
                        break
                    written += len(chunk)
                    if written > cap:
                        raise ProviderError(
                            f"{target.name}: gunzip exceeded the {cap} byte cap. "
                            "Raise DROPBOX_MAX_GUNZIP_BYTES or download without --gunzip."
                        )
                    dst.write(chunk)
            os.replace(plain, target)
        except BaseException:
            plain.unlink(missing_ok=True)
            raise
        return written
