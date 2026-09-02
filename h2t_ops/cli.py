"""h2t-ops CLI: dev wrapper + registry dispatch + doctor + legacy delegation + ingest shim."""
from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

from h2t_ops import build_info
from h2t_ops.core.errors import UsageError

# Route shim deprecation notices through emit()'s UTF-8 writer (reuses privates
# intentionally) so they don't UnicodeEncodeError on Windows consoles (#141 class).
from h2t_ops.core.output import _finalize, _utf8_writer, emit
from h2t_ops.core.registry import discover
from h2t_ops.dev import main as _dev_main

_MIGRATED = {"notion", "gmail", "calendar", "drive", "meetgeek", "granola", "telegram", "research", "evals", "dropbox"}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="h2t-ops", description="h2t-ops unified connector CLI")
    p.add_argument("--version", action="version", version=build_info.version_line())
    sub = p.add_subparsers(dest="connector")
    sub.add_parser("connectors", help="List available connectors")
    sub.add_parser("deploy", help="Profile-driven deploy commands")
    sub.add_parser("doctor", help="Installed CLI health (version, path, connectors, secrets)")
    for spec in discover():
        spec.register(sub)
    return p


def _doctor() -> int:
    print(build_info.version_line())
    print(f"executable: {shutil.which('h2t-ops') or sys.executable}")
    print("connectors:")
    for spec in discover():
        print(f"  - {spec.name}: {spec.help}")
    notion = bool(os.getenv("NOTION_API_TOKEN")) or \
        (Path.home() / ".config" / "notion" / "token").is_file()
    print(f"secrets: NOTION_API_TOKEN={'present' if notion else 'MISSING'}")
    gmail_creds = (Path.home() / ".config" / "gmail" / "credentials.json").is_file() or \
        (Path.home() / ".config" / "google-calendar-mcp" / "credentials.json").is_file()
    print(f"secrets: gmail credentials={'present' if gmail_creds else 'MISSING'}")
    return 0


def _legacy(argv: list[str]) -> int:
    try:
        from lib.cli.main import (
            main as legacy_main,  # legacy keeps its own sys.path hack
        )
    except ImportError:
        # Wave 1 emptied lib/cli, and the wheel no longer ships a top-level `lib` at all.
        # The contract for an unrecognised command is exit 2, not a traceback.
        print(f"error: unknown command: {argv[0] if argv else ''}", file=sys.stderr)
        return 2
    old = sys.argv
    sys.argv = ["h2t-ops", *argv]
    try:
        legacy_main()
        return 0
    except SystemExit as e:
        code = e.code
        if code is None:
            return 0
        return code if isinstance(code, int) else 1
    finally:
        sys.argv = old


def _fmt_from(argv: list[str]) -> str:
    if "--json" in argv:
        return "json"
    if "--format" in argv:
        i = argv.index("--format")
        if i + 1 < len(argv):
            return argv[i + 1]
    return "human"


def _run_connector(argv: list[str]) -> int:
    parser = build_parser()
    try:
        ns = parser.parse_args(argv)
    except SystemExit as e:
        code = e.code
        if code is None:
            return 0
        return code if isinstance(code, int) else 2
    handler = getattr(ns, "_handler", None)
    if handler is None:
        return emit(argv[0], exc=UsageError("no subcommand"), fmt="human")
    fmt = "json" if getattr(ns, "as_json", False) else getattr(ns, "fmt", "human")
    provider = argv[0]
    try:
        return emit(provider, result=handler(ns), fmt=fmt)
    except SystemExit:
        raise
    except BaseException as exc:  # noqa: BLE001 — central error→exit mapping
        return emit(provider, exc=exc, fmt=fmt)


def _deploy_dispatch(argv: list[str]) -> int:
    from h2t_ops.deploy.commands import dispatch as deploy_dispatch

    return deploy_dispatch(argv)


