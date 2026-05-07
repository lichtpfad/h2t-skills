"""Tests for fetch_url.py — provider ladder CLI for h2t-ops:research skill.

Spec: docs/superpowers/specs/2026-05-07-research-fetch-url-ladder.md
Issue: lichtpfad/h2t-skills#103
"""
from __future__ import annotations

import io
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Make script importable as a module.
SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import fetch_url  # noqa: E402


def test_fetch_url_module_imports():
    assert hasattr(fetch_url, "__version__")
    assert fetch_url.__version__ == "0.0.1"


def test_build_fetch_envelope_minimal_failed():
    env = fetch_url.build_fetch_envelope(
        status="FAILED",
        url="https://example.com/x",
        final_url=None,
        provider_used="none",
        content_type="unknown",
        content_gate="none",
        title=None,
        body_markdown="",
        body_text="",
        body_chars=0,
        links=[],
        attempts=[],
        providers_skipped={},
        reason_for_failed="all_providers_failed",
        reason_for_degraded=None,
        raw_html_path=None,
        site=None,
        canonical_url=None,
        lang=None,
        detected_reason=None,
        user_agent="ua/test",
    )
    assert env["status"] == "FAILED"
    assert env["url"] == "https://example.com/x"
    assert env["provider_used"] == "none"
    assert env["meta"]["primary_engine"] == "fetch_ladder"
    assert env["meta"]["envelope_version"] == "1"
    assert env["meta"]["fetch_envelope_version"] == "1"
    assert env["telemetry"]["total_latency_ms"] == 0
    assert env["telemetry"]["reason_for_failed"] == "all_providers_failed"
    assert env["metadata"]["raw_html_path"] is None


def test_build_fetch_envelope_ok_with_attempts_sums_latency():
    attempts = [
        {"provider": "direct", "http": 403, "latency_ms": 100, "error": "fetch_http_4xx_nonretryable"},
        {"provider": "jina", "http": 200, "latency_ms": 250, "error": None},
    ]
    env = fetch_url.build_fetch_envelope(
        status="OK",
        url="https://example.com/x",
        final_url="https://example.com/x",
        provider_used="jina",
        content_type="article",
        content_gate="none",
        title="Hello",
        body_markdown="# Hello\n\nWorld",
        body_text="Hello\n\nWorld",
        body_chars=12,
        links=[],
        attempts=attempts,
        providers_skipped={"playwright": "not_configured_stub"},
        reason_for_failed=None,
        reason_for_degraded=None,
        raw_html_path=None,
        site="example.com",
        canonical_url=None,
        lang=None,
        detected_reason=None,
        user_agent="ua/test",
    )
    assert env["telemetry"]["total_latency_ms"] == 350
    assert env["telemetry"]["providers_skipped"] == ["playwright"]
    assert env["telemetry"]["providers_skipped_reason"] == {"playwright": "not_configured_stub"}
    assert env["provider_used"] == "jina"
    assert env["title"] == "Hello"
