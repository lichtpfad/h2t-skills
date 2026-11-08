"""Settings a machine relied on by default and has not set (#581).

`h2t-ops setup doctor` runs this before a removed default stops applying, so a machine learns
what it was using. Every detector reads the machine (files, the index, `gh`, `git`) and
changes nothing; suggestions are built from what was found, never from a literal.

gap     the key is unset and the machine holds a trace of using the removed default
info    normal on a fresh install; shown, never demanded
manual  a removed default that leaves no trace; shown with the key to set
"""
from __future__ import annotations

import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

from h2t_ops.core import paths, secrets, settings, store, user_config
from h2t_ops.core.errors import ConfigError

Runner = Callable[[list[str], int], dict[str, Any]]
Kind = Literal["gap", "info", "manual"]

GUARDS_WITH_LOG = ("grade", "plain")   # structure guard writes no log (structure_guard.py:364)
BOUND = 10   # seconds for one gh or git call


@dataclass(frozen=True)
class Gap:
    kind: Kind
    key: str
    evidence: str
    suggestion: str | None


def _unset(name: str) -> bool:
    """Neither the environment nor a file answered. A file that cannot be read is `error`
    in settings.rows and is not a gap here: its own row already says so."""
    try:
        return settings.resolve(name).source in ("unset", "default")
    except ConfigError:
        return False


def _value(name: str) -> object:
    try:
        return settings.resolve(name).value
    except ConfigError:
        return None


def _ok(result: dict[str, Any]) -> bool:
    return result.get("status") == "ok" and result.get("exit_code") == 0


def _model_summaries() -> bool:
    db = paths.state_dir() / "index.sqlite"
    if not db.is_file():
        return False
    try:   # store.read_sqlite is mode=ro: doctor must not create or touch the index
        with store.read_sqlite(db) as con:
            return con.execute(
                "SELECT 1 FROM sessions WHERE summary_source = 'model' LIMIT 1").fetchone() is not None
    except sqlite3.Error:
        return False


def _summaries() -> list[Gap]:
    if _unset("sessions.summaries") and _model_summaries():
        return [Gap("gap", "sessions.summaries", "the index holds session summaries written by the model",
                    f"sessions.summaries: true in {user_config.path()}")]
    return []


def _guards() -> list[Gap]:
    found = [name for name in GUARDS_WITH_LOG
             if (log := paths.logs_dir() / f"{name}-guard.jsonl").is_file() and log.stat().st_size > 0]
    if found and _unset("guards"):
        return [Gap("gap", "guards", f"guard logs exist for: {', '.join(found)}",
                    f"guards: [{', '.join(found)}] in {user_config.path()}")]
    return []


def _evals_url() -> list[Gap]:
    if secrets.get("H2T_EVALS_TOKEN") is not None and settings.resolve("evals.service_url").source == "unset":
        env_file = secrets.provider_file(settings.EVALS_ENV.removesuffix(".env"))
        return [Gap("gap", "evals.service_url",
                    "an evals token is set and was sent to the built-in service address",
                    f"add the line H2T_EVALS_SERVICE_URL=<your service> to {env_file}")]
    return []


def _legacy_secret_names() -> set[str]:
    """Names of the keys with a value in the two 3.x DOR secrets files. Values are dropped
    as they are read."""
    names: set[str] = set()
    for key in sorted(k for k in paths.DOR_KEYS if k.startswith("secrets.")):
        try:
            # diagnostic: reads .dor after migration on purpose, to report what it would lose
            text = paths.legacy(key).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        names |= {name for name, value in secrets.parse_env(text).items() if value}
    return names


def _dor_after_migration() -> list[Gap]:
    if not paths.migrated():
        return []
    out: list[Gap] = []
    missing = sorted(_legacy_secret_names() - set(secrets._new_values()))
    if missing:
        out.append(Gap("gap", "secrets", f"the 3.x secrets files hold {len(missing)} key(s) the new "
                       f"store lacks: {', '.join(missing)}",
                       f"add them as KEY=value lines to a file in {paths.secrets_shared()} "
                       f"(run `h2t-ops setup secrets skeleton` to see the layout)"))
    lake_key = next(k for k in sorted(paths.DOR_KEYS) if k.startswith("lake."))
    old = paths.legacy(lake_key)
    if old.is_dir() and _unset("path.lake"):
        out.append(Gap("gap", "path.lake", f"{old} exists and no lake place is declared",
                       f"run: h2t-ops paths set lake {old}"))
    return out


