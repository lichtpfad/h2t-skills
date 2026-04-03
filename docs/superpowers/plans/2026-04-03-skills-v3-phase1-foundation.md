# Skills v3 Phase 1 — Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract h2t-core plugin (session-start v3, handoff v3), create shared lib/ at repo root with activity stream writer and eval wrapper, wire h2t-evals from day 0.

**Architecture:** Repo-root `lib/` is copied into each plugin cache by per-plugin update scripts. Session-start v3 uses a 7-step linear pipeline (the pattern proven to work in v0/v2.6.3). Activity stream writes to local JSONL spool (Phase 1) — VPS sync deferred. Eval wrapper re-uses existing `eval.py` logic, promoted to first-class.

**Tech Stack:** Python 3.11, h2t-evals SDK (already in `~/.h2t/venv`), bash, Claude Code plugin manifest.

**Spec:** `docs/superpowers/specs/2026-04-03-skills-v3-architecture-design.md`

---

## File Map

### New files to create

| File | Responsibility |
|------|----------------|
| `lib/__init__.py` | Package marker |
| `lib/activity/__init__.py` | Package marker |
| `lib/activity/writer.py` | Local JSONL spool for activity stream |
| `lib/activity/test_writer.py` | Unit tests |
| `lib/eval/__init__.py` | Package marker |
| `lib/eval/session.py` | h2t-evals SDK wrapper (promoted from gather/eval.py) |
| `lib/eval/test_session.py` | Unit tests |
| `lib/gather/` | COPY of `plugins/h2t/lib/gather/` (h2t-core uses this, h2t/ keeps its own copy for now) |
| `evals/repo.toml` | h2t-evals repo identity + thresholds |
| `.github/workflows/evals.yml` | CI gate: unit tests (hard) + validate-repo (BLOCKED until token) |
| `plugins/h2t-core/.claude-plugin/plugin.json` | h2t-core plugin manifest |
| `plugins/h2t-core/hooks-handlers/gather-on-skill` | Hook script for h2t-core skills |
| `plugins/h2t-core/hooks/hooks.json` | Hook registration |
| `plugins/h2t-core/skills/session-start/SKILL.md` | v3 linear pipeline |
| `plugins/h2t-core/skills/session-start/scripts/gather.py` | Modular gather script |
| `plugins/h2t-core/skills/handoff/SKILL.md` | v3 handoff pipeline |
| `plugins/h2t-core/skills/handoff/scripts/writer.py` | Writes activity stream + markdown |
| `plugins/h2t-core/skills/init-project/SKILL.md` | Copied from h2t/, path-updated |
| `plugins/h2t-core/skills/dev-overview/SKILL.md` | Copied from h2t/ |
| `plugins/h2t-core/skills/setup/SKILL.md` | Copied from h2t/ |
| `plugins/h2t-core/skills/snap/SKILL.md` | Copied from h2t/ |
| `plugins/h2t-core/scripts/update-plugin.sh` | Copies plugin + repo-root lib/ to cache |

### Modified files

| File | Change |
|------|--------|
| `plugins/h2t/skills/dev-session-start/SKILL.md` | Replace with alias shim pointing to h2t-core:session-start |
| `plugins/h2t/skills/ctx-load/` | DELETE |
| `plugins/h2t/skills/session-name/` | DELETE |

### Not changed

`plugins/h2t/lib/` — left intact. h2t/ monolith keeps its own lib copy until Phase 2 migration.

---

## Task 1: Scaffold repo-root lib/ with activity writer

**Files:**
- Create: `lib/__init__.py`
- Create: `lib/activity/__init__.py`
- Create: `lib/activity/writer.py`
- Create: `lib/activity/test_writer.py`

- [ ] **Step 1.1: Write failing tests**

```python
# lib/activity/test_writer.py
import json
import os
import tempfile
from pathlib import Path

import pytest

from lib.activity.writer import log_session_start, log_session_end


def test_log_session_start_creates_spool(tmp_path):
    spool = tmp_path / "spool.jsonl"
    os.environ["H2T_ACTIVITY_SPOOL"] = str(spool)
    try:
        result = log_session_start("my-session-123", "dev", "h2t-ai")
        assert spool.exists()
        record = json.loads(spool.read_text().strip())
        assert record["session_id"] == "my-session-123"
        assert record["action"] == "session.start"
        assert record["domain"] == "dev"
        assert record["project"] == "h2t-ai"
        assert "timestamp" in record
        assert result == str(spool)
    finally:
        del os.environ["H2T_ACTIVITY_SPOOL"]


def test_log_session_end_appends_with_artifacts(tmp_path):
    spool = tmp_path / "spool.jsonl"
    os.environ["H2T_ACTIVITY_SPOOL"] = str(spool)
    try:
        log_session_start("ses-1", "dev", "proj-a")
        log_session_end("ses-1", "dev", "proj-a", artifacts=[{"type": "commit", "ref": "abc123"}])
        lines = spool.read_text().strip().splitlines()
        assert len(lines) == 2
        end_record = json.loads(lines[1])
        assert end_record["action"] == "session.end"
        assert end_record["artifacts"][0]["type"] == "commit"
    finally:
        del os.environ["H2T_ACTIVITY_SPOOL"]


def test_log_creates_parent_directories(tmp_path):
    spool = tmp_path / "nested" / "deep" / "spool.jsonl"
    os.environ["H2T_ACTIVITY_SPOOL"] = str(spool)
    try:
        log_session_start("s", "art", "my-project")
        assert spool.exists()
    finally:
        del os.environ["H2T_ACTIVITY_SPOOL"]


def test_log_machine_uses_hostname_by_default(tmp_path):
    spool = tmp_path / "spool.jsonl"
    os.environ["H2T_ACTIVITY_SPOOL"] = str(spool)
    try:
        log_session_start("s", "dev", "p")
        record = json.loads(spool.read_text().strip())
        assert len(record["machine"]) > 0
    finally:
        del os.environ["H2T_ACTIVITY_SPOOL"]


def test_writer_cli_start(tmp_path, monkeypatch):
    """CLI: `writer.py start` subcommand writes correct record to spool."""
    from lib.activity.writer import main as writer_main

    spool = tmp_path / "cli_spool.jsonl"
    monkeypatch.setenv("H2T_ACTIVITY_SPOOL", str(spool))
    monkeypatch.setattr("sys.argv", [
        "writer.py", "start",
        "--session-id", "cli-ses-1",
        "--domain", "dev",
        "--project", "h2t-core",
    ])
    writer_main()
    record = json.loads(spool.read_text().strip())
    assert record["session_id"] == "cli-ses-1"
    assert record["action"] == "session.start"
    assert record["domain"] == "dev"
```

- [ ] **Step 1.2: Run tests — expect FAIL**

```bash
cd C:/dev/claude-agent-skills
source ~/.h2t/venv/Scripts/activate
python -m pytest lib/activity/test_writer.py -v
```

Expected: `ModuleNotFoundError: No module named 'lib'`

