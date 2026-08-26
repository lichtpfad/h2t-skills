---
title: "h2t-ops Visual OCR Fallback Implementation Plan"
status: "draft"
date: "2026-05-25"
milestone: ""
---
# h2t-ops Visual OCR Fallback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a small, honest `h2t-ops research visual-ocr` rescue path that turns one existing fetch sidecar plus one page image captured via the already existing screenshot tooling into a review-required OCR artifact.

**Architecture:** Keep OCR outside the fetch ladder. `h2t_ops.connectors.research.fetch` remains unchanged as the structured provider ladder; a new `visual_ocr` helper module consumes a saved fetch envelope and one local image, enforces the narrow trigger gate, and runs one OCR engine. Artifact writing stays in `ResearchClient` so the OCR helper remains pure and there is no import cycle with `client.py`. Capture is explicitly out of scope for repo code: v1 accepts any user-supplied image path, while the existing `h2t-tools:screenshot` skill is only the preferred operator workflow for producing that image.

**Tech Stack:** Python 3.11+, `rapidocr-onnxruntime` for local OCR, existing `h2t_ops.connectors.research` client/commands/artifact helpers, existing `h2t-tools:screenshot` skill for capture, `pytest`.

---

## File Structure

### Create

- `h2t_ops/connectors/research/visual_ocr.py`
  - Visual OCR helper substrate.
  - Loads the existing fetch sidecar.
  - Enforces trigger rules.
  - Runs one OCR engine on one image.
  - Builds the non-canonical OCR envelope.
  - Does not import `client.py` and does not write artifacts directly.

- `tests/connectors/research/test_visual_ocr.py`
  - Unit tests for trigger gating, sidecar loading, OCR envelope shape, and artifact honesty.

- `tests/connectors/research/fixtures/visual_ocr/fetch_failed.sources.json`
  - Minimal `FAILED` fetch sidecar fixture that should allow OCR rescue.

- `tests/connectors/research/fixtures/visual_ocr/fetch_gated.sources.json`
  - Minimal gated fetch sidecar fixture that must block OCR rescue.

- `tests/connectors/research/fixtures/visual_ocr/fetch_degraded_short_body.sources.json`
  - Minimal `DEGRADED` fetch sidecar fixture with an allowed degraded reason.

### Modify

- `pyproject.toml`
  - Add the single OCR runtime dependency.

- `h2t_ops/connectors/research/commands.py`
  - Register `research visual-ocr`.
  - Parse `--fetch-sidecar`, `--image-path`, `--project`, `--output-dir`.

- `h2t_ops/connectors/research/client.py`
  - Add `ResearchClient.visual_ocr(...)`.
  - Add a dedicated OCR artifact writer using low-level artifact path/JSON helpers, but not the generic `results`-based provider writer.
  - Emit the OCR artifact and telemetry.

- `tests/connectors/research/test_commands.py`
  - Cover parser registration and dispatch for the new subcommand.

- `tests/connectors/research/test_client.py`
  - Cover `ResearchClient.visual_ocr(...)` happy path and gate failures.

- `plugins/h2t-ops/skills/research/SKILL.md`
  - Document the new rescue command and the screenshot-skill/operator capture example.

## Task 1: Add the command surface and red tests

**Files:**
- Modify: `h2t_ops/connectors/research/commands.py`
- Modify: `tests/connectors/research/test_commands.py`
- Test: `tests/connectors/research/test_commands.py`

- [ ] **Step 1: Write the failing parser and dispatch tests**

Add these tests to `tests/connectors/research/test_commands.py`:

```python
def test_parser_registration_for_research_visual_ocr():
    parser = cli.build_parser()

    parsed = parser.parse_args(
        [
            "research",
            "visual-ocr",
            "--fetch-sidecar",
            "artifact.sources.json",
            "--image-path",
            "capture.png",
            "--json",
        ]
    )

    assert parsed.connector == "research"
    assert parsed.research_cmd == "visual-ocr"
    assert parsed.fetch_sidecar == "artifact.sources.json"
    assert parsed.image_path == "capture.png"
    assert parsed.as_json is True
    assert parsed._handler is commands.run


def test_run_dispatches_visual_ocr(monkeypatch):
    _patch_fake_client(monkeypatch)
    args = argparse.Namespace(
        research_cmd="visual-ocr",
        output_dir=None,
        fetch_sidecar="artifact.sources.json",
        image_path="capture.png",
        project="demo",
    )

    result = commands.run(args)

    assert result["method"] == "visual_ocr"
    assert result["kwargs"] == {
        "fetch_sidecar": "artifact.sources.json",
        "image_path": "capture.png",
        "project": "demo",
    }
```

