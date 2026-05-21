"""Tests for h2t_ops.connectors.research.client helper substrate."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

import pytest

from h2t_ops.core.errors import ConfigError
from h2t_ops.connectors.research import client


def _clear_secret_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "EXA_API_KEY",
        "JINA_API_KEY",
        "H2T_RESEARCH_TELEMETRY_DISABLE",
        "H2T_SECRETS_FILE",
    ):
        monkeypatch.delenv(name, raising=False)


def test_resolve_secret_env_wins(tmp_path, monkeypatch):
    _clear_secret_env(monkeypatch)
    secrets = tmp_path / "secrets.env"
    secrets.write_text("EXA_API_KEY=file-value\n", encoding="utf-8")
    monkeypatch.setenv("EXA_API_KEY", "env-value")
    monkeypatch.setenv("H2T_SECRETS_FILE", str(secrets))

    assert client.resolve_secret("EXA_API_KEY") == "env-value"


def test_resolve_secret_h2t_secrets_file(tmp_path, monkeypatch):
    _clear_secret_env(monkeypatch)
    secrets = tmp_path / "secrets.env"
    secrets.write_text(
        """
        # comment
        EXA_API_KEY="file-value"
        JINA_API_KEY='jina-value'
        """,
        encoding="utf-8",
    )
    monkeypatch.setenv("H2T_SECRETS_FILE", str(secrets))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    assert client.resolve_secret("EXA_API_KEY") == "file-value"
    assert client.resolve_secret("JINA_API_KEY") == "jina-value"


def test_resolve_secret_canonical_and_legacy_paths(tmp_path, monkeypatch):
    _clear_secret_env(monkeypatch)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    canonical = tmp_path / ".dor" / "secrets" / "secrets.env"
    legacy = tmp_path / ".dor" / "secrets.env"
    canonical.parent.mkdir(parents=True)
    canonical.write_text("EXA_API_KEY=canonical-value\n", encoding="utf-8")
    legacy.write_text("EXA_API_KEY=legacy-value\n", encoding="utf-8")

    assert client.resolve_secret("EXA_API_KEY") == "canonical-value"
    canonical.unlink()
    assert client.resolve_secret("EXA_API_KEY") == "legacy-value"


def test_resolve_secret_missing_raises_configerror(tmp_path, monkeypatch):
    _clear_secret_env(monkeypatch)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    with pytest.raises(ConfigError) as ei:
        client.resolve_secret("EXA_API_KEY")

    assert "EXA_API_KEY" in str(ei.value)
    assert "H2T_SECRETS_FILE" in (ei.value.hint or "")


def test_artifact_paths_are_under_output_dir(tmp_path):
    paths = client.artifact_paths(
        output_dir=tmp_path,
        project="H2T Ops",
        slug_source="Market Scan: TouchDesigner?",
        kind="brief",
    )

    assert tmp_path.is_dir()
    assert set(paths) == {"partial_md", "sources_json", "artifact_json", "raw_html"}
    for path in paths.values():
        assert path.is_relative_to(tmp_path)
        assert path.parent == tmp_path
    assert paths["sources_json"].name.startswith(
        "h2t-ops-market-scan-touchdesigner-brief-"
    )
    assert re.fullmatch(
        (
            r"h2t-ops-market-scan-touchdesigner-brief-"
            r"20\d\d-\d\d-\d\d-\d{6}-[0-9a-f]{8}\.sources\.json"
        ),
        paths["sources_json"].name,
    )
    assert paths["artifact_json"].name.endswith(".artifact.json")


def test_artifact_paths_slugify_kind_and_stay_flat(tmp_path):
    paths = client.artifact_paths(
        output_dir=tmp_path,
        project="Project",
        slug_source="Source",
        kind="x/../../escape",
    )

    for path in paths.values():
        assert path.parent == tmp_path
        assert path.is_relative_to(tmp_path)
        assert ".." not in path.name
        assert "/" not in path.name
        assert "\\" not in path.name
        assert "-x-escape-" in path.name


def test_artifact_paths_do_not_collide_for_same_args(tmp_path):
    first = client.artifact_paths(
        output_dir=tmp_path,
        project="Project",
        slug_source="Source",
        kind="brief",
    )
    second = client.artifact_paths(
        output_dir=tmp_path,
        project="Project",
        slug_source="Source",
        kind="brief",
    )

    assert first["artifact_json"] != second["artifact_json"]
    assert first["sources_json"] != second["sources_json"]


def test_sanitize_details_redacts_known_tokens():
    details = {
        "headers": {
            "Authorization": "Bearer exa-real-token",
            "x-api-key": "jina-real-token",
        },
        "api_key": "plain-api-key",
        "nested": [
            "EXA_API_KEY=exa-secret",
            "JINA_API_KEY='jina-secret'",
            "curl -H 'Authorization: Bearer bearer-secret' https://example.com",
            "value=secret_internal_token",
        ],
    }

    sanitized = client.sanitize_details(details)
    text = json.dumps(sanitized)

    assert "exa-real-token" not in text
    assert "jina-real-token" not in text
    assert "plain-api-key" not in text
    assert "exa-secret" not in text
    assert "jina-secret" not in text
    assert "bearer-secret" not in text
    assert "secret_internal_token" not in text
    assert "[REDACTED]" in text


@pytest.mark.parametrize(
    "details, leaked",
    [
        ({"Bearer leak-token": "ok"}, "leak-token"),
        ({"x-api-key: jina-real-token": "ok"}, "jina-real-token"),
        ({"api_key=plain-api-key": "ok"}, "plain-api-key"),
    ],
)
def test_sanitize_details_redacts_secrets_in_dict_keys(details, leaked):
    sanitized = client.sanitize_details(details)
    text = json.dumps(sanitized)

    assert leaked not in text
    assert json.loads(text) == {"[REDACTED_KEY]": "[REDACTED]"}


def test_write_research_artifact_json(tmp_path):
    paths = client.artifact_paths(
        output_dir=tmp_path,
        project="Project",
        slug_source="Query",
        kind="fast",
    )
    artifact = client.build_research_artifact(
        artifact_id="research_123",
        provider_status="OK",
        tool="research",
        artifact_refs={
            "sources_json": "sources.json",
            "partial_md": "partial.md",
            "artifact_json": "artifact.json",
            "raw_html": None,
        },
        telemetry={
            "calls": 1,
            "providers": ["exa"],
            "estimated_cost_usd": 0.012,
            "cost_basis": "provider_reported",
        },
    )

    client.write_json(paths["artifact_json"], artifact)
    loaded = json.loads(paths["artifact_json"].read_text(encoding="utf-8"))

    assert loaded["kind"] == "research_artifact"
    assert loaded["version"] == "v1"
    assert loaded["artifact_id"] == "research_123"
    assert loaded["provider_status"] == "OK"
    assert loaded["telemetry"]["cost_basis"] == "provider_reported"


def test_append_telemetry_best_effort(tmp_path, monkeypatch):
    _clear_secret_env(monkeypatch)
    ledger = tmp_path / "telemetry.jsonl"

    assert client.append_telemetry(ledger, {"event": "ok", "token": "secret"}) is True
    line = ledger.read_text(encoding="utf-8").strip()
    assert json.loads(line) == {"event": "ok", "[REDACTED_KEY]": "[REDACTED]"}

    monkeypatch.setenv("H2T_RESEARCH_TELEMETRY_DISABLE", "1")
    assert client.append_telemetry(ledger, {"event": "disabled"}) is False

    monkeypatch.delenv("H2T_RESEARCH_TELEMETRY_DISABLE", raising=False)
    assert client.append_telemetry(tmp_path, {"event": "fails"}) is False


def test_append_telemetry_coerces_non_json_values(tmp_path, monkeypatch):
    _clear_secret_env(monkeypatch)
    ledger = tmp_path / "telemetry.jsonl"
    now = datetime(2026, 5, 21, tzinfo=timezone.utc)

    assert client.append_telemetry(
        ledger,
        {"path": tmp_path / "artifact.json", "created_at": now},
    ) is True
    loaded = json.loads(ledger.read_text(encoding="utf-8"))

    assert loaded["path"] == str(tmp_path / "artifact.json")
    assert loaded["created_at"] == str(now)
