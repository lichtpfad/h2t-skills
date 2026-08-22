#!/usr/bin/env python3
"""
MeetGeek API CLI — list, get, transcript, summary, highlights, insights,
download, sync, auth-check, teams.

Bypasses broken Drive auto-sync (re-transcription bug, POS#80) by pulling
originals directly from MeetGeek Public API.

Auth: MEETGEEK_API_KEY env (loaded from ~/.dor/secrets/secrets.env if present).
Base URL: MEETGEEK_BASE_URL env, default https://api.meetgeek.ai.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

try:
    import requests
except ImportError:
    print("ERROR: 'requests' not installed. Run: pip install requests", file=sys.stderr)
    sys.exit(2)

def _load_secret_env_files() -> None:
    """Load canonical then legacy h2t secrets files without overriding env."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    override = os.environ.get("H2T_SECRETS_FILE")
    paths = [Path(override)] if override else [
        Path.home() / ".dor" / "secrets" / "secrets.env",
        Path.home() / ".dor" / "secrets.env",
    ]
    for path in paths:
        load_dotenv(path, override=False)


_load_secret_env_files()

# ─── Recovery module ──────────────────────────────────────────────────────────
import sys as _sys_r
from pathlib import Path as _Path_r
_sys_r.path.insert(0, str(_Path_r(__file__).parent))
from recovery import (  # noqa: E402
    RecoveryError,
    now_iso as _now_iso,
    staging_dir as _staging_dir,
    ffmpeg_exe as _ffmpeg_exe,
    ffmpeg_probe as _ffmpeg_probe,
    build_convert_cmd as _build_convert_cmd,
    convert_media,
    drive_service as _drive_service,
    drive_upload_file as _drive_upload_file,
    drive_audit_public as _drive_audit_public,
    drive_download_url as _drive_download_url,
    submit_url_via_h2t_ops as _submit_url_via_h2t_ops,
    title_from_filename as _title_from_filename,
    DRIVE_ROOT_FOLDER_NAME,
    uploads_manifest_path as _uploads_manifest_path,
    read_uploads_manifest as _read_uploads_manifest,
    append_uploads_manifest as _append_uploads_manifest,
    is_already_submitted as _is_already_submitted,
    process_one as _process_one_for_upload,
    emit_submission_artifact,
)

API_KEY = os.environ.get("MEETGEEK_API_KEY", "").strip()
BASE_URL = os.environ.get("MEETGEEK_BASE_URL", "https://api.meetgeek.ai").rstrip("/")
TIMEOUT = int(os.environ.get("MEETGEEK_TIMEOUT", "30"))
MAX_PAGES = int(os.environ.get("MEETGEEK_MAX_PAGES", "1000"))
CURSOR_PATH_DEFAULT = Path.home() / ".dor" / "lake" / "_cursors" / "meetgeek.json"


# ─── HTTP ─────────────────────────────────────────────────────────────────────

class ApiError(Exception):
    """Raised on any non-2xx API response or network failure. Carries exit code."""
    def __init__(self, message: str, exit_code: int = 1):
        super().__init__(message)
        self.exit_code = exit_code


def _headers() -> dict[str, str]:
    if not API_KEY:
        raise ApiError(
            "MEETGEEK_API_KEY not set.\n"
            "Hint: export MEETGEEK_API_KEY=... or add to ~/.dor/secrets/secrets.env\n"
            "Registry: ~/.h2t/config/secrets/meetgeek.md",
            exit_code=1,
        )
    return {
        "Authorization": f"Bearer {API_KEY}",
        "Accept": "application/json",
    }


def _request(method: str, path: str, *, params: dict | None = None,
             json_body: Any = None, retries: int = 3) -> requests.Response:
    url = f"{BASE_URL}{path}" if path.startswith("/") else f"{BASE_URL}/{path}"
    backoff = 1.0
    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            r = requests.request(
                method, url,
                headers=_headers(),
                params=params,
                json=json_body,
                timeout=TIMEOUT,
            )
        except requests.RequestException as e:
            last_exc = e
            if attempt + 1 == retries:
                break
            time.sleep(backoff)
            backoff *= 2
            continue

        if r.status_code == 429:
            retry_after = float(r.headers.get("Retry-After", backoff))
            time.sleep(retry_after)
            backoff *= 2
            continue
        if 500 <= r.status_code < 600 and attempt + 1 < retries:
            time.sleep(backoff)
            backoff *= 2
            continue
        return r

    msg = f"network failure after {retries} retries: {last_exc}" if last_exc \
        else f"request failed after {retries} retries"
    raise ApiError(msg, exit_code=2)


