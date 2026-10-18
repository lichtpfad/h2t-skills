"""Mutual exclusion of store.append, deterministic (§7.3 «Тест блокировки»)."""
import subprocess
import sys
import time

from h2t_ops.core import store

HOLDER = r"""
import os, sys, time
from h2t_ops.core import store
fd = os.open(sys.argv[1], os.O_WRONLY | os.O_APPEND | os.O_CREAT | getattr(os, "O_BINARY", 0), 0o644)
with store._lock(fd):
    print("locked", flush=True)
    time.sleep(1.0)
    os.write(fd, b"A\n")
os.close(fd)
"""


def test_append_waits_for_the_holder(tmp_path, monkeypatch):
    monkeypatch.setenv("H2T_PATH_ROOT", str(tmp_path / "root"))
    target = tmp_path / "root" / "records" / "activity" / "m.jsonl"
    target.parent.mkdir(parents=True)
    holder = subprocess.Popen([sys.executable, "-c", HOLDER, str(target)],
                              stdout=subprocess.PIPE, text=True)
    assert holder.stdout.readline().strip() == "locked"
    t0 = time.monotonic()
    store.append(target, "B", place="records.activity")
    waited = time.monotonic() - t0
    holder.wait(timeout=10)
    assert waited >= 0.7, f"append did not wait for the lock ({waited:.2f}s)"
    assert target.read_text().splitlines() == ["A", "B"]


def test_two_writers_1000_lines_each_stay_whole(tmp_path, monkeypatch):
    monkeypatch.setenv("H2T_PATH_ROOT", str(tmp_path / "root"))
    target = tmp_path / "root" / "records" / "activity" / "m.jsonl"
    code = ("import sys\nfrom h2t_ops.core import store\n"
            "for i in range(1000): store.append(sys.argv[1], sys.argv[2] + str(i) + 'x' * 200, "
            "place='records.activity')\n")
    env = {**__import__("os").environ, "H2T_PATH_ROOT": str(tmp_path / "root")}
    ps = [subprocess.Popen([sys.executable, "-c", code, str(target), tag], env=env) for tag in "PQ"]
    for p in ps:
        assert p.wait(timeout=120) == 0
    lines = target.read_text().splitlines()
    assert len(lines) == 2000
    assert all(len(line) >= 201 and line[0] in "PQ" and line.endswith("x") for line in lines)
