"""Eval sessions are records: records/evals/<machine>/<skill>/<run>.json (#548 §3, §7.1)."""
import json
import re
import sys
import types

from h2t_ops.core import paths, store
from h2t_ops.lifecycle.eval import session as sess
from h2t_ops.lifecycle.eval.session import SkillEval
from h2t_ops.lifecycle.eval.status import get_status


def _skill_dir(skill: str):
    return paths.records("evals", paths.machine_name()) / skill


def test_session_lands_in_records_evals_machine_skill(monkeypatch):
    monkeypatch.setenv("H2T_EVALS_MODE", "local")
    monkeypatch.setenv("H2T_MACHINE_NAME", "mac")
    with SkillEval("session-start", domain="dev", project="p"):
        pass
    [f] = list((paths.records("evals") / "mac" / "session-start").glob("*.json"))
    # <run> is the 3.x file name: <prefix>-<stamp>-<uuid8>
    assert re.fullmatch(r"se-\d{4}-\d{2}-\d{2}-\d{6}-\d{6}-[0-9a-f]{8}\.json", f.name)
    assert json.loads(f.read_text(encoding="utf-8"))["skill"] == "session-start"
    assert not paths.legacy("evals").exists()


def test_a_taken_run_name_gets_the_next_suffix(monkeypatch):
    """records are created, never replaced: a file with the run's name stays as it is."""
    monkeypatch.setenv("H2T_EVALS_MODE", "local")
    monkeypatch.setattr(SkillEval, "_run_name", lambda self: "ha-fixed")
    d = _skill_dir("handoff")
    d.mkdir(parents=True)
    (d / "ha-fixed.json").write_text("theirs", encoding="utf-8")
    for _ in range(2):
        with SkillEval("handoff", domain="dev", project="p"):
            pass
    assert (d / "ha-fixed.json").read_text(encoding="utf-8") == "theirs"
    assert json.loads((d / "ha-fixed-2.json").read_text(encoding="utf-8"))["skill"] == "handoff"
    assert (d / "ha-fixed-3.json").is_file()


def test_spool_is_handed_to_the_sdk_through_store(monkeypatch):
    """The SDK opens state/evals-spool.sqlite itself; store.managed hands it over (§7.2)."""
    seen = {}

    class FakeClient:
        def __init__(self, *, service_url, token, spool_path):
            seen["spool"] = spool_path
            seen["delegated"] = store.delegated(spool_path)

        def flush(self, **kw):
            pass

    class FakeSession:
        def __init__(self, **kw):
            pass

        def start(self):
            pass

        def metric(self, key, **kw):
            pass

        def finish(self, **kw):
            pass

    fake = types.ModuleType("h2t_evals.sdk")
    fake.EvalClient, fake.EvalSession = FakeClient, FakeSession
    monkeypatch.setitem(sys.modules, "h2t_evals", types.ModuleType("h2t_evals"))
    monkeypatch.setitem(sys.modules, "h2t_evals.sdk", fake)
    monkeypatch.setenv("H2T_EVALS_MODE", "push")
    with SkillEval("research", domain="d", project="p"):
        pass
    assert seen == {"spool": str(paths.state_dir() / "evals-spool.sqlite"), "delegated": "h2t_evals"}


def test_written_session_is_read_by_report_and_status(monkeypatch, capsys):
    """The round trip: SkillEval writes, `evals report` loads it, `evals status` counts it."""
    from h2t_ops.cli import dispatch

    monkeypatch.setenv("H2T_EVALS_MODE", "local")
    with SkillEval("session-start", domain="dev", project="p"):
        pass
    capsys.readouterr()
    assert dispatch(["evals", "report", "--json", "--min-n", "1"]) == 0
    report = json.loads(capsys.readouterr().out)["result"]
    assert report["load"]["loaded"] == 1
    st = get_status(env={})
    assert st["session_count"] == 1
    assert st["local_dir"] == str(paths.records("evals"))


def test_status_counts_sessions_of_every_machine(monkeypatch):
    monkeypatch.setattr(sess, "_sdk_available", lambda: False)
    for machine in ("mac", "win"):
        d = paths.records("evals", machine) / "handoff"
        d.mkdir(parents=True)
        (d / "ha-1.json").write_text("{}", encoding="utf-8")
    assert get_status(env={})["session_count"] == 2
