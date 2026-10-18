"""Tests for secrets skeleton and preflight in setup_h2t.py."""

import pytest

from h2t_ops.core import paths
from h2t_ops.setup import legacy as setup_h2t

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

@pytest.fixture(autouse=True)
def _no_real_secrets(tmp_path, monkeypatch):
    """skeleton and preflight read through core.secrets, whose places hang off HOME (#548)."""
    monkeypatch.setattr(setup_h2t, "_home", lambda: tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.delenv("H2T_PATH_ROOT", raising=False)
    monkeypatch.delenv("H2T_SECRETS_FILE", raising=False)
    for key in (*REGISTRY, "GRANOLA_API_KEY", "ZZZ_KEY"):
        monkeypatch.delenv(key, raising=False)


def _env_keys(path):
    from h2t_ops.core import secrets
    return secrets.parse_env(path.read_text(encoding="utf-8"))


def test_skeleton_skips_a_key_the_connectors_read_elsewhere(tmp_path):
    """A key kept only in the 3.x per-provider file is not missing (#524)."""
    documented = paths.legacy("secrets.h2t")
    documented.mkdir(parents=True)
    (documented / "notion.env").write_text("NOTION_API_TOKEN=fake-secret_x\n", encoding="utf-8")
    out = tmp_path / "sk"

    result = setup_h2t.secrets_skeleton(REGISTRY, secrets_dir=out)

    assert "NOTION_API_TOKEN" not in result["added"]
    assert "NOTION_API_TOKEN" in result["skipped"]
    assert not (out / "notion.env").exists()


def test_skeleton_still_adds_a_key_set_nowhere(tmp_path):
    result = setup_h2t.secrets_skeleton(REGISTRY, secrets_dir=tmp_path / "sk")

    assert set(result["added"]) == set(REGISTRY)


def test_skeleton_creates_files_when_absent(tmp_path):
    out = tmp_path / "sk"
    result = setup_h2t.secrets_skeleton(REGISTRY, secrets_dir=out)
    assert result["kind"] == "h2t_secrets_skeleton/v1"
    assert set(result["added"]) == {"EXA_API_KEY", "NOTION_API_TOKEN", "MEETGEEK_API_KEY"}
    assert result["skipped"] == []
    assert _env_keys(out / "exa.env") == {"EXA_API_KEY": ""}
    assert _env_keys(out / "notion.env") == {"NOTION_API_TOKEN": ""}
    assert _env_keys(out / "meetgeek.env") == {"MEETGEEK_API_KEY": ""}


def test_skeleton_writes_one_file_per_provider(tmp_path):
    registry = {k: REGISTRY[k] for k in ("EXA_API_KEY", "NOTION_API_TOKEN")}
    registry["ZZZ_KEY"] = {"description": "No provider", "url": "", "validator": "nonempty", "connector": ""}
    out = tmp_path / "sk"

    result = setup_h2t.secrets_skeleton(registry, secrets_dir=out)

    assert sorted(p.name for p in out.iterdir()) == ["exa.env", "notion.env", "other.env"]
    assert result["files"] == {
        "exa.env": {"path": str(out / "exa.env"), "added": ["EXA_API_KEY"]},
        "notion.env": {"path": str(out / "notion.env"), "added": ["NOTION_API_TOKEN"]},
        "other.env": {"path": str(out / "other.env"), "added": ["ZZZ_KEY"]},
    }
    assert _env_keys(out / "other.env") == {"ZZZ_KEY": ""}
    before = {p.name: p.read_bytes() for p in out.iterdir()}
    again = setup_h2t.secrets_skeleton(registry, secrets_dir=out)
    assert again["added"] == [] and again["files"] == {}
    assert {p.name: p.read_bytes() for p in out.iterdir()} == before


def test_skeleton_skips_a_key_in_the_old_dor_file(tmp_path):
    old = paths.legacy("secrets.dor_old")
    old.parent.mkdir(parents=True)
    old.write_text("EXA_API_KEY=fake-old-exa\n", encoding="utf-8")
    result = setup_h2t.secrets_skeleton(REGISTRY, secrets_dir=tmp_path / "sk")
    assert "EXA_API_KEY" in result["skipped"] and "EXA_API_KEY" not in result["added"]


def test_skeleton_defaults_to_secrets_shared():
    result = setup_h2t.secrets_skeleton(REGISTRY)
    assert result["path"] == str(paths.secrets_shared())
    assert _env_keys(paths.secrets_shared() / "exa.env") == {"EXA_API_KEY": ""}


def test_skeleton_values_are_empty(tmp_path):
    out = tmp_path / "sk"
    setup_h2t.secrets_skeleton(REGISTRY, secrets_dir=out)
    for f in out.iterdir():
        assert all(v == "" for v in _env_keys(f).values()), f.name


def test_skeleton_keeps_existing_lines_and_comments(tmp_path):
    out = tmp_path / "sk"
    out.mkdir()
    (out / "notion.env").write_text("# mine\nNOTION_OTHER=keep", encoding="utf-8")   # no final newline
    result = setup_h2t.secrets_skeleton(REGISTRY, secrets_dir=out)
    assert "NOTION_API_TOKEN" in result["added"]
    text = (out / "notion.env").read_text(encoding="utf-8")
    assert text.startswith("# mine\nNOTION_OTHER=keep\n")
    assert _env_keys(out / "notion.env") == {"NOTION_OTHER": "keep", "NOTION_API_TOKEN": ""}


def test_skeleton_does_not_repeat_an_empty_line_already_there(tmp_path):
    out = tmp_path / "sk"
    out.mkdir()
    (out / "exa.env").write_text("EXA_API_KEY=\n", encoding="utf-8")
    result = setup_h2t.secrets_skeleton(REGISTRY, secrets_dir=out)
    assert "EXA_API_KEY" not in result["added"]
    assert (out / "exa.env").read_text(encoding="utf-8") == "EXA_API_KEY=\n"


def test_skeleton_result_path_is_str(tmp_path):
    result = setup_h2t.secrets_skeleton(REGISTRY, secrets_dir=tmp_path / "sk")
    assert isinstance(result["path"], str)


def test_skeleton_refuses_a_directory_inside_a_package_place():
    from h2t_ops.core import store
    with pytest.raises(store.WriteRefused):
        setup_h2t.secrets_skeleton(REGISTRY, secrets_dir=paths.state_dir() / "sk")


# --- secrets_preflight tests ---

def test_preflight_found_and_uuid_valid(tmp_path, monkeypatch):
    monkeypatch.delenv("EXA_API_KEY", raising=False)
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


def test_preflight_starts_with_validator(tmp_path, monkeypatch):
    monkeypatch.delenv("NOTION_API_TOKEN", raising=False)
    secrets_dir = tmp_path / ".dor" / "secrets"
    secrets_dir.mkdir(parents=True)
    (secrets_dir / "secrets.env").write_text("NOTION_API_TOKEN=secret_abc123\n")
    registry = {"NOTION_API_TOKEN": {"validator": "starts_with:secret_", "connector": "notion", "description": "", "url": ""}}
    result = setup_h2t.secrets_preflight(registry, home=tmp_path)
    assert result["results"][0]["valid"] is True


def test_preflight_starts_with_invalid(tmp_path, monkeypatch):
    monkeypatch.delenv("NOTION_API_TOKEN", raising=False)
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


def test_preflight_honors_legacy_path(tmp_path, monkeypatch):
    monkeypatch.delenv("EXA_API_KEY", raising=False)
    """Resolution chain: legacy ~/.dor/secrets.env is a valid fallback."""
    legacy = tmp_path / ".dor" / "secrets.env"
    legacy.parent.mkdir(parents=True)
    legacy.write_text("EXA_API_KEY=12345678-1234-1234-1234-123456789012\n")
    registry = {"EXA_API_KEY": {"validator": "uuid", "connector": "research", "description": "", "url": ""}}
    result = setup_h2t.secrets_preflight(registry, home=tmp_path)
    assert result["results"][0]["found"] is True


def test_preflight_no_values_in_output(tmp_path, monkeypatch):
    monkeypatch.delenv("EXA_API_KEY", raising=False)
    """Security: key values must never appear in the result JSON."""
    import json
    secrets_dir = tmp_path / ".dor" / "secrets"
    secrets_dir.mkdir(parents=True)
    secret_value = "12345678-1234-1234-1234-123456789012"
    (secrets_dir / "secrets.env").write_text(f"EXA_API_KEY={secret_value}\n")
    registry = {"EXA_API_KEY": {"validator": "uuid", "connector": "research", "description": "", "url": ""}}
    result = setup_h2t.secrets_preflight(registry, home=tmp_path)
    assert secret_value not in json.dumps(result)


def test_preflight_nonempty_validator(tmp_path, monkeypatch):
    monkeypatch.delenv("MEETGEEK_API_KEY", raising=False)
    secrets_dir = tmp_path / ".dor" / "secrets"
    secrets_dir.mkdir(parents=True)
    (secrets_dir / "secrets.env").write_text("MEETGEEK_API_KEY=anything\n")
    registry = {"MEETGEEK_API_KEY": {"validator": "nonempty", "connector": "meetgeek", "description": "", "url": ""}}
    result = setup_h2t.secrets_preflight(registry, home=tmp_path)
    assert result["results"][0]["valid"] is True


def test_preflight_nonempty_fails_empty(tmp_path, monkeypatch):
    monkeypatch.delenv("MEETGEEK_API_KEY", raising=False)
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
