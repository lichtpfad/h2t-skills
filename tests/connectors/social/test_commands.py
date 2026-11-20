import json
import re
from pathlib import Path

import pytest
import yaml

from h2t_ops.cli import dispatch
from h2t_ops.connectors.social import journal
from h2t_ops.connectors.social.journal import journal_path
from h2t_ops.connectors.social.meta import MetaClient as meta_cls
from h2t_ops.connectors.social.threads import ThreadsClient as threads_cls

USER = "EAA" + "u" * 12 + "-user"
PAGE1 = "EAA" + "p" * 12 + "-page1"
PAGE2 = "EAA" + "q" * 12 + "-page2"
THR = "THAA" + "t" * 12 + "-thr"
TOKENS = (USER, PAGE1, PAGE2, THR)
GRAPH = "https://graph.facebook.com/v27.0/"
THREADS = "https://graph.threads.net/v1.0/"


def _accounts_body():
    return {"data": [
        {"id": "page_222", "name": "Acme One", "access_token": PAGE1,
         "instagram_business_account": {"id": "ig_111", "username": "acme"}},
        {"id": "page_223", "name": "Acme Two!", "access_token": PAGE2}]}


class Session:
    """Routes a GET by URL suffix; records calls. `routes` maps path -> (status, body)."""

    def __init__(self, routes):
        self.routes, self.calls = routes, []

    def get(self, url, params=None, timeout=None):
        self.calls.append(url)
        path = url.split("/v27.0/")[-1].split("/v1.0/")[-1]
        status, body = self.routes[path]
        return type("R", (), {"status_code": status, "json": lambda self: body})()


def _routes(expired=False):
    media = {"data": [{"id": f"m{i}", "timestamp": f"2026-11-0{i}T09:00:00+0000", "permalink": f"p{i}"}
                      for i in (1, 2)]}
    err = {"error": {"code": 190, "message": "Session has expired"}}
    return {
        "me/accounts": (400, err) if expired else (200, _accounts_body()),
        "ig_111": (200, {"username": "acme", "followers_count": 5, "media_count": 2, "id": "ig_111"}),
        "ig_111/media": (200, media),
        "m1/insights": (200, {"data": [{"name": "reach", "values": [{"value": 10}]}]}),
        "m2/insights": (200, {"data": [{"name": "reach", "values": [{"value": 20}]}]}),
        "ig_111/insights": (200, {"data": []}),
        "me": (200, {"id": "th_111", "username": "acme"}),
        "me/threads": (200, {"data": [{"id": "t1", "timestamp": "2026-11-02T09:00:00+0000",
                                       "permalink": "tp"}]}),
        "t1/insights": (200, {"data": [{"name": "views", "values": [{"value": 7}]}]}),
    }


@pytest.fixture
def env(social_config, social_data, monkeypatch):
    """Fake secrets, fake HTTP at the client session seam, timezone UTC. Returns the session."""
    values = {"META_H2T_SOCIAL_USER_TOKEN": USER, "THREADS_TOKEN_ACME": THR}
    monkeypatch.setattr("h2t_ops.core.secrets.get", values.get)
    monkeypatch.setattr("h2t_ops.core.secrets.keys_with_prefix",
                        lambda p: sorted(k for k in values if k.startswith(p)))
    monkeypatch.setattr("h2t_ops.core.user_config.get",
                        lambda key, *a: "UTC" if key == "timezone" else None)
    session = Session(_routes())
    from h2t_ops.connectors.social import meta, threads
    monkeypatch.setattr(meta, "MetaClient", lambda *a, **k: meta_cls(*a, session=session, **k))
    monkeypatch.setattr(threads, "ThreadsClient", lambda *a, **k: threads_cls(*a, session=session, **k))
    return session


def run(capsys, *argv):
    code = dispatch(["social", *argv])
    out = capsys.readouterr()
    return code, out.out, out.err


def _journal():
    return [json.loads(x) for x in journal_path().read_text(encoding="utf-8").splitlines()]


def _file(social_config):
    return social_config() / "social" / "accounts.yaml"


def test_connector_is_discovered():
    from h2t_ops.core.registry import discover
    assert "social" in {s.name for s in discover()}


