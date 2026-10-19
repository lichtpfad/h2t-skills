import os

import pytest

from h2t_ops.core import paths, secrets
from h2t_ops.core.errors import ConfigError, UsageError


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


def test_new_provider_file_wins_and_legacy_fills_what_it_lacks(home):
    _w(paths.secrets_shared() / "exa.env", "EXA_API_KEY=fake-new\n")
    _w(paths.legacy("secrets.dor_old"), "EXA_API_KEY=fake-old\nNOTION_API_TOKEN=fake-notion\n")
    assert secrets.get("EXA_API_KEY") == "fake-new"
    assert secrets.get("NOTION_API_TOKEN") == "fake-notion"  # no notion.env yet: fallback


def test_fallback_is_per_key_not_per_file(home):
    """A key absent or empty in <provider>.env is not migrated: the skeleton writes empty
    KEY= lines, and a file-level rule would break a working 3.x key (Task 10 ruling)."""
    _w(paths.secrets_shared() / "exa.env", "EXA_OTHER=fake-exa-other\nJINA_X=\n")
    _w(paths.secrets_shared() / "jina.env", "JINA_API_KEY=\n")
    _w(paths.legacy("secrets.dor_old"), "EXA_API_KEY=fake-old\nJINA_API_KEY=fake-old-jina\n")
    assert secrets.get("EXA_API_KEY") == "fake-old"
    assert secrets.get("JINA_API_KEY") == "fake-old-jina"
    assert secrets.get("EXA_OTHER") == "fake-exa-other"


def test_empty_everywhere_is_absent(home):
    _w(paths.secrets_shared() / "exa.env", "EXA_API_KEY=\n")
    _w(paths.legacy("secrets.dor_old"), "EXA_API_KEY=\n")
    assert secrets.get("EXA_API_KEY") is None


def test_load_secrets_falls_back_per_key(home, monkeypatch):
    monkeypatch.delenv("EXA_API_KEY", raising=False)
    _w(paths.secrets_shared() / "exa.env", "EXA_API_KEY=\n")
    _w(paths.legacy("secrets.dor_old"), "EXA_API_KEY=fake-old\n")
    secrets.load_secrets()
    assert os.environ["EXA_API_KEY"] == "fake-old"


def test_empty_notion_key_in_new_file_falls_back_to_the_token_file(home):
    _w(paths.secrets_shared() / "notion.env", "NOTION_API_TOKEN=\n")
    _w(paths.legacy("notion.token"), "fake-old-notion\n")
    assert secrets.resolve_notion_token() == "fake-old-notion"


def test_new_notion_value_beats_the_token_file(home):
    _w(paths.secrets_shared() / "notion.env", "NOTION_API_TOKEN=fake-new-notion\n")
    _w(paths.legacy("notion.token"), "fake-old-notion\n")
    assert secrets.resolve_notion_token() == "fake-new-notion"


def test_new_value_beats_the_legacy_ladder(home):
    _w(paths.secrets_shared() / "meetgeek.env", "MEETGEEK_API_KEY=fake-new\n")
    _w(paths.legacy("secrets.h2t") / "secrets.env", "MEETGEEK_API_KEY=fake-old\n")
    assert secrets.get("MEETGEEK_API_KEY") == "fake-new"


# --- evals_env (R33): H2T_EVALS_* by prefix ---------------------------------------------------

def test_evals_env_order_is_env_new_dor_then_ladder(home, monkeypatch):
    _w(paths.secrets_shared() / "h2t-evals.env", "H2T_EVALS_TOKEN=fake-new\nH2T_EVALS_RUN_ENV=\n")
    _w(paths.legacy("secrets.dor_old"), "H2T_EVALS_TOKEN=fake-dor\nH2T_EVALS_RUN_ENV=fake-dor-run\n"
                                        "H2T_EVALS_SERVICE_URL=fake-dor-url\n")
    _w(paths.legacy("secrets.h2t") / "secrets.env", "H2T_EVALS_SERVICE_URL=fake-h2t-url\n"
                                                    "H2T_EVALS_MODE=fake-ladder-mode\n")
    monkeypatch.setenv("H2T_EVALS_MODE", "local")
    assert secrets.evals_env() == {"H2T_EVALS_TOKEN": "fake-new", "H2T_EVALS_RUN_ENV": "fake-dor-run",
                                   "H2T_EVALS_SERVICE_URL": "fake-dor-url", "H2T_EVALS_MODE": "local"}