Extend `FakeResearchClient` in the same file:

```python
    def visual_ocr(self, **kwargs) -> dict:
        self.calls.append(("visual_ocr", kwargs))
        return {"method": "visual_ocr", "kwargs": kwargs}
```

- [ ] **Step 2: Run the focused command tests and confirm they fail**

Run:

```bash
uv.exe run pytest tests/connectors/research/test_commands.py -k "visual_ocr" -v
```

Expected: FAIL with `invalid choice: 'visual-ocr'` or missing `visual_ocr` dispatch branch.

- [ ] **Step 3: Add the `visual-ocr` argparse surface**

Edit `h2t_ops/connectors/research/commands.py` by adding this parser block after `fetch`:

```python
    visual_ocr = cmds.add_parser(
        "visual-ocr",
        help="Create a review-required OCR rescue artifact from one fetch sidecar and one page image",
    )
    visual_ocr.add_argument("--fetch-sidecar", required=True, dest="fetch_sidecar")
    visual_ocr.add_argument("--image-path", required=True, dest="image_path")
    visual_ocr.add_argument("--project", default="default")
    visual_ocr.add_argument("--output-dir", dest="output_dir")
    add_fmt(visual_ocr)
```

Add this dispatch branch inside `run(args)`:

```python
    if cmd == "visual-ocr":
        return client.visual_ocr(
            fetch_sidecar=args.fetch_sidecar,
            image_path=args.image_path,
            project=args.project,
        )
```

- [ ] **Step 4: Run the focused command tests and confirm they pass**

Run:

```bash
uv.exe run pytest tests/connectors/research/test_commands.py -k "visual_ocr" -v
```

Expected: PASS for both new tests.

- [ ] **Step 5: Commit the command-surface slice**

```bash
git add h2t_ops/connectors/research/commands.py tests/connectors/research/test_commands.py
git commit -m "feat(research): add visual ocr command surface"
```

## Task 2: Build the visual OCR helper module with hard gates

**Files:**
- Create: `h2t_ops/connectors/research/visual_ocr.py`
- Create: `tests/connectors/research/test_visual_ocr.py`
- Create: `tests/connectors/research/fixtures/visual_ocr/fetch_failed.sources.json`
- Create: `tests/connectors/research/fixtures/visual_ocr/fetch_gated.sources.json`
- Create: `tests/connectors/research/fixtures/visual_ocr/fetch_degraded_short_body.sources.json`
- Modify: `pyproject.toml`

- [ ] **Step 1: Add failing unit tests for pure helper behavior and trigger gates**

Create `tests/connectors/research/test_visual_ocr.py`:

