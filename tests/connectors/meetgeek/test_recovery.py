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
        lines = [json.loads(line) for line in manifest.read_text().splitlines()]
        assert lines[0]["status"] == "converted"

    def test_append_multiple_preserves_order(self, rec, tmp_path):
        manifest = tmp_path / "manifest.jsonl"
        rec.append_uploads_manifest({"source_webm": "/x.webm", "status": "converted"}, manifest)
        rec.append_uploads_manifest({"source_webm": "/x.webm", "status": "submitted"}, manifest)
        lines = manifest.read_text().strip().splitlines()
        assert len(lines) == 2


class TestIsAlreadySubmitted:
    def test_true_when_submitted(self, rec):
        state = {"/a/b.webm": {"status": "submitted", "source_size_bytes": 100,
                                "source_mtime": "2026-05-20T10:00:00Z"}}
        assert rec.is_already_submitted(state, "/a/b.webm")

    def test_false_when_not_submitted(self, rec):
        state = {"/a/b.webm": {"status": "converted", "source_size_bytes": 100,
                                "source_mtime": "2026-05-20T10:00:00Z"}}
        assert not rec.is_already_submitted(state, "/a/b.webm")

    def test_false_when_key_absent(self, rec):
        assert not rec.is_already_submitted({}, "/a/b.webm")


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
        lines = [json.loads(line) for line in manifest.read_text().splitlines() if line.strip()]
        statuses = [rec["status"] for rec in lines]
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
        # The cached-drive path re-shares before submitting (#386): drive-audit
        # --revoke may have removed the ACL the original upload granted.
        monkeypatch.setattr(rec, "ensure_drive_public", lambda fid: None)
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

        lines = [json.loads(line) for line in manifest.read_text().splitlines() if line.strip()]
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

        lines = [json.loads(line) for line in manifest.read_text().splitlines() if line.strip()]
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
