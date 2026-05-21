# h2t-ops Research Parity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a first-class `h2t_ops.connectors.research` runtime for Exa search/crawl and the URL fetch ladder while preserving rich provider envelopes, traceability, cost telemetry, and POS-safe artifact boundaries.

**Architecture:** Research is a TZ-2 thick connector. Split the mature skill-local scripts into focused modules: `exa.py` for Exa provider logic, `fetch.py` for URL provider ladder logic, `client.py` for secrets/artifacts/facade methods, and `commands.py` for argparse only. Keep POS registration as an artifact/skill contract: connector emits provider artifacts, the skill/agent supplies registration context, POS owns indexing and promotion.

**Tech Stack:** Python 3.11, stdlib `urllib`/`argparse`/`json`, pytest, h2t_ops typed errors/envelopes, existing lazy connector registry, existing research scripts/tests as behavior authority.

---

## Inputs

| Source | Path / Issue | Use |
|---|---|---|
| Design | `docs/superpowers/specs/2026-05-21-h2t-ops-research-parity-design.md` | Source of truth for scope and boundaries |
| Issue | `#136` | Research connector migration |
| Issue | `#137` | URL fetch ladder integration under research |
| Roadmap | `docs/h2t-ops-roadmap.md` | Closure order and runbook checklist |
| Runbook | `plugins/h2t-ops/references/h2t-connector-runbook.md` | Connector procedure |
| POS boundary | `plugins/h2t-ops/references/pos-operational-boundary.md` | No POS/vault/lake/context writes |
| Legacy Exa runtime | `plugins/h2t-ops/skills/research/scripts/exa_search.py` | Behavior source |
| Legacy fetch runtime | `plugins/h2t-ops/skills/research/scripts/fetch_url.py` | Behavior source |
| Legacy Exa tests | `plugins/h2t-ops/skills/research/tests/test_exa_search.py` | Behavior tests to port |
| Legacy fetch tests | `plugins/h2t-ops/skills/research/tests/test_fetch_url.py` | Behavior tests to port |
| Connector pattern | `h2t_ops/connectors/{gmail,telegram,meetgeek}/` | CLI/test style |

---

## File Map

| File | Action | Owner task | Responsibility |
|---|---|---|---|
| `h2t_ops/core/errors.py` | Modify | T1 | Add sanitized JSON details support to typed errors |
| `h2t_ops/core/envelope.py` | Modify | T1 | Include `error.details` when present |
| `tests/core/test_errors.py` | Modify | T1 | Details storage tests |
| `tests/core/test_envelope.py` | Modify | T1 | Details envelope tests |
| `tests/core/test_output.py` | Modify | T1 | JSON output keeps details and old shape |
| `h2t_ops/connectors/research/__init__.py` | Create | T7 | ConnectorSpec registration |
| `h2t_ops/connectors/research/client.py` | Create | T2/T4/T6 | Secrets, artifact helpers, ResearchClient facade |
| `h2t_ops/connectors/research/exa.py` | Create | T3 | Exa `/search` and `/contents` provider logic |
| `h2t_ops/connectors/research/systemprompts/*.md` | Create | T3 | Package-local Exa mode prompts |
| `h2t_ops/connectors/research/fetch.py` | Create | T5/T6 | URL fetch providers and ladder |
| `h2t_ops/connectors/research/commands.py` | Create | T7 | argparse surface, lazy client dispatch |
| `h2t_ops/cli.py` | Modify | T7 | Add `"research"` to `_MIGRATED` |
| `pyproject.toml` | Modify | T3 | Include research prompt markdown files as package data |
| `tests/connectors/research/__init__.py` | Create | T2 | Test package marker |
| `tests/connectors/research/test_client.py` | Create | T2/T4/T6 | Secrets, artifacts, facade tests |
| `tests/connectors/research/test_exa.py` | Create | T3/T4 | Ported Exa tests |
| `tests/connectors/research/test_fetch.py` | Create | T5/T6 | Ported fetch ladder tests |
| `tests/connectors/research/test_commands.py` | Create | T7 | Parser/dispatch/lazy tests |
| `tests/connectors/research/fixtures/fetch/*` | Create | T5 | Copied fetch fixtures |
| `plugins/h2t-ops/skills/research/SKILL.md` | Modify | T8 | Thin connector delegation + traceability workflow |
| `plugins/h2t-ops/skills/research/references/research-artifact-contract.md` | Create | T8 | Provider artifact and registration manifest contract |
| `plugins/h2t-ops/skills/research/references/traceability-policy.md` | Create | T8 | URL + quote + confidence policy |
| `plugins/h2t-ops/skills/research/references/telemetry-policy.md` | Create | T8 | Cost/usage telemetry policy |
| `plugins/h2t-ops/skills/research/references/templates/*.md` | Create | T8 | Lazy report/registration templates |

Do not modify `plugins/h2t/skills/research/**` in this plan.

---

## Hard Constraints

1. Do not create a top-level `h2t-ops fetch` connector.
2. `h2t_ops/connectors/research/**` must not write `~/.dor/**`, `vault`, `lake`, `context`, `pos.db`, or `dor.db`; read-only `~/.dor/secrets/...` fallback is explicitly allowed for secrets.
3. `h2t_ops/connectors/research/**` must not import POS modules or call POS CLIs.
4. `h2t_ops/connectors/research/**` must not use WebSearch/WebFetch fallback logic.
5. `h2t_ops/connectors/research/**` must not discover plugin-cache script paths.
6. `h2t-ops --help` and `h2t-ops connectors` must not resolve `EXA_API_KEY`, call Exa, call Jina, or touch network.
7. Preserve `OK | DEGRADED | FAILED` provider status exactly.
8. Preserve hard-gate behavior for login/paywall content.
9. Preserve `~/.h2t/research/` artifact storage.
10. Keep `research_artifact_registration/v1` as a skill/agent/POS contract unless a writer script is explicitly added in T8.
11. Details included in error envelopes must be public, sanitized, JSON-serializable data.
12. Each commit-bearing task stages only files listed for that task.

---

## Shared Commands

Use these commands unless a task gives a narrower command:

```powershell
uv run pytest tests/core tests/connectors -q
uv run h2t-ops dev check lazy-registry
uv run h2t-ops connectors
```

Expected:

```text
OK lazy-registry
```

Boundary grep:

```powershell
Select-String -Path h2t_ops/connectors/research/*.py -Pattern "vault|lake|pos\\.db|dor\\.db|context/|WebSearch|WebFetch|plugins/cache|CLAUDE_PLUGIN_ROOT|H2T_PLUGIN_ROOT"
Select-String -Path h2t_ops/connectors/research/*.py -Pattern "\\.dor" | Where-Object { $_.Line -notmatch 'secrets' }
```

Expected: no matches. Read-only `~/.dor/secrets/...` fallback lines are allowed.

Token leak grep:

```powershell
Select-String -Path h2t_ops/connectors/research/*.py,tests/connectors/research/*.py,plugins/h2t-ops/skills/research/references/*.md,plugins/h2t-ops/skills/research/references/templates/*.md -Pattern "secret_[A-Za-z0-9]|EXA_API_KEY=[A-Za-z0-9]|JINA_API_KEY=[A-Za-z0-9]|Bearer [A-Za-z0-9]"
```

Expected: no matches.

---

## T0 - Baseline And File-State Verification

**Files:**
- Read only

- [ ] **Step 1: Confirm branch and dirty tree**

Run:

```powershell
git status --short --branch
```

Expected:

```text
## main...origin/main
```

or:

```text
## main...origin/main [ahead 1]
```

Unrelated dirty files may exist. Do not stage or modify them.

- [ ] **Step 2: Confirm research connector does not already exist**

Run:

```powershell
Test-Path h2t_ops/connectors/research
```

Expected:

```text
False
```

If it prints `True`, stop and inspect the existing package before continuing.

- [ ] **Step 3: Run existing research tests as baseline**

Run:

```powershell
uv run pytest plugins/h2t-ops/skills/research/tests -q
```

Expected: all existing research tests pass. If a known optional `trafilatura` test is skipped, record the skip count and continue.

- [ ] **Step 4: Run connector baseline**

Run:

```powershell
uv run pytest tests/core tests/connectors -q
uv run h2t-ops dev check lazy-registry
```

Expected: all current core/connector tests pass and lazy-registry prints `OK lazy-registry`.

- [ ] **Step 5: Do not commit**

T0 is read-only. No git add, no commit.

---

## T1 - Core Error Details Support

**Files:**
- Modify: `h2t_ops/core/errors.py`
- Modify: `h2t_ops/core/envelope.py`
- Test: `tests/core/test_errors.py`
- Test: `tests/core/test_envelope.py`
- Test: `tests/core/test_output.py`

- [ ] **Step 1: Add failing tests for details storage**

Append to `tests/core/test_errors.py`:

```python
def test_details_stored_and_defaults_none():
    e = UsageError("bad arg", details={"field": "query", "reason": "missing"})
    assert e.details == {"field": "query", "reason": "missing"}
    assert UsageError("bad arg").details is None


def test_details_do_not_change_message_or_hint():
    e = ConfigError("missing key", hint="Set EXA_API_KEY", details={"key": "EXA_API_KEY"})
    assert str(e) == "missing key"
    assert e.hint == "Set EXA_API_KEY"
    assert e.details == {"key": "EXA_API_KEY"}
```

- [ ] **Step 2: Add failing tests for error envelope details**

Append to `tests/core/test_envelope.py`:

```python
from h2t_ops.core.errors import ProviderError


def test_error_shape_with_details():
    env = error_envelope(
        "research",
        ProviderError(
            "Exa failed",
            details={"provider_envelope": {"status": "FAILED", "primary_engine": "exa"}},
        ),
    )
    assert env == {
        "ok": False,
        "provider": "research",
        "error": {
            "type": "provider",
            "message": "Exa failed",
            "hint": None,
            "details": {"provider_envelope": {"status": "FAILED", "primary_engine": "exa"}},
        },
    }


def test_error_shape_without_details_keeps_old_shape():
    env = error_envelope("research", ProviderError("Exa failed"))
    assert env == {
        "ok": False,
        "provider": "research",
        "error": {"type": "provider", "message": "Exa failed", "hint": None},
    }
```

