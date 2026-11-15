"""The release workflow, read as data (spec §7.1).

The order is the contract: the wheel is built, tested installed, published, and only then
does the pointer move — and it moves only from `previous`. A workflow that gets the order
wrong still runs green on the day it is written, so the order is asserted here.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "release.yml"
JOBS = ["build", "test-installed", "release", "pointer"]


@pytest.fixture(scope="module")
def wf() -> dict:
    assert WORKFLOW.is_file(), f"{WORKFLOW.relative_to(ROOT)} does not exist"
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def _on(wf: dict) -> dict:
    # PyYAML reads the bare key `on` as the boolean True (YAML 1.1).
    return wf.get("on", wf.get(True))


def _runs(job: dict) -> list[str]:
    return [step.get("run", "") for step in job["steps"]]


def _script(job: dict) -> str:
    return "\n".join(_runs(job))


def test_triggers_on_version_tags_only(wf):
    assert _on(wf) == {"push": {"tags": ["v*"]}}


def test_releases_never_run_in_parallel(wf):
    assert wf["concurrency"] == {"group": "release", "cancel-in-progress": False}


def test_write_permission_only_where_it_is_used(wf):
    assert wf["permissions"] == {"contents": "read"}
    expected = {"build": {"contents": "read", "checks": "read"},  # the CI gate (#583)
                "release": {"contents": "write"}, "pointer": {"contents": "write"}}
    for name in JOBS:
        assert wf["jobs"][name].get("permissions") == expected.get(name), name


def test_jobs_form_one_chain_in_release_order(wf):
    assert list(wf["jobs"]) == JOBS
    for before, after in zip(JOBS, JOBS[1:]):
        assert wf["jobs"][after]["needs"] == before, after


def test_installed_wheel_runs_the_wheel_and_setup_tests(wf):
    script = _script(wf["jobs"]["test-installed"])
    for path in ("tests/tools/test_resources_from_wheel.py", "tests/setup",
                 "tests/release/test_determinism.py"):
        assert path in script, path
    assert wf["env"]["PYTHON"] == "3.12.11"
    assert re.search(r'--python "\$PYTHON" --managed-python', script), "not the release Python"
    assert re.search(r"-c\s+\S*constraints\.txt", script), "the install is not constrained"
    assert "'$VER'" not in script, "the version is spliced into Python source; pass it as argv"


def test_release_publishes_the_wheel_and_the_constraints(wf):
    create = [r for r in _runs(wf["jobs"]["release"]) if "gh release create" in r]
    assert len(create) == 1
    assert ".whl" in create[0] and "constraints.txt" in create[0]
    assert "--notes-file" in create[0]


def _order(script: str, *needles: str) -> list[int]:
    found = [script.find(n) for n in needles]
    assert -1 not in found, dict(zip(needles, found))
    return found


def test_the_guard_runs_before_anything_is_published(wf):
    """A bad tag must fail in build, not leave an orphan public Release behind it.

    scripts/release_guard.py holds the reachability and `previous` checks for both jobs,
    so the preflight and the re-check cannot drift apart."""
    build = _script(wf["jobs"]["build"])
    guard, upload = _order(build, 'release_guard.py "v$VER"', "uv build")
    assert guard < upload
    assert "--allow-done" not in build, "a build of a finished release must not publish again"
    checkout = wf["jobs"]["build"]["steps"][0]
    assert checkout.get("with", {}).get("fetch-depth") == 0, "the guard needs origin/main"


def test_pointer_rechecks_moves_and_verifies_before_it_pushes(wf):
    script = _script(wf["jobs"]["pointer"])
    guard, done, view, move, verify, labels, commit, push = _order(
        script, 'release_guard.py "v$VER" --allow-done', "already at v$VER", "gh release view",
        "release_pointer.py set", "release_pointer.py check", "check_marketplace_sync.py",
        "git commit", "git push")
    assert guard < done < view < move < verify < labels < commit < push
    assert "exit 0" in script[done:view], "a re-run after the push must be a no-op"
    assert "exit 1" in script[view:move], "the pointer could name a tag with no Release"
    assert "exit 1" in script[verify:labels], "the moved pointer is committed unchecked"
    assert "exit 1" in script[labels:commit], "the moved labels are committed unchecked"


def test_every_action_is_pinned(wf):
    uses = [step["uses"] for job in wf["jobs"].values() for step in job["steps"] if "uses" in step]
    assert uses
    loose = [u for u in uses if not re.fullmatch(r"[\w.-]+/[\w.-]+@v\d+(\.\d+)*", u)]
    assert not loose, loose


def test_setup_uv_pins_the_uv_version(wf):
    pins = [step.get("with", {}).get("version") for job in wf["jobs"].values()
            for step in job["steps"] if step.get("uses", "").startswith("astral-sh/setup-uv@")]
    assert pins and all(re.fullmatch(r"\d+\.\d+\.\d+", str(p)) for p in pins), pins


def test_the_workflow_never_prepares_a_release(wf):
    """prepare runs on the release commit before the tag; the tag is what CI checks."""
    steps = "\n".join(_script(job) for job in wf["jobs"].values())
    assert "release.py prepare" not in steps
    assert "release.py" in steps, "the guard reads nothing: no step names release.py at all"
    assert "release.json" in _script(wf["jobs"]["build"])


# --- release gates (#583) -------------------------------------------------------------------

def test_green_ci_on_the_tagged_commit_gates_the_build(wf):
    build = _script(wf["jobs"]["build"])
    guard, gate, upload = _order(build, 'release_guard.py "v$VER"',
                                 'release_ci_gate.py "$GITHUB_SHA"', "uv build")
    assert guard < gate < upload, "a tag on a red commit must publish nothing"
    step = next(s for s in wf["jobs"]["build"]["steps"] if "release_ci_gate.py" in s.get("run", ""))
    assert step.get("env", {}).get("GH_TOKEN"), "gh api needs a token"


def test_the_installed_wheel_runs_in_an_empty_home_and_meets_the_contract(wf):
    script = _script(wf["jobs"]["test-installed"])
    assert 'release_empty_home.py "$RUNNER_TEMP/venv/bin/h2t-ops"' in script
    move, contract = _order(script, 'mv h2t_ops "$RUNNER_TEMP/h2t_ops-source"', "tests/contracts")
    assert move < contract, "the contract must be checked against the wheel, not the checkout"


def test_the_notes_record_tag_commit_and_wheel_digest(wf):
    script = _script(wf["jobs"]["release"])
    notes, create = _order(script, ">> \"$RUNNER_TEMP/notes.md\"", "gh release create")
    assert notes < create
    for needle in ("tag: `v%s`", "commit: `%s`", "wheel sha256: `%s`", "sha256sum", "git rev-parse HEAD"):
        assert needle in script, needle
