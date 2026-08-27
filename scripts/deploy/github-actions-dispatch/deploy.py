"""GitHub Actions workflow dispatch deploy profile."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


def main() -> int:
    # Windows encodes a piped stdout with the ANSI codepage, whatever chcp says, so
    # a non-ASCII payload reaches the caller as cp1252 — or kills the write outright
    # where cp1252 has no byte for the character. Every caller decodes UTF-8 (#428).
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    try:
        payload = _load_payload()
        config = _require_config(payload, "repo", "workflow", "ref")
        service = _require_service(payload)
        gh_bin = os.environ.get("H2T_DEPLOY_GH", "gh")
        command = [
            gh_bin,
            "workflow",
            "run",
            config["workflow"],
            "--repo",
            config["repo"],
            "--ref",
            config["ref"],
        ]

        if payload["dry_run"]:
            return _emit_success(
                {
                    "service": service,
                    "target": payload["target"],
                    "status": "dry_run",
                    "details": {
                        "profile": payload["profile"],
                        "mode": "dry_run",
                        "resolved_command": _shell_preview(command),
                        "repo": config["repo"],
                        "workflow": config["workflow"],
                        "ref": config["ref"],
                    },
                }
            )

        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0:
            return _emit_error(
                "provider",
                "GitHub workflow dispatch failed",
                details={
                    "command": command,
                    "returncode": completed.returncode,
                    "stderr": (completed.stderr or "").strip(),
                    "stdout": (completed.stdout or "").strip(),
                },
                exit_code=1,
            )

        return _emit_success(
            {
                "service": service,
                "target": payload["target"],
                "status": "dispatched",
                "details": {
                    "profile": payload["profile"],
                    "repo": config["repo"],
                    "workflow": config["workflow"],
                    "ref": config["ref"],
                    "resolved_command": _shell_preview(command),
                    "gh_stdout": (completed.stdout or "").strip(),
                },
            }
        )
    except DeployScriptError as exc:
        return _emit_error(exc.error_type, str(exc), details=exc.details, exit_code=1)
    except Exception as exc:  # noqa: BLE001 - script must emit machine-readable failure
        return _emit_error("provider", f"Unhandled deploy script failure: {exc}", exit_code=1)


class DeployScriptError(Exception):
    def __init__(self, message: str, *, error_type: str = "config", details: dict[str, Any] | None = None):
        super().__init__(message)
        self.error_type = error_type
        self.details = details


def _load_payload() -> dict[str, Any]:
    input_path = os.environ.get("H2T_DEPLOY_INPUT_JSON")
    if not input_path:
        raise DeployScriptError("H2T_DEPLOY_INPUT_JSON is not set", error_type="usage")

    try:
        payload = json.loads(Path(input_path).read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise DeployScriptError(
            f"Deploy input JSON not found: {input_path}",
            error_type="config",
        ) from exc
    except json.JSONDecodeError as exc:
        raise DeployScriptError(
            "Deploy input JSON is malformed",
            error_type="config",
            details={"path": input_path, "error": str(exc)},
        ) from exc

    if not isinstance(payload, dict):
        raise DeployScriptError("Deploy input payload must be an object", error_type="config")
    return payload


def _require_config(payload: dict[str, Any], *keys: str) -> dict[str, str]:
    config = payload.get("config")
    if not isinstance(config, dict):
        raise DeployScriptError("Deploy payload missing config object", error_type="config")

    resolved: dict[str, str] = {}
    for key in keys:
        value = config.get(key)
        if not isinstance(value, str) or not value.strip():
            raise DeployScriptError(
                f"Deploy payload missing required config value: {key}",
                error_type="config",
                details={"field": key},
            )
        resolved[key] = value
    return resolved


def _require_service(payload: dict[str, Any]) -> str:
    value = payload.get("service")
    if not isinstance(value, str) or not value.strip():
        raise DeployScriptError(
            "Deploy payload missing service name",
            error_type="config",
            details={"field": "service"},
        )
    return value


def _emit_success(result: dict[str, Any]) -> int:
    print(json.dumps({"ok": True, "provider": "deploy", "result": result}))
    return 0


def _emit_error(
    error_type: str,
    message: str,
    *,
    details: dict[str, Any] | None = None,
    exit_code: int,
) -> int:
    error: dict[str, Any] = {"type": error_type, "message": message}
    if details:
        error["details"] = details
    print(json.dumps({"ok": False, "provider": "deploy", "error": error}))
    return exit_code


def _shell_preview(command: list[str]) -> str:
    return subprocess.list2cmdline(command)


if __name__ == "__main__":
    sys.exit(main())
