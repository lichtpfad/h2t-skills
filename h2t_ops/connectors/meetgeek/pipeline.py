"""MeetGeek verbs that keep local state: recovery upload, lake sync, webhook receiver.

Ported from plugins/h2t-ops/skills/meetgeek/scripts/meetgeek_cli.py so that script can be
deleted (#541). API calls go through MeetGeekClient; the local pipeline (ffmpeg, Drive,
uploads manifest) is the package copy of recovery.py. Lake files go through core.lake (own
files only, manifest protocol), cursors live in state/cursors (#548).

Imported only from commands.run, so nothing here is loaded to build the parser.
"""
from __future__ import annotations

import glob
import json
import os
import sys
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from h2t_ops.core import lake as _lake
from h2t_ops.core import paths, store
from h2t_ops.core.errors import H2TError, ProviderError, UsageError

from . import recovery

SYNC_INCLUDE = {"transcripts", "summaries", "highlights", "insights", "recordings"}


def _typed(exc: recovery.RecoveryError) -> H2TError:
    """The script exited with RecoveryError.exit_code; 2 there was a usage error."""
    return UsageError(str(exc)) if exc.exit_code == 2 else ProviderError(str(exc))


# ─── Recovery verbs ───────────────────────────────────────────────────────────

def convert(args: Any) -> Any:
    src = paths.expand_user_dest(args.input).resolve()
    if not src.exists():
        raise ProviderError(f"input not found: {src}")
    out_path = paths.expand_user_dest(args.output) if args.output else None
    try:
        probe = recovery.ffmpeg_probe(str(src))
        if args.probe:
            return probe
        result = recovery.convert_media(src, audio_only=args.audio_only, mix_mode=args.mix_mode,
                                        output_path=out_path, probe=probe)
    except recovery.RecoveryError as e:
        raise _typed(e) from e
    return str(result)


def drive_upload(args: Any) -> dict:
    try:
        return recovery.drive_upload_file(Path(args.file), folder=args.folder,
                                          make_public=args.make_public)
    except recovery.RecoveryError as e:
        raise _typed(e) from e


def drive_audit(args: Any) -> dict:
    try:
        return recovery.drive_audit_public(revoke=args.revoke, min_age_hours=args.min_age_hours)
    except recovery.RecoveryError as e:
        raise _typed(e) from e


def staging_purge(args: Any) -> dict:
    try:
        return recovery.purge_staging(min_age_hours=args.min_age_hours, dry_run=args.dry_run,
                                      verify_drive=args.verify_drive)
    except recovery.RecoveryError as e:
        raise _typed(e) from e


