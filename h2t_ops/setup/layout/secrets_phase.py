"""Layout 1, phase `secrets` (#548 §8 п. 2, п. 6; plan R6, R19, R25, R37, R38).

Every old secret place is read, through core.secrets only (R38), and copied into
secrets/shared and secrets/local; the old files are never changed. Before the first write
the phase journals the set of (key, sha256) pairs and the senior value of every key, so
verify checks the result against what was there, not against what was just written. An
empty value (the skeleton's KEY=) is no value: it neither wins nor counts (Task 10).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from h2t_ops.core import google_auth, paths, providers, secrets
from h2t_ops.core.errors import ConfigError
from h2t_ops.setup.layout import engine, verify

SHARED = "secrets.shared"
LOCAL = "secrets.local"
_HINT = "re-save it as UTF-8 and run `h2t-setup layout migrate` again"


def ladder() -> list[tuple[str, Path]]:
    """Senior first; the list and its dedup live in secrets.migration_sources (plan R38)."""
    return [(name, p) for name, p, _ in secrets.migration_sources()]


def evals_ladder(lad):
    """H2T_EVALS_*: ~/.dor/secrets.env first — the only file evals read in 3.x."""
    return sorted(lad, key=lambda kv: kv[0] != "dor")


def _notion_path() -> Path:
    return paths.legacy("notion.token")


def _telegram_dir() -> Path:
    return paths.legacy("telegram")


def _decoded(read, path: Path):
    try:
        return read()
    except UnicodeDecodeError as exc:
        raise ConfigError(f"{path} is not UTF-8 text ({exc.reason} at byte {exc.start})",
                          hint=_HINT) from exc


def translated_extras() -> list[tuple[str, dict[str, str]]]:
    """Sources that are not env files, under their new key names, junior to every env file
    (§8 п. 2): the notion token file and the telegram config.json."""
    out: list[tuple[str, dict[str, str]]] = []
    tok = _decoded(secrets.notion_legacy_token, _notion_path())
    if tok:
        out.append(("notion-token", {"NOTION_API_TOKEN": tok}))
    cfg = _decoded(secrets.telegram_legacy_config, _telegram_dir() / "config.json")
    if isinstance(cfg, dict):
        vals = {k: str(cfg[s]) for k, s in (("TELEGRAM_API_ID", "api_id"), ("TELEGRAM_API_HASH", "api_hash"))
                if cfg.get(s) not in (None, "")}
        if vals:
            out.append(("telegram-config", vals))
    return out


def _extra_path(name: str) -> Path:
    return _notion_path() if name == "notion-token" else _telegram_dir() / "config.json"


def target_of(key: str) -> str:
    prov = providers.provider_of_key(key)
    return f"{prov}.env" if prov else "other.env"


def _inputs():
    """-> (order senior first, values per source, foreign files, foreign source names, the old
    file of every source). Empty values are dropped here: they are absent for that key."""
    srcs = secrets.migration_sources()
    lad = [(name, p) for name, p, _ in srcs]
    foreign = [p for _, p in lad
               if p.parent == paths.legacy("secrets.h2t") and p.stem != "secrets"
               and not providers.is_package_provider(p.stem)]
    extras = translated_extras()
    sources = {name: {k: v for k, v in vals.items() if v} for name, _, vals in srcs}
    sources.update((name, {k: v for k, v in vals.items() if v}) for name, vals in extras)
    order = [*lad, *((src, None) for src, _ in extras)]   # extras are the most junior
    foreign_srcs = {src for src, p in lad if p in foreign}
    origin = {**dict(lad), **{name: _extra_path(name) for name, _ in extras}}
    return order, sources, foreign, foreign_srcs, origin


def plan_env() -> tuple[dict[str, dict[str, str]], dict[str, dict[str, dict[str, str]]], list[Path]]:
    """-> (winners per target file, losers per target file per source, foreign files to copy)."""
    winners: dict[str, dict[str, str]] = {}
    losers: dict[str, dict[str, dict[str, str]]] = {}
    existing = {name: {k: v for k, v in vals.items() if v}
                for name, vals in secrets.shared_env_values().items() if name.endswith(".env")}
    order_all, sources, foreign, foreign_srcs, _ = _inputs()
    keys = {k for vals in sources.values() for k in vals}
    for key in sorted(keys):
        tgt = target_of(key)
        order = evals_ladder(order_all) if key.startswith("H2T_EVALS_") else order_all
        candidates = [(src, sources[src][key]) for src, _ in order if key in sources[src]]
        if tgt == "other.env":
            candidates = [c for c in candidates if c[0] not in foreign_srcs]
            if not candidates:
                continue
        if key in existing.get(tgt, {}):
            win_src, win_val = "existing", existing[tgt][key]
        else:
            win_src, win_val = candidates[0]
        winners.setdefault(tgt, {})[key] = win_val
        for src, val in candidates:
            if src != win_src and val != win_val:
                losers.setdefault(tgt, {}).setdefault(src, {})[key] = val
    return winners, losers, foreign


def _contributors() -> dict[str, tuple[Path, ...]]:
    """Target file -> every old file that has a value for one of its keys: each gets a
    source row (MOVED-TO.txt), also when its value lost or equalled the winner."""
    _, sources, _, foreign_srcs, origin = _inputs()
    out: dict[str, set[Path]] = {}
    for src, vals in sources.items():
        for key in vals:
            tgt = target_of(key)
            if tgt == "other.env" and src in foreign_srcs:
                continue
            out.setdefault(tgt, set()).add(origin[src])
    return {t: tuple(sorted(ps)) for t, ps in out.items()}


def _line(key: str, val: str) -> str:
    """One KEY=value line that parse_env reads back as exactly `val`."""
    for form in (val, f'"{val}"', f"'{val}'"):
        if secrets.parse_env(f"{key}={form}\n").get(key) == val:
            return f"{key}={form}\n"
    raise ConfigError(f"the value of {key} cannot be written as one env line",
                      hint="edit that value in its old file and run `h2t-setup layout migrate` again")


def _env_bytes(vals: dict[str, str]) -> bytes:
    return "".join(_line(k, v) for k, v in sorted(vals.items())).encode("utf-8")


def _extend(prev: bytes, add: dict[str, str]) -> bytes:
    """`prev` with the keys it lacks: an empty KEY= line takes its value in place (the first
    occurrence is the one parse_env reads), the rest are appended. Nothing else changes."""
    if not add:
        return prev
    pending = dict(add)
    out = []
    for raw in prev.decode("utf-8").splitlines(keepends=True):
        key = next(iter(secrets.parse_env(raw)), None)
        if key in pending:
            body = raw.rstrip("\r\n")
            bom = "﻿" if raw.startswith("﻿") else ""
            raw = bom + _line(key, pending.pop(key)).rstrip("\n") + raw[len(body):]
        out.append(raw)
    text = "".join(out)
    if pending and text and not text.endswith("\n"):
        text += "\n"
    return (text + "".join(_line(k, v) for k, v in sorted(pending.items()))).encode("utf-8")


def _sha(val: str) -> str:
    return hashlib.sha256(val.encode()).hexdigest()


def _snapshot_taken(journal) -> bool:
    """Taken once, before the first write: a file row means the phase has written, and the
    files are no longer what the baseline must describe. Until then a retake (a kill
    between snapshot rows) reads the same untouched files and adds the same rows."""
    return any(r["op"] in ("intent", "created", "replaced", "removed", "source")
               for r in journal.entries())


def _json_doc(raw: bytes, path: Path) -> dict:
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ConfigError(f"{path} is not UTF-8 text (at byte {exc.start})", hint=_HINT) from exc
    try:
        doc = json.loads(text)
    except ValueError as exc:
        # position only: the message of a JSON error can quote the text around it
        where = f"line {exc.lineno} column {exc.colno}" if isinstance(exc, json.JSONDecodeError) else ""
        raise ConfigError(f"{path} is not valid JSON ({where})",
                          hint="fix the JSON or move the file away, then run "
                               "`h2t-setup layout migrate` again") from exc
    if not isinstance(doc, dict):
        raise ConfigError(f"{path} is not a JSON object", hint="fix it or move it away, then run "
                          "`h2t-setup layout migrate` again")
    return doc


def token_bytes(durable: dict) -> bytes:
    """The shape secrets.write_json gives the token, so a login written later is the same file."""
    return json.dumps(durable, ensure_ascii=False, indent=2).encode("utf-8")


def _google_client_sources() -> list[tuple[str, Path]]:
    return [("google-calendar-mcp", paths.legacy("google.store") / "credentials.json"),
            ("gmail", paths.legacy("google.gmail") / "credentials.json"),
            ("dor", paths.legacy("google.dor"))]


def _google_token_sources() -> list[tuple[str, Path]]:
    return [("google-calendar-mcp", paths.legacy("google.store") / "tokens.json"),
            ("gmail", paths.legacy("google.gmail") / "token.json")]


def phase_secrets(ctx) -> None:
    j = ctx.journal
    # Everything is read before the first write: a Telegram that holds its session open
    # stops the phase with nothing written (R25).
    session_src = _telegram_dir() / "session.session"
    session = (engine.quiet_sqlite_bytes(session_src, read=secrets.read_secret_bytes)
               if session_src.is_file() else None)
    winners, losers, foreign = plan_env()
    _, _, _, _, origin = _inputs()
    names = {p: name for name, p in origin.items()}
    contributors = _contributors()
    tokens, unusable = [], []
    for label, src in _google_token_sources():
        if src.is_file():
            durable = google_auth.durable_token(_json_doc(secrets.read_secret_bytes(src), src))
            # without a refresh token it cannot sign in: it must not outrank one that can
            (tokens if durable.get("refresh_token") else unusable).append((label, src, durable))
    if unusable and not tokens:
        ctx.report.notes.append(
            "layout 1: secrets: no refresh_token in " + ", ".join(str(s) for _, s, _ in unusable)
            + "; no Google token copied, sign in with `h2t-ops google auth`")

    if not _snapshot_taken(j):
        j.baseline(verify.baseline())
        for tgt, vals in sorted(winners.items()):
            for key, val in sorted(vals.items()):
                j.winner(tgt, key, _sha(val))

    shared, local = paths.secrets_shared(), paths.secrets_local()
    existing = secrets.shared_env_values()
    for tgt, vals in sorted(winners.items()):
        target = shared / tgt
        srcs = contributors.get(tgt, ())
        have = existing.get(tgt)
        if have is None:
            engine.put(j, target, _env_bytes(vals), place=SHARED, source="migration",
                       keys=tuple(sorted(vals)), sources=srcs)
            continue
        data = _extend(secrets.read_secret_bytes(target), {k: v for k, v in vals.items() if not have.get(k)})
        engine.put_union(j, target, data, place=SHARED,
                         keys=tuple(sorted(secrets.parse_env(data.decode("utf-8")))), sources=srcs)
    for tgt, by_src in sorted(losers.items()):
        for src, vals in sorted(by_src.items()):
            engine.put(j, shared / tgt, _env_bytes(vals), place=SHARED, source=src,
                       keys=tuple(sorted(vals)), sources=(origin[src],))
    for path in foreign:
        data = secrets.read_secret_bytes(path)
        engine.put(j, shared / path.name, data, place=SHARED, source=names[path], source_path=path,
                   keys=tuple(sorted(secrets.parse_env(data.decode("utf-8")))))

    for label, src in _google_client_sources():
        if src.is_file():
            engine.put(j, shared / "google.client.json", secrets.read_secret_bytes(src),
                       place=SHARED, source=label, source_path=src)
    for label, src, durable in tokens:          # transformed, not byte-copied (§4, R37)
        engine.put(j, local / "google.token.json", token_bytes(durable), place=LOCAL,
                   source=label, source_path=src, rule="google-durable", keys=tuple(durable))

    if session is not None:
        # Always through put: Task 9's adapter may have copied it already and Telethon may
        # have changed that copy since — then both are kept, the old one as .from-telegram.
        engine.put(j, local / "telegram.session", session, place=LOCAL, source="telegram",
                   source_path=session_src)
    auth = _telegram_dir() / "auth_state.json"
    if auth.is_file():
        engine.put(j, local / "telegram.auth-state.json", secrets.read_secret_bytes(auth),
                   place=LOCAL, source="telegram", source_path=auth)
