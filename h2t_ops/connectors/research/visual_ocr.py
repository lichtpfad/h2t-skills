"""Pure helpers for the research visual OCR rescue path."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from h2t_ops.core.errors import ConfigError, ProviderError, UsageError

ALLOWED_DEGRADED_REASONS = {
    "redirect_collapsed_to_homepage",
    "all_providers_degraded_js_shell",
    "all_providers_degraded_short_body",
}


def load_fetch_sidecar(path: str | Path) -> dict[str, Any]:
    sidecar_path = Path(path).expanduser()
    try:
        raw = sidecar_path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise UsageError(
            f"visual-ocr fetch sidecar not found: {sidecar_path}",
            hint="Pass an existing .sources.json file produced by research fetch.",
        ) from exc
    except OSError as exc:
        raise UsageError(
            f"visual-ocr could not read fetch sidecar: {sidecar_path}",
            hint="Check file permissions and path correctness.",
        ) from exc

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise UsageError(
            f"visual-ocr fetch sidecar is not valid JSON: {sidecar_path}",
            hint="Use a valid research fetch .sources.json file.",
        ) from exc
    if not isinstance(payload, dict) or "envelope" not in payload:
        raise UsageError(
            "visual-ocr requires a fetch .sources.json sidecar",
            hint="Pass the full .sources.json output from research fetch.",
        )
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
    image = Path(image_path).expanduser()
    if not image.is_file():
        raise UsageError(
            f"visual-ocr image not found: {image}",
            hint="Pass an existing screenshot image path via --image-path.",
        )

    try:
        from rapidocr_onnxruntime import RapidOCR
    except ModuleNotFoundError as exc:  # pragma: no cover
        raise ConfigError(
            "research visual-ocr environment is incomplete: rapidocr-onnxruntime is missing",
            hint="Repair the project environment so the declared runtime dependency is installed.",
        ) from exc
    except Exception as exc:  # pragma: no cover
        raise ConfigError(
            "research visual-ocr environment is broken: rapidocr-onnxruntime could not be imported",
            hint="Verify the project environment and installed runtime dependencies.",
        ) from exc

    try:
        engine = RapidOCR()
    except Exception as exc:
        raise ProviderError(
            "visual-ocr could not initialize the OCR engine",
            details={"image_path": str(image)},
        ) from exc

    try:
        result = engine(str(image))
    except Exception as exc:
        raise ProviderError(
            "visual-ocr failed while processing the image",
            details={"image_path": str(image)},
        ) from exc

    if isinstance(result, tuple) and len(result) == 2:
        ocr_result = result[0]
    else:
        ocr_result = result

    if not ocr_result:
        return "", [], "low"

    if not isinstance(ocr_result, (list, tuple)):
        raise UsageError(
            "visual-ocr returned an unexpected OCR result shape",
            hint="Confirm the OCR engine returns line items with text payloads.",
        )

    lines: list[str] = []
    for item in ocr_result:
        if not isinstance(item, (list, tuple)) or len(item) <= 1:
            continue
        text = str(item[1]).strip()
        if text:
            lines.append(text)

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
    captured_at: str,
    image_path: str,
    extracted_text: str,
    visible_headings: list[str],
    ocr_confidence: str,
) -> dict[str, Any]:
    status = "OK" if extracted_text.strip() else "FAILED"
    if not str(captured_at or "").strip():
        raise UsageError(
            "visual-ocr requires an explicit captured_at timestamp",
            hint="Pass the capture time from the caller so envelope creation stays deterministic.",
        )
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
            "captured_at": captured_at,
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
    def _slugify(text: str) -> str:
        slug = []
        prev_dash = False
        for char in text.lower():
            if char.isalnum():
                slug.append(char)
                prev_dash = False
            elif not prev_dash:
                slug.append("-")
                prev_dash = True
        value = "".join(slug).strip("-")
        return value or "research"

    base = f"{_slugify(project)}-{_slugify(slug_source)}-{_slugify('visual-ocr')}"
    output_dir = Path(output_dir).expanduser()
    return {
        "partial_md": output_dir / f"{base}.partial.md",
        "sources_json": output_dir / f"{base}.sources.json",
        "artifact_json": output_dir / f"{base}.artifact.json",
        "raw_html": output_dir / f"{base}.raw.html",
    }
