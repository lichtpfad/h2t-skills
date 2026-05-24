"""Pure helpers for the research visual OCR rescue path."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from h2t_ops.core.errors import ConfigError, UsageError

ALLOWED_DEGRADED_REASONS = {
    "redirect_collapsed_to_homepage",
    "all_providers_degraded_js_shell",
    "all_providers_degraded_short_body",
}


def load_fetch_sidecar(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).expanduser().read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or "envelope" not in payload:
        raise UsageError("visual-ocr requires a fetch .sources.json sidecar")
    return payload


def load_fetch_envelope(sidecar: dict[str, Any]) -> dict[str, Any]:
    envelope = sidecar.get("envelope")
    if not isinstance(envelope, dict):
        raise UsageError("fetch sidecar is missing envelope")
    return envelope


def validate_visual_ocr_trigger(envelope: dict[str, Any]) -> None:
    status = envelope.get("status")
    gate = envelope.get("content_gate", "none")
    telemetry = envelope.get("telemetry") or {}
    reason_failed = telemetry.get("reason_for_failed")
    reason_degraded = telemetry.get("reason_for_degraded")

    if gate in {"login_required", "paid"}:
        raise UsageError(f"visual-ocr blocked for gated content: {gate}")
    if status == "FAILED":
        return
    if status == "DEGRADED" and reason_degraded in ALLOWED_DEGRADED_REASONS:
        return
    raise UsageError(
        "visual-ocr allowed only after FAILED or specific degraded reasons; "
        f"got status={status!r} reason_failed={reason_failed!r} reason_degraded={reason_degraded!r}"
    )


def extract_text_from_image(image_path: str | Path) -> tuple[str, list[str], str]:
    try:
        from rapidocr_onnxruntime import RapidOCR
    except Exception as exc:  # pragma: no cover
        raise ConfigError(
            "rapidocr-onnxruntime is required for research visual-ocr",
            hint="Install project dependencies with uv sync / uv run.",
        ) from exc

    engine = RapidOCR()
    result = engine(str(Path(image_path).expanduser()))
    if isinstance(result, tuple) and len(result) == 2:
        ocr_result = result[0]
    else:
        ocr_result = result

    if not ocr_result:
        return "", [], "low"

    lines: list[str] = []
    for item in ocr_result:
        if isinstance(item, (list, tuple)) and len(item) > 1 and item[1]:
            lines.append(str(item[1]).strip())

    text = "\n".join(line for line in lines if line).strip()
    headings = [line for line in lines[:5] if line.strip()]
    # Heuristic confidence only; this is not engine-derived quality scoring.
    confidence = "medium" if text else "low"
    return text, headings, confidence


def build_visual_ocr_envelope(
    *,
    url: str,
    source_fetch_status: str,
    source_fetch_reason: str | None,
    image_path: str,
    extracted_text: str,
    visible_headings: list[str],
    ocr_confidence: str,
) -> dict[str, Any]:
    status = "OK" if extracted_text.strip() else "FAILED"
    return {
        "status": status,
        "provider_used": "visual_ocr",
        "text_source": "visual_ocr",
        "canonical": False,
        "url": url,
        "body_text_visual_ocr": extracted_text,
        "visible_headings": visible_headings,
        "ocr_confidence": ocr_confidence,
        "quote_safe": False,
        "needs_review": True,
        "review_status": "unreviewed",
        "limitations": ["visual_only", "not_quote_safe", "links_not_reliable"],
        "provenance": {
            "capture_method": "external_image",
            "capture_tool": "user_supplied_image",
            "image_path": str(image_path),
            "captured_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "source_fetch_status": source_fetch_status,
            "source_fetch_reason": source_fetch_reason,
        },
    }


def build_visual_ocr_artifact_paths(
    *,
    output_dir: Path,
    project: str,
    slug_source: str,
) -> dict[str, Path]:
    from h2t_ops.connectors.research.client import artifact_paths

    return artifact_paths(
        output_dir=output_dir,
        project=project,
        slug_source=slug_source,
        kind="visual-ocr",
    )