```python
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from h2t_ops.core.errors import UsageError
from h2t_ops.connectors.research import visual_ocr


FIXTURES = Path(__file__).parent / "fixtures" / "visual_ocr"


def _load_sidecar(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_validate_trigger_allows_failed_sidecar():
    sidecar = _load_sidecar("fetch_failed.sources.json")
    envelope = visual_ocr.load_fetch_envelope(sidecar)

    visual_ocr.validate_visual_ocr_trigger(envelope)


def test_validate_trigger_blocks_gated_sidecar():
    sidecar = _load_sidecar("fetch_gated.sources.json")
    envelope = visual_ocr.load_fetch_envelope(sidecar)

    with pytest.raises(UsageError) as ei:
        visual_ocr.validate_visual_ocr_trigger(envelope)

    assert "login_required" in str(ei.value)


def test_validate_trigger_allows_degraded_short_body():
    sidecar = _load_sidecar("fetch_degraded_short_body.sources.json")
    envelope = visual_ocr.load_fetch_envelope(sidecar)

    visual_ocr.validate_visual_ocr_trigger(envelope)


def test_validate_trigger_blocks_unsupported_degraded_reason():
    envelope = {
        "status": "DEGRADED",
        "content_gate": "none",
        "telemetry": {"reason_for_degraded": "degraded_but_still_readable"},
    }

    with pytest.raises(UsageError):
        visual_ocr.validate_visual_ocr_trigger(envelope)


def test_build_visual_ocr_envelope_marks_result_noncanonical():
    envelope = visual_ocr.build_visual_ocr_envelope(
        url="https://example.com/pops",
        source_fetch_status="FAILED",
        source_fetch_reason="redirect_collapsed_to_homepage",
        captured_at="2026-05-25T00:00:00+00:00",
        image_path="capture.png",
        extracted_text="POPs in TouchDesigner",
        visible_headings=["POPs in TouchDesigner"],
        ocr_confidence="medium",
    )

    assert envelope["provider_used"] == "visual_ocr"
    assert envelope["text_source"] == "visual_ocr"
    assert envelope["body_text_visual_ocr"] == "POPs in TouchDesigner"
    assert envelope["quote_safe"] is False
    assert envelope["needs_review"] is True
    assert envelope["review_status"] == "unreviewed"
    assert "visual_only" in envelope["limitations"]


def test_build_visual_ocr_artifact_paths_returns_pure_paths(tmp_path):
    artifact_paths = visual_ocr.build_visual_ocr_artifact_paths(
        output_dir=tmp_path,
        project="demo",
        slug_source="https://example.com/pops",
    )
    assert tmp_path.exists() is False
    assert artifact_paths["sources_json"].parent == tmp_path
    assert artifact_paths["artifact_json"].parent == tmp_path
    assert artifact_paths["partial_md"].parent == tmp_path
```

Create `tests/connectors/research/fixtures/visual_ocr/fetch_failed.sources.json`:

```json
{
  "meta": {
    "tool": "fetch_url.py",
    "status": "FAILED"
  },
  "envelope": {
    "status": "FAILED",
    "url": "https://example.com/pops",
    "content_gate": "none",
    "telemetry": {
      "reason_for_failed": "redirect_collapsed_to_homepage"
    }
  }
}
```

Create `tests/connectors/research/fixtures/visual_ocr/fetch_gated.sources.json`:

```json
{
  "meta": {
    "tool": "fetch_url.py",
    "status": "FAILED"
  },
  "envelope": {
    "status": "FAILED",
    "url": "https://example.com/pops",
    "content_gate": "login_required",
    "telemetry": {
      "reason_for_failed": "all_providers_failed"
    }
  }
}
```

Create `tests/connectors/research/fixtures/visual_ocr/fetch_degraded_short_body.sources.json`:

```json
{
  "meta": {
    "tool": "fetch_url.py",
    "status": "DEGRADED"
  },
  "envelope": {
    "status": "DEGRADED",
    "url": "https://example.com/pops",
    "content_gate": "none",
    "telemetry": {
      "reason_for_degraded": "all_providers_degraded_short_body"
    }
  }
}
```

- [ ] **Step 2: Run the new OCR unit tests and confirm they fail**

Run:

```bash
uv.exe run pytest tests/connectors/research/test_visual_ocr.py -v
```

Expected: FAIL with `cannot import name 'visual_ocr'` or missing helper functions.

- [ ] **Step 3: Add the single OCR dependency**

Update `pyproject.toml` dependencies:

```toml
dependencies = [
  "notion-client>=2.0",
  "httpx>=0.27",
  "python-dotenv>=1.0",
  "google-api-python-client>=2.0",
  "google-auth>=2.0",
  "google-auth-oauthlib>=1.0",
  "tzdata>=2024.1",
  "telethon>=1.36,<1.43",
  "rapidocr-onnxruntime>=1.3.24",
]
```

- [ ] **Step 4: Implement the helper module with the narrow contract**

Create `h2t_ops/connectors/research/visual_ocr.py`:

```python
from __future__ import annotations

import json
from datetime import datetime, timezone
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
        f"visual-ocr allowed only after FAILED or specific degraded reasons; got status={status!r} "
        f"reason_failed={reason_failed!r} reason_degraded={reason_degraded!r}"
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
            "rapidocr-onnxruntime is required for research visual-ocr",
            hint="Install project dependencies with uv sync / uv run.",
        ) from exc
    except Exception as exc:  # pragma: no cover
        raise ConfigError(
            "rapidocr-onnxruntime could not be imported for research visual-ocr",
            hint="Verify the project environment and installed dependencies.",
        ) from exc

    try:
        engine = RapidOCR()
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

    lines = []
    for item in ocr_result:
        if not isinstance(item, (list, tuple)) or len(item) <= 1:
            continue
        text = str(item[1]).strip()
        if text:
            lines.append(text)
    text = "\n".join(lines).strip()
    headings = [line for line in lines[:5] if line.strip()]
    # V1 confidence is heuristic only, not engine-derived quality scoring.
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
    return {
        "status": status,
        "provider_used": "visual_ocr",
        "text_source": "visual_ocr",
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

    output_dir = Path(output_dir).expanduser()
    base = f"{_slugify(project)}-{_slugify(slug_source)}-visual-ocr"
    return {
        "partial_md": output_dir / f"{base}.partial.md",
        "sources_json": output_dir / f"{base}.sources.json",
        "artifact_json": output_dir / f"{base}.artifact.json",
        "raw_html": output_dir / f"{base}.raw.html",
    }
```

- [ ] **Step 5: Run the OCR helper unit tests and confirm they pass**

Run:

```bash
uv.exe run pytest tests/connectors/research/test_visual_ocr.py -v
```

Expected: PASS for the pure-helper tests, including bad-input paths and OCR parsing seams.

- [ ] **Step 6: Commit the OCR helper slice**

```bash
git add pyproject.toml h2t_ops/connectors/research/visual_ocr.py tests/connectors/research/test_visual_ocr.py tests/connectors/research/fixtures/visual_ocr
git commit -m "feat(research): add visual ocr rescue helper"
```

## Task 3: Wire the helper into `ResearchClient` and write artifacts

**Files:**
- Modify: `h2t_ops/connectors/research/client.py`
- Modify: `tests/connectors/research/test_client.py`
- Test: `tests/connectors/research/test_client.py`

- [ ] **Step 1: Add failing client tests**

Append these tests to `tests/connectors/research/test_client.py`:

```python
def test_visual_ocr_writes_artifacts_and_returns_envelope(tmp_path, monkeypatch):
    sidecar = tmp_path / "fetch.sources.json"
    sidecar.write_text(
        json.dumps(
            {
                "envelope": {
                    "status": "FAILED",
                    "url": "https://example.com/pops",
                    "content_gate": "none",
                    "telemetry": {"reason_for_failed": "redirect_collapsed_to_homepage"},
                }
            }
        ),
        encoding="utf-8",
    )
    image = tmp_path / "capture.png"
    image.write_bytes(b"fake-image")

    monkeypatch.setattr(
        "h2t_ops.connectors.research.visual_ocr.extract_text_from_image",
        lambda path: ("POPs in TouchDesigner", ["POPs in TouchDesigner"], "medium"),
    )

    rc = client.ResearchClient(output_dir=tmp_path)
    result = rc.visual_ocr(
        fetch_sidecar=str(sidecar),
        image_path=str(image),
        project="demo",
    )

    assert result["kind"] == "research_visual_ocr_envelope"
    assert result["provider_used"] == "visual_ocr"
    assert result["artifact"]["provider_status"] == "OK"
    assert result["artifact"]["artifact_refs"]["sources_json"].endswith(".sources.json")
    persisted = json.loads(
        (tmp_path / result["artifact"]["artifact_refs"]["sources_json"]).read_text(encoding="utf-8")
    )
    assert persisted["body_text_visual_ocr"] == "POPs in TouchDesigner"
    assert (tmp_path / result["artifact"]["artifact_refs"]["artifact_json"]).is_file()
    assert (tmp_path / result["artifact"]["artifact_refs"]["partial_md"]).is_file()


def test_visual_ocr_blocks_login_required(tmp_path):
    sidecar = tmp_path / "fetch.sources.json"
    sidecar.write_text(
        json.dumps(
            {
                "envelope": {
                    "status": "FAILED",
                    "url": "https://example.com/pops",
                    "content_gate": "login_required",
                    "telemetry": {"reason_for_failed": "all_providers_failed"},
                }
            }
        ),
        encoding="utf-8",
    )
    image = tmp_path / "capture.png"
    image.write_bytes(b"fake-image")

    rc = client.ResearchClient(output_dir=tmp_path)
    with pytest.raises(UsageError):
        rc.visual_ocr(fetch_sidecar=str(sidecar), image_path=str(image), project="demo")
```