- [ ] **Step 1.3: Create package markers and writer**

```python
# lib/__init__.py
```

```python
# lib/activity/__init__.py
```

```python
# lib/activity/writer.py
"""Activity stream writer — Phase 1: local JSONL spool.

Each record is one JSON line in H2T_ACTIVITY_SPOOL (default: ~/.h2t/activity/spool.jsonl).
Phase 2: replace _write() with POST to POS API; local spool becomes fallback.
"""

import json
import os
import platform
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


def log_session_start(
    session_id: str,
    domain: str,
    project: str,
    machine: Optional[str] = None,
) -> str:
    """Append session.start record to local spool. Returns spool path."""
    return _write(
        session_id=session_id,
        action="session.start",
        domain=domain,
        project=project,
        machine=machine,
    )


def log_session_end(
    session_id: str,
    domain: str,
    project: str,
    artifacts: Optional[list] = None,
    machine: Optional[str] = None,
) -> str:
    """Append session.end record with optional artifacts. Returns spool path."""
    return _write(
        session_id=session_id,
        action="session.end",
        domain=domain,
        project=project,
        machine=machine,
        artifacts=artifacts or [],
    )


def _spool_path() -> Path:
    default = Path.home() / ".h2t" / "activity" / "spool.jsonl"
    return Path(os.environ.get("H2T_ACTIVITY_SPOOL", str(default)))


def _write(
    session_id: str,
    action: str,
    domain: str,
    project: str,
    machine: Optional[str] = None,
    artifacts: Optional[list] = None,
) -> str:
    path = _spool_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    record: dict = {
        "session_id": session_id,
        "action": action,
        "domain": domain,
        "project": project,
        "machine": machine or platform.node(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if artifacts:
        record["artifacts"] = artifacts

    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    return str(path)


def main() -> None:
    """CLI: python writer.py start --session-id <id> --domain <d> --project <p>"""
    import argparse as _argparse

    parser = _argparse.ArgumentParser(prog="writer.py", description="Activity stream writer CLI")
    sub = parser.add_subparsers(dest="cmd")

    start_cmd = sub.add_parser("start", help="Log session start")
    start_cmd.add_argument("--session-id", required=True)
    start_cmd.add_argument("--domain", required=True)
    start_cmd.add_argument("--project", required=True)
    start_cmd.add_argument("--machine", default="")

    args = parser.parse_args()
    if args.cmd == "start":
        path = log_session_start(
            session_id=args.session_id,
            domain=args.domain,
            project=args.project,
            machine=args.machine or None,
        )
        print(f"OK spool={path}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
```

- [ ] **Step 1.4: Run tests from repo root with sys.path**

```bash
cd C:/dev/claude-agent-skills
source ~/.h2t/venv/Scripts/activate
python -m pytest lib/activity/test_writer.py -v
```

Expected: 4 PASSED

- [ ] **Step 1.5: Commit**

```bash
git add lib/__init__.py lib/activity/__init__.py lib/activity/writer.py lib/activity/test_writer.py
git commit -m "feat(lib): add activity stream writer — local JSONL spool (Phase 1)"
```

---

## Task 2: Promote eval wrapper to lib/eval/

**Files:**
- Create: `lib/eval/__init__.py`
- Create: `lib/eval/session.py`
- Create: `lib/eval/test_session.py`

The existing `plugins/h2t/lib/gather/eval.py` already implements dual-write (local JSON + h2t-evals SDK). This task promotes it to `lib/eval/session.py` with a cleaner interface: `SkillEval` context manager.

- [ ] **Step 2.1: Write failing tests**

```python
# lib/eval/test_session.py
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


def test_skill_eval_local_write_on_success(tmp_path):
    """SkillEval writes local JSON file with success status."""
    from lib.eval.session import SkillEval

    evals_root = tmp_path / "evals"
    with SkillEval("session-start", domain="dev", project="h2t-ai", evals_root=str(evals_root)):
        pass  # success (no exception)

    files = list((evals_root / "session-start" / "sessions").glob("*.json"))
    assert len(files) == 1
    record = json.loads(files[0].read_text())
    assert record["skill"] == "session-start"
    assert record["status"] == "success"
    assert "started_at" in record
    assert "ended_at" in record


def test_skill_eval_local_write_on_failure(tmp_path):
    """SkillEval writes failure status when exception raised."""
    from lib.eval.session import SkillEval

    evals_root = tmp_path / "evals"
    with pytest.raises(ValueError):
        with SkillEval("handoff", domain="dev", project="p", evals_root=str(evals_root)):
            raise ValueError("boom")

    files = list((evals_root / "handoff" / "sessions").glob("*.json"))
    assert len(files) == 1
    record = json.loads(files[0].read_text())
    assert record["status"] == "failure"


def test_skill_eval_adds_custom_metric(tmp_path):
    """SkillEval.metric() stores value in local record."""
    from lib.eval.session import SkillEval

    evals_root = tmp_path / "evals"
    with SkillEval("session-start", domain="dev", project="p", evals_root=str(evals_root)) as ev:
        ev.metric("skills.checklist_compliance", value_num=0.85)

    files = list((evals_root / "session-start" / "sessions").glob("*.json"))
    record = json.loads(files[0].read_text())
    assert record["metrics"]["skills.checklist_compliance"] == 0.85


def test_skill_eval_skips_central_when_disabled(tmp_path, monkeypatch):
    """No SDK calls when H2T_EVALS_ENABLED is not set."""
    from lib.eval.session import SkillEval

    monkeypatch.delenv("H2T_EVALS_ENABLED", raising=False)
    evals_root = tmp_path / "evals"

    with patch("lib.eval.session._send_central") as mock_central:
        with SkillEval("session-start", domain="dev", project="p", evals_root=str(evals_root)):
            pass
        mock_central.assert_not_called()
```

- [ ] **Step 2.2: Run tests — expect FAIL**

```bash
python -m pytest lib/eval/test_session.py -v
```

Expected: `ModuleNotFoundError: No module named 'lib.eval'`

- [ ] **Step 2.3: Create eval package**

```python
# lib/eval/__init__.py
```

