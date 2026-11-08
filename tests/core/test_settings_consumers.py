"""Consumers of the interface settings read env first, and carry no author default (#581)."""
import sys
import types
from datetime import date

from h2t_ops.core import paths
from h2t_ops.lifecycle.eval.session import SkillEval
from h2t_ops.lifecycle.eval.status import get_status

_SCHEMA = """notion:
  tasks_schema:
    title: Name
    due: Due
    due_kind: Kind
    day: Day
    done: Done
    kinds: {external: Ext, check: Chk, intent: Int}
"""


def test_lake_place_reads_env(monkeypatch, tmp_path):
    monkeypatch.setenv("H2T_PATH_LAKE", str(tmp_path / "lk"))
    assert paths.place("lake") == tmp_path / "lk"
    assert paths.source("lake") == "H2T_PATH_LAKE"


def test_notion_tasks_db_reads_env(capsys, monkeypatch):
    from h2t_ops.cli import dispatch
    from h2t_ops.connectors.notion import client

    f = paths.config_dir() / "user.yaml"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(_SCHEMA, encoding="utf-8")
    monkeypatch.setenv("H2T_NOTION_TASKS_DB", "db1")
    seen = {}

    class Fake:
        def query_database_page(self, database_id, filter_dict=None, **_):
            seen["db"] = database_id
            return {"items": [], "truncated": False}

    monkeypatch.setattr(client, "NotionClient", Fake)
    rc = dispatch(["notion", "brief-tasks", "--today", date(2026, 11, 8).isoformat()])
    assert rc == 0, capsys.readouterr().err
    assert seen == {"db": "db1"}


def test_evals_status_without_url_is_unconfigured():
    assert get_status(env={})["service_url"] is None


def _fake_sdk(monkeypatch, captured):
    class FakeSession:
        def __init__(self, **kw):
            captured["session"] = True

        def start(self): ...
        def metric(self, key, **kw): ...
        def finish(self, **kw): ...

    class FakeClient:
        def __init__(self, **kw):
            captured["client"] = kw

        def flush(self, **kw): ...

    fake = types.ModuleType("h2t_evals.sdk")
    fake.EvalClient = FakeClient
    fake.EvalSession = FakeSession
    monkeypatch.setitem(sys.modules, "h2t_evals", types.ModuleType("h2t_evals"))
    monkeypatch.setitem(sys.modules, "h2t_evals.sdk", fake)
    for var in ("H2T_EVALS_MODE", "H2T_EVALS_ENABLED", "H2T_EVALS_TOKEN", "H2T_EVALS_SERVICE_URL"):
        monkeypatch.delenv(var, raising=False)


def test_evals_session_without_url_does_not_probe(monkeypatch):
    captured: dict = {}
    _fake_sdk(monkeypatch, captured)
    monkeypatch.setenv("H2T_EVALS_MODE", "push")
    monkeypatch.setenv("H2T_EVALS_TOKEN", "tok")
    with SkillEval("research", domain="d", project="p"):
        pass
    assert captured == {}


def test_evals_url_from_secrets_file_still_works(monkeypatch):
    captured: dict = {}
    _fake_sdk(monkeypatch, captured)
    f = paths.secrets_shared() / "h2t-evals.env"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("H2T_EVALS_SERVICE_URL=https://evals.example.test\nH2T_EVALS_TOKEN=tok\n",
                 encoding="utf-8")
    monkeypatch.setenv("H2T_EVALS_MODE", "push")
    with SkillEval("research", domain="d", project="p"):
        pass
    assert captured["client"]["service_url"] == "https://evals.example.test"