def test_discover_without_write_changes_nothing(env, social_config, capsys):
    social_config(accounts={"accounts": []})
    f = _file(social_config)
    before = f.read_text(encoding="utf-8")
    code, out, _ = run(capsys, "accounts", "discover", "--json")
    assert code == 0
    doc = yaml.safe_load(json.loads(out)["result"]["yaml"])
    ids = {f"{a['network']}:{a['handle']}" for a in doc["accounts"]}
    assert ids == {"instagram:acme", "facebook:acme_one", "facebook:acme_two", "threads:acme"}
    assert f.read_text(encoding="utf-8") == before


def test_discover_human_is_a_table(env, social_config, capsys):
    social_config(accounts={"accounts": []})
    code, out, _ = run(capsys, "accounts", "discover")
    assert code == 0
    lines = out.strip().splitlines()
    assert not out.lstrip().startswith("{")
    assert all(w in lines[0] for w in ("id", "enabled", "token_key"))
    assert len([x for x in lines if "instagram:acme" in x]) == 1
    assert "not written" in lines[-1] and "--write" in lines[-1]


def test_discover_merges_and_keeps_enabled(env, social_config, capsys):
    social_config(
        accounts={"api": {"meta_graph": "https://graph.facebook.com/v27.0"},
                  "accounts": [{"network": "instagram", "handle": "acme", "remote_id": "old",
                                "token_key": "META_H2T_SOCIAL_USER_TOKEN", "enabled": True, "project": "proj_x"},
                                {"network": "instagram", "handle": "gone", "remote_id": "ig_9",
                                 "token_key": "META_H2T_SOCIAL_USER_TOKEN"}]},
        domains={"d": {"projects": [{"id": "proj_x"}]}})
    code, out, err = run(capsys, "accounts", "discover", "--write", "--json")
    assert code == 0, out + err
    doc = yaml.safe_load(_file(social_config).read_text(encoding="utf-8"))
    by_id = {f"{a['network']}:{a['handle']}": a for a in doc["accounts"]}
    assert doc["api"] == {"meta_graph": "https://graph.facebook.com/v27.0"}
    assert by_id["instagram:acme"]["enabled"] is True and by_id["instagram:acme"]["project"] == "proj_x"
    assert by_id["instagram:acme"]["remote_id"] == "ig_111" and by_id["instagram:acme"]["page_id"] == "page_222"
    assert by_id["facebook:acme_two"]["enabled"] is False and "project" not in by_id["facebook:acme_two"]
    assert by_id["threads:acme"]["token_key"] == "THREADS_TOKEN_ACME"
    assert "instagram:gone" in by_id   # unseen accounts stay
    from h2t_ops.connectors.social.config import load_accounts
    assert len(load_accounts()) == 5   # the file still loads


@pytest.mark.parametrize("cmd", ["discover", "check"])
def test_discover_and_check_are_journaled(env, social_config, capsys, cmd):
    if cmd == "check":
        social_config(accounts={"accounts": [
            {"network": "instagram", "handle": "acme", "remote_id": "ig_111", "page_id": "page_222",
             "token_key": "META_H2T_SOCIAL_USER_TOKEN", "enabled": True},
            {"network": "threads", "handle": "acme", "remote_id": "th_111",
             "token_key": "THREADS_TOKEN_ACME", "enabled": True}]})
        argv = ("check", "--json")
    else:
        social_config(accounts={"accounts": []})
        argv = ("accounts", "discover", "--json")
    code, out, err = run(capsys, *argv)
    assert code == 0, out + err
    recs = _journal()
    process = "accounts" if cmd == "discover" else "check"
    assert [r["step"] for r in recs if r["step"] != 2] == [1, 6]
    assert recs[0]["process"] == process
    assert sum(r["step"] == 2 for r in recs) == len(env.calls)
    raw = "".join(p.read_text(encoding="utf-8") for p in (journal_path().parent / "raw").rglob("*.jsonl"))
    assert PAGE1 not in raw and PAGE2 not in raw and "access_token" not in raw