def _get_json(path: str, params: dict | None = None) -> dict:
    r = _request("GET", path, params=params)
    if r.status_code == 401:
        raise ApiError(
            "401: invalid MEETGEEK_API_KEY (check ~/.h2t/config/secrets/meetgeek.md)",
            exit_code=1,
        )
    if r.status_code == 404:
        raise ApiError(f"404: {path} not found", exit_code=1)
    if r.status_code >= 400:
        raise ApiError(f"{r.status_code}: {r.text[:500]}", exit_code=1)
    try:
        return r.json()
    except ValueError:
        raise ApiError(f"malformed JSON response from {path}", exit_code=1)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _print_json(data: Any) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


_YAML_UNSAFE = (":", "#", "'", '"', ",", "[", "]", "{", "}", "\n", "&", "*", "!", "|", ">", "%", "@", "`")


def _yaml_value(v: Any) -> str:
    """Safe YAML scalar/list rendering via JSON for tricky strings."""
    if isinstance(v, list):
        return json.dumps(v, ensure_ascii=False)
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    if v is None:
        return ""
    s = str(v)
    if not s:
        return '""'
    if any(c in s for c in _YAML_UNSAFE) or s.strip() != s:
        return json.dumps(s, ensure_ascii=False)
    return s


def _frontmatter(fields: dict) -> str:
    lines = ["---"]
    for k, v in fields.items():
        if v is None or v == "":
            continue
        lines.append(f"{k}: {_yaml_value(v)}")
    lines.append("---")
    return "\n".join(lines)


def _meeting_pick(m: dict) -> dict:
    """Normalize meeting record fields used in frontmatter / manifest.

    The MeetGeek list endpoint returns timestamps as `timestamp_start_utc`
    / `timestamp_end_utc` (verified live 2026-05-06). Earlier versions of
    this picker only checked `start_time` / `created_at`, which silently
    produced `null` timestamps for every backfill entry. Now the
    canonical API field is checked first, with `start_time` /
    `created_at` retained as fallbacks for any older response shape.
    """
    attendees = m.get("attendees") or m.get("participants") or []
    names = []
    for a in attendees:
        if isinstance(a, dict):
            names.append(a.get("name") or a.get("email") or "")
        elif isinstance(a, str):
            names.append(a)
    start_ts = (m.get("timestamp_start_utc")
                or m.get("start_time")
                or m.get("created_at"))
    end_ts = m.get("timestamp_end_utc") or m.get("end_time")
    mid = m.get("id") or m.get("meeting_id")
    return {
        "meeting_id": mid,
        "title": m.get("title") or m.get("name") or "",
        "attendees": [n for n in names if n],
        "date": (start_ts or "")[:10],
        "timestamp_start_utc": start_ts,
        "timestamp_end_utc": end_ts,
        "duration_seconds": m.get("duration") or m.get("duration_seconds"),
        "language": m.get("language") or m.get("language_code"),
        "provider_url": f"https://app2.meetgeek.ai/meeting/{mid}" if mid else None,
    }



# ─── Formatters ───────────────────────────────────────────────────────────────

def _extract_speakers(transcript: dict) -> list[str]:
    """Unique speakers from transcript.sentences (preserves first-seen order)."""
    seen: list[str] = []
    for s in transcript.get("sentences") or transcript.get("transcript") or []:
        sp = (s.get("speaker") or s.get("speaker_name") or "").strip()
        if sp and sp not in seen:
            seen.append(sp)
    return seen