- [ ] **Step 2: Run the client tests and confirm they fail**

Run:

```bash
uv.exe run pytest tests/connectors/research/test_client.py -k "visual_ocr" -v
```

Expected: FAIL with `ResearchClient` missing `visual_ocr`.

- [ ] **Step 3: Implement `ResearchClient.visual_ocr(...)`**

Add these methods to `h2t_ops/connectors/research/client.py`:

```python
    def _write_visual_ocr_artifacts(
        self,
        *,
        project: str,
        slug_source: str,
        envelope: dict[str, Any],
        telemetry: dict[str, Any],
    ) -> dict[str, Any]:
        paths = artifact_paths(
            output_dir=self.output_dir,
            project=project,
            slug_source=slug_source,
            kind="visual-ocr",
        )
        write_json(paths["sources_json"], envelope)
        partial = [
            "# Research Visual OCR Rescue",
            "",
            f"- status: {envelope.get('status')}",
            f"- provider_used: {envelope.get('provider_used')}",
            f"- url: {envelope.get('url')}",
            f"- quote_safe: {envelope.get('quote_safe')}",
            "",
            "## Visible Headings",
            "",
        ]
        for heading in envelope.get("visible_headings", []):
            partial.append(f"- {heading}")
        partial.extend(
            [
                "",
                "## OCR Text",
                "",
                envelope.get("body_text_visual_ocr", ""),
                "",
            ]
        )
        paths["partial_md"].write_text("\n".join(partial), encoding="utf-8")
        artifact = build_research_artifact(
            artifact_id=artifact_id("research-visual-ocr"),
            provider_status=str(envelope.get("status", "FAILED")),
            tool="h2t-ops research visual-ocr",
            artifact_refs={
                "sources_json": paths["sources_json"].name,
                "partial_md": paths["partial_md"].name,
                "artifact_json": paths["artifact_json"].name,
                "raw_html": None,
            },
            telemetry=telemetry,
        )
        write_json(paths["artifact_json"], artifact)
        append_telemetry(
            self.output_dir / "telemetry.jsonl",
            {
                "kind": "research_telemetry",
                "version": "v1",
                "provider": "visual_ocr",
                "endpoint": "visual_ocr",
                "mode": "single_image",
                "status": envelope.get("status"),
                "latency_ms": None,
                "result_count": 1 if envelope.get("body_text_visual_ocr") else 0,
                "estimated_cost_usd": telemetry.get("estimated_cost_usd"),
                "cost_basis": telemetry.get("cost_basis"),
                "artifact_id": artifact["artifact_id"],
            },
        )
        return artifact


    def visual_ocr(
        self,
        *,
        fetch_sidecar: str,
        image_path: str,
        project: str = "default",
    ) -> dict[str, Any]:
        from h2t_ops.connectors.research import visual_ocr

        sidecar = visual_ocr.load_fetch_sidecar(fetch_sidecar)
        fetch_envelope = visual_ocr.load_fetch_envelope(sidecar)
        visual_ocr.validate_visual_ocr_trigger(fetch_envelope)

        image = Path(image_path).expanduser()
        if not image.is_file():
            raise UsageError(
                f"visual-ocr image not found: {image}",
                hint="Pass one existing PNG/JPG/WebP screenshot via --image-path.",
            )

        text, headings, confidence = visual_ocr.extract_text_from_image(image)
        ocr_envelope = visual_ocr.build_visual_ocr_envelope(
            url=str(fetch_envelope["url"]),
            source_fetch_status=str(fetch_envelope["status"]),
            source_fetch_reason=(
                fetch_envelope.get("telemetry", {}).get("reason_for_failed")
                or fetch_envelope.get("telemetry", {}).get("reason_for_degraded")
            ),
            captured_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            image_path=str(image),
            extracted_text=text,
            visible_headings=headings,
            ocr_confidence=confidence,
        )

        artifact = self._write_visual_ocr_artifacts(
            project=project,
            slug_source=str(fetch_envelope["url"]),
            envelope=ocr_envelope,
            telemetry={
                "calls": 1,
                "providers": ["visual_ocr"],
                "estimated_cost_usd": 0.0,
                "cost_basis": "local_ocr",
            },
        )
        return {"kind": "research_visual_ocr_envelope", **ocr_envelope, "artifact": artifact}
```

