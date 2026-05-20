# MeetGeek Local Recording Recovery — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract local recording recovery logic from `meetgeek_cli.py` into a testable `recovery.py` coordinator module, add `recording_submission_artifact` emission after successful submit, and extend test coverage in `tests/connectors/meetgeek/test_recovery.py`.

**Architecture:** Three-phase extraction: (1) stateless helpers (ffmpeg, Drive, submit, title) → `recovery.py`; (2) manifest state machine + pipeline coordinator → `recovery.py`; (3) thin CLI wrappers + `recording_submission_artifact` emission. The `h2t-ops meetgeek submit-url` delegation stays unchanged. Drive upload remains embedded — current `h2t-ops drive upload` lacks recovery-compatible semantics (no folder hierarchy, no public sharing, no usercontent URL). `recovery.py` is NOT an h2t-ops connector verb — it is a skill-layer coordinator script.

**Tech Stack:** Python 3.11, imageio-ffmpeg, google-api-python-client, pytest, subprocess delegation to `h2t-ops meetgeek submit-url`.

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `plugins/h2t-ops/skills/meetgeek/scripts/recovery.py` | Create | All recovery logic: ffmpeg, Drive, manifest, pipeline, artifact emission |
| `plugins/h2t-ops/skills/meetgeek/scripts/meetgeek_cli.py` | Modify | Thin CLI wrappers only; imports from `recovery.py` |
| `tests/connectors/meetgeek/test_recovery.py` | Create (incremental) | Initial pure + manifest tests in T1; pipeline + emit tests appended in T4 |

---

### Task 0: Verification baseline

**Files:** read-only scan, no changes.

- [ ] **Step 1: Run all --help exits**

```bash
~/.h2t/venv/Scripts/python.exe plugins/h2t-ops/skills/meetgeek/scripts/meetgeek_cli.py convert --help
~/.h2t/venv/Scripts/python.exe plugins/h2t-ops/skills/meetgeek/scripts/meetgeek_cli.py upload --help
~/.h2t/venv/Scripts/python.exe plugins/h2t-ops/skills/meetgeek/scripts/meetgeek_cli.py drive-upload --help
~/.h2t/venv/Scripts/python.exe plugins/h2t-ops/skills/meetgeek/scripts/meetgeek_cli.py sync --help
~/.h2t/venv/Scripts/python.exe plugins/h2t-ops/skills/meetgeek/scripts/meetgeek_cli.py webhook-server --help
```

Expected: each exits 0 with no tracebacks.

- [ ] **Step 2: Dummy dry-run**

```bash
~/.h2t/venv/Scripts/python.exe -c "from pathlib import Path; Path('C:/tmp/dummy_rec.webm').parent.mkdir(exist_ok=True); Path('C:/tmp/dummy_rec.webm').write_bytes(b'x' * 1024)"
~/.h2t/venv/Scripts/python.exe plugins/h2t-ops/skills/meetgeek/scripts/meetgeek_cli.py upload --from-file C:/tmp/dummy_rec.webm --dry-run
```

Expected: `[1/1] dummy_rec.webm  would: convert+drive+upload`, exit 0.

- [ ] **Step 3: Run legacy test suite**

```bash
~/.h2t/venv/Scripts/python.exe -m pytest plugins/h2t-ops/skills/meetgeek/tests/test_meetgeek_cli.py -v
```

Expected: all pass.

- [ ] **Step 4: Run connector test suite**

```bash
~/.h2t/venv/Scripts/python.exe -m pytest tests/connectors/meetgeek/ -v
```

Expected: all pass. If anything fails here, stop and fix before continuing.

---

### Task 1: Create recovery.py with stateless helpers (TDD)

**Files:**
- Create: `tests/connectors/meetgeek/test_recovery.py`
- Create: `plugins/h2t-ops/skills/meetgeek/scripts/recovery.py`
- Modify: `plugins/h2t-ops/skills/meetgeek/scripts/meetgeek_cli.py`

- [ ] **Step 1: Write failing tests for pure functions, manifest helpers, and submit delegation**

Create `tests/connectors/meetgeek/test_recovery.py` with the content below. These tests cover what T1 implements; the rest (process_one, emit) are added in T4.

