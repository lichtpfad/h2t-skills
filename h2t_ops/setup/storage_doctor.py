"""What `h2t-ops doctor` says about storage (#548 §7.4). A report, never a gate, never a write
of its own: the caller exits 0 whatever is found (#451).

Secret values are never printed: a path, a key name, a length and sha256[:12] at most.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import stat
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from h2t_ops.core import paths, providers, secrets, store
from h2t_ops.core.errors import ConfigError


@dataclass(frozen=True)
class Finding:
    level: str   # error | warn | info
    code: str
    text: str


_MARKERS = {".stfolder": "Syncthing", ".dropbox": "Dropbox"}
_NEVER_SYNCED = ("secrets.local", "state", "logs", "run/rollback")
_SYNC_SHOWN = ("config", "secrets.shared", "secrets.local", "records", "data", "state", "logs")
_TMP = store._TMP_SUFFIX          # store's temp files are .<name>.XXXX.h2t-tmp (R48)
_STALE_S = 24 * 3600
# class label, its verb, the 3.x entries, where 4.0 keeps it
_LEGACY_CLASSES = (
    ("sessions", "are", ("sessions.h2t", "sessions.dor"), lambda: paths.records("sessions")),
    ("activity", "is", ("activity",), lambda: paths.records("activity")),
    ("evals", "are", ("evals",), lambda: paths.records("evals")),
    ("research", "is", ("research",), lambda: paths.data_dir() / "research"),
    ("creative profiles", "are", ("creative",), lambda: paths.data_dir() / "creative" / "profiles"),
    ("the DOR registry", "is", ("registry.dor",), lambda: paths.records("imports")),
    ("secrets", "are", ("secrets.h2t", "secrets.dor", "secrets.dor_old", "notion.token",
                        "google.store", "google.gmail", "google.dor", "telegram"),
     lambda: paths.root() / "secrets"),
)
_OLD_ENV_HINT = {
    "lake": "the value moved to paths.yaml (lake)",
    "secrets-source": "the migration read that file as a secrets source",
    "evals-spool-source": "the migration copied that spool into state/evals-spool.sqlite",
    "remove": "the package does not read it — remove it",
}


def _show(p: Path) -> str:
    try:
        return str(Path("~") / Path(p).relative_to(paths.home()))
    except ValueError:
        return str(p)


def _sha12(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:12]


def _config() -> paths.PathsConfig:
    try:
        return paths.paths_config()
    except ConfigError:
        return paths.PathsConfig()


def _dir(place_id: str) -> Path:
    if place_id == "run/rollback":
        return paths.run_dir() / "rollback"
    if place_id in ("records", "secrets"):
        return paths.root() / place_id
    return paths.dir_of(place_id)


def _marker(directory: Path) -> Path | None:
    real = Path(os.path.realpath(directory))
    for d in (real, *real.parents):
        for name in _MARKERS:
            if (d / name).exists():
                return d / name
    return None


def _declared(place_id: str, cfg: paths.PathsConfig) -> str | None:
    for key in (place_id, place_id.split(".")[0], place_id.split("/")[0]):
        if key in cfg.sync:
            return cfg.sync[key]
    return None


def sync_status(place_id: str) -> tuple[str, str]:
    """confirmed (a marker up the tree), declared (paths.yaml sync: only) or unknown: what is
    syncing may leave no trace here, so an absent marker is never "not synced"."""
    marker = _marker(_dir(place_id))
    if marker is not None:
        return "confirmed", f"{marker.name} at {_show(marker.parent)}"
    tool = _declared(place_id, _config())
    if tool is not None:
        return "declared", tool
    return "unknown", ""


def _has_data(p: Path) -> bool:
    if p.is_file():
        return True
    return p.is_dir() and any(c.name != "MOVED-TO.txt" for c in p.rglob("*") if c.is_file())


def _git(cfg: Path, *args: str) -> bytes | None:
    try:
        out = subprocess.run(["git", "-C", str(cfg), *args], capture_output=True, timeout=30, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout if out.returncode == 0 else None


def _secret_tracked() -> list[Finding]:
    cfg = paths.config_dir()
    if not (cfg / ".git").exists():
        return []
    listed = _git(cfg, "ls-files", "-z")
    if listed is None:
        return []
    out: list[Finding] = []
    for rel in filter(None, listed.decode("utf-8", "replace").split("\0")):
        shown = _show(cfg / rel)
        if rel.startswith("secrets/"):
            out.append(Finding("error", "secret-tracked", f"{shown} is tracked by git in {_show(cfg)}"))
        body = _git(cfg, "show", f":{rel}")
        if body is None:
            continue
        keys: list[str] = []
        for line in body.decode("utf-8", "replace").splitlines():
            for key, val in secrets.parse_env(line).items():
                if val and providers.provider_of_key(key) and key not in keys:
                    keys.append(key)
        out += [Finding("error", "secret-tracked", f"{shown} holds a value for {k} and is tracked by git")
                for k in keys]
    return out


def _local_in_sync(cfg: paths.PathsConfig) -> list[Finding]:
    out: list[Finding] = []
    for pid in _NEVER_SYNCED:
        d = _dir(pid)
        marker = _marker(d)
        tool = _declared(pid, cfg)
        if marker is not None:
            out.append(Finding("error", "local-in-sync",
                               f"{_show(d)} lies inside a {_MARKERS[marker.name]} folder ({_show(marker)})"))
        elif tool is not None and tool != "none":
            out.append(Finding("error", "local-in-sync",
                               f"{_show(d)} is declared synced ({tool}) in {_show(paths.paths_yaml())}"))
    return out


def _legacy_only() -> list[Finding]:
    out: list[Finding] = []
    for label, verb, names, new in _LEGACY_CLASSES:
        found = [paths.legacy(n) for n in names if _has_data(paths.legacy(n))]
        if found and not _has_data(new()):
            where = ", ".join(_show(p) for p in found)
            out.append(Finding("warn", "legacy-only", f"{label} {verb} only in {where} — h2t-setup sync moves them"))
    return out


def _sync_conflicts() -> list[Finding]:
    out: list[Finding] = []
    for cls in ("records", "secrets", "config"):
        d = paths.root() / cls
        if d.is_dir():
            out += [Finding("warn", "sync-conflict", f"{_show(p)}: a sync conflict copy")
                    for p in sorted(d.rglob("*.sync-conflict-*"))]
    return out


def _known_root_names() -> set[str]:
    names = {"run", paths.layout_file().name, ".stignore", *_MARKERS}
    names |= {p.id.split(".")[0] for p in paths.PLACES if p.kind == "class"}
    # 3.x directories inside ~/.h2t: legacy-only names them, not this check
    names |= {parts[1] for parts in paths.LEGACY.values() if parts[0] == ".h2t" and len(parts) > 1}
    return names


def _unknown_root() -> list[Finding]:
    root = paths.root()
    if not root.is_dir():
        return []
    known = _known_root_names()
    return [Finding("warn", "unknown-root-entry", f"{_show(p)} is not a place of the package")
            for p in sorted(root.iterdir()) if p.name not in known]


def _index_schema() -> list[Finding]:
    from h2t_ops.lifecycle.index.query import index_path
    from h2t_ops.lifecycle.index.schema import SCHEMA_VERSION
    path = index_path()
    if not path.is_file():
        return []
    try:
        with store.connect_sqlite(path, place="state", library="doctor") as conn:
            row = conn.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
    except sqlite3.DatabaseError as exc:
        return [Finding("warn", "index-schema", f"{_show(path)} cannot be read ({exc}) — h2t-ops index rebuild")]
    got = row[0] if row else None
    if got != str(SCHEMA_VERSION):
        return [Finding("warn", "index-schema",
                        f"{_show(path)} has schema {got}, expected {SCHEMA_VERSION} — h2t-ops index rebuild")]
    return []


def _old_env() -> list[Finding]:
    return [Finding("warn", "old-env-name",
                    f"{name} is set; the package no longer reads it: {_OLD_ENV_HINT[paths.OLD_ENV[name]]}")
            for name in paths.old_env_in_use()]


def _places(cfg: paths.PathsConfig) -> list[Finding]:
    out = [Finding("warn", "place-missing", f"{pid} {_show(p)} does not exist")
           for pid, p in sorted(cfg.places.items()) if not p.exists()]
    if not paths.vault().exists():
        out.append(Finding("warn", "place-missing", f"vault {_show(paths.vault())} does not exist ({paths.VAULT_HINT})"))
    out += [Finding("info", "place-unset", f"{pid} is not set; the package uses {_show(paths.data_dir() / pid)}"
                                           f" — h2t-ops paths set {pid} <path>")
            for pid in ("lake", "inbox") if pid not in cfg.places]
    return out


def _config_backups() -> list[Finding]:
    d = paths.config_dir()
    if not d.is_dir():
        return []
    return [Finding("warn", "config-backup", f"{_show(p)} is a 3.x copy; copies now live in "
                                             f"{_show(paths.backups_dir())}")
            for p in sorted(d.glob("*.yaml.bak*")) if p.is_file()]


def _from_copy(p: Path) -> str:
    in_secrets = (paths.root() / "secrets") in Path(os.path.realpath(p)).parents
    try:
        raw = secrets.read_secret_bytes(p) if in_secrets else p.read_bytes()
        if ".env.from-" not in p.name:
            return f"{_show(p)}: sha256 {_sha12(raw)}"
        values = secrets.parse_env(raw.decode("utf-8"))
    except (ConfigError, OSError, UnicodeDecodeError) as exc:
        return f"{_show(p)}: UNREADABLE ({type(exc).__name__})"
    keys = ", ".join(f"{k} (len {len(v)}, sha256 {_sha12(v.encode('utf-8'))})" for k, v in values.items())
    return f"{_show(p)}: {keys or 'no keys'}"


def _from_copies() -> list[Finding]:
    """Every place the migration writes into (§8: both copies are kept, doctor shows them)."""
    root = paths.root()
    found: list[Path] = []
    for d in (paths.secrets_shared(), paths.secrets_local(), root / "records", paths.state_dir(),
              paths.data_dir()):
        if d.is_dir():
            found += sorted(d.rglob("*.from-*"))
    if paths.config_dir().is_dir():
        found += sorted(paths.config_dir().glob("*.from-*"))
    return [Finding("info", "from-copies", _from_copy(p)) for p in found if p.is_file()]


def _stale_temps(cfg: paths.PathsConfig) -> list[Finding]:
    root = paths.root()
    dirs = [root / c for c in ("config", "secrets", "records", "data", "state", "logs")]
    dirs += [paths.run_dir(), *(cfg.places[p] for p in ("lake", "inbox") if p in cfg.places)]
    now = time.time()
    out: list[Finding] = []
    for d in dirs:
        if not d.is_dir():
            continue
        for p in sorted(d.rglob(f".*{_TMP}")):
            try:
                st = p.stat()
            except OSError:
                continue
            if p.is_file() and now - st.st_mtime > _STALE_S:
                out.append(Finding("warn", "stale-temp",
                                   f"{_show(p)} ({st.st_size} bytes) is left from a killed write; remove it by hand"))
    return out


def _perms() -> list[Finding]:
    if os.name == "nt":              # Windows: the profile ACL protects, nothing to check (§11.3)
        return []
    base = paths.root() / "secrets"
    if not base.is_dir():
        return []
    out: list[Finding] = []
    for d, _dirs, files in os.walk(base):
        for p, want in ((Path(d), 0o700), *((Path(d) / f, 0o600) for f in files)):
            st = os.lstat(p)
            if stat.S_ISLNK(st.st_mode):
                continue
            mode = stat.S_IMODE(st.st_mode)
            if mode != want:
                out.append(Finding("error", "perms", f"{_show(p)} is {mode:04o}, expected {want:04o}"))
    return out


_RANK = {"error": 0, "warn": 1, "info": 2}


def check() -> list[Finding]:
    try:
        cfg = paths.paths_config()
        broken: list[Finding] = []
    except ConfigError as exc:
        cfg, broken = paths.PathsConfig(), [Finding("error", "paths-yaml", str(exc))]
    found = [*broken, *_secret_tracked(), *_local_in_sync(cfg), *_perms(), *_legacy_only(),
             *_sync_conflicts(), *_unknown_root(), *_index_schema(), *_old_env(), *_places(cfg),
             *_config_backups(), *_stale_temps(cfg), *_from_copies()]
    return sorted(found, key=lambda f: _RANK[f.level])


def _layout() -> str:
    f = paths.layout_file()
    if not f.is_file():
        return "none"
    try:
        return str(json.loads(f.read_text(encoding="utf-8")).get("layout"))
    except (OSError, ValueError, AttributeError):
        return "unreadable"


def report() -> list[str]:
    lines = [f"storage: layout {_layout()}, root {_show(paths.root())}"]
    sync = []
    for pid in _SYNC_SHOWN:
        status, why = sync_status(pid)
        sync.append(f"{pid} = {status}" + (f" ({why})" if why else ""))
    lines.append("storage: sync " + ", ".join(sync))
    label = {"error": "ERROR", "warn": "warn", "info": "info"}
    lines += [f"storage: {label[f.level]} {f.code}: {f.text}" for f in check()]
    return lines
