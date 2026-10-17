"""h2t-ops CLI: registry dispatch + doctor + legacy delegation + ingest shim."""
from __future__ import annotations

import argparse
import shutil
import sys

import h2t_ops
from h2t_ops import build_info
from h2t_ops.core.errors import UsageError

# Route shim deprecation notices through emit()'s UTF-8 writer (reuses privates
# intentionally) so they don't UnicodeEncodeError on Windows consoles (#141 class).
from h2t_ops.core.output import _finalize, _utf8_writer, emit
from h2t_ops.core.registry import discover

_MIGRATED = {"notion", "gmail", "calendar", "drive", "meetgeek", "granola", "telegram", "research", "evals", "dropbox", "google"}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="h2t-ops", description="h2t-ops unified connector CLI")
    p.add_argument("--version", action="version", version=build_info.version_line())
    sub = p.add_subparsers(dest="connector")
    sub.add_parser("connectors", help="List available connectors")
    sub.add_parser("deploy", help="Profile-driven deploy commands")
    sub.add_parser("version", help="Check the installed version and entry points (--expect V, --json); exit 3 if not ok")
    sub.add_parser("doctor", help="Report installed CLI state (version, path, connectors, secrets); always exits 0, connectors-check is the gate")
    sub.add_parser("setup", help="The h2t-core setup skill's backend: doctor, setup, install-h2t-ops, connectors-check, secrets")
    for spec in discover():
        spec.register(sub)
    return p


def _doctor() -> int:
    """Report install state; always exits 0 (#451, owner's decision 2026-10-10).

    doctor is a report, not a gate: a non-zero exit when any connector is unconfigured
    would be red on every machine that does not use all of them. The readiness gate is
    the h2t-core setup skill's `connectors-check`.
    """
    print(build_info.version_line())
    print(f"executable: {shutil.which('h2t-ops') or sys.executable}")
    print("connectors:")
    names = []
    for spec in discover():
        names.append(spec.name)
        print(f"  - {spec.name}: {spec.help}")
    # Ask the same code the connectors use (#451): the literals here missed a token kept in
    # a secrets file, and took gmail's client credentials for a signed-in token.
    from h2t_ops.core import google_auth
    from h2t_ops.core.errors import ConfigError
    from h2t_ops.core.secrets import resolve_notion_token
    try:
        resolve_notion_token()
        notion = "present"
    except ConfigError:
        notion = "MISSING"
    except (OSError, UnicodeDecodeError) as exc:
        notion = f"UNREADABLE ({exc})"
    print(f"secrets: NOTION_API_TOKEN={notion}")
    gmail_token = any(token.is_file() for token, _ in google_auth._candidate_paths("gmail"))
    print(f"secrets: gmail token={'present' if gmail_token else 'MISSING'}")
    unchecked = [name for name in names if name not in ("notion", "gmail")]
    print(f"not checked here: {', '.join(unchecked)}; run the h2t-core setup skill's connectors-check")
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


_VERSION_MESSAGES = {
    "not_installed": "h2t-ops is not installed as a tool",
    "version": "installed version does not match the expected one",
    "path": "PATH does not lead to the installed entry points",
}


def _version(argv: list[str]) -> int:
    import json

    from h2t_ops.core.envelope import success_envelope
    from h2t_ops.setup import version_check

    vp = argparse.ArgumentParser(prog="h2t-ops version")
    vp.add_argument("--expect", default=None)
    vp.add_argument("--json", action="store_true")
    args = vp.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    result = version_check.check(args.expect if args.expect is not None else h2t_ops.__version__)
    if args.json:
        if result["ok"]:
            envelope = success_envelope("version", result)
        else:
            envelope = {"ok": False, "provider": "version",
                        "error": {"type": "config", "message": _VERSION_MESSAGES[result["reason"]],
                                  "hint": result["hint"]},
                        "result": result}
        print(json.dumps(envelope, ensure_ascii=False))
    else:
        print(result["version"] if result["ok"] else f"{result['reason']}: {result['hint']}")
    return 0 if result["ok"] else 3


def _deploy_dispatch(argv: list[str]) -> int:
    from h2t_ops.deploy.commands import dispatch as deploy_dispatch

    return deploy_dispatch(argv)


def dispatch(argv: list[str]) -> int:
    if argv and argv[0] == "deploy":
        return _deploy_dispatch(argv[1:])
    if argv and argv[0] in ("--help", "-h"):
        build_parser().print_help()
        return 0
    if argv and argv[0] in ("--version", "-V"):
        print(build_info.version_line())
        return 0
    if argv and argv[0] == "version":
        return _version(argv[1:])
    if argv and argv[0] == "doctor":
        return _doctor()
    if argv and argv[0] == "setup":
        # The setup skill's backend, moved from its plugin script as is (Task 12).
        from h2t_ops.setup import legacy
        try:
            return legacy.main(argv[1:])
        except SystemExit as e:  # argparse usage errors and --help
            return e.code if isinstance(e.code, int) else (0 if e.code is None else 2)
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
        # One gather implementation: the package module h2t-gather runs. lib/cli/main.py
        # carried a second copy that never gained find_latest_session_index, so this path
        # silently lost "### Previous Session".
        from h2t_ops.lifecycle import run_main, session_start
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
        return run_main(session_start.main, forwarded[0], forwarded[1:])
    if argv and argv[0] in _MIGRATED:
        return _run_connector(argv)
    if not argv:
        build_parser().print_help()
        return 0
    return _legacy(argv)


def main() -> None:
    # argparse prints --help and usage errors itself, past emit()'s UTF-8 writer, so a
    # cp1252 pipe on Windows died on the first `→` in a help string. meetgeek_cli.py had
    # this guard (#428); it did not come along when the CLI took over its verbs (#541).
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    sys.exit(dispatch(sys.argv[1:]))


if __name__ == "__main__":
    main()
