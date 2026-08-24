from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from h2t_ops.connectors.research import visual_ocr
from h2t_ops.core.errors import ProviderError, UsageError

FIXTURES = Path(__file__).parent / "fixtures" / "visual_ocr"


def _load_sidecar(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_load_fetch_sidecar_and_envelope_happy_path():
    sidecar = visual_ocr.load_fetch_sidecar(FIXTURES / "fetch_failed.sources.json")
    envelope = visual_ocr.load_fetch_envelope(sidecar)

    assert sidecar["meta"]["status"] == "FAILED"
    assert envelope["status"] == "FAILED"
    assert envelope["url"] == "https://example.com/pops"


def test_load_fetch_sidecar_missing_path_raises_usage_error(tmp_path):
    with pytest.raises(UsageError) as ei:
        visual_ocr.load_fetch_sidecar(tmp_path / "missing.sources.json")

    assert "not found" in str(ei.value)


def test_load_fetch_sidecar_malformed_json_raises_usage_error(tmp_path):
    bad = tmp_path / "bad.sources.json"
    bad.write_text("{not json", encoding="utf-8")

    with pytest.raises(UsageError) as ei:
        visual_ocr.load_fetch_sidecar(bad)

    assert "not valid JSON" in str(ei.value)


def test_validate_trigger_allows_failed():
    sidecar = _load_sidecar("fetch_failed.sources.json")
    envelope = visual_ocr.load_fetch_envelope(sidecar)

    visual_ocr.validate_visual_ocr_trigger(envelope)


def test_validate_trigger_blocks_gated():
    sidecar = _load_sidecar("fetch_gated.sources.json")
    envelope = visual_ocr.load_fetch_envelope(sidecar)

    with pytest.raises(UsageError) as ei:
        visual_ocr.validate_visual_ocr_trigger(envelope)

    assert "login_required" in str(ei.value)


def test_validate_trigger_blocks_paid_gate():
    envelope = {
        "status": "FAILED",
        "content_gate": "paid",
        "telemetry": {
            "reason_for_failed": "all_providers_failed",
        },
    }

    with pytest.raises(UsageError) as ei:
        visual_ocr.validate_visual_ocr_trigger(envelope)

    assert "paid" in str(ei.value)


def test_validate_trigger_allows_allowed_degraded_reason():
    sidecar = _load_sidecar("fetch_degraded_short_body.sources.json")
    envelope = visual_ocr.load_fetch_envelope(sidecar)

    visual_ocr.validate_visual_ocr_trigger(envelope)


def test_validate_trigger_blocks_unsupported_degraded_reason():
    envelope = {
        "status": "DEGRADED",
        "content_gate": "none",
        "telemetry": {
            "reason_for_degraded": "all_providers_degraded_opaque_binary",
        },
    }

    with pytest.raises(UsageError) as ei:
        visual_ocr.validate_visual_ocr_trigger(envelope)

    assert "allowed only after FAILED" in str(ei.value)


def test_build_visual_ocr_envelope_marks_output_non_canonical():
    envelope = visual_ocr.build_visual_ocr_envelope(
        url="https://example.com/pops",
        source_fetch_status="FAILED",
        source_fetch_reason="redirect_collapsed_to_homepage",
        captured_at="2026-05-25T12:34:56+00:00",
        image_path="capture.png",
        extracted_text="POPs in TouchDesigner",
        visible_headings=["POPs in TouchDesigner"],
        ocr_confidence="medium",
    )

    assert envelope["provider_used"] == "visual_ocr"
    assert envelope["text_source"] == "visual_ocr"
    assert envelope["canonical"] is False
    assert envelope["body_text_visual_ocr"] == "POPs in TouchDesigner"
    assert envelope["quote_safe"] is False
    assert envelope["needs_review"] is True
    assert envelope["review_status"] == "unreviewed"
    assert "visual_only" in envelope["limitations"]
    assert envelope["provenance"]["captured_at"] == "2026-05-25T12:34:56+00:00"


def test_build_visual_ocr_envelope_rejects_missing_captured_at():
    with pytest.raises(UsageError) as ei:
        visual_ocr.build_visual_ocr_envelope(
            url="https://example.com/pops",
            source_fetch_status="FAILED",
            source_fetch_reason="redirect_collapsed_to_homepage",
            captured_at=None,
            image_path="capture.png",
            extracted_text="POPs in TouchDesigner",
            visible_headings=["POPs in TouchDesigner"],
            ocr_confidence="medium",
        )

    assert "captured_at" in str(ei.value)


def test_build_visual_ocr_artifact_paths_returns_paths_under_output_dir(tmp_path):
    output_dir = tmp_path / "artifacts"
    artifact_paths = visual_ocr.build_visual_ocr_artifact_paths(
        output_dir=output_dir,
        project="demo",
        slug_source="https://example.com/pops",
    )

    assert output_dir.exists() is False
    assert artifact_paths["sources_json"].parent == output_dir
    assert artifact_paths["artifact_json"].parent == output_dir
    assert artifact_paths["partial_md"].parent == output_dir
    assert artifact_paths["raw_html"].parent == output_dir


def test_extract_text_from_image_missing_path_raises_usage_error(tmp_path):
    with pytest.raises(UsageError) as ei:
        visual_ocr.extract_text_from_image(tmp_path / "missing.png")

    assert "image not found" in str(ei.value)


def test_extract_text_from_image_parses_monkeypatched_result(tmp_path, monkeypatch):
    image = tmp_path / "capture.png"
    image.write_bytes(b"fake-image")

    class FakeRapidOCR:
        def __call__(self, image_path: str):
            assert image_path == str(image)
            return (
                [
                    ((0, 0, 10, 10), "POPs in TouchDesigner", 0.99),
                    ((0, 20, 10, 30), "Attribute lifecycle", 0.95),
                ],
                None,
            )

    monkeypatch.setitem(
        sys.modules,
        "rapidocr_onnxruntime",
        SimpleNamespace(RapidOCR=FakeRapidOCR),
    )

    text, headings, confidence = visual_ocr.extract_text_from_image(image)

    assert "POPs in TouchDesigner" in text
    assert headings == ["POPs in TouchDesigner", "Attribute lifecycle"]
    assert confidence == "medium"


def test_extract_text_from_image_empty_result_returns_low(tmp_path, monkeypatch):
    image = tmp_path / "capture.png"
    image.write_bytes(b"fake-image")

    class FakeRapidOCR:
        def __call__(self, image_path: str):
            return ([], None)

    monkeypatch.setitem(
        sys.modules,
        "rapidocr_onnxruntime",
        SimpleNamespace(RapidOCR=FakeRapidOCR),
    )

    text, headings, confidence = visual_ocr.extract_text_from_image(image)

    assert text == ""
    assert headings == []
    assert confidence == "low"


def test_extract_text_from_image_engine_failure_raises_provider_error(tmp_path, monkeypatch):
    image = tmp_path / "capture.png"
    image.write_bytes(b"fake-image")

    class FakeRapidOCR:
        def __call__(self, image_path: str):
            raise RuntimeError("boom")

    monkeypatch.setitem(
        sys.modules,
        "rapidocr_onnxruntime",
        SimpleNamespace(RapidOCR=FakeRapidOCR),
    )

    with pytest.raises(ProviderError) as ei:
        visual_ocr.extract_text_from_image(image)

    assert "failed while processing the image" in str(ei.value)


def test_capture_and_ocr_ok(monkeypatch, tmp_path):
    """capture_and_ocr calls h2t-screenshot, copies screenshot to stable path, runs OCR."""
    import shutil as _shutil
    import subprocess
    from unittest.mock import patch as _patch

    monkeypatch.setattr(_shutil, "which", lambda cmd: "/usr/bin/h2t-screenshot")

    fake_image = tmp_path / "tmp_screenshot" / "test.png"
    fake_image.parent.mkdir()
    fake_image.write_bytes(
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
        b"\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
    )

    fake_stdout = f"→ https://example.com\n  ✓ desktop: {fake_image}\n"

    fake_run_result = MagicMock()
    fake_run_result.returncode = 0
    fake_run_result.stdout = fake_stdout
    fake_run_result.stderr = ""

    output_dir = tmp_path / "artifacts"
    with _patch("subprocess.run", return_value=fake_run_result):
        with _patch.object(
            visual_ocr,
            "extract_text_from_image",
            return_value=("Recovered text from page", ["Heading One"], "medium"),
        ):
            envelope, exit_code = visual_ocr.capture_and_ocr(
                "https://example.com",
                output_dir=output_dir,
                project="test",
            )

    assert exit_code == 0
    assert envelope["status"] == "OK"
    assert envelope["provider_used"] == "visual_ocr"
    assert "Recovered text" in envelope["body_text_visual_ocr"]
    assert envelope["needs_review"] is True
    assert envelope["quote_safe"] is False
    # Stable image must exist in output_dir (not in a deleted temp dir)
    stable_image = Path(envelope["provenance"]["image_path"])
    assert stable_image.is_file(), "screenshot must be copied to output_dir, not left in tmp"
    assert str(output_dir) in str(stable_image)
    # Sidecar JSON must be written by capture_and_ocr itself
    import glob as _glob
    sidecar_files = list(output_dir.rglob("*.sources.json"))
    assert sidecar_files, "capture_and_ocr must write sources.json sidecar"
    sidecar_data = json.loads(sidecar_files[0].read_text(encoding="utf-8"))
    assert sidecar_data["meta"]["url"] == "https://example.com"
    assert sidecar_data["envelope"]["status"] == "OK"


def test_capture_and_ocr_rejects_file_url(tmp_path):
    """UsageError for file:// URLs — SSRF guard."""
    from h2t_ops.core.errors import UsageError
    with pytest.raises(UsageError):
        visual_ocr.capture_and_ocr(
            "file:///etc/passwd", output_dir=tmp_path, project="test"
        )


def test_capture_and_ocr_rejects_localhost(tmp_path):
    """UsageError for localhost URLs — SSRF guard."""
    from h2t_ops.core.errors import UsageError
    with pytest.raises(UsageError):
        visual_ocr.capture_and_ocr(
            "http://localhost:8080/admin", output_dir=tmp_path, project="test"
        )


def test_capture_and_ocr_rejects_private_ip(tmp_path):
    """UsageError for private IP ranges — SSRF guard."""
    from h2t_ops.core.errors import UsageError
    with pytest.raises(UsageError):
        visual_ocr.capture_and_ocr(
            "http://192.168.1.1/", output_dir=tmp_path, project="test"
        )


def test_capture_and_ocr_screenshot_not_on_path(monkeypatch, tmp_path):
    """ConfigError when h2t-screenshot is not installed."""
    import shutil as _shutil
    monkeypatch.setattr(_shutil, "which", lambda cmd: None)

    from h2t_ops.core.errors import ConfigError
    with pytest.raises(ConfigError) as ei:
        visual_ocr.capture_and_ocr(
            "https://example.com", output_dir=tmp_path, project="test"
        )

    assert "h2t-screenshot" in str(ei.value)


def test_capture_and_ocr_screenshot_fails(monkeypatch, tmp_path):
    """ProviderError when h2t-screenshot returns non-zero."""
    import shutil as _shutil
    import subprocess
    from unittest.mock import patch as _patch

    monkeypatch.setattr(_shutil, "which", lambda cmd: "/usr/bin/h2t-screenshot")

    fake_result = MagicMock()
    fake_result.returncode = 1
    fake_result.stdout = ""
    fake_result.stderr = "browser launch failed"

    with _patch("subprocess.run", return_value=fake_result):
        from h2t_ops.core.errors import ProviderError
        with pytest.raises(ProviderError):
            visual_ocr.capture_and_ocr(
                "https://example.com", output_dir=tmp_path, project="test"
            )
