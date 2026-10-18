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

from h2t_ops.core import paths
from h2t_ops.lifecycle import session_record

ROOT = Path(__file__).resolve().parents[2]
WRITER = "h2t_ops.lifecycle.handoff"
# One copy since Task 12; the plugin's vendored lib, which the hook used to run, is gone.
LIB_COPIES = {
    "root": ROOT / "h2t_ops" / "lifecycle" / "gather" / "sessions.py",
}


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(params=sorted(LIB_COPIES), ids=sorted(LIB_COPIES))
def sessions(request, monkeypatch):
    """Loaded from the file, fresh per test, as the copies were while there were two."""
    return _load(LIB_COPIES[request.param], f"sessions_{request.param}")


def _write_handoff(project: str, session_id: str) -> None:
    env = dict(os.environ)
    env["H2T_MACHINE_NAME"] = "test-machine"
    env["H2T_EVALS_MODE"] = "off"
    result = subprocess.run(
        [
            sys.executable, "-m", WRITER, "write",
            "--session-id", session_id,
            "--domain", "personal-os",
            "--project", project,
            "--what-done", "did the thing",
            "--what-remains", "- [ ] the next thing",
        ],
        capture_output=True, text=True, encoding="utf-8", env=env, cwd=ROOT,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["status"] == "ok"


def test_handoff_is_found_by_the_repo_name_of_the_next_session(tmp_path, monkeypatch, sessions):
    """h2t-skills -> agent-skills: write under project.id, read from the repo directory."""
    _write_handoff("agent-skills", "personal-os-h2t-skills-topic-2026-08-22")

    latest = sessions.find_latest_session_index("h2t-skills", "agent-skills")

    assert latest is not None, "the handoff just written is invisible to the next session"
    assert latest["session_id"] == "personal-os-h2t-skills-topic-2026-08-22"


def test_two_repos_of_one_project_share_history(tmp_path, monkeypatch, sessions):
    """DocGraph and SpecDesigner map onto docgraph; a session in one sees the other."""
    _write_handoff("docgraph", "dev-docgraph-topic-2026-08-22")

    latest = sessions.find_latest_session_index("SpecDesigner", "docgraph")

    assert latest is not None
    assert latest["session_id"] == "dev-docgraph-topic-2026-08-22"


def test_markdown_listing_spans_both_keys(tmp_path, monkeypatch, sessions):
    """find_session_files backs the handoff count; it must not miss the project dir."""
    root = paths.records("sessions")
    _write_handoff("agent-skills", "personal-os-h2t-skills-new-2026-08-22")
    legacy = root / "test-machine" / "h2t-skills"
    legacy.mkdir(parents=True, exist_ok=True)
    # Recorded under the repo name before the project was mapped; the index reads frontmatter.
    (legacy / "personal-os-h2t-skills-old-2026-08-20.md").write_bytes(session_record.render(
        {"session_id": "personal-os-h2t-skills-old-2026-08-20", "machine": "test-machine",
         "project": "h2t-skills", "updated_at": "2026-08-20T10:00:00Z"}, b"older\n"))

    files = sessions.find_session_files("h2t-skills", "agent-skills")

    names = {Path(f).name for f in files}
    assert "personal-os-h2t-skills-new-2026-08-22.md" in names, "project.id directory missed"
    assert "personal-os-h2t-skills-old-2026-08-20.md" in names, "legacy repo directory missed"


def test_a_single_name_still_works(tmp_path, monkeypatch, sessions):
    """Callers passing one key (the pre-#377 signature) must keep working."""
    _write_handoff("dor-core", "personal-os-dor-core-topic-2026-08-22")

    assert sessions.find_latest_session_index("dor-core") is not None
    assert sessions.find_latest_session_index("unrelated-repo") is None


def test_the_gather_entrypoint_passes_both_keys():
    """The fix is only real if gather.py hands the reader both identities."""
    source = (ROOT / "h2t_ops" / "lifecycle" / "session_start.py").read_text(encoding="utf-8")
    assert "find_latest_session_index(proj_id, repo_name)" in source
    assert "find_session_files(proj_id, repo_name)" in source
