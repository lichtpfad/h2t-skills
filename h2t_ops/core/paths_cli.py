"""`h2t-ops paths` and `h2t-ops index` (#548 §3, §5, §6).

paths: where each place is and why (list), one path for a skill or another program to ask
instead of spelling it (get), and the one supported edit of paths.yaml (set). index: build
state/index.sqlite again, and ask it for a project's sessions.
"""
from __future__ import annotations

import argparse
import io
import re

from h2t_ops.core import paths
from h2t_ops.core.errors import ConfigError, UsageError
from h2t_ops.core.output import emit

_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_REPO = "cwd or --repo-root of each command"


class _Parser(argparse.ArgumentParser):
    """A usage error is UsageError (exit 2 through emit), not argparse's own exit."""

    def error(self, message):
        raise UsageError(message, hint=f"{self.prog} --help")


def _rows() -> tuple[list[dict], str | None]:
    """One row per place, and the paths.yaml error if the file is broken: list is how the
    user finds out what to repair, so a broken file is shown, not raised."""
    try:
        declared, broken = paths.paths_config().places, None
    except ConfigError as exc:
        declared, broken = {}, str(exc)
    rows = []
    for p in paths.PLACES:
        if p.id == "repo":
            where, source = None, _REPO
        elif p.id in paths.YAML_PLACES:
            if p.id in declared:
                where, source = declared[p.id], "paths.yaml"
            elif broken:
                where, source = None, "paths.yaml (broken)"
            else:
                where, source = paths.data_dir() / p.id, "default (not set)"
        else:
            where, source = paths.dir_of(p.id), paths.source(p.id)
        rows.append({"id": p.id, "path": str(where) if where else None, "kind": p.kind,
                     "sync": p.sync, "exists": bool(where and where.exists()), "source": source})
    return rows, broken


def _list(args) -> dict | str:
    rows, broken = _rows()
    old = [{"name": n, "note": "not read"} for n in paths.old_env_in_use()]
    if args.as_json:
        return {"places": rows, "old_env": old, "problem": broken}
    width = max(len(r["id"]) for r in rows)
    lines = [f"{r['id']:<{width}}  {r['path'] or '—'}  [{r['kind']}, sync {r['sync']}, "
             f"{'exists' if r['exists'] else 'missing'}]  {r['source']}" for r in rows]
    lines += [f"{o['name']} is set: not read by 4.0 (h2t-ops doctor says what replaces it)"
              for o in old]
    if broken:
        lines.append(f"paths.yaml is broken: {broken}")
    return "\n".join(lines)


def _get(args) -> str:
    key = args.id
    kind, _, name = key.partition(":")
    if key == "repo":
        raise UsageError("repo has no single path: it is the directory a command runs in",
                         hint="pass --repo-root to the command, or run it inside the repository")
    if name and kind in ("secret", "data"):
        if kind == "secret":
            from h2t_ops.core import secrets
            try:
                return str(secrets.json_path(name))     # google.token, google.client, …
            except KeyError:
                pass
            if _NAME.match(name) and ".." not in name:
                return str(secrets.provider_file(name))
        elif all(_NAME.match(part) and part != ".." for part in name.split("/")):
            return str(paths.data_dir() / name)
        raise UsageError(f"{key!r}: not a name", hint="letters, digits, . _ - (data: also /)")
    if key in paths.YAML_PLACES:
        return str(paths.place_or_default(key)[0])
    if key in {p.id for p in paths.PLACES}:
        return str(paths.dir_of(key))
    raise UsageError(f"unknown place {key!r}",
                     hint=f"one of: {', '.join(p.id for p in paths.PLACES)}, secret:<provider>, data:<name>")


def _set(args) -> dict | str:
    from ruamel.yaml import YAML
    from ruamel.yaml.comments import CommentedMap
    from ruamel.yaml.error import YAMLError

    from h2t_ops.core import backups, store

    name, value = args.place, args.path
    if name == "vault":
        raise UsageError("vault is not set in paths.yaml",
                         hint=paths.VAULT_HINT)
    if name not in paths.YAML_PLACES:
        raise UsageError(f"{name!r} cannot be set", hint=f"places set here: {', '.join(paths.YAML_PLACES)}")
    f = paths.paths_yaml()
    yaml = YAML()
    yaml.preserve_quotes = True

    def once() -> dict:
        seen = store.stamp(f)                   # before the read: what replace(expect=) holds
        old = f.read_bytes() if seen is not None else None
        doc, unreadable = None, False
        if old is not None:
            try:
                doc = yaml.load(old.decode("utf-8-sig"))
            except (UnicodeDecodeError, YAMLError):
                unreadable = True
            unreadable = unreadable or doc is not None and not isinstance(doc, dict)
        if not isinstance(doc, dict):
            doc = CommentedMap()
        dropped = _repair(doc, name, f)
        doc["places"][name] = value
        # The new document is what is checked (R34): the old one may be the broken file this
        # command is repairing, and an overlap with a valid place leaves the file as it was.
        paths.validate_config(doc, source=f)
        backup = backups.save_backup(f) if old is not None else None
        buf = io.StringIO()
        yaml.dump(doc, buf)
        store.replace(f, buf.getvalue(), place="config", expect=seen)
        return {"place": name, "path": value, "file": str(f),
                "backup": str(backup) if backup else None,
                "repaired": unreadable or bool(dropped), "unreadable": unreadable, "dropped": dropped}

    for _ in range(_SET_TRIES):
        try:
            result = once()
            break
        except store.Changed:
            continue                            # another writer saved in between: read again
    else:
        raise ConfigError(f"{f} kept changing while it was being set ({_SET_TRIES} tries)",
                          hint="another program is writing it; retry, or edit it once it stops")
    if args.as_json:
        return result
    lines = [f"{name}: {value} (in {f})"]
    if result["unreadable"]:
        lines.append(f"the old file did not parse; it was rewritten with {name} only")
    lines += [f"dropped {d}" for d in result["dropped"]]
    if result["repaired"]:
        lines.append(f"the old content is saved in {result['backup']}")
    return "\n".join(lines)