def _fmt_transcript_md(meeting: dict, transcript: dict) -> str:
    meta = _meeting_pick(meeting)
    if not meta["attendees"]:
        meta["attendees"] = _extract_speakers(transcript)
    fm = _frontmatter({
        **meta,
        "source": "meetgeek-api",
        "fetched_at": _now_iso(),
        "api_version": "v1",
    })
    title = meta["title"] or meta["meeting_id"] or "Meeting"
    lines = [fm, "", f"# {title}", "", "## Transcript", ""]
    sentences = transcript.get("sentences") or transcript.get("transcript") or []
    for s in sentences:
        speaker = s.get("speaker") or s.get("speaker_name") or "Speaker"
        ts = s.get("timestamp") or s.get("start_time") or ""
        text = s.get("transcript") or s.get("text") or ""
        if isinstance(ts, (int, float)):
            mins, secs = divmod(int(ts), 60)
            hrs, mins = divmod(mins, 60)
            ts = f"{hrs:02d}:{mins:02d}:{secs:02d}"
        elif isinstance(ts, str) and "T" in ts:
            ts = ts[11:19]
        lines.append(f"**{speaker}** [{ts}] — {text}")
    return "\n".join(lines) + "\n"


def _fmt_summary_md(meeting: dict, summary: dict) -> str:
    meta = _meeting_pick(meeting)
    fm = _frontmatter({**meta, "type": "summary", "source": "meetgeek-api", "fetched_at": _now_iso()})
    body = summary.get("summary") or summary.get("text") or ""
    parts = [fm, "", f"# Summary — {meta['title'] or meta['meeting_id']}", "", body, ""]
    actions = summary.get("action_items") or []
    if actions:
        parts.append("## Action Items\n")
        for a in actions:
            owner = a.get("owner") or a.get("assignee") or "—"
            text = a.get("text") or a.get("description") or ""
            parts.append(f"- [ ] **{owner}**: {text}")
    return "\n".join(parts) + "\n"


def _fmt_highlights_md(meeting: dict, highlights: dict) -> str:
    meta = _meeting_pick(meeting)
    fm = _frontmatter({**meta, "type": "highlights", "source": "meetgeek-api", "fetched_at": _now_iso()})
    items = highlights.get("highlights") or highlights.get("items") or []
    parts = [fm, "", f"# Highlights — {meta['title'] or meta['meeting_id']}", ""]
    for h in items:
        text = h.get("text") or h.get("description") or ""
        ts = h.get("timestamp") or ""
        parts.append(f"- [{ts}] {text}" if ts else f"- {text}")
    return "\n".join(parts) + "\n"


def _fmt_insights_md(meeting: dict, insights: dict) -> str:
    meta = _meeting_pick(meeting)
    fm = _frontmatter({**meta, "type": "insights", "source": "meetgeek-api", "fetched_at": _now_iso()})
    return fm + "\n\n# Insights\n\n```json\n" + json.dumps(insights, ensure_ascii=False, indent=2) + "\n```\n"


# ─── Pagination ───────────────────────────────────────────────────────────────

def _iter_meetings(limit: int | None = None, cursor: str | None = None,
                   from_date: str | None = None, to_date: str | None = None) -> Iterable[dict]:
    fetched = 0
    pages = 0
    params: dict[str, Any] = {}
    if cursor:
        params["cursor"] = cursor
    if from_date:
        params["from_date"] = from_date
    if to_date:
        params["to_date"] = to_date

    while True:
        if pages >= MAX_PAGES:
            print(f"WARN: max pages ({MAX_PAGES}) reached, stopping", file=sys.stderr)
            return
        data = _get_json("/v1/meetings", params=params)
        if isinstance(data, list):
            items = data
            next_cursor = None
        else:
            items = data.get("meetings") or data.get("items") or data.get("data") or []
            pagination = data.get("pagination") or {}
            next_cursor = (
                pagination.get("next_cursor")
                or data.get("next_cursor")
                or data.get("cursor")
            )
        for m in items:
            yield m
            fetched += 1
            if limit and fetched >= limit:
                return
        if not next_cursor or not items:
            return
        params = {"cursor": next_cursor}
        if from_date:
            params["from_date"] = from_date
        if to_date:
            params["to_date"] = to_date
        pages += 1


# ─── Commands ─────────────────────────────────────────────────────────────────