```python
"""Tests for recovery.py — TDD: pure functions, manifest, submit delegation."""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

RECOVERY = Path(__file__).resolve().parent.parent.parent.parent / \
           "plugins" / "h2t-ops" / "skills" / "meetgeek" / "scripts" / "recovery.py"


@pytest.fixture()
def rec(monkeypatch):
    """Load recovery module with deterministic env."""
    monkeypatch.setenv("H2T_OPS", "h2t-ops-stub")
    spec = importlib.util.spec_from_file_location("recovery_under_test", RECOVERY)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["recovery_under_test"] = mod
    spec.loader.exec_module(mod)
    return mod


class TestTitleFromFilename:
    def test_canonical_recording_name(self, rec):
        stem = "meetgeek-recording-2026-05-20T10-30-00-1Z"
        assert rec.title_from_filename(stem) == "Meeting 2026-05-20 10:30 UTC"

    def test_unknown_name(self, rec):
        assert rec.title_from_filename("my-recording") == "Meeting my-recording"


class TestDriveDownloadUrl:
    def test_format(self, rec):
        url = rec.drive_download_url("abc123")
        assert url == "https://drive.usercontent.google.com/download?id=abc123&export=download&confirm=t"

    def test_different_id(self, rec):
        assert "xyz999" in rec.drive_download_url("xyz999")


class TestBuildConvertCmd:
    def test_single_track_maps_audio(self, rec):
        with patch.object(rec, "ffmpeg_exe", return_value="/usr/bin/ffmpeg"):
            probe = {"audio_streams": 1, "has_video": True, "duration_seconds": 60}
            cmd = rec.build_convert_cmd("in.webm", "out.mp4", probe=probe,
                                        audio_only=False, mix_mode="amix")
        assert "out.mp4" in cmd
        assert "0:a:0?" in cmd

    def test_audio_only_excludes_video_codec(self, rec):
        with patch.object(rec, "ffmpeg_exe", return_value="/usr/bin/ffmpeg"):
            probe = {"audio_streams": 1, "has_video": False, "duration_seconds": 30}
            cmd = rec.build_convert_cmd("in.webm", "out.m4a", probe=probe,
                                        audio_only=True, mix_mode="amix")
        assert "libx264" not in cmd
        assert "-vn" in cmd

    def test_multi_track_amix_uses_filter_complex(self, rec):
        with patch.object(rec, "ffmpeg_exe", return_value="/usr/bin/ffmpeg"):
            probe = {"audio_streams": 2, "has_video": True, "duration_seconds": 60}
            cmd = rec.build_convert_cmd("in.webm", "out.mp4", probe=probe,
                                        audio_only=False, mix_mode="amix")
        assert "-filter_complex" in cmd
        assert "amix=inputs=2" in " ".join(cmd)


class TestReadUploadsManifest:
    def test_empty_file_returns_empty_dict(self, rec, tmp_path):
        manifest = tmp_path / "manifest.jsonl"
        manifest.write_text("", encoding="utf-8")
        assert rec.read_uploads_manifest(manifest) == {}

    def test_last_line_wins(self, rec, tmp_path):
        manifest = tmp_path / "manifest.jsonl"
        manifest.write_text(
            json.dumps({"source_webm": "/a/b.webm", "status": "converted"}) + "\n"
            + json.dumps({"source_webm": "/a/b.webm", "status": "submitted"}) + "\n",
            encoding="utf-8",
        )
        state = rec.read_uploads_manifest(manifest)
        assert state["/a/b.webm"]["status"] == "submitted"

    def test_missing_file_returns_empty_dict(self, rec, tmp_path):
        assert rec.read_uploads_manifest(tmp_path / "nonexistent.jsonl") == {}

    def test_skips_malformed_lines(self, rec, tmp_path):
        manifest = tmp_path / "manifest.jsonl"
        manifest.write_text(
            "not-json\n"
            + json.dumps({"source_webm": "/a/b.webm", "status": "converted"}) + "\n",
            encoding="utf-8",
        )
        assert "/a/b.webm" in rec.read_uploads_manifest(manifest)


class TestAppendUploadsManifest:
    def test_creates_parent_dirs_and_appends(self, rec, tmp_path):
        manifest = tmp_path / "sub" / "manifest.jsonl"
        rec.append_uploads_manifest({"source_webm": "/x.webm", "status": "converted"}, manifest)
        lines = [json.loads(l) for l in manifest.read_text().splitlines()]
        assert lines[0]["status"] == "converted"

    def test_append_multiple_preserves_order(self, rec, tmp_path):
        manifest = tmp_path / "manifest.jsonl"
        rec.append_uploads_manifest({"source_webm": "/x.webm", "status": "converted"}, manifest)
        rec.append_uploads_manifest({"source_webm": "/x.webm", "status": "submitted"}, manifest)
        lines = manifest.read_text().strip().splitlines()
        assert len(lines) == 2


class TestIsAlreadySubmitted:
    def test_true_when_submitted_matching_size_mtime(self, rec):
        state = {"/a/b.webm": {"status": "submitted", "source_size_bytes": 100,
                                "source_mtime": "2026-05-20T10:00:00Z"}}
        assert rec.is_already_submitted(state, "/a/b.webm", size=100, mtime="2026-05-20T10:00:00Z")

    def test_false_when_size_differs(self, rec):
        state = {"/a/b.webm": {"status": "submitted", "source_size_bytes": 100,
                                "source_mtime": "2026-05-20T10:00:00Z"}}
        assert not rec.is_already_submitted(state, "/a/b.webm", size=200, mtime="2026-05-20T10:00:00Z")

    def test_false_when_not_submitted(self, rec):
        state = {"/a/b.webm": {"status": "converted", "source_size_bytes": 100,
                                "source_mtime": "2026-05-20T10:00:00Z"}}
        assert not rec.is_already_submitted(state, "/a/b.webm", size=100, mtime="2026-05-20T10:00:00Z")

    def test_false_when_key_absent(self, rec):
        assert not rec.is_already_submitted({}, "/a/b.webm", size=100, mtime="2026-05-20T10:00:00Z")


class TestSubmitUrlViaH2tOps:
    def test_delegates_to_h2t_ops_submit_url(self, rec, monkeypatch):
        calls = []
        class FakeProc:
            returncode = 0
            stdout = '{"ok": true, "result": {"message": "processing"}}'
            stderr = ""
        monkeypatch.setattr("subprocess.run", lambda cmd, **kw: (calls.append(cmd), FakeProc())[1])
        result = rec.submit_url_via_h2t_ops("https://example.com/r.mp4", "My Meeting", "ru")
        assert calls[0][:3] == ["h2t-ops-stub", "meetgeek", "submit-url"]
        assert "https://example.com/r.mp4" in calls[0]
        assert "--title" in calls[0]
        assert "--language-code" in calls[0]
        assert result == {"message": "processing"}

    def test_raises_on_non_ok_response(self, rec, monkeypatch):
        class FakeProc:
            returncode = 0
            stdout = '{"ok": false, "error": {"message": "quota exceeded"}}'
            stderr = ""
        monkeypatch.setattr("subprocess.run", lambda cmd, **kw: FakeProc())
        with pytest.raises(rec.RecoveryError, match="quota exceeded"):
            rec.submit_url_via_h2t_ops("https://example.com/r.mp4", None, None)

    def test_raises_on_nonzero_exit(self, rec, monkeypatch):
        class FakeProc:
            returncode = 1
            stdout = ""
            stderr = "connection refused"
        monkeypatch.setattr("subprocess.run", lambda cmd, **kw: FakeProc())
        with pytest.raises(rec.RecoveryError):
            rec.submit_url_via_h2t_ops("https://example.com/r.mp4", None, None)
```

