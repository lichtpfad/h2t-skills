"""Pure helpers for the research visual OCR rescue path."""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from datetime import UTC, datetime
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


def _parse_screenshot_path(stdout: str) -> str | None:
    """Extract the desktop image path from h2t-screenshot stdout."""
    for line in stdout.splitlines():
        stripped = line.strip()
        # Match "✓ desktop:" or mojibake equivalent on Windows (cp1252 decode of UTF-8)
        if "✓ desktop:" in stripped or "desktop:" in stripped and stripped.endswith(".png"):
            for marker in ("✓ desktop:", "desktop:"):
                if marker in stripped:
                    return stripped.split(marker, 1)[1].strip()
    return None


def capture_and_ocr(
    url: str,
    *,
    output_dir: Path,
    project: str,
) -> tuple[dict, int]:
    """Auto-capture a screenshot of url and run OCR. No sidecar required."""
    from h2t_ops.connectors.research.client import validate_public_http_url
    validate_public_http_url(url)  # SSRF guard: reject file://, localhost, private IPs, credentials

    if not shutil.which("h2t-screenshot"):
        raise ConfigError(
            "h2t-screenshot not found on PATH",
            hint="Install with: uv tool install --editable C:/dev/h2t-tools",
        )

    # Build stable artifact paths — screenshot persists here alongside other artifacts
    artifact_paths = build_visual_ocr_artifact_paths(
        output_dir=Path(output_dir),
        project=project,
        slug_source=url,
    )
    artifact_paths["sources_json"].parent.mkdir(parents=True, exist_ok=True)
    stable_image = artifact_paths["sources_json"].with_suffix(".capture.png")

    with tempfile.TemporaryDirectory() as tmp_dir:
        result = subprocess.run(
            ["h2t-screenshot", url, "--format", "desktop", "--out", tmp_dir],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )
        if result.returncode != 0:
            raise ProviderError(
                f"h2t-screenshot failed for {url}",
                details={"returncode": result.returncode, "stderr": result.stderr[:300]},
            )

        image_path_str = _parse_screenshot_path(result.stdout)
        if not image_path_str or not Path(image_path_str).is_file():
            raise ProviderError(
                "h2t-screenshot did not produce a desktop image file",
                details={"stdout": result.stdout[:300]},
            )

        # Copy to stable location before TemporaryDirectory is deleted
        shutil.copy2(image_path_str, stable_image)

    # Temp dir deleted — use stable_image for OCR and provenance
    extracted_text, visible_headings, confidence = extract_text_from_image(stable_image)
    captured_at = datetime.now(UTC).isoformat(timespec="seconds")

    envelope = build_visual_ocr_envelope(
        url=url,
        source_fetch_status="unknown",
        source_fetch_reason=None,
        captured_at=captured_at,
        image_path=str(stable_image),
        extracted_text=extracted_text,
        visible_headings=visible_headings,
        ocr_confidence=confidence,
    )
    envelope["provenance"]["capture_method"] = "auto_screenshot"
    envelope["provenance"]["capture_tool"] = "h2t-screenshot"

    sidecar = {
        "envelope": envelope,
        "meta": {
            "status": envelope["status"],
            "url": url,
            "captured_at": captured_at,
        },
    }
    artifact_paths["sources_json"].write_text(
        json.dumps(sidecar, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    exit_code = 0 if envelope["status"] in ("OK", "DEGRADED") else 1
    return envelope, exit_code
