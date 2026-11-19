"""accounts.yaml and rules.yaml of the social connector. Token values never live here."""
from __future__ import annotations

import re
from dataclasses import dataclass
from importlib import resources
from pathlib import Path

import yaml

from h2t_ops.core import paths, providers, settings
from h2t_ops.core.errors import ConfigError

NETWORKS = ("instagram", "facebook", "threads")
VERDICTS = ("auto", "ask", "deny")
_API_KEY = {"meta": "meta_graph", "instagram": "meta_graph", "facebook": "meta_graph",
            "threads": "threads_graph"}
_TOKEN_VALUE = re.compile(r"^(EAA|THAA|IGAA)[A-Za-z0-9]{20,}")
_TOKEN_NAMES = ("token", "access_token")


@dataclass(frozen=True)
class Account:
    id: str
    network: str
    handle: str
    remote_id: str
    page_id: str | None
    token_key: str
    project: str | None
    enabled: bool


@dataclass(frozen=True)
class Rule:
    id: str
    process: str
    action: str
    account: str
    kind: str
    verdict: str
    added: str
    origin: str


def accounts_path() -> Path:
    return paths.config_dir() / "social" / "accounts.yaml"


def rules_path() -> Path:
    return paths.config_dir() / "social" / "rules.yaml"


def _scan(node, f: Path, where: str) -> None:
    """Refuse a token key or a token-shaped value anywhere inside `node`."""
    if isinstance(node, dict):
        for k, v in node.items():
            if k in _TOKEN_NAMES:
                raise ConfigError(f"{f}: {where}: `{k}` holds a token; keep only the secret key name "
                                  "in `token_key`")
            _scan(v, f, f"{where}.{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            _scan(v, f, f"{where}[{i}]")
    elif isinstance(node, str) and _TOKEN_VALUE.match(node):
        raise ConfigError(f"{f}: {where}: a token value is written in the file; keep only the "
                          "secret key name in `token_key`")


def _read(f: Path, entries_key: str, label) -> dict | None:
    try:
        text = f.read_text(encoding="utf-8-sig")
    except FileNotFoundError:
        return None
    try:
        doc = yaml.safe_load(text) or {}
    except yaml.YAMLError as e:
        raise ConfigError(f"{f}: not valid YAML: {e}") from e
    if not isinstance(doc, dict):
        raise ConfigError(f"{f}: top level must be a mapping")
    for k, v in doc.items():
        if k == entries_key and isinstance(v, list):
            for e in v:
                _scan(e, f, label(e) if isinstance(e, dict) else entries_key)
        else:
            _scan(v, f, k)
    return doc


def _entries(doc: dict, key: str, f: Path) -> list[dict]:
    items = doc.get(key) or []
    if not isinstance(items, list) or not all(isinstance(i, dict) for i in items):
        raise ConfigError(f"{f}: `{key}` must be a list of mappings")
    return items


def _project_ids() -> set[str]:
    domains = settings.resolve("domains").value or {}
    ids = set(domains)
    for data in domains.values():
        for proj in (data or {}).get("projects") or []:
            if isinstance(proj, dict) and proj.get("id"):
                ids.add(str(proj["id"]))
    return ids


def load_accounts() -> list[Account]:
    f = accounts_path()
    doc = _read(f, "accounts", lambda e: f"account {e.get('network')}:{e.get('handle')}")
    if doc is None:
        raise ConfigError(f"no accounts file: {f}", hint="run `h2t-ops social accounts discover`")
    known = _project_ids()
    out = []
    for e in _entries(doc, "accounts", f):
        who = f"{e.get('network')}:{e.get('handle')}"
        if e.get("network") not in NETWORKS:
            raise ConfigError(f"{f}: account {who}: network must be one of {', '.join(NETWORKS)}")
        for k in ("handle", "remote_id", "token_key"):
            if not e.get(k):
                raise ConfigError(f"{f}: account {who}: `{k}` is required")
        if providers.provider_of_key(str(e["token_key"])) not in ("meta", "threads"):
            raise ConfigError(f"{f}: account {who}: token_key {e['token_key']!r} has no META_ or "
                              "THREADS_ prefix")
        project = e.get("project")
        if project and known and project not in known:
            raise ConfigError(f"{f}: account {who}: unknown project {project!r}")
        enabled = e.get("enabled", True)
        if not isinstance(enabled, bool):
            raise ConfigError(f"{f}: account {who}: `enabled` must be true or false, got {enabled!r}")
        out.append(Account(
            id=who, network=e["network"], handle=str(e["handle"]), remote_id=str(e["remote_id"]),
            page_id=str(e["page_id"]) if e.get("page_id") else None, token_key=str(e["token_key"]),
            project=project or None, enabled=enabled))
    return out


def load_rules() -> list[Rule]:
    f = rules_path()
    doc = _read(f, "rules", lambda e: f"rule {e.get('id') or '?'}")
    if doc is None:
        return []
    out = []
    for e in _entries(doc, "rules", f):
        rid = e.get("id")
        for k in ("id", "process", "action", "verdict", "added", "origin"):
            if not e.get(k):
                raise ConfigError(f"{f}: rule {rid or '?'}: `{k}` is required"
                                  + (" (a rule needs the example it came from)" if k == "origin" else ""))
        if e["verdict"] not in VERDICTS:
            raise ConfigError(f"{f}: rule {rid}: verdict must be one of {', '.join(VERDICTS)}")
        out.append(Rule(id=str(rid), process=str(e["process"]), action=str(e["action"]),
                        account=str(e.get("account") or "*"), kind=str(e.get("kind") or "*"),
                        verdict=e["verdict"], added=str(e["added"]), origin=str(e["origin"])))
    return out


def api_base(network: str) -> str:
    key = _API_KEY.get(network)
    if key is None:
        raise ConfigError(f"unknown network {network!r}; expected one of {', '.join(_API_KEY)}")
    f = accounts_path()
    api = (_read(f, "accounts", lambda e: "account") or {}).get("api") or {}
    if not isinstance(api, dict):
        raise ConfigError(f"{f}: `api` must be a mapping")
    override = api.get(key)
    if override is not None:
        if not isinstance(override, str) or not override:
            raise ConfigError(f"{f}: api.{key} must be a non-empty string")
        return override
    text = (resources.files("h2t_ops.resources") / "social" / "defaults.yaml").read_text(encoding="utf-8-sig")
    return yaml.safe_load(text)["api"][key]
