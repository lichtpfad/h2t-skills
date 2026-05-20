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
