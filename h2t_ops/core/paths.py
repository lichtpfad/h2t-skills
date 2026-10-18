"""Where every class of data lives — the only module that knows (#548 §3, §6, §7.2).

The target boundary: nothing else in h2t_ops calls Path.home() or expanduser, reads
H2T_PATH_ROOT, H2T_PATH_VAULT or the 3.x variable names, or spells ~/.dor or
~/.config/<program>. Code outside still does; the ratchets in tests/governance count it and
hold the count from rising until it reaches zero (Task 24).
"""
from __future__ import annotations

import json
import os
import platform
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from h2t_ops.core.errors import ConfigError


@dataclass(frozen=True)
class Place:
    id: str
    kind: str   # fixed | class | place | file
    cls: str    # run | config | secrets | records | data | state | logs | external | root
    sync: str   # never | user | owner


PLACES: tuple[Place, ...] = (
    Place("run", "fixed", "run", "never"),
    Place("config", "class", "config", "user"),
    Place("secrets.shared", "class", "secrets", "user"),
    Place("secrets.local", "class", "secrets", "never"),
    Place("records.sessions", "class", "records", "user"),
    Place("records.activity", "class", "records", "user"),
    Place("records.evals", "class", "records", "user"),
    Place("records.imports", "class", "records", "user"),
    Place("data", "class", "data", "user"),
    Place("state", "class", "state", "never"),
    Place("logs", "class", "logs", "never"),
    Place("lake", "place", "external", "owner"),
    Place("inbox", "place", "external", "owner"),
    Place("vault", "place", "external", "owner"),
    Place("kb", "place", "external", "owner"),
    Place("repo", "place", "external", "owner"),
    Place("harness", "place", "external", "owner"),
    Place("tmp", "place", "external", "never"),
    Place("layout", "file", "root", "never"),
)
_BY_ID = {p.id: p for p in PLACES}
EXTERNAL = ("lake", "inbox", "vault", "kb")
YAML_PLACES = ("lake", "inbox", "kb")   # vault comes from H2T_PATH_VAULT (§6 п. 5)

# 3.x variable names. 4.0 does not read them for paths (§6 п. 5); migration and doctor do,
# to say what became of each: an external place the migration writes into paths.yaml, one
# more secrets source for the migration, or a variable to remove.
OLD_ENV: dict[str, str] = {
    "H2T_LAKE_ROOT": "lake",
    "H2T_SECRETS_FILE": "secrets-source",
    "H2T_CONFIG_ROOT": "remove",
    "H2T_SESSION_ROOT": "remove",
    "H2T_ACTIVITY_SPOOL": "remove",
    "H2T_EVALS_ROOT": "remove",
    "H2T_EVALS_SPOOL": "evals-spool-source",   # the migration copies that spool (plan R22)
}

# Where 3.x looked when a "remove" variable was not set. The migration copies only from
# these; a variable that moved its data elsewhere stops it (§6 п. 5, §8).
OLD_ENV_DEFAULT: dict[str, tuple[str, ...]] = {
    "H2T_CONFIG_ROOT": (".h2t", "config"),
    "H2T_SESSION_ROOT": (".h2t", "sessions"),
    "H2T_ACTIVITY_SPOOL": (".h2t", "activity", "spool.jsonl"),
    "H2T_EVALS_ROOT": (".h2t", "evals"),
}