- [ ] **Step 2: Run tests — verify FAIL**

```bash
~/.h2t/venv/Scripts/python.exe -m pytest tests/connectors/meetgeek/test_recovery.py -v
```

Expected: collection error or `AssertionError` on `assert spec and spec.loader` because `recovery.py` does not exist yet. This is the TDD red state.

- [ ] **Step 3: Create recovery.py**

Create `plugins/h2t-ops/skills/meetgeek/scripts/recovery.py` with the full content below:

```python
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
```

- [ ] **Step 4: Add import block to meetgeek_cli.py**

After the existing `try: import requests` block (before `API_KEY = ...`), add:

```python
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
    drive_download_url as _drive_download_url,
    submit_url_via_h2t_ops as _submit_url_via_h2t_ops,
    title_from_filename as _title_from_filename,
    DRIVE_ROOT_FOLDER_NAME,
)
```

- [ ] **Step 5: Delete moved sections from meetgeek_cli.py**

Remove these sections (they are now provided by `recovery.py`):

1. The `try: import imageio_ffmpeg` block (near line 458).
2. Constants: `DRIVE_CONFIG_DIR`, `DRIVE_TOKEN_FILE`, `DRIVE_CREDENTIALS_FILE`, `DRIVE_SCOPES`, `DRIVE_ROOT_FOLDER_NAME`.
3. Functions: `_ffmpeg_exe`, `_DURATION_RE`, `_STREAM_AUDIO_RE`, `_STREAM_VIDEO_RE`, `_ffmpeg_probe`, `_staging_dir`, `_build_convert_cmd`.
4. Functions: `_drive_service`, `_drive_find_or_create_folder`, `_drive_find_file`, `_drive_make_public`, `_drive_download_url`, `_drive_upload_file`.
5. Function: `_submit_url_via_h2t_ops`.
6. `import re as _re_titles`, `_RECORDING_NAME_RE`, `_title_from_filename`.
7. Function: `_now_iso` (now provided by `recovery.now_iso`, aliased as `_now_iso`).

