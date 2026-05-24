"""Tests for secrets skeleton and preflight in setup_h2t.py."""
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


# --- _load_known_secrets tests ---

def test_load_known_secrets_file_not_found(tmp_path):
    with pytest.raises(FileNotFoundError):
        setup_h2t._load_known_secrets(tmp_path / "nonexistent.yaml")


def test_load_known_secrets_starts_with_value(tmp_path):
    yaml_content = 'NOTION_API_TOKEN:\n  validator: "starts_with:secret_"\n  connector: notion\n'
    f = tmp_path / "known_secrets.yaml"
    f.write_text(yaml_content)
    result = setup_h2t._load_known_secrets(f)
    assert result["NOTION_API_TOKEN"]["validator"] == "starts_with:secret_"
    assert result["NOTION_API_TOKEN"]["connector"] == "notion"


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


# --- secrets_preflight tests ---

def test_preflight_found_and_uuid_valid(tmp_path):
    # Write to canonical secrets path under tmp_path home
    secrets_dir = tmp_path / ".dor" / "secrets"
    secrets_dir.mkdir(parents=True)
    (secrets_dir / "secrets.env").write_text("EXA_API_KEY=12345678-1234-1234-1234-123456789012\n")
    registry = {"EXA_API_KEY": {"validator": "uuid", "connector": "research", "description": "", "url": ""}}
    result = setup_h2t.secrets_preflight(registry, home=tmp_path)
    assert result["kind"] == "h2t_secrets_preflight/v1"
    r = result["results"][0]
    assert r["key"] == "EXA_API_KEY"
    assert r["found"] is True
    assert r["valid"] is True
    assert r["connector"] == "research"


def test_preflight_invalid_uuid(tmp_path, monkeypatch):
    monkeypatch.delenv("EXA_API_KEY", raising=False)
    secrets_dir = tmp_path / ".dor" / "secrets"
    secrets_dir.mkdir(parents=True)
    (secrets_dir / "secrets.env").write_text("EXA_API_KEY=not-a-uuid\n")
    registry = {"EXA_API_KEY": {"validator": "uuid", "connector": "research", "description": "", "url": ""}}
    result = setup_h2t.secrets_preflight(registry, home=tmp_path)
    assert result["results"][0]["found"] is True
    assert result["results"][0]["valid"] is False


def test_preflight_starts_with_validator(tmp_path):
    secrets_dir = tmp_path / ".dor" / "secrets"
    secrets_dir.mkdir(parents=True)
    (secrets_dir / "secrets.env").write_text("NOTION_API_TOKEN=secret_abc123\n")
    registry = {"NOTION_API_TOKEN": {"validator": "starts_with:secret_", "connector": "notion", "description": "", "url": ""}}
    result = setup_h2t.secrets_preflight(registry, home=tmp_path)
    assert result["results"][0]["valid"] is True


def test_preflight_starts_with_invalid(tmp_path):
    secrets_dir = tmp_path / ".dor" / "secrets"
    secrets_dir.mkdir(parents=True)
    (secrets_dir / "secrets.env").write_text("NOTION_API_TOKEN=wrong_prefix\n")
    registry = {"NOTION_API_TOKEN": {"validator": "starts_with:secret_", "connector": "notion", "description": "", "url": ""}}
    result = setup_h2t.secrets_preflight(registry, home=tmp_path)
    assert result["results"][0]["valid"] is False


def test_preflight_missing_key(tmp_path, monkeypatch):
    monkeypatch.delenv("EXA_API_KEY", raising=False)
    secrets_dir = tmp_path / ".dor" / "secrets"
    secrets_dir.mkdir(parents=True)
    (secrets_dir / "secrets.env").write_text("OTHER_KEY=value\n")
    registry = {"EXA_API_KEY": {"validator": "uuid", "connector": "research", "description": "", "url": ""}}
    result = setup_h2t.secrets_preflight(registry, home=tmp_path)
    assert result["results"][0]["found"] is False
    assert result["results"][0]["valid"] is False


def test_preflight_honors_env_var(tmp_path, monkeypatch):
    """Resolution chain: os.environ takes precedence over secrets file."""
    monkeypatch.setenv("EXA_API_KEY", "12345678-1234-1234-1234-123456789012")
    registry = {"EXA_API_KEY": {"validator": "uuid", "connector": "research", "description": "", "url": ""}}
    result = setup_h2t.secrets_preflight(registry, home=tmp_path)
    assert result["results"][0]["found"] is True
    assert result["results"][0]["valid"] is True


def test_preflight_honors_legacy_path(tmp_path):
    """Resolution chain: legacy ~/.dor/secrets.env is a valid fallback."""
    legacy = tmp_path / ".dor" / "secrets.env"
    legacy.parent.mkdir(parents=True)
    legacy.write_text("EXA_API_KEY=12345678-1234-1234-1234-123456789012\n")
    registry = {"EXA_API_KEY": {"validator": "uuid", "connector": "research", "description": "", "url": ""}}
    result = setup_h2t.secrets_preflight(registry, home=tmp_path)
    assert result["results"][0]["found"] is True


def test_preflight_no_values_in_output(tmp_path):
    """Security: key values must never appear in the result JSON."""
    import json
    secrets_dir = tmp_path / ".dor" / "secrets"
    secrets_dir.mkdir(parents=True)
    secret_value = "12345678-1234-1234-1234-123456789012"
    (secrets_dir / "secrets.env").write_text(f"EXA_API_KEY={secret_value}\n")
    registry = {"EXA_API_KEY": {"validator": "uuid", "connector": "research", "description": "", "url": ""}}
    result = setup_h2t.secrets_preflight(registry, home=tmp_path)
    assert secret_value not in json.dumps(result)


def test_preflight_nonempty_validator(tmp_path):
    secrets_dir = tmp_path / ".dor" / "secrets"
    secrets_dir.mkdir(parents=True)
    (secrets_dir / "secrets.env").write_text("MEETGEEK_API_KEY=anything\n")
    registry = {"MEETGEEK_API_KEY": {"validator": "nonempty", "connector": "meetgeek", "description": "", "url": ""}}
    result = setup_h2t.secrets_preflight(registry, home=tmp_path)
    assert result["results"][0]["valid"] is True


def test_preflight_nonempty_fails_empty(tmp_path):
    secrets_dir = tmp_path / ".dor" / "secrets"
    secrets_dir.mkdir(parents=True)
    (secrets_dir / "secrets.env").write_text("MEETGEEK_API_KEY=\n")
    registry = {"MEETGEEK_API_KEY": {"validator": "nonempty", "connector": "meetgeek", "description": "", "url": ""}}
    result = setup_h2t.secrets_preflight(registry, home=tmp_path)
    assert result["results"][0]["found"] is False
    assert result["results"][0]["valid"] is False


def test_preflight_live_calls_runner(tmp_path, monkeypatch):
    monkeypatch.setenv("EXA_API_KEY", "12345678-1234-1234-1234-123456789012")
    registry = {"EXA_API_KEY": {"validator": "uuid", "connector": "research", "description": "", "url": ""}}
    calls = []
    def fake_runner(cmd, timeout):
        calls.append(cmd)
        return {"exit_code": 0, "stdout": '{"ok": true}', "stderr": ""}
    result = setup_h2t.secrets_preflight(registry, home=tmp_path, live=True, runner=fake_runner)
    assert result["results"][0]["live"]["status"] == "ok"
    assert any("research" in str(c) for c in calls)