def upload(args: Any) -> dict:
    if args.download_url:
        try:
            resp = recovery.submit_url_via_h2t_ops(args.download_url, args.title, args.language)
        except recovery.RecoveryError as e:
            raise _typed(e) from e
        return {"status": "submitted", "response": resp}

    if not args.from_file:
        raise UsageError("either --download-url or --from-file required")

    raw_path = paths.expand_user_dest(args.from_file)
    if raw_path.is_dir():
        expanded = sorted(raw_path.rglob("*.webm"))
    elif raw_path.is_file():
        expanded = [raw_path]
    else:
        expanded = sorted(Path(p) for p in glob.glob(str(raw_path), recursive=True))
    if not expanded:
        raise ProviderError(f"no files match: {args.from_file}")

    manifest_path = recovery.uploads_manifest_path()
    processed = skipped = errors = 0
    results: list[dict] = []
    total = len(expanded)
    for i, src_path in enumerate(expanded, 1):
        if not src_path.is_file():
            continue
        size = src_path.stat().st_size
        # Re-read per file: two copies of one recording in the same batch (see the script).
        state = recovery.read_uploads_manifest(manifest_path)
        done = (recovery.submitted_record(state, str(src_path.resolve()))
                if args.skip_existing else None)
        if done is not None:
            submitted_size = done.get("source_size_bytes")
            note = ("" if submitted_size == size
                    else f" — submitted copy was {submitted_size} B, this one {size} B")
            print(f"[{i}/{total}] {src_path.name}  skip (already submitted){note}",
                  file=sys.stderr)
            skipped += 1
            continue
        if args.dry_run:
            print(f"[{i}/{total}] {src_path.name}  would: convert+drive+upload", file=sys.stderr)
            continue
        try:
            print(f"[{i}/{total}] {src_path.name}  convert ...", file=sys.stderr)
            results.append(recovery.process_one(
                src_path, language=args.language, title_override=args.title,
                audio_only=args.audio_only, mix_mode=args.mix_mode,
                manifest_path=manifest_path,
            ))
            processed += 1
            print(f"[{i}/{total}] {src_path.name}  ✓ submitted", file=sys.stderr)
        except (H2TError, recovery.RecoveryError) as e:
            # process_one already journalled the failing stage.
            print(f"[{i}/{total}] {src_path.name}  ✗ {e}", file=sys.stderr)
            errors += 1

    report: dict[str, Any] = {
        "processed": processed, "skipped": skipped, "errors": errors,
        "drive_folder": f"{recovery.DRIVE_ROOT_FOLDER_NAME}/{datetime.now(UTC).strftime('%Y-%m-%d')}",
        "results_count": len(results),
    }
    if args.housekeeping and not args.dry_run:
        print(f"housekeeping (>{recovery.HOUSEKEEPING_MIN_AGE_HOURS:g}h) ...", file=sys.stderr)
        report["housekeeping"] = recovery.run_housekeeping(manifest_path=manifest_path)
    if errors:
        raise ProviderError(f"upload: {errors} of {total} file(s) failed", details=report)
    return report


# ─── Recording download ───────────────────────────────────────────────────────

def download(args: Any) -> str:
    """Signed recording URL, or the file written to --output (as the script printed)."""
    from .client import MeetGeekClient

    client = MeetGeekClient()
    url = client.get_download_url(args.meeting_id)["download_url"]
    if not args.output:
        return url
    client.download_to(url, Path(args.output))
    return args.output


# ─── Lake sync ────────────────────────────────────────────────────────────────

def _iter_meetings(client: Any, *, limit: int | None, from_date: str | None,
                   to_date: str | None):
    max_pages = int(os.environ.get("MEETGEEK_MAX_PAGES", "1000"))
    fetched = pages = 0
    cursor: str | None = None
    while True:
        if pages >= max_pages:
            print(f"WARN: max pages ({max_pages}) reached, stopping", file=sys.stderr)
            return
        page = client.list_meetings(cursor=cursor, from_date=from_date, to_date=to_date)
        items = page["rows"]
        for m in items:
            yield m
            fetched += 1
            if limit and fetched >= limit:
                return
        cursor = page.get("next_cursor")
        if not cursor or not items:
            return
        pages += 1


def _read_manifest_ids(lake: _lake.ConnectorDir) -> set[str]:
    """Meetings a committed row (or a 3.x row, which has no state) already carries. A row
    with refused files is not a synced meeting: the next run fetches it again."""
    return {r["meeting_id"] for r in lake.committed_rows()
            if r.get("meeting_id") and not r.get("refused")}


def _pair(part: str, mid: str, md: str, raw: dict) -> dict[str, bytes]:
    return {f"{part}/{mid}.md": md.encode("utf-8"),
            f"{part}/{mid}.json": json.dumps(raw, ensure_ascii=False, indent=2).encode("utf-8")}


