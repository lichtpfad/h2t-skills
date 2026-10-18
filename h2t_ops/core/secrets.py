"""The only reader of secrets (#548 §4, §7.2).

New places: ~/.h2t/secrets/shared/<provider>.env and provider-format files, and
secrets/local for what must not leave the machine. Through 4.0.x the 3.x ladder is read as
a fallback, per key: a key with a value in the new file is migrated and the legacy places are
not read for it, so a stale legacy value can never shadow it; a key absent or empty there
(the skeleton writes empty KEY= lines) still falls back. 4.1 deletes the fallback.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

from h2t_ops.core import paths, providers, store
from h2t_ops.core.errors import ConfigError, UsageError

_JSON = {"google.client": ("secrets.shared", "google.client.json"),
         "google.token": ("secrets.local", "google.token.json"),   # per machine (R19)
         "telegram.auth-state": ("secrets.local", "telegram.auth-state.json")}


def parse_env(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for raw in text.lstrip("\ufeff").splitlines():   # escaped: a literal BOM vanishes in copy-paste
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        if key.startswith("export "):
            key = key[len("export "):].strip()
        if key and key not in out:
            out[key] = val.strip().strip('"').strip("'")
    return out


def _read_env(path: Path) -> dict[str, str]:
    """An absent file is empty; an undecodable one raises, as in 3.x — swallowing it would
    turn a corrupt secrets file into a silent MISSING (doctor reports UNREADABLE, #451)."""
    try:
        return parse_env(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}


def provider_file(provider: str, *, local: bool = False) -> Path:
    base = paths.secrets_local() if local else paths.secrets_shared()
    return base / f"{provider}.env"


def legacy_sources() -> list[tuple[str, Path]]:
    """The 3.x ladder, in its order (core/secrets.py of 3.3.0 — #432, #483).

    H2T_SECRETS_FILE is not read any more (plan R5); the migration takes its file as one more
    source through paths.old_env_by_use("secrets-source") (Task 22)."""
    d = paths.legacy("secrets.h2t")
    out = [("h2t-config", d / "secrets.env")]
    if d.is_dir():
        out += [(f"h2t-config-{p.stem}", p) for p in sorted(d.glob("*.env"), key=lambda p: p.name)
                if p.name != "secrets.env"]
    return out + [("dor-secrets", paths.legacy("secrets.dor")), ("dor", paths.legacy("secrets.dor_old"))]


def candidate_secret_files(env_file: Path | None = None) -> list[Path]:
    """Files the package reads keys from: its providers' files and other.env, then the 3.x
    ladder. Foreign files in shared (getcourse.env, …) are not the package's to read (§4)."""
    if env_file is not None:
        return [env_file]
    shared = paths.secrets_shared()
    new = [shared / f"{p}.env" for p in sorted(providers.PROVIDERS)] + [shared / "other.env"]
    return [*(p for p in new if p.is_file()), *(p for _, p in legacy_sources())]


def _new_values() -> dict[str, str]:
    """Keys with a value in the new files; an empty KEY= is not a value (not migrated)."""
    out: dict[str, str] = {}
    shared = paths.secrets_shared()
    for provider in sorted(providers.PROVIDERS) + ["other"]:
        for key, val in _read_env(shared / f"{provider}.env").items():
            if val:
                out.setdefault(key, val)
    return out


def _merged(layers) -> dict[str, str]:
    """First non-empty value of each key across the layers, in their order."""
    out: dict[str, str] = {}
    for layer in layers:
        for key, val in layer.items():
            if val and key not in out:
                out[key] = val
    return out


def get(key: str) -> str | None:
    if os.environ.get(key):
        return os.environ[key]
    new = _new_values()
    if key in new:
        return new[key]
    for _, path in legacy_sources():
        val = _read_env(path).get(key)
        if val:
            return val
    return None


def load_secrets(env_file: Path | None = None) -> None:
    """Merge every known key into os.environ without overriding (3.x contract kept)."""
    if env_file is not None:
        merged = _read_env(env_file)
    else:
        merged = _merged([_new_values(), *(_read_env(p) for _, p in legacy_sources())])
    for key, val in merged.items():
        if key and key not in os.environ:
            os.environ[key] = val


def _legacy_json(name: str) -> list[Path]:
    if name == "google.client":
        return [paths.legacy("google.store") / "credentials.json",
                paths.legacy("google.gmail") / "credentials.json", paths.legacy("google.dor")]
    if name == "google.token":
        return [paths.legacy("google.store") / "tokens.json", paths.legacy("google.gmail") / "token.json"]
    if name == "telegram.auth-state":
        return [paths.legacy("telegram") / "auth_state.json"]
    raise KeyError(name)


def json_path(name: str) -> Path:
    place, file = _JSON[name]
    return paths.dir_of(place) / file


def read_json(name: str) -> tuple[dict | None, Path | None]:
    for path in (json_path(name), *_legacy_json(name)):
        if path.is_file():
            try:
                return json.loads(path.read_bytes().decode("utf-8-sig")), path
            except (ValueError, UnicodeDecodeError) as exc:
                raise ConfigError(f"{path} is not valid JSON: {exc}", hint="re-save it as UTF-8 JSON") from exc
    return None, None


def telegram_legacy_config(config_dir: Path | None = None) -> dict | None:
    """api_id/api_hash from the 3.x ~/.config/telegram/config.json (fallback in 4.0.x), or from
    <config_dir>/config.json when the caller names its own directory (Task 9, R42).

    Read with jsonfile.read_json_config, as 3.x did: BOM-tolerant, line numbers in errors."""
    from h2t_ops.core.jsonfile import read_json_config
    path = (Path(config_dir) if config_dir is not None else paths.legacy("telegram")) / "config.json"
    return read_json_config(path) if path.is_file() else None


def read_json_at(path: Path, *, root: Path) -> dict | None:
    """A secret JSON file in a directory the caller names explicitly (config_dir=); None if absent."""
    if not Path(path).is_file():
        return None
    raw = read_secret_bytes(path, root=root)
    try:
        return json.loads(raw.decode("utf-8-sig"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise ConfigError(f"{path} is not valid JSON: {exc}", hint="re-save it as UTF-8 JSON") from exc


def write_json(name: str, data: dict) -> Path:
    place, _ = _JSON[name]
    return store.replace(json_path(name), json.dumps(data, ensure_ascii=False, indent=2), place=place,
                         keys=tuple(data))       # field names only (R41)


_KEY = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _check_env(provider: str, values: dict[str, str]) -> None:
    """The §4 contract, so a write never lands a file _new_values() would not read: a package
    provider (or other.env), keys named <PROVIDER>_<WHAT>, one line per value."""
    if provider != "other" and not providers.is_package_provider(provider):
        raise UsageError(f"{provider!r} is not a provider of this package",
                         hint=f"one of: {', '.join(sorted(providers.PROVIDERS))}, or other")
    prefix = providers.key_prefix(provider)
    for key, val in values.items():
        if not _KEY.match(key) or (provider != "other" and not key.startswith(prefix)):
            raise UsageError(f"key {key!r} does not belong in {provider}.env",
                             hint=f"keys there are named {prefix}<WHAT>" if provider != "other"
                             else "a key is letters, digits and _")
        if "\n" in val or "\r" in val:
            raise UsageError(f"the value of {key} spans lines", hint="one line per value")


def write_env(provider: str, values: dict[str, str], *, local: bool = False) -> Path:
    _check_env(provider, values)
    body = "".join(f"{k}={v}\n" for k, v in values.items())
    return store.replace(provider_file(provider, local=local), body,
                         place="secrets.local" if local else "secrets.shared", keys=tuple(values))


def evals_env(env_file: Path | None = None) -> dict[str, str]:
    """Every H2T_EVALS_* key, by prefix as in 3.x — no list of keys to drop one silently —
    except the 3.x path variables, which the package does not read (Q8).

    Per key: environment, then h2t-evals.env, then ~/.dor/secrets.env (where 3.x read them),
    then the rest of the ladder. env_file: only that file and the environment."""
    prefix = providers.key_prefix("h2t-evals")
    if env_file is not None:
        layers = [_read_env(Path(env_file))]
    else:
        layers = [_read_env(provider_file("h2t-evals")), _read_env(paths.legacy("secrets.dor_old")),
                  *(_read_env(p) for name, p in legacy_sources() if name != "dor")]
    merged = _merged([dict(os.environ), *layers])
    return {k: v for k, v in merged.items() if k.startswith(prefix) and k not in paths.OLD_ENV}


def notion_legacy_token() -> str | None:
    cfg = paths.legacy("notion.token")
    if not cfg.is_file():
        return None
    return cfg.read_text(encoding="utf-8").strip() or None


def resolve_notion_token() -> str:
    tok = get("NOTION_API_TOKEN") or notion_legacy_token()
    if tok:
        return tok
    raise ConfigError("Notion API token not found.",
                      hint=f"Set NOTION_API_TOKEN in {provider_file('notion')}")


# --- readers for the migration (plan R38): it reads secrets only through these -------------

def _read_env_named(path: Path) -> dict[str, str]:
    """_read_env for the migration: an undecodable file stops it with the file's name — a
    source silently dropped would be a value lost without a word."""
    try:
        return _read_env(path)
    except UnicodeDecodeError as exc:
        raise ConfigError(f"{path} is not UTF-8 text ({exc.reason} at byte {exc.start})",
                          hint="re-save it as UTF-8 and run `h2t-setup layout migrate` again") from exc


_SECRET_LEGACY = ("secrets.h2t", "secrets.dor", "secrets.dor_old", "notion.token",
                  "google.store", "google.gmail", "google.dor", "telegram")


def migration_sources() -> list[tuple[str, Path, dict[str, str]]]:
    """Senior first: the 3.x H2T_SECRETS_FILE file once, then the 3.x ladder. A file that
    appears twice (the variable pointing at a ladder file) counts once, at its senior place."""
    out = [("secretsfile", p) for p in paths.old_env_by_use("secrets-source").values()]
    out += legacy_sources()
    seen: set[str] = set()
    result = []
    for name, p in out:
        real = os.path.realpath(p)
        if p.is_file() and real not in seen:
            seen.add(real)
            result.append((name, p, _read_env_named(p)))
    return result


# A .from- copy, and the numbered one store.unique_name gives on a second clash:
# meetgeek.env.from-dor, then meetgeek.env-2.from-dor (stem + -N + suffix).
ENV_COPY = re.compile(r"\.env(-\d+)?\.from-")


def shared_env_values() -> dict[str, dict[str, str]]:
    shared = paths.secrets_shared()
    if not shared.is_dir():
        return {}
    return {p.name: _read_env_named(p) for p in sorted(shared.iterdir())
            if p.name.endswith(".env") or ENV_COPY.search(p.name)}


def read_secret_bytes(path: Path, *, root: Path | None = None) -> bytes:
    """root: a directory the user named explicitly (--secrets-dir, config_dir=) — the only
    other place a secret may be read from; without it, secrets/ and the 3.x secret places."""
    real = Path(os.path.realpath(path))
    roots = ([Path(root)] if root is not None
             else [paths.root() / "secrets", *(paths.legacy(n) for n in _SECRET_LEGACY)])
    if not any(real == Path(os.path.realpath(r)) or Path(os.path.realpath(r)) in real.parents
               for r in roots):
        raise ConfigError(f"{path} is not a secrets location", hint="read it through its own module")
    return real.read_bytes()