def cmd_auth_check(_args: argparse.Namespace) -> int:
    r = _request("GET", "/v1/meetings", params={"limit": 1})
    if r.status_code == 200:
        print("OK: MEETGEEK_API_KEY valid")
        return 0
    if r.status_code == 401:
        print("FAIL: 401 Unauthorized — key invalid", file=sys.stderr)
        return 1
    print(f"FAIL: status {r.status_code} — {r.text[:200]}", file=sys.stderr)
    return 1


def cmd_teams(_args: argparse.Namespace) -> int:
    _print_json(_get_json("/v1/teams"))
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    out: list[dict] = []
    for m in _iter_meetings(limit=args.limit, cursor=args.cursor,
                            from_date=args.from_date, to_date=args.to_date):
        out.append(m)
    _print_json(out)
    return 0


def cmd_get(args: argparse.Namespace) -> int:
    _print_json(_get_json(f"/v1/meeting/{args.meeting_id}"))
    return 0


def _output(text_or_obj: Any, path: str | None) -> None:
    payload = text_or_obj if isinstance(text_or_obj, str) else json.dumps(text_or_obj, ensure_ascii=False, indent=2)
    if path:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(payload, encoding="utf-8")
        print(path)
    else:
        print(payload)


def _fetch_transcript_full(meeting_id: str) -> dict:
    """Walk transcript pagination; return single dict with combined `sentences`."""
    pages = 0
    cursor: str | None = None
    sentences: list[dict] = []
    base: dict = {}
    while True:
        if pages >= MAX_PAGES:
            print(f"WARN: max pages ({MAX_PAGES}) reached for transcript {meeting_id}", file=sys.stderr)
            break
        params = {"cursor": cursor} if cursor else None
        page = _get_json(f"/v1/meetings/{meeting_id}/transcript", params=params)
        if pages == 0:
            base = {k: v for k, v in page.items() if k not in ("sentences", "transcript", "pagination")}
        page_sentences = page.get("sentences") or page.get("transcript") or []
        sentences.extend(page_sentences)
        pagination = page.get("pagination") or {}
        cursor = pagination.get("next_cursor") or page.get("next_cursor")
        pages += 1
        if not cursor or not page_sentences:
            break
    return {**base, "sentences": sentences}


def cmd_transcript(args: argparse.Namespace) -> int:
    transcript = _fetch_transcript_full(args.meeting_id)
    if args.format == "json":
        _output(transcript, args.output)
    else:
        meeting = {"meeting_id": args.meeting_id}
        _output(_fmt_transcript_md(meeting, transcript), args.output)
    return 0


def cmd_summary(args: argparse.Namespace) -> int:
    summary = _get_json(f"/v1/meetings/{args.meeting_id}/summary")
    if args.format == "json":
        _output(summary, args.output)
    else:
        meeting = {"meeting_id": args.meeting_id}
        _output(_fmt_summary_md(meeting, summary), args.output)
    return 0


def cmd_highlights(args: argparse.Namespace) -> int:
    highlights = _get_json(f"/v1/meetings/{args.meeting_id}/highlights")
    if args.format == "json":
        _output(highlights, args.output)
    else:
        meeting = {"meeting_id": args.meeting_id}
        _output(_fmt_highlights_md(meeting, highlights), args.output)
    return 0


def cmd_insights(args: argparse.Namespace) -> int:
    insights = _get_json(f"/v1/meetings/{args.meeting_id}/insights")
    if args.format == "json":
        _output(insights, args.output)
    else:
        meeting = {"meeting_id": args.meeting_id}
        _output(_fmt_insights_md(meeting, insights), args.output)
    return 0