def test_check_names_a_missing_account(env, social_config, capsys):
    social_config(accounts={"accounts": []})
    code, out, _ = run(capsys, "check", "--json")
    assert code == 5 and not env.calls


def test_check_facebook_prints_note(env, social_config, capsys):
    social_config(accounts={"accounts": [{"network": "facebook", "handle": "acme_two_",
                                          "remote_id": "page_223", "page_id": "page_223",
                                          "token_key": "META_H2T_SOCIAL_USER_TOKEN", "enabled": True}]})
    code, out, _ = run(capsys, "check", "--json")
    row = json.loads(out)["result"][0]
    assert code == 0 and "profile only" in row["note"] and "posts" not in row


def test_run_insights_envelope_json(env, social_config, capsys):
    social_config(accounts={"accounts": [
        {"network": "instagram", "handle": "acme", "remote_id": "ig_111", "page_id": "page_222",
         "token_key": "META_H2T_SOCIAL_USER_TOKEN", "enabled": True}]})
    code, out, err = run(capsys, "run", "insights", "--account", "instagram:acme", "--limit", "5", "--json")
    assert code == 0, out + err
    env_ = json.loads(out)
    assert env_["ok"] is True and env_["provider"] == "social"
    assert env_["result"]["accounts"]["instagram:acme"]["summary"]["posts"] == 2


def test_journal_reads_and_fails_loud_when_empty(env, social_config, capsys):
    code, out, err = run(capsys, "journal", "--json")
    assert code == 5 and "no journal records" in out + err
    social_config(accounts={"accounts": []})
    run(capsys, "accounts", "discover", "--json")
    run_id = _journal()[0]["run_id"]
    code, out, _ = run(capsys, "journal", "--run", run_id, "--json")
    assert code == 0 and all(r["run_id"] == run_id for r in json.loads(out)["result"])
    code, out, _ = run(capsys, "journal", "--run", "nope", "--json")
    assert code == 5


@pytest.mark.parametrize("fmt", ["--json", "--format=human"])
def test_cli_output_and_errors_never_show_tokens(env, social_config, capsys, fmt):
    social_config(accounts={"accounts": [
        {"network": "instagram", "handle": "acme", "remote_id": "ig_111", "page_id": "page_222",
         "token_key": "META_H2T_SOCIAL_USER_TOKEN", "enabled": True},
        {"network": "threads", "handle": "acme", "remote_id": "th_111",
         "token_key": "THREADS_TOKEN_ACME", "enabled": True}]})
    seen = []
    for argv in (("accounts", "discover"), ("accounts", "list"), ("check",), ("run", "insights"),
                 ("journal",)):
        code, out, err = run(capsys, *argv, fmt)
        assert code == 0, (argv, out, err)
        seen.append(out + err)
    env.routes["me/accounts"] = _routes(expired=True)["me/accounts"]   # code 190
    code, out, err = run(capsys, "check", fmt)
    assert code == 4
    seen.append(out + err)
    text = "\n".join(seen)
    assert "190" in text   # positive control: the error text really was captured
    for tok in TOKENS:
        assert tok not in text
    assert all(tok not in journal_path().read_text(encoding="utf-8") for tok in TOKENS)
    assert journal._runtime_secrets   # positive control: the clients did register the tokens


def test_no_client_import_outside_run_modules():
    pkg = Path(__file__).parents[3] / "h2t_ops"
    call = re.compile(r"\b(MetaClient|ThreadsClient)\(")
    hits = {p.relative_to(pkg).as_posix() for p in pkg.rglob("*.py")
            if any(call.search(line) for line in p.read_text(encoding="utf-8").splitlines()
                   if not line.startswith("class "))}
    assert hits == {"connectors/social/commands.py", "connectors/social/insights.py"}


def _only_secrets(monkeypatch, values):
    monkeypatch.setattr("h2t_ops.core.secrets.get", values.get)
    monkeypatch.setattr("h2t_ops.core.secrets.keys_with_prefix",
                        lambda p: sorted(k for k in values if k.startswith(p)))


