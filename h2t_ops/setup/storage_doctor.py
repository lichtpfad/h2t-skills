"""What `h2t-ops doctor` says about storage (#548 §7.4). A report, never a gate, never a write
of its own: the caller exits 0 whatever is found (#451).

Secret values are never printed: a path, a key name, a length and sha256[:12] at most.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import stat
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

import yaml

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
    "lake": "the migration moves the value into paths.yaml (lake)",
    "secrets-source": "the migration reads that file as a secrets source",
    "evals-spool-source": "the migration copies that spool into state/evals-spool.sqlite",
    "remove": "the migration does not copy from it — move what it names to the 3.x default, then remove it",
}


def _show(p: Path) -> str:
    """~/… with forward slashes on every platform, as the spec and paths.yaml write it."""
    return paths.home_form(Path(p))


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
            m = d / name
            # Dropbox marks a synced folder with a `.dropbox` file; ~/.dropbox, a directory,
            # is the client's own state and sits in every home that has the client.
            if m.is_file() if name == ".dropbox" else m.exists():
                return m
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


_GIT_TIMEOUT_S = 30


def _git(cfg: Path, *args: str) -> tuple[bytes | None, str]:
    """(stdout, "") or (None, why it failed): a failed git is said, never a silent skip."""
    try:
        out = subprocess.run(["git", "-C", str(cfg), *args], capture_output=True,
                             timeout=_GIT_TIMEOUT_S, check=False)
    except subprocess.TimeoutExpired:
        return None, f"git {args[0]} timed out after {_GIT_TIMEOUT_S} s"
    except (OSError, subprocess.SubprocessError) as exc:
        return None, f"git {args[0]} could not run ({type(exc).__name__}: {exc})"
    if out.returncode != 0:
        err = out.stderr.decode("utf-8", "replace").strip().splitlines()
        return None, f"git {args[0]} exited {out.returncode}" + (f": {err[0]}" if err else "")
    return out.stdout, ""


def _unreadable(where: str, why: str) -> Finding:
    return Finding("warn", "secret-tracked", f"UNREADABLE {where}: {why}")


# Fields that hold a credential in the JSON and YAML the providers ship (a Google client or
# token, Telegram's config.json), beside the provider env keys (EXA_API_KEY, …).
_SECRET_FIELDS = frozenset({"refresh_token", "access_token", "client_secret", "api_hash"})


# A provider prefix alone does not make a credential: NOTION_DB_ID is a database id. The
# key must also end in a credential word (EXA_API_KEY, NOTION_API_TOKEN, TELEGRAM_API_HASH).
_CREDENTIAL_END = re.compile(r"_(KEY|TOKEN|SECRET|HASH|PASSWORD)$")
# An example in a rule or README, not a value: `...`, `<your key>`, `$KEY`, `${KEY}`, `xxx`.
_PLACEHOLDER = re.compile(r"^(\.{2,}|<[^>]*>|\$\{?\w+\}?|x{3,}|your[\w-]*|changeme)$", re.I)


def _is_secret_key(key: str) -> bool:
    up = key.upper()
    return key.lower() in _SECRET_FIELDS or (
        providers.provider_of_key(up) is not None and _CREDENTIAL_END.search(up) is not None)


def _is_value(val: object) -> bool:
    s = str(val).strip()
    return bool(s) and _PLACEHOLDER.match(s) is None


def _structured_keys(rel: str, body: bytes) -> list[str]:
    """Secret keys with a non-empty value anywhere in a tracked YAML or JSON file. Names
    only; a file that does not parse is not reported here (it is not a credential store)."""
    if not rel.endswith((".yaml", ".yml", ".json")):
        return []
    try:
        text = body.decode("utf-8-sig")
        doc = json.loads(text) if rel.endswith(".json") else yaml.safe_load(text)
    except (ValueError, yaml.YAMLError):
        return []
    found: list[str] = []
    stack = [doc]
    seen: set[int] = set()      # a YAML alias can make a container hold itself
    while stack:
        node = stack.pop()
        if isinstance(node, (dict, list)):
            if id(node) in seen:
                continue
            seen.add(id(node))
        if isinstance(node, dict):
            for k, v in node.items():
                if isinstance(v, (dict, list)):
                    stack.append(v)
                elif isinstance(k, str) and v is not None and _is_value(v) and _is_secret_key(k) \
                        and k not in found:
                    found.append(k)
        elif isinstance(node, list):
            stack.extend(node)
    return sorted(found)


def _secret_tracked() -> list[Finding]:
    cfg = paths.config_dir()
    if not (cfg / ".git").exists():
        return []
    listed, why = _git(cfg, "ls-files", "-z")
    if listed is None:
        return [_unreadable(_show(cfg), why)]
    out: list[Finding] = []
    for rel in filter(None, listed.decode("utf-8", "replace").split("\0")):
        shown = _show(cfg / rel)
        if rel.startswith("secrets/"):
            out.append(Finding("error", "secret-tracked", f"{shown} is tracked by git in {_show(cfg)}"))
        body, why = _git(cfg, "show", f":{rel}")
        if body is None:
            out.append(_unreadable(shown, why))
            continue
        keys: list[str] = []
        for line in body.decode("utf-8", "replace").splitlines():
            for key, val in secrets.parse_env(line).items():
                if _is_value(val) and _is_secret_key(key) and key not in keys:
                    keys.append(key)
        keys += [k for k in _structured_keys(rel, body) if k not in keys]
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
    # .DS_Store: Finder writes it anywhere; graphs: h2t-transcription keeps its graphs there
    names = {"run", paths.layout_file().name, ".stignore", ".DS_Store", "graphs", *_MARKERS,
             *paths.ROOT_3X}
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
        return [Finding("info", "index-schema", f"{_show(path)} is not built yet; the first session-start"
                                                f" or h2t-ops index rebuild builds it")]
    try:
        with store.read_sqlite(path) as conn:      # read-only: doctor writes nothing
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
        # Only a vault someone set is a problem; the default absent is a new user without POS (§12).
        level = "info" if paths.source("vault") == "default" else "warn"
        out.append(Finding(level, "place-missing", f"vault {_show(paths.vault())} does not exist ({paths.VAULT_HINT})"))
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
            for p in sorted(d.glob("*.bak*")) if p.is_file()]


def _from_copy(p: Path) -> str:
    real = Path(os.path.realpath(p))
    in_secrets = any(Path(os.path.realpath(s)) in real.parents
                     for s in (paths.root() / "secrets", paths.secrets_shared(), paths.secrets_local()))
    try:
        raw = secrets.read_secret_bytes(p) if in_secrets else p.read_bytes()
        if not secrets.ENV_COPY.search(p.name):      # numbered too: exa.env-2.from-dor
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
    shared = paths.secrets_shared()
    out: list[Finding] = []
    for d, dirs, files in os.walk(base):
        # secrets/shared is synced: a Windows peer sends 0644 with every edit, and the owner
        # does not want its modes checked (#573). Only the machine's own secrets are.
        dirs[:] = [x for x in dirs if Path(d) / x != shared]
        for p, want in ((Path(d), 0o700), *((Path(d) / f, 0o600) for f in files)):
            st = os.lstat(p)
            if stat.S_ISLNK(st.st_mode):
                continue
            mode = stat.S_IMODE(st.st_mode)
            if mode != want:
                out.append(Finding("error", "perms", f"{_show(p)} is {mode:04o}, expected {want:04o}"))
    return out


def _foreign_files(cfg: paths.PathsConfig) -> list[Finding]:
    """§7.1 manifest protocol, step 3: a file on a path a connector tried to create but does
    not own (refused by a committed row, or named by a pending row and never committed) is
    left untouched by the connector — and shown here."""
    from h2t_ops.core.lake import ConnectorDir
    lakes = [cfg.places["lake"]] if "lake" in cfg.places else []
    lakes.append(paths.data_dir() / "lake")
    out: list[Finding] = []
    for lake in lakes:
        if not lake.is_dir():
            continue
        for d in sorted(p for p in lake.iterdir() if (p / "manifest.jsonl").is_file()):
            cdir = ConnectorDir(d.name, root=d)
            rows = cdir._rows()
            committed = {r.get("op") for r in rows if r.get("state") == "committed"}
            named = {rel for r in rows if r.get("state") == "committed" for rel in r.get("refused") or ()}
            named |= {rel for r in rows if r.get("state") == "pending" and r.get("op") not in committed
                      for rel in r.get("files") or {}}
            own = cdir.owned()
            out += [Finding("warn", "foreign-file", f"{_show(d / rel)} is not {d.name}'s own (its manifest "
                                                    f"does not list it); the connector leaves it untouched")
                    for rel in sorted(named - set(own)) if (d / rel).is_file()]
    return out


_RANK = {"error": 0, "warn": 1, "info": 2}


def _paths_yaml_finding(exc: ConfigError) -> Finding:
    """One line, like every other finding: the file under ~, the parser's first line, the hint."""
    msg = str(exc).replace(str(paths.paths_yaml()), "").lstrip(": ").splitlines()
    hint = f" — {exc.hint}" if exc.hint else ""
    return Finding("error", "paths-yaml", f"{_show(paths.paths_yaml())}: {msg[0] if msg else 'broken'}{hint}"
                                          "; checks below run without its places and sync:")


