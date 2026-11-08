"""The settings table: env -> file -> default, and which one answered (#581)."""
import json

import pytest

from h2t_ops.core import paths, settings
from h2t_ops.core.errors import ConfigError, UsageError
from h2t_ops.core.settings import KEYS

ENV_KEYS = [k for k in KEYS if k.env]
ALL_ENV = [k.env for k in ENV_KEYS]


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for var in (*ALL_ENV, "DOR_MACHINE_NAME", "H2T_EVALS_MODE", "H2T_EVALS_TOKEN"):
        monkeypatch.delenv(var, raising=False)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.mark.parametrize("key", ENV_KEYS, ids=lambda k: k.name)
def test_each_env_key_reads_its_var(key, monkeypatch, tmp_path):
    value = str(tmp_path / "x")      # a full path, so path keys compare as written
    monkeypatch.setenv(key.env, value)
    got = settings.resolve(key.name)
    assert (got.value, got.source) == (value, "env")


def test_file_key_reads_its_file(monkeypatch, tmp_path):
    cfg = paths.config_dir()
    _write(cfg / "user.yaml",
           "github: {owner: acme}\nnotion: {tasks_database_id: db9, tasks_schema: {title: T}}\n"
           "language: de\ntimezone: Europe/Paris\nguards: [a]\nsessions: {summaries: true}\n"
           "domain_patterns: [p]\ncontext: {by_domain: {d: x}, strategy: s}\n"
           "daily_brief: {domains: {d: 1}}\n")
    _write(cfg / "paths.yaml", f"version: 1\nplaces:\n  lake: {tmp_path / 'lk'}\n")
    _write(cfg / "repo-mapping.yaml", "mappings: {pat: r}\n")
    _write(cfg / "domains.yaml", "domains: {work: {}}\n")
    _write(paths.secrets_shared() / "h2t-evals.env", "H2T_EVALS_SERVICE_URL=https://e.example.test\n")
    expect = {"github.owner": "acme", "notion.tasks_database_id": "db9",
              "notion.tasks_schema": {"title": "T"}, "language": "de",
              "timezone": "Europe/Paris", "guards": ["a"], "sessions.summaries": True,
              "domain_patterns": ["p"], "context.by_domain": {"d": "x"},
              "context.strategy": "s", "daily_brief.domains": {"d": 1},
              "path.lake": str(tmp_path / "lk"), "repos": {"mappings": {"pat": "r"}},
              "domains": {"work": {}}, "evals.service_url": "https://e.example.test"}
    for name, value in expect.items():
        got = settings.resolve(name)
        assert (got.value, got.source) == (value, "file"), name
    assert {k.file for k in KEYS if k.file} >= {"user.yaml", "paths.yaml", "repo-mapping.yaml",
                                                "domains.yaml", "h2t-evals.env"}


def test_empty_environment_gives_neutral_or_config_error():
    for key in KEYS:
        if key.default is None:
            got = settings.resolve(key.name)
            assert (got.value, got.source) == (None, "unset"), key.name
            with pytest.raises(ConfigError):
                settings.require(key.name)
        elif key.name in ("path.root", "path.vault", "machine.name"):
            got = settings.resolve(key.name)
            assert got.source == "default" and got.value, key.name
        else:
            got = settings.resolve(key.name)
            assert (got.value, got.source) == (key.default, "default"), key.name
    assert settings.resolve("path.vault").value == str(paths.vault())
    assert settings.resolve("path.root").value == str(paths.root())


def test_empty_env_string_is_unset(monkeypatch):
    for var in ALL_ENV:
        monkeypatch.setenv(var, "")
    assert settings.resolve("github.owner").source == "unset"
    assert settings.resolve("path.lake").source == "unset"
    assert settings.resolve("evals.service_url").source == "unset"
    assert settings.resolve("path.root").source == "default"
    assert settings.resolve("machine.name").source == "default"


@pytest.mark.parametrize("blank", ['""', '"   "'], ids=["empty", "spaces"])
def test_blank_file_string_is_unset(blank, capsys):
    """An empty value in a file is not a value: `/widget` was the result (final review, I3)."""
    _write(paths.config_dir() / "user.yaml",
           f"github:\n  owner: {blank}\nnotion:\n  tasks_database_id: {blank}\nlanguage: {blank}\n")
    assert settings.resolve("github.owner") == settings.Resolved(None, "unset")
    assert settings.resolve("language") == settings.Resolved("en", "default")
    with pytest.raises(ConfigError):
        settings.require("github.owner")
    assert _cli(capsys, "get", "notion.tasks_database_id")[0] == 3