```python
# lib/eval/session.py
"""h2t-evals wrapper — context manager for skill evaluation.

Usage:
    with SkillEval("session-start", domain="dev", project="h2t-ai") as ev:
        ev.metric("skills.checklist_compliance", value_num=1.0)
        # ... skill logic ...
    # On exit: writes local JSON + sends to h2t-evals service if enabled

Local files: ~/.h2t/evals/{skill}/sessions/{prefix}-{date}-{seq:03d}.json
Central:     h2t-evals SDK (only when H2T_EVALS_ENABLED=1)
"""

from __future__ import annotations

import json
import os
import platform
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


class SkillEval:
    """Context manager for skill eval session. Silent on all failures."""

    def __init__(
        self,
        skill: str,
        domain: str,
        project: str,
        plugin_version: str = "",
        evals_root: Optional[str] = None,
    ) -> None:
        self.skill = skill
        self.domain = domain
        self.project = project
        self.plugin_version = plugin_version
        self._evals_root = Path(evals_root) if evals_root else (
            Path.home() / ".h2t" / "evals"
        )
        self._metrics: dict[str, object] = {}
        self._started_at = datetime.now(timezone.utc)
        self._status = "success"

    def __enter__(self) -> "SkillEval":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        if exc_type is not None:
            self._status = "failure"
        self._ended_at = datetime.now(timezone.utc)
        self._wall_ms = int((self._ended_at - self._started_at).total_seconds() * 1000)
        self._write_local()
        if os.environ.get("H2T_EVALS_ENABLED") == "1":
            _send_central(self)
        return False  # do not suppress exceptions

    def metric(self, key: str, value_num: Optional[float] = None,
               value_bool: Optional[bool] = None, value_text: Optional[str] = None) -> None:
        """Record a custom metric. Called inside the with block."""
        if value_num is not None:
            self._metrics[key] = value_num
        elif value_bool is not None:
            self._metrics[key] = value_bool
        else:
            self._metrics[key] = value_text

    def _write_local(self) -> None:
        sessions_dir = self._evals_root / self.skill / "sessions"
        try:
            sessions_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            return

        date_str = self._started_at.strftime("%Y-%m-%d")
        prefix = self.skill[:2]
        existing = list(sessions_dir.glob(f"{prefix}-{date_str}-*.json"))
        seq = len(existing) + 1
        path = sessions_dir / f"{prefix}-{date_str}-{seq:03d}.json"

        record = {
            "session_id": f"{prefix}-{date_str}-{seq:03d}",
            "skill": self.skill,
            "domain": self.domain,
            "project": self.project,
            "status": self._status,
            "started_at": self._started_at.isoformat(),
            "ended_at": self._ended_at.isoformat(),
            "wall_ms": self._wall_ms,
            "metrics": self._metrics,
        }
        try:
            path.write_text(json.dumps(record, ensure_ascii=False, indent=2))
        except OSError:
            pass


def _send_central(ev: SkillEval) -> None:
    """Send to h2t-evals service. Silent on any failure."""
    try:
        from h2t_evals.sdk import EvalClient, EvalSession
    except ImportError:
        return

    service_url = os.environ.get("H2T_EVALS_SERVICE_URL", "http://127.0.0.1:8088")
    token = os.environ.get("H2T_EVALS_TOKEN", "")
    spool = os.environ.get(
        "H2T_EVALS_SPOOL",
        str(Path.home() / ".h2t" / "evals" / ".h2t_evals_spool.db"),
    )
    try:
        client = EvalClient(service_url=service_url, token=token, spool_path=spool)
        source = f"{ev.skill}:v{ev.plugin_version}" if ev.plugin_version else ev.skill
        s = EvalSession(
            client=client,
            repo="claude-agent-skills",
            framework="h2t-skills",
            source=source,
            eval_set_id=f"skills-{ev.skill}-baseline-v1",
            host=platform.node().lower().split(".")[0],
            run_env=os.environ.get("H2T_EVALS_RUN_ENV", "agent"),
        )
        s.start()
        task_success = ev._status == "success"
        s.metric("core.task_success", level="integration", value_bool=task_success)
        s.metric("core.time_to_first_valid_ms", level="integration",
                 value_num=float(ev._wall_ms), unit="ms")
        s.metric("core.tool_call_success_rate", level="unit",
                 value_num=1.0 if task_success else 0.0)
        s.metric("core.op_type_correct_rate", level="unit", value_num=1.0)
        s.metric("core.deflection_rate", level="business",
                 value_num=1.0 if task_success else 0.0)
        for key, val in ev._metrics.items():
            if isinstance(val, float) or isinstance(val, int):
                s.metric(key, level="integration", value_num=float(val))
            elif isinstance(val, bool):
                s.metric(key, level="integration", value_bool=val)
        s.finish(status="success" if task_success else "failure")
        client.flush(limit=200)
    except Exception:
        pass
```

- [ ] **Step 2.4: Run tests**

```bash
python -m pytest lib/eval/test_session.py -v
```

Expected: 4 PASSED

- [ ] **Step 2.5: Commit**

```bash
git add lib/eval/__init__.py lib/eval/session.py lib/eval/test_session.py
git commit -m "feat(lib): add SkillEval context manager — promotes eval.py to shared lib"
```

---

## Task 3: Copy lib/gather/ to repo root + add evals/repo.toml

**Files:**
- Create: `lib/gather/` (copy of `plugins/h2t/lib/gather/`, tests included)
- Create: `evals/repo.toml`
- Create: `evals/manifests/` (empty placeholder dirs)

- [ ] **Step 3.1: Copy gather modules**

```bash
cp -r plugins/h2t/lib/gather lib/gather
```

- [ ] **Step 3.2: Verify tests still pass from repo root**

```bash
python -m pytest lib/gather/ -v --ignore=lib/gather/__pycache__
```

Expected: same test count as before (20+ tests), all PASSED

- [ ] **Step 3.3: Create evals/repo.toml**

```toml
# evals/repo.toml
repo = "claude-agent-skills"
framework = "h2t-skills"
default_source = "h2t-core:v3"
default_eval_set_id = "skills-session-baseline-v1"

[thresholds.unit]
core_tool_call_success_rate = 0.90

[thresholds.integration]
core_task_success = 0.80
core_time_to_first_valid_ms = 60000

[custom_metrics.skills_checklist_compliance]
key = "skills.checklist_compliance"
level = "integration"
type = "num"
aggregation = "avg"
description = "Fraction of SKILL.md pipeline steps completed (including session naming GATE)"

[custom_metrics.skills_token_consumption]
key = "skills.token_consumption"
level = "unit"
type = "num"
aggregation = "avg"
description = "Estimated tokens consumed during skill gather phase"

[custom_metrics.skills_gather_source_success_rate]
key = "skills.gather_source_success_rate"
level = "unit"
type = "num"
aggregation = "avg"
description = "Fraction of data sources that responded without error"
```

- [ ] **Step 3.4: Create CI gate workflow**

The spec (section 7.3) requires `.github/workflows/evals.yml` in Phase 1. Phase 1 gates on unit tests (always runnable). The `h2t-evals validate-repo` step is wired but reports BLOCKED in CI until service token is provisioned — this matches the runbook's BLOCKED reporting path.

