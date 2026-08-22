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
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "meetgeek_cli.py"

# Captured before any fixture redirects HOME — the production path the suite must never touch.
_REAL_HOME = Path.home()


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
    mod._ffmpeg_probe.__globals__["ffmpeg_exe"] = lambda: "ffmpeg"
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


def test_meeting_pick_reads_timestamp_start_utc(cli):
    """Regression: list endpoint returns timestamp_start_utc / timestamp_end_utc;
    earlier picker only checked start_time/created_at and lost dates for the
    entire historical backfill (~200 entries with null timestamps).
    """
    m = {
        "meeting_id": "abc",
        "title": "Test",
        "timestamp_start_utc": "2026-04-18T13:55:34Z",
        "timestamp_end_utc": "2026-04-18T14:55:34Z",
    }
    out = cli._meeting_pick(m)
    assert out["timestamp_start_utc"] == "2026-04-18T13:55:34Z"
    assert out["timestamp_end_utc"] == "2026-04-18T14:55:34Z"
    assert out["date"] == "2026-04-18"


def test_meeting_pick_falls_back_to_start_time(cli):
    """Older response shapes (or `/v1/meeting/{id}`) used start_time."""
    m = {"meeting_id": "x", "start_time": "2026-01-01T00:00:00Z"}
    out = cli._meeting_pick(m)
    assert out["timestamp_start_utc"] == "2026-01-01T00:00:00Z"
    assert out["date"] == "2026-01-01"


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
    with _pytest.raises((cli.ApiError, cli.RecoveryError)):
        cli._ffmpeg_probe("/broken.webm")


def test_ffmpeg_probe_ignores_output_section_audio_streams(cli, monkeypatch):
    """Regression: ffmpeg also prints Stream #...: Audio: lines for the null
    muxer's Output # block; those must NOT count toward input audio_streams.
    """
    fake_stderr = (
        "Input #0, matroska,webm, from 'x.webm':\n"
        "  Stream #0:0(eng): Video: vp8, 1280x720\n"
        "  Stream #0:1(eng): Audio: opus, 48000 Hz, stereo\n"
        "Output #0, null, to 'pipe:':\n"
        "  Stream #0:0(eng): Video: rawvideo\n"
        "  Stream #0:1(eng): Audio: pcm_s16le, 48000 Hz, stereo\n"
        "frame= 100 fps=30\n"
        "video:1KiB audio:42KiB\n"
    )
    class R:
        returncode = 0
        stderr = fake_stderr
        stdout = ""
    monkeypatch.setattr(cli.subprocess, "run", lambda *a, **kw: R())
    info = cli._ffmpeg_probe("/fake.webm")
    assert info["audio_streams"] == 1  # only the input stream, not the null-muxer output
    assert info["has_video"] is True


# ─── convert ───────────────────────────────────────────────────────────────────

def test_convert_single_track_builds_simple_recipe(cli, tmp_path, monkeypatch):
    src = tmp_path / "in.webm"
    src.write_bytes(b"x")  # presence-only; ffmpeg is mocked

    # probe → 1 audio stream, has_video
    monkeypatch.setattr(cli, "_ffmpeg_probe",
                        lambda p: {"audio_streams": 1, "has_video": True,
                                   "duration_seconds": 60, "raw_stderr_tail": ""})

    captured: dict = {}

    def fake_run(cmd, **kw):
        captured["cmd"] = cmd
        # write a fake mp4 so size>1KB check passes
        out_path = cmd[-1]
        from pathlib import Path as P
        P(out_path).write_bytes(b"M" * 2048)
        class R:
            returncode = 0; stderr = ""; stdout = ""
        return R()

    monkeypatch.setattr(cli.subprocess, "run", fake_run)

    out = tmp_path / "out.mp4"
    rc = cli.main(["convert", str(src), "-o", str(out)])
    assert rc == 0
    assert out.exists() and out.stat().st_size > 1024
    cmd = captured["cmd"]
    assert "-c:v" in cmd and "libx264" in cmd
    assert "-c:a" in cmd and "aac" in cmd
    # single-track path should NOT use amix filter
    assert not any("amix=" in a for a in cmd)


def test_convert_skip_if_cached(cli, tmp_path, monkeypatch):
    src = tmp_path / "in.webm"; src.write_bytes(b"x")
    out = tmp_path / "out.mp4"; out.write_bytes(b"M" * 2048)  # already big enough

    monkeypatch.setattr(cli, "_ffmpeg_probe",
                        lambda p: {"audio_streams": 1, "has_video": True,
                                   "duration_seconds": 60, "raw_stderr_tail": ""})
    called = {"n": 0}
    def no_run(*a, **kw):
        called["n"] += 1
        raise AssertionError("ffmpeg should not run when cache hit")
    monkeypatch.setattr(cli.subprocess, "run", no_run)

    rc = cli.main(["convert", str(src), "-o", str(out)])
    assert rc == 0
    assert called["n"] == 0


def test_convert_corrupted_raises(cli, tmp_path, monkeypatch):
    src = tmp_path / "broken.webm"; src.write_bytes(b"x")
    def bad_probe(p): raise cli.ApiError("ffmpeg cannot probe", exit_code=1)
    monkeypatch.setattr(cli, "_ffmpeg_probe", bad_probe)
    rc = cli.main(["convert", str(src), "-o", str(tmp_path / "out.mp4")])
    assert rc == 1


