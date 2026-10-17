"""scripts/release_guard.py: may this tag move the pointer (spec §7.1)?

One script answers for both callers in release.yml: the `build` preflight, before anything
is published, and the `pointer` job, which re-asks because main can move between jobs.
Each case is a real git repository with an `origin` whose main carries marketplace.json.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
GUARD = ROOT / "scripts" / "release_guard.py"
URL = "https://github.com/lichtpfad/h2t-skills.git"

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="needs git")


def _git(cwd: Path, *args: str) -> str:
    r = subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "init.defaultBranch=main",
                        *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


def _market(ref: str, sha: str) -> str:
    plugins = [{"name": n, "version": "1.0.0", "source": {"source": "git-subdir", "url": URL,
                "path": f"plugins/{n}", "ref": ref, "sha": sha}} for n in ("h2t-core", "h2t-ops")]
    return json.dumps({"name": "lichtpfad", "plugins": plugins}, indent=2) + "\n"


def _commit(repo: Path, message: str, *, previous: str | None = None, pointer: tuple[str, str] | None = None) -> str:
    if previous is not None:
        (repo / "release.json").write_text(json.dumps({"version": "x", "previous": previous}), encoding="utf-8")
    if pointer is not None:
        (repo / ".claude-plugin").mkdir(exist_ok=True)
        (repo / ".claude-plugin" / "marketplace.json").write_text(_market(*pointer), encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "--allow-empty", "-m", message)
    return _git(repo, "rev-parse", "HEAD")


@pytest.fixture
def repo(tmp_path) -> Path:
    """origin/main: the freeze at v3.3.0, then the 4.0.0 release commit tagged v4.0.0."""
    work = tmp_path / "work"
    work.mkdir()
    _git(work, "init", "-q")
    freeze = _commit(work, "freeze", pointer=("v3.3.0", "a" * 40))
    _git(work, "tag", "v3.3.0", freeze)
    release = _commit(work, "release 4.0.0", previous="3.3.0")
    _git(work, "tag", "v4.0.0", release)
    _git(tmp_path, "clone", "-q", "--bare", str(work), "origin.git")
    _git(work, "remote", "add", "origin", str(tmp_path / "origin.git"))
    _git(work, "fetch", "-q", "origin")
    return work


def _guard(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(GUARD), *args], cwd=repo, capture_output=True,
                          text=True, encoding="utf-8")


def _push_main(repo: Path) -> None:
    _git(repo, "push", "-q", "origin", "HEAD:main")
    _git(repo, "fetch", "-q", "origin")


def test_a_tag_on_main_after_previous_may_move(repo):
    r = _guard(repo, "v4.0.0")
    assert (r.returncode, r.stdout.strip()) == (0, "move"), r.stderr


def test_a_tag_off_main_is_refused(repo):
    _git(repo, "checkout", "-q", "-b", "side")
    _git(repo, "tag", "v4.0.1", _commit(repo, "side", previous="4.0.0"))
    r = _guard(repo, "v4.0.1")
    assert r.returncode == 1
    assert "not reachable from origin/main" in r.stderr


def test_a_pointer_elsewhere_than_previous_is_refused(repo):
    _commit(repo, "pointer moved by hand", pointer=("v3.2.0", "b" * 40))
    _push_main(repo)
    r = _guard(repo, "v4.0.0")
    assert r.returncode == 1
    assert "pointer is at v3.2.0" in r.stderr and "previous = 3.3.0" in r.stderr


def test_a_pointer_already_at_this_tag_is_done_only_when_allowed(repo):
    sha = _git(repo, "rev-parse", "v4.0.0^{commit}")
    _commit(repo, "chore(release): pointer → v4.0.0", pointer=("v4.0.0", sha))
    _push_main(repo)
    rerun = _guard(repo, "v4.0.0", "--allow-done")
    assert (rerun.returncode, rerun.stdout.strip()) == (0, "done"), rerun.stderr
    assert "already at v4.0.0" in rerun.stderr
    fresh = _guard(repo, "v4.0.0")
    assert fresh.returncode == 1, "a build of a finished release must not publish again"


def test_a_pointer_at_this_tag_with_another_sha_is_refused(repo):
    _commit(repo, "pointer at the right tag, wrong commit", pointer=("v4.0.0", "c" * 40))
    _push_main(repo)
    r = _guard(repo, "v4.0.0", "--allow-done")
    assert r.returncode == 1