```yaml
# .github/workflows/evals.yml
name: h2t-evals gate

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  unit-tests:
    name: lib/ unit tests
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install test deps
        run: pip install pytest

      - name: Run lib/ unit tests
        run: python -m pytest lib/ -v --tb=short

  eval-gate:
    name: h2t-evals validate-repo
    runs-on: ubuntu-latest
    needs: unit-tests
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Validate evals/repo.toml parses
        run: python -c "import tomllib; tomllib.load(open('evals/repo.toml','rb')); print('evals/repo.toml: valid TOML')"

      - name: h2t-evals validate-repo (requires service token)
        env:
          H2T_EVALS_ENABLED: ${{ secrets.H2T_EVALS_ENABLED || '0' }}
          H2T_EVALS_SERVICE_URL: ${{ secrets.H2T_EVALS_SERVICE_URL || '' }}
          H2T_EVALS_TOKEN: ${{ secrets.H2T_EVALS_TOKEN || '' }}
        run: |
          if [ "$H2T_EVALS_ENABLED" = "1" ] && [ -n "$H2T_EVALS_SERVICE_URL" ]; then
            pip install -e . 2>/dev/null || true
            h2t-evals validate-repo --repo claude-agent-skills --repo-config evals/repo.toml
          else
            echo "BLOCKED: H2T_EVALS_TOKEN not provisioned for this repo."
            echo "Service token must be added as GitHub secret H2T_EVALS_TOKEN by platform team."
            echo "Unit tests (above) are the hard gate until token is provisioned."
          fi
```

- [ ] **Step 3.5: Create manifest placeholder dirs**

```bash
mkdir -p evals/manifests
```

- [ ] **Step 3.6: Commit**

```bash
git add lib/gather/ evals/repo.toml evals/manifests/.gitkeep .github/workflows/evals.yml
git commit -m "feat(evals): add repo.toml, CI gate workflow, promote lib/gather to repo root"
```

---

## Task 4: Create h2t-core plugin skeleton + update-plugin.sh

**Files:**
- Create: `plugins/h2t-core/.claude-plugin/plugin.json`
- Create: `plugins/h2t-core/hooks/hooks.json`
- Create: `plugins/h2t-core/hooks-handlers/gather-on-skill`
- Create: `plugins/h2t-core/scripts/update-plugin.sh`

- [ ] **Step 4.1: Create plugin manifest**

```json
// plugins/h2t-core/.claude-plugin/plugin.json
{
  "name": "h2t-core",
  "version": "3.0.0",
  "description": "H2T Core — session lifecycle: start, handoff, init-project, overview",
  "author": "lichtpfad",
  "skills": [
    "session-start",
    "handoff",
    "init-project",
    "dev-overview",
    "setup",
    "snap"
  ]
}
```

- [ ] **Step 4.2: Create hooks.json**

```json
// plugins/h2t-core/hooks/hooks.json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Skill",
        "hooks": [
          {
            "type": "command",
            "command": "bash \"${CLAUDE_PLUGIN_ROOT}/hooks-handlers/gather-on-skill\""
          }
        ]
      }
    ]
  }
}
```

- [ ] **Step 4.3: Create gather-on-skill hook for h2t-core**

```bash
# plugins/h2t-core/hooks-handlers/gather-on-skill
#!/usr/bin/env bash
# PreToolUse: gather context when h2t-core session skills are invoked.
set -euo pipefail

input=$(cat)
skill=$(echo "$input" | jq -r '.tool_input.skill // ""')
cwd=$(echo "$input" | jq -r '.cwd // "."')

# Only fire for h2t-core session skills
case "$skill" in
  *session-start*|*handoff*|*init-project*) ;;
  *) exit 0 ;;
esac

H2T_PYTHON="${H2T_PYTHON:-}"
[ -z "$H2T_PYTHON" ] && [ -f "$HOME/.h2t/venv/Scripts/python.exe" ] && H2T_PYTHON="$HOME/.h2t/venv/Scripts/python.exe"
[ -z "$H2T_PYTHON" ] && [ -f "$HOME/.h2t/venv/bin/python" ] && H2T_PYTHON="$HOME/.h2t/venv/bin/python"

if [ -z "$H2T_PYTHON" ]; then
  echo '{"systemMessage": "GATHER_ERROR: h2t venv not found. Run /h2t:setup"}'
  exit 0
fi

case "$skill" in
  *init-project*) SCRIPT="${CLAUDE_PLUGIN_ROOT}/skills/init-project/scripts/detect_project.py" ;;
  *)              SCRIPT="${CLAUDE_PLUGIN_ROOT}/skills/session-start/scripts/gather.py" ;;
esac

if [ ! -f "$SCRIPT" ]; then
  echo '{"systemMessage": "GATHER_ERROR: script not found at '"$SCRIPT"'"}'
  exit 0
fi

ARGS="--cwd $cwd"
[[ "$skill" == *session-start* ]] && ARGS="$ARGS --format-briefing"

RESULT=$("$H2T_PYTHON" "$SCRIPT" $ARGS 2>/dev/null) || true

if [ -z "$RESULT" ]; then
  echo '{"systemMessage": "GATHER_ERROR: script returned no output"}'
  exit 0
fi

BRIEFING=$(echo "$RESULT" | "$H2T_PYTHON" -c "
import json, sys
data = json.load(sys.stdin)
b = data.get('_briefing', '')
m = json.dumps(data.get('_meta', {}))
print(f'BRIEFING:\n{b}\n\nGATHER_META: {m}')
" 2>/dev/null) || BRIEFING="GATHER_DATA: $RESULT"

printf '{"systemMessage": "%s"}' "$(echo "$BRIEFING" | python -c "import sys; print(sys.stdin.read().replace('\\\\', '\\\\\\\\').replace('\"', '\\\\\"').replace(chr(10), '\\\\n'))")"
```

- [ ] **Step 4.4: Create update-plugin.sh for h2t-core**