def test_convert_single_track_maps_audio_explicitly(cli, tmp_path, monkeypatch):
    """Regression: when any -map is specified, ffmpeg disables auto-mapping.
    The single-track recipe used to give -map 0:v? without an audio map,
    silently producing video-only mp4 that MeetGeek then rejects as Failed.
    """
    src = tmp_path / "in.webm"; src.write_bytes(b"x")
    monkeypatch.setattr(cli, "_ffmpeg_probe",
                        lambda p: {"audio_streams": 1, "has_video": True,
                                   "duration_seconds": 60, "raw_stderr_tail": ""})
    captured: dict = {}
    def fake_run(cmd, **kw):
        captured["cmd"] = cmd
        from pathlib import Path as P
        P(cmd[-1]).write_bytes(b"M" * 2048)
        class R: returncode = 0; stderr = ""; stdout = ""
        return R()
    monkeypatch.setattr(cli.subprocess, "run", fake_run)

    cli.main(["convert", str(src), "-o", str(tmp_path / "out.mp4")])
    cmd = captured["cmd"]
    # Both video and audio maps must be present
    map_args = [cmd[i + 1] for i, a in enumerate(cmd) if a == "-map"]
    assert "0:v?" in map_args
    assert "0:a:0?" in map_args


def test_convert_audio_only_still_maps_audio(cli, tmp_path, monkeypatch):
    """audio_only must map audio stream explicitly (in addition to -vn)."""
    src = tmp_path / "in.webm"; src.write_bytes(b"x")
    monkeypatch.setattr(cli, "_ffmpeg_probe",
                        lambda p: {"audio_streams": 1, "has_video": True,
                                   "duration_seconds": 60, "raw_stderr_tail": ""})
    captured: dict = {}
    def fake_run(cmd, **kw):
        captured["cmd"] = cmd
        from pathlib import Path as P
        P(cmd[-1]).write_bytes(b"M" * 2048)
        class R: returncode = 0; stderr = ""; stdout = ""
        return R()
    monkeypatch.setattr(cli.subprocess, "run", fake_run)

    cli.main(["convert", str(src), "-o", str(tmp_path / "out.m4a"), "--audio-only"])
    cmd = captured["cmd"]
    map_args = [cmd[i + 1] for i, a in enumerate(cmd) if a == "-map"]
    assert "0:a:0?" in map_args
    assert "-vn" in cmd


def test_convert_multi_track_uses_amix(cli, tmp_path, monkeypatch):
    src = tmp_path / "in.webm"; src.write_bytes(b"x")
    monkeypatch.setattr(cli, "_ffmpeg_probe",
                        lambda p: {"audio_streams": 3, "has_video": True,
                                   "duration_seconds": 60, "raw_stderr_tail": ""})
    captured: dict = {}
    def fake_run(cmd, **kw):
        captured["cmd"] = cmd
        from pathlib import Path as P
        P(cmd[-1]).write_bytes(b"M" * 2048)
        class R: returncode = 0; stderr = ""; stdout = ""
        return R()
    monkeypatch.setattr(cli.subprocess, "run", fake_run)

    out = tmp_path / "out.mp4"
    rc = cli.main(["convert", str(src), "-o", str(out)])
    assert rc == 0
    cmd = captured["cmd"]
    fc_idx = cmd.index("-filter_complex")
    filtergraph = cmd[fc_idx + 1]
    assert "amix=inputs=3" in filtergraph
    assert "[0:a:0][0:a:1][0:a:2]" in filtergraph
    assert "duration=longest" in filtergraph
    assert "aresample=48000" in filtergraph
    assert '[a]' in cmd


def test_convert_mix_mode_first_picks_first_stream(cli, tmp_path, monkeypatch):
    src = tmp_path / "in.webm"; src.write_bytes(b"x")
    monkeypatch.setattr(cli, "_ffmpeg_probe",
                        lambda p: {"audio_streams": 3, "has_video": True,
                                   "duration_seconds": 60, "raw_stderr_tail": ""})
    captured = {}
    def fake_run(cmd, **kw):
        captured["cmd"] = cmd
        from pathlib import Path as P
        P(cmd[-1]).write_bytes(b"M" * 2048)
        class R: returncode = 0; stderr = ""; stdout = ""
        return R()
    monkeypatch.setattr(cli.subprocess, "run", fake_run)

    cli.main(["convert", str(src), "-o", str(tmp_path / "out.mp4"), "--mix-mode", "first"])
    cmd = captured["cmd"]
    assert "-filter_complex" not in cmd
    # mapping uses optional `?` form (0:a:0?) to tolerate truncated containers
    assert any("0:a:0" in a for a in cmd)


def test_convert_audio_only_strips_video_codec_flags(cli, tmp_path, monkeypatch):
    src = tmp_path / "in.webm"; src.write_bytes(b"x")
    monkeypatch.setattr(cli, "_ffmpeg_probe",
                        lambda p: {"audio_streams": 1, "has_video": True,
                                   "duration_seconds": 60, "raw_stderr_tail": ""})
    captured = {}
    def fake_run(cmd, **kw):
        captured["cmd"] = cmd
        from pathlib import Path as P
        P(cmd[-1]).write_bytes(b"M" * 2048)
        class R: returncode = 0; stderr = ""; stdout = ""
        return R()
    monkeypatch.setattr(cli.subprocess, "run", fake_run)

    cli.main(["convert", str(src), "-o", str(tmp_path / "out.m4a"), "--audio-only"])
    cmd = captured["cmd"]
    assert "libx264" not in cmd
    assert "-vn" in cmd
    assert "aac" in cmd


# ─── drive upload ──────────────────────────────────────────────────────────────

def test_drive_download_url_uses_usercontent_with_confirm(cli):
    """Regression: large Drive files (>100 MB) need usercontent host +
    confirm=t to bypass virus-scan HTML interstitial. Live-verified that
    drive.google.com/uc?... returns text/html for big files."""
    url = cli._drive_download_url("ABC123")
    assert "drive.usercontent.google.com/download" in url
    assert "id=ABC123" in url
    assert "confirm=t" in url


