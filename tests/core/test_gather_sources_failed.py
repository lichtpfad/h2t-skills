"""A dead GitHub source must reach GATHER_META, not vanish into an empty list.

On 2026-08-22 two consecutive `h2t-gather` runs disagreed: the first timed out on
every gh call (gather_ms 15110 == the 15s cap in runner._run_one) and printed
"Нет открытых issues" with `sources_failed: []`; the second listed 20 issues and
3 PRs.

There used to be two orchestrations to keep in step; the lib/cli/main.py twin was deleted
in #392 after it was measured producing a briefing without its `### Previous Session`
block. One implementation remains — the plugin script, which is what both `h2t-gather`
and `h2t-ops gather` now execute — so this file no longer parametrises over a second one.
"""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PLUGIN_SCRIPT = ROOT / "plugins" / "h2t-core" / "skills" / "session-start" / "scripts" / "gather.py"

FAILED_GITHUB = {
    "milestones": [], "current_milestone": None, "milestone_issues": [],
    "issues": [], "bugs": [], "prs": [], "failed": ["issues", "prs"],
}
HEALTHY_GITHUB = {**FAILED_GITHUB, "failed": []}


def _load_plugin_gather():
    """Import the plugin script the same way run_plugin_main does."""
    sys.path.insert(0, str(ROOT / "plugins" / "h2t-core" / "lib"))
    spec = importlib.util.spec_from_file_location("_plugin_gather", PLUGIN_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(params=["plugin"])
def gather_module(request):
    return _load_plugin_gather()


def _run(gather_module, monkeypatch, capfd, tmp_path, github_result):
    m = gather_module
    monkeypatch.setenv("H2T_EVALS_MODE", "local")
    monkeypatch.setattr(m, "identify_project", lambda cwd: {
        "id": "p", "domain": "d", "type": "git",
        "github": "o/r", "config_root": str(tmp_path),
    })
    monkeypatch.setattr(m, "gather_user_context", lambda **kw: {})
    monkeypatch.setattr(m, "gather_github", lambda owner_repo: github_result)
    monkeypatch.setattr(m, "find_session_files", lambda *a, **kw: [])
    if hasattr(m, "find_latest_session_index"):
        monkeypatch.setattr(m, "find_latest_session_index", lambda *a, **kw: None)

    if hasattr(m, "_run_gather"):
        m._run_gather("session-start", str(ROOT), False)
    else:
        monkeypatch.setattr(sys, "argv", ["gather.py", "--cwd", str(ROOT)])
        m.main()
    return json.loads(capfd.readouterr().out)


def test_failed_github_calls_land_in_sources_failed(gather_module, monkeypatch, capfd, tmp_path):
    data = _run(gather_module, monkeypatch, capfd, tmp_path, FAILED_GITHUB)
    assert data["_meta"]["sources_failed"] == ["github"]


def test_healthy_github_leaves_sources_failed_empty(gather_module, monkeypatch, capfd, tmp_path):
    data = _run(gather_module, monkeypatch, capfd, tmp_path, HEALTHY_GITHUB)
    assert data["_meta"]["sources_failed"] == []