def test_evals_env_drops_path_variables_and_foreign_keys(home, monkeypatch):
    _w(paths.secrets_shared() / "h2t-evals.env", "H2T_EVALS_TOKEN=fake-t\n")
    _w(paths.legacy("secrets.dor_old"), "H2T_EVALS_SPOOL=/x/spool.db\nEXA_API_KEY=fake-exa\n")
    monkeypatch.setenv("H2T_EVALS_ROOT", "/x/evals")
    assert secrets.evals_env() == {"H2T_EVALS_TOKEN": "fake-t"}


def test_evals_env_with_a_file_reads_only_it_and_the_environment(home, monkeypatch, tmp_path):
    _w(paths.secrets_shared() / "h2t-evals.env", "H2T_EVALS_TOKEN=fake-new\n")
    only = tmp_path / "only.env"
    _w(only, "H2T_EVALS_SERVICE_URL=fake-only-url\n")
    monkeypatch.setenv("H2T_EVALS_RUN_ENV", "fake-env-run")
    assert secrets.evals_env(env_file=only) == {"H2T_EVALS_SERVICE_URL": "fake-only-url",
                                                "H2T_EVALS_RUN_ENV": "fake-env-run"}


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
    _w(paths.secrets_shared() / "exa.env", "EXA_API_KEY=fake-exa\n")
    _w(paths.secrets_shared() / "other.env", "ZZZ=fake-zzz\n")
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
    _w(paths.secrets_shared() / "exa.env.from-dor", "EXA_API_KEY=fake-from-dor\n")
    _w(paths.secrets_shared() / "google.client.json", "{}")
    assert secrets.shared_env_values() == {"exa.env.from-dor": {"EXA_API_KEY": "fake-from-dor"}}


def test_read_secret_bytes_refuses_a_path_outside_the_secret_places(home):
    notes = home / "notes.txt"
    _w(notes, "fake-notes")
    with pytest.raises(ConfigError):
        secrets.read_secret_bytes(notes)
    _w(paths.legacy("telegram") / "config.json", "{}")
    assert secrets.read_secret_bytes(paths.legacy("telegram") / "config.json") == b"{}"
    assert secrets.read_secret_bytes(notes, root=home) == b"fake-notes"


# --- write_env keeps to the §4 naming contract -------------------------------------------------

def test_write_env_round_trips_through_get(home):
    secrets.write_env("exa", {"EXA_API_KEY": "fake-exa-written"})
    secrets.write_env("other", {"ZZZ_TOKEN": "fake-other-written"})
    assert secrets.get("EXA_API_KEY") == "fake-exa-written"
    assert secrets.get("ZZZ_TOKEN") == "fake-other-written"


@pytest.mark.parametrize("provider, values", [
    ("getcourse", {"GETCOURSE_KEY": "fake-foreign"}),        # not a package provider
    ("../exa", {"EXA_API_KEY": "fake-traversal"}),            # path separator
    ("exa", {"JINA_API_KEY": "fake-wrong-prefix"}),           # key of another provider
    ("exa", {"EXA_API_KEY": "fake-line\nNOTION_API_TOKEN=fake-injected"}),
])
def test_write_env_rejects_non_contract_writes(home, provider, values):
    with pytest.raises(UsageError):
        secrets.write_env(provider, values)
    assert not paths.secrets_shared().exists() or not any(paths.secrets_shared().iterdir())