Do NOT remove: `ApiError`, `_headers`, `_request`, `_get_json`, formatter functions, `_iter_meetings`, all `cmd_*` functions, `sync` helpers, `webhook-server`, `argparse`, `main`.

- [ ] **Step 6: Run help checks**

```bash
~/.h2t/venv/Scripts/python.exe plugins/h2t-ops/skills/meetgeek/scripts/meetgeek_cli.py convert --help
~/.h2t/venv/Scripts/python.exe plugins/h2t-ops/skills/meetgeek/scripts/meetgeek_cli.py upload --help
```

Expected: exit 0. If ImportError appears, check that `sys.path.insert` runs before `from recovery import`.

- [ ] **Step 7: Run ALL test suites — verify GREEN**

```bash
~/.h2t/venv/Scripts/python.exe -m pytest tests/connectors/meetgeek/test_recovery.py -v
~/.h2t/venv/Scripts/python.exe -m pytest plugins/h2t-ops/skills/meetgeek/tests/test_meetgeek_cli.py -v
~/.h2t/venv/Scripts/python.exe -m pytest tests/connectors/meetgeek/ -v
```

Expected: all pass. `test_recovery.py` must pass now (was RED in Step 2).

- [ ] **Step 8: Commit**

```bash
git add tests/connectors/meetgeek/test_recovery.py
git add plugins/h2t-ops/skills/meetgeek/scripts/recovery.py
git add plugins/h2t-ops/skills/meetgeek/scripts/meetgeek_cli.py
git commit -m "refactor(meetgeek): extract stateless helpers to recovery.py + TDD tests"
```

---

### Task 2: Move manifest helpers and pipeline to recovery.py

**Files:**
- Modify: `plugins/h2t-ops/skills/meetgeek/scripts/recovery.py` (append)
- Modify: `plugins/h2t-ops/skills/meetgeek/scripts/meetgeek_cli.py`

- [ ] **Step 1: Append manifest helpers and process_one to recovery.py**

Append to the end of `plugins/h2t-ops/skills/meetgeek/scripts/recovery.py`:

```python
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
    return final
```

- [ ] **Step 2: Extend the import block in meetgeek_cli.py**

In the `from recovery import (...)` block added in Task 1, add:

```python
    uploads_manifest_path as _uploads_manifest_path,
    read_uploads_manifest as _read_uploads_manifest,
    append_uploads_manifest as _append_uploads_manifest,
    is_already_submitted as _is_already_submitted,
    process_one as _process_one_for_upload,
```

- [ ] **Step 3: Delete moved sections from meetgeek_cli.py**

Remove from `meetgeek_cli.py`:
1. Functions: `_uploads_manifest_path`, `_read_uploads_manifest`, `_append_uploads_manifest`, `_is_already_submitted`.
2. Function: `_process_one_for_upload` (now an import alias).

- [ ] **Step 4: Update cmd_upload error catch**

In `cmd_upload`, the per-file except currently catches `ApiError`. Change it to also catch `RecoveryError`:

```python
        except (ApiError, RecoveryError) as e:
            print(f"[{i}/{total}] {src_path.name}  ✗ {e}", file=sys.stderr)
            errors += 1
            continue
```

- [ ] **Step 5: Run test suites**

```bash
~/.h2t/venv/Scripts/python.exe -m pytest plugins/h2t-ops/skills/meetgeek/tests/test_meetgeek_cli.py -v
~/.h2t/venv/Scripts/python.exe -m pytest tests/connectors/meetgeek/ -v
```

Expected: all pass.

- [ ] **Step 6: Dummy dry-run regression check**

```bash
~/.h2t/venv/Scripts/python.exe plugins/h2t-ops/skills/meetgeek/scripts/meetgeek_cli.py upload --from-file C:/tmp/dummy_rec.webm --dry-run
```

Expected: `[1/1] dummy_rec.webm  would: convert+drive+upload`, exit 0.

- [ ] **Step 7: Commit**

```bash
git add plugins/h2t-ops/skills/meetgeek/scripts/recovery.py
git add plugins/h2t-ops/skills/meetgeek/scripts/meetgeek_cli.py
git commit -m "refactor(meetgeek): move manifest helpers and process_one to recovery.py"
```

---

### Task 3: Thin CLI wrappers + recording_submission_artifact

**Files:**
- Modify: `plugins/h2t-ops/skills/meetgeek/scripts/recovery.py` (append)
- Modify: `plugins/h2t-ops/skills/meetgeek/scripts/meetgeek_cli.py`