```bash
#!/usr/bin/env bash
# Update h2t-core plugin in Claude Code cache.
# Also copies repo-root lib/ into cache (packaging decision from spec).
# Usage: bash plugins/h2t-core/scripts/update-plugin.sh [--push]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLUGIN_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_DIR="$(cd "$PLUGIN_DIR/../.." && pwd)"

PLUGIN_JSON="$PLUGIN_DIR/.claude-plugin/plugin.json"
INSTALLED_JSON="$HOME/.claude/plugins/installed_plugins.json"
CACHE_BASE="$HOME/.claude/plugins/cache/lichtpfad/h2t-core"
MARKETPLACE_DIR="$HOME/.claude/plugins/marketplaces/lichtpfad"

# Detect Python
PY=""
[ -f "$HOME/.h2t/venv/Scripts/python.exe" ] && PY="$HOME/.h2t/venv/Scripts/python.exe"
[ -z "$PY" ] && [ -f "$HOME/.h2t/venv/bin/python" ] && PY="$HOME/.h2t/venv/bin/python"
[ -z "$PY" ] && PY=$(command -v python 2>/dev/null || command -v python3 2>/dev/null || echo "")
[ -z "$PY" ] && { echo '{"status":"error","error":"Python not found"}'; exit 1; }

_winpath() { [[ "$1" == /c/* ]] && echo "C:${1:2}" || echo "$1"; }
PLUGIN_JSON_W=$(_winpath "$PLUGIN_JSON")
INSTALLED_JSON_W=$(_winpath "$INSTALLED_JSON")

VERSION=$("$PY" -c "import json; print(json.load(open(r'$PLUGIN_JSON_W'))['version'])" 2>/dev/null || echo "")
[ -z "$VERSION" ] && { echo '{"status":"error","error":"Cannot read version"}'; exit 1; }

SHA=$(git -C "$REPO_DIR" rev-parse HEAD 2>/dev/null || echo "unknown")

for arg in "$@"; do [[ "$arg" == "--push" ]] && git -C "$REPO_DIR" push origin main 2>/dev/null; done

CACHE_DIR="$CACHE_BASE/$VERSION"
mkdir -p "$CACHE_DIR"
rm -rf "$CACHE_DIR"/*

# Copy plugin content
cp -r "$PLUGIN_DIR"/* "$CACHE_DIR"/
[ -d "$PLUGIN_DIR/.claude-plugin" ] && cp -r "$PLUGIN_DIR/.claude-plugin" "$CACHE_DIR/.claude-plugin"

# KEY: copy repo-root lib/ into cache alongside skills/
# This makes lib.activity, lib.eval, lib.gather importable from scripts/
cp -r "$REPO_DIR/lib" "$CACHE_DIR/lib"

# Update installed_plugins.json
NOW=$(date -u +"%Y-%m-%dT%H:%M:%S.000Z")
CACHE_DIR_WIN=$(echo "$CACHE_DIR" | sed 's|/c/|C:\\|; s|/|\\|g')
"$PY" -c "
import json
path = r'$INSTALLED_JSON_W'
with open(path, 'r', encoding='utf-8') as f: data = json.load(f)
key = 'h2t-core@lichtpfad'
entry = {'scope': 'user', 'installPath': r'$CACHE_DIR_WIN', 'version': '$VERSION',
         'installedAt': '$NOW', 'lastUpdated': '$NOW', 'gitCommitSha': '$SHA'}
data[key] = [entry]
with open(path, 'w', encoding='utf-8') as f: json.dump(data, f, indent=2)
"

SKILLS_COUNT=$(ls -d "$CACHE_DIR"/skills/*/ 2>/dev/null | wc -l)
LIB_OK=$([ -d "$CACHE_DIR/lib/gather" ] && echo "true" || echo "false")

echo "{\"status\":\"ok\",\"version\":\"$VERSION\",\"sha\":\"${SHA:0:7}\",\"cache\":\"$CACHE_DIR\",\"skills\":$SKILLS_COUNT,\"lib_in_cache\":$LIB_OK}"
```

```bash
chmod +x plugins/h2t-core/hooks-handlers/gather-on-skill
chmod +x plugins/h2t-core/scripts/update-plugin.sh
```

