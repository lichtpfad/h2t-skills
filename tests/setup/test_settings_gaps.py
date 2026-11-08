"""Doctor tells a machine which removed defaults it relied on, from evidence on disk (#581)."""
import json
import sqlite3

import pytest
import yaml

from h2t_ops.core import paths, settings, user_config
from h2t_ops.lifecycle.index import schema
from h2t_ops.setup import legacy, settings_gaps


@pytest.fixture(autouse=True)
def _machine(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("H2T_PATH_ROOT", str(tmp_path / "root"))
    for key in settings.KEYS:
        if key.env and key.name != "path.root":
            monkeypatch.delenv(key.env, raising=False)
    monkeypatch.delenv("H2T_EVALS_TOKEN", raising=False)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _user(text):
    _write(paths.config_dir() / "user.yaml", text)


def _layout(n):
    _write(paths.layout_file(), json.dumps({"layout": n}))


def _index(*sources):
    db = paths.state_dir() / "index.sqlite"
    db.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db)
    con.executescript(schema.DDL)
    for i, source in enumerate(sources):
        con.execute("INSERT INTO sessions(path, summary_source) VALUES (?, ?)", (f"p{i}", source))
    con.commit()
    con.close()
    return db


def _runner(table=None):
    """A fake bounded runner: `table` maps the argument tuple to a result dict, a missing
    entry is a missing binary."""
    table = table or {}

    def run(args, timeout=15):
        got = table.get(tuple(args))
        if got is None:
            return {"status": "missing", "exit_code": 127, "stdout": "", "stderr": "no such binary"}
        return got
    return run


def _ok(out):
    return {"status": "ok", "exit_code": 0, "stdout": out, "stderr": ""}


def _of(kind, runner=None):
    return [g for g in settings_gaps.gaps(runner or _runner()) if g.kind == kind]


def _keys(kind, runner=None):
    return [g.key for g in _of(kind, runner)]


# summaries

def test_model_summary_row_and_key_unset_is_a_gap():
    _index("handoff", "model")
    found = [g for g in _of("gap") if g.key == "sessions.summaries"]
    assert len(found) == 1
    assert found[0].value is True
    assert found[0].suggestion == f"merge into {user_config.path()}:\nsessions:\n  summaries: true"


def test_summaries_key_set_is_no_gap():
    _index("model")
    _user("sessions: {summaries: true}\n")
    assert "sessions.summaries" not in _keys("gap")


def test_summaries_explicitly_off_is_no_gap():
    _index("model")
    _user("sessions: {summaries: false}\n")
    assert "sessions.summaries" not in _keys("gap")


def test_handoff_summaries_are_not_evidence():
    _index("handoff", "handoff", None)
    assert "sessions.summaries" not in _keys("gap")


def test_no_index_is_no_evidence_and_is_not_created():
    assert "sessions.summaries" not in _keys("gap")
    assert not (paths.state_dir() / "index.sqlite").exists()


def test_index_is_read_without_writing():
    db = _index("model")
    before = db.read_bytes()
    settings_gaps.gaps(_runner())
    assert db.read_bytes() == before
    assert not list(db.parent.glob("index.sqlite-*"))


def test_unreadable_index_is_no_evidence():
    db = paths.state_dir() / "index.sqlite"
    _write(db, "this is not a database")
    assert "sessions.summaries" not in _keys("gap")


# guards

def test_guard_logs_found_are_named_in_the_suggestion():
    _write(paths.logs_dir() / "grade-guard.jsonl", '{"a": 1}\n')
    found = [g for g in _of("gap") if g.key == "guards"]
    assert len(found) == 1
    assert found[0].value == ["grade"]
    assert found[0].suggestion == f"merge into {user_config.path()}:\nguards:\n- grade"


def test_both_guard_logs():
    for name in ("grade", "plain"):
        _write(paths.logs_dir() / f"{name}-guard.jsonl", "x\n")
    assert [g for g in _of("gap") if g.key == "guards"][0].value == ["grade", "plain"]


def test_empty_guard_log_is_no_evidence():
    _write(paths.logs_dir() / "grade-guard.jsonl", "")
    assert "guards" not in _keys("gap")