- [ ] **Step 1: Append emit_submission_artifact to recovery.py**

```python
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
```

- [ ] **Step 2: Wire emit into process_one**

In `recovery.py` `process_one`, after `append_uploads_manifest(final, manifest_path)` and before `return final`, add:

```python
    try:
        emit_submission_artifact(final)
    except Exception as e:  # noqa: BLE001
        print(f"WARN: artifact emission failed: {e}", file=sys.stderr)
```

- [ ] **Step 3: Add emit_submission_artifact to imports in meetgeek_cli.py**

In the `from recovery import (...)` block, add:

```python
    emit_submission_artifact,
```

- [ ] **Step 4: Simplify cmd_convert**

Replace the existing `cmd_convert` in `meetgeek_cli.py` with:

```python
def cmd_convert(args: argparse.Namespace) -> int:
    src = Path(args.input).expanduser().resolve()
    if not src.exists():
        raise ApiError(f"input not found: {src}", exit_code=1)
    if args.probe:
        _print_json(_ffmpeg_probe(str(src)))
        return 0
    out_path = Path(args.output).expanduser() if args.output else None
    try:
        result = convert_media(src, audio_only=args.audio_only, mix_mode=args.mix_mode,
                               output_path=out_path)
    except RecoveryError as e:
        raise ApiError(str(e), exit_code=e.exit_code) from e
    print(result)
    return 0
```

- [ ] **Step 5: Simplify cmd_drive_upload**

Replace the existing `cmd_drive_upload` with:

```python
def cmd_drive_upload(args: argparse.Namespace) -> int:
    try:
        info = _drive_upload_file(Path(args.file), folder=args.folder,
                                  make_public=args.make_public)
    except RecoveryError as e:
        raise ApiError(str(e), exit_code=e.exit_code) from e
    _print_json(info)
    return 0
```

- [ ] **Step 6: Update main() to catch RecoveryError**

In `main()`:

```python
def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (ApiError, RecoveryError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return e.exit_code
```

- [ ] **Step 7: Run all checks**

```bash
~/.h2t/venv/Scripts/python.exe plugins/h2t-ops/skills/meetgeek/scripts/meetgeek_cli.py convert --help
~/.h2t/venv/Scripts/python.exe plugins/h2t-ops/skills/meetgeek/scripts/meetgeek_cli.py drive-upload --help
~/.h2t/venv/Scripts/python.exe plugins/h2t-ops/skills/meetgeek/scripts/meetgeek_cli.py upload --from-file C:/tmp/dummy_rec.webm --dry-run
~/.h2t/venv/Scripts/python.exe -m pytest plugins/h2t-ops/skills/meetgeek/tests/test_meetgeek_cli.py -v
~/.h2t/venv/Scripts/python.exe -m pytest tests/connectors/meetgeek/ -v
```

Expected: all exit 0 / all pass.

- [ ] **Step 8: Commit**

```bash
git add plugins/h2t-ops/skills/meetgeek/scripts/recovery.py
git add plugins/h2t-ops/skills/meetgeek/scripts/meetgeek_cli.py
git commit -m "feat(meetgeek): add recording_submission_artifact + thin CLI wrappers"
```

---

### Task 4: Recovery tests (extend)

**Files:**
- Modify: `tests/connectors/meetgeek/test_recovery.py`
- Modify: `tests/connectors/meetgeek/test_commands.py`

- [ ] **Step 1: Append remaining tests to test_recovery.py**

`tests/connectors/meetgeek/test_recovery.py` was created in T1. Append the following classes to the bottom of that file:

```python
# ─── ffmpeg_probe ─────────────────────────────────────────────────────────────

class TestFfmpegProbe:
    _STDERR_SAMPLE = (
        "Input #0, matroska,webm, from 'test.webm':\n"
        "  Duration: 00:01:23.45\n"
        "    Stream #0:0: Video: vp8\n"
        "    Stream #0:1: Audio: opus\n"
        "    Stream #0:2: Audio: opus\n"
        "Output #0, null, to 'pipe:'\n"
        "    Stream #0:0: Audio: pcm_s16le\n"
    )

    def test_parses_streams_and_duration(self, rec, tmp_path):
        dummy = tmp_path / "test.webm"
        dummy.write_bytes(b"x")
        fake_result = MagicMock(returncode=0, stderr=self._STDERR_SAMPLE)
        with patch.object(rec, "ffmpeg_exe", return_value="/usr/bin/ffmpeg"):
            with patch("subprocess.run", return_value=fake_result):
                probe = rec.ffmpeg_probe(str(dummy))
        assert probe["audio_streams"] == 2
        assert probe["has_video"] is True
        assert probe["duration_seconds"] == 83

    def test_ignores_output_section_audio(self, rec, tmp_path):
        dummy = tmp_path / "test.webm"
        dummy.write_bytes(b"x")
        fake_result = MagicMock(returncode=0, stderr=self._STDERR_SAMPLE)
        with patch.object(rec, "ffmpeg_exe", return_value="/usr/bin/ffmpeg"):
            with patch("subprocess.run", return_value=fake_result):
                probe = rec.ffmpeg_probe(str(dummy))
        assert probe["audio_streams"] == 2  # not 3; Output section excluded


# ─── process_one ──────────────────────────────────────────────────────────────

def _make_src(tmp_path: Path) -> Path:
    src = tmp_path / "meetgeek-recording-2026-05-20T10-00-00-1Z.webm"
    src.write_bytes(b"x" * 1024)
    return src


class TestProcessOne:
    def _mp4(self, tmp_path: Path) -> Path:
        p = tmp_path / "converted.mp4"
        p.write_bytes(b"y" * 2048)
        return p

    def test_full_pipeline_writes_submitted(self, rec, tmp_path, monkeypatch):
        src = _make_src(tmp_path)
        mp4 = self._mp4(tmp_path)
        manifest = tmp_path / "manifest.jsonl"
        drive_result = {"drive_id": "d1", "download_url": "https://example.com/d1",
                        "web_url": "https://drive.google.com/d1", "created": True}

        monkeypatch.setattr(rec, "convert_media", lambda s, **kw: mp4)
        monkeypatch.setattr(rec, "drive_upload_file", lambda p, **kw: drive_result)
        monkeypatch.setattr(rec, "submit_url_via_h2t_ops", lambda url, title, lang: {"message": "ok"})
        monkeypatch.setattr(rec, "emit_submission_artifact", lambda r, **kw: tmp_path / "art.json")

        result = rec.process_one(src, language="ru", title_override=None,
                                 audio_only=False, mix_mode="amix", manifest_path=manifest)

        assert result["status"] == "submitted"
        assert result["drive_id"] == "d1"
        lines = [json.loads(l) for l in manifest.read_text().splitlines() if l.strip()]
        statuses = [l["status"] for l in lines]
        assert statuses == ["converted", "in-drive", "submitted"]

    def test_resume_from_in_drive_skips_convert_and_drive(self, rec, tmp_path, monkeypatch):
        src = _make_src(tmp_path)
        mp4 = self._mp4(tmp_path)
        manifest = tmp_path / "manifest.jsonl"
        rec.append_uploads_manifest({
            "source_webm": str(src),
            "source_size_bytes": src.stat().st_size,
            "source_mtime": "2026-05-20T10:00:00Z",
            "mp4_path": str(mp4),
            "mp4_size_bytes": mp4.stat().st_size,
            "drive_id": "d2",
            "drive_download_url": "https://example.com/d2",
            "drive_web_url": None,
            "status": "in-drive",
        }, manifest)

        convert_calls = []
        drive_calls = []
        monkeypatch.setattr(rec, "convert_media", lambda s, **kw: convert_calls.append(1) or mp4)
        monkeypatch.setattr(rec, "drive_upload_file", lambda p, **kw: drive_calls.append(1) or {})
        monkeypatch.setattr(rec, "submit_url_via_h2t_ops", lambda url, title, lang: {"message": "ok"})
        monkeypatch.setattr(rec, "emit_submission_artifact", lambda r, **kw: tmp_path / "art.json")

        result = rec.process_one(src, language=None, title_override=None,
                                 audio_only=False, mix_mode="amix", manifest_path=manifest)

        assert result["status"] == "submitted"
        assert convert_calls == []
        assert drive_calls == []

    def test_convert_failure_writes_convert_failed(self, rec, tmp_path, monkeypatch):
        src = _make_src(tmp_path)
        manifest = tmp_path / "manifest.jsonl"

        def fail_convert(s, **kw):
            raise rec.RecoveryError("encode failed", exit_code=1)

        monkeypatch.setattr(rec, "convert_media", fail_convert)

        with pytest.raises(rec.RecoveryError):
            rec.process_one(src, language=None, title_override=None,
                            audio_only=False, mix_mode="amix", manifest_path=manifest)

        lines = [json.loads(l) for l in manifest.read_text().splitlines() if l.strip()]
        assert lines[-1]["status"] == "convert-failed"

    def test_drive_failure_writes_drive_failed(self, rec, tmp_path, monkeypatch):
        src = _make_src(tmp_path)
        mp4 = self._mp4(tmp_path)
        manifest = tmp_path / "manifest.jsonl"

        monkeypatch.setattr(rec, "convert_media", lambda s, **kw: mp4)
        monkeypatch.setattr(rec, "drive_upload_file",
                            lambda p, **kw: (_ for _ in ()).throw(rec.RecoveryError("auth failed")))

        with pytest.raises(rec.RecoveryError):
            rec.process_one(src, language=None, title_override=None,
                            audio_only=False, mix_mode="amix", manifest_path=manifest)

        lines = [json.loads(l) for l in manifest.read_text().splitlines() if l.strip()]
        assert lines[-1]["status"] == "drive-failed"

    def test_infers_title_from_filename(self, rec, tmp_path, monkeypatch):
        src = _make_src(tmp_path)
        mp4 = self._mp4(tmp_path)
        manifest = tmp_path / "manifest.jsonl"
        captured = {}

        def capture_submit(url, title, lang):
            captured["title"] = title
            return {"message": "ok"}

        monkeypatch.setattr(rec, "convert_media", lambda s, **kw: mp4)
        monkeypatch.setattr(rec, "drive_upload_file",
                            lambda p, **kw: {"drive_id": "d", "download_url": "u",
                                             "web_url": None, "created": True})
        monkeypatch.setattr(rec, "submit_url_via_h2t_ops", capture_submit)
        monkeypatch.setattr(rec, "emit_submission_artifact", lambda r, **kw: tmp_path / "art.json")

        rec.process_one(src, language=None, title_override=None,
                        audio_only=False, mix_mode="amix", manifest_path=manifest)

        assert captured["title"] == "Meeting 2026-05-20 10:00 UTC"


# ─── emit_submission_artifact ─────────────────────────────────────────────────

class TestEmitSubmissionArtifact:
    def test_writes_json_with_correct_type(self, rec, tmp_path):
        result = {
            "source_webm": str(tmp_path / "rec.webm"),
            "source_size_bytes": 1024,
            "source_mtime": "2026-05-20T10:00:00Z",
            "mp4_path": str(tmp_path / "rec.mp4"),
            "drive_id": "d1",
            "drive_download_url": "https://example.com/d1",
            "title": "Meeting 2026-05-20 10:00 UTC",
            "language": "ru",
            "submitted_at": "2026-05-20T10:05:00Z",
            "status": "submitted",
        }
        path = rec.emit_submission_artifact(result, artifact_dir=tmp_path)
        artifact = json.loads(path.read_text(encoding="utf-8"))
        assert artifact["artifact_type"] == "recording_submission_artifact"
        assert artifact["meetgeek_meeting_id"] is None
        assert artifact["provider"] == "meetgeek"
        assert artifact["drive_id"] == "d1"

    def test_output_filename_matches_source_stem(self, rec, tmp_path):
        result = {
            "source_webm": str(tmp_path / "my-recording.webm"),
            "source_size_bytes": 1024, "source_mtime": "2026-05-20T10:00:00Z",
            "mp4_path": None, "drive_id": None, "drive_download_url": None,
            "title": None, "language": None, "submitted_at": None, "status": "submitted",
        }
        path = rec.emit_submission_artifact(result, artifact_dir=tmp_path)
        assert path.name == "my-recording.submission.json"
```

