"""h2t-ops CLI: dev wrapper + registry dispatch + doctor + legacy delegation + ingest shim."""
from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

import h2t_ops
from h2t_ops.core.errors import UsageError
from h2t_ops.core.output import emit
from h2t_ops.core.registry import discover
from h2t_ops.dev import main as _dev_main

_MIGRATED = {"notion", "gmail"}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="h2t-ops", description="h2t-ops unified connector CLI")
    p.add_argument("--version", action="version", version=f"h2t-ops {h2t_ops.__version__}")
    sub = p.add_subparsers(dest="connector")
    sub.add_parser("connectors", help="List available connectors")
    sub.add_parser("doctor", help="Installed CLI health (version, path, connectors, secrets)")
    for spec in discover():
        spec.register(sub)
    return p


def _doctor() -> int:
    print(f"h2t-ops {h2t_ops.__version__}")
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
    from lib.cli.main import main as legacy_main  # legacy keeps its own sys.path hack
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


def dispatch(argv: list[str]) -> int:
    if argv and argv[0] == "dev":
        return _dev_main(argv[1:])
    if argv and argv[0] in ("--version", "-V"):
        print(f"h2t-ops {h2t_ops.__version__}")
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
            print("deprecated: `h2t-ops ingest notion` → use `h2t-ops notion` (spec §10)",
                  file=sys.stderr)
        return _run_connector(["notion", *norm])
    # ingest gmail shim → new connector (spec §10.2)
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
            print("deprecated: `h2t-ops ingest gmail` → use `h2t-ops gmail` (spec §10)",
                  file=sys.stderr)
        return _run_connector(["gmail", *norm])
    if argv and argv[0] in ("gather", "ingest"):
        return _legacy(argv)
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
