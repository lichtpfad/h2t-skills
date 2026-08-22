"""A handoff must be readable by the session-start that follows it (#377).

The writer keys the session directory by `project.id` (`writer.py:49`), the reader keyed
it by the tail of the github remote (`gather.py:100`). For the 20 of 38 entries in
repo-mapping.yaml where the two differ, every handoff landed in a directory session-start
never looked in — silently, because `latest.json` still existed under the repo name and
the briefing merely showed an older session.

project.id is the primary key, not merely an alternative: several repositories map onto
one project on purpose (DocGraph and SpecDesigner -> docgraph), and only project.id keeps
their history together. The repo name is read as well, for handoffs written before a
project was mapped.
"""

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
WRITER = ROOT / "plugins" / "h2t-core" / "skills" / "handoff" / "scripts" / "writer.py"
LIB_COPIES = {
    "root": ROOT / "lib" / "gather" / "sessions.py",
    "vendored": ROOT / "plugins" / "h2t-core" / "lib" / "gather" / "sessions.py",
}


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(params=sorted(LIB_COPIES), ids=sorted(LIB_COPIES))
def sessions(request, monkeypatch):
    """Both copies must agree; the vendored one is what the hook actually runs."""
    return _load(LIB_COPIES[request.param], f"sessions_{request.param}")


def _write_handoff(root: Path, project: str, session_id: str) -> None:
    env = dict(os.environ)
    env["H2T_SESSION_ROOT"] = str(root)
    env["H2T_MACHINE_NAME"] = "test-machine"
    env["H2T_EVALS_MODE"] = "off"
    result = subprocess.run(
        [
            sys.executable, str(WRITER), "write",
            "--session-id", session_id,
            "--domain", "personal-os",
            "--project", project,
            "--what-done", "did the thing",
            "--what-remains", "- [ ] the next thing",
        ],
        capture_output=True, text=True, env=env, cwd=ROOT,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["status"] == "ok"


def test_handoff_is_found_by_the_repo_name_of_the_next_session(tmp_path, monkeypatch, sessions):
    """h2t-skills -> agent-skills: write under project.id, read from the repo directory."""
    root = tmp_path / "sessions"
    _write_handoff(root, "agent-skills", "personal-os-h2t-skills-topic-2026-08-22")
    monkeypatch.setenv("H2T_SESSION_ROOT", str(root))

    latest = sessions.find_latest_session_index("h2t-skills", "agent-skills")

    assert latest is not None, "the handoff just written is invisible to the next session"
    assert latest["session_id"] == "personal-os-h2t-skills-topic-2026-08-22"


def test_two_repos_of_one_project_share_history(tmp_path, monkeypatch, sessions):
    """DocGraph and SpecDesigner map onto docgraph; a session in one sees the other."""
    root = tmp_path / "sessions"
    _write_handoff(root, "docgraph", "dev-docgraph-topic-2026-08-22")
    monkeypatch.setenv("H2T_SESSION_ROOT", str(root))

    latest = sessions.find_latest_session_index("SpecDesigner", "docgraph")

    assert latest is not None
    assert latest["session_id"] == "dev-docgraph-topic-2026-08-22"


def test_markdown_listing_spans_both_keys(tmp_path, monkeypatch, sessions):
    """find_session_files backs the handoff count; it must not miss the project dir."""
    root = tmp_path / "sessions"
    _write_handoff(root, "agent-skills", "personal-os-h2t-skills-new-2026-08-22")
    legacy = root / "test-machine" / "h2t-skills"
    legacy.mkdir(parents=True, exist_ok=True)
    (legacy / "personal-os-h2t-skills-old-2026-08-20.md").write_text("older", encoding="utf-8")
    monkeypatch.setenv("H2T_SESSION_ROOT", str(root))

    files = sessions.find_session_files("h2t-skills", "agent-skills")

    names = {Path(f).name for f in files}
    assert "personal-os-h2t-skills-new-2026-08-22.md" in names, "project.id directory missed"
    assert "personal-os-h2t-skills-old-2026-08-20.md" in names, "legacy repo directory missed"


def test_a_single_name_still_works(tmp_path, monkeypatch, sessions):
    """Callers passing one key (the pre-#377 signature) must keep working."""
    root = tmp_path / "sessions"
    _write_handoff(root, "dor-core", "personal-os-dor-core-topic-2026-08-22")
    monkeypatch.setenv("H2T_SESSION_ROOT", str(root))

    assert sessions.find_latest_session_index("dor-core") is not None
    assert sessions.find_latest_session_index("unrelated-repo") is None


def test_the_gather_entrypoint_passes_both_keys():
    """The fix is only real if gather.py hands the reader both identities."""
    source = (
        ROOT / "plugins" / "h2t-core" / "skills" / "session-start" / "scripts" / "gather.py"
    ).read_text(encoding="utf-8")
    assert "find_latest_session_index(proj_id, repo_name)" in source
    assert "find_session_files(proj_id, repo_name)" in source