- [ ] **Step 2: Append regression guard to test_commands.py**

`upload --download-url` fast-path must delegate to `_submit_url_via_h2t_ops`, not inline POST. Append to `tests/connectors/meetgeek/test_commands.py`:

```python
# ─── upload --download-url regression guard ───────────────────────────────────

class TestCmdUploadDirectUrl:
    """upload --download-url must delegate to _submit_url_via_h2t_ops, not inline POST.

    Regression guard: before #149 extraction this path called _request("POST", ...)
    inline inside cmd_upload. After extraction it must call _submit_url_via_h2t_ops.
    """

    def test_delegates_to_submit_url_not_inline_post(self, tmp_path, monkeypatch):
        import argparse
        import importlib.util
        import sys
        from pathlib import Path

        CLI = (Path(__file__).resolve().parent.parent.parent.parent
               / "plugins" / "h2t-ops" / "skills" / "meetgeek" / "scripts" / "meetgeek_cli.py")
        spec = importlib.util.spec_from_file_location("_cli_download_url_test", CLI)
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        sys.modules["_cli_download_url_test"] = mod
        spec.loader.exec_module(mod)

        captured = []
        monkeypatch.setattr(
            mod, "_submit_url_via_h2t_ops",
            lambda url, title, lang: captured.append((url, title, lang)) or {"message": "ok"},
        )

        args = argparse.Namespace(
            download_url="https://drive.usercontent.google.com/download?id=testfile&confirm=t",
            title="Test Meeting",
            language_code="ru",
            from_file=None,
            from_manifest=None,
            dry_run=False,
        )
        mod.cmd_upload(args)

        assert len(captured) == 1
        assert captured[0][0] == args.download_url
```