def test_discover_uses_the_configured_meta_key(env, social_config, capsys, monkeypatch):
    _only_secrets(monkeypatch, {"META_OTHER_USER": USER})
    social_config(accounts={"secrets": {"meta_user_token": "META_OTHER_USER"}, "accounts": []})
    code, out, err = run(capsys, "accounts", "discover", "--json")
    assert code == 0, out + err
    doc = yaml.safe_load(json.loads(out)["result"]["yaml"])
    assert {a["token_key"] for a in doc["accounts"]} == {"META_OTHER_USER"}


def test_discover_uses_the_configured_threads_prefix(env, social_config, capsys, monkeypatch):
    _only_secrets(monkeypatch, {"THREADS_MY_ACME": THR, "THREADS_TOKEN_ACME": THR})
    social_config(accounts={"secrets": {"threads_token_prefix": "THREADS_MY_"}, "accounts": []})
    code, out, err = run(capsys, "accounts", "discover", "--json")
    assert code == 0, out + err
    doc = yaml.safe_load(json.loads(out)["result"]["yaml"])
    assert {a["token_key"] for a in doc["accounts"]} == {"THREADS_MY_ACME"}


def test_threads_only_discover_skips_meta_and_says_so(env, social_config, capsys, monkeypatch):
    _only_secrets(monkeypatch, {"THREADS_TOKEN_ACME": THR})
    social_config(accounts={"accounts": []})
    code, out, err = run(capsys, "accounts", "discover", "--json")
    assert code == 0, out + err
    result = json.loads(out)["result"]
    doc = yaml.safe_load(result["yaml"])
    assert [f"{a['network']}:{a['handle']}" for a in doc["accounts"]] == ["threads:acme"]
    assert any("META_H2T_SOCIAL_USER_TOKEN" in n for n in result["notes"])
    assert not any("me/accounts" in c for c in env.calls)


def test_discover_with_no_token_at_all_fails_loud(env, social_config, capsys, monkeypatch):
    _only_secrets(monkeypatch, {})
    social_config(accounts={"accounts": []})
    code, out, err = run(capsys, "accounts", "discover", "--json")
    assert code == 3 and "no accounts found" in out + err


def test_discover_with_expired_meta_token_still_fails_auth(env, social_config, capsys):
    env.routes["me/accounts"] = _routes(expired=True)["me/accounts"]
    social_config(accounts={"accounts": []})
    code, out, err = run(capsys, "accounts", "discover", "--json")
    assert code == 4


def test_discover_refuses_an_existing_file_with_a_token(env, social_config, capsys):
    social_config(accounts={"accounts": [
        {"network": "instagram", "handle": "acme", "remote_id": "ig_111",
         "token_key": "META_H2T_SOCIAL_USER_TOKEN", "token": "legacy-" + "s" * 12}]})
    f = _file(social_config)
    before = f.read_text(encoding="utf-8")
    code, out, err = run(capsys, "accounts", "discover", "--write", "--json")
    assert code == 3 and not env.calls and not journal_path().exists()   # refused before a run opens
    assert "legacy-" not in out + err
    assert f.read_text(encoding="utf-8") == before


def test_discover_keeps_project_exactly_and_drops_unknown_fields(env, social_config, capsys):
    social_config(accounts={"accounts": [
        {"network": "instagram", "handle": "acme", "remote_id": "ig_111",
         "token_key": "META_H2T_SOCIAL_USER_TOKEN", "project": "", "legacy_note": "x"}]})
    code, out, err = run(capsys, "accounts", "discover", "--write", "--json")
    assert code == 0, out + err
    doc = yaml.safe_load(_file(social_config).read_text(encoding="utf-8"))
    acme = next(a for a in doc["accounts"] if a["handle"] == "acme" and a["network"] == "instagram")
    assert acme["project"] == "" and "legacy_note" not in acme


def test_discover_never_echoes_a_token_in_an_api_override(env, social_config, capsys):
    social_config(accounts={"api": {"meta_graph": "https://host.test/v27?access_token=" + PAGE1},
                            "accounts": []})
    code, out, err = run(capsys, "accounts", "discover", "--json")
    assert code == 3 and not env.calls
    assert PAGE1 not in out + err


