#!/usr/bin/env python3
"""
Recovery coordinator for MeetGeek local recording upload pipeline.

Stateless helpers (ffmpeg, Drive) and stateful pipeline (manifest, process_one)
for the local recording → convert → Drive → MeetGeek submit flow.

NOT an h2t-ops connector. Submit stage delegates to `h2t-ops meetgeek submit-url` (#134).
Drive upload is embedded — h2t-ops drive upload lacks recovery-compatible semantics
(no folder hierarchy, no public sharing, no usercontent URL).
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import imageio_ffmpeg
except ImportError:
    imageio_ffmpeg = None


# ─── Constants ────────────────────────────────────────────────────────────────

DRIVE_CONFIG_DIR = Path.home() / ".config" / "google-calendar-mcp"
DRIVE_TOKEN_FILE = DRIVE_CONFIG_DIR / "tokens.json"
DRIVE_CREDENTIALS_FILE = DRIVE_CONFIG_DIR / "credentials.json"
DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive"]
DRIVE_ROOT_FOLDER_NAME = "MeetGeek Uploads"

_RECORDING_NAME_RE = re.compile(
    r"meetgeek-recording-(\d{4})-(\d{2})-(\d{2})T(\d{2})-(\d{2})-\d{2}-\d+Z"
)
_DURATION_RE = re.compile(r"Duration:\s*(\d+):(\d+):(\d+)(?:\.(\d+))?")
_STREAM_AUDIO_RE = re.compile(r"Stream\s+#\d+:\d+(?:\([^)]+\))?: Audio:")
_STREAM_VIDEO_RE = re.compile(r"Stream\s+#\d+:\d+(?:\([^)]+\))?: Video:")


# ─── Error ────────────────────────────────────────────────────────────────────

class RecoveryError(Exception):
    """Expected failure in recovery pipeline. Carries exit code."""
    def __init__(self, message: str, exit_code: int = 1):
        super().__init__(message)
        self.exit_code = exit_code


# ─── Utilities ────────────────────────────────────────────────────────────────

def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def staging_dir() -> Path:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return Path.home() / ".dor" / "lake" / "meetgeek" / "uploads-staging" / today


def title_from_filename(stem: str) -> str:
    m = _RECORDING_NAME_RE.search(stem)
    if m:
        y, mo, d, hh, mm = m.groups()
        return f"Meeting {y}-{mo}-{d} {hh}:{mm} UTC"
    return f"Meeting {stem}"


# ─── ffmpeg ───────────────────────────────────────────────────────────────────

def ffmpeg_exe() -> str:
    if imageio_ffmpeg is None:
        raise RecoveryError(
            "imageio-ffmpeg not installed; run: "
            "~/.h2t/venv/Scripts/python.exe -m pip install imageio-ffmpeg",
            exit_code=2,
        )
    return imageio_ffmpeg.get_ffmpeg_exe()


def ffmpeg_probe(path: str) -> dict:
    """Parse audio/video streams and duration from ffmpeg stderr."""
    r = subprocess.run(
        [ffmpeg_exe(), "-hide_banner", "-i", path, "-f", "null", "-"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    stderr = r.stderr or ""
    output_marker = stderr.find("Output #")
    input_section = stderr[:output_marker] if output_marker != -1 else stderr
    audio = len(_STREAM_AUDIO_RE.findall(input_section))
    video = len(_STREAM_VIDEO_RE.findall(input_section))
    dur_match = _DURATION_RE.search(stderr)
    duration = None
    if dur_match:
        h, m, s, _ = dur_match.groups()
        duration = int(h) * 3600 + int(m) * 60 + int(s)
    if audio == 0 and r.returncode != 0:
        raise RecoveryError(f"ffmpeg cannot probe {path}: {stderr[:300]}", exit_code=1)
    return {
        "audio_streams": audio,
        "has_video": video > 0,
        "duration_seconds": duration,
        "raw_stderr_tail": stderr[-500:],
    }


def build_convert_cmd(input_path: str, output_path: str, *,
                      probe: dict, audio_only: bool, mix_mode: str) -> list[str]:
    """Construct ffmpeg argv. Explicit -map required when any -map is given."""
    exe = ffmpeg_exe()
    if probe["audio_streams"] <= 1 or mix_mode == "first":
        argv = [exe, "-y", "-hide_banner", "-i", input_path]
        if audio_only:
            argv += ["-vn", "-map", "0:a:0?"]
        else:
            argv += ["-map", "0:v?", "-map", "0:a:0?"]
        argv += ["-c:v", "libx264", "-preset", "medium", "-crf", "23",
                 "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
                 output_path]
        if audio_only:
            for k in ("-c:v", "libx264", "-preset", "medium", "-crf", "23"):
                if k in argv:
                    argv.remove(k)
        return argv
    if mix_mode == "keep":
        argv = [exe, "-y", "-hide_banner", "-i", input_path,
                "-map", "0", "-c:v", "libx264", "-preset", "medium", "-crf", "23",
                "-c:a", "aac", "-b:a", "192k", output_path]
        if audio_only:
            argv = [a for a in argv if a not in ("-c:v", "libx264", "-preset", "medium", "-crf", "23")]
            argv.insert(argv.index("-i") + 2, "-vn")
        return argv
    n = probe["audio_streams"]
    inputs = "".join(f"[0:a:{i}]" for i in range(n))
    filtergraph = (
        f"{inputs}amix=inputs={n}:duration=longest:dropout_transition=0,"
        f"aresample=48000[a]"
    )
    argv = [exe, "-y", "-hide_banner", "-i", input_path, "-filter_complex", filtergraph]
    if audio_only:
        argv += ["-map", "[a]", "-c:a", "aac", "-b:a", "192k", "-ac", "2", output_path]
    else:
        argv += ["-map", "0:v?", "-map", "[a]",
                 "-c:v", "libx264", "-preset", "medium", "-crf", "23",
                 "-c:a", "aac", "-b:a", "192k", "-ac", "2", output_path]
    return argv


def convert_media(src: Path, *, audio_only: bool, mix_mode: str,
                  output_path: Path | None = None) -> Path:
    """Probe src and encode to mp4/m4a. Skip if output already exists and >1 KB."""
    src = src.resolve()
    if not src.exists():
        raise RecoveryError(f"input not found: {src}", exit_code=1)
    probe = ffmpeg_probe(str(src))
    if output_path is None:
        suffix = ".m4a" if audio_only else ".mp4"
        output_path = staging_dir() / (src.stem + suffix)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists() and output_path.stat().st_size > 1024:
        print(f"INFO: cached {output_path} (skip)", file=sys.stderr)
        return output_path
    cmd = build_convert_cmd(str(src), str(output_path), probe=probe,
                            audio_only=audio_only, mix_mode=mix_mode)
    print(f"INFO: ffmpeg {len(cmd)} args (audio_streams={probe['audio_streams']})",
          file=sys.stderr)
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        if output_path.exists():
            output_path.unlink()
        raise RecoveryError(f"ffmpeg encode failed: {r.stderr[:500]}", exit_code=1)
    if not output_path.exists() or output_path.stat().st_size <= 1024:
        if output_path.exists():
            output_path.unlink()
        raise RecoveryError(f"ffmpeg produced empty output: {output_path}", exit_code=1)
    return output_path


# ─── Drive ────────────────────────────────────────────────────────────────────

def drive_service():
    """Build Drive v3 service from shared OAuth token (~/.config/google-calendar-mcp/tokens.json)."""
    if not DRIVE_TOKEN_FILE.exists():
        raise RecoveryError(
            f"Drive auth missing — token not at {DRIVE_TOKEN_FILE}. "
            "Run /h2t-ops:drive list to trigger OAuth.",
            exit_code=1,
        )
    try:
        from google.auth.transport.requests import Request as _GReq
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
    except ImportError as e:
        raise RecoveryError(
            f"google-api-python-client not installed: {e}",
            exit_code=2,
        ) from e
    with DRIVE_TOKEN_FILE.open(encoding="utf-8") as f:
        token_data = json.load(f)
    if "normal" in token_data:
        token_data = token_data["normal"]
    if "client_id" not in token_data:
        if not DRIVE_CREDENTIALS_FILE.exists():
            raise RecoveryError(f"Drive credentials missing: {DRIVE_CREDENTIALS_FILE}", exit_code=1)
        with DRIVE_CREDENTIALS_FILE.open(encoding="utf-8") as f:
            creds_data = json.load(f)
        installed = creds_data.get("installed", creds_data)
        token_data["client_id"] = installed.get("client_id")
        token_data["client_secret"] = installed.get("client_secret")
        token_data["token_uri"] = installed.get("token_uri", "https://oauth2.googleapis.com/token")
    existing_scopes = token_data.get("scopes") or []
    if isinstance(existing_scopes, str):
        existing_scopes = existing_scopes.split()
    creds = Credentials.from_authorized_user_info(
        token_data, scopes=existing_scopes or DRIVE_SCOPES
    )
    if creds.expired and creds.refresh_token:
        creds.refresh(_GReq())
        DRIVE_TOKEN_FILE.write_text(creds.to_json())
    return build("drive", "v3", credentials=creds)


def drive_download_url(file_id: str) -> str:
    """Direct download URL; bypasses virus-scan interstitial for files of any size."""
    return (
        "https://drive.usercontent.google.com/download"
        f"?id={file_id}&export=download&confirm=t"
    )


def _drive_find_or_create_folder(svc, name: str, parent_id: str | None = None) -> str:
    parent_clause = f" and '{parent_id}' in parents" if parent_id else " and 'root' in parents"
    q = (f"name = '{name}' and mimeType = 'application/vnd.google-apps.folder' "
         f"and trashed = false{parent_clause}")
    res = svc.files().list(q=q, fields="files(id,name)", pageSize=1).execute()
    files = res.get("files", [])
    if files:
        return files[0]["id"]
    body = {"name": name, "mimeType": "application/vnd.google-apps.folder"}
    if parent_id:
        body["parents"] = [parent_id]
    return svc.files().create(body=body, fields="id").execute()["id"]


def _drive_find_file(svc, name: str, folder_id: str) -> dict | None:
    q = f"name = '{name}' and '{folder_id}' in parents and trashed = false"
    res = svc.files().list(q=q, fields="files(id,name,webViewLink)", pageSize=1).execute()
    files = res.get("files", [])
    return files[0] if files else None


def _drive_make_public(svc, file_id: str) -> None:
    svc.permissions().create(
        fileId=file_id, body={"type": "anyone", "role": "reader"}, fields="id",
    ).execute()


def drive_upload_file(path: Path, *, folder: str | None = None,
                      make_public: bool = True) -> dict:
    """Upload to Drive. Idempotent by filename within folder. Returns {drive_id, web_url, download_url, created}."""
    src = Path(path).expanduser().resolve()
    if not src.exists():
        raise RecoveryError(f"file not found: {src}", exit_code=1)
    svc = drive_service()
    if folder:
        parts = [p for p in folder.replace("\\", "/").split("/") if p]
    else:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        parts = [DRIVE_ROOT_FOLDER_NAME, date]
    parent_id: str | None = None
    for part in parts:
        parent_id = _drive_find_or_create_folder(svc, part, parent_id)
    folder_id = parent_id
    existing = _drive_find_file(svc, src.name, folder_id)
    if existing:
        if make_public:
            try:
                _drive_make_public(svc, existing["id"])
            except Exception:  # noqa: BLE001
                pass
        return {
            "drive_id": existing["id"],
            "web_url": existing.get("webViewLink"),
            "download_url": drive_download_url(existing["id"]),
            "created": False,
        }
    from googleapiclient.http import MediaFileUpload
    media = MediaFileUpload(str(src), resumable=True)
    body = {"name": src.name, "parents": [folder_id]}
    file = svc.files().create(body=body, media_body=media, fields="id,webViewLink").execute()
    if make_public:
        _drive_make_public(svc, file["id"])
    return {
        "drive_id": file["id"],
        "web_url": file.get("webViewLink"),
        "download_url": drive_download_url(file["id"]),
        "created": True,
    }


# ─── Submit ───────────────────────────────────────────────────────────────────

def submit_url_via_h2t_ops(download_url: str, title: str | None,
                           language: str | None) -> dict:
    """Delegate POST /v1/upload to `h2t-ops meetgeek submit-url` (#134)."""
    h2t_ops = os.environ.get("H2T_OPS", "h2t-ops")
    cmd = [h2t_ops, "meetgeek", "submit-url", download_url, "--json"]
    if title:
        cmd.extend(["--title", title])
    if language:
        cmd.extend(["--language-code", language])
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              encoding="utf-8", errors="replace")
    except OSError as exc:
        raise RecoveryError(f"h2t-ops submit-url failed to start: {exc}", exit_code=1) from exc
    raw = (proc.stdout or proc.stderr or "").strip()
    if proc.returncode != 0:
        try:
            env = json.loads(raw)
            msg = (env.get("error") or {}).get("message") or raw
        except ValueError:
            msg = raw or f"exit {proc.returncode}"
        raise RecoveryError(f"h2t-ops submit-url failed: {msg}", exit_code=proc.returncode or 1)
    try:
        env = json.loads(proc.stdout)
    except ValueError as exc:
        raise RecoveryError(
            f"h2t-ops submit-url returned malformed JSON: {raw[:300]}", exit_code=1
        ) from exc
    if env.get("ok") is not True:
        msg = (env.get("error") or {}).get("message") or str(env)
        raise RecoveryError(f"h2t-ops submit-url failed: {msg}", exit_code=1)
    return env.get("result") or {}


