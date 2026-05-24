from __future__ import annotations

import json
import sys
from types import SimpleNamespace
from pathlib import Path

import pytest

from h2t_ops.core.errors import ProviderError, UsageError
from h2t_ops.connectors.research import visual_ocr


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


def test_validate_trigger_allows_allowed_degraded_reason():
    sidecar = _load_sidecar("fetch_degraded_short_body.sources.json")
    envelope = visual_ocr.load_fetch_envelope(sidecar)

    visual_ocr.validate_visual_ocr_trigger(envelope)


def test_build_visual_ocr_envelope_marks_output_non_canonical():
    envelope = visual_ocr.build_visual_ocr_envelope(
        url="https://example.com/pops",
        source_fetch_status="FAILED",
        source_fetch_reason="redirect_collapsed_to_homepage",
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
