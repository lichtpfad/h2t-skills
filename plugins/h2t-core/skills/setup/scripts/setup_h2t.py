"""Deterministic h2t-core setup/update backend.

This script is intentionally standalone: it must run from an installed plugin
cache before POS/DOR is configured. POS/DOR paths are inspected only as optional
state and never treated as setup prerequisites.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

KIND_DOCTOR = "h2t_setup_doctor/v1"
KIND_CONNECTORS = "h2t_connectors_check/v1"
KIND_INSTALL = "h2t_ops_install/v1"
KIND_SECRETS_SKELETON = "h2t_secrets_skeleton/v1"
KIND_SECRETS_PREFLIGHT = "h2t_secrets_preflight/v1"
CANONICAL_H2T_OPS_SOURCE = "git+https://github.com/lichtpfad/h2t-skills.git"
SECRET_KEYS = {
    "notion": ["NOTION_API_TOKEN"],
    "meetgeek": ["MEETGEEK_API_KEY"],
    "research": ["EXA_API_KEY"],
}

Runner = Callable[[list[str], int], dict[str, Any]]


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
    return Path.home()


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


def resolve_h2t_ops(which: Callable[[str], str | None] = shutil.which, home: Path | None = None) -> dict[str, Any]:
    home = home or _home()
    for name in (["h2t-ops.exe", "h2t-ops"] if sys.platform.startswith("win") else ["h2t-ops", "h2t-ops.exe"]):
        found = which(name)
        if found:
            return {"status": "ready", "path": found, "source": "PATH"}
    candidate = home / ".local" / "bin" / ("h2t-ops.exe" if sys.platform.startswith("win") else "h2t-ops")
    if candidate.is_file():
        return {"status": "ready", "path": str(candidate), "source": "~/.local/bin"}
    return {
        "status": "missing",
        "path": "",
        "source": "not-found",
        "hint": "Run setup_h2t.py install-h2t-ops --source main",
    }


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


def _candidate_secret_files(home: Path) -> list[Path]:
    files: list[Path] = []
    override = os.environ.get("H2T_SECRETS_FILE")
    if override:
        files.append(Path(override))
    files.extend([
        home / ".dor" / "secrets" / "secrets.env",
        home / ".dor" / "secrets.env",
    ])
    return files


def _secret_present(key: str, home: Path) -> bool:
    if os.environ.get(key):
        return True
    for path in _candidate_secret_files(home):
        if not path.is_file():
            continue
        try:
            for raw in path.read_text(encoding="utf-8").splitlines():
                line = raw.strip()
                if line.startswith(f"{key}="):
                    return bool(line.partition("=")[2].strip().strip('"').strip("'"))
        except OSError:
            continue
    return False


def _file_status(path: Path) -> dict[str, str]:
    return {"path": str(path), "status": "present" if path.is_file() else "missing"}


def optional_pos_status(home: Path | None = None) -> dict[str, Any]:
    home = home or _home()
    candidates = [
        home / ".dor",
        home / ".h2t" / "config",
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
    home = home or _home()
    root = home / ".claude" / "plugins" / "cache" / "lichtpfad" / "h2t-core"
    versions = []
    if root.is_dir():
        versions = [str(path) for path in sorted(root.iterdir()) if path.is_dir()]
    return {
        "h2t_core_cache": str(root),
        "versions": versions,
        "latest": versions[-1] if versions else "",
        "status": "present" if versions else "missing",
    }


def doctor(runner: Runner = _run) -> dict[str, Any]:
    h2t_ops = resolve_h2t_ops()
    h2t_ops.update(_version_for_h2t_ops(h2t_ops.get("path", ""), runner))
    return {
        "kind": KIND_DOCTOR,
        "platform": detect_platform(),
        "uv": resolve_uv(),
        "h2t_ops": h2t_ops,
        "plugin_cache": plugin_cache_status(),
        "optional_pos": optional_pos_status(),
        "boundaries": {
            "root_h2t_touched": False,
            "pos_required": False,
        },
    }


def _google_oauth_status(home: Path) -> dict[str, Any]:
    cfg = home / ".config" / "google-calendar-mcp"
    return {
        "credentials": _file_status(cfg / "credentials.json"),
        "tokens": _file_status(cfg / "tokens.json"),
    }


def connector_matrix(home: Path | None = None, *, live: bool = False, include_paid: bool = False,
                     runner: Runner = _run) -> dict[str, Any]:
    home = home or _home()
    h2t_ops = resolve_h2t_ops(home=home)
    h2t_ops_path = h2t_ops.get("path", "")
    google = _google_oauth_status(home)
    checks: list[dict[str, Any]] = [
        {"connector": "calendar", "status": _ready_if_files(google), "checks": google, "live": "skipped"},
        {"connector": "gmail", "status": _ready_if_files(google), "checks": google, "live": "skipped"},
        {"connector": "drive", "status": _ready_if_files(google), "checks": google, "live": "skipped"},
        {
            "connector": "notion",
            "status": "ready" if _secret_present("NOTION_API_TOKEN", home) or (home / ".config" / "notion" / "token").is_file() else "missing",
            "checks": {"token": "present" if _secret_present("NOTION_API_TOKEN", home) or (home / ".config" / "notion" / "token").is_file() else "missing"},
            "live": "skipped",
        },
        {
            "connector": "telegram",
            "status": "ready" if (home / ".config" / "telegram" / "config.json").is_file() else "missing",
            "checks": {
                "config": _file_status(home / ".config" / "telegram" / "config.json"),
                "session": _file_status(home / ".config" / "telegram" / "session.session"),
            },
            "live": "skipped",
        },
        {
            "connector": "meetgeek",
            "status": "ready" if _secret_present("MEETGEEK_API_KEY", home) else "missing",
            "checks": {"MEETGEEK_API_KEY": "present" if _secret_present("MEETGEEK_API_KEY", home) else "missing"},
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
    command = [uv["path"], "tool", "install", "--reinstall", normalized]
    if dry_run:
        return {
            "kind": KIND_INSTALL,
            "status": "dry_run",
            "source": normalized,
            "command": command,
            "root_h2t_touched": False,
        }
    result = runner(command, 300)
    return {
        "kind": KIND_INSTALL,
        "status": "ok" if result.get("exit_code") == 0 else "error",
        "source": normalized,
        "command": command,
        "result": result,
        "root_h2t_touched": False,
    }


def _human(obj: dict[str, Any]) -> str:
    if obj.get("kind") == KIND_DOCTOR:
        return (
            f"h2t setup doctor\n"
            f"- platform: {obj['platform']['name']}\n"
            f"- uv: {obj['uv']['status']} {obj['uv'].get('path', '')}\n"
            f"- h2t-ops: {obj['h2t_ops']['status']} {obj['h2t_ops'].get('version', '')}\n"
            f"- optional POS/DOR: {obj['optional_pos']['status']}\n"
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


def secrets_skeleton(secrets_file: Path, registry: dict[str, dict[str, str]]) -> dict[str, Any]:
    """Create or extend secrets.env with placeholder KEY= lines for missing keys.

    Uses atomic write (temp file + rename) so a crash leaves no partial state.
    """
    secrets_file.parent.mkdir(parents=True, exist_ok=True)
    existing_content = ""
    existing_keys: set[str] = set()
    if secrets_file.is_file():
        existing_content = secrets_file.read_text(encoding="utf-8")
        for raw in existing_content.splitlines():
            line = raw.strip()
            if line and not line.startswith("#") and "=" in line:
                existing_keys.add(line.split("=", 1)[0].strip())
    added: list[str] = []
    skipped: list[str] = []
    new_lines: list[str] = []
    for key, meta in registry.items():
        if key in existing_keys:
            skipped.append(key)
        else:
            desc = meta.get("description", "")
            url = meta.get("url", "")
            new_lines.append(f"# {desc}")
            if url:
                new_lines.append(f"# Get at: {url}")
            new_lines.append(f"{key}=")
            new_lines.append("")
            added.append(key)
    if new_lines:
        separator = "\n" if existing_content and not existing_content.endswith("\n") else ""
        full_content = existing_content + separator + "\n".join(new_lines)
        tmp = secrets_file.parent / (secrets_file.name + ".tmp")
        tmp.write_text(full_content, encoding="utf-8")
        tmp.replace(secrets_file)
    return {
        "kind": KIND_SECRETS_SKELETON,
        "path": str(secrets_file),
        "added": added,
        "skipped": skipped,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="setup_h2t.py")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("doctor", "setup", "repair", "update"):
        p = sub.add_parser(name)
        p.add_argument("--json", action="store_true")
    cc = sub.add_parser("connectors-check")
    cc.add_argument("--json", action="store_true")
    cc.add_argument("--live", action="store_true", help="Run explicit read-only provider checks where safe")
    cc.add_argument("--include-paid", action="store_true", help="Allow paid provider preflights such as Exa")
    ins = sub.add_parser("install-h2t-ops")
    ins.add_argument("--source", default="main")
    ins.add_argument("--dry-run", action="store_true")
    ins.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command in {"doctor", "setup", "repair", "update"}:
            result = doctor()
        elif args.command == "connectors-check":
            result = connector_matrix(live=args.live, include_paid=args.include_paid)
        elif args.command == "install-h2t-ops":
            result = install_h2t_ops(args.source, dry_run=args.dry_run)
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