def test_guards_key_set_is_no_gap():
    _write(paths.logs_dir() / "plain-guard.jsonl", "x\n")
    _user("guards: [plain]\n")
    assert "guards" not in _keys("gap")


# evals url

def test_evals_token_without_url_is_a_gap(monkeypatch):
    monkeypatch.setenv("H2T_EVALS_TOKEN", "t0ken-value")
    found = [g for g in _of("gap") if g.key == "evals.service_url"]
    assert len(found) == 1
    assert found[0].suggestion.startswith("add the line H2T_EVALS_SERVICE_URL=")
    assert "h2t-evals.env" in found[0].suggestion
    assert "t0ken-value" not in repr(found)


def test_evals_url_set_is_no_gap(monkeypatch):
    monkeypatch.setenv("H2T_EVALS_TOKEN", "t")
    monkeypatch.setenv("H2T_EVALS_SERVICE_URL", "https://e.example.test")
    assert "evals.service_url" not in _keys("gap")


def test_evals_without_token_is_no_gap():
    assert "evals.service_url" not in _keys("gap")


# .dor after migration

def _dor_secrets(text):
    _write(paths.legacy("secrets.dor_old"), text)


def test_secret_gap_names_keys_never_values():
    _layout(1)
    _dor_secrets("SOME_API_KEY=sekret-value-1\nHAVE_IT=sekret-value-2\n# C=3\n")
    _write(paths.secrets_shared() / "other.env", "HAVE_IT=already\n")
    found = [g for g in _of("gap") if g.key == "secrets"]
    assert len(found) == 1
    text = repr(found)
    assert "SOME_API_KEY" in text
    assert "HAVE_IT" not in text
    assert "sekret-value" not in text


def test_secret_gap_reads_both_dor_secret_files():
    _layout(1)
    _dor_secrets("OLD_ONE=a\n")
    _write(paths.legacy("secrets.dor"), "NEWER_ONE=b\n")
    text = repr([g for g in _of("gap") if g.key == "secrets"])
    assert "OLD_ONE" in text
    assert "NEWER_ONE" in text


def test_secrets_before_migration_are_no_gap():
    _layout(0)
    _dor_secrets("SOME_API_KEY=v\n")
    assert "secrets" not in _keys("gap")


def test_secrets_all_present_in_the_new_store_are_no_gap():
    _layout(1)
    _dor_secrets("SOME_API_KEY=v\n")
    _write(paths.secrets_shared() / "other.env", "SOME_API_KEY=v2\n")
    assert "secrets" not in _keys("gap")


def test_dor_lake_without_a_declared_place_is_a_gap():
    _layout(1)
    paths.legacy("lake.dor").mkdir(parents=True)
    found = [g for g in _of("gap") if g.key == "path.lake"]
    assert len(found) == 1
    assert found[0].suggestion.startswith("run: h2t-ops paths set lake ")


def test_dor_lake_with_a_declared_place_is_no_gap(tmp_path):
    _layout(1)
    paths.legacy("lake.dor").mkdir(parents=True)
    _write(paths.paths_yaml(), f"version: 1\nplaces:\n  lake: {tmp_path / 'elsewhere'}\n")
    assert "path.lake" not in _keys("gap")


def test_dor_lake_before_migration_is_no_gap():
    _layout(0)
    paths.legacy("lake.dor").mkdir(parents=True)
    assert "path.lake" not in _keys("gap")


# info

def test_repo_mapping_empty_is_info_and_filled_is_not():
    assert "repos" in _keys("info")
    _write(paths.config_dir() / "repo-mapping.yaml", "mappings: {pat: r}\n")
    assert "repos" not in _keys("info")


GH = ("gh", "auth", "status")
GH_USER = ("gh", "api", "user", "--jq", ".login")


def test_github_owner_from_a_logged_in_gh():
    found = [g for g in _of("info", _runner({GH: _ok("Logged in to github.com account octo"),
                                              GH_USER: _ok("octo\n")}))
             if g.key == "github.owner"]
    assert len(found) == 1
    assert found[0].value == "octo"
    assert found[0].suggestion.endswith(":\ngithub:\n  owner: octo")


def test_two_accounts_suggest_the_active_login_and_say_so():
    status = _ok("Logged in to github.com account octo (keyring)\n"
                 "Logged in to github.com account other (keyring)\n")
    found = [g for g in _of("info", _runner({GH: status, GH_USER: _ok("other\n")}))
             if g.key == "github.owner"]
    assert found[0].value == "other"
    assert "2 accounts" in found[0].evidence