def test_drive_service_raises_when_token_missing(cli, tmp_path, monkeypatch):
    import sys as _sys
    _rec_mod = _sys.modules.get("recovery")
    assert _rec_mod is not None, "recovery module not found in sys.modules"
    monkeypatch.setattr(_rec_mod, "DRIVE_TOKEN_FILE", tmp_path / "missing.json")
    import pytest as _p
    with _p.raises((cli.ApiError, cli.RecoveryError)) as e:
        cli._drive_service()
    assert "tokens.json" in str(e.value).lower() or "drive auth" in str(e.value).lower()


def test_drive_upload_idempotent_returns_existing(cli, tmp_path, monkeypatch):
    file_path = tmp_path / "test.mp4"; file_path.write_bytes(b"M" * 1024)

    folder_resp = {"files": [{"id": "FOLDER123", "name": "MeetGeek Uploads"}]}
    dated_resp = {"files": [{"id": "DATED456", "name": "2026-05-06"}]}
    file_resp = {"files": [{"id": "EXISTING789", "name": "test.mp4",
                            "webViewLink": "https://drive.google.com/file/d/EXISTING789"}]}
    responses = [folder_resp, dated_resp, file_resp]

    class FakeService:
        def files(self): return self
        def list(self, **kw):
            self._resp = responses.pop(0); return self
        def execute(self): return self._resp
        def permissions(self):
            class _P:
                def create(self, **kw):
                    class _R:
                        def execute(self): return {"id": "perm_x"}
                    return _R()
            return _P()

    import sys as _sys
    _rec_mod = _sys.modules.get("recovery")
    assert _rec_mod is not None, "recovery module not found"
    monkeypatch.setattr(_rec_mod, "drive_service", lambda: FakeService())

    rc = cli.main(["drive-upload", str(file_path)])
    assert rc == 0


# ─── upload (POST /v1/upload) ─────────────────────────────────────────────────

def test_upload_direct_url_succeeds_on_202(cli, monkeypatch, capsys):
    captured = []
    monkeypatch.setattr(cli, "_submit_url_via_h2t_ops",
                        lambda url, title, lang: captured.append((url, title, lang)) or {"message": "submitted"})
    rc = cli.main(["upload", "--download-url", "https://example.com/x.mp4",
                   "--title", "Test", "--language", "ru"])
    assert rc == 0
    assert len(captured) == 1
    assert captured[0][0] == "https://example.com/x.mp4"
    assert captured[0][1] == "Test"
    assert captured[0][2] == "ru"


def test_upload_direct_url_401_aborts(cli, monkeypatch):
    def _fail(url, title, lang):
        raise cli.ApiError("unauthorized", exit_code=1)
    monkeypatch.setattr(cli, "_submit_url_via_h2t_ops", _fail)
    rc = cli.main(["upload", "--download-url", "https://example.com/x.mp4"])
    assert rc == 1


def test_upload_direct_url_400_invalid(cli, monkeypatch):
    def _fail(url, title, lang):
        raise cli.ApiError("bad: download_url field is not a valid url", exit_code=1)
    monkeypatch.setattr(cli, "_submit_url_via_h2t_ops", _fail)
    rc = cli.main(["upload", "--download-url", "not-a-url"])
    assert rc == 1


def test_drive_upload_creates_dated_folder_and_uploads(cli, tmp_path, monkeypatch):
    file_path = tmp_path / "x.mp4"; file_path.write_bytes(b"M" * 1024)
    state = {"folders": {}, "files": {}, "perm_calls": []}

    class _FakePerms:
        def __init__(self, s): self.s = s
        def create(self, fileId, body, fields=None):
            self.s["perm_calls"].append((fileId, body))
            class _R:
                def execute(_): return {"id": "perm_x"}
            return _R()

    class FakeService:
        def files(self): return self
        def list(self, q, **kw):
            self._mode = ("folder" if "folder" in q else "file")
            return self
        def create(self, body, fields=None, media_body=None):
            self._create_body = body
            return self
        def permissions(self): return _FakePerms(state)
        def execute(self):
            if getattr(self, "_create_body", None):
                b = self._create_body; self._create_body = None
                if b.get("mimeType") == "application/vnd.google-apps.folder":
                    new_id = f"FOLDER_{b['name']}"
                    state["folders"][b["name"]] = new_id
                    return {"id": new_id}
                else:
                    new_id = f"FILE_{b['name']}"
                    state["files"][b["name"]] = new_id
                    return {"id": new_id, "webViewLink": f"https://drive/{new_id}"}
            return {"files": []}

    import sys as _sys
    _rec_mod = _sys.modules.get("recovery")
    assert _rec_mod is not None, "recovery module not found"
    monkeypatch.setattr(_rec_mod, "drive_service", lambda: FakeService())
    # MediaFileUpload imported lazily inside drive_upload_file — patch via googleapiclient.http
    import googleapiclient.http as _ghttp
    monkeypatch.setattr(_ghttp, "MediaFileUpload", lambda *a, **kw: object())

    rc = cli.main(["drive-upload", str(file_path)])
    assert rc == 0
    assert any(f.startswith("FILE_") for f in state["files"].values())
    assert len(state["perm_calls"]) == 1
    assert state["perm_calls"][0][1] == {"type": "anyone", "role": "reader"}


# ─── uploads manifest ──────────────────────────────────────────────────────────

