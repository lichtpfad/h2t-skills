import os

import pytest

from h2t_ops.core import paths, secrets
from h2t_ops.core.errors import ConfigError


@pytest.fixture
def home(tmp_path, monkeypatch):
    h = tmp_path / "home"
    h.mkdir()
    monkeypatch.setenv("HOME", str(h))
    monkeypatch.setenv("USERPROFILE", str(h))
    for k in list(os.environ):
        if k.startswith(("H2T_PATH_", "EXA_", "JINA_", "NOTION_", "MEETGEEK_", "GRANOLA_",
                         "DROPBOX_", "TELEGRAM_", "H2T_EVALS_")) or k in paths.OLD_ENV:
            monkeypatch.delenv(k, raising=False)
    return h


def _w(p, text):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def test_new_provider_file_wins_and_legacy_is_not_read_for_that_provider(home):
    _w(paths.secrets_shared() / "exa.env", "EXA_API_KEY=fake-new\n")
    _w(paths.legacy("secrets.dor_old"), "EXA_API_KEY=fake-old\nNOTION_API_TOKEN=fake-notion\n")
    assert secrets.get("EXA_API_KEY") == "fake-new"
    assert secrets.get("NOTION_API_TOKEN") == "fake-notion"  # no notion.env yet: fallback


def test_migrated_provider_never_falls_back(home):
    _w(paths.secrets_shared() / "exa.env", "EXA_OTHER=fake\n")
    _w(paths.legacy("secrets.dor_old"), "EXA_API_KEY=fake-old\n")
    assert secrets.get("EXA_API_KEY") is None


def test_environment_beats_files(home, monkeypatch):
    _w(paths.secrets_shared() / "exa.env", "EXA_API_KEY=fake-file\n")
    monkeypatch.setenv("EXA_API_KEY", "fake-env")
    assert secrets.get("EXA_API_KEY") == "fake-env"


def test_legacy_ladder_order_is_3x_order(home):
    _w(paths.legacy("secrets.h2t") / "secrets.env", "MEETGEEK_API_KEY=fake-a\n")
    _w(paths.legacy("secrets.dor"), "MEETGEEK_API_KEY=fake-b\nGRANOLA_API_KEY=fake-g\n")
    assert secrets.get("MEETGEEK_API_KEY") == "fake-a"
    assert secrets.get("GRANOLA_API_KEY") == "fake-g"


def test_secrets_file_variable_is_not_read(home, monkeypatch, tmp_path):
    only = tmp_path / "only.env"
    _w(only, "GRANOLA_API_KEY=fake-only\n")
    _w(paths.legacy("secrets.dor"), "GRANOLA_API_KEY=fake-b\nMEETGEEK_API_KEY=fake-m\n")
    monkeypatch.setenv("H2T_SECRETS_FILE", str(only))      # 3.x name; 4.0 ignores it (R5)
    assert secrets.get("GRANOLA_API_KEY") == "fake-b"
    assert secrets.get("MEETGEEK_API_KEY") == "fake-m"
    assert only not in secrets.candidate_secret_files()


def test_foreign_env_files_are_not_candidates(home):
    _w(paths.secrets_shared() / "exa.env", "EXA_API_KEY=fake\n")
    _w(paths.secrets_shared() / "other.env", "ZZZ=fake\n")
    _w(paths.secrets_shared() / "getcourse.env", "EXA_API_KEY=fake-foreign\n")
    names = [p.name for p in secrets.candidate_secret_files()]
    assert "exa.env" in names and "other.env" in names and "getcourse.env" not in names


def test_env_parse_matches_3x_on_awkward_files():
    text = '\ufeffA=1\r\n# c\r\nexport B="two"\nC=\'three\'\n D = four \nbad line\n'
    assert secrets.parse_env(text) == {"A": "1", "B": "two", "C": "three", "D": "four"}


def test_load_secrets_merges_without_override(home, monkeypatch):
    _w(paths.secrets_shared() / "granola.env", "GRANOLA_API_KEY=fake-g\n")
    monkeypatch.setenv("GRANOLA_API_KEY", "fake-env")
    secrets.load_secrets()
    assert os.environ["GRANOLA_API_KEY"] == "fake-env"


def test_google_json_new_then_legacy(home):
    _w(paths.legacy("google.store") / "tokens.json", '{"refresh_token": "fake-old"}')
    data, where = secrets.read_json("google.token")
    assert data == {"refresh_token": "fake-old"} and where.name == "tokens.json"
    secrets.write_json("google.token", {"refresh_token": "fake-new"})
    data, where = secrets.read_json("google.token")
    assert data == {"refresh_token": "fake-new"} and where == paths.secrets_local() / "google.token.json"


def test_notion_token_file_is_last_resort(home):
    _w(paths.legacy("notion.token"), "fake-file-token\n")
    assert secrets.resolve_notion_token() == "fake-file-token"
    _w(paths.secrets_shared() / "notion.env", "NOTION_API_TOKEN=fake-env-file\n")
    assert secrets.resolve_notion_token() == "fake-env-file"


# --- readers for the migration (R38) ---------------------------------------------------------

def test_migration_sources_name_a_ladder_file_once_at_the_senior_place(home, monkeypatch):
    dor = paths.legacy("secrets.dor")
    _w(dor, "MEETGEEK_API_KEY=fake-m\n")
    _w(paths.legacy("secrets.dor_old"), "GRANOLA_API_KEY=fake-g\n")
    monkeypatch.setenv("H2T_SECRETS_FILE", str(dor))
    got = secrets.migration_sources()
    assert [(n, p) for n, p, _ in got] == [("secretsfile", dor), ("dor", paths.legacy("secrets.dor_old"))]
    assert got[0][2] == {"MEETGEEK_API_KEY": "fake-m"}


def test_shared_env_values_without_a_directory_is_empty(home):
    assert secrets.shared_env_values() == {}
    _w(paths.secrets_shared() / "exa.env.from-dor", "EXA_API_KEY=fake\n")
    _w(paths.secrets_shared() / "google.client.json", "{}")
    assert secrets.shared_env_values() == {"exa.env.from-dor": {"EXA_API_KEY": "fake"}}


def test_read_secret_bytes_refuses_a_path_outside_the_secret_places(home):
    notes = home / "notes.txt"
    _w(notes, "fake-notes")
    with pytest.raises(ConfigError):
        secrets.read_secret_bytes(notes)
    _w(paths.legacy("telegram") / "config.json", "{}")
    assert secrets.read_secret_bytes(paths.legacy("telegram") / "config.json") == b"{}"
    assert secrets.read_secret_bytes(notes, root=home) == b"fake-notes"