def _sync_once(client: Any, args: Any) -> dict:
    from .commands import (
        _fmt_highlights_md,
        _fmt_insights_md,
        _fmt_summary_md,
        _fmt_transcript_md,
        _normalize_meeting,
    )

    lake = _lake.ConnectorDir("meetgeek", root=paths.expand_user_dest(args.to))
    lake.recover()
    include = {p.strip() for p in (args.include or "transcripts").split(",") if p.strip()}
    unknown = include - SYNC_INCLUDE
    if unknown:
        raise UsageError(f"unknown --include values: {unknown} (valid: {sorted(SYNC_INCLUDE)})")

    cursor_path = paths.expand_user_dest(args.cursor_file) if args.cursor_file else None
    cursor = _lake.read_cursor("meetgeek", cursor_path)
    cursor_ts: str | None = None
    from_date = args.since
    cached_ts = cursor.get("last_seen_ts")
    if args.since_cursor and isinstance(cached_ts, str):
        cursor_ts = cached_ts
        from_date = cursor_ts[:10]

    seen_ids = _read_manifest_ids(lake)
    count = skipped = errors = refused_n = 0
    last_seen_ts: str | None = cursor.get("last_seen_ts")
    last_seen_id: str | None = cursor.get("last_seen_id")

    for m in _iter_meetings(client, limit=args.limit, from_date=from_date, to_date=args.to_date):
        meta = _normalize_meeting(m)
        mid = meta["meeting_id"]
        if not mid:
            continue
        if mid in seen_ids:
            skipped += 1
            continue
        ts = meta.get("timestamp_start_utc")
        if cursor_ts and ts and ts <= cursor_ts:
            skipped += 1
            continue
        files: dict[str, Any] = {}
        try:
            if "transcripts" in include:
                t = client.get_transcript(mid)
                if not meta["attendees"]:
                    meta["attendees"] = _speakers(t)
                files.update(_pair("transcripts", mid, _fmt_transcript_md(m, t), t))
            if "summaries" in include:
                s = client.get_summary(mid)
                files.update(_pair("summaries", mid, _fmt_summary_md(m, s), s))
            if "highlights" in include:
                h = client.get_highlights(mid)
                files.update(_pair("highlights", mid, _fmt_highlights_md(m, h), h))
            if "insights" in include:
                i = client.get_insights(mid)
                files.update(_pair("insights", mid, _fmt_insights_md(m, i), i))
            if "recordings" in include:
                url = client.get_download_url(mid)["download_url"]
                # Chunks, spooled and hashed by publish: an own recording is replaced, a new
                # one created, a foreign one refused (R29, R47).
                files[f"recordings/{mid}.mp4"] = client.iter_download(url)
            refused = lake.publish(files, op_id=uuid.uuid4().hex, meta=meta)
        except H2TError as e:
            errors += 1
            print(f"WARN: skip {mid}: {e}", file=sys.stderr)
            continue

        if refused:
            refused_n += 1
            print(f"WARN: {mid}: not replacing files the package did not write: {', '.join(refused)}",
                  file=sys.stderr)
            continue
        seen_ids.add(mid)
        count += 1
        if ts and (last_seen_ts is None or ts > last_seen_ts):
            last_seen_ts = ts
            last_seen_id = mid

    if refused_n:
        # A meeting with a refused file is not synced; --since-cursor must list it again.
        last_seen_ts, last_seen_id = cursor.get("last_seen_ts"), cursor.get("last_seen_id")
    cursor.update({
        "source": "meetgeek",
        "cursor_type": "timestamp",
        "last_seen_ts": last_seen_ts,
        "last_seen_id": last_seen_id,
        "last_run_at": recovery.now_iso(),
        "last_run_status": "ok" if errors == 0 else f"partial({errors})",
        "items_ingested": cursor.get("items_ingested", 0) + count,
        "version": 1,
    })
    written = _lake.write_cursor("meetgeek", cursor, cursor_path)
    return {"synced": count, "skipped": skipped, "errors": errors, "refused": refused_n,
            "cursor": str(written)}


def _speakers(transcript: dict) -> list[str]:
    seen: list[str] = []
    for s in transcript.get("sentences") or transcript.get("transcript") or []:
        sp = (s.get("speaker") or s.get("speaker_name") or "").strip()
        if sp and sp not in seen:
            seen.append(sp)
    return seen


