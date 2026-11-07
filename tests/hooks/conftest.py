"""Hook tests: no SessionStart in this directory starts a real `sessions daily` child."""
from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest


@pytest.fixture(autouse=True)
def _fresh_daily_stamp(_isolate_home_writes):
    """Seed a fresh daily-pass stamp in the isolated home, so `daily.maybe_spawn` returns False.
    A test of the trigger removes or replaces it. Subprocess rigs with their own HOME
    (test_budgets) seed their own."""
    from h2t_ops.lifecycle.pulse import daily
    daily.stamp_path().parent.mkdir(parents=True, exist_ok=True)
    daily.stamp_path().write_text(
        json.dumps({"ran_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")}), encoding="utf-8")