def _guarded(code: str, fn, *args) -> list[Finding]:
    """One check's failure is that check's finding; the others still run."""
    try:
        return fn(*args)
    except (ConfigError, OSError, UnicodeDecodeError, sqlite3.Error) as exc:
        return [Finding("warn", code, f"UNREADABLE: the check stopped ({type(exc).__name__}: "
                                    f"{(str(exc).splitlines() or [''])[0]})")]


def check() -> list[Finding]:
    try:
        cfg = paths.paths_config()
        broken: list[Finding] = []
    except ConfigError as exc:
        cfg, broken = paths.PathsConfig(), [_paths_yaml_finding(exc)]
    found = [*broken,
             *_guarded("secret-tracked", _secret_tracked), *_guarded("local-in-sync", _local_in_sync, cfg),
             *_guarded("perms", _perms), *_guarded("legacy-only", _legacy_only),
             *_guarded("sync-conflict", _sync_conflicts), *_guarded("unknown-root-entry", _unknown_root),
             *_guarded("index-schema", _index_schema), *_guarded("old-env-name", _old_env),
             *_guarded("place-missing", _places, cfg), *_guarded("config-backup", _config_backups),
             *_guarded("stale-temp", _stale_temps, cfg), *_guarded("foreign-file", _foreign_files, cfg),
             *_guarded("from-copies", _from_copies)]
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