def sync(args: Any) -> dict:
    from .client import MeetGeekClient

    client = MeetGeekClient()
    if not getattr(args, "watch", None):
        report = _sync_once(client, args)
        if report["errors"]:
            raise ProviderError(f"sync: {report['errors']} meeting(s) failed", details=report)
        return report
    interval = max(int(args.watch), 30)
    print(f"watch mode: interval={interval}s, --since-cursor={args.since_cursor}", file=sys.stderr)
    runs = 0
    while True:
        try:
            report = _sync_once(client, args)
            runs += 1
            print("synced={synced} skipped={skipped} errors={errors} cursor={cursor}".format(**report),
                  file=sys.stderr)
        except H2TError as e:
            print(f"WARN run failed: {e}", file=sys.stderr)
        try:
            time.sleep(interval)
        except KeyboardInterrupt:
            print("\nwatch stopped", file=sys.stderr)
            return {"watch_stopped": True, "runs": runs}


# ─── Webhook receiver ─────────────────────────────────────────────────────────

_SECRET_HEADERS = {"authorization", "proxy-authorization", "cookie", "set-cookie"}
_SECRET_WORDS = ("secret", "token", "key", "auth", "signature", "password")


def _safe_headers(items) -> dict[str, str]:
    """Request headers without credentials: the event file lands in the synced lake."""
    out = {}
    for k, v in items:
        name = k.lower()
        if name in _SECRET_HEADERS or any(w in name for w in _SECRET_WORDS):
            continue
        out[k] = v
    return out


def webhook_server(args: Any) -> dict:
    """Minimal HTTP server that dumps incoming POSTs as JSON files."""
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from urllib.parse import urlsplit
    from uuid import uuid4

    from h2t_ops.core import secrets

    out_dir = (paths.expand_user_dest(args.out) if args.out
               else _lake.ConnectorDir("meetgeek").root / "webhooks")
    place, user = _lake.origin(out_dir)
    store.mkdir(out_dir, place=place, dest=user)
    if args.secret is None:
        args.secret = secrets.get("MEETGEEK_WEBHOOK_SECRET") or ""
    secret = (args.secret or "").strip()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *a):  # noqa: A002 — base class signature
            sys.stderr.write(f"[webhook] {self.address_string()} - {format % a}\n")

        def _reply(self, code: int, body: str = ""):
            self.send_response(code)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            if body:
                self.wfile.write(body.encode("utf-8"))

        def do_POST(self):
            if secret and self.headers.get("X-Webhook-Secret", "") != secret:
                return self._reply(401, "unauthorized\n")
            length = int(self.headers.get("Content-Length", "0") or 0)
            raw = self.rfile.read(length) if length else b""
            try:
                payload = json.loads(raw.decode("utf-8")) if raw else {}
            except (UnicodeDecodeError, ValueError):
                payload = {"_raw_base64": raw.hex()}
            event = {
                "received_at": recovery.now_iso(),
                # No query string: a secret in the hook URL (?token=…) must not reach the lake.
                "path": urlsplit(self.path).path,
                "headers": _safe_headers(self.headers.items()),
                "payload": payload,
            }
            try:
                store.create(out_dir / f"{uuid4()}.json",
                             json.dumps(event, ensure_ascii=False, indent=2), place=place, dest=user)
            except store.AlreadyExists:
                pass                    # that event is already on disk
            self._reply(200, "ok\n")

        def do_GET(self):  # health probe
            self._reply(200, "meetgeek webhook receiver\n")

    server = ThreadingHTTPServer((args.bind, args.port), Handler)
    print(f"webhook-server: bind={args.bind}:{args.port} out={out_dir} "
          f"secret={'set' if secret else 'none'}", file=sys.stderr)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped", file=sys.stderr)
    finally:
        server.server_close()
    return {"stopped": True, "out": str(out_dir)}


VERBS = {
    "convert": convert,
    "drive-upload": drive_upload,
    "drive-audit": drive_audit,
    "staging-purge": staging_purge,
    "upload": upload,
    "download": download,
    "sync": sync,
    "webhook-server": webhook_server,
}