@pytest.mark.parametrize("table", [
    {},   # gh is not installed
    {GH: {"status": "timeout", "exit_code": 124, "stdout": "", "stderr": ""}},
    {GH: {"status": "error", "exit_code": 1, "stdout": "", "stderr": "not logged in"}},
    {GH: _ok("Logged in"), GH_USER: {"status": "timeout", "exit_code": 124, "stdout": "", "stderr": ""}},
    {GH: _ok("Logged in"), GH_USER: _ok("\n")},
], ids=["missing", "timeout", "logged-out", "user-timeout", "no-login"])
def test_gh_missing_timeout_or_logged_out_gives_no_owner_info(table):
    assert "github.owner" not in _keys("info", _runner(table))


def test_github_owner_set_gives_no_info():
    _user("github: {owner: acme}\n")
    table = {GH: _ok("Logged in"), GH_USER: _ok("octo")}
    assert "github.owner" not in _keys("info", _runner(table))


GIT_NAME = ("git", "config", "user.name")


def test_git_user_name_empty_is_info():
    unset = {"status": "error", "exit_code": 1, "stdout": "", "stderr": ""}
    assert "git.user.name" in _keys("info", _runner({GIT_NAME: unset}))
    assert "git.user.name" in _keys("info", _runner({GIT_NAME: _ok("\n")}))


def test_git_user_name_set_or_git_missing_is_no_info():
    assert "git.user.name" not in _keys("info", _runner({GIT_NAME: _ok("Ada\n")}))
    assert "git.user.name" not in _keys("info", _runner({}))


def test_about_me_files_without_the_key_is_info():
    _write(paths.config_dir() / "about-me" / "core.md", "x")
    found = [g for g in _of("info") if g.key == "context.by_domain"]
    assert len(found) == 1
    assert "core.md" in found[0].evidence
    _user("context: {by_domain: {work: [core.md]}}\n")
    assert "context.by_domain" not in _keys("info")


def test_domains_without_domain_patterns_is_info():
    _write(paths.config_dir() / "domains.yaml", "domains: {work: {}}\n")
    assert "domain_patterns" in _keys("info")
    _user("domain_patterns: [x]\n")
    assert "domain_patterns" not in _keys("info")


# manual and the fresh machine

def test_manual_items_name_their_keys():
    assert {"guards", "language", "daily_brief.domains"} <= set(_keys("manual"))
    structure = [g for g in _of("manual") if g.key == "guards"][0]
    assert structure.value == ["structure"]


def test_fresh_install_has_no_gap_only_info_and_manual():
    found = settings_gaps.gaps(_runner())
    assert found
    assert {g.kind for g in found} <= {"info", "manual"}


def test_gaps_never_write_state(tmp_path):
    _index("model")
    _layout(1)
    snapshot = sorted(p for p in tmp_path.rglob("*") if p.is_file())
    settings_gaps.gaps(_runner())
    assert sorted(p for p in tmp_path.rglob("*") if p.is_file()) == snapshot


# doctor

def test_doctor_json_has_settings_gaps(monkeypatch):
    _index("model")
    monkeypatch.setattr(legacy, "resolve_h2t_ops", lambda *a, **k: {"status": "missing"})
    report = legacy.doctor(runner=_runner())
    assert report["settings"]
    items = report["settings_gaps"]
    assert any(i["kind"] == "gap" and i["key"] == "sessions.summaries" for i in items)
    assert set(items[0]) == {"kind", "key", "evidence", "suggestion", "value"}
    json.dumps(report["settings_gaps"])


# a suggestion takes effect when merged as instructed (final review, Critical 1)

def _merge(items):
    """What the setup skill tells the agent to do: merge each item's key and value into
    the existing user.yaml mapping, one list for every `guards` item."""
    f = user_config.path()
    doc = (yaml.safe_load(f.read_text(encoding="utf-8")) if f.is_file() else None) or {}
    for g in items:
        *parents, last = g.key.split(".")
        node = doc
        for part in parents:
            node = node.setdefault(part, {})
        old = node.get(last)
        if isinstance(old, list) and isinstance(g.value, list):
            node[last] = old + [v for v in g.value if v not in old]
        else:
            node[last] = g.value
    _write(f, yaml.safe_dump(doc, sort_keys=False))


