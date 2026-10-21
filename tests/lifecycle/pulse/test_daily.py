"""The daily pass: trigger once a day, stage order, the audit_map line and its footer."""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import UTC, datetime, timedelta

import pytest

from h2t_ops.core import paths, store
from h2t_ops.lifecycle.pulse import daily, view


@pytest.fixture(autouse=True)
def _machine(monkeypatch):
    monkeypatch.setenv("H2T_MACHINE_NAME", "test-machine")


@pytest.fixture
def popen(monkeypatch):
    calls: list = []
    monkeypatch.setattr(daily.subprocess, "Popen", lambda *a, **k: calls.append((a, k)))
    return calls


def _stamp(age: timedelta) -> None:
    ran = (datetime.now(UTC) - age).strftime("%Y-%m-%dT%H:%M:%SZ")
    store.replace(daily.stamp_path(), json.dumps({"ran_at": ran, "backfill_since_ns": 10**15}), place="state")


def _user_yaml(text: str) -> None:
    f = paths.config_dir() / "user.yaml"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(text, encoding="utf-8")


def test_maybe_spawn_once_a_day(popen):
    _stamp(timedelta(hours=1))
    assert daily.maybe_spawn() is False and popen == []          # fresh stamp
    _stamp(timedelta(hours=25))
    assert daily.maybe_spawn() is True and len(popen) == 1       # old stamp
    argv = popen[0][0][0]
    assert argv == [sys.executable, "-m", "h2t_ops.cli", "sessions", "daily"]
    assert daily.maybe_spawn() is False and len(popen) == 1      # the lock holds


def test_a_missing_stamp_spawns(popen):
    assert daily.maybe_spawn() is True and len(popen) == 1


def test_a_stale_lock_is_replaced(popen):
    _stamp(timedelta(hours=30))
    lock = daily.lock_path()
    store.create(lock, "9999", place="state")
    old = time.time() - 3 * 3600
    os.utime(lock, (old, old))
    assert daily.maybe_spawn() is True and len(popen) == 1
    assert lock.is_file() and time.time() - lock.stat().st_mtime < 600


def test_run_calls_stages_in_order(monkeypatch):
    seen: list[str] = []
    monkeypatch.setattr(daily.backfill, "run", lambda since_ns=0: seen.append(f"backfill:{since_ns}") or {})
    monkeypatch.setattr(daily.record, "settle_open", lambda: seen.append("settle") or 0)
    monkeypatch.setattr(daily.status, "refresh", lambda conn: seen.append("status") or 0)
    monkeypatch.setattr(daily.summary, "run", lambda conn: seen.append("summary") or {})
    monkeypatch.setattr(daily, "audit_map", lambda: seen.append("audit") or {"branches": 1})
    store.create(daily.lock_path(), "1", place="state")
    _stamp(timedelta(hours=30))
    out = daily.run()
    assert seen == [f"backfill:{10**15 - 86400 * 10**9}", "settle", "status", "summary", "audit"]
    written = json.loads(daily.stamp_path().read_text(encoding="utf-8"))
    assert written["audit_map"] == {"branches": 1} and written["backfill_since_ns"] > 10**15
    assert out["audit_map"] == {"branches": 1}
    assert not daily.lock_path().exists()


def _fake_script(tmp_path, body: str) -> None:
    script = tmp_path / "fake_audit.py"
    script.write_text(body, encoding="utf-8")
    _user_yaml(f"sessions:\n  audit_map: [{json.dumps(sys.executable)}, {json.dumps(str(script))}]\n")


_WRITE_TSV = r"""import sys
out = sys.argv[sys.argv.index('--out') + 1]
open(out, 'w').write('repo\tbranch_count\tstash_count\na\t3\t1\nb\t2\t0\n')
"""


def test_audit_map_counts(tmp_path):
    _fake_script(tmp_path, _WRITE_TSV)
    got = daily.audit_map()
    assert (got["branches"], got["stash"]) == (3, 1)
    assert got["report"].endswith("audit-map.tsv") and got["ran_at"]


def test_audit_map_not_configured():
    assert daily.audit_map() == {}


@pytest.mark.parametrize("body", ["import sys\nsys.exit(3)\n", "pass\n"])
def test_audit_map_failure_is_an_error_not_a_raise(tmp_path, body):
    _fake_script(tmp_path, body)
    assert daily.audit_map()["error"]


def test_audit_map_missing_program(tmp_path):
    _user_yaml("sessions:\n  audit_map: [no-such-program-xyz]\n")
    assert daily.audit_map()["error"]


def test_footer_without_config():
    assert view.footer() == "Работа без сессии: audit_map не настроен (sessions.audit_map в config/user.yaml)"


def test_footer_with_counts_and_with_error(tmp_path):
    _user_yaml("sessions:\n  audit_map: [x]\n")
    store.replace(daily.stamp_path(), json.dumps({"ran_at": "2026-10-20T08:00:00Z", "audit_map": {
        "branches": 4, "stash": 2, "report": "r.tsv", "ran_at": "2026-10-20T08:00:00Z"}}), place="state")
    assert view.footer() == "Работа без сессии: 4 веток, 2 stash — r.tsv (2026-10-20)"
    store.replace(daily.stamp_path(), json.dumps({"ran_at": "2026-10-20T08:00:00Z",
                                                  "audit_map": {"error": "код 3"}}), place="state")
    assert view.footer() == "Работа без сессии: audit_map не отработал (код 3)"


def test_sessions_daily_prints_the_result_as_json(monkeypatch, capsys):
    from h2t_ops.lifecycle.pulse import cli
    monkeypatch.setattr(daily, "run", lambda: {"ran_at": "x", "audit_map": {}})
    assert cli.main(["daily", "--json"]) == 0
    assert '"ran_at": "x"' in capsys.readouterr().out
