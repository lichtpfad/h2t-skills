"""Unit tests for SkillGraphClient — all HTTP mocked."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "lib"))

import os
import json
import pytest
from unittest.mock import patch, mock_open, MagicMock


def test_load_secrets_from_env_file(tmp_path):
    secrets_file = tmp_path / "secrets.env"
    secrets_file.write_text(
        "H2T_SKILL_GRAPH_TOKEN_RO=ro-test-token\n"
        "H2T_SKILL_GRAPH_TOKEN_RW=rw-test-token\n"
        "H2T_SKILL_GRAPH_PROJECT_ID=abc123\n"
        "H2T_GRAPHS_URL=https://test.example.com\n"
    )
    from skill_graph.client import _load_secrets
    secrets = _load_secrets(secrets_path=str(secrets_file))
    assert secrets["H2T_SKILL_GRAPH_TOKEN_RO"] == "ro-test-token"
    assert secrets["H2T_SKILL_GRAPH_TOKEN_RW"] == "rw-test-token"
    assert secrets["H2T_SKILL_GRAPH_PROJECT_ID"] == "abc123"
    assert secrets["H2T_GRAPHS_URL"] == "https://test.example.com"


def test_load_secrets_falls_back_to_env(tmp_path, monkeypatch):
    monkeypatch.setenv("H2T_SKILL_GRAPH_TOKEN_RO", "env-ro")
    monkeypatch.setenv("H2T_SKILL_GRAPH_TOKEN_RW", "env-rw")
    monkeypatch.setenv("H2T_SKILL_GRAPH_PROJECT_ID", "proj-123")
    from skill_graph.client import _load_secrets
    secrets = _load_secrets(secrets_path=str(tmp_path / "nonexistent.env"))
    assert secrets["H2T_SKILL_GRAPH_TOKEN_RO"] == "env-ro"
    assert secrets["H2T_SKILL_GRAPH_TOKEN_RW"] == "env-rw"
    assert secrets["H2T_SKILL_GRAPH_PROJECT_ID"] == "proj-123"


def _make_client(url="https://test.example.com", ro="ro-tok", rw="rw-tok", project_id="proj-test"):
    from skill_graph.client import SkillGraphClient
    client = SkillGraphClient(url=url, secrets_path="/nonexistent")
    client._secrets = {
        "H2T_SKILL_GRAPH_TOKEN_RO": ro,
        "H2T_SKILL_GRAPH_TOKEN_RW": rw,
        "H2T_SKILL_GRAPH_PROJECT_ID": project_id,
    }
    client._project_id = project_id
    return client


def _mock_urlopen(response_data: dict):
    """Return a context manager mock that yields a response with json data."""
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(response_data).encode()
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


def test_query_uses_ro_token():
    client = _make_client()
    fake_resp = {"results": [{"id": "p1", "score": 0.9, "title": "Hook pattern"}]}
    with patch("urllib.request.urlopen", return_value=_mock_urlopen(fake_resp)) as mock_open:
        results = client.query("hook injection", sources=("skill-patterns",))
    call_args = mock_open.call_args[0][0]
    assert call_args.get_header("X-h2t-token") == "ro-tok"


def test_query_sends_semantic_param():
    client = _make_client()
    fake_resp = {"results": []}
    with patch("urllib.request.urlopen", return_value=_mock_urlopen(fake_resp)) as m:
        client.query("my context", sources=("skill-patterns",))
    url = m.call_args[0][0].full_url
    assert "semantic=my+context" in url or "semantic=my%20context" in url
    # source param must be project-scoped: {project_id}-{alias}
    assert "source=proj-test-skill-patterns" in url


def test_query_merges_sources_and_returns_top_k():
    client = _make_client()
    resp_patterns = {"results": [
        {"id": "p1", "score": 0.9},
        {"id": "p2", "score": 0.5},
    ]}
    resp_lessons = {"results": [
        {"id": "l1", "score": 0.8},
    ]}
    responses = [_mock_urlopen(resp_patterns), _mock_urlopen(resp_lessons)]
    with patch("urllib.request.urlopen", side_effect=responses):
        results = client.query("test", sources=("skill-patterns", "skill-lessons"), top_k=2)
    assert len(results) == 2
    assert results[0]["id"] == "p1"   # highest score first
    assert results[1]["id"] == "l1"


def test_query_silent_on_http_error():
    client = _make_client()
    import urllib.error
    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("timeout")):
        results = client.query("test")  # must not raise
    assert results == []
