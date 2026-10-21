"""`h2t-ops sessions`: list (default), status, backfill."""

from __future__ import annotations

import argparse

from h2t_ops.core.errors import UsageError
from h2t_ops.core.output import emit
from h2t_ops.lifecycle.index import query
from h2t_ops.lifecycle.pulse import backfill, record, status, view

_COMMANDS = ("list", "status", "backfill")


class _Parser(argparse.ArgumentParser):
    """A usage error is UsageError (exit 2 through emit), not argparse's own exit."""

    def error(self, message):
        raise UsageError(message, hint=f"{self.prog} --help")


def _parser() -> argparse.ArgumentParser:
    p = _Parser(prog="h2t-ops sessions")
    sub = p.add_subparsers(dest="cmd", required=True, parser_class=_Parser)
    ls = sub.add_parser("list", help="Sessions by domain, project, repo, branch (default)")
    for flag in ("domain", "project", "repo", "status", "pr", "tool"):
        ls.add_argument(f"--{flag}")
    ls.add_argument("--since", help="YYYY-MM-DD: sessions started on or after it")
    ls.add_argument("--all", action="store_true", help="Also machine, unknown and empty sessions")
    ls.set_defaults(fn=_list)
    sub.add_parser("status", help="Refresh PR and issue status of every branch (gh, network)") \
        .set_defaults(fn=_status)
    sub.add_parser("backfill", help="Write records for sessions the hook missed") \
        .set_defaults(fn=_backfill)
    for s in sub.choices.values():
        s.add_argument("--json", dest="as_json", action="store_true")
    return p


def _list(args) -> dict | list | str:
    record.settle_open()
    with query.connect() as conn:
        status.local_status(conn)
    found = view.rows(view.Filters(domain=args.domain, project=args.project, repo=args.repo,
                                   status=args.status, pr=args.pr, tool=args.tool,
                                   since=args.since, all=args.all))
    if args.as_json:
        return found
    if not found:
        return "нет сессий"
    hidden = "" if args.all else "; пустые и машинные скрыты (--all)"
    return view.render(found, f"сессий: {len(found)}{hidden}")


def _status(args) -> dict | str:
    with query.connect() as conn:
        n = status.refresh(conn)
    return {"branches": n} if args.as_json else f"веток обновлено: {n}"


def _backfill(args) -> dict | str:
    counts = backfill.run()
    return counts if args.as_json else ", ".join(f"{k}: {v}" for k, v in counts.items())


def main(argv: list[str]) -> int:
    argv = list(argv)
    if not argv or (argv[0] not in _COMMANDS and argv[0].startswith("-") and argv[0] not in ("-h", "--help")):
        argv = ["list", *argv]
    fmt = "json" if "--json" in argv else "human"
    try:
        args = _parser().parse_args(argv)
        return emit("sessions", result=args.fn(args), fmt=fmt)
    except SystemExit as e:                  # --help
        return e.code if isinstance(e.code, int) else 0
    except Exception as exc:  # noqa: BLE001 — central error→exit mapping, as paths_cli
        return emit("sessions", exc=exc, fmt=fmt)