def test_uploads_manifest_last_line_wins(cli, tmp_path):
    m = tmp_path / "manifest.jsonl"
    lines = [
        {"source_webm": "/a.webm", "status": "converted",
         "source_size_bytes": 100, "source_mtime": "2026-05-06T10:00:00Z"},
        {"source_webm": "/a.webm", "status": "in-drive",
         "source_size_bytes": 100, "source_mtime": "2026-05-06T10:00:00Z",
         "drive_id": "X"},
        {"source_webm": "/b.webm", "status": "submitted",
         "source_size_bytes": 200, "source_mtime": "2026-05-06T11:00:00Z"},
    ]
    with m.open("w", encoding="utf-8") as f:
        for r in lines:
            f.write(json.dumps(r) + "\n")
    state = cli._read_uploads_manifest(m)
    assert state["/a.webm"]["status"] == "in-drive"
    assert state["/a.webm"]["drive_id"] == "X"
    assert state["/b.webm"]["status"] == "submitted"


def test_uploads_manifest_skip_existing_size_mtime_match(cli, tmp_path):
    m = tmp_path / "manifest.jsonl"
    rec = {"source_webm": "/x.webm", "status": "submitted",
           "source_size_bytes": 100, "source_mtime": "2026-05-06T10:00:00Z"}
    m.write_text(json.dumps(rec) + "\n", encoding="utf-8")
    state = cli._read_uploads_manifest(m)
    assert cli._is_already_submitted(state, "/x.webm",
                                     size=100, mtime="2026-05-06T10:00:00Z") is True
    assert cli._is_already_submitted(state, "/x.webm",
                                     size=200, mtime="2026-05-06T10:00:00Z") is False
    assert cli._is_already_submitted(state, "/x.webm",
                                     size=100, mtime="2026-05-06T11:00:00Z") is False


# ─── upload --from-file (single file) ─────────────────────────────────────────

def test_upload_from_file_chains_convert_drive_submit(cli, tmp_path, monkeypatch):
    src = tmp_path / "meetgeek-recording-2026-01-20T15-44-31-132Z.webm"
    src.write_bytes(b"x" * 1024)

    import sys as _sys
    _rec_mod = _sys.modules.get("recovery")
    assert _rec_mod is not None, "recovery module not found in sys.modules"

    calls = []

    def fake_convert_media(src_p, *, audio_only, mix_mode, output_path=None):
        calls.append(("convert", str(src_p)))
        from pathlib import Path as P
        out = output_path or (cli._staging_dir() / (P(str(src_p)).stem + ".mp4"))
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"M" * 2048)
        return out

    posted = []
    def fake_post_upload(url, title, lang):
        posted.append({"url": url, "title": title, "lang": lang})
        return {"message": "submitted (mock)"}

    monkeypatch.setattr(_rec_mod, "convert_media", fake_convert_media)
    monkeypatch.setattr(_rec_mod, "submit_url_via_h2t_ops", fake_post_upload)
    monkeypatch.setattr(_rec_mod, "drive_upload_file",
                        lambda path, **kw:
                        {"drive_id": "FAKE", "download_url": "https://example.com/dl/FAKE",
                         "web_url": "https://drive/FAKE", "created": True})

    manifest = tmp_path / "manifest.jsonl"
    monkeypatch.setattr(cli, "_uploads_manifest_path", lambda: manifest)

    rc = cli.main(["upload", "--from-file", str(src), "--language", "ru"])
    assert rc == 0
    assert len(posted) == 1
    assert posted[0]["url"] == "https://example.com/dl/FAKE"
    assert "2026-01-20" in (posted[0]["title"] or "")
    lines = manifest.read_text(encoding="utf-8").strip().splitlines()
    assert any('"status": "submitted"' in ln for ln in lines)


def test_upload_from_file_glob_processes_all(cli, tmp_path, monkeypatch):
    a = tmp_path / "meetgeek-recording-2026-01-01T10-00-00-000Z.webm"
    b = tmp_path / "meetgeek-recording-2026-01-02T11-00-00-000Z.webm"
    a.write_bytes(b"x" * 1024); b.write_bytes(b"x" * 1024)

    posted = []
    def fake_process(src, **kw):
        posted.append(src.name)
        return {"source_webm": str(src), "status": "submitted"}
    monkeypatch.setattr(cli, "_process_one_for_upload", fake_process)

    manifest = tmp_path / "manifest.jsonl"
    monkeypatch.setattr(cli, "_uploads_manifest_path", lambda: manifest)

    pattern = str(tmp_path / "meetgeek-recording-*.webm")
    rc = cli.main(["upload", "--from-file", pattern])
    assert rc == 0
    assert sorted(posted) == [a.name, b.name]


