"""The 3.x handlers give what test_command_hooks.py records, on the same scenarios.

This is what makes those records the 3.x behaviour and not just the port's: each scenario
runs the old handler from plugins/h2t-core/hooks-handlers — bash for the git hooks, this
interpreter for the two python ones — and must meet the same expectation. Task 12a deletes
the old handlers and this test with them; test_command_hooks.py keeps the records.
"""
from __future__ import annotations

import os
import shutil
import sys

import pytest

from tests.hooks import test_command_hooks as ch

OLD = ch.ROOT / "plugins" / "h2t-core" / "hooks-handlers"
BASH = shutil.which("bash")
# Where the port differs on purpose. Anything else that differs is a defect.
DECLARED = {
    # bash's own complaint about `[ 2 -le lots ]`, printed before the refusal; not a message.
    "bulk-precommit/threshold-not-a-number": "integer expression expected",
}
pytestmark = pytest.mark.skipif(os.name == "nt" or BASH is None or ch.GIT is None,
                                reason="the 3.x handlers are bash and POSIX-only")


@pytest.mark.parametrize("s", ch.SCENARIOS, ids=[ch.scenario_id(s) for s in ch.SCENARIOS])
def test_the_3x_handler_meets_the_record(s, tmp_path):
    repo, env = ch.prepare(s, tmp_path)
    handler = OLD / s["hook"]
    interpreter = sys.executable if handler.read_text(encoding="utf-8").startswith(
        "#!/usr/bin/env python3") else BASH
    done = ch.run([interpreter, str(handler)], repo, env, s.get("stdin", ""))
    noise = DECLARED.get(ch.scenario_id(s))
    if noise:
        first, rest = done.stderr.split(b"\n", 1)
        assert noise.encode() in first, done.stderr
        done.stderr = rest
    ch.check(s, done, repo, tmp_path)
