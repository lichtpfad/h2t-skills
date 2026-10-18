"""Deterministic h2t-core setup/update backend, run as `h2t-ops setup <verb>`.

Copied from plugins/h2t-core/skills/setup/scripts/setup_h2t.py in Task 12 so the setup
skill calls a command instead of a plugin script; parity with the original is held by
tests/tools/test_tool_copy_parity.py until 12c deletes it. `h2t-setup sync` (Task 14)
supersedes it. The note below is the original's and describes the plugin copy.

This script is intentionally standalone: it must run from an installed plugin
cache before POS/DOR is configured. POS/DOR paths are inspected only as optional
state and never treated as setup prerequisites.
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import platform
import re
import shlex
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from h2t_ops.core import paths, store

KIND_DOCTOR = "h2t_setup_doctor/v1"
KIND_CONNECTORS = "h2t_connectors_check/v1"
KIND_INSTALL = "h2t_ops_install/v1"
KIND_SECRETS_SKELETON = "h2t_secrets_skeleton/v1"
KIND_SECRETS_PREFLIGHT = "h2t_secrets_preflight/v1"
CANONICAL_H2T_OPS_SOURCE = "git+https://github.com/lichtpfad/h2t-skills.git"
SECRET_KEYS = {
    "notion": ["NOTION_API_TOKEN"],
    "meetgeek": ["MEETGEEK_API_KEY"],
    "granola": ["GRANOLA_API_KEY"],
    "research": ["EXA_API_KEY"],
}

Runner = Callable[[list[str], int], dict[str, Any]]


def _semver_key(name: str) -> tuple[int, int, int]:
    parts = name.split(".")
    try:
        return tuple(int(p) for p in parts[:3]) + (0,) * (3 - len(parts[:3]))
    except ValueError:
        return (0, 0, 0)


def detect_platform() -> dict[str, str]:
    raw = sys.platform
    if raw.startswith("win"):
        name = "windows"
    elif raw == "darwin":
        name = "macos"
    elif raw.startswith("linux"):
        name = "linux"
    else:
        name = raw
    return {
        "name": name,
        "sys_platform": raw,
        "machine": platform.machine(),
        "python": sys.executable,
        "python_version": platform.python_version(),
    }


def _path_exists(path: Path) -> bool:
    try:
        return path.exists()
    except OSError:
        return False


def _home() -> Path:
    return paths.home()


def _windows_uv_candidates(home: Path) -> list[Path]:
    local = os.environ.get("LOCALAPPDATA")
    candidates: list[Path] = []
    if local:
        candidates.append(Path(local) / "Microsoft" / "WinGet" / "Links" / "uv.exe")
        winget = Path(local) / "Microsoft" / "WinGet" / "Packages"
        if _path_exists(winget):
            candidates.extend(sorted(winget.glob("astral-sh.uv_*/*/uv.exe")))
            candidates.extend(sorted(winget.glob("astral-sh.uv_*/*/*/uv.exe")))
            candidates.extend(sorted(winget.glob("astral-sh.uv_*/uv.exe")))
    candidates.append(home / ".local" / "bin" / "uv.exe")
    return candidates


def _user_which(name: str) -> str | None:
    """shutil.which over PATH minus the bin directory of the venv running this script (#523).

    `uv run` started inside a checkout picks up the repo's .venv and puts its bin first on
    PATH, so the doctor reported that venv's h2t-ops, not the one `uv tool install` replaces.
    """
    if sys.prefix == sys.base_prefix:
        return shutil.which(name)
    own = os.path.normcase(os.path.realpath(Path(sys.prefix) / ("Scripts" if sys.platform.startswith("win") else "bin")))
    entries = [e for e in os.environ.get("PATH", "").split(os.pathsep) if e and os.path.normcase(os.path.realpath(e)) != own]
    return shutil.which(name, path=os.pathsep.join(entries))


def resolve_uv(which: Callable[[str], str | None] = shutil.which, home: Path | None = None) -> dict[str, Any]:
    home = home or _home()
    names = ["uv.exe", "uv"] if sys.platform.startswith("win") else ["uv", "uv.exe"]
    for name in names:
        found = which(name)
        if found:
            return {"status": "ready", "path": found, "source": "PATH"}
    if sys.platform.startswith("win"):
        for candidate in _windows_uv_candidates(home):
            if candidate.is_file():
                return {"status": "ready", "path": str(candidate), "source": "known-windows-path"}
    return {
        "status": "missing",
        "path": "",
        "source": "not-found",
        "hint": "Install uv: https://docs.astral.sh/uv/getting-started/installation/",
    }


ENTRY_POINT_NAMES = ["h2t-ops", "h2t-gather", "h2t-activity-log", "h2t-handoff"]


def _resolve_cli(name: str, which: Callable[[str], str | None] = _user_which, home: Path | None = None) -> dict[str, Any]:
    home = home or _home()
    is_win = sys.platform.startswith("win")
    names = [f"{name}.exe", name] if is_win else [name, f"{name}.exe"]
    for n in names:
        found = which(n)
        if found:
            return {"status": "ready", "path": found, "source": "PATH"}
    candidate = home / ".local" / "bin" / (f"{name}.exe" if is_win else name)
    if candidate.is_file():
        return {"status": "ready", "path": str(candidate), "source": "local-bin"}
    return {"status": "missing", "path": "", "source": "not-found"}


def _install_hint() -> str:
    """What to run when the CLI is missing: something that does not need the CLI.

    The hint used to name `install-h2t-ops`, a subcommand of the very tool that is missing.
    A release carries its bootstrap in _release.py (scripts/release.py writes it); a checkout
    has none, and gets the two ways that work there.
    """
    from h2t_ops.setup import _release

    if _release.BOOTSTRAP_COMMAND:
        return f"Run: {_release.BOOTSTRAP_COMMAND} sync"
    return "Run /h2t-core:setup, or from a developer checkout: `uv run h2t-setup dev-sync`"


def resolve_h2t_ops(which: Callable[[str], str | None] = _user_which, home: Path | None = None) -> dict[str, Any]:
    result = _resolve_cli("h2t-ops", which, home)
    if result["status"] == "missing":
        result["hint"] = _install_hint()
    return result


def resolve_entry_points(which: Callable[[str], str | None] = _user_which, home: Path | None = None) -> dict[str, Any]:
    commands = {name: _resolve_cli(name, which, home) for name in ENTRY_POINT_NAMES}
    statuses = [v["status"] for v in commands.values()]
    if all(s == "ready" for s in statuses):
        overall = "ready"
    elif any(s == "ready" for s in statuses):
        overall = "partial"
    else:
        overall = "missing"
    result: dict[str, Any] = {"status": overall, "commands": commands}
    if overall != "ready":
        result["hint"] = _install_hint()
    return result


def _run(args: list[str], timeout: int = 15) -> dict[str, Any]:
    try:
        proc = subprocess.run(
            args,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as exc:
        return {"status": "missing", "exit_code": 127, "stdout": "", "stderr": str(exc)}
    except subprocess.TimeoutExpired as exc:
        return {
            "status": "timeout",
            "exit_code": 124,
            "stdout": (exc.stdout or "")[:2000],
            "stderr": (exc.stderr or "")[:2000],
        }
    return {
        "status": "ok" if proc.returncode == 0 else "error",
        "exit_code": proc.returncode,
        "stdout": proc.stdout[:4000],
        "stderr": proc.stderr[:4000],
    }


def _version_for_h2t_ops(path: str, runner: Runner = _run) -> dict[str, Any]:
    if not path:
        return {"status": "missing", "version": ""}
    result = runner([path, "--version"], 10)
    version = result.get("stdout", "").strip().splitlines()
    return {
        "status": "ready" if result.get("exit_code") == 0 else "error",
        "version": version[0] if version else "",
        "exit_code": result.get("exit_code"),
    }


def _secret_present(key: str, home: Path) -> bool:
    """Through core.secrets, the reader every connector uses (#448, #548 §7.2): environment,
    secrets/shared/<provider>.env, then the 3.x ladder. `home` is kept for the callers; the
    places come from core.paths."""
    from h2t_ops.core import secrets

    return secrets.get(key) is not None


def _file_status(path: Path) -> dict[str, str]:
    return {"path": str(path), "status": "present" if path.is_file() else "missing"}


def optional_pos_status() -> dict[str, Any]:
    candidates = [
        paths.legacy_dir("secrets.dor_old"),   # the 3.x DOR directory itself
        paths.config_dir(),
    ]
    configured = any(_path_exists(path) for path in candidates)
    return {
        "status": "configured" if configured else "not_configured",
        "impact": (
            "lifecycle and connector provider I/O still work; POS publishing disabled"
            if not configured else "optional POS/DOR paths detected"
        ),
        "paths": [{"path": str(path), "exists": _path_exists(path)} for path in candidates],
    }


def plugin_cache_status(home: Path | None = None) -> dict[str, Any]:
    """Installed h2t-core versions under any marketplace, for Claude Code and Codex (#451).

    The same search the plugin-script ladder (h2t_ops.plugin_entrypoints, deleted in Task 12)
    made, written out here because setup_h2t.py could not import h2t_ops. A hardcoded
    `cache/lichtpfad/h2t-core` reported a working install under another marketplace name
    as missing.
    """
    home = home or _home()
    root: Path | None = None
    found: list[Path] = []
    for var, default in (("CLAUDE_CONFIG_DIR", ".claude"), ("CODEX_HOME", ".codex")):
        override = os.environ.get(var)
        cache = (paths.expand_user_dest(override) if override else home / default) / "plugins" / "cache"
        # Name the directory actually searched, even when nothing is there (#522): a fixed
        # ~/.claude here sat beside `missing` while CLAUDE_CONFIG_DIR pointed elsewhere.
        root = root or cache / "lichtpfad" / "h2t-core"
        if cache.is_dir():
            found.extend(path for path in cache.glob("*/h2t-core/*") if path.is_dir())
    # Oldest first, so the last is latest: non-semver dirs (Codex `local`, content hashes)
    # by mtime, then semver ones by version, which win when both exist.
    found.sort(key=lambda path: (_semver_key(path.name) != (0, 0, 0), _semver_key(path.name), path.stat().st_mtime))
    versions = [str(path) for path in found]
    if found:
        root = found[-1].parent
    return {
        "h2t_core_cache": str(root),
        "versions": versions,
        "latest": versions[-1] if versions else "",
        "status": "present" if versions else "missing",
    }


def legacy_shim_status(home: Path | None = None) -> dict[str, Any]:
    """Report an `h2t` command left in the pre-#449 venv under ~/.h2t by a dead install (#476).

    The 3.0.x line installed `h2t-core-cli` editable into that venv, pinned to a
    version-numbered plugin cache directory that the next plugin update removes. Agents find
    tools by listing bin/, so this broken `h2t` is the first thing they run. Report only: a
    diagnostic must not delete anything.
    """
    home = home or _home()
    venv = home / ".h2t" / "venv"
    windows = sys.platform.startswith("win")
    shim = venv / ("Scripts" if windows else "bin") / ("h2t.exe" if windows else "h2t")
    if not shim.is_file():
        return {"status": "ok"}
    site_dirs = [venv / "Lib" / "site-packages"] if windows else sorted(venv.glob("lib/python*/site-packages"))
    for site in site_dirs:
        for entry_points in site.glob("*.dist-info/entry_points.txt"):
            text = entry_points.read_text(encoding="utf-8", errors="replace")
            if not re.search(r"^h2t\s*=", text, re.M):
                continue
            name, _, version = entry_points.parent.name.removesuffix(".dist-info").partition("-")
            finder = site / f"__editable___{name.replace('-', '_')}_{version.replace('.', '_')}_finder.py"
            targets: list[str] = []
            if finder.is_file():
                match = re.search(r"MAPPING[^=]*=\s*(\{.*?\})", finder.read_text(encoding="utf-8", errors="replace"), re.S)
                if match:
                    try:
                        targets = list(ast.literal_eval(match.group(1)).values())
                    except (ValueError, SyntaxError):
                        targets = []
            missing = [target for target in targets if not Path(target).exists()]
            python = venv / ("Scripts/python.exe" if windows else "bin/python")
            return {
                "status": "stale" if missing else "ok",
                "path": str(shim),
                "package": f"{name} {version}",
                "editable_targets": targets,
                "missing_targets": missing,
                # uv, not `python -m pip`: this venv is not guaranteed to have pip.
                "remediation": f"uv pip uninstall --python {python} {name}" if missing else "",
            }
    return {"status": "ok", "path": str(shim), "package": "", "editable_targets": [], "missing_targets": []}


def doctor(runner: Runner = _run) -> dict[str, Any]:
    h2t_ops = resolve_h2t_ops()
    h2t_ops.update(_version_for_h2t_ops(h2t_ops.get("path", ""), runner))
    return {
        "kind": KIND_DOCTOR,
        "platform": detect_platform(),
        "uv": resolve_uv(),
        "h2t_ops": h2t_ops,
        "entry_points": resolve_entry_points(),
        "plugin_cache": plugin_cache_status(),
        "optional_pos": optional_pos_status(),
        "legacy_shims": legacy_shim_status(),
        "boundaries": {
            "root_h2t_touched": False,
            "pos_required": False,
        },
    }


def ensure_machine_name(*, name: str = "") -> dict[str, Any]:
    """Pin H2T_MACHINE_NAME in Claude Code's settings `env`, once (#491, ADR 0003).

    On macOS the hostname follows the network, so session records of one machine split
    across two directories. Claude Code passes `env` from settings.json to every process
    it starts, hooks included, whatever the shell. An existing value is never changed.

    Without `name`, today's name by the shared rule is written only if the session roots
    have a folder for it or no folders at all. Otherwise the hostname may already have
    drifted from the history (#517), and the roots may hold other machines' folders too,
    so nothing is written and the folders come back as candidates for the user to pick.
    """
    settings = paths.dir_of("harness") / "settings.json"
    from h2t_ops.lifecycle.gather.sessions import get_machine_name

    # Claude Code writes this file too. Replace it only if it is unchanged since it was
    # read, so a preference saved meanwhile is not overwritten with the stale copy.
    for _ in range(3):
        stamp = settings.stat().st_mtime_ns if settings.is_file() else None
        data: Any = {}
        if stamp is not None:
            try:
                data = json.loads(settings.read_text(encoding="utf-8"))
            except ValueError as exc:
                return {"status": "error", "path": str(settings), "error": f"not valid JSON, left untouched: {exc}"}
        if not isinstance(data, dict) or not isinstance(data.get("env", {}), dict):
            return {"status": "error", "path": str(settings), "error": "unexpected shape, left untouched"}
        current = data.get("env", {}).get("H2T_MACHINE_NAME")
        if current:
            return {"status": "unchanged", "path": str(settings), "value": current}
        if not name:
            today = get_machine_name()
            # The handoff writer's root and its 3.x one; the legacy ~/.dor/sessions is
            # shared between machines, so its folders say nothing about this one.
            roots = (paths.records("sessions"), paths.legacy("sessions.h2t"))
            folders = sorted({p.name for root in roots if root.is_dir() for p in root.iterdir()
                              if p.is_dir() and not p.name.startswith(".")})
            if folders and today not in folders:
                return {"status": "needs_choice", "path": str(settings), "today": today, "candidates": folders}
            name = today
        data.setdefault("env", {})["H2T_MACHINE_NAME"] = name
        if (settings.stat().st_mtime_ns if settings.is_file() else None) != stamp:
            continue
        store.replace(settings, json.dumps(data, indent=2, ensure_ascii=False) + "\n", place="harness")
        return {"status": "written", "path": str(settings), "value": name}
    return {"status": "error", "path": str(settings), "error": "kept changing while being updated, left untouched"}


def _google_json_status(name: str) -> dict[str, str]:
    from h2t_ops.core import secrets
    from h2t_ops.core.errors import ConfigError

    try:
        _, where = secrets.read_json(name)
    except ConfigError:
        return {"path": str(secrets.json_path(name)), "status": "unreadable"}
    return {"path": str(where or secrets.json_path(name)), "status": "present" if where else "missing"}


def _telegram_status() -> dict[str, dict[str, str]]:
    """Keys in telegram.env (per key, the 3.x config.json as the 4.0.x fallback) and the
    session in secrets/local (the 3.x session.session as the fallback), through core."""
    from h2t_ops.core import paths, secrets
    from h2t_ops.core.errors import ConfigError

    keys = {k: secrets.get(k) for k in ("TELEGRAM_API_ID", "TELEGRAM_API_HASH")}
    config = {"path": str(secrets.provider_file("telegram")), "status": "present"}
    if not all(keys.values()):
        legacy_cfg = paths.legacy("telegram") / "config.json"
        try:
            legacy = secrets.telegram_legacy_config() or {}
        except (ConfigError, UnicodeDecodeError, OSError):
            legacy = None
        if legacy is None:
            config = {"path": str(legacy_cfg), "status": "unreadable"}
        elif (keys["TELEGRAM_API_ID"] or legacy.get("api_id")) and (keys["TELEGRAM_API_HASH"] or legacy.get("api_hash")):
            config = {"path": str(legacy_cfg), "status": "present"}
        else:
            config["status"] = "missing"
    session = paths.secrets_local() / "telegram.session"
    if not session.is_file() and (paths.legacy("telegram") / "session.session").is_file():
        session = paths.legacy("telegram") / "session.session"
    return {"config": config, "session": _file_status(session)}


def _google_oauth_status(home: Path) -> dict[str, Any]:
    """The client and this machine's token through core.secrets: secrets/shared and
    secrets/local first, the 3.x files as a fallback (§4, R19)."""
    return {
        "credentials": _google_json_status("google.client"),
        "tokens": _google_json_status("google.token"),
    }


def connector_matrix(home: Path | None = None, *, live: bool = False, include_paid: bool = False,
                     runner: Runner = _run) -> dict[str, Any]:
    home = home or _home()
    h2t_ops = resolve_h2t_ops(home=home)
    h2t_ops_path = h2t_ops.get("path", "")
    google = _google_oauth_status(home)
    telegram = _telegram_status()
    checks: list[dict[str, Any]] = [
        {"connector": "calendar", "status": _ready_if_files(google), "checks": google, "live": "skipped"},
        {"connector": "gmail", "status": _ready_if_files(google), "checks": google, "live": "skipped"},
        {"connector": "drive", "status": _ready_if_files(google), "checks": google, "live": "skipped"},
        {
            "connector": "notion",
            "status": "ready" if _secret_present("NOTION_API_TOKEN", home) or paths.legacy("notion.token").is_file() else "missing",
            "checks": {"token": "present" if _secret_present("NOTION_API_TOKEN", home) or paths.legacy("notion.token").is_file() else "missing"},
            "live": "skipped",
        },
        {
            "connector": "telegram",
            "status": "ready" if telegram["config"]["status"] == "present" else "missing",
            "checks": telegram,
            "live": "skipped",
        },
        {
            "connector": "meetgeek",
            "status": "ready" if _secret_present("MEETGEEK_API_KEY", home) else "missing",
            "checks": {"MEETGEEK_API_KEY": "present" if _secret_present("MEETGEEK_API_KEY", home) else "missing"},
            "live": "skipped",
        },
        {
            "connector": "granola",
            "status": "ready" if _secret_present("GRANOLA_API_KEY", home) else "missing",
            "checks": {"GRANOLA_API_KEY": "present" if _secret_present("GRANOLA_API_KEY", home) else "missing"},
            "live": "skipped",
        },
        {
            "connector": "research",
            "status": "ready" if _secret_present("EXA_API_KEY", home) else "missing",
            "checks": {"EXA_API_KEY": "present" if _secret_present("EXA_API_KEY", home) else "missing"},
            "live": "skipped_paid" if not include_paid else "skipped",
        },
    ]
    if live and h2t_ops_path:
        _attach_live_checks(checks, h2t_ops_path, include_paid, runner)
    return {
        "kind": KIND_CONNECTORS,
        "h2t_ops": h2t_ops,
        "mode": "live" if live else "credential-only",
        "include_paid": include_paid,
        "connectors": checks,
    }


def _ready_if_files(checks: dict[str, dict[str, str]]) -> str:
    return "ready" if all(item["status"] == "present" for item in checks.values()) else "missing"


def _attach_live_checks(checks: list[dict[str, Any]], h2t_ops_path: str, include_paid: bool, runner: Runner) -> None:
    commands = {
        "telegram": [h2t_ops_path, "telegram", "auth", "status", "--json"],
        "meetgeek": [h2t_ops_path, "meetgeek", "auth-check", "--json"],
        "granola": [h2t_ops_path, "granola", "auth-check", "--json"],
    }
    if include_paid:
        commands["research"] = [h2t_ops_path, "research", "preflight", "--json"]
    for check in checks:
        cmd = commands.get(check["connector"])
        if not cmd:
            continue
        result = runner(cmd, 30)
        check["live"] = {
            "command": cmd[1:],
            "status": "ready" if result.get("exit_code") == 0 else "error",
            "exit_code": result.get("exit_code"),
            "stderr": result.get("stderr", "")[:800],
        }


def normalize_source(source: str) -> str:
    source = source.strip()
    if source == "main":
        return CANONICAL_H2T_OPS_SOURCE
    lower = source.lower()
    if lower == "h2t" or lower.endswith("/h2t") or lower.endswith("\\h2t"):
        raise ValueError("Refusing to install or repair root h2t; use h2t-ops / h2t-skills source.")
    return source


def install_h2t_ops(source: str, *, dry_run: bool = False, runner: Runner = _run) -> dict[str, Any]:
    uv = resolve_uv()
    if uv["status"] != "ready":
        return {"kind": KIND_INSTALL, "status": "missing_uv", "uv": uv, "command": []}
    normalized = normalize_source(source)
    is_local = Path(normalized).is_dir()
    if is_local:
        command = [uv["path"], "tool", "install", "--editable", normalized]
    else:
        command = [uv["path"], "tool", "install", "--reinstall", normalized]
    if dry_run:
        return {
            "kind": KIND_INSTALL,
            "status": "dry_run",
            "source": normalized,
            "editable": is_local,
            "command": command,
            "root_h2t_touched": False,
        }
    # Not run from here: this process is the h2t-ops tool that `uv tool install` replaces,
    # and on Windows its running h2t-ops.exe and python.exe are locked. The plugin script
    # ran under a separate interpreter; the package copy hands the line to the caller.
    line = shlex.join(command)
    return {
        "kind": KIND_INSTALL,
        "status": "error",
        "error": "h2t-ops cannot reinstall itself from inside its own process",
        "hint": f"Run this line yourself, after the user approves it: {line}",
        "source": normalized,
        "editable": is_local,
        "command": command,
        "root_h2t_touched": False,
    }


def _machine_name_line(info: dict[str, Any] | None) -> str:
    if not info:
        return ""
    detail = info.get("value") or info.get("error", "")
    return f"- machine name: {info['status']} {detail} ({info['path']})\n"


def _legacy_shim_line(info: dict[str, Any] | None) -> str:
    if not info or info.get("status") != "stale":
        return ""
    return (
        f"- legacy h2t command: stale {info['path']} ({info['package']}, its code is gone); "
        f"use h2t-ops. Remove with: {info['remediation']}\n"
    )


def _human(obj: dict[str, Any]) -> str:
    if obj.get("kind") == KIND_DOCTOR:
        ep = obj.get("entry_points", {})
        ep_status = ep.get("status", "unknown")
        missing_eps = [name for name, info in ep.get("commands", {}).items() if info.get("status") != "ready"]
        ep_detail = f" (missing: {', '.join(missing_eps)})" if missing_eps else ""
        return (
            f"h2t setup doctor\n"
            f"- platform: {obj['platform']['name']}\n"
            f"- uv: {obj['uv']['status']} {obj['uv'].get('path', '')}\n"
            f"- h2t-ops: {obj['h2t_ops']['status']} {obj['h2t_ops'].get('version', '')}\n"
            f"- entry points: {ep_status}{ep_detail}\n"
            f"- optional POS/DOR: {obj['optional_pos']['status']}\n"
            + _machine_name_line(obj.get("machine_name"))
            + _legacy_shim_line(obj.get("legacy_shims"))
        )
    if obj.get("kind") == KIND_CONNECTORS:
        rows = [f"- {c['connector']}: {c['status']} ({c['live']})" for c in obj["connectors"]]
        return "h2t connectors-check\n" + "\n".join(rows) + "\n"
    if obj.get("kind") == KIND_INSTALL:
        return f"h2t-ops install: {obj['status']}\ncommand: {' '.join(obj.get('command', []))}\n"
    return json.dumps(obj, ensure_ascii=False, indent=2)


def _load_known_secrets(registry_path: Path) -> dict[str, dict[str, str]]:
    """Parse known_secrets.yaml without PyYAML — handles only this file's flat structure."""
    if not registry_path.is_file():
        raise FileNotFoundError(f"known_secrets.yaml not found: {registry_path}")
    result: dict[str, dict[str, str]] = {}
    current: str | None = None
    for raw in registry_path.read_text(encoding="utf-8").splitlines():
        line = raw.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        if not line[0].isspace():
            current = line.rstrip(":").strip()
            result[current] = {}
        elif current and ":" in line:
            k, _, v = line.strip().partition(":")
            result[current][k.strip()] = v.strip().strip('"').strip("'")
    return result


def secrets_skeleton(registry: dict[str, dict[str, str]], *, secrets_dir: Path | None = None,
                     home: Path | None = None) -> dict[str, Any]:
    """Placeholder KEY= lines for missing keys, one file per provider (§4, R40).

    A key the connectors already resolve — environment, the new files or the 3.x ladder — is
    not missing (#524): a placeholder for it told the user to paste a key that already worked.
    Missing keys are grouped by provider (no provider: other.env) and appended to
    <secrets_dir>/<provider>.env; lines already there, comments included, stay as they are.

    secrets_dir: a directory the caller names (dest=True, R42); default secrets/shared.
    """
    from h2t_ops.core import paths, providers, secrets, store

    explicit = secrets_dir is not None
    secrets_dir = Path(secrets_dir) if explicit else paths.secrets_shared()
    groups: dict[str, list[str]] = {}
    skipped: list[str] = []
    for key in registry:
        if secrets.get(key) is not None:
            skipped.append(key)
        else:
            groups.setdefault(providers.provider_of_key(key) or "other", []).append(key)
    files: dict[str, dict[str, Any]] = {}
    added: list[str] = []
    for provider, keys in groups.items():
        path = secrets_dir / f"{provider}.env"
        existing = ""
        if path.is_file():
            raw = secrets.read_secret_bytes(path, root=secrets_dir) if explicit else secrets.read_secret_bytes(path)
            existing = raw.decode("utf-8")
        present = set(secrets.parse_env(existing))
        new_keys = [k for k in keys if k not in present]   # an empty KEY= already there stays one
        skipped += [k for k in keys if k in present]
        if not new_keys:
            continue
        lines: list[str] = []
        for key in new_keys:
            meta = registry[key]
            lines.append(f"# {meta.get('description', '')}")
            if meta.get("url"):
                lines.append(f"# Get at: {meta['url']}")
            lines += [f"{key}=", ""]
        separator = "\n" if existing and not existing.endswith("\n") else ""
        store.replace(path, existing + separator + "\n".join(lines), place="secrets.shared",
                      keys=tuple(new_keys), dest=explicit)
        files[path.name] = {"path": str(path), "added": new_keys}
        added += new_keys
    return {
        "kind": KIND_SECRETS_SKELETON,
        "path": str(secrets_dir),
        "files": files,
        "added": added,
        "skipped": skipped,
    }


def _validate_key(value: str, validator: str) -> bool:
    """Apply format validator. Only called when value is non-empty."""
    if validator == "uuid":
        return bool(re.fullmatch(
            r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
            value,
            re.IGNORECASE,
        ))
    if validator.startswith("starts_with:"):
        prefix = validator[len("starts_with:"):]
        return value.startswith(prefix)
    if validator == "nonempty":
        return bool(value)
    return bool(value)  # unknown validator: treat as nonempty


def secrets_preflight(
    registry: dict[str, dict[str, str]],
    *,
    home: Path | None = None,
    live: bool = False,
    runner: Runner = _run,
) -> dict[str, Any]:
    """Check each key using full resolution chain. Never returns key values.

    With live=True, also runs connector smoke tests.
    """
    home = home or _home()
    h2t_ops = resolve_h2t_ops()
    h2t_ops_path = h2t_ops.get("path", "") or "h2t-ops"
    results: list[dict[str, Any]] = []
    live_commands = {"research": "research preflight --json"}
    from h2t_ops.core import secrets

    for key, meta in registry.items():
        value = secrets.get(key) or ""   # local format validation only, never in the output
        found = bool(value)
        valid = found and _validate_key(value, meta.get("validator", "nonempty"))
        entry: dict[str, Any] = {
            "key": key,
            "found": found,
            "valid": valid,
            "connector": meta.get("connector", ""),
        }
        if live and found:
            connector = meta.get("connector", "")
            live_cmd = live_commands.get(connector)
            if live_cmd:
                cmd = [h2t_ops_path] + live_cmd.split()
                live_result = runner(cmd, 30)
                entry["live"] = {
                    "status": "ok" if live_result.get("exit_code") == 0 else "error",
                    "exit_code": live_result.get("exit_code"),
                }
        results.append(entry)
    return {
        "kind": KIND_SECRETS_PREFLIGHT,
        "results": results,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="h2t-ops setup")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("doctor", "setup", "repair", "update"):
        p = sub.add_parser(name)
        p.add_argument("--json", action="store_true")
        if name == "setup":
            p.add_argument("--machine-name", default="", help="Pin this name; the answer to needs_choice")
    cc = sub.add_parser("connectors-check")
    cc.add_argument("--json", action="store_true")
    cc.add_argument("--live", action="store_true", help="Run explicit read-only provider checks where safe")
    cc.add_argument("--include-paid", action="store_true", help="Allow paid provider preflights such as Exa")
    ins = sub.add_parser("install-h2t-ops")
    ins.add_argument("--source", default="main")
    ins.add_argument("--dry-run", action="store_true")
    ins.add_argument("--json", action="store_true")
    sk = sub.add_parser("secrets")
    sk_sub = sk.add_subparsers(dest="secrets_cmd", required=True)
    sk_skel = sk_sub.add_parser("skeleton")
    sk_skel.add_argument("--json", action="store_true")
    sk_pre = sk_sub.add_parser("preflight")
    sk_pre.add_argument("--json", action="store_true")
    sk_pre.add_argument("--live", action="store_true", help="Run live connector smoke tests")
    return parser


def main(argv: list[str] | None = None) -> int:
    # Windows encodes a piped stdout with the ANSI codepage, whatever chcp says, so
    # a non-ASCII payload reaches the caller as cp1252 — or kills the write outright
    # where cp1252 has no byte for the character. Every caller decodes UTF-8 (#428).
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = build_parser().parse_args(argv)
    try:
        if args.command in {"doctor", "setup", "repair", "update"}:
            result = doctor()
            if args.command == "setup":
                result["machine_name"] = ensure_machine_name(name=args.machine_name)
                if result["machine_name"]["status"] == "error":
                    result["status"] = "error"
        elif args.command == "connectors-check":
            result = connector_matrix(live=args.live, include_paid=args.include_paid)
        elif args.command == "install-h2t-ops":
            result = install_h2t_ops(args.source, dry_run=args.dry_run)
            if result.get("status") == "ok":
                plugin_cache = paths.dir_of("harness") / "plugins" / "cache" / "lichtpfad" / "h2t-core"
                if plugin_cache.exists():
                    versions = sorted(
                        [d for d in plugin_cache.iterdir()
                         if d.is_dir() and d.name != "latest" and _semver_key(d.name) != (0, 0, 0)],
                        key=lambda p: _semver_key(p.name),
                    )
                    if versions:
                        current = versions[-1]
                        # No `latest` junction is created any more. It was refreshed only
                        # here, never by `/plugin marketplace update`, so it drifted behind
                        # the installed version and silently answered the wrong one.
                        # Hooks resolve through `h2t-hook` at fire time instead.
                        versions_file = paths.config_dir() / "plugin-versions.json"
                        _data = {}
                        if versions_file.exists():
                            try:
                                _data = json.loads(versions_file.read_text(encoding="utf-8"))
                            except Exception:
                                pass
                        _data["h2t-core"] = str(current)
                        store.replace(versions_file, json.dumps(_data, indent=2), place="config")
        elif args.command == "secrets":
            from h2t_ops.resources import known_secrets_path

            registry_path = known_secrets_path()
            try:
                registry = _load_known_secrets(registry_path)
            except FileNotFoundError as exc:
                result = {"kind": "h2t_setup_error/v1", "status": "error", "error": str(exc)}
                print(json.dumps(result, ensure_ascii=False, indent=2))
                return 3
            if args.secrets_cmd == "skeleton":
                result = secrets_skeleton(registry)
            elif args.secrets_cmd == "preflight":
                result = secrets_preflight(registry, live=args.live)
            else:
                raise AssertionError(args.secrets_cmd)
        else:
            raise AssertionError(args.command)
    except ValueError as exc:
        result = {"kind": "h2t_setup_error/v1", "status": "error", "error": str(exc)}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2
    if getattr(args, "json", False):
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(_human(result))
    return 0 if result.get("status") not in {"error", "missing_uv"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