- [ ] **Step 4: Run the focused client tests and confirm they pass**

Run:

```bash
uv.exe run pytest tests/connectors/research/test_client.py -k "visual_ocr" -v
```

Expected: PASS for both new tests.

- [ ] **Step 5: Run the combined research connector unit subset**

Run:

```bash
uv.exe run pytest tests/connectors/research/test_commands.py tests/connectors/research/test_client.py tests/connectors/research/test_visual_ocr.py -v
```

Expected: PASS for the new visual OCR tests plus existing unaffected research connector tests.

- [ ] **Step 6: Commit the client integration slice**

```bash
git add h2t_ops/connectors/research/client.py tests/connectors/research/test_client.py
git commit -m "feat(research): wire visual ocr rescue into client"
```

## Task 4: Document the workflow and verify the public CLI

**Files:**
- Modify: `plugins/h2t-ops/skills/research/SKILL.md`
- Modify: `tests/cli/test_h2t_ops_cli.py`
- Test: `tests/cli/test_h2t_ops_cli.py`

- [ ] **Step 1: Add a failing public CLI/help test**

Append to `tests/cli/test_h2t_ops_cli.py`:

```python
def test_h2t_ops_research_help_lists_visual_ocr(capsys):
    code = dispatch(["research", "--help"])

    captured = capsys.readouterr()
    assert code == 0
    assert "visual-ocr" in captured.out
```

- [ ] **Step 2: Run the CLI help test and confirm it fails**

Run:

```bash
uv.exe run pytest tests/cli/test_h2t_ops_cli.py -k "visual_ocr" -v
```

Expected: FAIL because help does not yet mention `visual-ocr`.

- [ ] **Step 3: Update the research skill docs**

In `plugins/h2t-ops/skills/research/SKILL.md`, extend the command block:

```bash
h2t-ops research preflight --json
h2t-ops research search --query "..." --mode generic --num-results 10 --json
h2t-ops research crawl --url "https://..." --json
h2t-ops research fetch --url "https://..." --provider auto --json
h2t-ops research visual-ocr --fetch-sidecar ~/.h2t/research/example.sources.json --image-path ./capture.png --json
```

Add workflow notes under `Required Workflow`:

```md
8. Use `research visual-ocr` only after `fetch` returns `FAILED` or one of the allowed degraded reasons; do not use it for `login_required` or `paid`.
9. `visual-ocr` accepts any existing image path via `--image-path`; screenshot capture is an operator concern, not a hard product dependency of `h2t-ops`.
10. Preferred operator workflow: use the existing `h2t-tools:screenshot` skill to produce one full-page screenshot, then pass that file via `--image-path`.
11. `visual-ocr` produces a weaker, review-required artifact and is not quote-safe by default.
```

- [ ] **Step 4: Run the CLI help test and a focused research connector sweep**

Run:

```bash
uv.exe run pytest tests/cli/test_h2t_ops_cli.py -k "visual_ocr" -v
uv.exe run pytest tests/connectors/research -v
```

Expected:
- first command: PASS
- second command: PASS

- [ ] **Step 5: Manual smoke the public CLI**

Run:

```bash
uv.exe run h2t-ops research visual-ocr --help
```

Expected output includes:

