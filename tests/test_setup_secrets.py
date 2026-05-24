"""Tests for secrets skeleton and preflight in setup_h2t.py."""
import json
import sys
from pathlib import Path

import pytest

# setup_h2t.py is standalone — add its directory to sys.path
SCRIPTS_DIR = Path(__file__).parent.parent / "plugins" / "h2t-core" / "skills" / "setup" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import setup_h2t  # noqa: E402


REGISTRY = {
    "EXA_API_KEY": {
        "description": "Exa key",
        "url": "https://dashboard.exa.ai/api-keys",
        "validator": "uuid",
        "connector": "research",
    },
    "NOTION_API_TOKEN": {
        "description": "Notion token",
        "url": "https://www.notion.so/profile/integrations",
        "validator": "starts_with:secret_",
        "connector": "notion",
    },
    "MEETGEEK_API_KEY": {
        "description": "MeetGeek key",
        "url": "https://app.meetgeek.ai/settings/api",
        "validator": "nonempty",
        "connector": "meetgeek",
    },
}


# --- secrets_skeleton tests ---

def test_skeleton_creates_file_when_absent(tmp_path):
    secrets_file = tmp_path / "secrets.env"
    result = setup_h2t.secrets_skeleton(secrets_file, REGISTRY)
    assert result["kind"] == "h2t_secrets_skeleton/v1"
    assert set(result["added"]) == {"EXA_API_KEY", "NOTION_API_TOKEN", "MEETGEEK_API_KEY"}
    assert result["skipped"] == []
    assert secrets_file.is_file()
    content = secrets_file.read_text()
    assert "EXA_API_KEY=" in content
    assert "NOTION_API_TOKEN=" in content
    assert "MEETGEEK_API_KEY=" in content


def test_skeleton_values_are_empty(tmp_path):
    secrets_file = tmp_path / "secrets.env"
    setup_h2t.secrets_skeleton(secrets_file, REGISTRY)
    for line in secrets_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            assert line.split("=", 1)[1] == "", f"Value should be empty: {line}"


def test_skeleton_skips_existing_keys(tmp_path):
    secrets_file = tmp_path / "secrets.env"
    secrets_file.write_text("EXA_API_KEY=some-existing-value\n")
    result = setup_h2t.secrets_skeleton(secrets_file, REGISTRY)
    assert "EXA_API_KEY" in result["skipped"]
    assert "NOTION_API_TOKEN" in result["added"]
    assert "MEETGEEK_API_KEY" in result["added"]
    # Existing value must be preserved
    assert "EXA_API_KEY=some-existing-value" in secrets_file.read_text()


def test_skeleton_creates_parent_dir(tmp_path):
    secrets_file = tmp_path / "new_dir" / "secrets.env"
    setup_h2t.secrets_skeleton(secrets_file, REGISTRY)
    assert secrets_file.is_file()


def test_skeleton_result_path_is_str(tmp_path):
    secrets_file = tmp_path / "secrets.env"
    result = setup_h2t.secrets_skeleton(secrets_file, REGISTRY)
    assert isinstance(result["path"], str)