def dispatch(argv: list[str]) -> int:
    if argv and argv[0] == "dev":
        return _dev_main(argv[1:])
    if argv and argv[0] == "deploy":
        return _deploy_dispatch(argv[1:])
    if argv and argv[0] in ("--help", "-h"):
        build_parser().print_help()
        return 0
    if argv and argv[0] in ("--version", "-V"):
        print(build_info.version_line())
        return 0
    if argv and argv[0] == "doctor":
        return _doctor()
    if argv and argv[0] == "connectors":
        for spec in discover():
            print(f"{spec.name:12} {spec.help}")
        return 0
    # ingest notion shim → new connector (spec §10)
    if len(argv) >= 2 and argv[0] == "ingest" and argv[1] == "notion":
        rest, norm, skip = argv[2:], [], False
        for j, a in enumerate(argv[2:]):
            if skip:
                skip = False
                continue
            if a == "--format" and j + 1 < len(rest) and rest[j + 1] in ("json", "markdown"):
                norm += ["--json"] if rest[j + 1] == "json" else ["--format", "md"]
                skip = True
            else:
                norm.append(a)
        if _fmt_from(norm) != "json":
            _w, _c = _utf8_writer(sys.stderr)
            print("deprecated: `h2t-ops ingest notion` → use `h2t-ops notion` (spec §10)",
                  file=_w)
            _finalize(_w, _c)
        return _run_connector(["notion", *norm])
    # ingest gmail shim → new connector (spec §10.2).
    # Gmail legacy accepted `--format plain` (& friends); notion did not — so we
    # consume ANY `--format <val>` (json→--json, others dropped), unlike the
    # notion shim above which only consumes json/markdown. Do not unify.
    if len(argv) >= 2 and argv[0] == "ingest" and argv[1] == "gmail":
        rest, norm, skip = argv[2:], [], False
        for j, a in enumerate(argv[2:]):
            if skip:
                skip = False
                continue
            if a == "--format" and j + 1 < len(rest):
                if rest[j + 1] == "json":
                    norm.append("--json")
                # "plain" (and any non-json) → drop; connector human default
                skip = True
            else:
                norm.append(a)
        if _fmt_from(norm) != "json":
            _w, _c = _utf8_writer(sys.stderr)
            print("deprecated: `h2t-ops ingest gmail` → use `h2t-ops gmail` (spec §10)",
                  file=_w)
            _finalize(_w, _c)
        return _run_connector(["gmail", *norm])
    # ingest calendar shim → new connector (spec §10.2). Mirror Gmail variant.
    if len(argv) >= 2 and argv[0] == "ingest" and argv[1] == "calendar":
        rest, norm, skip = argv[2:], [], False
        for j, a in enumerate(argv[2:]):
            if skip:
                skip = False
                continue
            if a == "--format" and j + 1 < len(rest):
                if rest[j + 1] == "json":
                    norm.append("--json")
                # non-json (e.g. legacy "markdown") → drop; connector human default
                skip = True
            else:
                norm.append(a)
        if _fmt_from(norm) != "json":
            _w, _c = _utf8_writer(sys.stderr)
            print("deprecated: `h2t-ops ingest calendar` → use `h2t-ops calendar` (spec §10)",
                  file=_w)
            _finalize(_w, _c)
        return _run_connector(["calendar", *norm])
    if argv and argv[0] == "ingest":
        # Only the three shims above survive: lib/clients is retired (#356), so any
        # other ingest source has no implementation left to reach.
        return emit("ingest", exc=UsageError(
            "`h2t-ops ingest` is retired — use the connector directly, e.g. `h2t-ops gmail list`"
        ), fmt=_fmt_from(argv))
    if argv and argv[0] == "gather":
        # One gather implementation: the plugin script, reached through the same ladder
        # h2t-gather uses. lib/cli/main.py carried a second copy that never gained
        # find_latest_session_index, so this path silently lost "### Previous Session".
        from h2t_ops.plugin_entrypoints import run_plugin_main
        # Replicate the legacy parser rather than slicing argv: argparse accepts the
        # optional positional anywhere, so `gather --cwd /tmp session-start` is a valid
        # legacy shape that hand-rolled parsing would reject.
        gp = argparse.ArgumentParser(prog="h2t-ops gather")
        gp.add_argument("skill", nargs="?", default="")
        gp.add_argument("--cwd", default=".")
        gp.add_argument("--format-briefing", action="store_true")
        gp.add_argument("--briefing-only", action="store_true")
        gathered = gp.parse_args(argv[1:])
        if not gathered.skill:
            print("error: gather requires a skill name (e.g. session-start, handoff)",
                  file=sys.stderr)
            return 2
        forwarded = ["h2t-gather", "--skill", gathered.skill, "--cwd", gathered.cwd]
        if gathered.format_briefing:
            forwarded.append("--format-briefing")
        if gathered.briefing_only:
            forwarded.append("--briefing-only")
        sys.argv = forwarded
        return run_plugin_main("skills/session-start/scripts/gather.py")
    if argv and argv[0] in _MIGRATED:
        return _run_connector(argv)
    if not argv:
        build_parser().print_help()
        return 0
    return _legacy(argv)


def main() -> None:
    sys.exit(dispatch(sys.argv[1:]))


if __name__ == "__main__":
    main()