```text
usage: h2t-ops research visual-ocr ...
--fetch-sidecar
--image-path
```

Optional operator smoke with a real screenshot from the existing screenshot skill:

```bash
C:/dev/h2t-tools/.venv/Scripts/python.exe C:/dev/h2t-tools/scripts/screenshot/screenshot.py https://example.com/article --format desktop --out C:/tmp/research-ocr
```

Expected: one PNG under `C:/tmp/research-ocr/<domain>/...png`.

Then run:

```bash
uv.exe run h2t-ops research visual-ocr --fetch-sidecar C:\path\to\failed.sources.json --image-path C:\path\to\capture.png --json
```

Expected output shape includes:

```json
{
  "kind": "research_visual_ocr_envelope",
  "provider_used": "visual_ocr",
  "text_source": "visual_ocr",
  "quote_safe": false,
  "needs_review": true
}
```

- [ ] **Step 6: Commit the docs and final verification slice**

```bash
git add plugins/h2t-ops/skills/research/SKILL.md tests/cli/test_h2t_ops_cli.py
git commit -m "docs(research): document visual ocr rescue workflow"
```

## Task 5: Final review and merge readiness

**Files:**
- Modify: none
- Test: `tests/connectors/research/test_commands.py`
- Test: `tests/connectors/research/test_client.py`
- Test: `tests/connectors/research/test_visual_ocr.py`
- Test: `tests/cli/test_h2t_ops_cli.py`

- [ ] **Step 1: Run the exact final regression suite**

Run:

```bash
uv.exe run pytest tests/connectors/research/test_commands.py tests/connectors/research/test_client.py tests/connectors/research/test_visual_ocr.py tests/cli/test_h2t_ops_cli.py -v
```

Expected: PASS.

- [ ] **Step 2: Inspect git diff for scope discipline**

Run:

```bash
git diff --stat
git diff -- h2t_ops/connectors/research pyproject.toml tests/connectors/research tests/cli/test_h2t_ops_cli.py plugins/h2t-ops/skills/research/SKILL.md
```

Expected:
- only research connector files, one dependency line, tests, and skill docs changed;
- no edits to `fetch.py` ladder behavior;
- no new capture implementation in this repo; screenshot capture remains an external/operator workflow;
- no unrelated `docs/superpowers/*` drafts included.

- [ ] **Step 3: Create the final implementation commit**

```bash
git add pyproject.toml h2t_ops/connectors/research h2t_ops/connectors/research/visual_ocr.py tests/connectors/research tests/cli/test_h2t_ops_cli.py plugins/h2t-ops/skills/research/SKILL.md
git commit -m "feat(research): add visual ocr rescue fallback"
```

- [ ] **Step 4: Push and open PR**

```bash
git push -u origin <branch-name>
gh pr create --fill
```

Expected: branch pushed and PR opened with the visual OCR fallback scope only.

## Self-Review

### Spec coverage

- Separate post-fetch rescue step, not provider rung: covered in Task 2 (`visual_ocr.py`) and Task 3 (`ResearchClient.visual_ocr(...)`), with no ladder mutation.
- Narrow trigger gate: covered in Task 2 tests and `validate_visual_ocr_trigger(...)`.
- Non-canonical output shape: covered in Task 2 envelope builder and Task 3 return artifact.
- One capture path / one OCR path / no stitching: covered by the CLI contract in Task 1 (`--image-path` single file) and the single-image OCR implementation in Task 2.
- Public CLI availability: covered in Task 1 command registration, Task 4 help/smoke/docs.

### Placeholder scan

- No `TODO`, `TBD`, or “handle appropriately” placeholders remain.
- Every task has exact file paths, commands, and concrete code blocks.

### Type consistency

- Public command name is always `visual-ocr`.
- Client method is always `visual_ocr(...)`.
- Envelope keys are always `provider_used`, `text_source`, `body_text_visual_ocr`, `quote_safe`, `needs_review`, `review_status`.
- Input flags are always `--fetch-sidecar` and `--image-path`.

Plan complete and saved to `docs/superpowers/plans/2026-05-25-h2t-ops-visual-ocr-fallback-implementation.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