def test_blank_env_string_is_unset(monkeypatch):
    monkeypatch.setenv("H2T_GITHUB_OWNER", "   ")
    assert settings.resolve("github.owner").source == "unset"


def test_lake_from_the_3x_fallback_is_a_default_not_unset():
    """paths.place answers ~/.dor/lake before layout 1; the resolver must not say unset."""
    lake = paths.legacy("lake.dor")
    lake.mkdir(parents=True)
    assert paths.place("lake") == lake
    assert settings.resolve("path.lake") == settings.Resolved(str(lake), "default")


def test_broken_repo_mapping_is_an_error_row_not_a_default():
    _write(paths.config_dir() / "repo-mapping.yaml", "mappings: [unclosed\n")
    row = next(r for r in settings.rows() if r["key"] == "repos")
    assert row["source"] == "error" and "repo-mapping.yaml" in row["error"]
    with pytest.raises(ConfigError):
        settings.resolve("repos")


def test_listing_settings_writes_no_index(capsys):
    _write(paths.config_dir() / "repo-mapping.yaml", "mappings: {pat: r}\n")
    _write(paths.config_dir() / "domains.yaml", "domains: {work: {}}\n")
    assert _cli(capsys, "list")[0] == 0
    assert not (paths.state_dir() / "index.sqlite").exists()
    assert not (paths.state_dir() / "index.lock").exists()


def test_env_wins_over_file(monkeypatch):
    _write(paths.config_dir() / "user.yaml", "github: {owner: from-file}\n")
    monkeypatch.setenv("H2T_GITHUB_OWNER", "from-env")
    assert settings.resolve("github.owner") == settings.Resolved("from-env", "env")


def test_require_hint_names_the_right_file():
    with pytest.raises(ConfigError) as exc:
        settings.require("path.lake")
    assert "H2T_PATH_LAKE" in exc.value.hint and str(paths.paths_yaml()) in exc.value.hint
    with pytest.raises(ConfigError) as exc:
        settings.require("github.owner")
    assert "github.owner" in exc.value.hint and str(paths.config_dir() / "user.yaml") in exc.value.hint


def test_require_returns_the_value(monkeypatch):
    monkeypatch.setenv("H2T_GITHUB_OWNER", "acme")
    assert settings.require("github.owner") == "acme"


def test_unknown_name_is_usage_error():
    with pytest.raises(UsageError):
        settings.resolve("no.such.key")


def test_evals_url_source_is_file_when_from_h2t_evals_env(monkeypatch):
    _write(paths.secrets_shared() / "h2t-evals.env", "H2T_EVALS_SERVICE_URL=https://e.example.test\n")
    assert settings.resolve("evals.service_url").source == "file"
    monkeypatch.setenv("H2T_EVALS_SERVICE_URL", "https://env.example.test")
    assert settings.resolve("evals.service_url") == settings.Resolved("https://env.example.test", "env")


def _cli(capsys, *argv):
    from h2t_ops.cli import dispatch
    rc = dispatch(["settings", *argv])
    out, err = capsys.readouterr()
    return rc, out, err


def test_settings_list_json_names_every_key(capsys):
    rc, out, err = _cli(capsys, "list", "--json")
    assert rc == 0, err
    rows = json.loads(out)["result"]["settings"]
    assert [r["key"] for r in rows] == [k.name for k in KEYS]
    assert all(set(r) >= {"key", "value", "source"} for r in rows)


def test_settings_list_human_has_a_line_per_key(capsys):
    rc, out, _ = _cli(capsys, "list")
    assert rc == 0 and len(out.strip().splitlines()) == len(KEYS)


def test_settings_get_exit_codes(capsys, monkeypatch):
    assert _cli(capsys, "get", "no.such.key")[0] == 2
    rc, _, err = _cli(capsys, "get", "github.owner")
    assert rc == 3 and "H2T_GITHUB_OWNER" in err
    monkeypatch.setenv("H2T_GITHUB_OWNER", "acme")
    rc, out, _ = _cli(capsys, "get", "github.owner", "--json")
    assert rc == 0
    assert json.loads(out)["result"] == {"key": "github.owner", "value": "acme", "source": "env"}


def test_doctor_reports_settings():
    from h2t_ops.setup import legacy
    got = legacy.doctor(runner=lambda _args, _timeout: {"exit_code": 127, "stdout": "", "stderr": ""})["settings"]
    assert [r["key"] for r in got] == [k.name for k in KEYS]