def cmd_download(args: argparse.Namespace) -> int:
    r = _request("POST", f"/v1/meetings/{args.meeting_id}/download")
    if r.status_code == 401:
        raise ApiError("401: invalid MEETGEEK_API_KEY", exit_code=1)
    if r.status_code == 404:
        raise ApiError(f"404: meeting {args.meeting_id} not found", exit_code=1)
    if r.status_code >= 400:
        raise ApiError(f"download endpoint returned {r.status_code}: {r.text[:200]}", exit_code=1)
    try:
        info = r.json()
    except ValueError:
        raise ApiError("malformed JSON from /download", exit_code=1)
    url = info.get("download_link") or info.get("download_url") or info.get("url")
    if not url:
        raise ApiError(f"no download link in response: {info}", exit_code=1)
    if not args.output:
        print(url)
        return 0
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    # Signed URL on media.meetgeek.ai (token in URL) — no Bearer needed.
    api_host = BASE_URL.split("//", 1)[-1].split("/", 1)[0]
    extra = {"Authorization": f"Bearer {API_KEY}"} if api_host in url else {}
    with requests.get(url, headers=extra, stream=True, timeout=TIMEOUT) as r:
        if r.status_code >= 400:
            raise ApiError(f"download failed: {r.status_code} {r.text[:200]}", exit_code=1)
        with open(args.output, "wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 16):
                if chunk:
                    f.write(chunk)
    print(args.output)
    return 0



def cmd_convert(args: argparse.Namespace) -> int:
    src = Path(args.input).expanduser().resolve()
    if not src.exists():
        raise ApiError(f"input not found: {src}", exit_code=1)
    out_path = Path(args.output).expanduser() if args.output else None
    try:
        probe = _ffmpeg_probe(str(src))
        if args.probe:
            _print_json(probe)
            return 0
        result = convert_media(src, audio_only=args.audio_only, mix_mode=args.mix_mode,
                               output_path=out_path, probe=probe)
    except RecoveryError as e:
        raise ApiError(str(e), exit_code=e.exit_code) from e
    print(result)
    return 0



def cmd_drive_audit(args: argparse.Namespace) -> int:
    """Report anyone-with-link access on uploaded recordings; --revoke to remove it."""
    try:
        report = _drive_audit_public(revoke=args.revoke)
    except RecoveryError as e:
        raise ApiError(str(e), exit_code=e.exit_code) from e
    _print_json(report)
    return 0


def cmd_drive_upload(args: argparse.Namespace) -> int:
    try:
        info = _drive_upload_file(Path(args.file), folder=args.folder,
                                  make_public=args.make_public)
    except RecoveryError as e:
        raise ApiError(str(e), exit_code=e.exit_code) from e
    _print_json(info)
    return 0



# ─── Upload commands ─────────────────────────────────────────────────────────

def cmd_upload(args: argparse.Namespace) -> int:
    if args.download_url:
        resp = _submit_url_via_h2t_ops(args.download_url, args.title, args.language)
        _print_json({"status": "submitted", "response": resp})
        return 0

    if not args.from_file:
        raise ApiError("either --download-url or --from-file required", exit_code=2)

    raw = args.from_file
    raw_path = Path(raw).expanduser()
    if raw_path.is_dir():
        # Directory mode: recursive *.webm walk
        expanded = sorted(raw_path.rglob("*.webm"))
    elif raw_path.is_file():
        # Direct file path
        expanded = [raw_path]
    else:
        # Glob fallback (string contains wildcard or path doesn't exist as-is)
        expanded = sorted(Path(p) for p in glob.glob(str(raw_path), recursive=True))
    if not expanded:
        raise ApiError(f"no files match: {raw}", exit_code=1)

    manifest_path = _uploads_manifest_path()
    state = _read_uploads_manifest(manifest_path)
    processed = 0
    skipped = 0
    errors = 0
    results: list[dict] = []
    total = len(expanded)
    for i, src_path in enumerate(expanded, 1):
        if not src_path.is_file():
            continue
        size = src_path.stat().st_size
        mtime = datetime.fromtimestamp(src_path.stat().st_mtime, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        if args.skip_existing and _is_already_submitted(state, str(src_path.resolve()),
                                                        size=size, mtime=mtime):
            print(f"[{i}/{total}] {src_path.name}  skip (already submitted)", file=sys.stderr)
            skipped += 1
            continue
        if args.dry_run:
            print(f"[{i}/{total}] {src_path.name}  would: convert+drive+upload", file=sys.stderr)
            continue
        try:
            print(f"[{i}/{total}] {src_path.name}  convert ...", file=sys.stderr)
            final = _process_one_for_upload(
                src_path,
                language=args.language,
                title_override=args.title,
                audio_only=args.audio_only,
                mix_mode=args.mix_mode,
                manifest_path=manifest_path,
            )
            results.append(final)
            processed += 1
            print(f"[{i}/{total}] {src_path.name}  ✓ submitted", file=sys.stderr)
        except (ApiError, RecoveryError) as e:
            print(f"[{i}/{total}] {src_path.name}  ✗ {e}", file=sys.stderr)
            errors += 1
            # Per-stage handler in _process_one_for_upload already wrote the
            # appropriate convert-failed / drive-failed / upload-rejected entry
            # to manifest. Don't add a synthetic "upload-failed" line — it
            # would drift from the spec's status enum.
            continue

    _print_json({"processed": processed, "skipped": skipped, "errors": errors,
                 "drive_folder": f"{DRIVE_ROOT_FOLDER_NAME}/{datetime.now(timezone.utc).strftime('%Y-%m-%d')}",
                 "results_count": len(results)})
    return 0 if errors == 0 else 1


# ─── Sync pipeline ────────────────────────────────────────────────────────────

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
    """Return set of meeting_ids already in manifest.jsonl (for dedup)."""
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
            mid = rec.get("meeting_id")
            if mid:
                seen.add(mid)
    return seen


def _fetch_recording_url(meeting_id: str) -> str:
    """POST /v1/meetings/{id}/download → temp signed URL (download_link)."""
    r = _request("POST", f"/v1/meetings/{meeting_id}/download")
    if r.status_code >= 400:
        raise ApiError(f"download endpoint {r.status_code}: {r.text[:200]}", exit_code=1)
    info = r.json()
    url = info.get("download_link") or info.get("download_url") or info.get("url")
    if not url:
        raise ApiError(f"no download link: {info}", exit_code=1)
    return url


def _stream_to_file(url: str, dest: Path) -> int:
    api_host = BASE_URL.split("//", 1)[-1].split("/", 1)[0]
    headers = {"Authorization": f"Bearer {API_KEY}"} if api_host in url else {}
    bytes_written = 0
    dest.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, headers=headers, stream=True, timeout=TIMEOUT) as r:
        if r.status_code >= 400:
            raise ApiError(f"download stream {r.status_code}: {r.text[:200]}", exit_code=1)
        with dest.open("wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 16):
                if chunk:
                    f.write(chunk)
                    bytes_written += len(chunk)
    return bytes_written


def _run_sync_once(args: argparse.Namespace) -> tuple[int, int, int]:
    """Single sync pass. Returns (synced, skipped, errors)."""
    lake = Path(args.to).expanduser()
    lake.mkdir(parents=True, exist_ok=True)

    include = {p.strip() for p in (args.include or "transcripts").split(",") if p.strip()}
    valid = {"transcripts", "summaries", "highlights", "insights", "recordings"}
    unknown = include - valid
    if unknown:
        raise ApiError(f"unknown --include values: {unknown} (valid: {sorted(valid)})", exit_code=2)

    cursor_path = Path(args.cursor_file).expanduser() if args.cursor_file else CURSOR_PATH_DEFAULT
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
    count = 0
    skipped = 0
    last_seen_ts: str | None = cursor.get("last_seen_ts")
    last_seen_id: str | None = cursor.get("last_seen_id")
    errors = 0

    for m in _iter_meetings(limit=args.limit, from_date=from_date, to_date=args.to_date):
        meta = _meeting_pick(m)
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
                t = _fetch_transcript_full(mid)
                if not meta["attendees"]:
                    meta["attendees"] = _extract_speakers(t)
                _write_pair(lake / "transcripts", mid, _fmt_transcript_md(m, t), t)
            if "summaries" in include:
                s = _get_json(f"/v1/meetings/{mid}/summary")
                _write_pair(lake / "summaries", mid, _fmt_summary_md(m, s), s)
            if "highlights" in include:
                h = _get_json(f"/v1/meetings/{mid}/highlights")
                _write_pair(lake / "highlights", mid, _fmt_highlights_md(m, h), h)
            if "insights" in include:
                i = _get_json(f"/v1/meetings/{mid}/insights")
                _write_pair(lake / "insights", mid, _fmt_insights_md(m, i), i)
            if "recordings" in include:
                url = _fetch_recording_url(mid)
                rec_path = lake / "recordings" / f"{mid}.mp4"
                if not rec_path.exists():
                    _stream_to_file(url, rec_path)
        except ApiError as e:
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
        "last_run_at": _now_iso(),
        "last_run_status": "ok" if errors == 0 else f"partial({errors})",
        "items_ingested": cursor.get("items_ingested", 0) + count,
        "version": 1,
    })
    _save_cursor(cursor_path, cursor)

    print(f"synced={count} skipped={skipped} errors={errors} cursor={cursor_path}")
    return count, skipped, errors


