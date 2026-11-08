"""`h2t-ops settings`: every setting with its value and where it came from (#581)."""
from __future__ import annotations

import argparse

from h2t_ops.core import settings
from h2t_ops.core.errors import UsageError
from h2t_ops.core.output import emit


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise UsageError(message, hint=f"{self.prog} --help")


def _show(value: object) -> str:
    return "—" if value is None else str(value)


def _list(args) -> dict | str:
    rows = settings.rows()
    if args.as_json:
        return {"settings": rows}
    width = max(len(r["key"]) for r in rows)
    return "\n".join(f"{r['key']:<{width}}  {_show(r['value'])}  [{r['source']}]" for r in rows)


def _get(args) -> dict | str:
    got = settings.resolve(args.name)
    if got.source == "unset":
        settings.require(args.name)   # raises ConfigError with the hint
    if args.as_json:
        return {"key": args.name, "value": got.value, "source": got.source}
    return _show(got.value)


def _parser() -> argparse.ArgumentParser:
    p = _Parser(prog="h2t-ops settings")
    sub = p.add_subparsers(dest="cmd", required=True, parser_class=_Parser)
    sub.add_parser("list", help="Every setting: value and source").set_defaults(fn=_list)
    g = sub.add_parser("get", help="One setting; exit 3 if it is unset")
    g.add_argument("name")
    g.set_defaults(fn=_get)
    for s in sub.choices.values():
        s.add_argument("--json", dest="as_json", action="store_true")
    return p


def main(argv: list[str]) -> int:
    fmt = "json" if "--json" in argv else "human"
    try:
        args = _parser().parse_args(argv)
        return emit("settings", result=args.fn(args), fmt=fmt)
    except SystemExit as e:                  # --help
        return e.code if isinstance(e.code, int) else 0
    except Exception as exc:  # noqa: BLE001 — central error→exit mapping, as paths_cli
        return emit("settings", exc=exc, fmt=fmt)