_META_IG = {"network": "instagram", "handle": "acme", "remote_id": "ig_111", "page_id": "page_222",
            "token_key": "META_H2T_SOCIAL_USER_TOKEN", "enabled": True}


@pytest.mark.parametrize("argv", [("check",), ("run", "insights"), ("accounts", "discover")])
def test_error_body_is_journaled_before_the_failure_outcome(env, social_config, capsys, argv):
    social_config(accounts={"accounts": [_META_IG]})
    env.routes["me/accounts"] = _routes(expired=True)["me/accounts"]   # HTTP 400, code 190
    code, out, err = run(capsys, *argv, "--json")
    assert code == 4
    recs = _journal()
    bodies = [r for r in recs if r["step"] == 2]
    assert len(bodies) == 1
    raw = "".join(p.read_text(encoding="utf-8") for p in (journal_path().parent / "raw").rglob("*.jsonl"))
    assert "Session has expired" in raw
    assert all(tok not in raw for tok in TOKENS)
    assert [r["step"] for r in recs] == [1, 2, 6]
    assert recs[-1]["result"]["error"].startswith("AuthError")


def test_discover_with_tokens_but_no_pages_is_a_provider_error(env, social_config, capsys, monkeypatch):
    _only_secrets(monkeypatch, {"META_H2T_SOCIAL_USER_TOKEN": USER})
    env.routes["me/accounts"] = (200, {"data": []})
    social_config(accounts={"accounts": []})
    code, out, err = run(capsys, "accounts", "discover", "--json")
    assert code == 1 and "no accounts found" in out + err


def test_run_insights_store_and_trigger(env, social_config, capsys):
    from h2t_ops.connectors.social import db
    social_config(accounts={"accounts": [_META_IG]})
    code, out, err = run(capsys, "run", "insights", "--trigger", "schedule", "--store", "--json")
    assert code == 0, out + err
    rid = json.loads(out)["result"]["run_id"]
    step1 = next(r for r in db.read_journal(rid) if r["step"] == 1)
    assert step1["trigger"] == "schedule"
    assert len(db.read_results(rid)) == 1 and db.read_raw(rid)


def test_run_insights_default_is_cli_and_no_db(env, social_config, capsys):
    from h2t_ops.connectors.social import db
    social_config(accounts={"accounts": [_META_IG]})
    code, out, err = run(capsys, "run", "insights", "--json")
    assert code == 0, out + err
    recs = [json.loads(line) for line in journal_path().read_text(encoding="utf-8").splitlines()]
    assert next(r for r in recs if r["step"] == 1)["trigger"] == "cli"
    assert not db.db_path().exists()


@pytest.mark.parametrize("limit", ["0", "-5"])
def test_non_positive_limit_is_a_usage_error_before_any_call(env, social_config, capsys, limit):
    social_config(accounts={"accounts": [_META_IG]})
    code, out, err = run(capsys, "run", "insights", "--limit", limit, "--json")
    assert code == 2 and not env.calls and not journal_path().exists()


def test_facebook_handle_has_no_edge_underscores(env, social_config, capsys):
    social_config(accounts={"accounts": []})
    code, out, _ = run(capsys, "accounts", "discover", "--json")
    ids = {f"{a['network']}:{a['handle']}" for a in yaml.safe_load(json.loads(out)["result"]["yaml"])["accounts"]}
    assert "facebook:acme_two" in ids and not any(i.endswith("_") for i in ids)


def test_colliding_facebook_handles_get_the_page_id(env, social_config, capsys):
    body = {"data": [{"id": "page_1", "name": "Acme One"}, {"id": "page_2", "name": "acme-one!"},
                     {"id": "page_3", "name": "Other"}]}
    env.routes["me/accounts"] = (200, body)
    social_config(accounts={"accounts": []})
    code, out, _ = run(capsys, "accounts", "discover", "--json")
    accounts = yaml.safe_load(json.loads(out)["result"]["yaml"])["accounts"]
    fb = {a["remote_id"]: a["handle"] for a in accounts if a["network"] == "facebook"}
    assert fb == {"page_1": "acme_one_page_1", "page_2": "acme_one_page_2", "page_3": "other"}