# Where 3.x kept things. Read for migration and fallback in 4.0.x; never written except
# the Google mirror and MOVED-TO.txt (§7.3). ~/.dor/vault is not here: it is the vault's
# default address, shared with POS (plan R12).
LEGACY: dict[str, tuple[str, ...]] = {
    "secrets.h2t": (".h2t", "config", "secrets"),
    "secrets.dor": (".dor", "secrets", "secrets.env"),
    "secrets.dor_old": (".dor", "secrets.env"),
    "notion.token": (".config", "notion", "token"),
    "google.store": (".config", "google-calendar-mcp"),
    "google.gmail": (".config", "gmail"),
    "google.dor": (".dor", "google-credentials.json"),
    "telegram": (".config", "telegram"),
    "sessions.h2t": (".h2t", "sessions"),
    "sessions.dor": (".dor", "sessions"),
    "activity": (".h2t", "activity"),
    "evals": (".h2t", "evals"),
    "research": (".h2t", "research"),
    "creative": (".h2t", "creative", "profiles"),
    "registry.dor": (".dor", "registry.jsonl"),
    "lake.dor": (".dor", "lake"),
    "downloads": ("Downloads",),
}


# 3.x entries in the ~/.h2t root that are not data and have no new place: the pre-#449
# venv of the bare `h2t` shim (setup.legacy.legacy_shim_status). doctor knows them.
ROOT_3X = ("venv",)


def home() -> Path:
    return Path.home()


def _env(name: str) -> Path | None:
    value = os.environ.get(name)
    return Path(value).expanduser() if value else None


def root() -> Path:
    return _env("H2T_PATH_ROOT") or home() / ".h2t"


def run_dir() -> Path:
    """Fixed by the 4.0 install contract: hooks/run reads $HOME/.h2t/run in bash."""
    return home() / ".h2t" / "run"


def vault() -> Path:
    """The vault POS owns; its address is a contract between the two programs (plan R12)."""
    return _env("H2T_PATH_VAULT") or home() / ".dor" / "vault"


VAULT_HINT = "vault is shared with POS: set H2T_PATH_VAULT (default ~/.dor/vault)"


def source(place_id: str) -> str:
    """What decides a place's path, for `h2t-ops paths list`: the variable that moved it,
    or default. Places paths.yaml declares are answered by the caller, which has the file."""
    p = _BY_ID[place_id]
    if p.kind == "fixed":
        return "default (the install contract; H2T_PATH_ROOT does not move it)"
    name = "H2T_PATH_ROOT" if p.kind in ("class", "file") else \
        {"vault": "H2T_PATH_VAULT", "harness": "CLAUDE_CONFIG_DIR"}.get(place_id)
    return name if name and os.environ.get(name) else "default"


def dir_of(place_id: str) -> Path:
    p = _BY_ID[place_id]
    if p.kind == "fixed":
        return run_dir()
    if p.kind == "file":
        return layout_file()
    if p.kind == "class":
        cls, _, sub = place_id.partition(".")
        return root() / cls / sub if sub else root() / cls
    if place_id == "vault":
        return vault()
    if place_id == "harness":
        return _env("CLAUDE_CONFIG_DIR") or home() / ".claude"
    if place_id == "tmp":
        return Path(tempfile.gettempdir())
    if place_id == "repo":
        raise ValueError("repo has no fixed directory; pass the repository root to store.repo()")
    found = place(place_id)
    if found is None:
        raise ConfigError(f"place {place_id!r} is not set",
                          hint=f"h2t-ops paths set {place_id} <path>")
    return found


def config_dir() -> Path:
    return dir_of("config")


def secrets_shared() -> Path:
    return dir_of("secrets.shared")


def secrets_local() -> Path:
    return dir_of("secrets.local")


def state_dir() -> Path:
    return dir_of("state")


def logs_dir() -> Path:
    return dir_of("logs")


def data_dir() -> Path:
    return dir_of("data")


def layout_file() -> Path:
    return root() / "layout.json"


def paths_yaml() -> Path:
    return config_dir() / "paths.yaml"


def backups_dir() -> Path:
    return state_dir() / "backups"


def records(kind: str, machine: str | None = None) -> Path:
    base = dir_of(f"records.{kind}")
    return base / machine if machine else base


def activity_file(machine: str) -> Path:
    return records("activity") / f"{machine}.jsonl"


def evals_spool() -> Path:
    return state_dir() / "evals-spool.sqlite"


