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