def _repos() -> list[Gap]:
    if not _value("repos"):
        return [Gap("info", "repos", "repo-mapping.yaml is empty or absent",
                    f"list your repositories in {paths.config_dir() / 'repo-mapping.yaml'}")]
    return []


def _github_owner(runner: Runner) -> list[Gap]:
    if not _unset("github.owner"):
        return []
    status = runner(["gh", "auth", "status"], BOUND)
    if not _ok(status):
        return []
    login = runner(["gh", "api", "user", "--jq", ".login"], BOUND)
    name = login.get("stdout", "").strip() if _ok(login) else ""
    if not name:
        return []
    accounts = status.get("stdout", "").count("Logged in to")
    evidence = "gh is logged in"
    if accounts > 1:
        evidence += f" ({accounts} accounts; the active one is suggested)"
    return [Gap("info", "github.owner", evidence, f"github.owner: {name}")]


def _git_user_name(runner: Runner) -> list[Gap]:
    got = runner(["git", "config", "user.name"], BOUND)
    if got.get("status") in ("ok", "error") and got.get("exit_code") in (0, 1) \
            and not got.get("stdout", "").strip():
        return [Gap("info", "git.user.name", "git has no user.name; documents fall back to no owner",
                    "git config --global user.name \"<your name>\"")]
    return []


def _context_files() -> list[Gap]:
    about = paths.config_dir() / "about-me"
    files = sorted(p.name for p in about.iterdir() if p.is_file()) if about.is_dir() else []
    if files and _unset("context.by_domain"):
        return [Gap("info", "context.by_domain", f"{about} holds: {', '.join(files)}",
                    "context.by_domain: {<domain>: about-me/<file>} in user.yaml")]
    return []


def _domain_patterns() -> list[Gap]:
    if _value("domains") and _unset("domain_patterns"):
        return [Gap("info", "domain_patterns", "domains.yaml declares domains and no patterns map repos to them",
                    "new repos will ask for a domain; domain_patterns: [...] in user.yaml maps them by name")]
    return []


def _manual() -> list[Gap]:
    chosen = _value("guards")
    out: list[Gap] = []
    if not (isinstance(chosen, list) and "structure" in chosen):
        out.append(Gap("manual", "guards", "the structure guard writes no log, so nothing shows it was on",
                       "guards: [structure]"))
    if _unset("language"):
        out.append(Gap("manual", "language", "the session language is no longer assumed",
                       "language: <code> in user.yaml"))
    if _unset("daily_brief.domains"):
        out.append(Gap("manual", "daily_brief.domains", "the daily brief has no built-in keyword groups",
                       "daily_brief: {domains: {<domain>: [<keyword>]}} in user.yaml"))
    out.append(Gap("manual", "REPO_EXTRA_DIRS", "extra directories per repository are no longer built in",
                   "declare them for the repositories that need them in repo-mapping.yaml"))
    return out


def gaps(runner: Runner | None = None) -> list[Gap]:
    if runner is None:
        from h2t_ops.setup.legacy import _run as runner
    detectors: list[Callable[[], list[Gap]]] = [
        _summaries, _guards, _evals_url, _dor_after_migration, _repos,
        lambda: _github_owner(runner), lambda: _git_user_name(runner),
        _context_files, _domain_patterns, _manual,
    ]
    out: list[Gap] = []
    for detect in detectors:
        try:   # one unreadable file must not hide the other findings
            out += detect()
        except (ConfigError, OSError, ValueError, sqlite3.Error):
            continue
    order = {"gap": 0, "info": 1, "manual": 2}
    return sorted(out, key=lambda g: order[g.kind])