def cmd_sync(args: argparse.Namespace) -> int:
    if not getattr(args, "watch", None):
        _, _, errors = _run_sync_once(args)
        return 0 if errors == 0 else 1
    interval = max(int(args.watch), 30)
    print(f"watch mode: interval={interval}s, --since-cursor={args.since_cursor}")
    while True:
        try:
            _run_sync_once(args)
        except ApiError as e:
            print(f"WARN run failed: {e}", file=sys.stderr)
        try:
            time.sleep(interval)
        except KeyboardInterrupt:
            print("\nwatch stopped", file=sys.stderr)
            return 0


# ─── Webhook receiver ─────────────────────────────────────────────────────────

def cmd_webhook_server(args: argparse.Namespace) -> int:
    """Minimal HTTP server that dumps incoming POSTs as JSON files."""
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from uuid import uuid4

    out_dir = Path(args.out).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)
    secret = (args.secret or "").strip()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):  # noqa: A002 — base class signature
            sys.stderr.write(f"[webhook] {self.address_string()} - {format % args}\n")

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
                "received_at": _now_iso(),
                "path": self.path,
                "headers": {k: v for k, v in self.headers.items()},
                "payload": payload,
            }
            event_id = str(uuid4())
            (out_dir / f"{event_id}.json").write_text(
                json.dumps(event, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            self._reply(200, "ok\n")

        def do_GET(self):  # health probe
            self._reply(200, "meetgeek webhook receiver\n")

    server = ThreadingHTTPServer((args.bind, args.port), Handler)
    print(f"webhook-server: bind={args.bind}:{args.port} out={out_dir} secret={'set' if secret else 'none'}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped", file=sys.stderr)
    finally:
        server.server_close()
    return 0


def _write_pair(folder: Path, mid: str, md: str, raw: dict) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{mid}.md").write_text(md, encoding="utf-8")
    (folder / f"{mid}.json").write_text(
        json.dumps(raw, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# ─── argparse ─────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="meetgeek_cli", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("auth-check", help="Validate MEETGEEK_API_KEY")
    s.set_defaults(func=cmd_auth_check)

    s = sub.add_parser("teams", help="List user's teams")
    s.set_defaults(func=cmd_teams)

    s = sub.add_parser("list", help="List paginated past meetings")
    s.add_argument("--limit", type=int, default=None)
    s.add_argument("--cursor", default=None)
    s.add_argument("--from-date", dest="from_date", default=None)
    s.add_argument("--to-date", dest="to_date", default=None)
    s.set_defaults(func=cmd_list)

    s = sub.add_parser("get", help="Meeting metadata")
    s.add_argument("meeting_id")
    s.set_defaults(func=cmd_get)

    for name, fn, help_text in [
        ("transcript", cmd_transcript, "Transcript with speakers and timestamps"),
        ("summary", cmd_summary, "Summary + action items"),
        ("highlights", cmd_highlights, "AI key moments"),
        ("insights", cmd_insights, "Meeting insights"),
    ]:
        s = sub.add_parser(name, help=help_text)
        s.add_argument("meeting_id")
        s.add_argument("--format", choices=["md", "json"], default="md")
        s.add_argument("-o", "--output", default=None)
        s.set_defaults(func=fn)

    s = sub.add_parser("download", help="Get recording download URL or file")
    s.add_argument("meeting_id")
    s.add_argument("-o", "--output", default=None,
                   help="If omitted, prints URL; otherwise downloads to PATH")
    s.set_defaults(func=cmd_download)

    s = sub.add_parser("convert", help="Convert media file (webm→mp4 default)")
    s.add_argument("input")
    s.add_argument("-o", "--output", default=None,
                   help="Output path; default: ~/.dor/lake/meetgeek/uploads-staging/{YYYY-MM-DD}/{name}.mp4")
    s.add_argument("--audio-only", action="store_true",
                   help="Strip video; output .m4a")
    s.add_argument("--mix-mode", choices=["amix", "first", "keep"], default="amix",
                   help="Multi-track audio strategy (default: amix — sums all tracks)")
    s.add_argument("--probe", action="store_true",
                   help="Print probe info as JSON and exit")
    s.set_defaults(func=cmd_convert)

    s = sub.add_parser("drive-upload", help="Upload a file to Drive (idempotent by name)")
    s.add_argument("file")
    s.add_argument("--folder", default=None,
                   help="Path like 'MeetGeek Uploads/2026-05-06'; default: MeetGeek Uploads/{today UTC}")
    s.add_argument("--make-public", action=argparse.BooleanOptionalAction, default=True,
                   help="Set permissions to anyone-with-link reader (default on)")
    s.set_defaults(func=cmd_drive_upload)

    s = sub.add_parser("drive-audit",
                       help="Report anyone-with-link access on uploaded recordings")
    s.add_argument("--revoke", action="store_true",
                   help="Remove the anyone permission (off by default; only safe once "
                        "MeetGeek has fetched the recording)")
    s.set_defaults(func=cmd_drive_audit)

    s = sub.add_parser("upload", help="Submit URL or local file to MeetGeek /v1/upload")
    grp = s.add_mutually_exclusive_group(required=True)
    grp.add_argument("--download-url", default=None,
                     help="Public URL MeetGeek will fetch (e.g. Drive uc?export=download)")
    grp.add_argument("--from-file", default=None,
                     help="Local file path or glob; orchestrates convert + drive-upload + upload")
    s.add_argument("--title", default=None)
    s.add_argument("--language", default=None,
                   help="Language hint (ru, en, auto, etc.)")
    s.add_argument("--audio-only", action="store_true")
    s.add_argument("--mix-mode", choices=["amix", "first", "keep"], default="amix")
    s.add_argument("--skip-existing", action=argparse.BooleanOptionalAction, default=True,
                   help="Skip files already in manifest with status=submitted (default on)")
    s.add_argument("--dry-run", action="store_true",
                   help="Print plan; do not convert/upload")
    s.set_defaults(func=cmd_upload)

    s = sub.add_parser("sync", help="Bulk pull to LAKE_PATH (manifest.jsonl + per-asset folders)")
    s.add_argument("--to", required=True, help="Lake destination (e.g. ~/.dor/lake/meetgeek/historical/)")
    s.add_argument("--include", default="transcripts",
                   help="Comma-separated: transcripts,summaries,highlights,insights,recordings")
    s.add_argument("--since", default=None, help="ISO date YYYY-MM-DD")
    s.add_argument("--since-cursor", action="store_true",
                   help="Resume from last_seen_ts in cursor file")
    s.add_argument("--to-date", dest="to_date", default=None)
    s.add_argument("--limit", type=int, default=None)
    s.add_argument("--cursor-file", dest="cursor_file", default=None,
                   help=f"Default: {CURSOR_PATH_DEFAULT}")
    s.add_argument("--watch", type=int, default=None, metavar="SECONDS",
                   help="Run sync in a loop every N seconds (min 30); Ctrl-C to stop")
    s.set_defaults(func=cmd_sync)

    s = sub.add_parser("webhook-server", help="Receive MeetGeek webhook events to disk")
    s.add_argument("--port", type=int, default=8765)
    s.add_argument("--bind", default="127.0.0.1")
    s.add_argument("--out", default=str(Path.home() / ".dor" / "lake" / "meetgeek" / "webhooks"),
                   help="Directory to dump received events as JSON")
    s.add_argument("--secret", default=os.environ.get("MEETGEEK_WEBHOOK_SECRET", ""),
                   help="Optional shared secret; if set, requests without matching X-Webhook-Secret are 401'd")
    s.set_defaults(func=cmd_webhook_server)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (ApiError, RecoveryError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return e.exit_code


if __name__ == "__main__":
    sys.exit(main())