- [ ] **Step 3: Run all meetgeek tests**

```bash
~/.h2t/venv/Scripts/python.exe -m pytest tests/connectors/meetgeek/test_recovery.py -v
~/.h2t/venv/Scripts/python.exe -m pytest tests/connectors/meetgeek/test_commands.py -v
```

Expected: all tests pass. If any fail, fix them before continuing.

- [ ] **Step 4: Commit**

```bash
git add tests/connectors/meetgeek/test_recovery.py
git add tests/connectors/meetgeek/test_commands.py
git commit -m "test(meetgeek): add test_recovery.py + download_url regression guard"
```

---

### Task 5: Final verification

**Files:** no changes.

- [ ] **Step 1: Full test run**

```bash
~/.h2t/venv/Scripts/python.exe -m pytest plugins/h2t-ops/skills/meetgeek/tests/test_meetgeek_cli.py tests/connectors/meetgeek/ -v
```

Expected: all pass, no warnings about missing imports.

- [ ] **Step 2: All --help exits**

```bash
~/.h2t/venv/Scripts/python.exe plugins/h2t-ops/skills/meetgeek/scripts/meetgeek_cli.py convert --help
~/.h2t/venv/Scripts/python.exe plugins/h2t-ops/skills/meetgeek/scripts/meetgeek_cli.py upload --help
~/.h2t/venv/Scripts/python.exe plugins/h2t-ops/skills/meetgeek/scripts/meetgeek_cli.py drive-upload --help
~/.h2t/venv/Scripts/python.exe plugins/h2t-ops/skills/meetgeek/scripts/meetgeek_cli.py sync --help
~/.h2t/venv/Scripts/python.exe plugins/h2t-ops/skills/meetgeek/scripts/meetgeek_cli.py webhook-server --help
```

Expected: each exits 0.

- [ ] **Step 3: Dry-run with dummy fixture**

```bash
~/.h2t/venv/Scripts/python.exe plugins/h2t-ops/skills/meetgeek/scripts/meetgeek_cli.py upload --from-file C:/tmp/dummy_rec.webm --dry-run
```

Expected: `[1/1] dummy_rec.webm  would: convert+drive+upload`, exit 0.

- [ ] **Step 4: Connector boundary audit**

Verify these are TRUE:
- `recovery.py` contains no `argparse` import and no `argparse.Namespace` usage.
- `recovery.py` has no `h2t-ops meetgeek recover` command registered anywhere.
- `recovery.py` does not write to any POS journal path (`~/.dor/vault`).
- `meetgeek_cli.py` `cmd_upload` does not contain the body of `_process_one_for_upload` inline — it uses `_process_one_for_upload` alias from recovery.
- `h2t-ops meetgeek submit-url` delegation is the only provider-write in Stage 3.

```bash
grep -n "argparse" plugins/h2t-ops/skills/meetgeek/scripts/recovery.py
grep -n "vault" plugins/h2t-ops/skills/meetgeek/scripts/recovery.py
grep -n "_process_one_for_upload\|process_one" plugins/h2t-ops/skills/meetgeek/scripts/meetgeek_cli.py
grep -n "download_url\|_submit_url_via_h2t_ops\|_request.*POST.*v1.upload" plugins/h2t-ops/skills/meetgeek/scripts/meetgeek_cli.py
```

Expected:
- `argparse` → 0 results in recovery.py
- `vault` → 0 results in recovery.py
- meetgeek_cli.py shows `process_one as _process_one_for_upload` in the import block and usage in `cmd_upload`, not a full definition.
- `download_url` appears as argparse flag and in `cmd_upload` calling `_submit_url_via_h2t_ops`
- `_request.*POST.*v1.upload` → 0 results in meetgeek_cli.py (no inline POST bypassing recovery)

---

## Non-Goals (reminder)

- No `h2t-ops meetgeek recover` CLI verb
- No POS journal writes
- No provider-neutral Granola/Krisp abstraction
- No transcript interpretation or fusion
- No Drive connector replacement (blocked until Drive connector gains recovery-compatible semantics: hierarchy, public sharing, usercontent URL, idempotency)
- `sync` and `webhook-server` commands untouched
