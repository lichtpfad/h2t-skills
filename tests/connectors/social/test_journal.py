import json

import pytest

from h2t_ops.connectors.social import journal
from h2t_ops.core.errors import ConfigError, UsageError

SECRET = "EAA" + "x" * 10 + "-fake-value"


def _lines(path):
    return path.read_text(encoding="utf-8").splitlines() if path.exists() else []


def _rules(rules):
    return {"rules": [{"added": "2026-11-19", "origin": "example", **r} for r in rules]}


def test_records_are_appended_never_rewritten(social_data):
    run = journal.new_run("insights", "manual")
    first = _lines(journal.journal_path())[0]
    journal.record(run, 6, outcome="ok")
    lines = _lines(journal.journal_path())
    assert len(lines) == 2
    assert lines[0] == first


def test_raw_zone_is_appended_never_rewritten(social_data):
    run = journal.new_run("insights", "manual")
    journal.write_raw(run, "insights", "instagram:acme", "/a", {"n": 1})
    raw_file = next((social_data / "social" / "raw" / "insights").glob("*.jsonl"))
    first = _lines(raw_file)[0]
    journal.write_raw(run, "insights", "instagram:acme", "/b", {"n": 2})
    lines = _lines(raw_file)
    assert len(lines) == 2
    assert lines[0] == first


SPEC_FIELDS = {"id", "ts", "run_id", "process", "step", "channel", "account", "action", "source_ids",
               "context_refs", "rule_id", "decision", "approved_by", "result", "task_id"}


def test_every_record_carries_the_spec_minimum(social_data):
    run = journal.new_run("insights", "manual")
    journal.write_raw(run, "insights", "instagram:acme", "/x", {"a": 1})
    journal.decide(run, "insights", "none", "instagram:acme")
    journal.record(run, 6, process="insights", result={"error": "boom"})
    recs = [json.loads(x) for x in _lines(journal.journal_path())]
    assert len(recs) == 4
    for rec in recs:
        assert SPEC_FIELDS <= set(rec), SPEC_FIELDS - set(rec)
        assert set(rec["result"]) == {"remote_id", "url", "error"}
        assert "error" not in rec
    first = recs[0]
    assert (first["source_ids"], first["context_refs"], first["rule_id"], first["task_id"]) == ([], [], None, None)
    assert first["result"] == {"remote_id": None, "url": None, "error": None}
    assert recs[-1]["result"] == {"remote_id": None, "url": None, "error": "boom"}


def test_step5_without_source_ids_is_refused(social_data):
    run = journal.new_run("communication", "manual")
    with pytest.raises(ValueError):
        journal.record(run, 5, action="x", source_ids=[])
    with pytest.raises(ValueError):
        journal.record(run, 5, action="x")
    assert len(_lines(journal.journal_path())) == 1
    journal.record(run, 5, action="x", source_ids=["a"])
    assert len(_lines(journal.journal_path())) == 2


def test_secret_value_never_written(social_data, monkeypatch):
    monkeypatch.setattr("h2t_ops.core.secrets.get",
                        lambda key: SECRET if key == "META_USER_TOKEN" else None)
    run = journal.new_run("insights", "manual")
    before = _lines(journal.journal_path())
    with pytest.raises(journal.SecretInRecord) as exc:
        journal.record(run, 6, note=f"leak {SECRET}")
    assert SECRET not in str(exc.value)
    assert _lines(journal.journal_path()) == before


def test_account_token_key_value_is_a_secret(social_data, social_config, monkeypatch):
    social_config(accounts={"accounts": [{
        "network": "threads", "handle": "acme", "remote_id": "th_1",
        "token_key": "THREADS_TOKEN_ACME"}]})
    monkeypatch.setattr("h2t_ops.core.secrets.get",
                        lambda key: "THtok-acme-value" if key == "THREADS_TOKEN_ACME" else None)
    run = journal.new_run("insights", "manual")
    with pytest.raises(journal.SecretInRecord):
        journal.record(run, 6, note="x THtok-acme-value")


def test_missing_accounts_file_does_not_break_journaling(social_data):
    run = journal.new_run("insights", "manual")
    journal.record(run, 6, outcome="ok")
    assert len(_lines(journal.journal_path())) == 2


def test_secret_error_is_a_config_error():
    assert issubclass(journal.SecretInRecord, ConfigError)


def test_decide_defaults_to_ask_and_records_step4(social_data):
    run = journal.new_run("communication", "manual")
    assert journal.decide(run, "communication", "reply", "instagram:acme", "dm") == "ask"
    rec = json.loads(_lines(journal.journal_path())[-1])
    assert rec["step"] == 4
    assert rec["rule_id"] is None
    assert rec["decision"] == "ask"


