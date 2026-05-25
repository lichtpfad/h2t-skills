"""Top-level deploy command parsing and dispatch."""

from __future__ import annotations

import argparse
from typing import Any

from h2t_ops.core.errors import AuthError, ConfigError, NetworkError, NotFoundError, ProviderError, UsageError
from h2t_ops.core.output import emit

from .executor import execute_deploy_action
from .profiles import load_profile_registry
from .registry import load_service_registry

_PROVIDER = "deploy"
_SPECIAL_MODES = {"list", "status"}
_ERROR_TYPES = {
    "usage": UsageError,
    "config": ConfigError,
    "auth": AuthError,
    "provider": ProviderError,
    "not_found": NotFoundError,
    "network": NetworkError,
}


class _DeployArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise UsageError(message)


def build_parser() -> argparse.ArgumentParser:
    parser = _DeployArgumentParser(
        prog="h2t-ops deploy",
        description="Profile-driven deploy commands",
        usage=(
            "h2t-ops deploy <service> [--target TARGET] [--dry-run] [--json]\n"
            "       h2t-ops deploy list [--json]\n"
            "       h2t-ops deploy status <service> [--target TARGET] [--json]"
        ),
    )
    parser.add_argument("mode", nargs="?", help="service name, 'list', or 'status'")
    parser.add_argument("service", nargs="?", help="service name for 'status'")
    parser.add_argument("--target", help="deploy target name")
    parser.add_argument("--dry-run", action="store_true", help="preview deploy action")
    parser.add_argument("--json", dest="as_json", action="store_true", help="emit JSON envelope")
    return parser


def dispatch(argv: list[str]) -> int:
    fmt = "json" if "--json" in argv else "human"
    parser = build_parser()
    try:
        ns = parser.parse_args(argv)
    except SystemExit as exc:
        code = exc.code
        if code is None:
            return 0
        return code if isinstance(code, int) else 2
    try:
        fmt = "json" if ns.as_json else "human"
        result = _dispatch_parsed(ns, fmt=fmt)
    except Exception as exc:  # noqa: BLE001 - central error->exit mapping
        return emit(_PROVIDER, exc=exc, fmt=fmt)
    return emit(_PROVIDER, result=result, fmt=fmt)


def _dispatch_parsed(ns: argparse.Namespace, *, fmt: str) -> Any:
    mode = ns.mode
    if mode is None:
        raise UsageError("deploy requires a subcommand or service name")

    if mode == "list":
        if ns.service is not None:
            raise UsageError("deploy list does not accept a service name")
        if ns.target is not None:
            raise UsageError("deploy list does not accept --target")
        if ns.dry_run:
            raise UsageError("deploy list does not accept --dry-run")
        rows = _list_services()
        return rows if fmt == "json" else _format_list_table(rows)

    if mode == "status":
        if ns.service is None:
            raise UsageError("deploy status requires a service name")
        if ns.dry_run:
            raise UsageError("deploy status does not accept --dry-run")
        return _execute_action(ns.service, action="status", target=ns.target, dry_run=False)

    if mode in _SPECIAL_MODES:
        raise UsageError(f"Unsupported deploy mode: {mode!r}")

    if ns.service is not None:
        raise UsageError("deploy <service> does not accept an extra positional argument")
    return _execute_action(mode, action="deploy", target=ns.target, dry_run=ns.dry_run)


def _list_services() -> list[dict[str, Any]]:
    profiles = load_profile_registry()
    services = load_service_registry(profiles=profiles)
    rows = []
    for service_name, service in services.items():
        for target_name, target in service.targets.items():
            rows.append(
                {
                    "service": service_name,
                    "service_type": service.service_type,
                    "target": target_name,
                    "profile": target.profile,
                    "is_default": target_name == service.default_target,
                }
            )
    return rows


def _format_list_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "No deploy targets registered."

    columns = ["service", "service_type", "target", "profile", "is_default"]
    widths = {
        column: max(len(column), *(len(str(row[column])) for row in rows))
        for column in columns
    }
    header = "  ".join(column.ljust(widths[column]) for column in columns)
    lines = [header]
    for row in rows:
        lines.append("  ".join(str(row[column]).ljust(widths[column]) for column in columns))
    return "\n".join(lines)


def _execute_action(service: str, *, action: str, target: str | None, dry_run: bool) -> Any:
    envelope = execute_deploy_action(service, action=action, target=target, dry_run=dry_run)
    return _unwrap_executor_envelope(envelope)


def _unwrap_executor_envelope(envelope: dict[str, Any]) -> Any:
    if envelope.get("ok") is True:
        return envelope.get("result")

    error = envelope.get("error")
    if not isinstance(error, dict):
        raise ProviderError("Deploy executor returned an invalid error envelope", details=envelope)

    error_type = error.get("type")
    message = error.get("message")
    hint = error.get("hint")
    details = error.get("details")
    exc_type = _ERROR_TYPES.get(error_type, ProviderError)
    raise exc_type(
        message if isinstance(message, str) and message else "Deploy executor failed",
        hint=hint if isinstance(hint, str) else None,
        details=details,
    )
