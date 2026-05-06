"""
Tests for meetgeek_cli.

Covers spec scenarios:
- auth-check (200, 401)
- list (paginated, date filter)
- transcript (markdown format, unicode, pagination)
- sync (to temp dir, cursor update, cursor resume, idempotent dedup)
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "meetgeek_cli.py"


@pytest.fixture()
def cli(monkeypatch):
    """Load fresh meetgeek_cli module with deterministic env."""
    monkeypatch.setenv("MEETGEEK_API_KEY", "test-key")
    monkeypatch.setenv("MEETGEEK_BASE_URL", "https://api.test")
    spec = importlib.util.spec_from_file_location("meetgeek_cli_under_test", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["meetgeek_cli_under_test"] = mod
    spec.loader.exec_module(mod)
    return mod


class FakeResponse:
    def __init__(self, status_code: int = 200, body: object | None = None,
                 headers: dict | None = None, raw_bytes: bytes | None = None):
        self.status_code = status_code
        self._body = body if body is not None else {}
        self.headers = headers or {}
        self._raw = raw_bytes or b""
        self.text = json.dumps(self._body) if not raw_bytes else ""

    def json(self):
        return self._body

    def iter_content(self, chunk_size: int = 1024):
        yield self._raw

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _scripted_request(scripts: list[FakeResponse]):
    """Return a callable that returns FakeResponses in order, recording calls."""
    calls: list[dict] = []
    iterator = iter(scripts)

    def fake(method, url, **kwargs):
        calls.append({"method": method, "url": url, **kwargs})
        try:
            return next(iterator)
        except StopIteration:
            raise AssertionError(f"Unexpected request: {method} {url}")

    return fake, calls


# ─── auth-check ────────────────────────────────────────────────────────────────

def test_auth_check_returns_ok(cli, capsys):
    fake, _ = _scripted_request([FakeResponse(200, {"meetings": []})])
    with patch.object(cli.requests, "request", fake):
        rc = cli.main(["auth-check"])
    assert rc == 0
    assert "OK" in capsys.readouterr().out


def test_auth_check_invalid_key(cli, capsys):
    fake, _ = _scripted_request([FakeResponse(401, {"error": "bad key"})])
    with patch.object(cli.requests, "request", fake):
        rc = cli.main(["auth-check"])
    assert rc == 1
    assert "401" in capsys.readouterr().err


# ─── list ──────────────────────────────────────────────────────────────────────

def test_list_paginated(cli, capsys):
    page1 = {"data": [{"meeting_id": "a"}, {"meeting_id": "b"}], "next_cursor": "c1"}
    page2 = {"data": [{"meeting_id": "c"}], "next_cursor": None}
    fake, calls = _scripted_request([FakeResponse(200, page1), FakeResponse(200, page2)])
    with patch.object(cli.requests, "request", fake):
        rc = cli.main(["list"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert [m["meeting_id"] for m in out] == ["a", "b", "c"]
    assert calls[1]["params"] == {"cursor": "c1"}


def test_list_date_filter(cli):
    fake, calls = _scripted_request([FakeResponse(200, {"data": []})])
    with patch.object(cli.requests, "request", fake):
        cli.main(["list", "--from-date", "2026-04-01", "--to-date", "2026-05-01"])
    assert calls[0]["params"]["from_date"] == "2026-04-01"
    assert calls[0]["params"]["to_date"] == "2026-05-01"


# ─── transcript ────────────────────────────────────────────────────────────────

_RU_SENTENCES = [
    {"speaker": "Максим Фадеев", "timestamp": "13:19:24", "transcript": "Должно работать"},
    {"speaker": "Stanislav", "timestamp": "13:19:30", "transcript": "Проверим"},
]


def test_transcript_markdown_format(cli, tmp_path, capsys):
    # transcript page (single) + meeting meta call
    fake, _ = _scripted_request([
        FakeResponse(200, {"meeting_id": "mid-1", "sentences": _RU_SENTENCES}),
        FakeResponse(200, {"id": "mid-1", "title": "Стрим: тест", "start_time": "2026-03-12T13:19:06Z"}),
    ])
    out_path = tmp_path / "tx.md"
    with patch.object(cli.requests, "request", fake):
        rc = cli.main(["transcript", "mid-1", "-o", str(out_path)])
    assert rc == 0
    md = out_path.read_text(encoding="utf-8")
    assert "meeting_id: mid-1" in md
    assert "Максим Фадеев" in md
    assert "## Transcript" in md


def test_transcript_extracts_attendees_from_speakers(cli, tmp_path):
    fake, _ = _scripted_request([
        FakeResponse(200, {"meeting_id": "mid", "sentences": _RU_SENTENCES}),
        FakeResponse(200, {"id": "mid", "title": "t"}),
    ])
    out_path = tmp_path / "tx.md"
    with patch.object(cli.requests, "request", fake):
        cli.main(["transcript", "mid", "-o", str(out_path)])
    md = out_path.read_text(encoding="utf-8")
    assert "Максим Фадеев" in md
    assert "Stanislav" in md
    # frontmatter attendees line carries both
    fm = md.split("---")[1]
    assert "attendees:" in fm
    assert "Максим Фадеев" in fm
    assert "Stanislav" in fm


def test_transcript_unicode_no_escaping(cli, tmp_path):
    fake, _ = _scripted_request([
        FakeResponse(200, {"meeting_id": "mid", "sentences": _RU_SENTENCES}),
        FakeResponse(200, {"id": "mid", "title": "x"}),
    ])
    out_path = tmp_path / "tx.md"
    with patch.object(cli.requests, "request", fake):
        rc = cli.main(["transcript", "mid", "-o", str(out_path)])
    assert rc == 0
    raw = out_path.read_text(encoding="utf-8")
    assert "\\u" not in raw  # no escape sequences in output
    assert "Должно работать" in raw


def test_transcript_pagination_assembled(cli, tmp_path):
    page1 = {"meeting_id": "mid", "sentences": [{"speaker": "A", "transcript": "p1"}],
             "pagination": {"next_cursor": "p2"}}
    page2 = {"meeting_id": "mid", "sentences": [{"speaker": "B", "transcript": "p2text"}],
             "pagination": {"next_cursor": None}}
    meta = {"id": "mid", "title": "t"}
    fake, calls = _scripted_request([
        FakeResponse(200, page1), FakeResponse(200, page2), FakeResponse(200, meta),
    ])
    out = tmp_path / "tx.json"
    with patch.object(cli.requests, "request", fake):
        cli.main(["transcript", "mid", "--format", "json", "-o", str(out)])
    data = json.loads(out.read_text(encoding="utf-8"))
    assert len(data["sentences"]) == 2
    assert data["sentences"][1]["transcript"] == "p2text"
    # cursor passed on second call
    assert calls[1]["params"] == {"cursor": "p2"}


# ─── sync ──────────────────────────────────────────────────────────────────────

def test_sync_to_temp_dir(cli, tmp_path):
    meetings = {"data": [
        {"meeting_id": "m1", "title": "T1", "start_time": "2026-04-10T10:00:00Z"},
        {"meeting_id": "m2", "title": "T2", "start_time": "2026-04-11T10:00:00Z"},
    ]}
    tx = {"meeting_id": "_", "sentences": [{"speaker": "x", "transcript": "y"}]}
    fake, _ = _scripted_request([
        FakeResponse(200, meetings),
        FakeResponse(200, tx),  # m1 transcript
        FakeResponse(200, tx),  # m2 transcript
    ])
    cursor_file = tmp_path / "cursor.json"
    with patch.object(cli.requests, "request", fake):
        rc = cli.main([
            "sync", "--to", str(tmp_path / "lake"),
            "--include", "transcripts", "--limit", "2",
            "--cursor-file", str(cursor_file),
        ])
    assert rc == 0
    lake = tmp_path / "lake"
    manifest = (lake / "manifest.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(manifest) == 2
    assert (lake / "transcripts" / "m1.md").exists()
    assert (lake / "transcripts" / "m2.json").exists()
    cur = json.loads(cursor_file.read_text())
    assert cur["last_seen_id"] == "m2"
    assert cur["items_ingested"] == 2


def test_sync_idempotent_dedup(cli, tmp_path):
    meetings = {"data": [{"meeting_id": "m1", "title": "T", "start_time": "2026-04-10T10:00:00Z"}]}
    tx = {"sentences": []}
    cursor_file = tmp_path / "cursor.json"
    lake = tmp_path / "lake"

    # first run: fetch list + tx
    fake1, _ = _scripted_request([FakeResponse(200, meetings), FakeResponse(200, tx)])
    with patch.object(cli.requests, "request", fake1):
        cli.main(["sync", "--to", str(lake), "--include", "transcripts",
                  "--limit", "1", "--cursor-file", str(cursor_file)])

    # second run: only list (m1 already in manifest -> skipped, no tx fetch)
    fake2, calls2 = _scripted_request([FakeResponse(200, meetings)])
    with patch.object(cli.requests, "request", fake2):
        rc = cli.main(["sync", "--to", str(lake), "--include", "transcripts",
                       "--limit", "1", "--cursor-file", str(cursor_file)])
    assert rc == 0
    assert len(calls2) == 1  # no transcript fetch
    manifest = (lake / "manifest.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(manifest) == 1


def test_sync_cursor_resume_filters_seen_ts(cli, tmp_path):
    cursor_file = tmp_path / "cursor.json"
    cursor_file.write_text(json.dumps({
        "source": "meetgeek",
        "last_seen_ts": "2026-04-10T12:00:00Z",
        "last_seen_id": "old",
        "items_ingested": 1,
        "version": 1,
    }))
    lake = tmp_path / "lake"

    # API returns old + new; only newer should be processed
    page = {"data": [
        {"meeting_id": "old", "start_time": "2026-04-10T12:00:00Z"},
        {"meeting_id": "new", "start_time": "2026-04-11T09:00:00Z", "title": "n"},
    ]}
    tx = {"sentences": []}
    fake, calls = _scripted_request([FakeResponse(200, page), FakeResponse(200, tx)])
    with patch.object(cli.requests, "request", fake):
        rc = cli.main(["sync", "--to", str(lake), "--include", "transcripts",
                       "--since-cursor", "--cursor-file", str(cursor_file)])
    assert rc == 0
    # from_date passed as date slice of last_seen_ts
    assert calls[0]["params"].get("from_date") == "2026-04-10"
    # only "new" got transcript fetch
    assert len(calls) == 2
    assert "/v1/meetings/new/transcript" in calls[1]["url"]


# ─── YAML safety ───────────────────────────────────────────────────────────────

# ─── recordings (sync --include) ──────────────────────────────────────────────

def test_sync_recordings_streams_file(cli, tmp_path):
    meetings = {"meetings": [{"meeting_id": "m1", "title": "T", "start_time": "2026-04-10T10:00:00Z"}]}
    download_resp = {"download_link": "https://media.meetgeek.ai/api/download?token=xyz"}
    cursor_file = tmp_path / "cursor.json"
    lake = tmp_path / "lake"

    fake, calls = _scripted_request([
        FakeResponse(200, meetings),       # /v1/meetings list
        FakeResponse(200, download_resp),  # POST /download
        FakeResponse(200, raw_bytes=b"FAKE_MP4_BYTES"),  # streamed file
    ])
    with patch.object(cli.requests, "request", fake), \
         patch.object(cli.requests, "get", lambda url, **kw: fake("GET", url, **kw)):
        rc = cli.main(["sync", "--to", str(lake), "--include", "recordings",
                       "--limit", "1", "--cursor-file", str(cursor_file)])
    assert rc == 0
    rec_path = lake / "recordings" / "m1.mp4"
    assert rec_path.exists() and rec_path.read_bytes() == b"FAKE_MP4_BYTES"
    # verify POST was used for /download endpoint
    download_call = [c for c in calls if c["url"].endswith("/download")][0]
    assert download_call["method"] == "POST"


# ─── webhook server (smoke) ───────────────────────────────────────────────────

def test_webhook_server_writes_event(cli, tmp_path):
    import threading
    import urllib.error
    import urllib.request
    import socket

    # find free port
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]

    out = tmp_path / "webhooks"
    args = ["webhook-server", "--port", str(port), "--bind", "127.0.0.1",
            "--out", str(out), "--secret", "S"]
    # Run server in a thread; stop via shutdown after one event
    parser = cli.build_parser()
    parsed = parser.parse_args(args)
    from http.server import ThreadingHTTPServer
    original_serve = ThreadingHTTPServer.serve_forever
    server_holder: dict = {}

    def capture_serve(self, *a, **kw):
        server_holder["s"] = self
        return original_serve(self, *a, **kw)

    with patch.object(ThreadingHTTPServer, "serve_forever", capture_serve):
        t = threading.Thread(target=cli.cmd_webhook_server, args=(parsed,), daemon=True)
        t.start()
        # wait for server start
        for _ in range(50):
            if "s" in server_holder:
                break
            import time as _t; _t.sleep(0.02)
        assert "s" in server_holder, "server did not start"

        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/event",
            data=json.dumps({"event": "meeting.completed", "id": "abc"}).encode("utf-8"),
            headers={"Content-Type": "application/json", "X-Webhook-Secret": "S"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=2) as resp:
            assert resp.status == 200

        # 401 without secret
        req2 = urllib.request.Request(
            f"http://127.0.0.1:{port}/event", data=b"{}",
            headers={"Content-Type": "application/json"}, method="POST")
        try:
            urllib.request.urlopen(req2, timeout=2)
            raise AssertionError("expected 401")
        except urllib.error.HTTPError as e:
            assert e.code == 401

        server_holder["s"].shutdown()
        t.join(timeout=2)

    files = list(out.glob("*.json"))
    assert len(files) == 1
    rec = json.loads(files[0].read_text(encoding="utf-8"))
    assert rec["payload"]["event"] == "meeting.completed"
    assert rec["path"] == "/event"


def test_frontmatter_escapes_special_chars(cli):
    val = cli._yaml_value('title with "quotes" and: colon')
    assert val.startswith('"') and val.endswith('"')
    parsed = json.loads(val)
    assert parsed == 'title with "quotes" and: colon'


def test_frontmatter_list_with_special_chars(cli):
    val = cli._yaml_value(["A, B", "with: colon"])
    parsed = json.loads(val)
    assert parsed == ["A, B", "with: colon"]


# ─── ffmpeg probe ──────────────────────────────────────────────────────────────

def test_ffmpeg_probe_single_audio_stream(cli, monkeypatch):
    """Single audio Stream line in stderr → audio_streams=1."""
    fake_stderr = (
        "ffmpeg version 6.0\n"
        "  Stream #0:0(eng): Video: vp9, 1280x720, 30 fps\n"
        "  Stream #0:1(eng): Audio: opus, 48000 Hz, stereo\n"
        "Duration: 00:41:23.45\n"
    )
    class R:
        returncode = 0
        stderr = fake_stderr
        stdout = ""
    monkeypatch.setattr(cli.subprocess, "run", lambda *a, **kw: R())
    info = cli._ffmpeg_probe("/fake/in.webm")
    assert info["audio_streams"] == 1
    assert info["has_video"] is True
    assert info["duration_seconds"] == 41 * 60 + 23


def test_ffmpeg_probe_multi_audio_streams(cli, monkeypatch):
    fake_stderr = (
        "  Stream #0:0: Video: h264, 1920x1080\n"
        "  Stream #0:1(eng): Audio: aac, 48000 Hz, stereo\n"
        "  Stream #0:2(rus): Audio: aac, 48000 Hz, stereo\n"
        "  Stream #0:3: Audio: aac, 44100 Hz, mono\n"
        "Duration: 01:00:00.00\n"
    )
    class R:
        returncode = 0
        stderr = fake_stderr
        stdout = ""
    monkeypatch.setattr(cli.subprocess, "run", lambda *a, **kw: R())
    info = cli._ffmpeg_probe("/fake.mp4")
    assert info["audio_streams"] == 3
    assert info["has_video"] is True
    assert info["duration_seconds"] == 3600


def test_ffmpeg_probe_corrupted_raises(cli, monkeypatch):
    class R:
        returncode = 1
        stderr = "Invalid data found when processing input\n"
        stdout = ""
    monkeypatch.setattr(cli.subprocess, "run", lambda *a, **kw: R())
    import pytest as _pytest
    with _pytest.raises(cli.ApiError):
        cli._ffmpeg_probe("/broken.webm")