def test_decide_exact_account_beats_wildcard(social_data, social_config):
    social_config(rules=_rules([
        {"id": "r-all", "process": "communication", "action": "reply", "account": "*", "verdict": "deny"},
        {"id": "r-acme", "process": "communication", "action": "reply",
         "account": "instagram:acme", "verdict": "auto"}]))
    run = journal.new_run("communication", "manual")
    assert journal.decide(run, "communication", "reply", "instagram:acme") == "auto"
    rec = json.loads(_lines(journal.journal_path())[-1])
    assert rec["rule_id"] == "r-acme"
    assert journal.decide(run, "communication", "reply", "instagram:other") == "deny"


def test_decide_kind_matches(social_data, social_config):
    social_config(rules=_rules([
        {"id": "r-reel", "process": "content", "action": "publish", "account": "*",
         "kind": "reel", "verdict": "auto"}]))
    run = journal.new_run("content", "manual")
    assert journal.decide(run, "content", "publish", "instagram:acme", "reel") == "auto"
    assert journal.decide(run, "content", "publish", "instagram:acme", "dm") == "ask"


def test_action_none_is_noop(social_data, monkeypatch):
    def boom():
        raise AssertionError("load_rules must not be called for action none")
    monkeypatch.setattr(journal, "load_rules", boom)
    run = journal.new_run("insights", "manual")
    assert journal.decide(run, "insights", "none", "instagram:acme") == "noop"
    rec = json.loads(_lines(journal.journal_path())[-1])
    assert rec["decision"] == "noop"
    assert rec["rule_id"] is None


def test_require_allowed_refuses_ask_and_deny(social_data, social_config):
    social_config(rules=_rules([
        {"id": "r-ok", "process": "p", "action": "ok", "account": "*", "verdict": "auto"},
        {"id": "r-no", "process": "p", "action": "no", "account": "*", "verdict": "deny"}]))
    run = journal.new_run("p", "manual")
    recs = {}
    for action in ("ok", "no", "other"):
        journal.decide(run, "p", action, "instagram:acme")
        recs[action] = json.loads(_lines(journal.journal_path())[-1])
    journal.require_allowed(recs["ok"])
    with pytest.raises(UsageError):
        journal.require_allowed(recs["no"])
    with pytest.raises(UsageError):
        journal.require_allowed(recs["other"])
    with pytest.raises(UsageError):
        journal.require_allowed({"step": 2, "decision": "auto"})
    journal.require_allowed({**recs["other"], "approved_by": "author"})


def test_raw_write_creates_step2_record(social_data):
    run = journal.new_run("insights", "manual")
    rid = journal.write_raw(run, "insights", "instagram:acme", "/media", {"data": [{"id": "1"}]})
    rec = json.loads(_lines(journal.journal_path())[-1])
    assert rec["step"] == 2
    assert rec["source_ids"] == [rid]
    raw = [json.loads(x) for x in _lines(next((social_data / "social" / "raw" / "insights").glob("*.jsonl")))]
    assert raw[0]["id"] == rid


def test_raw_payload_tokens_are_redacted(social_data):
    run = journal.new_run("insights", "manual")
    journal.write_raw(run, "insights", "instagram:acme", "/me/accounts",
                      {"data": [{"id": "1", "access_token": "PAGETOK",
                                 "nested": [{"token": "PAGETOK2"}]}]})
    raw = next((social_data / "social" / "raw" / "insights").glob("*.jsonl")).read_text(encoding="utf-8")
    assert "PAGETOK" not in raw
    assert '"id": "1"' in raw


def test_registered_runtime_secret_is_refused(social_data):
    journal.register_secret("PAGETOK")
    run = journal.new_run("insights", "manual")
    jl_before = _lines(journal.journal_path())
    with pytest.raises(journal.SecretInRecord):
        journal.write_raw(run, "insights", "instagram:acme", "/x", {"x": "PAGETOK"})
    assert _lines(journal.journal_path()) == jl_before
    assert not list((social_data / "social").glob("raw/**/*.jsonl"))


@pytest.mark.parametrize("secret", ['a"b-secret', "a\\b-secret"])
def test_json_escaped_secret_is_refused_in_journal(social_data, secret):
    journal.register_secret(secret)
    run = journal.new_run("insights", "manual")
    before = _lines(journal.journal_path())
    with pytest.raises(journal.SecretInRecord):
        journal.record(run, 6, note=secret)
    assert _lines(journal.journal_path()) == before


@pytest.mark.parametrize("secret", ['a"b-secret', "a\\b-secret"])
def test_json_escaped_secret_is_refused_in_raw(social_data, secret):
    journal.register_secret(secret)
    run = journal.new_run("insights", "manual")
    before = _lines(journal.journal_path())
    with pytest.raises(journal.SecretInRecord):
        journal.write_raw(run, "insights", "instagram:acme", "/x", {"x": secret})
    assert _lines(journal.journal_path()) == before
    assert not list((social_data / "social").glob("raw/**/*.jsonl"))