- [ ] **Step 3: Add failing test for JSON output with details**

Append to `tests/core/test_output.py`:

```python
import json

from h2t_ops.core.errors import ProviderError
from h2t_ops.core.output import emit


def test_emit_json_includes_error_details(capsys):
    code = emit(
        "research",
        exc=ProviderError(
            "Exa failed",
            details={"provider_envelope": {"status": "FAILED", "reason": "exa_4xx_nonretryable"}},
        ),
        fmt="json",
    )
    captured = capsys.readouterr()
    payload = json.loads(captured.err)
    assert code == 1
    assert payload["error"]["details"] == {
        "provider_envelope": {"status": "FAILED", "reason": "exa_4xx_nonretryable"}
    }
```

- [ ] **Step 4: Run tests and verify they fail**

Run:

```powershell
uv run pytest tests/core/test_errors.py::test_details_stored_and_defaults_none tests/core/test_envelope.py::test_error_shape_with_details tests/core/test_output.py::test_emit_json_includes_error_details -q
```

Expected: FAIL because `H2TError.__init__()` does not accept `details`.

- [ ] **Step 5: Implement details storage**

Modify `h2t_ops/core/errors.py` so `H2TError` becomes:

```python
class H2TError(Exception):
    """Base. Carries an optional install/fix hint and public diagnostic details.
    Always raise a typed subclass; do not raise H2TError directly."""
    kind: str = "provider"

    def __init__(
        self,
        message: str,
        *,
        hint: str | None = None,
        details: object | None = None,
    ) -> None:
        super().__init__(message)
        self.hint = hint
        self.details = details
```

- [ ] **Step 6: Implement envelope details**

Modify `h2t_ops/core/envelope.py` so `error_envelope()` becomes:

```python
def error_envelope(provider: str, exc: BaseException) -> dict[str, Any]:
    kind = exc.kind if isinstance(exc, H2TError) else "provider"
    hint = exc.hint if isinstance(exc, H2TError) else None
    error = {"type": kind, "message": str(exc), "hint": hint}
    if isinstance(exc, H2TError) and exc.details is not None:
        error["details"] = exc.details
    return {"ok": False, "provider": provider, "error": error}
```

- [ ] **Step 7: Run core tests**

Run:

```powershell
uv run pytest tests/core/test_errors.py tests/core/test_envelope.py tests/core/test_output.py -q
```

Expected: PASS.

- [ ] **Step 8: Run connector regression**

Run:

```powershell
uv run pytest tests/core tests/connectors -q
```

Expected: PASS.

- [ ] **Step 9: Commit**

Run:

```powershell
git add h2t_ops/core/errors.py h2t_ops/core/envelope.py tests/core/test_errors.py tests/core/test_envelope.py tests/core/test_output.py
git commit -m "feat(core): include sanitized error details"
```

---

## T2 - Research Secrets, Artifact, And Telemetry Helpers

**Files:**
- Create: `h2t_ops/connectors/research/client.py`
- Create: `tests/connectors/research/__init__.py`
- Create: `tests/connectors/research/test_client.py`

- [ ] **Step 1: Create research test package marker**

Create `tests/connectors/research/__init__.py` as an empty file.

- [ ] **Step 2: Add failing tests for secrets resolution**

Create `tests/connectors/research/test_client.py` with:

```python
from __future__ import annotations

import json
from pathlib import Path

import pytest

from h2t_ops.core.errors import ConfigError
from h2t_ops.connectors.research import client


def test_resolve_secret_env_wins(monkeypatch, tmp_path):
    file_path = tmp_path / "secrets.env"
    file_path.write_text("EXA_API_KEY=file-key\n", encoding="utf-8")
    monkeypatch.setenv("EXA_API_KEY", "env-key")
    monkeypatch.setenv("H2T_SECRETS_FILE", str(file_path))
    assert client.resolve_secret("EXA_API_KEY") == "env-key"


def test_resolve_secret_h2t_secrets_file(monkeypatch, tmp_path):
    file_path = tmp_path / "secrets.env"
    file_path.write_text("EXA_API_KEY=file-key\n", encoding="utf-8")
    monkeypatch.delenv("EXA_API_KEY", raising=False)
    monkeypatch.setenv("H2T_SECRETS_FILE", str(file_path))
    assert client.resolve_secret("EXA_API_KEY") == "file-key"


def test_resolve_secret_canonical_and_legacy_paths(monkeypatch, tmp_path):
    home = tmp_path / "home"
    canonical = home / ".dor" / "secrets" / "secrets.env"
    legacy = home / ".dor" / "secrets.env"
    canonical.parent.mkdir(parents=True)
    legacy.parent.mkdir(parents=True, exist_ok=True)
    canonical.write_text("EXA_API_KEY=canonical-key\n", encoding="utf-8")
    legacy.write_text("EXA_API_KEY=legacy-key\n", encoding="utf-8")
    monkeypatch.delenv("EXA_API_KEY", raising=False)
    monkeypatch.delenv("H2T_SECRETS_FILE", raising=False)
    monkeypatch.setattr(client.Path, "home", lambda: home)
    assert client.resolve_secret("EXA_API_KEY") == "canonical-key"
    canonical.unlink()
    assert client.resolve_secret("EXA_API_KEY") == "legacy-key"


def test_resolve_secret_missing_raises_configerror(monkeypatch, tmp_path):
    monkeypatch.delenv("EXA_API_KEY", raising=False)
    monkeypatch.delenv("H2T_SECRETS_FILE", raising=False)
    monkeypatch.setattr(client.Path, "home", lambda: tmp_path)
    with pytest.raises(ConfigError) as exc:
        client.resolve_secret("EXA_API_KEY")
    assert "EXA_API_KEY not found" in str(exc.value)
    assert exc.value.hint
```

- [ ] **Step 3: Add failing tests for artifact paths, redaction, and telemetry**

Append to `tests/connectors/research/test_client.py`:

```python
def test_artifact_paths_are_under_output_dir(tmp_path):
    paths = client.artifact_paths(
        output_dir=tmp_path,
        project="h2t skills",
        slug_source="Research connector migration",
        kind="search",
    )
    assert paths["sources_json"].parent == tmp_path
    assert paths["partial_md"].parent == tmp_path
    assert paths["artifact_json"].parent == tmp_path
    assert paths["sources_json"].name.startswith("h2t-skills-research-connector-migration-")
    assert paths["artifact_json"].name.endswith(".artifact.json")


def test_sanitize_details_redacts_known_tokens():
    exa_value = "secret" + "_exa_value"
    bearer_value = "abc123"
    jina_value = "jina-secret-value"
    details = {
        "request_headers": {
            "x-api-key": exa_value,
            "Authorization": "Bearer " + bearer_value,
        },
        "provider_envelope": {
            "status": "FAILED",
            "message": "JINA_API_KEY=" + jina_value,
        },
    }
    redacted = client.sanitize_details(details)
    text = json.dumps(redacted, ensure_ascii=False)
    assert exa_value not in text
    assert bearer_value not in text
    assert jina_value not in text
    assert "[REDACTED]" in text


def test_write_research_artifact_json(tmp_path):
    path = tmp_path / "artifact.json"
    artifact = client.build_research_artifact(
        artifact_id="research_test",
        provider_status="OK",
        tool="h2t-ops research",
        artifact_refs={
            "sources_json": "sources.json",
            "partial_md": "partial.md",
            "artifact_json": "artifact.json",
            "raw_html": None,
        },
        telemetry={"calls": 1, "providers": ["exa"], "estimated_cost_usd": 0.012, "cost_basis": "provider_reported"},
    )
    client.write_json(path, artifact)
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert loaded["kind"] == "research_artifact"
    assert loaded["version"] == "v1"
    assert loaded["telemetry"]["cost_basis"] == "provider_reported"


def test_append_telemetry_best_effort(tmp_path):
    ledger = tmp_path / "telemetry.jsonl"
    record = {
        "kind": "research_telemetry",
        "version": "v1",
        "provider": "exa",
        "status": "OK",
        "estimated_cost_usd": 0.012,
        "cost_basis": "provider_reported",
    }
    assert client.append_telemetry(ledger, record) is True
    assert json.loads(ledger.read_text(encoding="utf-8").strip()) == record
```

- [ ] **Step 4: Run tests and verify they fail**

Run:

```powershell
uv run pytest tests/connectors/research/test_client.py -q
```

Expected: FAIL because `h2t_ops.connectors.research` does not exist.

- [ ] **Step 5: Create minimal client helpers**

Create `h2t_ops/connectors/research/client.py` with:

```python
"""Research connector facade and shared helpers."""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from h2t_ops.core.errors import ConfigError

DEFAULT_OUTPUT_DIR = Path.home() / ".h2t" / "research"
CANONICAL_SECRETS_FILE = Path.home() / ".dor" / "secrets" / "secrets.env"
LEGACY_SECRETS_FILE = Path.home() / ".dor" / "secrets.env"
TOKEN_PATTERNS = (
    re.compile(r"secret_[A-Za-z0-9_\-]+"),
    re.compile(r"Bearer\s+[A-Za-z0-9._\-]+"),
    re.compile(r"(EXA_API_KEY|JINA_API_KEY)=([^,\s]+)"),
)


def _read_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        values[key.strip()] = value
    return values


def resolve_secret(name: str) -> str:
    existing = os.environ.get(name)
    if existing:
        return existing
    candidates: list[Path] = []
    override = os.environ.get("H2T_SECRETS_FILE")
    if override:
        candidates.append(Path(override))
    home = Path.home()
    candidates.append(home / ".dor" / "secrets" / "secrets.env")
    candidates.append(home / ".dor" / "secrets.env")
    for path in candidates:
        values = _read_env_file(path)
        value = values.get(name)
        if value:
            os.environ[name] = value
            return value
    raise ConfigError(
        f"{name} not found.",
        hint=(
            f"Set {name} in the shell, $H2T_SECRETS_FILE, "
            "~/.dor/secrets/secrets.env, or ~/.dor/secrets.env"
        ),
    )


def slugify(text: str, max_len: int = 60) -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "-", text.lower()).strip("-")
    return value[:max_len].strip("-") or "research"


def artifact_id(prefix: str = "research") -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{prefix}_{stamp}"


def artifact_paths(
    *,
    output_dir: Path,
    project: str,
    slug_source: str,
    kind: str,
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    base = f"{slugify(project)}-{slugify(slug_source)}-{kind}-{date}"
    return {
        "partial_md": output_dir / f"{base}.partial.md",
        "sources_json": output_dir / f"{base}.sources.json",
        "artifact_json": output_dir / f"{base}.artifact.json",
        "raw_html": output_dir / f"{base}.raw.html",
    }


def _redact_text(value: str) -> str:
    redacted = value
    for pattern in TOKEN_PATTERNS:
        redacted = pattern.sub("[REDACTED]", redacted)
    return redacted


def sanitize_details(value: Any) -> Any:
    if isinstance(value, str):
        return _redact_text(value)
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in value.items():
            if str(key).lower() in {"authorization", "x-api-key", "api_key", "token"}:
                result[str(key)] = "[REDACTED]"
            else:
                result[str(key)] = sanitize_details(item)
        return result
    if isinstance(value, list):
        return [sanitize_details(item) for item in value]
    if value is None or isinstance(value, (int, float, bool)):
        return value
    return _redact_text(str(value))


def build_research_artifact(
    *,
    artifact_id: str,
    provider_status: str,
    tool: str,
    artifact_refs: dict[str, Any],
    telemetry: dict[str, Any],
) -> dict[str, Any]:
    return {
        "kind": "research_artifact",
        "version": "v1",
        "artifact_id": artifact_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "tool": tool,
        "provider_status": provider_status,
        "artifact_refs": artifact_refs,
        "telemetry": telemetry,
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def append_telemetry(path: Path, record: dict[str, Any]) -> bool:
    if os.environ.get("H2T_RESEARCH_TELEMETRY_DISABLE") == "1":
        return False
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        return True
    except OSError:
        return False


class ResearchClient:
    """Facade filled by later tasks."""

    def __init__(self, *, output_dir: Path | None = None) -> None:
        self.output_dir = output_dir or DEFAULT_OUTPUT_DIR
```

- [ ] **Step 6: Run tests**

Run:

```powershell
uv run pytest tests/connectors/research/test_client.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

Run:

```powershell
git add h2t_ops/connectors/research/client.py tests/connectors/research/__init__.py tests/connectors/research/test_client.py
git commit -m "feat(research): add secrets and artifact helpers"
```

---

## T3 - Exa Provider Core

**Files:**
- Create: `h2t_ops/connectors/research/exa.py`
- Create: `h2t_ops/connectors/research/systemprompts/*.md`
- Modify: `pyproject.toml`
- Test: `tests/connectors/research/test_exa.py`

- [ ] **Step 1: Create exa tests by porting legacy tests**

Create `tests/connectors/research/test_exa.py` by copying the following behavior from `plugins/h2t-ops/skills/research/tests/test_exa_search.py` and changing imports from `exa_search` to `h2t_ops.connectors.research.exa`:

| Legacy test area | Required tests in `test_exa.py` |
|---|---|
| mode/category config | `test_mode_config_has_all_seven_modes`, `test_mode_config_competitor_uses_company_category`, `test_mode_config_deep_uses_deep_type_default_10`, `test_mode_config_fast_uses_fast_type` |
| args validation | `test_category_blocks_company_blocks_dates_and_domains`, `test_category_blocks_people_blocks_text_and_dates`, `test_validate_competitor_with_start_date_raises_usageerror`, `test_validate_people_with_exclude_text_raises_usageerror`, `test_validate_include_text_multi_item_raises_usageerror`, `test_validate_valid_combinations_pass` |
| system prompts | `test_load_system_prompt_parses_frontmatter_and_body`, `test_load_system_prompt_parses_output_schema_json`, `test_load_system_prompt_missing_file_raises_configerror` |
| body builder | `test_build_body_generic_minimal`, `test_build_body_competitor_sets_category`, `test_build_body_news_with_dates_and_domains`, `test_build_body_deep_with_additional_queries`, `test_build_body_with_schema_sets_structuredoutput`, `test_build_body_num_results_override` |
| Exa HTTP | `test_call_exa_returns_tuple_on_success`, `test_call_exa_raises_transient_on_5xx`, `test_call_exa_raises_transient_on_429`, `test_call_exa_raises_permanent_on_4xx`, `test_call_exa_raises_transient_on_urlerror`, `test_call_exa_raises_malformed_on_bad_json`, `test_call_exa_sets_user_agent_header` |
| envelope/retry | `test_build_envelope_ok_shape`, `test_build_envelope_degraded_with_reason`, `test_search_with_retry_ok_first_try`, `test_search_with_retry_empty_then_empty_is_degraded`, `test_search_with_retry_empty_then_ok_is_ok`, `test_search_with_retry_5xx_then_5xx_is_failed`, `test_search_with_retry_urlerror_then_urlerror_is_failed`, `test_search_with_retry_429_triggers_retry`, `test_search_with_retry_no_retry_flag_disables_retries` |

Important porting changes:

```python
from h2t_ops.core.errors import ConfigError, ProviderError, UsageError
from h2t_ops.connectors.research import exa
```

Replace `pytest.raises(SystemExit)` arg/config cases with typed errors:

```python
with pytest.raises(UsageError):
    exa.validate_args(args)
```

Replace missing system prompt exit with:

```python
with pytest.raises(ConfigError):
    exa.load_system_prompt("missing")
```

- [ ] **Step 2: Verify exact Exa test list is present**

Run:

```powershell
Select-String -Path tests/connectors/research/test_exa.py -Pattern "test_mode_config_has_all_seven_modes|test_search_with_retry_no_retry_flag_disables_retries|test_call_exa_sets_user_agent_header|test_load_system_prompt_missing_file_raises_configerror"
```

Expected: all four sentinel test names appear. If any sentinel is missing, stop and finish the port before running pytest.

- [ ] **Step 3: Run tests and verify they fail**

Run:

```powershell
uv run pytest tests/connectors/research/test_exa.py -q
```

Expected: FAIL because `h2t_ops.connectors.research.exa` does not exist.

- [ ] **Step 4: Copy package-local Exa system prompts**

Run:

```powershell
New-Item -ItemType Directory -Force h2t_ops/connectors/research/systemprompts
Copy-Item plugins/h2t-ops/skills/research/systemprompts/*.md h2t_ops/connectors/research/systemprompts/
```

Expected: `h2t_ops/connectors/research/systemprompts/` contains `academic.md`, `competitor.md`, `deep.md`, `fast.md`, `generic.md`, `news.md`, and `people.md`.

- [ ] **Step 5: Add package-data entry for prompts**

Append this section to `pyproject.toml` if it is not already present:

```toml
[tool.setuptools.package-data]
"h2t_ops.connectors.research" = ["systemprompts/*.md"]
```

- [ ] **Step 6: Create Exa provider module by mechanical port**

Create `h2t_ops/connectors/research/exa.py` by porting these exact symbols from `plugins/h2t-ops/skills/research/scripts/exa_search.py`:

```text
__version__
SCRIPT_DIR
SYSTEMPROMPTS_DIR
MODE_CONFIG
CATEGORY_BLOCKS
MODES
ExaTransientError
ExaPermanentError
ExaMalformedResponseError
sleep_with_jitter
ENVELOPE_VERSION
build_envelope
RETRY_BACKOFF_SECONDS
RETRY_BUDGET_SECONDS
_classify_attempt_from_call
_exit_code_for_failure
search_with_retry
call_exa
preflight
load_system_prompt
build_body
_split_csv
```

Required adaptations:

```python
from h2t_ops.core.errors import ConfigError, NetworkError, ProviderError, UsageError
```

Set prompt paths to the new package-local directory:

```python
SCRIPT_DIR = Path(__file__).resolve().parent
SYSTEMPROMPTS_DIR = SCRIPT_DIR / "systemprompts"
```

Use typed errors instead of `die()`:

```python
def validate_args(args: argparse.Namespace) -> None:
    ...
    raise UsageError("EXA_ERROR:ARGS ...")
```

Use `ConfigError` for missing prompt/config:

```python
raise ConfigError(f"systemprompt file missing: {path}")
```

Make `preflight()` silent and typed-error based. It must not print `OK`; the command layer will wrap its return value.

```python
def preflight(api_key: str) -> None:
    req = urllib.request.Request(
        f"{EXA_API}/",
        method="GET",
        headers={"User-Agent": f"exa_search.py/{__version__} (h2t-ops:research)"},
    )
    try:
        urllib.request.urlopen(req, timeout=5)
    except urllib.error.HTTPError:
        return
    except urllib.error.URLError as exc:
        raise NetworkError(f"EXA_ERROR:NETWORK cannot reach {EXA_API}: {exc.reason}") from exc
```

Keep provider exception classes local to `exa.py`; they are not `H2TError` because `search_with_retry()` converts them into provider envelopes.

Do not port these CLI/output symbols in T3:

```text
die
slugify
output_paths
render_stdout_summary
write_sources_json
write_partial_md
post_telemetry
_build_parser
main
_run_search
_run_crawl
```

- [ ] **Step 7: Run Exa tests**

Run:

```powershell
uv run pytest tests/connectors/research/test_exa.py -q
```

Expected: PASS.

- [ ] **Step 8: Run lazy registry**

Run:

```powershell
uv run h2t-ops dev check lazy-registry
```

Expected: `OK lazy-registry`.

- [ ] **Step 9: Commit**

Run:

```powershell
git add h2t_ops/connectors/research/exa.py h2t_ops/connectors/research/systemprompts pyproject.toml tests/connectors/research/test_exa.py
git commit -m "feat(research): add Exa provider core"
```

---

## T4 - Exa Facade, Artifacts, And Failed Envelope Mapping

**Files:**
- Modify: `h2t_ops/connectors/research/client.py`
- Modify: `tests/connectors/research/test_client.py`
- Modify: `tests/connectors/research/test_exa.py`

- [ ] **Step 1: Add failing ResearchClient search/crawl tests**

Append to `tests/connectors/research/test_client.py`:

```python
from unittest.mock import patch

from h2t_ops.core.errors import NetworkError, ProviderError


def test_research_client_search_ok_writes_sources_and_artifact(tmp_path, monkeypatch):
    monkeypatch.setenv("EXA_API_KEY", "env-key")
    provider_env = {
        "status": "OK",
        "primary_engine": "exa",
        "fallback_engine_used": None,
        "results": [{"title": "A", "url": "https://example.com", "highlights": ["quote"]}],
        "telemetry": {
            "attempts": [{"engine": "exa", "endpoint": "/search", "http": 200, "latency_ms": 10, "error": None}],
            "reason_for_fallback": None,
            "total_latency_ms": 10,
            "total_cost_usd": 0.012,
        },
        "meta": {"query": "q", "mode": "generic", "num_results_returned": 1, "envelope_version": "1"},
    }
    with patch("h2t_ops.connectors.research.exa.search_with_retry", return_value=(provider_env, 0)):
        with patch("h2t_ops.connectors.research.exa.load_system_prompt", return_value=("prompt", {})):
            result = client.ResearchClient(output_dir=tmp_path).search(query="q", mode="generic")
    assert result["status"] == "OK"
    assert result["artifact"]["kind"] == "research_artifact"
    assert Path(result["artifact"]["artifact_refs"]["sources_json"]).is_file()
    assert Path(result["artifact"]["artifact_refs"]["partial_md"]).is_file()
    assert Path(result["artifact"]["artifact_refs"]["artifact_json"]).is_file()
    assert result["artifact"]["telemetry"]["cost_basis"] == "provider_reported"


def test_research_client_search_failed_raises_providererror_with_details(tmp_path, monkeypatch):
    monkeypatch.setenv("EXA_API_KEY", "env-key")
    provider_env = {
        "status": "FAILED",
        "primary_engine": "exa",
        "fallback_engine_used": None,
        "results": [],
        "telemetry": {
            "attempts": [{"engine": "exa", "endpoint": "/search", "http": 401, "latency_ms": 10, "error": "exa_4xx_nonretryable"}],
            "reason_for_fallback": "exa_4xx_nonretryable",
            "total_latency_ms": 10,
            "total_cost_usd": 0.0,
        },
        "meta": {"query": "q", "mode": "generic", "num_results_returned": 0, "envelope_version": "1"},
    }
    with patch("h2t_ops.connectors.research.exa.search_with_retry", return_value=(provider_env, 2)):
        with patch("h2t_ops.connectors.research.exa.load_system_prompt", return_value=("prompt", {})):
            with pytest.raises(ProviderError) as exc:
                client.ResearchClient(output_dir=tmp_path).search(query="q", mode="generic")
    assert exc.value.details["provider_envelope"]["status"] == "FAILED"


def test_research_client_search_network_failure_maps_to_networkerror(tmp_path, monkeypatch):
    monkeypatch.setenv("EXA_API_KEY", "env-key")
    provider_env = {
        "status": "FAILED",
        "primary_engine": "exa",
        "fallback_engine_used": None,
        "results": [],
        "telemetry": {
            "attempts": [{"engine": "exa", "endpoint": "/search", "http": None, "latency_ms": 10, "error": "exa_network_timeout"}],
            "reason_for_fallback": "exa_network_timeout",
            "total_latency_ms": 10,
            "total_cost_usd": 0.0,
        },
        "meta": {"query": "q", "mode": "generic", "num_results_returned": 0, "envelope_version": "1"},
    }
    with patch("h2t_ops.connectors.research.exa.search_with_retry", return_value=(provider_env, 3)):
        with patch("h2t_ops.connectors.research.exa.load_system_prompt", return_value=("prompt", {})):
            with pytest.raises(NetworkError) as exc:
                client.ResearchClient(output_dir=tmp_path).search(query="q", mode="generic")
    assert exc.value.details["provider_envelope"]["telemetry"]["attempts"][0]["error"] == "exa_network_timeout"
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```powershell
uv run pytest tests/connectors/research/test_client.py -q
```

Expected: FAIL because `ResearchClient.search()` is not implemented.

- [ ] **Step 3: Implement Exa facade methods**

Modify `h2t_ops/connectors/research/client.py`:

Add imports:

```python
import argparse

from h2t_ops.core.errors import NetworkError, ProviderError, UsageError
```

Add helper:

```python
def _raise_for_provider_failure(message: str, provider_envelope: dict[str, Any], exit_code: int) -> None:
    details = sanitize_details({"provider_envelope": provider_envelope})
    if exit_code == 3:
        raise NetworkError(message, details=details)
    if exit_code == 1:
        raise UsageError(message, details=details)
    raise ProviderError(message, details=details)
```

Extend `ResearchClient`:

```python
    def _write_provider_artifacts(
        self,
        *,
        kind: str,
        slug_source: str,
        project: str,
        provider_envelope: dict[str, Any],
        telemetry: dict[str, Any],
        ledger_provider: str,
        ledger_endpoint: str,
        ledger_mode: str | None = None,
        raw_html_path: str | None = None,
    ) -> dict[str, Any]:
        paths = artifact_paths(
            output_dir=self.output_dir,
            project=project,
            slug_source=slug_source,
            kind=kind,
        )
        sources_payload = {
            "kind": "research_sources",
            "version": "v1",
            "project": project,
            "envelope": provider_envelope,
        }
        write_json(paths["sources_json"], sources_payload)
        partial = paths["partial_md"]
        partial.write_text(
            "\n".join(
                [
                    f"# Research artifact: {slug_source}",
                    "",
                    f"- status: {provider_envelope.get('status', 'UNKNOWN')}",
                    f"- provider: {ledger_provider}",
                    f"- endpoint: {ledger_endpoint}",
                    f"- sources_json: {paths['sources_json']}",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        artifact = build_research_artifact(
            artifact_id=artifact_id(),
            provider_status=provider_envelope.get("status", "UNKNOWN"),
            tool="h2t-ops research",
            artifact_refs={
                "sources_json": str(paths["sources_json"]),
                "partial_md": str(partial),
                "artifact_json": str(paths["artifact_json"]),
                "raw_html": raw_html_path,
            },
            telemetry=telemetry,
        )
        write_json(paths["artifact_json"], artifact)
        append_telemetry(
            self.output_dir / "telemetry.jsonl",
            {
                "kind": "research_telemetry",
                "version": "v1",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "artifact_id": artifact["artifact_id"],
                "provider": ledger_provider,
                "endpoint": ledger_endpoint,
                "mode": ledger_mode,
                "status": provider_envelope.get("status"),
                "estimated_cost_usd": telemetry["estimated_cost_usd"],
                "cost_basis": telemetry["cost_basis"],
                "result_count": len(provider_envelope.get("results", []))
                if "results" in provider_envelope
                else provider_envelope.get("body_chars", 0),
            },
        )
        return artifact

    def search(
        self,
        *,
        query: str,
        mode: str = "generic",
        depth: str = "standard",
        num_results: int | None = None,
        additional_queries: list[str] | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        include_domains: list[str] | None = None,
        exclude_domains: list[str] | None = None,
        include_text: list[str] | None = None,
        exclude_text: list[str] | None = None,
        country: str | None = None,
        full_text: bool = False,
        project: str = "default",
        no_retry: bool = False,
    ) -> dict[str, Any]:
        from h2t_ops.connectors.research import exa

        api_key = resolve_secret("EXA_API_KEY")
        args = argparse.Namespace(
            query=query,
            mode=mode,
            depth=depth,
            num_results=num_results,
            additional_queries=additional_queries,
            start_date=start_date,
            end_date=end_date,
            include_domains=include_domains,
            exclude_domains=exclude_domains,
            include_text=include_text,
            exclude_text=exclude_text,
            country=country,
            full_text=full_text,
            no_retry=no_retry,
        )
        exa.validate_args(args)
        prompt, schema = exa.load_system_prompt(mode)
        body = exa.build_body(args, prompt, schema)
        provider_envelope, exit_code = exa.search_with_retry(
            body=body,
            api_key=api_key,
            retry=not no_retry,
            mode=mode,
        )
        attempts = provider_envelope.get("telemetry", {}).get("attempts", [])
        telemetry = {
            "calls": len(attempts),
            "providers": sorted({
                attempt.get("engine") or attempt.get("provider")
                for attempt in attempts
                if attempt.get("engine") or attempt.get("provider")
            }),
            "estimated_cost_usd": provider_envelope.get("telemetry", {}).get("total_cost_usd"),
            "cost_basis": "provider_reported",
        }
        artifact = self._write_provider_artifacts(
            kind="search",
            slug_source=query,
            project=project,
            provider_envelope=provider_envelope,
            telemetry=telemetry,
            ledger_provider="exa",
            ledger_endpoint="/search",
            ledger_mode=mode,
        )
        if provider_envelope.get("status") == "FAILED":
            _raise_for_provider_failure("Exa search failed", provider_envelope, exit_code)
        return {"kind": "research_provider_envelope", **provider_envelope, "artifact": artifact}
```

Do not implement `crawl()` in T4. T7 implements and tests it after command tests define the exact CLI shape.

- [ ] **Step 4: Run tests**

Run:

```powershell
uv run pytest tests/connectors/research/test_client.py tests/connectors/research/test_exa.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```powershell
git add h2t_ops/connectors/research/client.py tests/connectors/research/test_client.py tests/connectors/research/test_exa.py
git commit -m "feat(research): wrap Exa results as provider artifacts"
```

---

## T5 - Fetch Provider Core

**Files:**
- Create/Modify: `h2t_ops/connectors/research/fetch.py`
- Create: `tests/connectors/research/test_fetch.py`
- Create: `tests/connectors/research/fixtures/fetch/*`

- [ ] **Step 1: Copy fetch fixtures**

Copy every file from:

```text
plugins/h2t-ops/skills/research/tests/fixtures/fetch/
```

to:

```text
tests/connectors/research/fixtures/fetch/
```

Expected files:

```text
alltd_403_body.html
js_shell.html
login_wall.html
non_ascii_article.html
paywall.html
public_article_jina.md
public_article.html
redirect_to_login.html
short_body.html
```

- [ ] **Step 2: Create fetch provider tests by porting legacy tests**

Create `tests/connectors/research/test_fetch.py` by copying provider-level tests from `plugins/h2t-ops/skills/research/tests/test_fetch_url.py` and changing imports from `fetch_url` to `h2t_ops.connectors.research.fetch`.

Required provider test groups:

| Legacy test area | Required tests in `test_fetch.py` |
|---|---|
| envelope + exceptions | `test_build_fetch_envelope_minimal_failed`, `test_build_fetch_envelope_ok_with_attempts_sums_latency`, `test_provider_exceptions_have_required_attrs`, `test_provider_result_dataclass_fields` |
| inline extraction | `test_inline_extract_public_article`, `test_inline_baseline_works_without_trafilatura`, `test_unicode_article_extracts_safely` |
| direct provider | `test_direct_provider_happy_path_extracts_article`, `test_direct_provider_4xx_raises_permanent`, `test_direct_provider_5xx_raises_transient`, `test_direct_provider_429_raises_transient`, `test_direct_provider_urlerror_raises_transient`, `test_direct_provider_401_with_www_authenticate_is_gated`, `test_direct_provider_403_without_auth_header_is_permanent_not_gated`, `test_direct_provider_final_url_after_redirect` |
| classifiers | `test_detect_js_shell_true_for_spa_skeleton`, `test_detect_login_wall_true_for_login_form`, `test_detect_paywall_true_for_dom_token`, `test_classify_content_type_article`, `test_classify_content_type_short_body`, `test_classify_content_type_js_shell`, `test_classify_content_type_gated_login`, `test_classify_content_type_gated_paid`, `test_detect_homepage_redirect_true_for_alltd_pattern` |
| Jina provider | `test_jina_provider_happy_path_extracts_markdown`, `test_jina_provider_passes_authorization_when_key_set`, `test_jina_provider_5xx_transient`, `test_jina_provider_4xx_permanent`, `test_jina_provider_urlerror_transient` |
| stubs/config | `test_stub_providers_not_configured_and_fetch_raises`, `test_load_config_returns_defaults_when_file_missing`, `test_load_config_overrides_with_user_file` |

Use this import header:

```python
from h2t_ops.connectors.research import fetch
```

- [ ] **Step 3: Verify exact fetch test list is present**

Run:

```powershell
Select-String -Path tests/connectors/research/test_fetch.py -Pattern "test_direct_provider_happy_path_extracts_article|test_jina_provider_happy_path_extracts_markdown|test_ladder_direct_403_falls_through_to_jina|test_ladder_cumulative_timeout_skips_remaining"
```

Expected: all four sentinel test names appear. If any sentinel is missing, stop and finish the port before running pytest.

- [ ] **Step 4: Run tests and verify they fail**

Run:

```powershell
uv run pytest tests/connectors/research/test_fetch.py -q
```

Expected: FAIL because `h2t_ops.connectors.research.fetch` does not exist.

- [ ] **Step 5: Create fetch provider module by mechanical port**

Create `h2t_ops/connectors/research/fetch.py` by porting these exact symbols from `plugins/h2t-ops/skills/research/scripts/fetch_url.py`:

```text
__version__
DEFAULT_USER_AGENT
ENVELOPE_VERSION
FETCH_ENVELOPE_VERSION
ProviderTransientError
ProviderPermanentError
ProviderHardGate
ProviderNotConfigured
ProviderResult
_InlineExtractor
_tokens_to_markdown_and_text
_inline_extract
_reset_trafilatura_warned_for_tests
_extract_with_optional_uplift
_site_from_url
DirectProvider
_detect_encoding
_detect_js_shell
LOGIN_DOM_TOKENS
_LOGIN_FORM_ACTION_RE
_META_REFRESH_LOGIN_RE
_detect_login_wall
PAYWALL_DOM_TOKENS
KNOWN_PAYWALLED_DOMAINS
_detect_paywall
_detect_homepage_redirect
_classify_content
JINA_ENDPOINT_DEFAULT
JinaProvider
_jina_extract_title
_jina_extract_url_source
_jina_extract_body
_StubProvider
PlaywrightProvider
Crawl4AIProvider
FirecrawlProvider
BrowserlessProvider
DEFAULT_CONFIG
_deep_merge
load_config
LADDER_CLASSES
CUMULATIVE_TIMEOUT_WARN
_attempt_record
build_fetch_envelope
```

Do not port these CLI/output symbols in T5:

```text
_build_parser
_die_args
_force_utf8_streams
main
_slug_from_url
_output_paths
_write_sources_json
_run_fetch
_write_partial_md
_emit_stdout_and_exit
_render_markdown_summary
_emit_stderr_for_failed
_run_preflight
```

- [ ] **Step 6: Run provider tests**

Run:

```powershell
uv run pytest tests/connectors/research/test_fetch.py -q
```

Expected: provider-level tests pass. Ladder/facade/CLI tests may not exist yet.

- [ ] **Step 7: Commit**

Run:

```powershell
git add h2t_ops/connectors/research/fetch.py tests/connectors/research/test_fetch.py tests/connectors/research/fixtures/fetch
git commit -m "feat(research): add fetch provider core"
```

---

## T6 - Fetch Ladder Facade And Artifact Mapping

**Files:**
- Modify: `h2t_ops/connectors/research/fetch.py`
- Modify: `h2t_ops/connectors/research/client.py`
- Modify: `tests/connectors/research/test_fetch.py`
- Modify: `tests/connectors/research/test_client.py`

- [ ] **Step 1: Add fetch ladder tests**

Append these ladder tests to `tests/connectors/research/test_fetch.py` by porting the matching legacy behavior:

```text
test_ladder_single_provider_ok_returns_envelope
test_ladder_direct_403_falls_through_to_jina
test_ladder_login_wall_short_circuits_does_not_call_jina
test_ladder_paywall_short_circuits
test_ladder_all_active_providers_fail_returns_failed
test_ladder_degraded_picks_best_candidate_by_body_chars
test_ladder_explicit_direct_does_not_fallback_to_jina
test_ladder_stubs_skipped_with_reason_in_auto
test_ladder_jina_disabled_skipped_in_config
test_ladder_cumulative_timeout_skips_remaining
test_ladder_alltd_collapse_falls_through_to_jina_then_degraded
test_ladder_alltd_collapse_recovers_via_jina
```

Use `fetch.fetch_via_ladder(...)` as the public function under test.

- [ ] **Step 2: Add ResearchClient fetch tests**

Append to `tests/connectors/research/test_client.py`:

```python
def test_research_client_fetch_ok_writes_artifact(tmp_path):
    provider_env = {
        "status": "OK",
        "url": "https://example.com",
        "final_url": "https://example.com",
        "provider_used": "direct",
        "content_type": "article",
        "content_gate": "none",
        "title": "Example",
        "body_markdown": "Body",
        "body_text": "Body",
        "body_chars": 4,
        "links": [],
        "metadata": {"raw_html_path": None},
        "telemetry": {
            "attempts": [{"provider": "direct", "http": 200, "latency_ms": 10, "error": None}],
            "reason_for_degraded": None,
            "reason_for_failed": None,
            "total_latency_ms": 10,
            "providers_skipped": [],
            "providers_skipped_reason": {},
        },
        "meta": {"primary_engine": "fetch_ladder", "envelope_version": "1"},
    }
    with patch("h2t_ops.connectors.research.fetch.fetch_via_ladder", return_value=provider_env):
        result = client.ResearchClient(output_dir=tmp_path).fetch_url("https://example.com")
    assert result["status"] == "OK"
    assert result["artifact"]["telemetry"]["providers"] == ["direct"]
    assert result["artifact"]["telemetry"]["cost_basis"] == "zero"


def test_research_client_fetch_gated_maps_to_autherror(tmp_path):
    from h2t_ops.core.errors import AuthError

    provider_env = {
        "status": "FAILED",
        "url": "https://example.com/private",
        "final_url": "https://example.com/login",
        "provider_used": "none",
        "content_type": "gated",
        "content_gate": "login_required",
        "title": None,
        "body_markdown": "",
        "body_text": "",
        "body_chars": 0,
        "links": [],
        "metadata": {"raw_html_path": None},
        "telemetry": {
            "attempts": [{"provider": "direct", "http": 401, "latency_ms": 10, "error": "fetch_gated_login_required"}],
            "reason_for_degraded": None,
            "reason_for_failed": "content_gate_login_required",
            "total_latency_ms": 10,
            "providers_skipped": [],
            "providers_skipped_reason": {},
        },
        "meta": {"primary_engine": "fetch_ladder", "envelope_version": "1"},
    }
    with patch("h2t_ops.connectors.research.fetch.fetch_via_ladder", return_value=provider_env):
        with pytest.raises(AuthError) as exc:
            client.ResearchClient(output_dir=tmp_path).fetch_url("https://example.com/private")
    assert exc.value.details["provider_envelope"]["content_gate"] == "login_required"
```

- [ ] **Step 3: Run tests and verify they fail**

Run:

```powershell
uv run pytest tests/connectors/research/test_fetch.py tests/connectors/research/test_client.py -q
```

Expected: FAIL because `fetch_via_ladder()` and `ResearchClient.fetch_url()` are missing or incomplete.

- [ ] **Step 4: Port ladder function**

Add `fetch_via_ladder()` to `h2t_ops/connectors/research/fetch.py` by mechanically porting it from `plugins/h2t-ops/skills/research/scripts/fetch_url.py`.

Keep behavior unchanged:

```text
ProviderHardGate -> FAILED and stop
ProviderPermanentError -> record attempt and continue
ProviderTransientError -> record attempt and continue
ProviderNotConfigured -> skip
redirect_collapsed -> DEGRADED candidate and continue
article -> OK
all degraded -> best DEGRADED candidate
all failed -> FAILED
```

- [ ] **Step 5: Implement ResearchClient.fetch_url()**

Modify `h2t_ops/connectors/research/client.py`.

Add import:

```python
from h2t_ops.core.errors import AuthError
```

Add method:

```python
    def fetch_url(
        self,
        url: str,
        *,
        provider: str = "auto",
        keep_raw: bool = False,
        timeout_ms: int = 15000,
        min_body_chars: int = 200,
        user_agent: str | None = None,
        project: str = "default",
        config_path: str | None = None,
    ) -> dict[str, Any]:
        from h2t_ops.connectors.research import fetch

        config = fetch.load_config(config_path)
        config["ladder"]["per_provider_timeout_ms"] = timeout_ms
        config["ladder"]["min_body_chars"] = min_body_chars
        provider_envelope = fetch.fetch_via_ladder(
            url=url,
            provider_choice=provider,
            config=config,
            user_agent=user_agent or fetch.DEFAULT_USER_AGENT,
            keep_raw=keep_raw,
            min_body_chars=min_body_chars,
            output_paths=artifact_paths(
                output_dir=self.output_dir,
                project=project,
                slug_source=url,
                kind="fetch",
            ),
        )
        attempts = provider_envelope.get("telemetry", {}).get("attempts", [])
        providers = sorted({
            attempt.get("provider") or attempt.get("engine")
            for attempt in attempts
            if attempt.get("provider") or attempt.get("engine")
        })
        provider_used = provider_envelope.get("provider_used")
        if provider_used and provider_used not in providers:
            providers.append(provider_used)
        telemetry = {
            "calls": len(attempts),
            "providers": providers,
            "estimated_cost_usd": 0.0 if provider_envelope.get("provider_used") == "direct" else None,
            "cost_basis": "zero" if provider_envelope.get("provider_used") == "direct" else "unknown",
        }
        artifact = self._write_provider_artifacts(
            kind="fetch",
            slug_source=url,
            project=project,
            provider_envelope=provider_envelope,
            telemetry=telemetry,
            ledger_provider=provider_envelope.get("provider_used") or provider,
            ledger_endpoint="fetch_ladder",
            ledger_mode=provider,
            raw_html_path=provider_envelope.get("metadata", {}).get("raw_html_path"),
        )
        result = {"kind": "research_fetch_envelope", **provider_envelope, "artifact": artifact}
        if provider_envelope.get("status") != "FAILED":
            return result
        details = sanitize_details({"provider_envelope": provider_envelope})
        gate = provider_envelope.get("content_gate")
        if gate in {"login_required", "paid"}:
            raise AuthError(f"Fetch gated: {gate}", details=details)
        last_attempts = provider_envelope.get("telemetry", {}).get("attempts", [])
        last_error = last_attempts[-1].get("error") if last_attempts else None
        if last_error == "fetch_network_timeout":
            raise NetworkError("Fetch failed: network timeout", details=details)
        raise ProviderError("Fetch failed", details=details)
```

The `fetch.fetch_via_ladder()` signature must match the legacy public function exactly: keyword-only `url`, `provider_choice`, `config`, `user_agent`, `keep_raw`, `min_body_chars`, and `output_paths`.

- [ ] **Step 6: Run tests**

Run:

```powershell
uv run pytest tests/connectors/research/test_fetch.py tests/connectors/research/test_client.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

Run:

```powershell
git add h2t_ops/connectors/research/fetch.py h2t_ops/connectors/research/client.py tests/connectors/research/test_fetch.py tests/connectors/research/test_client.py
git commit -m "feat(research): add fetch ladder facade"
```

---

## T7 - Connector Registration And Commands

**Files:**
- Create: `h2t_ops/connectors/research/__init__.py`
- Create: `h2t_ops/connectors/research/commands.py`
- Modify: `h2t_ops/cli.py`
- Test: `tests/connectors/research/test_commands.py`
- Modify: `tests/connectors/research/test_client.py`

- [ ] **Step 1: Add command tests**

Create `tests/connectors/research/test_commands.py` with:

```python
from __future__ import annotations

import argparse
import json
from unittest.mock import patch

import pytest

from h2t_ops.cli import build_parser, dispatch
from h2t_ops.connectors.research import commands
from h2t_ops.core.errors import ProviderError


def _parse(argv: list[str]) -> argparse.Namespace:
    parser = build_parser()
    return parser.parse_args(argv)


def test_research_registered_in_parser():
    ns = _parse(["research", "search", "--query", "x", "--json"])
    assert ns.connector == "research"
    assert ns.research_cmd == "search"
    assert ns.query == "x"
    assert ns.as_json is True


def test_search_dispatch_calls_client():
    ns = _parse(["research", "search", "--query", "x", "--mode", "fast", "--json"])
    with patch("h2t_ops.connectors.research.client.ResearchClient.search", return_value={"status": "OK"}) as m:
        assert commands.run(ns) == {"status": "OK"}
    assert m.call_args.kwargs["query"] == "x"
    assert m.call_args.kwargs["mode"] == "fast"


def test_fetch_dispatch_calls_client():
    ns = _parse(["research", "fetch", "--url", "https://example.com", "--provider", "direct", "--json"])
    with patch("h2t_ops.connectors.research.client.ResearchClient.fetch_url", return_value={"status": "OK"}) as m:
        assert commands.run(ns) == {"status": "OK"}
    assert m.call_args.args == ("https://example.com",)
    assert m.call_args.kwargs["provider"] == "direct"


def test_preflight_dispatch_calls_client():
    ns = _parse(["research", "preflight", "--json"])
    with patch("h2t_ops.connectors.research.client.ResearchClient.preflight", return_value={"status": "OK"}) as m:
        assert commands.run(ns) == {"status": "OK"}
    m.assert_called_once_with()


def test_crawl_dispatch_calls_client():
    ns = _parse(["research", "crawl", "--url", "https://example.com", "--json"])
    with patch("h2t_ops.connectors.research.client.ResearchClient.crawl", return_value={"status": "OK"}) as m:
        assert commands.run(ns) == {"status": "OK"}
    assert m.call_args.args == ("https://example.com",)


def test_json_failed_preserves_provider_envelope(capsys):
    with patch(
        "h2t_ops.connectors.research.client.ResearchClient.search",
        side_effect=ProviderError(
            "Exa failed",
            details={"provider_envelope": {"status": "FAILED", "primary_engine": "exa"}},
        ),
    ):
        code = dispatch(["research", "search", "--query", "x", "--json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.err)
    assert code == 1
    assert payload["error"]["details"]["provider_envelope"]["status"] == "FAILED"


def test_help_does_not_instantiate_client(monkeypatch):
    def boom(*args, **kwargs):
        raise AssertionError("ResearchClient should not be instantiated for help")

    monkeypatch.setattr("h2t_ops.connectors.research.client.ResearchClient", boom)
    code = dispatch(["research", "--help"])
    assert code == 0
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```powershell
uv run pytest tests/connectors/research/test_commands.py -q
```

Expected: FAIL because connector is not registered and `commands.py` does not exist.

- [ ] **Step 3: Create ConnectorSpec**

Create `h2t_ops/connectors/research/__init__.py`:

```python
"""Research connector registration."""
from h2t_ops.core.registry import ConnectorSpec
from .commands import register

CONNECTOR = ConnectorSpec(
    name="research",
    help="Run Exa research and URL fetch ladder",
    client="h2t_ops.connectors.research.client:ResearchClient",
    register=register,
)
```

- [ ] **Step 4: Create commands module**

Create `h2t_ops/connectors/research/commands.py`:

```python
"""Research CLI adapter. argparse only at module scope; client imported in run()."""
from __future__ import annotations

from typing import Any

PROVIDER = "research"


def register(subparsers: Any) -> None:
    p = subparsers.add_parser("research", help="Run Exa research and URL fetch ladder")
    cmds = p.add_subparsers(dest="research_cmd", required=True)

    def add_fmt(sp: Any) -> None:
        sp.add_argument("--json", dest="as_json", action="store_true", help="raw machine-readable envelope")
        sp.add_argument("--format", dest="fmt", choices=["human", "md"], default="human")

    preflight = cmds.add_parser("preflight", help="Check research provider configuration")
    add_fmt(preflight)

    search = cmds.add_parser("search", help="Run Exa /search")
    search.add_argument("--query", required=True)
    search.add_argument("--mode", choices=["fast", "generic", "news", "academic", "competitor", "people", "deep"], default="generic")
    search.add_argument("--depth", choices=["shallow", "standard", "deep"], default="standard")
    search.add_argument("--num-results", type=int, dest="num_results")
    search.add_argument("--additional-queries")
    search.add_argument("--start-date", dest="start_date")
    search.add_argument("--end-date", dest="end_date")
    search.add_argument("--include-domains", dest="include_domains")
    search.add_argument("--exclude-domains", dest="exclude_domains")
    search.add_argument("--include-text", dest="include_text")
    search.add_argument("--exclude-text", dest="exclude_text")
    search.add_argument("--country")
    search.add_argument("--full-text", action="store_true", dest="full_text")
    search.add_argument("--output-dir", dest="output_dir")
    search.add_argument("--project", default="default")
    search.add_argument("--no-retry", action="store_true", dest="no_retry")
    add_fmt(search)

    crawl = cmds.add_parser("crawl", help="Run Exa /contents for one URL")
    crawl.add_argument("--url", required=True)
    crawl.add_argument("--output-dir", dest="output_dir")
    crawl.add_argument("--project", default="default")
    add_fmt(crawl)

    fetch = cmds.add_parser("fetch", help="Fetch one URL through provider ladder")
    fetch.add_argument("--url", required=True)
    fetch.add_argument("--provider", choices=["auto", "direct", "jina", "playwright", "crawl4ai", "firecrawl", "browserless"], default="auto")
    fetch.add_argument("--keep-raw", action="store_true", dest="keep_raw")
    fetch.add_argument("--timeout-ms", type=int, default=15000, dest="timeout_ms")
    fetch.add_argument("--min-body-chars", type=int, default=200, dest="min_body_chars")
    fetch.add_argument("--user-agent", dest="user_agent")
    fetch.add_argument("--output-dir", dest="output_dir")
    fetch.add_argument("--project", default="default")
    fetch.add_argument("--config", dest="config_path")
    add_fmt(fetch)

    p.set_defaults(_handler=run)


def _split_csv(raw: str | None) -> list[str] | None:
    return [item.strip() for item in raw.split(",") if item.strip()] if raw else None


def run(args: Any) -> Any:
    from pathlib import Path

    from h2t_ops.connectors.research.client import ResearchClient
    from h2t_ops.core.errors import UsageError

    client = ResearchClient(output_dir=Path(args.output_dir) if getattr(args, "output_dir", None) else None)
    cmd = args.research_cmd
    if cmd == "preflight":
        return client.preflight()
    if cmd == "search":
        return client.search(
            query=args.query,
            mode=args.mode,
            depth=args.depth,
            num_results=args.num_results,
            additional_queries=_split_csv(args.additional_queries),
            start_date=args.start_date,
            end_date=args.end_date,
            include_domains=_split_csv(args.include_domains),
            exclude_domains=_split_csv(args.exclude_domains),
            include_text=_split_csv(args.include_text),
            exclude_text=_split_csv(args.exclude_text),
            country=args.country,
            full_text=args.full_text,
            project=args.project,
            no_retry=args.no_retry,
        )
    if cmd == "crawl":
        return client.crawl(args.url, project=args.project)
    if cmd == "fetch":
        return client.fetch_url(
            args.url,
            provider=args.provider,
            keep_raw=args.keep_raw,
            timeout_ms=args.timeout_ms,
            min_body_chars=args.min_body_chars,
            user_agent=args.user_agent,
            project=args.project,
            config_path=args.config_path,
        )
    raise UsageError(f"unknown research subcommand: {cmd}")
```

- [ ] **Step 5: Add client preflight and crawl stubs with real behavior**

Modify `ResearchClient` in `h2t_ops/connectors/research/client.py`:

```python
    def preflight(self) -> dict[str, Any]:
        from h2t_ops.connectors.research import exa

        exa.preflight(resolve_secret("EXA_API_KEY"))
        return {"status": "OK", "provider": "exa"}

    def crawl(self, url: str, *, project: str = "default") -> dict[str, Any]:
        from h2t_ops.connectors.research import exa

        api_key = resolve_secret("EXA_API_KEY")
        body = {"urls": [url], "text": {"maxCharacters": 15000}}
        try:
            status, data, latency_ms = exa.call_exa("/contents", body, api_key)
        except exa.ExaPermanentError as exc:
            raise ProviderError(
                f"Exa crawl failed: http {exc.http_status}",
                details=sanitize_details({"provider_error": exc.body}),
            ) from exc
        except exa.ExaTransientError as exc:
            details = sanitize_details({"http_status": exc.http_status, "latency_ms": exc.latency_ms})
            if exc.http_status is None:
                raise NetworkError(f"Exa crawl network failed: {exc}", details=details) from exc
            raise ProviderError(f"Exa crawl failed: http {exc.http_status}", details=details) from exc
        except exa.ExaMalformedResponseError as exc:
            raise ProviderError(f"Exa crawl malformed response: {exc}") from exc
        results = data.get("results", [])
        provider_envelope = exa.build_envelope(
            status="OK" if results else "DEGRADED",
            results=results,
            attempts=[{"engine": "exa", "endpoint": "/contents", "http": status, "latency_ms": latency_ms, "error": None if results else "exa_empty_results"}],
            reason_for_fallback=None if results else "exa_empty_results",
            total_latency_ms=latency_ms,
            total_cost_usd=float(data.get("costDollars", {}).get("total", 0.0)),
            meta={"query": url, "mode": "crawl", "num_results_requested": 1, "num_results_returned": len(results)},
        )
        telemetry = {
            "calls": 1,
            "providers": ["exa"],
            "estimated_cost_usd": provider_envelope.get("telemetry", {}).get("total_cost_usd"),
            "cost_basis": "provider_reported",
        }
        artifact = self._write_provider_artifacts(
            kind="crawl",
            slug_source=url,
            project=project,
            provider_envelope=provider_envelope,
            telemetry=telemetry,
            ledger_provider="exa",
            ledger_endpoint="/contents",
            ledger_mode="crawl",
        )
        return {"kind": "research_provider_envelope", **provider_envelope, "artifact": artifact}
```

- [ ] **Step 6: Add `"research"` to `_MIGRATED`**

Modify `h2t_ops/cli.py`:

```python
_MIGRATED = {"notion", "gmail", "calendar", "drive", "meetgeek", "telegram", "research"}
```

- [ ] **Step 7: Run command tests**

Run:

```powershell
uv run pytest tests/connectors/research/test_commands.py tests/connectors/research/test_client.py -q
```

Expected: PASS.

- [ ] **Step 8: Run registry smoke**

Run:

```powershell
uv run h2t-ops connectors
uv run h2t-ops research --help
uv run h2t-ops research search --help
uv run h2t-ops research fetch --help
uv run h2t-ops dev check lazy-registry
```

Expected:

```text
research
OK lazy-registry
```

- [ ] **Step 9: Commit**

Run:

```powershell
git add h2t_ops/connectors/research/__init__.py h2t_ops/connectors/research/commands.py h2t_ops/connectors/research/client.py h2t_ops/cli.py tests/connectors/research/test_commands.py tests/connectors/research/test_client.py
git commit -m "feat(research): add connector commands and registry entry"
```

---

## T8 - Skill References, Templates, And Thin SKILL.md

**Files:**
- Modify: `plugins/h2t-ops/skills/research/SKILL.md`
- Create: `plugins/h2t-ops/skills/research/references/research-artifact-contract.md`
- Create: `plugins/h2t-ops/skills/research/references/traceability-policy.md`
- Create: `plugins/h2t-ops/skills/research/references/telemetry-policy.md`
- Create: `plugins/h2t-ops/skills/research/references/templates/technical-decision.md`
- Create: `plugins/h2t-ops/skills/research/references/templates/api-audit.md`
- Create: `plugins/h2t-ops/skills/research/references/templates/market-research.md`
- Create: `plugins/h2t-ops/skills/research/references/templates/company.md`
- Create: `plugins/h2t-ops/skills/research/references/templates/academic.md`
- Create: `plugins/h2t-ops/skills/research/references/templates/news-monitoring.md`
- Create: `plugins/h2t-ops/skills/research/references/templates/person.md`

- [ ] **Step 1: Create artifact contract reference**

Create `plugins/h2t-ops/skills/research/references/research-artifact-contract.md`:

```markdown
# Research Artifact Contract

Research output is evidence, not canonical knowledge.

## Provider Artifact: `research_artifact/v1`

Written or returned by `h2t-ops research`.

Required fields:

- `kind: "research_artifact"`
- `version: "v1"`
- `artifact_id`
- `created_at`
- `tool`
- `provider_status: "OK" | "DEGRADED" | "FAILED"`
- `artifact_refs.sources_json`
- `artifact_refs.artifact_json`
- `telemetry.calls`
- `telemetry.providers`
- `telemetry.estimated_cost_usd`
- `telemetry.cost_basis`

## Registration Manifest: `research_artifact_registration/v1`

Filled by the agent after final synthesis while the work context is fresh.

Required sections:

- `artifact`
- `request`
- `work_context`
- `traceability`
- `pos_intake`

Default POS promotion:

```json
{"promotion_status": "evidence_only"}
```

POS may index and link this artifact. POS owns dedupe, lifecycle, and promotion.
```

- [ ] **Step 2: Create traceability policy**

Create `plugins/h2t-ops/skills/research/references/traceability-policy.md`:

```markdown
# Research Traceability Policy

Every Key Finding must include:

1. A source URL.
2. A verbatim quote from the source or provider highlight.
3. A confidence label: `high`, `medium`, or `low`.
4. A one-sentence confidence reason.

No URL + quote means the claim belongs in Limitations, not Key Findings.

Provider result, provider summary, and agent synthesis are evidence, not truth.
The POS/coordinator decides whether evidence becomes KB, journal, accepted task,
decision, or follow-up.
```

- [ ] **Step 3: Create telemetry policy**

Create `plugins/h2t-ops/skills/research/references/telemetry-policy.md`:

```markdown
# Research Telemetry Policy

Exa is paid. Every research run must preserve usage telemetry.

Required telemetry fields:

- provider
- endpoint
- mode or fetch provider
- template id when selected
- status
- latency
- result count
- estimated cost
- cost basis
- artifact id
- repo/issue/session when the agent knows them

Allowed `cost_basis` values:

- `provider_reported`
- `estimated`
- `zero`
- `unknown`

Default local ledger:

```text
~/.h2t/research/telemetry.jsonl
```

The ledger is best-effort. A failed ledger append must not make research fail.
```

- [ ] **Step 4: Create templates**

For each file below, create the shown content.

`plugins/h2t-ops/skills/research/references/templates/technical-decision.md`:

```markdown
# Template: technical-decision/v1

Use for engineering decisions, connector migrations, API choice, or architecture tradeoffs.

Required registration fields:

- `request.original_user_request`
- `request.normalized_query`
- `request.domain`
- `request.purpose: "decision_support"`
- `work_context.repo`
- `work_context.cwd`
- `work_context.issue`
- `traceability.has_source_urls: true`
- `traceability.has_verbatim_quotes: true`
- `traceability.limitations_recorded: true`

POS defaults:

- `promotion_status: evidence_only`
- `suggested_collections: ["research", "engineering"]`

Validation rules:

- `min_sources: 3`
- `quotes_required: true`
- `limitations_required: true`
- `confidence_required: true`
```

`plugins/h2t-ops/skills/research/references/templates/api-audit.md`:

```markdown
# Template: api-audit/v1

Use for provider API coverage and legacy parity audits.

Required sections:

- Provider capabilities checked
- Existing local implementation
- Gaps
- Side effects
- Auth/secrets
- Tests
- Follow-up issues

Validation rules:

- `min_sources: 2`
- `quotes_required: true`
- `gap_table_required: true`
- `side_effects_required: true`
```

`plugins/h2t-ops/skills/research/references/templates/market-research.md`:

```markdown
# Template: market-research/v1

Use for market, product, competitor, and positioning research.

Validation rules:

- `min_sources: 5`
- `quotes_required: true`
- `date_range_required: true`
- `limitations_required: true`

POS defaults:

- `promotion_status: evidence_only`
- `suggested_collections: ["research", "market"]`
```

`plugins/h2t-ops/skills/research/references/templates/company.md`:

```markdown
# Template: company/v1

Use for company intel and competitor scan.

Recommended mode: `competitor` or `news`.

Validation rules:

- `min_sources: 4`
- `quotes_required: true`
- `company_identity_required: true`
- `freshness_note_required: true`
```

`plugins/h2t-ops/skills/research/references/templates/academic.md`:

```markdown
# Template: academic/v1

Use for papers, research claims, methods, and scientific context.

Recommended mode: `academic`.

Validation rules:

- `min_sources: 3`
- `quotes_required: true`
- `publication_metadata_required: true`
- `limitations_required: true`
```

`plugins/h2t-ops/skills/research/references/templates/news-monitoring.md`:

```markdown
# Template: news-monitoring/v1

Use for recent developments and dated press coverage.

Recommended mode: `news`.

Validation rules:

- `min_sources: 3`
- `quotes_required: true`
- `date_range_required: true`
- `freshness_note_required: true`
```

`plugins/h2t-ops/skills/research/references/templates/person.md`:

```markdown
# Template: person/v1

Use for people research and public professional background.

Recommended mode: `people`.

Validation rules:

- `min_sources: 3`
- `quotes_required: true`
- `identity_disambiguation_required: true`
- `privacy_note_required: true`
```

- [ ] **Step 5: Rewrite SKILL.md as thin guide**

Replace `plugins/h2t-ops/skills/research/SKILL.md` body with a concise guide that keeps the existing frontmatter and includes:

```markdown
# h2t-ops:research

Use `h2t-ops research` for provider-backed web research via Exa and the URL fetch ladder.

## Boundary

Research artifacts are evidence, not canonical knowledge. This skill may create
traceable research artifacts under `~/.h2t/research/`; POS owns indexing, dedupe,
linking, and promotion into KB/journal/tasks/decisions.

## Commands

```bash
h2t-ops research preflight --json
h2t-ops research search --query "..." --mode generic --num-results 10 --json
h2t-ops research crawl --url "https://..." --json
h2t-ops research fetch --url "https://..." --provider auto --json
```

## References

Load only what the request needs:

- `references/research-artifact-contract.md`
- `references/traceability-policy.md`
- `references/telemetry-policy.md`
- `references/templates/technical-decision.md`
- `references/templates/api-audit.md`
- `references/templates/market-research.md`
- `references/templates/company.md`
- `references/templates/academic.md`
- `references/templates/news-monitoring.md`
- `references/templates/person.md`

## Required Workflow

1. Pick a template if the request has a clear domain.
2. Run the relevant `h2t-ops research ...` command.
3. Inspect `result.status`; `exit 0` can still mean `DEGRADED`.
4. Write final findings only with source URL + quote + confidence.
5. Preserve artifact paths and telemetry.
6. Fill `research_artifact_registration/v1` context while the session context is fresh.
7. If POS intake exists, hand it the registration manifest; otherwise leave the manifest ready.

## Antipatterns

- No silent WebSearch/WebFetch fallback.
- No paywall/login bypass.
- No POS DB/vault/lake/context writes.
- No finding without URL + quote + confidence.
- No automatic KB promotion.
```

Keep the original frontmatter `name`, `description`, `compatibility`, and `metadata`, unless the implementation has bumped the skill version.

- [ ] **Step 6: Grep for obsolete cache-discovery instructions**

Run:

```powershell
Select-String -Path plugins/h2t-ops/skills/research/SKILL.md -Pattern "plugins/cache|CLAUDE_PLUGIN_ROOT|H2T_PLUGIN_ROOT|_EXA_PY|_FETCH_PY|EXA_CLI|FETCH_CLI"
```

Expected: no matches.

- [ ] **Step 7: Commit**

Run:

```powershell
git add plugins/h2t-ops/skills/research/SKILL.md plugins/h2t-ops/skills/research/references
git commit -m "docs(research): delegate skill to connector and artifact templates"
```

---

## T9 - Final Verification And Closure Evidence

**Files:**
- No commits

- [ ] **Step 1: Full test run**

Run:

```powershell
uv run pytest tests/core tests/connectors -q
```

Expected: all tests pass.

- [ ] **Step 2: Legacy research tests still pass or are intentionally superseded**

Run:

```powershell
uv run pytest plugins/h2t-ops/skills/research/tests -q
```

Expected: PASS, or document any intentional supersession in closure evidence. Do not delete legacy tests in #136.

- [ ] **Step 3: Lazy registry and help**

Run:

```powershell
uv run h2t-ops dev check lazy-registry
uv run h2t-ops connectors
uv run h2t-ops research --help
uv run h2t-ops research search --help
uv run h2t-ops research fetch --help
```

Expected:

```text
OK lazy-registry
research
```

- [ ] **Step 4: Boundary audit**

Run:

```powershell
Select-String -Path h2t_ops/connectors/research/*.py -Pattern "vault|lake|pos\\.db|dor\\.db|context/|WebSearch|WebFetch|plugins/cache|CLAUDE_PLUGIN_ROOT|H2T_PLUGIN_ROOT"
Select-String -Path h2t_ops/connectors/research/*.py -Pattern "\\.dor" | Where-Object { $_.Line -notmatch 'secrets' }
```

Expected: no matches.

- [ ] **Step 5: Token leak audit**

Run:

```powershell
Select-String -Path h2t_ops/connectors/research/*.py,tests/connectors/research/*.py,plugins/h2t-ops/skills/research/references/*.md,plugins/h2t-ops/skills/research/references/templates/*.md -Pattern "secret_[A-Za-z0-9]|EXA_API_KEY=[A-Za-z0-9]|JINA_API_KEY=[A-Za-z0-9]|Bearer [A-Za-z0-9]"
```

Expected: no matches.

- [ ] **Step 6: Installed/live read-only smoke**

Run after local install or from repo with `uv run`:

```powershell
uv run h2t-ops research preflight --json
uv run h2t-ops research search --query "h2t skills research connector" --mode fast --num-results 2 --json
uv run h2t-ops research fetch --url "https://example.com" --provider direct --json
```

Expected:

- `preflight`: exit 0 with JSON success envelope.
- `search`: exit 0 with `ok=true`, `provider=research`, `result.status` equal to `OK` or `DEGRADED`, and an artifact reference.
- `fetch`: exit 0 with `ok=true`, `provider=research`, `result.provider_used=direct`.

- [ ] **Step 7: Issue evidence block**

Prepare an issue comment for #136/#137 with:

```markdown
## Research connector closure evidence

- Tests: `uv run pytest tests/core tests/connectors -q` -> PASS
- Legacy research tests: `uv run pytest plugins/h2t-ops/skills/research/tests -q` -> PASS or documented supersession
- Lazy registry: `uv run h2t-ops dev check lazy-registry` -> OK
- CLI help: `research`, `research search`, `research fetch` -> exit 0
- Live smoke:
  - `research preflight --json` -> exit 0
  - `research search ... --json` -> exit 0, provider envelope preserved
  - `research fetch --url https://example.com --provider direct --json` -> exit 0
- Boundary:
  - no POS/vault/lake/context writes in connector
  - no WebSearch/WebFetch fallback
  - no plugin cache path discovery
- Traceability:
  - skill references define artifact contract, traceability policy, telemetry policy, templates
- Cost telemetry:
  - artifact telemetry includes `estimated_cost_usd` and `cost_basis`

Did not push / close without approval.
```

- [ ] **Step 8: Stop for approval**

Do not push. Do not close #136/#137. Report status and wait for explicit approval.

---

## Self-Review

### Spec Coverage

- Exa search/crawl parity: T3/T4/T7.
- Fetch ladder under `research fetch`: T5/T6/T7.
- Rich `OK | DEGRADED | FAILED` envelopes: T3/T4/T5/T6/T7.
- Failed JSON telemetry through `error.details`: T1/T4/T7.
- POS boundary: hard constraints + T9 boundary audit.
- `research_artifact/v1`: T2/T4/T6/T8.
- `research_artifact_registration/v1`: T8.
- Cost telemetry and `cost_basis`: T2/T4/T6/T8/T9.
- Lazy references/templates: T8.
- Template validation contract, not full validator: T8.
- Secrets fallback order: T2.
- Live smoke: T9.

### Placeholder Scan

The plan avoids placeholder markers and unchecked vague "handle edge cases" steps. Mechanical ports are bounded by exact source file paths and exact symbol/test lists.

### Type Consistency

Shared names used consistently:

- `ResearchClient`
- `resolve_secret`
- `sanitize_details`
- `artifact_paths`
- `build_research_artifact`
- `append_telemetry`
- `research_artifact`
- `research_artifact_registration`
- `cost_basis`
- `provider_envelope`
- `fetch_via_ladder`