_SET_TRIES = 3


def _repair(doc, name: str, f) -> list[str]:
    """Make `doc` a document `set` can write, in place, keeping comments: what is invalid on
    its own goes, with the reason — a places that is not a mapping, vault, an unknown name, a
    path that fails the checks — and so does a sync that is not a mapping. A version other
    than 1 is not repaired: that may be a newer file, and the final check refuses it."""
    from ruamel.yaml.comments import CommentedMap

    dropped: list[str] = []
    sync = doc.get("sync")
    if sync is not None and not isinstance(sync, dict):
        del doc["sync"]
        dropped.append(f"sync: not a mapping ({type(sync).__name__})")
    places = doc.get("places")
    if places is not None and not isinstance(places, dict):
        dropped.append(f"places: not a mapping ({type(places).__name__})")
        places = None
    if places is None:
        doc["places"] = places = CommentedMap()
    kept: dict = {}
    for key in list(places):
        if key == name:
            continue                            # replaced by the value being set
        try:
            if key == "vault":
                raise ConfigError("vault", hint=paths.VAULT_HINT)
            paths.validate_config({"places": {**kept, key: places[key]}}, source=f)
            kept[key] = places[key]
        except ConfigError as exc:
            del places[key]
            dropped.append(f"places.vault: {paths.VAULT_HINT}" if key == "vault"
                           else f"places.{key}: {str(exc).removeprefix(f'{f}: ')}")
    return dropped


def _rebuild(args) -> dict | str:
    from h2t_ops.lifecycle import index
    counts = index.rebuild()
    if args.as_json:
        return {"path": str(index.query.index_path()), **counts}
    return (f"rebuilt {index.query.index_path()}: {counts['sessions']} sessions, "
            f"{counts['projects']} projects, {counts['problems']} problems")


def _query(args) -> dict | str:
    from h2t_ops.lifecycle import index
    sessions, problems = index.latest_sessions([args.project], limit=args.limit), index.problems()
    if args.as_json:
        return {"project": args.project, "sessions": sessions, "problems": problems}
    lines = [f"{s['updated_at'] or '?'}  {s['machine']}  {s['session_id']}  {s['path']}"
             for s in sessions] or [f"no sessions of {args.project} in the index"]
    lines += [f"problem: {p['path']}: {p['error']}" for p in problems]
    return "\n".join(lines)


def _parser(command: str) -> argparse.ArgumentParser:
    p = _Parser(prog=f"h2t-ops {command}")
    sub = p.add_subparsers(dest="cmd", required=True, parser_class=_Parser)
    if command == "paths":
        sub.add_parser("list", help="Every place: path, kind, sync, source").set_defaults(fn=_list)
        g = sub.add_parser("get", help="One path: a place id, secret:<provider> or data:<name>")
        g.add_argument("id")
        g.set_defaults(fn=_get)
        s = sub.add_parser("set", help="Set lake, inbox or kb in paths.yaml")
        s.add_argument("place")
        s.add_argument("path")
        s.set_defaults(fn=_set)
    else:
        sub.add_parser("rebuild", help="Build state/index.sqlite again").set_defaults(fn=_rebuild)
        q = sub.add_parser("query", help="Newest sessions of a project, every machine")
        q.add_argument("--project", required=True)
        q.add_argument("--limit", type=int, default=5)
        q.set_defaults(fn=_query)
    for s in sub.choices.values():
        s.add_argument("--json", dest="as_json", action="store_true")
    return p


def main(command: str, argv: list[str]) -> int:
    fmt = "json" if "--json" in argv else "human"
    try:
        args = _parser(command).parse_args(argv)
        return emit(command, result=args.fn(args), fmt=fmt)
    except SystemExit as e:                  # --help
        return e.code if isinstance(e.code, int) else 0
    except Exception as exc:  # noqa: BLE001 — central error→exit mapping, as _run_connector
        return emit(command, exc=exc, fmt=fmt)
