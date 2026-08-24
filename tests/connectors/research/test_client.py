"""Tests for h2t_ops.connectors.research.client helper substrate."""
from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from h2t_ops.connectors.research import client, store
from h2t_ops.core.errors import (
    AuthError,
    ConfigError,
    NetworkError,
    NotFoundError,
    ProviderError,
    UsageError,
)


def _clear_sensitive_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "EXA_API_KEY",
        "JINA_API_KEY",
        "H2T_RESEARCH_TELEMETRY_DISABLE",
        "H2T_SECRETS_FILE",
    ):
        monkeypatch.delenv(name, raising=False)


def test_resolve_key_env_wins(tmp_path, monkeypatch):
    _clear_sensitive_env(monkeypatch)
    secrets = tmp_path / "secrets.env"
    secrets.write_text("EXA_API_KEY" + "=file-value\n", encoding="utf-8")
    monkeypatch.setenv("EXA_API_KEY", "env-value")
    monkeypatch.setenv("H2T_SECRETS_FILE", str(secrets))

    assert client.resolve_secret("EXA_API_KEY") == "env-value"


def test_resolve_key_h2t_secrets_file(tmp_path, monkeypatch):
    _clear_sensitive_env(monkeypatch)
    secrets = tmp_path / "secrets.env"
    secrets.write_text(
        "\n"
        "        # comment\n"
        "        EXA_API_KEY" + '="file-value"\n'
        "        JINA_API_KEY" + "='jina-value'\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("H2T_SECRETS_FILE", str(secrets))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    assert client.resolve_secret("EXA_API_KEY") == "file-value"
    assert client.resolve_secret("JINA_API_KEY") == "jina-value"


def test_resolve_key_canonical_and_legacy_paths(tmp_path, monkeypatch):
    _clear_sensitive_env(monkeypatch)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    canonical = tmp_path / ".dor" / "secrets" / "secrets.env"
    legacy = tmp_path / ".dor" / "secrets.env"
    canonical.parent.mkdir(parents=True)
    canonical.write_text("EXA_API_KEY" + "=canonical-value\n", encoding="utf-8")
    legacy.write_text("EXA_API_KEY" + "=legacy-value\n", encoding="utf-8")

    assert client.resolve_secret("EXA_API_KEY") == "canonical-value"
    canonical.unlink()
    assert client.resolve_secret("EXA_API_KEY") == "legacy-value"


def test_resolve_key_missing_raises_configerror(tmp_path, monkeypatch):
    _clear_sensitive_env(monkeypatch)
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


def test_validate_public_http_url_allows_public_http_url():
    assert client.validate_public_http_url("https://example.com/page") == "https://example.com/page"
    assert client.validate_public_http_url("http://93.184.216.34/") == "http://93.184.216.34/"


@pytest.mark.parametrize(
    "url",
    [
        "file:///C:/Users/stani/.dor/secrets.env",
        "https://user:password@example.com/page",
        "https://localhost/private",
        "http://127.0.0.1:8080/",
        "http://10.0.0.5/",
        "http://192.168.1.10/",
        "http://intranet/",
        "/relative/path",
        "https://ex[ample.com/page",
    ],
)
def test_validate_public_http_url_blocks_local_or_private_targets(url):
    with pytest.raises(UsageError):
        client.validate_public_http_url(url)


def test_sanitize_details_removes_url_userinfo():
    sanitized = client.sanitize_details(
        {"url": "https://user:password@example.com/path?safe=value"}
    )
    text = json.dumps(sanitized)

    assert "user:password" not in text
    assert "https://example.com/path?safe=value" in text


def test_sanitize_details_redacts_known_tokens():
    details = {
        "headers": {
            "Authorization": "Bearer " + "exa-real-token",
            "x-api-key": "jina-real-token",
        },
        "api_key": "plain-api-key",
        "nested": [
            "EXA_API_KEY" + "=exa-secret",
            "JINA_API_KEY" + "='jina-secret'",
            "curl -H 'Authorization: " + "Bearer " + "bearer-secret' https://example.com",
            "value=" + "secret" + "_internal_token",
        ],
        "source_url": "https://example.com/?access_token=url-leak-token&safe=value",
    }

    sanitized = client.sanitize_details(details)
    text = json.dumps(sanitized)

    assert "exa-real-token" not in text
    assert "jina-real-token" not in text
    assert "plain-api-key" not in text
    assert "exa-secret" not in text
    assert "jina-secret" not in text
    assert "bearer-secret" not in text
    assert "secret" + "_internal_token" not in text
    assert "url-leak-token" not in text
    assert "safe=value" in text
    assert "[REDACTED]" in text


@pytest.mark.parametrize(
    "details, leaked",
    [
        ({"Bearer " + "leak-token": "ok"}, "leak-token"),
        ({"x-api-key: jina-real-token": "ok"}, "jina-real-token"),
        ({"api_key=plain-api-key": "ok"}, "plain-api-key"),
    ],
)
def test_sanitize_details_redacts_sensitive_dict_keys(details, leaked):
    sanitized = client.sanitize_details(details)
    text = json.dumps(sanitized)

    assert leaked not in text
    assert json.loads(text) == {"[REDACTED_KEY]": "[REDACTED]"}


def test_sanitize_details_survives_malformed_url_token():
    # Regression: Exa highlights carry markdown-link fragments like `[text](url)`.
    # The URL regex over-matches `https://](https://`, whose netloc holds an
    # unbalanced `]`, and urlsplit raised ValueError("Invalid IPv6 URL"),
    # crashing the whole artifact/telemetry write path.
    sanitized = client.sanitize_details(
        "see [x](https://a.com) and broken https://](https://b.com)"
    )
    assert isinstance(sanitized, str)
    assert "a.com" in sanitized


def test_sanitize_details_redacts_secret_in_malformed_url():
    # Even when the URL token is unparseable, a key=value secret must still redact.
    sanitized = client.sanitize_details(
        "frag https://](https://x.com/?api_key=" + "malformed-url-secret"
    )
    assert "malformed-url-secret" not in sanitized
    assert "[REDACTED]" in sanitized


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
    _clear_sensitive_env(monkeypatch)
    ledger = tmp_path / "telemetry.jsonl"

    assert client.append_telemetry(ledger, {"event": "ok", "token": "secret"}) is True
    line = ledger.read_text(encoding="utf-8").strip()
    assert json.loads(line) == {"event": "ok", "[REDACTED_KEY]": "[REDACTED]"}

    monkeypatch.setenv("H2T_RESEARCH_TELEMETRY_DISABLE", "1")
    assert client.append_telemetry(ledger, {"event": "disabled"}) is False

    monkeypatch.delenv("H2T_RESEARCH_TELEMETRY_DISABLE", raising=False)
    assert client.append_telemetry(tmp_path, {"event": "fails"}) is False


def test_append_telemetry_coerces_non_json_values(tmp_path, monkeypatch):
    _clear_sensitive_env(monkeypatch)
    ledger = tmp_path / "telemetry.jsonl"
    now = datetime(2026, 5, 21, tzinfo=UTC)

    assert client.append_telemetry(
        ledger,
        {"path": tmp_path / "artifact.json", "created_at": now},
    ) is True
    loaded = json.loads(ledger.read_text(encoding="utf-8"))

    assert loaded["path"] == str(tmp_path / "artifact.json")
    assert loaded["created_at"] == str(now)


def _patch_exa_search(
    monkeypatch: pytest.MonkeyPatch,
    *,
    provider_envelope: dict,
    exit_code: int,
) -> SimpleNamespace:
    calls = SimpleNamespace(
        validate_args=[],
        load_system_prompt=[],
        build_body=[],
        search_with_retry=[],
    )

    def validate_args(args):
        calls.validate_args.append(args)

    def load_system_prompt(mode):
        calls.load_system_prompt.append(mode)
        return "system prompt", {"type": "object"}

    def build_body(args, system_prompt, output_schema):
        calls.build_body.append((args, system_prompt, output_schema))
        return {
            "query": args.query,
            "numResults": args.num_results,
            "systemPrompt": system_prompt,
            "outputSchema": output_schema,
        }

    def search_with_retry(*, body, api_key, retry, mode):
        calls.search_with_retry.append((body, api_key, retry, mode))
        return provider_envelope, exit_code

    from h2t_ops.connectors.research import exa

    monkeypatch.setattr(exa, "validate_args", validate_args)
    monkeypatch.setattr(exa, "load_system_prompt", load_system_prompt)
    monkeypatch.setattr(exa, "build_body", build_body)
    monkeypatch.setattr(exa, "search_with_retry", search_with_retry)
    return calls


def _provider_envelope(status: str = "OK") -> dict:
    return {
        "status": status,
        "primary_engine": "exa",
        "fallback_engine_used": None,
        "results": [
            {
                "title": "Result",
                "url": "https://example.com/result",
                "highlights": ["quoted evidence"],
            }
        ]
        if status == "OK"
        else [],
        "telemetry": {
            "attempts": [
                {
                    "engine": "exa",
                    "endpoint": "/search",
                    "http": 200 if status == "OK" else 500,
                    "latency_ms": 123,
                    "error": None if status == "OK" else "exa_5xx_retryable",
                }
            ],
            "reason_for_fallback": None,
            "total_latency_ms": 123,
            "total_cost_usd": 0.012,
        },
        "meta": {
            "query": "research connector migration",
            "mode": "generic",
            "num_results_requested": 3,
            "num_results_returned": 1 if status == "OK" else 0,
            "envelope_version": "1",
        },
    }


def test_research_client_search_ok_writes_artifacts(tmp_path, monkeypatch):
    _clear_sensitive_env(monkeypatch)
    monkeypatch.setattr(client, "resolve_secret", lambda name: "exa-key")
    provider_envelope = _provider_envelope("OK")
    calls = _patch_exa_search(
        monkeypatch,
        provider_envelope=provider_envelope,
        exit_code=0,
    )

    result = client.ResearchClient(output_dir=tmp_path).search(
        query="research connector migration",
        mode="generic",
        num_results=3,
        project="h2t skills",
        no_retry=True,
    )

    assert result["kind"] == "research_provider_envelope"
    assert result["status"] == "OK"
    assert result["results"] == provider_envelope["results"]
    artifact = result["artifact"]
    assert artifact["kind"] == "research_artifact"
    assert artifact["provider_status"] == "OK"
    assert artifact["telemetry"]["cost_basis"] == "provider_reported"
    assert artifact["telemetry"]["estimated_cost_usd"] == 0.012

    refs = artifact["artifact_refs"]
    sources_path = tmp_path / refs["sources_json"]
    partial_path = tmp_path / refs["partial_md"]
    artifact_path = tmp_path / refs["artifact_json"]
    assert json.loads(sources_path.read_text(encoding="utf-8")) == provider_envelope["results"]
    assert "https://example.com/result" in partial_path.read_text(encoding="utf-8")
    assert json.loads(artifact_path.read_text(encoding="utf-8")) == artifact

    telemetry_lines = (tmp_path / "telemetry.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(telemetry_lines) == 1
    telemetry = json.loads(telemetry_lines[0])
    assert telemetry["provider"] == "exa"
    assert telemetry["endpoint"] == "/search"
    assert telemetry["cost_basis"] == "provider_reported"
    assert telemetry["artifact_id"] == artifact["artifact_id"]

    assert calls.validate_args[0].query == "research connector migration"
    assert calls.search_with_retry == [
        (
            {
                "query": "research connector migration",
                "numResults": 3,
                "systemPrompt": "system prompt",
                "outputSchema": {"type": "object"},
            },
            "exa-key",
            False,
            "generic",
        )
    ]


def test_write_provider_artifacts_does_not_persist_document_generically(tmp_path):
    rc = client.ResearchClient(output_dir=tmp_path)
    provider_envelope = {
        "status": "OK",
        "results": [
            {
                "url": "https://example.com/post",
                "title": "Example Post",
                "text": "Example body text",
            }
        ],
        "telemetry": {"attempts": []},
        "meta": {"query": "https://example.com/post"},
    }
    telemetry = {
        "calls": 1,
        "providers": ["exa"],
        "estimated_cost_usd": 0.0,
        "cost_basis": "test",
    }

    artifact = rc._write_provider_artifacts(
        kind="fetch",
        slug_source="https://example.com/post",
        project="demo",
        provider_envelope=provider_envelope,
        telemetry=telemetry,
        ledger_provider="exa",
        ledger_endpoint="/contents",
        ledger_mode="fetch",
    )

    assert "research_refs" not in artifact
    assert not (tmp_path / "objects" / "documents").exists()
    assert not (tmp_path / "indexes" / "documents.index.json").exists()
    assert not (tmp_path / "indexes" / "aliases.index.json").exists()


def test_write_visual_ocr_artifacts_persists_document(tmp_path):
    rc = client.ResearchClient(output_dir=tmp_path)
    telemetry = {
        "calls": 1,
        "providers": ["visual_ocr"],
        "estimated_cost_usd": 0.0,
        "cost_basis": "local_ocr",
    }
    envelope = {
        "kind": "research_visual_ocr_envelope",
        "url": "https://example.com/post",
        "body_text_visual_ocr": "Recovered visible text",
        "visible_headings": ["Headline"],
        "ocr_confidence": "medium",
        "quote_safe": False,
        "review_status": "unreviewed",
        "provenance": {
            "captured_at": "2026-05-26T09:00:00Z",
            "image_path": "page.png",
            "text_source": "visual_ocr",
        },
        "status": "OK",
    }

    artifact = rc._write_visual_ocr_artifacts(
        slug_source="https://example.com/post",
        project="demo",
        ocr_envelope=envelope,
        telemetry=telemetry,
    )

    document_path = Path(artifact["research_refs"]["document_json"])
    document = json.loads(document_path.read_text(encoding="utf-8"))

    assert document["provider"] == "visual_ocr"
    assert document["artifact_refs"]["normalized_text"] is not None


def test_search_persists_thread_and_run_artifacts(tmp_path, monkeypatch):
    rc = client.ResearchClient(output_dir=tmp_path)
    monkeypatch.setattr(client, "resolve_secret", lambda name: "test-secret")
    _patch_exa_search(
        monkeypatch,
        provider_envelope={
            "status": "OK",
            "primary_engine": "exa",
            "fallback_engine_used": None,
            "results": [{"url": "https://example.com/post", "title": "Example Post"}],
            "telemetry": {
                "attempts": [{"engine": "exa", "endpoint": "/search", "http": 200, "latency_ms": 10, "error": None}],
                "reason_for_fallback": None,
                "total_latency_ms": 10,
                "total_cost_usd": 0.0,
            },
            "meta": {
                "query": "exa api",
                "mode": "generic",
                "num_results_requested": 10,
                "num_results_returned": 1,
                "envelope_version": "1",
            },
        },
        exit_code=0,
    )

    result = rc.search(query="exa api", project="demo")

    thread_path = Path(result["artifact"]["research_refs"]["thread_json"])
    run_path = Path(result["artifact"]["research_refs"]["run_json"])

    assert thread_path.is_file()
    assert run_path.is_file()
    assert "document_json" not in result["artifact"]["research_refs"]
    assert not (tmp_path / "objects" / "documents").exists()


def test_answer_persists_synthesis_artifact(tmp_path, monkeypatch):
    rc = client.ResearchClient(output_dir=tmp_path)

    monkeypatch.setattr(
        "h2t_ops.connectors.research.exa.answer",
        lambda *args, **kwargs: (
            {
                "status": "OK",
                "primary_engine": "exa",
                "fallback_engine_used": None,
                "results": [{"answer": "Exa supports direct answers."}],
                "telemetry": {
                    "attempts": [{"engine": "exa", "endpoint": "/answer", "http": 200, "latency_ms": 10, "error": None}],
                    "reason_for_fallback": None,
                    "total_latency_ms": 10,
                    "total_cost_usd": 0.0,
                },
                "meta": {
                    "query": "what does exa answer do",
                    "mode": "answer",
                    "num_results_requested": 1,
                    "num_results_returned": 1,
                    "envelope_version": "1",
                },
            },
            0,
        ),
    )
    monkeypatch.setattr(client, "resolve_secret", lambda name: "test-secret")

    result = rc.answer("what does exa answer do")

    synthesis_path = Path(result["artifact"]["research_refs"]["synthesis_json"])
    synthesis = json.loads(synthesis_path.read_text(encoding="utf-8"))
    thread_path = Path(result["artifact"]["research_refs"]["thread_json"])
    thread = json.loads(thread_path.read_text(encoding="utf-8"))

    assert synthesis["status"] == "draft"
    assert synthesis["summary"] == "Exa supports direct answers."
    assert thread["latest_synthesis_id"] == synthesis["synthesis_id"]


def test_research_client_search_artifacts_redact_token_like_provider_values(
    tmp_path, monkeypatch
):
    _clear_sensitive_env(monkeypatch)
    monkeypatch.setattr(client, "resolve_secret", lambda name: "exa-key")
    query_secret = "query-exa-value"
    title_secret = "title-bearer-value"
    highlight_secret = "secret" + "_highlight_value"
    provider_envelope = _provider_envelope("OK")
    provider_envelope["meta"]["query"] = "EXA_API_KEY=" + query_secret
    provider_envelope["results"][0]["title"] = "Authorization: Bearer " + title_secret
    provider_envelope["results"][0]["highlights"] = ["quote " + highlight_secret]
    _patch_exa_search(
        monkeypatch,
        provider_envelope=provider_envelope,
        exit_code=0,
    )

    result = client.ResearchClient(output_dir=tmp_path).search(
        query="EXA_API_KEY=" + query_secret,
        project="h2t skills",
    )

    refs = result["artifact"]["artifact_refs"]
    partial_text = (tmp_path / refs["partial_md"]).read_text(encoding="utf-8")
    sources_text = (tmp_path / refs["sources_json"]).read_text(encoding="utf-8")
    artifact_text = (tmp_path / refs["artifact_json"]).read_text(encoding="utf-8")
    combined = "\n".join([partial_text, sources_text, artifact_text])

    assert query_secret not in combined
    assert title_secret not in combined
    assert highlight_secret not in combined
    assert "[REDACTED]" in combined
    result_text = json.dumps(result)
    assert query_secret not in result_text
    assert title_secret not in result_text
    assert highlight_secret not in result_text


def test_research_client_search_artifacts_redact_sensitive_url_query_params(
    tmp_path, monkeypatch
):
    _clear_sensitive_env(monkeypatch)
    monkeypatch.setattr(client, "resolve_secret", lambda name: "exa-key")
    url_secret = "url-leak-token"
    provider_envelope = _provider_envelope("OK")
    provider_envelope["results"][0]["url"] = (
        "https://example.com/result?access_token=" + url_secret + "&safe=value"
    )
    _patch_exa_search(
        monkeypatch,
        provider_envelope=provider_envelope,
        exit_code=0,
    )

    result = client.ResearchClient(output_dir=tmp_path).search(
        query="research connector migration",
        project="h2t skills",
    )

    refs = result["artifact"]["artifact_refs"]
    partial_text = (tmp_path / refs["partial_md"]).read_text(encoding="utf-8")
    sources_text = (tmp_path / refs["sources_json"]).read_text(encoding="utf-8")

    assert url_secret not in sources_text
    assert url_secret not in partial_text
    assert "safe=value" in sources_text
    assert "safe=value" in partial_text
    assert "[REDACTED]" in sources_text
    assert "[REDACTED]" in partial_text


def test_research_client_search_sanitizes_project_before_artifact_paths(
    tmp_path, monkeypatch
):
    _clear_sensitive_env(monkeypatch)
    monkeypatch.setattr(client, "resolve_secret", lambda name: "exa-key")
    project_secret = "project-leak-token"
    provider_envelope = _provider_envelope("OK")
    _patch_exa_search(
        monkeypatch,
        provider_envelope=provider_envelope,
        exit_code=0,
    )

    result = client.ResearchClient(output_dir=tmp_path).search(
        query="research connector migration",
        project="access_token=" + project_secret,
    )

    refs = result["artifact"]["artifact_refs"]
    ref_text = json.dumps(refs)
    generated_names = "\n".join(path.name for path in tmp_path.iterdir())

    assert project_secret not in ref_text
    assert project_secret not in generated_names
    assert "redacted" in ref_text
    assert "redacted" in generated_names


def test_research_client_search_failed_provider_envelope_raises_providererror(
    tmp_path, monkeypatch
):
    _clear_sensitive_env(monkeypatch)
    monkeypatch.setattr(client, "resolve_secret", lambda name: "exa-key")
    provider_envelope = _provider_envelope("FAILED")
    provider_envelope["telemetry"]["attempts"][0]["error"] = "exa_4xx_nonretryable"
    _patch_exa_search(monkeypatch, provider_envelope=provider_envelope, exit_code=2)

    with pytest.raises(ProviderError) as ei:
        client.ResearchClient(output_dir=tmp_path).search(query="q")

    details = ei.value.details
    assert details["provider_envelope"]["status"] == "FAILED"
    assert details["provider_envelope"]["telemetry"]["attempts"][0]["error"] == "exa_4xx_nonretryable"
    assert (tmp_path / "telemetry.jsonl").is_file()


def test_research_client_search_auth_error_raises_autherror(tmp_path, monkeypatch):
    _clear_sensitive_env(monkeypatch)
    monkeypatch.setattr(client, "resolve_secret", lambda name: "exa-key")
    provider_envelope = _provider_envelope("FAILED")
    provider_envelope["telemetry"]["attempts"][0].update(
        {"http": 401, "error": "exa_auth_error"}
    )
    _patch_exa_search(monkeypatch, provider_envelope=provider_envelope, exit_code=2)

    with pytest.raises(AuthError) as ei:
        client.ResearchClient(output_dir=tmp_path).search(query="q")

    assert ei.value.details["provider_envelope"]["telemetry"]["attempts"][0]["error"] == "exa_auth_error"


def test_research_client_search_exit_code_1_raises_usageerror(tmp_path, monkeypatch):
    _clear_sensitive_env(monkeypatch)
    monkeypatch.setattr(client, "resolve_secret", lambda name: "exa-key")
    provider_envelope = _provider_envelope("FAILED")
    provider_envelope["telemetry"]["attempts"][0]["error"] = "exa_usage_error"
    _patch_exa_search(monkeypatch, provider_envelope=provider_envelope, exit_code=1)

    with pytest.raises(UsageError) as ei:
        client.ResearchClient(output_dir=tmp_path).search(query="q")

    details = ei.value.details
    assert details["provider_envelope"]["status"] == "FAILED"
    assert details["provider_envelope"]["telemetry"]["attempts"][0]["error"] == "exa_usage_error"


def test_research_client_search_network_failure_exit_code_3_raises_networkerror(
    tmp_path, monkeypatch
):
    _clear_sensitive_env(monkeypatch)
    monkeypatch.setattr(client, "resolve_secret", lambda name: "exa-key")
    provider_envelope = _provider_envelope("FAILED")
    provider_envelope["telemetry"]["attempts"][0].update(
        {"http": None, "error": "exa_network_timeout"}
    )
    _patch_exa_search(monkeypatch, provider_envelope=provider_envelope, exit_code=3)

    with pytest.raises(NetworkError) as ei:
        client.ResearchClient(output_dir=tmp_path).search(query="q")

    details = ei.value.details
    assert details["provider_envelope"]["status"] == "FAILED"
    assert details["provider_envelope"]["telemetry"]["attempts"][0]["error"] == "exa_network_timeout"
    assert (tmp_path / "telemetry.jsonl").is_file()


def _fetch_provider_envelope(
    *,
    status: str = "OK",
    provider_used: str = "direct",
    content_gate: str = "none",
    raw_html_path: str | None = None,
) -> dict:
    return {
        "status": status,
        "url": "https://example.com",
        "final_url": "https://example.com",
        "provider_used": provider_used,
        "content_type": "article" if content_gate == "none" else "gated",
        "content_gate": content_gate,
        "title": "Example" if status != "FAILED" else None,
        "body_markdown": "Body" if status != "FAILED" else "",
        "body_text": "Body" if status != "FAILED" else "",
        "body_chars": 4 if status != "FAILED" else 0,
        "links": [],
        "metadata": {"raw_html_path": raw_html_path},
        "telemetry": {
            "attempts": [
                {
                    "provider": provider_used if provider_used != "none" else "direct",
                    "http": 200 if status != "FAILED" else 401,
                    "latency_ms": 10,
                    "error": None
                    if status != "FAILED"
                    else f"fetch_gated_{content_gate}",
                }
            ],
            "reason_for_degraded": None,
            "reason_for_failed": None
            if status != "FAILED"
            else f"content_gate_{content_gate}",
            "total_latency_ms": 10,
            "providers_skipped": [],
            "providers_skipped_reason": {},
        },
        "meta": {"primary_engine": "fetch_ladder", "envelope_version": "1"},
    }


def test_research_client_fetch_ok_writes_artifact(tmp_path):
    provider_env = _fetch_provider_envelope()
    with patch(
        "h2t_ops.connectors.research.fetch.fetch_via_ladder",
        return_value=provider_env,
    ) as fetch_ladder:
        result = client.ResearchClient(output_dir=tmp_path).fetch_url(
            "https://example.com",
        )

    assert result["kind"] == "research_fetch_envelope"
    assert result["status"] == "OK"
    assert result["artifact"]["telemetry"]["providers"] == ["direct"]
    assert result["artifact"]["telemetry"]["estimated_cost_usd"] == 0.0
    assert result["artifact"]["telemetry"]["cost_basis"] == "zero"

    refs = result["artifact"]["artifact_refs"]
    assert (tmp_path / refs["sources_json"]).is_file()
    assert (tmp_path / refs["partial_md"]).is_file()
    assert json.loads((tmp_path / refs["artifact_json"]).read_text(encoding="utf-8")) == result["artifact"]
    assert refs["raw_html"] is None
    document_path = Path(result["artifact"]["research_refs"]["document_json"])
    document = json.loads(document_path.read_text(encoding="utf-8"))
    assert document["canonical_url"] == "https://example.com"
    assert document["provider"] == "direct"
    assert fetch_ladder.call_args.kwargs["url"] == "https://example.com"
    assert fetch_ladder.call_args.kwargs["provider_choice"] == "auto"
    assert fetch_ladder.call_args.kwargs["config"]["ladder"]["per_provider_timeout_ms"] == 15000
    assert fetch_ladder.call_args.kwargs["config"]["ladder"]["min_body_chars"] == 200


def test_research_client_fetch_failed_does_not_persist_document(tmp_path):
    provider_env = {
        "status": "FAILED",
        "url": "https://example.com",
        "final_url": None,
        "provider_used": "none",
        "content_type": "unknown",
        "content_gate": "none",
        "title": None,
        "body_markdown": "",
        "body_text": "",
        "body_chars": 0,
        "links": [],
        "metadata": {"canonical_url": None, "site": "example.com", "lang": None},
        "telemetry": {
            "attempts": [{"provider": "direct", "http": None, "latency_ms": 19, "error": "fetch_network_timeout"}],
            "reason_for_degraded": None,
            "reason_for_failed": "all_providers_failed",
            "total_latency_ms": 19,
            "providers_skipped": [],
            "providers_skipped_reason": {},
        },
        "meta": {
            "primary_engine": "fetch_ladder",
            "envelope_version": "1",
            "fetch_envelope_version": "1",
            "timestamp": "2026-05-26T16:16:18+00:00",
            "user_agent": "h2t-research-fetch/0.0.1",
        },
    }

    with patch(
        "h2t_ops.connectors.research.fetch.fetch_via_ladder",
        return_value=provider_env,
    ):
        with pytest.raises(NetworkError):
            client.ResearchClient(output_dir=tmp_path).fetch_url("https://example.com")

    assert not (tmp_path / "objects" / "documents").exists()
    assert not (tmp_path / "indexes" / "documents.index.json").exists()
    assert not (tmp_path / "indexes" / "aliases.index.json").exists()


def test_research_client_fetch_timeout_updates_provider_configs_with_timeouts(tmp_path):
    provider_env = _fetch_provider_envelope()
    with patch(
        "h2t_ops.connectors.research.fetch.fetch_via_ladder",
        return_value=provider_env,
    ) as fetch_ladder:
        client.ResearchClient(output_dir=tmp_path).fetch_url(
            "https://example.com",
            timeout_ms=4321,
        )

    config = fetch_ladder.call_args.kwargs["config"]
    assert config["ladder"]["per_provider_timeout_ms"] == 4321
    assert config["providers"]["direct"]["timeout_ms"] == 4321
    assert config["providers"]["jina"]["timeout_ms"] == 4321
    assert config["providers"]["playwright"]["timeout_ms"] == 4321


def test_research_client_fetch_timeout_updates_explicit_disabled_provider_config(
    tmp_path,
):
    config_path = tmp_path / "fetch_config.json"
    config_path.write_text(
        json.dumps(
            {
                "providers": {
                    "direct": {"enabled": False, "timeout_ms": 9999},
                },
            }
        ),
        encoding="utf-8",
    )
    provider_env = _fetch_provider_envelope()

    with patch(
        "h2t_ops.connectors.research.fetch.fetch_via_ladder",
        return_value=provider_env,
    ) as fetch_ladder:
        client.ResearchClient(output_dir=tmp_path).fetch_url(
            "https://example.com",
            provider="direct",
            timeout_ms=1234,
            config_path=str(config_path),
        )

    config = fetch_ladder.call_args.kwargs["config"]
    assert fetch_ladder.call_args.kwargs["provider_choice"] == "direct"
    assert config["providers"]["direct"]["enabled"] is False
    assert config["providers"]["direct"]["timeout_ms"] == 1234


def test_research_client_fetch_gated_maps_to_autherror(tmp_path):
    provider_env = _fetch_provider_envelope(
        status="FAILED",
        provider_used="none",
        content_gate="login_required",
    )
    with patch(
        "h2t_ops.connectors.research.fetch.fetch_via_ladder",
        return_value=provider_env,
    ):
        with pytest.raises(AuthError) as exc:
            client.ResearchClient(output_dir=tmp_path).fetch_url(
                "https://example.com/private",
            )
    assert exc.value.details["provider_envelope"]["content_gate"] == "login_required"
    assert exc.value.details["provider_envelope"]["status"] == "FAILED"


def test_research_client_fetch_keep_raw_maps_raw_html_ref(tmp_path):
    raw_path = tmp_path / "example.raw.html"
    raw_path.write_text("<html>raw</html>", encoding="utf-8")
    provider_env = _fetch_provider_envelope(raw_html_path=str(raw_path))

    with patch(
        "h2t_ops.connectors.research.fetch.fetch_via_ladder",
        return_value=provider_env,
    ) as fetch_ladder:
        result = client.ResearchClient(output_dir=tmp_path).fetch_url(
            "https://example.com",
            keep_raw=True,
        )

    assert fetch_ladder.call_args.kwargs["keep_raw"] is True
    assert result["artifact"]["artifact_refs"]["raw_html"] == raw_path.name


def test_research_client_fetch_keep_raw_redacts_url_secrets_in_raw_ref(tmp_path):
    url = (
        "https://example.com/private"
        "?api_key=secret123&access_token=token456&safe=value"
    )
    captured: dict[str, Path] = {}

    def fake_fetch_via_ladder(**kwargs):
        raw_path = kwargs["output_paths"]["raw_html"]
        captured["raw_html_path"] = raw_path
        provider_env = _fetch_provider_envelope(raw_html_path=str(raw_path))
        provider_env["url"] = url
        return provider_env

    with patch(
        "h2t_ops.connectors.research.fetch.fetch_via_ladder",
        side_effect=fake_fetch_via_ladder,
    ):
        result = client.ResearchClient(output_dir=tmp_path).fetch_url(
            url,
            keep_raw=True,
        )

    raw_path = captured["raw_html_path"]
    raw_ref = result["artifact"]["artifact_refs"]["raw_html"]
    assert raw_path.is_relative_to(tmp_path)
    assert raw_ref == raw_path.name
    assert "secret123" not in raw_path.name
    assert "token456" not in raw_path.name
    assert "secret123" not in raw_ref
    assert "token456" not in raw_ref
    assert "redacted" in raw_ref.lower()
    result_text = json.dumps(result)
    assert "secret123" not in result_text
    assert "token456" not in result_text


@pytest.mark.parametrize("method", ["fetch_url", "crawl"])
def test_research_client_url_methods_reject_file_and_private_targets(tmp_path, method):
    research = client.ResearchClient(output_dir=tmp_path)
    with pytest.raises(UsageError):
        getattr(research, method)("file:///C:/Users/stani/.dor/secrets.env")


def test_research_client_preflight_resolves_key_and_calls_exa(monkeypatch):
    _clear_sensitive_env(monkeypatch)
    calls: list[str] = []

    from h2t_ops.connectors.research import exa

    monkeypatch.setattr(client, "resolve_secret", lambda name: "exa-key")
    monkeypatch.setattr(exa, "preflight", lambda api_key: calls.append(api_key))

    result = client.ResearchClient().preflight()

    assert result == {"status": "OK", "provider": "exa"}
    assert calls == ["exa-key"]


def test_research_client_crawl_ok_writes_artifacts(tmp_path, monkeypatch):
    _clear_sensitive_env(monkeypatch)
    from h2t_ops.connectors.research import exa

    monkeypatch.setattr(client, "resolve_secret", lambda name: "exa-key")

    def call_exa(endpoint, body, api_key):
        assert endpoint == "/contents"
        assert body == {"urls": ["https://example.com/page"], "text": {"maxCharacters": 15000}}
        assert api_key == "exa-key"
        return (
            200,
            {
                "results": [
                    {
                        "title": "Example",
                        "url": "https://example.com/page",
                        "text": "Evidence body",
                    }
                ],
                "costDollars": {"total": 0.034},
            },
            44,
        )

    monkeypatch.setattr(exa, "call_exa", call_exa)

    result = client.ResearchClient(output_dir=tmp_path).crawl(
        "https://example.com/page",
        project="h2t skills",
    )

    assert result["kind"] == "research_provider_envelope"
    assert result["status"] == "OK"
    assert result["telemetry"]["total_latency_ms"] == 44
    assert result["telemetry"]["total_cost_usd"] == 0.034
    assert result["telemetry"]["attempts"][0]["endpoint"] == "/contents"
    assert result["meta"]["mode"] == "crawl"
    assert result["artifact"]["provider_status"] == "OK"
    assert result["artifact"]["telemetry"]["estimated_cost_usd"] == 0.034

    refs = result["artifact"]["artifact_refs"]
    assert json.loads((tmp_path / refs["sources_json"]).read_text(encoding="utf-8")) == result["results"]
    assert json.loads((tmp_path / refs["artifact_json"]).read_text(encoding="utf-8")) == result["artifact"]
    document_path = Path(result["artifact"]["research_refs"]["document_json"])
    document = json.loads(document_path.read_text(encoding="utf-8"))
    assert document["canonical_url"] == "https://example.com/page"
    assert document["project_ids"] == ["project:h2t skills"]


def test_research_client_crawl_empty_results_returns_degraded(tmp_path, monkeypatch):
    _clear_sensitive_env(monkeypatch)
    from h2t_ops.connectors.research import exa

    monkeypatch.setattr(client, "resolve_secret", lambda name: "exa-key")
    monkeypatch.setattr(
        exa,
        "call_exa",
        lambda endpoint, body, api_key: (
            200,
            {"results": [], "costDollars": {"total": 0}},
            12,
        ),
    )

    result = client.ResearchClient(output_dir=tmp_path).crawl("https://example.com")

    assert result["status"] == "DEGRADED"
    assert result["telemetry"]["reason_for_fallback"] == "exa_empty_results"
    assert result["telemetry"]["attempts"][0]["error"] == "exa_empty_results"
    assert result["artifact"]["provider_status"] == "DEGRADED"


def test_research_client_crawl_empty_results_with_plain_403_status_raises_providererror(
    tmp_path,
    monkeypatch,
):
    _clear_sensitive_env(monkeypatch)
    from h2t_ops.connectors.research import exa

    statuses = [
        {
            "url": "https://example.com/private",
            "statusCode": 403,
            "error": "forbidden",
        }
    ]
    monkeypatch.setattr(client, "resolve_secret", lambda name: "exa-key")
    monkeypatch.setattr(
        exa,
        "call_exa",
        lambda endpoint, body, api_key: (
            200,
            {"results": [], "statuses": statuses, "costDollars": {"total": 0.011}},
            17,
        ),
    )

    with pytest.raises(ProviderError) as ei:
        client.ResearchClient(output_dir=tmp_path).crawl("https://example.com/private")

    envelope = ei.value.details["provider_envelope"]
    assert envelope["status"] == "FAILED"
    assert envelope["statuses"] == statuses
    assert envelope["telemetry"]["attempts"][0]["http"] == 403
    assert envelope["telemetry"]["attempts"][0]["error"] == "exa_contents_status_4xx"
    assert envelope["telemetry"]["total_cost_usd"] == 0.011


def test_research_client_crawl_empty_results_with_login_status_raises_autherror(
    tmp_path,
    monkeypatch,
):
    _clear_sensitive_env(monkeypatch)
    from h2t_ops.connectors.research import exa

    statuses = [
        {
            "url": "https://example.com/login",
            "http_status": 403,
            "error": "login_required",
        }
    ]
    monkeypatch.setattr(client, "resolve_secret", lambda name: "exa-key")
    monkeypatch.setattr(
        exa,
        "call_exa",
        lambda endpoint, body, api_key: (
            200,
            {"results": [], "statuses": statuses},
            21,
        ),
    )

    with pytest.raises(AuthError) as ei:
        client.ResearchClient(output_dir=tmp_path).crawl("https://example.com/login")

    envelope = ei.value.details["provider_envelope"]
    assert envelope["statuses"] == statuses
    assert envelope["telemetry"]["attempts"][0]["error"] == "exa_contents_status_gated"


def test_research_client_crawl_empty_results_with_unauthorized_status_raises_autherror(
    tmp_path,
    monkeypatch,
):
    _clear_sensitive_env(monkeypatch)
    from h2t_ops.connectors.research import exa

    statuses = [
        {
            "url": "https://example.com/unauthorized",
            "statusCode": 401,
            "error": "unauthorized",
        }
    ]
    monkeypatch.setattr(client, "resolve_secret", lambda name: "exa-key")
    monkeypatch.setattr(
        exa,
        "call_exa",
        lambda endpoint, body, api_key: (
            200,
            {"results": [], "statuses": statuses},
            19,
        ),
    )

    with pytest.raises(AuthError) as ei:
        client.ResearchClient(output_dir=tmp_path).crawl(
            "https://example.com/unauthorized"
        )

    envelope = ei.value.details["provider_envelope"]
    assert envelope["statuses"] == statuses
    assert envelope["telemetry"]["attempts"][0]["http"] == 401
    assert envelope["telemetry"]["attempts"][0]["error"] == "exa_contents_status_gated"


def test_research_client_crawl_empty_results_with_numeric_401_status_raises_autherror(
    tmp_path,
    monkeypatch,
):
    _clear_sensitive_env(monkeypatch)
    from h2t_ops.connectors.research import exa

    statuses = [{"statusCode": 401}]
    monkeypatch.setattr(client, "resolve_secret", lambda name: "exa-key")
    monkeypatch.setattr(
        exa,
        "call_exa",
        lambda endpoint, body, api_key: (
            200,
            {"results": [], "statuses": statuses},
            11,
        ),
    )

    with pytest.raises(AuthError) as ei:
        client.ResearchClient(output_dir=tmp_path).crawl("https://example.com/401")

    envelope = ei.value.details["provider_envelope"]
    assert envelope["statuses"] == statuses
    assert envelope["telemetry"]["attempts"][0]["http"] == 401
    assert envelope["telemetry"]["attempts"][0]["error"] == "exa_contents_status_gated"


def test_research_client_crawl_empty_results_with_timeout_status_raises_networkerror(
    tmp_path,
    monkeypatch,
):
    _clear_sensitive_env(monkeypatch)
    from h2t_ops.connectors.research import exa

    statuses = [
        {
            "url": "https://example.com/slow",
            "status": "timeout",
            "message": "request timed out",
        }
    ]
    monkeypatch.setattr(client, "resolve_secret", lambda name: "exa-key")
    monkeypatch.setattr(
        exa,
        "call_exa",
        lambda endpoint, body, api_key: (
            200,
            {"results": [], "statuses": statuses},
            30,
        ),
    )

    with pytest.raises(NetworkError) as ei:
        client.ResearchClient(output_dir=tmp_path).crawl("https://example.com/slow")

    envelope = ei.value.details["provider_envelope"]
    assert envelope["statuses"] == statuses
    assert envelope["telemetry"]["attempts"][0]["error"] == "exa_contents_status_network"


def test_research_client_crawl_empty_results_with_not_found_status_raises_providererror(
    tmp_path,
    monkeypatch,
):
    _clear_sensitive_env(monkeypatch)
    from h2t_ops.connectors.research import exa

    statuses = [
        {
            "url": "https://example.com/missing",
            "status_code": 404,
            "error": "not_found",
        }
    ]
    monkeypatch.setattr(client, "resolve_secret", lambda name: "exa-key")
    monkeypatch.setattr(
        exa,
        "call_exa",
        lambda endpoint, body, api_key: (
            200,
            {"results": [], "statuses": statuses},
            8,
        ),
    )

    with pytest.raises(ProviderError) as ei:
        client.ResearchClient(output_dir=tmp_path).crawl("https://example.com/missing")

    envelope = ei.value.details["provider_envelope"]
    assert envelope["statuses"] == statuses
    assert envelope["telemetry"]["attempts"][0]["http"] == 404
    assert envelope["telemetry"]["attempts"][0]["error"] == "exa_contents_status_4xx"


def test_research_client_crawl_permanent_error_sanitizes_details(tmp_path, monkeypatch):
    _clear_sensitive_env(monkeypatch)
    from h2t_ops.connectors.research import exa

    leaked = "secret" + "_exa_value"
    monkeypatch.setattr(client, "resolve_secret", lambda name: "exa-key")

    def call_exa(endpoint, body, api_key):
        raise exa.ExaPermanentError(
            "bad request",
            http_status=400,
            latency_ms=9,
            body={"message": "EXA_API_KEY=" + leaked, "x-api-key": leaked},
        )

    monkeypatch.setattr(exa, "call_exa", call_exa)

    with pytest.raises(ProviderError) as ei:
        client.ResearchClient(output_dir=tmp_path).crawl("https://example.com")

    details_text = json.dumps(ei.value.details)
    assert leaked not in details_text
    assert "[REDACTED]" in details_text
    assert ei.value.details["http_status"] == 400
    assert ei.value.details["latency_ms"] == 9


def test_research_client_crawl_network_failure_maps_to_networkerror(
    tmp_path,
    monkeypatch,
):
    _clear_sensitive_env(monkeypatch)
    from h2t_ops.connectors.research import exa

    monkeypatch.setattr(client, "resolve_secret", lambda name: "exa-key")

    def call_exa(endpoint, body, api_key):
        raise exa.ExaTransientError(
            "timed out",
            http_status=None,
            latency_ms=101,
        )

    monkeypatch.setattr(exa, "call_exa", call_exa)

    with pytest.raises(NetworkError) as ei:
        client.ResearchClient(output_dir=tmp_path).crawl("https://example.com")

    assert "network failed" in str(ei.value)
    assert ei.value.details == {
        "http_status": None,
        "latency_ms": 101,
        "provider_error": None,
    }


def test_research_client_visual_ocr_ok_writes_dedicated_artifacts(tmp_path, monkeypatch):
    _clear_sensitive_env(monkeypatch)
    fixed_now = datetime(2026, 5, 25, 12, 34, 56, tzinfo=UTC)

    class FixedDateTime:
        @classmethod
        def now(cls, tz=None):
            assert tz is UTC
            return fixed_now

    monkeypatch.setattr(client, "datetime", FixedDateTime)

    from h2t_ops.connectors.research import visual_ocr

    sidecar = {
        "meta": {"tool": "fetch_url.py", "status": "FAILED"},
        "envelope": {
            "status": "FAILED",
            "url": "https://example.com/pops",
            "content_gate": "none",
            "telemetry": {
                "reason_for_failed": "redirect_collapsed_to_homepage",
            },
        },
    }

    monkeypatch.setattr(visual_ocr, "load_fetch_sidecar", lambda path: sidecar)
    monkeypatch.setattr(visual_ocr, "load_fetch_envelope", lambda payload: payload["envelope"])
    monkeypatch.setattr(visual_ocr, "validate_visual_ocr_trigger", lambda envelope: None)
    monkeypatch.setattr(
        visual_ocr,
        "extract_text_from_image",
        lambda image_path: (
            "POPs in TouchDesigner\nAttribute lifecycle",
            ["POPs in TouchDesigner", "Attribute lifecycle"],
            "medium",
        ),
    )

    result = client.ResearchClient(output_dir=tmp_path).visual_ocr(
        fetch_sidecar="artifact.sources.json",
        image_path="capture.png",
        project="h2t skills",
    )

    assert result["kind"] == "research_visual_ocr_envelope"
    assert result["status"] == "OK"
    assert result["provider_used"] == "visual_ocr"
    assert result["provenance"]["captured_at"] == fixed_now.isoformat()

    artifact = result["artifact"]
    refs = artifact["artifact_refs"]
    sources_path = tmp_path / refs["sources_json"]
    partial_path = tmp_path / refs["partial_md"]
    artifact_path = tmp_path / refs["artifact_json"]

    assert sources_path.is_file()
    assert partial_path.is_file()
    assert artifact_path.is_file()
    assert json.loads(sources_path.read_text(encoding="utf-8")) == {
        key: value
        for key, value in result.items()
        if key not in {"artifact", "kind"}
    }

    partial_text = partial_path.read_text(encoding="utf-8")
    assert "Visual OCR Review Required" in partial_text
    assert "non-canonical OCR recovery" in partial_text
    assert "POPs in TouchDesigner" in partial_text
    assert "Attribute lifecycle" in partial_text
    assert "captured_at: 2026-05-25T12:34:56+00:00" in partial_text

    assert json.loads(artifact_path.read_text(encoding="utf-8")) == artifact
    assert artifact["provider_status"] == "OK"
    assert artifact["tool"] == "h2t-ops research visual-ocr"
    assert artifact["telemetry"]["providers"] == ["visual_ocr"]
    assert artifact["telemetry"]["captured_at"] == fixed_now.isoformat()
    assert artifact["telemetry"]["estimated_cost_usd"] == 0.0
    assert artifact["telemetry"]["cost_basis"] == "local_ocr"

    telemetry_lines = (tmp_path / "telemetry.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(telemetry_lines) == 1
    telemetry = json.loads(telemetry_lines[0])
    assert telemetry["provider"] == "visual_ocr"
    assert telemetry["endpoint"] == "visual_ocr"
    assert telemetry["mode"] == "single_image"
    assert telemetry["captured_at"] == fixed_now.isoformat()
    assert telemetry["latency_ms"] is None
    assert telemetry["result_count"] == 1
    assert telemetry["estimated_cost_usd"] == 0.0
    assert telemetry["cost_basis"] == "local_ocr"


def test_research_client_visual_ocr_artifacts_redact_sensitive_values(tmp_path, monkeypatch):
    _clear_sensitive_env(monkeypatch)
    fixed_now = datetime(2026, 5, 25, 12, 35, 0, tzinfo=UTC)

    class FixedDateTime:
        @classmethod
        def now(cls, tz=None):
            assert tz is UTC
            return fixed_now

    monkeypatch.setattr(client, "datetime", FixedDateTime)

    from h2t_ops.connectors.research import visual_ocr

    leaked_query = "ocr-url-secret"
    leaked_text = "secret" + "_ocr_token"
    sidecar = {
        "meta": {"tool": "fetch_url.py", "status": "FAILED"},
        "envelope": {
            "status": "FAILED",
            "url": f"https://example.com/pops?access_token={leaked_query}&safe=value",
            "content_gate": "none",
            "telemetry": {
                "reason_for_failed": "redirect_collapsed_to_homepage",
            },
        },
    }

    monkeypatch.setattr(visual_ocr, "load_fetch_sidecar", lambda path: sidecar)
    monkeypatch.setattr(visual_ocr, "load_fetch_envelope", lambda payload: payload["envelope"])
    monkeypatch.setattr(visual_ocr, "validate_visual_ocr_trigger", lambda envelope: None)
    monkeypatch.setattr(
        visual_ocr,
        "extract_text_from_image",
        lambda image_path: (
            "Authorization: Bearer token-123\n" + leaked_text,
            ["Authorization: Bearer token-123"],
            "medium",
        ),
    )

    result = client.ResearchClient(output_dir=tmp_path).visual_ocr(
        fetch_sidecar="artifact.sources.json",
        image_path="capture.png",
        project="access_token=project-secret",
    )

    refs = result["artifact"]["artifact_refs"]
    combined = "\n".join(
        [
            (tmp_path / refs["sources_json"]).read_text(encoding="utf-8"),
            (tmp_path / refs["partial_md"]).read_text(encoding="utf-8"),
            (tmp_path / refs["artifact_json"]).read_text(encoding="utf-8"),
            json.dumps(result),
        ]
    )
    generated_names = "\n".join(path.name for path in tmp_path.iterdir())

    assert leaked_query not in combined
    assert leaked_text not in combined
    assert "token-123" not in combined
    assert "project-secret" not in combined
    assert "safe=value" in combined
    assert "[REDACTED]" in combined
    assert "project-secret" not in generated_names
    assert "redacted" in generated_names.lower()

    telemetry = json.loads((tmp_path / "telemetry.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert telemetry["endpoint"] == "visual_ocr"
    assert telemetry["mode"] == "single_image"
    assert telemetry["latency_ms"] is None
    assert telemetry["result_count"] == 1
    assert telemetry["estimated_cost_usd"] == 0.0
    assert telemetry["cost_basis"] == "local_ocr"


def test_research_client_list_research_documents_by_project(tmp_path):
    root = tmp_path
    rows = [
        {
            "document_id": "research-doc:demo",
            "canonical_url": "https://demo.example",
            "provider": "jina",
            "title": "Demo",
            "status": "indexed",
            "review_status": "unreviewed",
            "thread_ids": [],
            "entity_ids": [],
            "project_ids": ["project:demo"],
            "updated_at": "2026-05-27T10:00:00Z",
        },
        {
            "document_id": "research-doc:other",
            "canonical_url": "https://other.example",
            "provider": "jina",
            "title": "Other",
            "status": "indexed",
            "review_status": "unreviewed",
            "thread_ids": [],
            "entity_ids": [],
            "project_ids": ["project:other"],
            "updated_at": "2026-05-27T10:00:00Z",
        },
    ]
    store.write_json(store.index_path(root, "documents"), rows)

    result = client.ResearchClient(output_dir=tmp_path).list_research_index(
        "documents",
        project="demo",
    )

    assert result["kind"] == "research_index"
    assert result["index"] == "documents"
    assert result["root"] == str(root)
    assert result["count"] == 1
    assert result["items"][0]["document_id"] == "research-doc:demo"


def test_research_client_show_research_document(tmp_path):
    document = store.build_research_document(
        canonical_url="https://example.com/post",
        source_url="https://example.com/post",
        provider="jina",
        title="Example",
        fetched_at="2026-05-27T10:00:00Z",
        content_hash="abc",
        artifact_refs={
            "metadata": "artifact.json",
            "normalized_text": "sources.json",
            "citation_bundle": None,
            "markdown_mirror": "partial.md",
        },
        project_ids=["project:demo"],
        thread_ids=[],
        entity_ids=[],
    )
    store.write_object(tmp_path, "documents", document["document_id"], document)

    result = client.ResearchClient(output_dir=tmp_path).show_research_object(
        "document",
        document["document_id"],
    )

    assert result["kind"] == "research_object"
    assert result["object_type"] == "document"
    assert result["object"]["document_id"] == document["document_id"]


def test_research_client_resolve_research_alias_url(tmp_path):
    document = store.build_research_document(
        canonical_url="https://example.com/post",
        source_url="https://example.com/post",
        provider="jina",
        title="Example",
        fetched_at="2026-05-27T10:00:00Z",
        content_hash="abc",
        artifact_refs={
            "metadata": "artifact.json",
            "normalized_text": "sources.json",
            "citation_bundle": None,
            "markdown_mirror": "partial.md",
        },
        project_ids=["project:demo"],
        thread_ids=[],
        entity_ids=[],
    )
    store.write_object(tmp_path, "documents", document["document_id"], document)

    store.upsert_alias_index(
        tmp_path,
        [
            {
                "alias_type": "url",
                "alias_value": "https://example.com/post",
                "target_object_type": "document",
                "target_id": document["document_id"],
                "confidence": "high",
            }
        ],
    )

    result = client.ResearchClient(output_dir=tmp_path).resolve_research_alias(
        "https://example.com/post",
        alias_type="url",
    )

    assert result["kind"] == "research_resolution"
    assert result["count"] == 1
    assert result["matches"][0]["target_id"] == document["document_id"]
    assert result["matches"][0]["object_exists"] is True


def test_research_client_doctor_delegates_to_maintenance(tmp_path, monkeypatch):
    calls = []

    def doctor(root):
        calls.append(root)
        return {"kind": "research_doctor", "ok": True}

    monkeypatch.setattr(client.maintenance, "doctor", doctor)

    result = client.ResearchClient(output_dir=tmp_path).research_doctor()

    assert result == {"kind": "research_doctor", "ok": True}
    assert calls == [tmp_path]


def test_research_client_rebuild_indexes_delegates_to_maintenance(tmp_path, monkeypatch):
    calls = []

    def rebuild_indexes(root):
        calls.append(root)
        return {"kind": "research_rebuild_indexes", "rebuilt": ["documents"]}

    monkeypatch.setattr(client.maintenance, "rebuild_indexes", rebuild_indexes)

    result = client.ResearchClient(output_dir=tmp_path).rebuild_research_indexes()

    assert result == {"kind": "research_rebuild_indexes", "rebuilt": ["documents"]}
    assert calls == [tmp_path]


def test_research_client_cleanup_delegates_to_maintenance(tmp_path, monkeypatch):
    calls = []

    def cleanup(root, *, dry_run=True):
        calls.append((root, dry_run))
        return {"kind": "research_cleanup", "dry_run": dry_run}

    monkeypatch.setattr(client.maintenance, "cleanup", cleanup)

    rc = client.ResearchClient(output_dir=tmp_path)

    assert rc.cleanup_research() == {"kind": "research_cleanup", "dry_run": True}
    assert rc.cleanup_research(dry_run=False) == {
        "kind": "research_cleanup",
        "dry_run": False,
    }
    assert calls == [(tmp_path, True), (tmp_path, False)]


def test_research_client_lists_provider_status(tmp_path, monkeypatch):
    from h2t_ops.connectors.research import provider_routing

    calls = []

    def fake_status(*, capability=None):
        calls.append(capability)
        return {"kind": "research_provider_status", "capability": capability}

    monkeypatch.setattr(provider_routing, "provider_status", fake_status)

    result = client.ResearchClient(output_dir=tmp_path).research_provider_status(
        capability="fetch"
    )

    assert result == {"kind": "research_provider_status", "capability": "fetch"}
    assert calls == ["fetch"]


def test_research_client_selects_provider_route(tmp_path, monkeypatch):
    from h2t_ops.connectors.research import provider_routing

    calls = []

    def fake_select(capability, *, provider=None):
        calls.append((capability, provider))
        return {
            "kind": "research_provider_route",
            "capability": capability,
            "selected_provider": provider or "exa",
        }

    monkeypatch.setattr(provider_routing, "select_route", fake_select)

    result = client.ResearchClient(output_dir=tmp_path).research_route(
        "search",
        provider="exa",
    )

    assert result["selected_provider"] == "exa"
    assert calls == [("search", "exa")]


def test_search_missing_exa_key_fails_before_artifact_writes(tmp_path, monkeypatch):
    from h2t_ops.connectors.research import provider_routing

    monkeypatch.setattr(provider_routing, "_secret_available", lambda name: False)

    with pytest.raises(UsageError, match="no configured research provider"):
        client.ResearchClient(output_dir=tmp_path).search(query="missing key")

    assert not any(tmp_path.iterdir())


def test_answer_missing_exa_key_fails_before_artifact_writes(tmp_path, monkeypatch):
    from h2t_ops.connectors.research import provider_routing

    monkeypatch.setattr(provider_routing, "_secret_available", lambda name: False)

    with pytest.raises(UsageError, match="no configured research provider"):
        client.ResearchClient(output_dir=tmp_path).answer("missing key")

    assert not any(tmp_path.iterdir())


def test_similar_missing_exa_key_fails_before_artifact_writes(tmp_path, monkeypatch):
    from h2t_ops.connectors.research import provider_routing

    monkeypatch.setattr(provider_routing, "_secret_available", lambda name: False)

    with pytest.raises(UsageError, match="no configured research provider"):
        client.ResearchClient(output_dir=tmp_path).similar("https://example.com")

    assert not any(tmp_path.iterdir())


def test_crawl_missing_exa_key_fails_before_artifact_writes(tmp_path, monkeypatch):
    from h2t_ops.connectors.research import provider_routing

    monkeypatch.setattr(provider_routing, "_secret_available", lambda name: False)

    with pytest.raises(UsageError, match="no configured research provider"):
        client.ResearchClient(output_dir=tmp_path).crawl("https://example.com")

    assert not any(tmp_path.iterdir())


def test_resolve_author_missing_exa_key_fails_before_provider_call(tmp_path, monkeypatch):
    from h2t_ops.connectors.research import author_resolve, provider_routing

    monkeypatch.setattr(provider_routing, "_secret_available", lambda name: False)

    def fail_if_called(*args, **kwargs):
        raise AssertionError("author provider should not be called without route")

    monkeypatch.setattr(author_resolve, "resolve_author", fail_if_called)

    with pytest.raises(UsageError, match="no configured research provider"):
        client.ResearchClient(output_dir=tmp_path).resolve_author("Ada Lovelace")

    assert not any(tmp_path.iterdir())


def test_preflight_missing_exa_key_fails_before_provider_call(tmp_path, monkeypatch):
    from h2t_ops.connectors.research import exa, provider_routing

    monkeypatch.setattr(provider_routing, "_secret_available", lambda name: False)

    def fail_if_called(*args, **kwargs):
        raise AssertionError("exa preflight should not be called without route")

    monkeypatch.setattr(exa, "preflight", fail_if_called)

    with pytest.raises(UsageError, match="no configured research provider"):
        client.ResearchClient(output_dir=tmp_path).preflight()

    assert not any(tmp_path.iterdir())


def test_research_client_list_research_index_propagates_navigation_error(tmp_path, monkeypatch):
    def failing_list_index(*args, **kwargs):
        raise UsageError("index helper failure")

    monkeypatch.setattr(client.navigation, "list_index", failing_list_index)

    with pytest.raises(UsageError, match="index helper failure"):
        client.ResearchClient(output_dir=tmp_path).list_research_index("documents")


def test_research_client_show_research_document_missing_raises_notfound(tmp_path):
    with pytest.raises(NotFoundError, match="research object not found"):
        client.ResearchClient(output_dir=tmp_path).show_research_object(
            "document",
            "research-doc:missing",
        )


def test_research_client_show_research_unknown_type_raises_usageerror(tmp_path):
    with pytest.raises(UsageError, match="unknown research object type"):
        client.ResearchClient(output_dir=tmp_path).show_research_object(
            "bad-type",
            "research-bad:abc",
        )


def test_research_client_resolve_research_alias_propagates_navigation_error(tmp_path, monkeypatch):
    def failing_resolve_alias(*args, **kwargs):
        raise ConfigError("alias helper failure")

    monkeypatch.setattr(client.navigation, "resolve_alias", failing_resolve_alias)

    with pytest.raises(ConfigError, match="alias helper failure"):
        client.ResearchClient(output_dir=tmp_path).resolve_research_alias(
            "https://example.com/missing",
        )


def test_client_research_ok(monkeypatch, tmp_path):
    from h2t_ops.connectors.research import client as client_mod
    from h2t_ops.connectors.research import exa

    monkeypatch.setattr(client_mod, "resolve_secret", lambda name: "k")
    monkeypatch.setattr(
        client_mod.ResearchClient, "_require_research_route",
        lambda self, cap, provider=None: {"selected_provider": "exa"},
    )

    envelope = exa.build_research_envelope(
        status="OK", research_id="r_1", model="exa-research-fast", instructions="Q",
        output={"content": "Answer."}, citations=[{"url": "https://x", "title": "X"}],
        attempts=[{"engine": "exa", "endpoint": "/research/v1", "http": 201, "latency_ms": 0, "error": None}],
        cost=0.02, num_searches=3, num_pages=5, reasoning_tokens=900,
    )
    monkeypatch.setattr(exa, "research_task", lambda instructions, **kw: (envelope, 0))

    client = client_mod.ResearchClient(output_dir=tmp_path)
    result = client.research(instructions="Q", project="h2t-skills")

    assert result["kind"] == "research_provider_envelope"
    assert result["status"] == "OK"
    assert result["output"]["content"] == "Answer."
    assert "artifact" in result


def test_client_research_failed_raises(monkeypatch, tmp_path):
    from h2t_ops.connectors.research import client as client_mod
    from h2t_ops.connectors.research import exa
    from h2t_ops.core.errors import ProviderError

    monkeypatch.setattr(client_mod, "resolve_secret", lambda name: "k")
    monkeypatch.setattr(
        client_mod.ResearchClient, "_require_research_route",
        lambda self, cap, provider=None: {"selected_provider": "exa"},
    )

    envelope = exa.build_research_envelope(
        status="FAILED", research_id="r_1", model="exa-research-fast", instructions="Q",
        output=None, citations=[],
        attempts=[{"engine": "exa", "endpoint": "/research/v1", "http": 201, "latency_ms": 0, "error": None}],
        cost=0.0, num_searches=None, num_pages=None, reasoning_tokens=None,
        reason_for_fallback="research_timeout",
    )
    monkeypatch.setattr(exa, "research_task", lambda instructions, **kw: (envelope, 1))

    client = client_mod.ResearchClient(output_dir=tmp_path)
    with pytest.raises(ProviderError):
        client.research(instructions="Q", project="h2t-skills")


def test_client_research_get_completed(monkeypatch, tmp_path):
    from h2t_ops.connectors.research import client as client_mod
    from h2t_ops.connectors.research import exa

    monkeypatch.setattr(client_mod, "resolve_secret", lambda name: "k")
    monkeypatch.setattr(
        client_mod.ResearchClient, "_require_research_route",
        lambda self, cap, provider=None: {"selected_provider": "exa"},
    )
    envelope = exa.build_research_envelope(
        status="OK", research_id="r_1", model="exa-research-fast", instructions="Q",
        output={"content": "Answer."}, citations=[{"url": "https://x", "title": "X"}],
        attempts=[{"engine": "exa", "endpoint": "/research/v1/r_1", "http": 200, "latency_ms": 0, "error": None}],
        cost=0.01, num_searches=1, num_pages=1, reasoning_tokens=10,
    )
    monkeypatch.setattr(exa, "research_status", lambda rid, **kw: (envelope, 0))

    client = client_mod.ResearchClient(output_dir=tmp_path)
    result = client.research_get("r_1", project="h2t-skills")
    assert result["status"] == "OK"
    assert "artifact" in result


def test_client_research_get_running_no_artifact(monkeypatch, tmp_path):
    from h2t_ops.connectors.research import client as client_mod
    from h2t_ops.connectors.research import exa

    monkeypatch.setattr(client_mod, "resolve_secret", lambda name: "k")
    monkeypatch.setattr(
        client_mod.ResearchClient, "_require_research_route",
        lambda self, cap, provider=None: {"selected_provider": "exa"},
    )
    envelope = exa.build_research_envelope(
        status="RUNNING", research_id="r_1", model="exa-research-fast", instructions="Q",
        output=None, citations=[], attempts=[], cost=0.0,
        num_searches=None, num_pages=None, reasoning_tokens=None,
    )
    monkeypatch.setattr(exa, "research_status", lambda rid, **kw: (envelope, 0))

    client = client_mod.ResearchClient(output_dir=tmp_path)
    result = client.research_get("r_1")
    assert result["status"] == "RUNNING"
    assert "artifact" not in result


def test_client_research_get_not_found_raises(monkeypatch, tmp_path):
    from h2t_ops.connectors.research import client as client_mod
    from h2t_ops.connectors.research import exa
    from h2t_ops.core.errors import NotFoundError

    monkeypatch.setattr(client_mod, "resolve_secret", lambda name: "k")
    monkeypatch.setattr(
        client_mod.ResearchClient, "_require_research_route",
        lambda self, cap, provider=None: {"selected_provider": "exa"},
    )
    envelope = exa.build_research_envelope(
        status="FAILED", research_id="r_x", model="", instructions="",
        output=None, citations=[],
        attempts=[{"engine": "exa", "endpoint": "/research/v1/r_x", "http": 404, "latency_ms": 0, "error": "exa_not_found"}],
        cost=0.0, num_searches=None, num_pages=None, reasoning_tokens=None,
        reason_for_fallback="exa_not_found",
    )
    monkeypatch.setattr(exa, "research_status", lambda rid, **kw: (envelope, 5))

    client = client_mod.ResearchClient(output_dir=tmp_path)
    with pytest.raises(NotFoundError):
        client.research_get("r_x")