def _user_yaml_items(found):
    return [g for g in found if g.kind in ("gap", "info") and "user.yaml" in (g.suggestion or "")]


def _every_trace():
    _index("model")
    _write(paths.logs_dir() / "grade-guard.jsonl", "x\n")
    _write(paths.logs_dir() / "plain-guard.jsonl", "x\n")
    _write(paths.config_dir() / "about-me" / "core.md", "x")
    _write(paths.config_dir() / "domains.yaml", "domains: {work: {}}\n")
    _write(paths.config_dir() / settings_gaps.STRATEGY_FILE, "x")
    # a file that already holds the parent mappings: an appended second `sessions:` would
    # silently replace this one
    _user("sessions:\n  keep: 1\ncontext:\n  keep: 2\n")
    return _runner({GH: _ok("Logged in to github.com account octo"), GH_USER: _ok("octo\n")})


def test_every_user_yaml_suggestion_takes_effect_when_merged():
    runner = _every_trace()
    items = _user_yaml_items(settings_gaps.gaps(runner))
    assert {g.key for g in items} >= {"sessions.summaries", "guards", "github.owner",
                                      "context.by_domain", "context.strategy", "domain_patterns"}
    assert all(g.value is not None for g in items), [g.key for g in items if g.value is None]
    _merge(items + [g for g in settings_gaps.gaps(runner) if g.kind == "manual" and g.key == "guards"])
    for g in items:
        got = settings.resolve(g.key)
        assert got.source == "file", g.key
        if g.key != "guards":
            assert got.value == g.value, g.key
    assert settings.resolve("guards").value == ["grade", "plain", "structure"]
    assert user_config.get("sessions.keep") == 1 and user_config.get("context.keep") == 2
    left = {g.key for g in settings_gaps.gaps(runner) if g.kind in ("gap", "info")}
    assert not left & {g.key for g in items}, left
    assert "guards" not in {g.key for g in settings_gaps.gaps(runner) if g.kind == "manual"}


def test_suggestion_text_is_the_nested_yaml_of_its_value():
    """The text a person reads and the value an agent merges say the same thing."""
    for g in _user_yaml_items(settings_gaps.gaps(_every_trace())):
        block = g.suggestion.split("\n", 1)[1]
        nested = g.value
        for part in reversed(g.key.split(".")):
            nested = {part: nested}
        assert yaml.safe_load(block) == nested, g.key


def test_by_domain_suggestion_has_the_shape_the_reader_reads():
    from h2t_ops.lifecycle.gather.user import gather_user_context
    _write(paths.config_dir() / "about-me" / "core.md", "x")
    _write(paths.config_dir() / "about-me" / "work.md", "x")
    found = [g for g in _of("info") if g.key == "context.by_domain"][0]
    assert found.value == {"<domain>": ["core.md", "work.md"]}
    _merge([found])
    got = gather_user_context(domain="<domain>")
    about = paths.config_dir() / "about-me"
    assert got["deep_paths"] == [str(about / "core.md"), str(about / "work.md")]


def test_strategy_file_without_the_key_is_a_gap():
    _write(paths.config_dir() / settings_gaps.STRATEGY_FILE, "x")
    found = [g for g in _of("gap") if g.key == "context.strategy"]
    assert len(found) == 1 and found[0].value == settings_gaps.STRATEGY_FILE
    _user(f"context:\n  strategy: {settings_gaps.STRATEGY_FILE}\n")
    assert "context.strategy" not in _keys("gap")


def test_no_strategy_file_is_no_gap():
    assert "context.strategy" not in _keys("gap")


def test_secret_gap_is_a_move_for_the_user_naming_keys_and_the_target():
    _layout(1)
    _dor_secrets("SOME_API_KEY=sekret-value-1\n")
    found = [g for g in _of("gap") if g.key == "secrets"][0]
    assert found.value is None
    assert "by hand" in found.suggestion
    assert str(paths.secrets_shared()) in found.suggestion
    assert "SOME_API_KEY" in found.suggestion
    assert "KEY=value" not in found.suggestion and "sekret" not in found.suggestion
