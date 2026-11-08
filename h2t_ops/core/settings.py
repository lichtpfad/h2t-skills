"""Every setting that names a path or an interface, with the place it comes from (#581).

One table. A key resolves env var -> file -> default, and says which one answered, so
`settings list` and doctor can show the source. A default is neutral (empty, off) or absent.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from h2t_ops.core import paths, secrets, user_config
from h2t_ops.core.errors import ConfigError, UsageError
from h2t_ops.lifecycle import index

Source = Literal["env", "file", "default", "unset"]


@dataclass(frozen=True)
class Key:
    name: str
    env: str | None
    file: str | None        # user.yaml, paths.yaml, repo-mapping.yaml, domains.yaml, EVALS_ENV
    file_key: str | None
    default: object = None  # None: no default, the key is unset


@dataclass(frozen=True)
class Resolved:
    value: object
    source: Source


EVALS_ENV = "h2t-evals.env"   # the evals provider file in secrets/shared

KEYS: tuple[Key, ...] = (
    # root, vault and the machine name have no file source, by construction: they are
    # computed (a callable default), and paths.py is the one reader of the path variables.
    Key("path.root", paths.env_var("root"), None, None, paths.root),
    Key("path.vault", paths.env_var("vault"), None, None, paths.vault),
    Key("path.lake", paths.env_var("lake"), "paths.yaml", "places.lake"),
    Key("path.inbox", paths.env_var("inbox"), "paths.yaml", "places.inbox"),
    Key("path.kb", paths.env_var("kb"), "paths.yaml", "places.kb"),
    Key("machine.name", "H2T_MACHINE_NAME", None, None, paths.machine_name),
    Key("github.owner", "H2T_GITHUB_OWNER", "user.yaml", "github.owner"),
    Key("notion.tasks_database_id", "H2T_NOTION_TASKS_DB", "user.yaml", "notion.tasks_database_id"),
    Key("notion.tasks_schema", None, "user.yaml", "notion.tasks_schema"),
    Key("evals.service_url", "H2T_EVALS_SERVICE_URL", EVALS_ENV, "H2T_EVALS_SERVICE_URL"),
    Key("repos", None, "repo-mapping.yaml", None, []),
    Key("domains", None, "domains.yaml", "domains", {}),
    Key("language", None, "user.yaml", "language", "en"),
    Key("timezone", None, "user.yaml", "timezone"),
    Key("guards", None, "user.yaml", "guards", []),
    Key("sessions.summaries", None, "user.yaml", "sessions.summaries", False),
    Key("domain_patterns", None, "user.yaml", "domain_patterns", []),
    Key("context.by_domain", None, "user.yaml", "context.by_domain", {}),
    Key("context.strategy", None, "user.yaml", "context.strategy"),
    Key("daily_brief.domains", None, "user.yaml", "daily_brief.domains", {}),
)


def _key(name: str) -> Key:
    for key in KEYS:
        if key.name == name:
            return key
    raise UsageError(f"unknown setting {name!r}", hint="h2t-ops settings list")


def _file_path(kind: str) -> Path:
    if kind == "user.yaml":
        return user_config.path()
    if kind == "paths.yaml":
        return paths.paths_yaml()
    if kind == EVALS_ENV:
        return secrets.provider_file(EVALS_ENV.removesuffix(".env"))
    return paths.config_dir() / kind


def _from_file(key: Key) -> object:
    if key.file == "user.yaml":
        return user_config.get(key.file_key)
    if key.file == "paths.yaml":
        return paths.paths_config().places.get(key.name.removeprefix("path."))
    if key.file == EVALS_ENV:
        return secrets.evals_env().get(key.file_key) or None
    if not _file_path(key.file).is_file():
        return None
    repo_mapping, domains = index.ontology()   # the one parser of these two files
    doc = repo_mapping if key.name == "repos" else domains.get(key.file_key)
    return doc or None


def resolve(name: str) -> Resolved:
    key = _key(name)
    raw = os.environ.get(key.env) if key.env else None
    if raw:
        # a path variable is read by paths, the one reader of them; the rest as written
        if name == "path.root":
            return Resolved(str(paths.root()), "env")
        if name == "path.vault":
            return Resolved(str(paths.vault()), "env")
        if name in ("path.lake", "path.inbox", "path.kb"):
            return Resolved(str(paths.place(name.removeprefix("path."))), "env")
        return Resolved(raw, "env")
    if key.file:
        found = _from_file(key)
        if found is not None:
            return Resolved(str(found) if key.file == "paths.yaml" else found, "file")
    if callable(key.default):
        return Resolved(str(key.default()), "default")
    return Resolved(key.default, "default" if key.default is not None else "unset")


def require(name: str) -> object:
    got = resolve(name)
    if got.source != "unset":
        return got.value
    key = _key(name)
    where = [f"set {key.env}"] if key.env else []
    if key.file and key.file_key:
        where.append(f"set {key.file_key} in {_file_path(key.file)}")
    raise ConfigError(f"{name} is not set", hint=" or ".join(where) or "h2t-ops settings list")


def rows() -> list[dict]:
    """Every key with value and source, for `settings list` and doctor. A key whose file
    cannot be read is shown with the reason, not raised: this is how the user finds it."""
    out = []
    for key in KEYS:
        try:
            got = resolve(key.name)
            out.append({"key": key.name, "value": got.value, "source": got.source})
        except ConfigError as exc:
            out.append({"key": key.name, "value": None, "source": "error", "error": str(exc)})
    return out