# ─── Manifest ─────────────────────────────────────────────────────────────────

def uploads_manifest_path() -> Path:
    return Path.home() / ".dor" / "lake" / "meetgeek" / "uploads-staging" / "manifest.jsonl"


def read_uploads_manifest(path: Path | None = None) -> dict[str, dict]:
    """Last-line-wins per source_webm key."""
    if path is None:
        path = uploads_manifest_path()
    state: dict[str, dict] = {}
    if not path.exists():
        return state
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            src = rec.get("source_webm")
            if src:
                state[src] = rec
    return state


def append_uploads_manifest(record: dict, path: Path | None = None) -> None:
    if path is None:
        path = uploads_manifest_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def is_already_submitted(state: dict[str, dict], source: str, *,
                         size: int, mtime: str) -> bool:
    rec = state.get(source)
    if not rec or rec.get("status") != "submitted":
        return False
    return rec.get("source_size_bytes") == size and rec.get("source_mtime") == mtime


# ─── Pipeline coordinator ─────────────────────────────────────────────────────

def process_one(src_path: Path, *, language: str | None, title_override: str | None,
                audio_only: bool, mix_mode: str, manifest_path: Path) -> dict:
    """Three-stage recovery pipeline: convert → drive → submit. Manifest-based resume."""
    src = src_path.resolve()
    src_size = src.stat().st_size
    src_mtime = datetime.fromtimestamp(src.stat().st_mtime, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    base_meta = {
        "source_webm": str(src),
        "source_size_bytes": src_size,
        "source_mtime": src_mtime,
    }

    state = read_uploads_manifest(manifest_path)
    rec = state.get(str(src), {}) or {}
    rec_status = rec.get("status")
    suffix = ".m4a" if audio_only else ".mp4"
    mp4_path = staging_dir() / (src.stem + suffix)
    mp4_size: int

    # ── Stage 1: Convert ──────────────────────────────────────────────────────
    cached_mp4 = rec.get("mp4_path")
    can_skip_convert = (
        rec_status in ("converted", "in-drive", "submitted")
        and cached_mp4
        and Path(cached_mp4).exists()
        and Path(cached_mp4).stat().st_size > 1024
    )
    if can_skip_convert:
        mp4_path = Path(cached_mp4)
        mp4_size = mp4_path.stat().st_size
        print(f"  [resume] convert ✓ (cached {mp4_path.name})", file=sys.stderr)
    else:
        try:
            mp4_path = convert_media(src, audio_only=audio_only, mix_mode=mix_mode,
                                     output_path=mp4_path)
            mp4_size = mp4_path.stat().st_size
            append_uploads_manifest({
                **base_meta,
                "mp4_path": str(mp4_path), "mp4_size_bytes": mp4_size,
                "status": "converted",
            }, manifest_path)
        except RecoveryError as e:
            append_uploads_manifest({
                **base_meta, "status": "convert-failed", "error": str(e),
            }, manifest_path)
            raise

    # ── Stage 2: Drive upload ─────────────────────────────────────────────────
    can_skip_drive = (
        rec_status in ("in-drive", "submitted")
        and rec.get("drive_id")
        and rec.get("drive_download_url")
    )
    if can_skip_drive:
        drive_info = {
            "drive_id": rec["drive_id"],
            "download_url": drive_download_url(rec["drive_id"]),
            "web_url": rec.get("drive_web_url"),
            "created": False,
        }
        print(f"  [resume] drive ✓ (cached {drive_info['drive_id']})", file=sys.stderr)
    else:
        try:
            drive_info = drive_upload_file(mp4_path)
            append_uploads_manifest({
                **base_meta,
                "mp4_path": str(mp4_path), "mp4_size_bytes": mp4_size,
                "drive_id": drive_info["drive_id"],
                "drive_download_url": drive_info["download_url"],
                "drive_web_url": drive_info.get("web_url"),
                "status": "in-drive",
            }, manifest_path)
        except RecoveryError as e:
            append_uploads_manifest({
                **base_meta,
                "mp4_path": str(mp4_path), "mp4_size_bytes": mp4_size,
                "status": "drive-failed", "error": str(e),
            }, manifest_path)
            raise

    # ── Stage 3: Submit ───────────────────────────────────────────────────────
    title = title_override or title_from_filename(src.stem)
    try:
        resp = submit_url_via_h2t_ops(drive_info["download_url"], title, language)
    except RecoveryError as e:
        append_uploads_manifest({
            **base_meta,
            "mp4_path": str(mp4_path), "mp4_size_bytes": mp4_size,
            "drive_id": drive_info["drive_id"],
            "drive_download_url": drive_info["download_url"],
            "title": title, "language": language,
            "status": "upload-rejected", "error": str(e),
        }, manifest_path)
        raise

    final = {
        **base_meta,
        "mp4_path": str(mp4_path), "mp4_size_bytes": mp4_size,
        "drive_id": drive_info["drive_id"],
        "drive_download_url": drive_info["download_url"],
        "title": title, "language": language,
        "submitted_at": now_iso(),
        "upload_response_message": (resp.get("message") if isinstance(resp, dict) else None),
        "status": "submitted",
    }
    append_uploads_manifest(final, manifest_path)
    try:
        emit_submission_artifact(final)
    except Exception as e:  # noqa: BLE001
        print(f"WARN: artifact emission failed: {e}", file=sys.stderr)
    return final


# ─── Artifact emission ────────────────────────────────────────────────────────

def emit_submission_artifact(result: dict, *, artifact_dir: Path | None = None) -> Path:
    """Write recording_submission_artifact after Stage 3 submit.

    Emitted immediately; meetgeek_meeting_id is null at this stage — MeetGeek
    has not yet processed the recording. meeting_transcript_artifact is emitted
    separately after transcript fetch/sync.
    """
    if artifact_dir is None:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        artifact_dir = (
            Path.home() / ".dor" / "lake" / "meetgeek" / "uploads-staging" / date
        )
    artifact_dir.mkdir(parents=True, exist_ok=True)
    stem = Path(result.get("source_webm", "unknown")).stem
    artifact = {
        "schema_version": "0.1",
        "artifact_type": "recording_submission_artifact",
        "provider": "meetgeek",
        "provenance": "local-recording-recovery",
        "source_file": result.get("source_webm"),
        "source_size_bytes": result.get("source_size_bytes"),
        "source_mtime": result.get("source_mtime"),
        "converted_file": result.get("mp4_path"),
        "drive_id": result.get("drive_id"),
        "drive_download_url": result.get("drive_download_url"),
        "title": result.get("title"),
        "language": result.get("language"),
        "submitted_at": result.get("submitted_at"),
        "meetgeek_meeting_id": None,
        "notes": None,
    }
    path = artifact_dir / f"{stem}.submission.json"
    path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