def old_env(name: str) -> Path | None:
    """A 3.x variable's value, for the migration and doctor only — never a path to use."""
    if name not in OLD_ENV:
        raise KeyError(name)
    return _env(name)


def old_env_in_use() -> list[str]:
    return sorted(n for n in OLD_ENV if os.environ.get(n))


def old_env_by_use(use: str) -> dict[str, Path]:
    """Set 3.x variables with this OLD_ENV use: callers never spell the old names (plan R22)."""
    return {n: _env(n) for n in old_env_in_use() if OLD_ENV[n] == use}



def old_env_moved() -> dict[str, tuple[Path, Path]]:
    """Set "remove" variables that name an existing place other than their 3.x default:
    name -> (value, default). Their data is where the migration does not look."""
    out: dict[str, tuple[Path, Path]] = {}
    for name, value in old_env_by_use("remove").items():
        default = home().joinpath(*OLD_ENV_DEFAULT[name])
        if value.exists() and os.path.realpath(value) != os.path.realpath(default):
            out[name] = (value, default)
    return out

@dataclass
class PathsConfig:
    places: dict[str, Path] = field(default_factory=dict)
    vault_rules: Path | None = None
    sync: dict[str, str] = field(default_factory=dict)


def _inside(a: Path, b: Path) -> bool:
    return a == b or b in a.parents


def paths_config() -> PathsConfig:
    f = paths_yaml()
    if not f.is_file():
        # No file declares a place, but the vault still comes from H2T_PATH_VAULT and may
        # overlap the root: the same check as with the file (§6 п. 4).
        return validate_config({}, source=f)
    try:
        doc = yaml.safe_load(f.read_bytes().decode("utf-8-sig")) or {}
    except UnicodeDecodeError as exc:
        raise ConfigError(f"{f} is not UTF-8: {exc}", hint="save the file as UTF-8") from exc
    except yaml.YAMLError as exc:
        raise ConfigError(f"{f} is not valid YAML: {exc}", hint="fix the file or remove it") from exc
    return validate_config(doc, source=f)


def _mapping(doc: dict, key: str, f: Path) -> dict:
    """An absent or empty (null) key is an empty mapping; any other non-mapping is an error,
    so a broken file surfaces as ConfigError, which _declared() tolerates (plan R17)."""
    value = doc.get(key)
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ConfigError(f"{f}: {key} must be a mapping, got {type(value).__name__}",
                          hint=f"{key}:\n  <name>: <value>")
    return value


def validate_config(doc: dict, *, source: Path) -> PathsConfig:
    """Every paths.yaml check, on a document in memory: `paths set` validates the new
    document while the file on disk may still be broken (plan R34)."""
    f = source
    if not isinstance(doc, dict):
        raise ConfigError(f"{f}: expected a mapping at the top", hint="version: 1 and a places: mapping")
    if doc.get("version", 1) != 1:
        raise ConfigError(f"{f}: version {doc.get('version')!r} is not supported", hint="version: 1")
    places: dict[str, Path] = {}
    for name, raw in _mapping(doc, "places", f).items():
        if name == "vault":
            raise ConfigError(f"{f}: vault is not set here; it comes from H2T_PATH_VAULT",
                              hint=VAULT_HINT)
        if name not in YAML_PLACES:
            raise ConfigError(f"{f}: unknown place {name!r}", hint=f"places are {', '.join(YAML_PLACES)}")
        value = Path(str(raw)).expanduser()
        if not value.is_absolute():
            raise ConfigError(f"{f}: place {name!r} must be an absolute path, got {raw!r}",
                              hint="use ~/… or a full path")
        places[name] = value
    real = {k: Path(os.path.realpath(v)) for k, v in {**places, "vault": vault()}.items()}
    h2t = Path(os.path.realpath(root()))
    for name, p in real.items():
        if _inside(p, h2t) or _inside(h2t, p):
            raise ConfigError(f"{f}: place {name!r} ({p}) overlaps the h2t root {h2t}",
                              hint="external places live outside ~/.h2t")
    names = list(real)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            if _inside(real[a], real[b]) or _inside(real[b], real[a]):
                raise ConfigError(f"{f}: places {a!r} and {b!r} overlap ({real[a]}, {real[b]})",
                                  hint="no place may lie inside another")
    rules = doc.get("vault_rules")
    return PathsConfig(places=places,
                       vault_rules=Path(str(rules)).expanduser() if rules else None,
                       sync={str(k): str(v) for k, v in _mapping(doc, "sync", f).items()})


