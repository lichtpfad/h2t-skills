from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

E2E_PREFIX = "h2t-e2e-connector-api"
EVIDENCE_PATH = Path("docs/reports/e2e/connector-api-coverage-p0.json")


def _enabled() -> bool:
    return os.environ.get("H2T_E2E_CONNECTORS") == "1"


def _need(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        pytest.skip(f"{name} is required for this connector E2E")
    return value


def _run(*args: str) -> dict:
    if not _enabled():
        pytest.skip("set H2T_E2E_CONNECTORS=1 to run connector E2E")
    result = subprocess.run(
        [sys.executable, "-m", "h2t_ops.cli", *args, "--json"],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    return payload["result"]


def _record(
    connector: str,
    command: str,
    result: dict,
    *,
    mode: str = "read_only",
    resource: dict | None = None,
    skip_reason: str | None = None,
) -> None:
    EVIDENCE_PATH.parent.mkdir(parents=True, exist_ok=True)
    if EVIDENCE_PATH.exists():
        data = json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))
    else:
        data = {"schema": "connector_api_coverage_e2e/v0.1", "runs": []}
    data["runs"].append({
        "at": datetime.now(UTC).isoformat(),
        "connector": connector,
        "command": command,
        "mode": mode,
        "ok": True,
        "resource": resource or {"cleanup": "not_created"},
        "skip_reason": skip_reason,
        "result_keys": sorted(result.keys()) if isinstance(result, dict) else [],
    })
    EVIDENCE_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def test_e2e_harness_skips_without_opt_in():
    if _enabled():
        pytest.skip("opt-in enabled; skip-only test not applicable")
    with pytest.raises(pytest.skip.Exception):
        _run("connectors")
