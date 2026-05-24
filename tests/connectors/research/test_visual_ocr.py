from __future__ import annotations

import json
from pathlib import Path

import pytest

from h2t_ops.core.errors import UsageError
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
    artifact_paths = visual_ocr.build_visual_ocr_artifact_paths(
        output_dir=tmp_path,
        project="demo",
        slug_source="https://example.com/pops",
    )

    assert artifact_paths["sources_json"].parent == tmp_path
    assert artifact_paths["artifact_json"].parent == tmp_path
    assert artifact_paths["partial_md"].parent == tmp_path
    assert artifact_paths["raw_html"].parent == tmp_path