def _layout() -> object:
    try:
        doc = json.loads(layout_file().read_bytes())
    except (OSError, ValueError):
        return None
    return doc.get("layout") if isinstance(doc, dict) else None


def _fallback(name: str) -> Path | None:
    """Before layout 1 the 3.x lake is the lake (§8: 4.0.x works on the old places until the
    machine migrates). A default of data/lake there would take granola and meetgeek sync
    away from the lake POS reads while their cursors advance, and the notes synced in that
    window would never be fetched again. After layout 1 only paths.yaml declares it (R2)."""
    if name != "lake" or _layout() == 1:
        return None
    old = legacy("lake.dor")
    return old if old.is_dir() else None


def place(name: str) -> Path | None:
    if name == "vault":
        return vault()
    found = paths_config().places.get(name)
    return found if found is not None else _fallback(name)


def place_or_default(name: str) -> tuple[Path, bool]:
    found = place(name)
    return (found, False) if found is not None else (data_dir() / name, True)


def legacy(name: str) -> Path:
    return home().joinpath(*LEGACY[name])


LEGACY_FILES = frozenset({"secrets.dor", "secrets.dor_old", "notion.token", "google.dor", "registry.dor"})


def legacy_dir(name: str) -> Path:
    """The directory a legacy entry lives in: itself, or its parent for a file entry."""
    p = legacy(name)
    return p.parent if name in LEGACY_FILES else p


def _declared() -> set[Path]:
    """Real paths of the external places, tolerant of a broken paths.yaml (plan R17)."""
    try:
        places = paths_config().places
    except ConfigError:
        places = {}
    found = [*places.values(), vault()]
    if "lake" not in places and (old := _fallback("lake")) is not None:
        found.append(old)
    return {Path(os.path.realpath(p)) for p in found}


def legacy_roots() -> list[Path]:
    """Roots that classify a write as legacy. For a file entry the root is its directory, so
    MOVED-TO.txt next to ~/.dor/secrets.env classifies as legacy too. A legacy root that is
    also a declared place (lake: ~/.dor/lake by R2) is that place, not legacy — decided here,
    not by the sort order in store._roots."""
    declared = _declared()
    out: list[Path] = []
    for n in LEGACY:
        if n == "downloads":
            continue
        d = legacy_dir(n)
        if Path(os.path.realpath(d)) not in declared and d not in out:
            out.append(d)
    return out


def home_form(p: Path) -> str:
    """A path as paths.yaml stores it: ~/… under home, so the file reads the same on every
    machine config/ syncs to (another user name, a Windows home); a full path otherwise.
    validate_config expands the ~ on each machine."""
    p, h = Path(p), home()
    if _inside(p, h) and p != h:
        return "~/" + p.relative_to(h).as_posix()
    return str(p)


def expand_user_dest(value: str) -> Path:
    return Path(value).expanduser().absolute()


def machine_name() -> str:
    """H2T_MACHINE_NAME (pinned in Claude settings by setup, ADR 0003) → DOR_MACHINE_NAME →
    hostname. No file pins it (plan R4)."""
    name = os.environ.get("H2T_MACHINE_NAME") or os.environ.get("DOR_MACHINE_NAME", "")
    return name or platform.node().lower().split(".")[0]
