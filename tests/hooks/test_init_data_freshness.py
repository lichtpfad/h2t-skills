"""INIT_DATA carries `cwd` and `at`, as GATHER_META does (spec §6.3, Task 12).

init-project uses the detection in its context only when it was made for this directory
in the last 120 s; otherwise it runs `h2t-detect-project` itself — the only path in Codex,
which runs no hooks. Without the two fields that rule cannot be applied.
"""
from __future__ import annotations

import json
import tempfile

from h2t_ops.hooks import gather


def test_init_data_names_its_directory_and_time(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.delenv("H2T_CONFIG_ROOT", raising=False)
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))  # the gather lock
    work = tmp_path / "work"
    work.mkdir()

    reply = gather.handle({"hook_event_name": "PreToolUse", "tool_name": "Skill",
                           "tool_input": {"skill": "h2t-core:init-project"},
                           "cwd": str(work)})

    assert reply.text.startswith("INIT_DATA: {"), reply.text[:200]
    data = json.loads(reply.text.removeprefix("INIT_DATA: "))
    assert data["cwd"] == str(work)
    assert data["at"][:4].isdigit() and ("+" in data["at"] or "-" in data["at"][10:])