def test_upload_from_file_skip_existing(cli, tmp_path, monkeypatch):
    src = tmp_path / "meetgeek-recording-2026-01-01T10-00-00-000Z.webm"
    src.write_bytes(b"x" * 1024)

    size = src.stat().st_size
    mtime = datetime.fromtimestamp(src.stat().st_mtime, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text(json.dumps({
        "source_webm": str(src.resolve()),
        "source_size_bytes": size, "source_mtime": mtime, "status": "submitted",
    }) + "\n", encoding="utf-8")

    monkeypatch.setattr(cli, "_uploads_manifest_path", lambda: manifest)
    called = {"n": 0}
    monkeypatch.setattr(cli, "_process_one_for_upload",
                        lambda *a, **kw: called.__setitem__("n", called["n"] + 1))

    rc = cli.main(["upload", "--from-file", str(src)])
    assert rc == 0
    assert called["n"] == 0


def test_upload_from_file_dry_run_no_calls(cli, tmp_path, monkeypatch):
    src = tmp_path / "meetgeek-recording-2026-01-01T10-00-00-000Z.webm"
    src.write_bytes(b"x" * 1024)
    monkeypatch.setattr(cli, "_uploads_manifest_path", lambda: tmp_path / "m.jsonl")
    called = {"n": 0}
    monkeypatch.setattr(cli, "_process_one_for_upload",
                        lambda *a, **kw: called.__setitem__("n", called["n"] + 1))
    rc = cli.main(["upload", "--from-file", str(src), "--dry-run"])
    assert rc == 0
    assert called["n"] == 0


def test_upload_from_file_continues_on_per_file_error(cli, tmp_path, monkeypatch):
    a = tmp_path / "meetgeek-recording-2026-01-01T10-00-00-000Z.webm"
    b = tmp_path / "meetgeek-recording-2026-01-02T10-00-00-000Z.webm"
    c = tmp_path / "meetgeek-recording-2026-01-03T10-00-00-000Z.webm"
    for f in (a, b, c): f.write_bytes(b"x" * 1024)

    def proc(src, **kw):
        if src.name == b.name:
            raise cli.ApiError("boom on B", exit_code=1)
        return {"source_webm": str(src), "status": "submitted"}
    monkeypatch.setattr(cli, "_process_one_for_upload", proc)
    monkeypatch.setattr(cli, "_uploads_manifest_path", lambda: tmp_path / "m.jsonl")

    rc = cli.main(["upload", "--from-file", str(tmp_path / "meetgeek-recording-*.webm")])
    assert rc == 1  # errors > 0


# ─── resume + directory + per-stage failure ──────────────────────────────────

def test_upload_resumes_from_converted_state(cli, tmp_path, monkeypatch):
    src = tmp_path / "meetgeek-recording-2026-01-01T10-00-00-000Z.webm"
    src.write_bytes(b"x" * 1024)
    size = src.stat().st_size
    mtime = datetime.fromtimestamp(src.stat().st_mtime, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    cached_mp4 = tmp_path / "cached.mp4"
    cached_mp4.write_bytes(b"M" * 2048)

    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text(json.dumps({
        "source_webm": str(src.resolve()),
        "source_size_bytes": size, "source_mtime": mtime,
        "mp4_path": str(cached_mp4), "mp4_size_bytes": 2048,
        "status": "converted",
    }) + "\n", encoding="utf-8")
    monkeypatch.setattr(cli, "_uploads_manifest_path", lambda: manifest)

    import sys as _sys
    _rec_mod = _sys.modules.get("recovery")
    assert _rec_mod is not None, "recovery module not found in sys.modules"

    convert_called = {"n": 0}
    def fake_convert_media(src_p, *, audio_only, mix_mode, output_path=None):
        convert_called["n"] += 1
        return output_path or (tmp_path / "out.mp4")
    monkeypatch.setattr(_rec_mod, "convert_media", fake_convert_media)

    monkeypatch.setattr(_rec_mod, "drive_upload_file",
                        lambda path, **kw: {"drive_id": "DID",
                                            "download_url": "https://x/d",
                                            "web_url": "https://x/w", "created": True})
    monkeypatch.setattr(_rec_mod, "submit_url_via_h2t_ops",
                        lambda url, title, lang: {"message": "ok"})

    rc = cli.main(["upload", "--from-file", str(src), "--language", "ru", "--no-skip-existing"])
    assert rc == 0
    assert convert_called["n"] == 0  # convert skipped via resume


def test_upload_resumes_from_in_drive_state(cli, tmp_path, monkeypatch):
    src = tmp_path / "meetgeek-recording-2026-01-01T10-00-00-000Z.webm"
    src.write_bytes(b"x" * 1024)
    size = src.stat().st_size
    mtime = datetime.fromtimestamp(src.stat().st_mtime, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    cached_mp4 = tmp_path / "cached.mp4"
    cached_mp4.write_bytes(b"M" * 2048)

    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text(json.dumps({
        "source_webm": str(src.resolve()),
        "source_size_bytes": size, "source_mtime": mtime,
        "mp4_path": str(cached_mp4), "mp4_size_bytes": 2048,
        "drive_id": "EXISTING_DID",
        "drive_download_url": "https://drive.google.com/uc?export=download&id=EXISTING_DID",
        "status": "in-drive",
    }) + "\n", encoding="utf-8")
    monkeypatch.setattr(cli, "_uploads_manifest_path", lambda: manifest)

    import sys as _sys
    _rec_mod = _sys.modules.get("recovery")
    assert _rec_mod is not None, "recovery module not found in sys.modules"

    convert_called = {"n": 0}
    drive_called = {"n": 0}
    monkeypatch.setattr(_rec_mod, "convert_media",
                        lambda src_p, *, audio_only, mix_mode, output_path=None:
                        convert_called.__setitem__("n", convert_called["n"] + 1) or output_path)
    monkeypatch.setattr(_rec_mod, "drive_upload_file",
                        lambda path, **kw: drive_called.__setitem__("n", drive_called["n"] + 1) or {})
    # The cached-drive path re-shares before submitting (#386): drive-audit
    # --revoke may have removed the ACL the original upload granted.
    monkeypatch.setattr(_rec_mod, "ensure_drive_public", lambda fid: None)

    posted = []
    monkeypatch.setattr(_rec_mod, "submit_url_via_h2t_ops",
                        lambda url, title, lang: posted.append({"url": url}) or {"message": "ok"})

    rc = cli.main(["upload", "--from-file", str(src), "--language", "ru", "--no-skip-existing"])
    assert rc == 0
    assert convert_called["n"] == 0
    assert drive_called["n"] == 0
    assert len(posted) == 1
    # URL is regenerated from drive_id, not reused from cached manifest line —
    # this lets old entries pick up newer URL patterns (e.g. virus-scan bypass).
    assert "id=EXISTING_DID" in posted[0]["url"]
    assert "drive.usercontent.google.com" in posted[0]["url"]


def test_upload_drive_failure_writes_drive_failed_status(cli, tmp_path, monkeypatch):
    src = tmp_path / "meetgeek-recording-2026-01-01T10-00-00-000Z.webm"
    src.write_bytes(b"x" * 1024)
    manifest = tmp_path / "manifest.jsonl"
    monkeypatch.setattr(cli, "_uploads_manifest_path", lambda: manifest)

    import sys as _sys
    _rec_mod = _sys.modules.get("recovery")
    assert _rec_mod is not None, "recovery module not found in sys.modules"

    def fake_convert_media(src_p, *, audio_only, mix_mode, output_path=None):
        from pathlib import Path as P
        out = output_path or (tmp_path / (P(str(src_p)).stem + ".mp4"))
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"M" * 2048)
        return out
    monkeypatch.setattr(_rec_mod, "convert_media", fake_convert_media)

    def boom(*a, **kw):
        raise _rec_mod.RecoveryError("drive boom", exit_code=1)
    monkeypatch.setattr(_rec_mod, "drive_upload_file", boom)

    rc = cli.main(["upload", "--from-file", str(src)])
    assert rc == 1
    lines = [json.loads(ln) for ln in manifest.read_text(encoding="utf-8").strip().splitlines()]
    statuses = [r["status"] for r in lines]
    assert "converted" in statuses
    assert "drive-failed" in statuses
    assert "upload-failed" not in statuses  # spec enum compliance — synthetic status forbidden
    assert "upload-rejected" not in statuses  # drive failure ≠ upload failure


def test_upload_from_file_directory_walks_recursively(cli, tmp_path, monkeypatch):
    nested = tmp_path / "nested"
    nested.mkdir()
    a = tmp_path / "meetgeek-recording-2026-01-01T10-00-00-000Z.webm"
    b = nested / "meetgeek-recording-2026-01-02T10-00-00-000Z.webm"
    for f in (a, b):
        f.write_bytes(b"x" * 1024)

    seen = []
    monkeypatch.setattr(cli, "_process_one_for_upload",
                        lambda src, **kw: seen.append(src.name) or {"status": "submitted"})
    monkeypatch.setattr(cli, "_uploads_manifest_path", lambda: tmp_path / "m.jsonl")

    rc = cli.main(["upload", "--from-file", str(tmp_path)])
    assert rc == 0
    assert sorted(seen) == [a.name, b.name]


# ─── Lake root isolation (#386, defect 6) ─────────────────────────────────────
#
# staging_dir(), uploads_manifest_path() and the emit_submission_artifact()
# default all derived from Path.home() with no override, so four upload tests
# wrote mp4 stubs and submission artifacts into the user's real ~/.dor lake —
# and Syncthing carried them to the other machine.

def _recovery(cli):
    import sys as _sys
    mod = _sys.modules.get("recovery")
    assert mod is not None, "recovery module not found in sys.modules"
    return mod


def test_staging_dir_honours_h2t_lake_root(cli, tmp_path, monkeypatch):
    rec = _recovery(cli)
    lake = tmp_path / "lake"
    monkeypatch.setenv("H2T_LAKE_ROOT", str(lake))
    assert lake in rec.staging_dir().parents


def test_uploads_manifest_path_honours_h2t_lake_root(cli, tmp_path, monkeypatch):
    rec = _recovery(cli)
    lake = tmp_path / "lake"
    monkeypatch.setenv("H2T_LAKE_ROOT", str(lake))
    assert lake in rec.uploads_manifest_path().parents


def test_emit_submission_artifact_defaults_into_lake_root(cli, tmp_path, monkeypatch):
    rec = _recovery(cli)
    lake = tmp_path / "lake"
    monkeypatch.setenv("H2T_LAKE_ROOT", str(lake))
    path = rec.emit_submission_artifact({"source_webm": "/x/meetgeek-recording-a.webm"})
    assert lake in path.parents


def test_lake_root_defaults_to_dor_lake_when_unset(cli, monkeypatch):
    """Without the env var the historical location is preserved."""
    rec = _recovery(cli)
    monkeypatch.delenv("H2T_LAKE_ROOT", raising=False)
    assert rec.lake_root() == Path.home() / ".dor" / "lake"


def test_suite_never_points_at_the_real_lake(cli):
    """The autouse conftest fixture must redirect every test away from ~/.dor.

    Without it, a test that forgets to override the path writes into production
    data — which is how pytest fixtures ended up in the synced lake.
    """
    rec = _recovery(cli)
    # Path.home() is itself redirected by the fixture, so the real location has
    # to be captured at import time, before any fixture runs.
    real_lake = _REAL_HOME / ".dor" / "lake"
    assert rec.lake_root() != real_lake
    assert real_lake not in rec.staging_dir().parents


# ─── Public-ACL audit (#386, defect 2) ────────────────────────────────────────
#
# _drive_make_public() grants `type: anyone` so MeetGeek can fetch the recording
# by URL, and nothing ever revokes it: 26/26 uploads stayed world-readable by
# link for 108 days. Revoking inside Stage 3 would race MeetGeek's own async
# fetch, so the recovery path is a separate audit over the manifest's drive_ids.

class FakeDriveService:
    """Minimal Drive stub: permissions().list/delete over a dict of file -> perms."""

    def __init__(self, perms: dict[str, list[dict]]):
        self._perms = perms
        self.deleted: list[tuple[str, str]] = []

    def permissions(self):
        return self

    def list(self, *, fileId, fields=None):
        return _Exec({"permissions": list(self._perms.get(fileId, []))})

    def delete(self, *, fileId, permissionId):
        self.deleted.append((fileId, permissionId))
        self._perms[fileId] = [
            p for p in self._perms.get(fileId, []) if p["id"] != permissionId
        ]
        return _Exec({})


class _Exec:
    def __init__(self, value):
        self._value = value

    def execute(self):
        return self._value


def _manifest_with(tmp_path, records):
    path = tmp_path / "manifest.jsonl"
    path.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n",
        encoding="utf-8",
    )
    return path


def test_drive_audit_reports_public_uploads_without_revoking(cli, tmp_path):
    rec = _recovery(cli)
    manifest = _manifest_with(tmp_path, [
        {"source_webm": "/x/a.webm", "drive_id": "D1", "status": "submitted"},
        {"source_webm": "/x/b.webm", "drive_id": "D2", "status": "submitted"},
    ])
    svc = FakeDriveService({
        "D1": [{"id": "P1", "type": "anyone", "role": "reader"}],
        "D2": [{"id": "P2", "type": "user", "role": "owner"}],
    })
    report = rec.drive_audit_public(svc=svc, manifest_path=manifest)
    assert report["checked"] == 2
    assert report["public"] == ["D1"]
    assert report["revoked"] == 0
    assert svc.deleted == []


def test_drive_audit_revokes_only_the_anyone_permission(cli, tmp_path):
    rec = _recovery(cli)
    manifest = _manifest_with(tmp_path, [
        {"source_webm": "/x/a.webm", "drive_id": "D1", "status": "submitted"},
    ])
    svc = FakeDriveService({
        "D1": [
            {"id": "P1", "type": "anyone", "role": "reader"},
            {"id": "P2", "type": "user", "role": "owner"},
        ],
    })
    report = rec.drive_audit_public(svc=svc, manifest_path=manifest, revoke=True)
    assert report["revoked"] == 1
    assert svc.deleted == [("D1", "P1")]
    assert [p["id"] for p in svc._perms["D1"]] == ["P2"], "owner must survive the revoke"


def test_drive_audit_skips_records_without_a_drive_id(cli, tmp_path):
    """convert-failed and drive-failed records carry no drive_id."""
    rec = _recovery(cli)
    manifest = _manifest_with(tmp_path, [
        {"source_webm": "/x/a.webm", "status": "convert-failed"},
        {"source_webm": "/x/b.webm", "drive_id": "D2", "status": "submitted"},
    ])
    svc = FakeDriveService({"D2": [{"id": "P2", "type": "anyone", "role": "reader"}]})
    report = rec.drive_audit_public(svc=svc, manifest_path=manifest)
    assert report["checked"] == 1
    assert report["public"] == ["D2"]


def test_drive_audit_command_reports_without_revoking_by_default(cli, capsys, monkeypatch):
    """Revoking is destructive to a live pipeline, so it must be opt-in."""
    rec = _recovery(cli)
    seen = {}

    def fake_audit(*, svc=None, manifest_path=None, revoke=False):
        seen["revoke"] = revoke
        return {"checked": 2, "public": ["D1"], "revoked": 0}

    monkeypatch.setattr(rec, "drive_audit_public", fake_audit)
    monkeypatch.setattr(cli, "_drive_audit_public", fake_audit, raising=False)
    rc = cli.main(["drive-audit"])
    assert rc == 0
    assert seen["revoke"] is False
    assert json.loads(capsys.readouterr().out)["public"] == ["D1"]


def test_drive_audit_command_revokes_when_asked(cli, capsys, monkeypatch):
    rec = _recovery(cli)
    seen = {}

    def fake_audit(*, svc=None, manifest_path=None, revoke=False):
        seen["revoke"] = revoke
        return {"checked": 2, "public": ["D1"], "revoked": 1}

    monkeypatch.setattr(rec, "drive_audit_public", fake_audit)
    monkeypatch.setattr(cli, "_drive_audit_public", fake_audit, raising=False)
    rc = cli.main(["drive-audit", "--revoke"])
    assert rc == 0
    assert seen["revoke"] is True
    assert json.loads(capsys.readouterr().out)["revoked"] == 1


def test_drive_audit_scans_superseded_manifest_lines(cli, tmp_path):
    """An ACL sweep must read every line, not the last-line-wins state.

    read_uploads_manifest() collapses the JSONL to one record per source_webm.
    A retry that appends a line without a drive_id therefore hides the earlier,
    still-public upload — and --revoke would leave it exposed (codex [P2]).
    """
    rec = _recovery(cli)
    manifest = _manifest_with(tmp_path, [
        {"source_webm": "/x/a.webm", "drive_id": "D1", "status": "upload-rejected"},
        {"source_webm": "/x/a.webm", "status": "drive-failed"},
    ])
    svc = FakeDriveService({"D1": [{"id": "P1", "type": "anyone", "role": "reader"}]})
    report = rec.drive_audit_public(svc=svc, manifest_path=manifest, revoke=True)
    assert report["public"] == ["D1"]
    assert svc.deleted == [("D1", "P1")]


def test_drive_audit_checks_each_drive_id_once(cli, tmp_path):
    """Repeated lines for the same upload must not be probed twice."""
    rec = _recovery(cli)
    manifest = _manifest_with(tmp_path, [
        {"source_webm": "/x/a.webm", "drive_id": "D1", "status": "submitted"},
        {"source_webm": "/x/a.webm", "drive_id": "D1", "status": "submitted"},
    ])
    svc = FakeDriveService({"D1": [{"id": "P1", "type": "anyone", "role": "reader"}]})
    report = rec.drive_audit_public(svc=svc, manifest_path=manifest)
    assert report["checked"] == 1
    assert report["public"] == ["D1"]


def test_drive_audit_survives_a_stale_drive_id(cli, tmp_path):
    """A deleted Drive file must not abort the sweep (codex [P2]).

    The audit walks every historical manifest entry, so an id whose file is gone
    is expected. If permissions().list raises and nothing catches it, the later,
    still-public uploads are never reached.
    """
    rec = _recovery(cli)
    manifest = _manifest_with(tmp_path, [
        {"source_webm": "/x/a.webm", "drive_id": "GONE", "status": "submitted"},
        {"source_webm": "/x/b.webm", "drive_id": "D2", "status": "submitted"},
    ])

    class ExplodingService(FakeDriveService):
        def list(self, *, fileId, fields=None):
            if fileId == "GONE":
                raise RuntimeError("File not found: GONE")
            return super().list(fileId=fileId, fields=fields)

    svc = ExplodingService({"D2": [{"id": "P2", "type": "anyone", "role": "reader"}]})
    report = rec.drive_audit_public(svc=svc, manifest_path=manifest, revoke=True)
    assert report["public"] == ["D2"]
    assert svc.deleted == [("D2", "P2")]
    assert [e["drive_id"] for e in report["errors"]] == ["GONE"]


def test_drive_audit_reports_no_errors_on_a_clean_sweep(cli, tmp_path):
    rec = _recovery(cli)
    manifest = _manifest_with(tmp_path, [
        {"source_webm": "/x/a.webm", "drive_id": "D1", "status": "submitted"},
    ])
    svc = FakeDriveService({"D1": [{"id": "P1", "type": "user", "role": "owner"}]})
    assert rec.drive_audit_public(svc=svc, manifest_path=manifest)["errors"] == []


def test_drive_audit_revokes_an_in_flight_upload_too(cli, tmp_path):
    """Nothing is exempt: the resume path re-shares whatever it reuses.

    Skipping in-drive ids would leave them public indefinitely. Making
    process_one() re-share the cached file instead lets the sweep clean
    everything (codex [P2], rounds 3 and 4).
    """
    rec = _recovery(cli)
    manifest = _manifest_with(tmp_path, [
        {"source_webm": "/x/a.webm", "drive_id": "D1",
         "drive_download_url": "https://d/D1", "status": "in-drive"},
    ])
    svc = FakeDriveService({"D1": [{"id": "P1", "type": "anyone", "role": "reader"}]})
    report = rec.drive_audit_public(svc=svc, manifest_path=manifest, revoke=True)
    assert report["revoked"] == 1
    assert svc.deleted == [("D1", "P1")]


def test_drive_audit_revokes_a_submitted_upload(cli, tmp_path):
    """`submitted` is the terminal state — that is what the sweep exists for."""
    rec = _recovery(cli)
    manifest = _manifest_with(tmp_path, [
        {"source_webm": "/x/a.webm", "drive_id": "D1", "status": "submitted"},
    ])
    svc = FakeDriveService({"D1": [{"id": "P1", "type": "anyone", "role": "reader"}]})
    assert rec.drive_audit_public(svc=svc, manifest_path=manifest, revoke=True)["revoked"] == 1


def test_drive_audit_revokes_a_superseded_id_a_retry_will_reshare(cli, tmp_path):
    """A `drive-failed` retry re-uploads, and drive_upload_file re-shares by name.

    So the earlier id is safe to revoke — only `in-drive` is genuinely in flight.
    """
    rec = _recovery(cli)
    manifest = _manifest_with(tmp_path, [
        {"source_webm": "/x/a.webm", "drive_id": "D1", "status": "upload-rejected"},
        {"source_webm": "/x/a.webm", "status": "drive-failed"},
    ])
    svc = FakeDriveService({"D1": [{"id": "P1", "type": "anyone", "role": "reader"}]})
    report = rec.drive_audit_public(svc=svc, manifest_path=manifest, revoke=True)
    assert report["revoked"] == 1


def test_resume_reshares_the_cached_drive_file_before_submitting(cli, tmp_path, monkeypatch):
    """Reusing a cached Drive id must re-grant the anyone permission (codex [P2]).

    can_skip_drive short-circuits Stage 2 for in-drive and submitted records and
    submits the stored URL. Once drive-audit --revoke exists, that URL may be
    private — so the resume path can no longer assume the original ACL survived.
    """
    src = tmp_path / "meetgeek-recording-2026-01-01T10-00-00-000Z.webm"
    src.write_bytes(b"x" * 1024)
    size = src.stat().st_size
    mtime = datetime.fromtimestamp(src.stat().st_mtime, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    cached_mp4 = tmp_path / "cached.mp4"
    cached_mp4.write_bytes(b"M" * 2048)

    manifest = _manifest_with(tmp_path, [{
        "source_webm": str(src.resolve()),
        "source_size_bytes": size, "source_mtime": mtime,
        "mp4_path": str(cached_mp4), "mp4_size_bytes": 2048,
        "drive_id": "EXISTING_DID",
        "drive_download_url": "https://drive.google.com/uc?export=download&id=EXISTING_DID",
        "status": "in-drive",
    }])
    monkeypatch.setattr(cli, "_uploads_manifest_path", lambda: manifest)

    rec = _recovery(cli)
    shared: list[str] = []
    monkeypatch.setattr(rec, "ensure_drive_public", lambda fid: shared.append(fid))
    monkeypatch.setattr(rec, "convert_media",
                        lambda src_p, *, audio_only, mix_mode, output_path=None: output_path)
    monkeypatch.setattr(rec, "drive_upload_file", lambda path, **kw: {})
    monkeypatch.setattr(rec, "submit_url_via_h2t_ops",
                        lambda url, title, lang: {"message": "ok"})

    rc = cli.main(["upload", "--from-file", str(src), "--language", "ru", "--no-skip-existing"])
    assert rc == 0
    assert shared == ["EXISTING_DID"]