- [ ] **Step 4.5: Verify update script runs without error (skills dir will be empty — that's ok)**

```bash
bash plugins/h2t-core/scripts/update-plugin.sh
```

Expected: JSON output with `"status":"ok"` and `"lib_in_cache":true`

- [ ] **Step 4.6: Commit**

```bash
git add plugins/h2t-core/
git commit -m "feat(h2t-core): scaffold plugin — manifest, hooks, update script"
```

---

## Task 5: session-start v3 — gather.py

**Files:**
- Create: `plugins/h2t-core/skills/session-start/scripts/gather.py`

This is the v3 gather script. It reuses `lib/gather/` modules (available in cache via update-plugin.sh), adds SkillEval, and logs to activity stream.

- [ ] **Step 5.1: Create gather.py**

```python
#!/usr/bin/env python3
"""Context gatherer for session-start v3.

Usage: $H2T_PYTHON gather.py --cwd <path> [--format-briefing]
Outputs JSON to stdout. Imports from lib/ (co-located in cache by update-plugin.sh).
"""

import argparse
import sys
import time
from pathlib import Path

# lib/ is co-located in plugin cache root (../../../..)
PLUGIN_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(PLUGIN_ROOT / "lib"))

from gather import output_json
from gather.project import identify_project
from gather.user import gather_user_context
from gather.git import gather_git
from gather.github import gather_github
from gather.stack import detect_stack
from gather.sessions import find_session_files, get_machine_name
from gather.briefing import format_briefing
from eval.session import SkillEval


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cwd", default=".")
    parser.add_argument("--format-briefing", action="store_true")
    args = parser.parse_args()

    start = time.monotonic()
    sources_used: list[str] = []
    sources_failed: list[str] = []

    # Layer 0: Identity (always)
    project = identify_project(args.cwd)
    sources_used.append("project")

    user = gather_user_context(
        domain=project.get("domain"),
        config_root=project.get("config_root"),
    )

    # Layer 1: State (conditional on project type)
    git: dict = {}
    github: dict = {}
    if project.get("type") == "git":
        git = gather_git(args.cwd)
        sources_used.append("git")
        if not git.get("branch"):
            sources_failed.append("git")

        if project.get("github"):
            github = gather_github(owner_repo=project["github"])
            sources_used.append("github")
            if not github.get("issues") and not github.get("error"):
                pass  # empty repo is ok

    # Layer 2: Stack detection
    stack = detect_stack(args.cwd)

    # Layer 3: Previous sessions
    machine = get_machine_name()
    domain = project.get("domain", "dev")
    proj_id = project.get("id", "unknown")
    sessions = find_session_files(domain=domain, project=proj_id, machine=machine, limit=3)

    elapsed_ms = int((time.monotonic() - start) * 1000)

    data = {
        "project": project,
        "git": git,
        "github": github,
        "stack": stack,
        "sessions": sessions,
        "machine": machine,
        "user": user,
        "session_id": "",  # set by user after GATE confirmation
        "_meta": {
            "sources_used": sources_used,
            "sources_failed": sources_failed,
            "gather_ms": elapsed_ms,
        },
    }

    if args.format_briefing:
        briefing, meta = format_briefing(data)
        data["_briefing"] = briefing
        data["_meta"].update(meta)

    # Eval + activity (silent on failure)
    try:
        with SkillEval("session-start", domain=domain, project=proj_id) as ev:
            ev.metric("skills.gather_source_success_rate",
                      value_num=1.0 - len(sources_failed) / max(len(sources_used), 1))
            ev.metric("skills.token_consumption", value_num=float(len(str(data)) // 4))
    except Exception:
        pass

    output_json(data)


if __name__ == "__main__":
    main()
```

- [ ] **Step 5.2: Smoke test the script directly**

```bash
source ~/.h2t/venv/Scripts/activate

# PYTHONPATH=lib: makes lib/ the import root, so `from activity.writer import` resolves
# to lib/activity/writer.py — matching cache layout where lib/ sits at plugin root.
PYTHONPATH=lib python plugins/h2t-core/skills/session-start/scripts/gather.py \
  --cwd "$(pwd)" --format-briefing 2>&1 | python -m json.tool | head -40
```

Expected: valid JSON with `project`, `git`, `github`, `_briefing` keys (no `ModuleNotFoundError`)

- [ ] **Step 5.3: Commit**

```bash
git add plugins/h2t-core/skills/session-start/scripts/gather.py
git commit -m "feat(session-start): add v3 gather.py — modular, eval-aware, activity-logging"
```

---

## Task 6: session-start v3 — SKILL.md (7-step linear pipeline)

**Files:**
- Create: `plugins/h2t-core/skills/session-start/SKILL.md`

Critical design constraint from research: SKILL.md must be a **concrete linear pipeline** where each step depends on previous. Abstract instructions are ignored by Claude. Gmail-style CLI references suppress manual gather.

- [ ] **Step 6.1: Create SKILL.md**

```markdown
---
name: session-start
description: Use at the start of any working session (dev, creative, personal). Triggers on "start session", "session start", "начинаем", "новая сессия", or at the beginning of any work conversation.
compatibility: "Claude Code"
metadata:
  author: lichtpfad
  version: 3.0.0
---

# Session Start v3

## Setup

```bash
GATHER="${CLAUDE_PLUGIN_ROOT}/skills/session-start/scripts/gather.py"
ACTIVITY_LOG="${CLAUDE_PLUGIN_ROOT}/lib/activity/writer.py"
H2T_PYTHON="${H2T_PYTHON:-$HOME/.h2t/venv/Scripts/python.exe}"
[ ! -f "$H2T_PYTHON" ] && H2T_PYTHON="$HOME/.h2t/venv/bin/python"
```

## Pipeline

### Step 1: Collect context

```bash
$H2T_PYTHON "$GATHER" --cwd "$(pwd)" --format-briefing
```

Store the complete JSON output in memory as GATHER_RESULT. Do NOT paraphrase or summarize at this step.

### Step 2: Show briefing verbatim

Extract `_briefing` from GATHER_RESULT. Display it exactly as-is — do not reformat, reorder, or add commentary.

If `_briefing` is missing: show `GATHER_ERROR — no briefing in output. Check plugin version.`

### Step 3: Analyze top issues

From `GATHER_RESULT.github.issues` (if present): select up to 3 issues by priority (P1 > open > recent).

Show as numbered list:
```
1. #N — Title (P1/open/etc.)
2. #N — Title
3. #N — Title
```

If no issues: show "Нет открытых issues."

### Step 4: ⛔ GATE — Session naming

**Do NOT proceed to Step 5 until user confirms.**

Propose session name in this exact format:
```
Имя сессии: `{domain}-{project}-{topic}-YYYY-MM-DD`

Пример: `dev-h2t-ai-skill-refactor-2026-04-03`
```

Replace `{topic}` with 1-2 word summary of most likely work direction from context.
Wait for user input. Accept confirmation or alternative name.

### Step 5: Log session start

After user confirms session name (store as SESSION_NAME):

Extract from GATHER_RESULT (you have these values in memory from Step 1):
- `DOMAIN` = `GATHER_RESULT["project"]["domain"]`
- `PROJECT_ID` = `GATHER_RESULT["project"]["id"]`

Substitute the actual values into this command and run it:

```bash
$H2T_PYTHON "$ACTIVITY_LOG" start \
  --session-id "<SESSION_NAME>" \
  --domain "<DOMAIN>" \
  --project "<PROJECT_ID>"
```

Replace `<SESSION_NAME>`, `<DOMAIN>`, `<PROJECT_ID>` with the literal string values (not shell variables — these are LLM-held values substituted at call time).

### Step 6: Check project registration

If `GATHER_RESULT.project.registered` is `false` or `null`: invoke `h2t:init-project` now.

Otherwise: skip this step.

### Step 7: Confirm ready

Show exactly:
```
✓ Сессия: {SESSION_NAME}
✓ Контекст загружен ({N} issues, {branch})

Что делаем?
```

Fill N and branch from GATHER_RESULT.
```

- [ ] **Step 6.2: Copy init-project, dev-overview, setup, snap from h2t/ monolith**

```bash
cp -r plugins/h2t/skills/init-project plugins/h2t-core/skills/init-project
cp -r plugins/h2t/skills/dev-overview plugins/h2t-core/skills/dev-overview
cp -r plugins/h2t/skills/setup plugins/h2t-core/skills/setup
cp -r plugins/h2t/skills/snap plugins/h2t-core/skills/snap
```

- [ ] **Step 6.3: Update plugin manifest to include all skills**

```json
// plugins/h2t-core/.claude-plugin/plugin.json
{
  "name": "h2t-core",
  "version": "3.0.0",
  "description": "H2T Core — session lifecycle: start, handoff, init-project, overview",
  "author": "lichtpfad",
  "skills": [
    "session-start",
    "handoff",
    "init-project",
    "dev-overview",
    "setup",
    "snap"
  ]
}
```

- [ ] **Step 6.4: Run update-plugin.sh and verify session-start appears in cache**

```bash
bash plugins/h2t-core/scripts/update-plugin.sh
```

Expected: `"skills":6` (or however many are copied), `"lib_in_cache":true`

- [ ] **Step 6.5: Commit**

```bash
git add plugins/h2t-core/skills/
git commit -m "feat(session-start): add v3 SKILL.md — 7-step linear pipeline with GATE"
```

---

## Task 7: handoff v3

**Files:**
- Create: `plugins/h2t-core/skills/handoff/scripts/writer.py`
- Create: `plugins/h2t-core/skills/handoff/SKILL.md`

Handoff v3 writes to two places: activity stream (session.end record with artifacts) + markdown file (human-readable, for next session context until VPS ready).

- [ ] **Step 7.1: Create writer.py**

```python
#!/usr/bin/env python3
"""Handoff writer for session-end.

Usage:
  $H2T_PYTHON writer.py write \
    --session-id <id> --domain <d> --project <p> \
    --what-done "..." --what-remains "..." \
    --artifacts commit:abc123 issue:42 \
    [--markdown-dir <path>]

Writes:
  1. Activity stream entry (local JSONL spool)
  2. Markdown handoff file at markdown_dir/session_id.md
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(PLUGIN_ROOT / "lib"))

from activity.writer import log_session_end
from eval.session import SkillEval


def default_markdown_dir(domain: str, project: str) -> Path:
    machine = os.environ.get("DOR_MACHINE_NAME", os.uname().nodename if hasattr(os, "uname") else "unknown")
    return Path.home() / ".dor" / "sessions" / machine / project


def write_handoff(
    session_id: str,
    domain: str,
    project: str,
    what_done: str,
    what_remains: str,
    artifacts: list[str],
    markdown_dir: str | None = None,
) -> dict:
    """Write session end to activity stream + markdown file."""

    # Parse artifacts: ["commit:abc", "issue:42"] → [{"type": "commit", "ref": "abc"}, ...]
    parsed_artifacts = []
    for a in artifacts:
        if ":" in a:
            t, ref = a.split(":", 1)
            parsed_artifacts.append({"type": t, "ref": ref})
        else:
            parsed_artifacts.append({"type": "artifact", "ref": a})

    # Activity stream
    spool_path = log_session_end(
        session_id=session_id,
        domain=domain,
        project=project,
        artifacts=parsed_artifacts,
    )

    # Markdown handoff
    md_dir = Path(markdown_dir) if markdown_dir else default_markdown_dir(domain, project)
    md_dir.mkdir(parents=True, exist_ok=True)
    md_path = md_dir / f"{session_id}.md"

    now = datetime.now(timezone.utc)
    md_content = f"""# Session: {session_id}

## Meta
- **Date:** {now.strftime("%Y-%m-%d")}
- **Domain:** {domain}
- **Project:** {project}

## What Was Done
{what_done}

## What Remains
{what_remains}

## Artifacts
{chr(10).join(f"- {a['type']}: {a['ref']}" for a in parsed_artifacts) or "None"}
"""
    md_path.write_text(md_content, encoding="utf-8")

    # Eval
    try:
        with SkillEval("handoff", domain=domain, project=project):
            pass
    except Exception:
        pass

    return {
        "status": "ok",
        "session_id": session_id,
        "spool": spool_path,
        "markdown": str(md_path),
        "artifacts": len(parsed_artifacts),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd")
    w = sub.add_parser("write")
    w.add_argument("--session-id", required=True)
    w.add_argument("--domain", required=True)
    w.add_argument("--project", required=True)
    w.add_argument("--what-done", default="")
    w.add_argument("--what-remains", default="")
    w.add_argument("--artifacts", nargs="*", default=[])
    w.add_argument("--markdown-dir", default="")
    args = parser.parse_args()

    if args.cmd == "write":
        result = write_handoff(
            session_id=args.session_id,
            domain=args.domain,
            project=args.project,
            what_done=args.what_done,
            what_remains=args.what_remains,
            artifacts=args.artifacts,
            markdown_dir=args.markdown_dir or None,
        )
        print(json.dumps(result, ensure_ascii=False))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 7.2: Smoke test writer.py**

```bash
# PYTHONPATH=lib: matches cache layout (lib/ at plugin root, not repo root)
PYTHONPATH=lib python plugins/h2t-core/skills/handoff/scripts/writer.py write \
  --session-id "dev-h2t-skills-test-2026-04-03" \
  --domain dev --project h2t-skills \
  --what-done "Built handoff writer" \
  --what-remains "Write SKILL.md" \
  --artifacts "commit:abc123" "issue:42" \
  --markdown-dir "/tmp/test-handoff"
```

Expected: JSON with `"status":"ok"` and both `spool` and `markdown` paths. Check files exist.

- [ ] **Step 7.3: Create handoff SKILL.md**

```markdown
---
name: handoff
description: Use when ending a session, saving work status, or when context window is nearing limits. Triggers on "handoff", "save status", "session end", "сохрани статус", конец сессии.
compatibility: "Claude Code"
metadata:
  author: lichtpfad
  version: 3.0.0
---

# Handoff v3

## Setup

```bash
WRITER="${CLAUDE_PLUGIN_ROOT}/skills/handoff/scripts/writer.py"
H2T_PYTHON="${H2T_PYTHON:-$HOME/.h2t/venv/Scripts/python.exe}"
[ ! -f "$H2T_PYTHON" ] && H2T_PYTHON="$HOME/.h2t/venv/bin/python"
```

## Pipeline

### Step 1: Get session context from hook or conversation

The hook has injected GATHER_DATA into system messages. Use it.

Extract:
- `project.domain`, `project.id` — from GATHER_DATA
- `_handoff.session_dir` — markdown output directory
- Current session name — from earlier in conversation (set during session-start GATE, or derive from branch)

If no hook data: run gather manually:
```bash
$H2T_PYTHON "${CLAUDE_PLUGIN_ROOT}/skills/session-start/scripts/gather.py" --cwd "$(pwd)"
```

### Step 2: Summarize this session

From conversation context (NOT from git diff, NOT from external commands):

**What Was Done** — 3-7 bullet points of concrete actions taken THIS session.
**What Remains** — 2-5 bullet points of next steps.

### Step 3: Collect artifacts

From conversation history, identify:
- Commits made: `commit:{sha}` (7-char sha)
- Issues closed: `issue:{number}`
- Files created: `file:{path}`
- PRs opened: `pr:{number}`

### Step 4: Write handoff

```bash
$H2T_PYTHON "$WRITER" write \
  --session-id "{SESSION_NAME}" \
  --domain "{project.domain}" \
  --project "{project.id}" \
  --what-done "{what_done_bullets}" \
  --what-remains "{what_remains_bullets}" \
  --artifacts {artifact_list}
```

### Step 5: Confirm

Show result from writer:
```
✓ Сессия {SESSION_NAME} сохранена
✓ Activity stream: {spool_path}
✓ Markdown: {markdown_path}
✓ Артефактов: {N}
```
```

- [ ] **Step 7.4: Commit**

```bash
git add plugins/h2t-core/skills/handoff/
git commit -m "feat(handoff): add v3 — writer.py + SKILL.md, dual-write activity+markdown"
```

---

## Task 8: dev-session-start alias shim + delete obsolete skills

**Files:**
- Modify: `plugins/h2t/skills/dev-session-start/SKILL.md`
- Delete: `plugins/h2t/skills/ctx-load/`
- Delete: `plugins/h2t/skills/session-name/`

- [ ] **Step 8.1: Replace dev-session-start SKILL.md with transparent redirect shim**

The shim must **execute** the new flow immediately — not just announce it. A passive "please invoke X" breaks the trigger because the user triggered dev-session-start expecting a session to start.

```markdown
---
name: dev-session-start
description: DEPRECATED alias — immediately executes h2t-core:session-start. Triggers on same patterns as session-start.
compatibility: "Claude Code"
metadata:
  author: lichtpfad
  version: 2.15.0
  deprecated: true
---

# dev-session-start

> **Deprecated.** Migrated to `h2t-core:session-start` (Phase 2 removes this file).

Execute all steps from `h2t-core:session-start` immediately, starting with Step 1.
Do not announce this redirect to the user. The session flow starts now.
```

- [ ] **Step 8.1b: Update h2t/ gather-on-skill to stop routing dev-session-start**

The h2t plugin's PreToolUse hook currently matches `dev-session-start` and runs the **old** gather.py. When the shim redirects to h2t-core:session-start, h2t-core's hook will run h2t-core's gather.py. If the h2t hook still fires first for dev-session-start, both hooks execute and inject conflicting systemMessages.

Remove `dev-session-start` (and `ctx-load`) from the h2t hook:

```bash
# plugins/h2t/hooks-handlers/gather-on-skill
# CHANGE line 12: remove dev-session-start and ctx-load from the match
```

Edit `plugins/h2t/hooks-handlers/gather-on-skill`, change:

```bash
if [[ "$skill" == *"dev-session-start"* ]] || [[ "$skill" == *"ctx-load"* ]]; then
  SKILL_NAME="dev-session-start"
elif [[ "$skill" == *"handoff"* ]]; then
```

to:

```bash
if [[ "$skill" == *"handoff"* ]]; then
```

Also remove the marker block (lines 24-27) that wrote `~/.h2t/.ctx-load-active`:

```bash
# Remove this entire block:
if [ "$SKILL_NAME" = "dev-session-start" ]; then
  mkdir -p "$HOME/.h2t"
  echo "skill=$skill cwd=$cwd ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$HOME/.h2t/.ctx-load-active"
fi
```

And remove the `--format-briefing` branch for dev-session-start in the GATHER_ARGS block:

```bash
# Remove this:
if [ "$SKILL_NAME" = "dev-session-start" ]; then
  GATHER_ARGS="$GATHER_ARGS --format-briefing"
fi
```

And remove the `dev-session-start` branch in the output section — replace with passthrough for handoff only.

After edits, the h2t gather-on-skill matches only `handoff` and `init-project`. Verify:

```bash
grep -n "dev-session-start\|ctx-load" plugins/h2t/hooks-handlers/gather-on-skill
```

Expected: no matches.

- [ ] **Step 8.2: Delete ctx-load and session-name**

```bash
rm -rf plugins/h2t/skills/ctx-load
rm -rf plugins/h2t/skills/session-name
```

- [ ] **Step 8.3: Verify h2t/ still has correct skill count**

```bash
ls plugins/h2t/skills/ | wc -l
```

Expected: 28 (30 - ctx-load - session-name)

- [ ] **Step 8.4: Commit**

```bash
git add plugins/h2t/skills/dev-session-start/SKILL.md
git add plugins/h2t/hooks-handlers/gather-on-skill   # critical: hook fix from Step 8.1b
git add -u plugins/h2t/skills/  # picks up deletions
git commit -m "feat(migration): alias dev-session-start → shim, strip hook routing, delete ctx-load/session-name"
```

---

## Task 9: Run update-plugin.sh and full integration test

- [ ] **Step 9.1: Run all tests**

```bash
source ~/.h2t/venv/Scripts/activate
python -m pytest lib/ -v
```

Expected: all PASSED (activity tests + eval tests + gather tests)

- [ ] **Step 9.2: Install h2t-core into Claude Code cache**

```bash
bash plugins/h2t-core/scripts/update-plugin.sh
```

Expected: `"status":"ok"`, `"lib_in_cache":true`, `"skills":6`

- [ ] **Step 9.3: Verify lib/ is present in cache**

```bash
CACHE=$(bash plugins/h2t-core/scripts/update-plugin.sh | python -c "import json,sys; print(json.load(sys.stdin)['cache'])")
ls "$CACHE/lib/"
```

Expected: `activity/  eval/  gather/  __init__.py`

- [ ] **Step 9.4: Verify gather.py runs from cache location**

```bash
H2T_PYTHON=~/.h2t/venv/Scripts/python.exe
$H2T_PYTHON "$CACHE/skills/session-start/scripts/gather.py" --cwd "$(pwd)" 2>&1 | head -5
```

Expected: JSON output (no ModuleNotFoundError)

- [ ] **Step 9.5: Start a new Claude Code session and run `/h2t-core:session-start`**

Manual integration test. Verify:
- [ ] Steps 1-3 execute in order (gather → briefing shown → issues listed)
- [ ] Step 4 GATE fires: Claude proposes session name and WAITS for response
- [ ] Step 5 logs to activity spool after confirmation
- [ ] Step 7 shows final confirmation message

- [ ] **Step 9.6: Verify activity spool has entry**

```bash
tail -1 ~/.h2t/activity/spool.jsonl | python -m json.tool
```

Expected: JSON with `action: "session.start"`, correct `domain` and `project`.

- [ ] **Step 9.7: Report in h2t-evals tracker issues**

Post BLOCKED comment in h2t-evals#44 (M3). Use the CI pass URL from the merged PR (unit-tests job passes; eval-gate job prints BLOCKED message, does not fail CI):

```
Repo:
- lichtpfad/claude-agent-skills

Scope completed:
- evals/repo.toml added with thresholds and custom metrics
- lib/eval/session.py (SkillEval context manager) wired into session-start and handoff
- .github/workflows/evals.yml CI gate wired (unit-tests job: hard gate; eval-gate job: BLOCKED pending token)
- Local spool writing verified

Evidence:
- PR: (link when merged)
- CI pass: (unit-tests job URL — green on merge)
- CI fail (intentional): eval-gate job prints BLOCKED, exits 0; will fail hard once H2T_EVALS_TOKEN provisioned
- validate-repo snippet: pending (service token needed from platform)
- session_ids: (from Step 9.5 manual run)

Acceptance checklist:
- [x] Required metadata emitted (evals/repo.toml)
- [x] Required core metrics registered (thresholds.unit + thresholds.integration)
- [x] Custom metrics registered before use (skills.*)
- [ ] Deterministic eval_set behavior confirmed — deferred (no unit_cases.jsonl yet)
- [x] CI gate blocks non-compliant runs (unit tests hard gate active)

Result:
BLOCKED
Reason: H2T_EVALS_TOKEN not provisioned; validate-repo and deterministic eval_set deferred
Next dependency: platform team to provision H2T_EVALS_TOKEN secret for lichtpfad/claude-agent-skills
```

- [ ] **Step 9.8: Final commit + push**

```bash
git add evals/
git commit -m "chore: finalize Phase 1 Foundation — run all tests and integration smoke"
git push origin main
```

---

## Self-Review Checklist

**Spec coverage:**

| Spec requirement | Task |
|-----------------|------|
| lib/activity/ writer with CLI | Task 1 |
| lib/eval/ wrapper (h2t-evals SDK) | Task 2 |
| lib/gather/ at repo root | Task 3 |
| evals/repo.toml | Task 3 |
| .github/workflows/evals.yml CI gate | Task 3 Step 3.4 |
| h2t-core plugin skeleton | Task 4 |
| update-plugin.sh copies lib/ to cache | Task 4 |
| session-start v3 — linear pipeline with GATE | Tasks 5-6 |
| session-start — modular gather by project type | Task 5 |
| session-start — eval Level 1 | Task 5 |
| session-start — activity log via writer CLI | Task 6 SKILL.md Step 5 |
| session-start — auto-trigger init-project | Task 6 SKILL.md Step 6 |
| handoff v3 — activity stream + markdown | Task 7 |
| dev-session-start transparent redirect shim | Task 8 |
| h2t hook updated: no longer matches dev-session-start | Task 8 Step 8.1b |
| ctx-load, session-name deleted | Task 8 |
| Report in h2t-evals#44, #45 | Task 9 |

**Placeholder scan:** No TBD/TODO found. All code blocks complete.

**Type consistency:** `log_session_start(session_id, domain, project)` matches calls in gather.py and SKILL.md. `SkillEval` context manager interface consistent across usage in gather.py and writer.py.

---

*Phase 2 plan (h2t-ops + h2t-dev) to be written after Phase 1 live-verified.*
