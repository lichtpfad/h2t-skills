"""MeetGeek verbs that keep local state: recovery upload, lake sync, webhook receiver.

Ported from plugins/h2t-ops/skills/meetgeek/scripts/meetgeek_cli.py so that script can be
deleted (#541). API calls go through MeetGeekClient; the local pipeline (ffmpeg, Drive,
uploads manifest) is the package copy of recovery.py. Data paths are the script's, unchanged
— the lake under ~/.dor/lake is subsystem 2's to move (#548).

Imported only from commands.run, so nothing here is loaded to build the parser.
"""
from __future__ import annotations

import glob
import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from h2t_ops.core.errors import H2TError, ProviderError, UsageError

from . import recovery


def _cursor_path_default() -> Path:
    # meetgeek_cli.py's CURSOR_PATH_DEFAULT, resolved per call rather than at import.
    return Path.home() / ".dor" / "lake" / "_cursors" / "meetgeek.json"


SYNC_INCLUDE = {"transcripts", "summaries", "highlights", "insights", "recordings"}


def _typed(exc: recovery.RecoveryError) -> H2TError:
    """The script exited with RecoveryError.exit_code; 2 there was a usage error."""
    return UsageError(str(exc)) if exc.exit_code == 2 else ProviderError(str(exc))


# ─── Recovery verbs ───────────────────────────────────────────────────────────

def convert(args: Any) -> Any:
    src = Path(args.input).expanduser().resolve()
    if not src.exists():
        raise ProviderError(f"input not found: {src}")
    out_path = Path(args.output).expanduser() if args.output else None
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

    raw_path = Path(args.from_file).expanduser()
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


def _load_cursor(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            pass
    return {}


def _save_cursor(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_manifest_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    seen: set[str] = set()
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if rec.get("meeting_id"):
                seen.add(rec["meeting_id"])
    return seen


def _write_pair(folder: Path, mid: str, md: str, raw: dict) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{mid}.md").write_text(md, encoding="utf-8")
    (folder / f"{mid}.json").write_text(json.dumps(raw, ensure_ascii=False, indent=2),
                                        encoding="utf-8")


def _sync_once(client: Any, args: Any) -> dict:
    from .commands import (
        _fmt_highlights_md,
        _fmt_insights_md,
        _fmt_summary_md,
        _fmt_transcript_md,
        _normalize_meeting,
    )

    lake = Path(args.to).expanduser()
    lake.mkdir(parents=True, exist_ok=True)
    include = {p.strip() for p in (args.include or "transcripts").split(",") if p.strip()}
    unknown = include - SYNC_INCLUDE
    if unknown:
        raise UsageError(f"unknown --include values: {unknown} (valid: {sorted(SYNC_INCLUDE)})")

    cursor_path = Path(args.cursor_file).expanduser() if args.cursor_file else _cursor_path_default()
    cursor = _load_cursor(cursor_path)
    cursor_ts: str | None = None
    from_date = args.since
    cached_ts = cursor.get("last_seen_ts")
    if args.since_cursor and isinstance(cached_ts, str):
        cursor_ts = cached_ts
        from_date = cursor_ts[:10]

    manifest_path = lake / "manifest.jsonl"
    seen_ids = _read_manifest_ids(manifest_path)
    manifest_lines: list[str] = []
    count = skipped = errors = 0
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
        try:
            if "transcripts" in include:
                t = client.get_transcript(mid)
                if not meta["attendees"]:
                    meta["attendees"] = _speakers(t)
                _write_pair(lake / "transcripts", mid, _fmt_transcript_md(m, t), t)
            if "summaries" in include:
                s = client.get_summary(mid)
                _write_pair(lake / "summaries", mid, _fmt_summary_md(m, s), s)
            if "highlights" in include:
                h = client.get_highlights(mid)
                _write_pair(lake / "highlights", mid, _fmt_highlights_md(m, h), h)
            if "insights" in include:
                i = client.get_insights(mid)
                _write_pair(lake / "insights", mid, _fmt_insights_md(m, i), i)
            if "recordings" in include:
                url = client.get_download_url(mid)["download_url"]
                rec_path = lake / "recordings" / f"{mid}.mp4"
                if not rec_path.exists():
                    client.download_to(url, rec_path)
        except H2TError as e:
            errors += 1
            print(f"WARN: skip {mid}: {e}", file=sys.stderr)
            continue

        manifest_lines.append(json.dumps(meta, ensure_ascii=False))
        seen_ids.add(mid)
        count += 1
        if ts and (last_seen_ts is None or ts > last_seen_ts):
            last_seen_ts = ts
            last_seen_id = mid

    if manifest_lines:
        with manifest_path.open("a", encoding="utf-8") as f:
            for line in manifest_lines:
                f.write(line + "\n")

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
    _save_cursor(cursor_path, cursor)
    return {"synced": count, "skipped": skipped, "errors": errors, "cursor": str(cursor_path)}


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

def webhook_server(args: Any) -> dict:
    """Minimal HTTP server that dumps incoming POSTs as JSON files."""
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from uuid import uuid4

    from h2t_ops.core import secrets

    out_dir = Path(args.out).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)
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
                "path": self.path,
                "headers": {k: v for k, v in self.headers.items()},
                "payload": payload,
            }
            (out_dir / f"{uuid4()}.json").write_text(
                json.dumps(event, ensure_ascii=False, indent=2), encoding="utf-8"
            )
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
