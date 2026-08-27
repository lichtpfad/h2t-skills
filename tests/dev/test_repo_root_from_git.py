"""The repository you are in is a question git answers exactly (#444).

`docs-lint` and `docs-index` used to walk up from the cwd looking for a directory whose
*name* appears in `REPO_MANIFEST` — sixteen of the author's private repositories. Inside
anything else the walk fell through, and `lint.py` returned the cwd. Measured
2026-08-27 before the fix: run from `docs/sub` of a repository not on that list,
`repo_root` came back as `docs/sub`. Not "some checks are disabled" — the wrong root,
with no notice.

`git rev-parse --show-toplevel` is right for everyone, including the sixteen. The name
walk survives as a second answer, for a plain directory tree that is one of them without
being a checkout.
"""

import importlib.util
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
COMMON = ROOT / "plugins" / "h2t-dev" / "lib" / "docs" / "common.py"


def _common():
    spec = importlib.util.spec_from_file_location("_docs_common", COMMON)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def repo(tmp_path):
    (tmp_path / "docs" / "sub").mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    return tmp_path


def test_a_repository_not_on_the_list_still_resolves(repo, monkeypatch):
    """The defect. `repo.name` is a tmp directory — nowhere near REPO_MANIFEST."""
    m = _common()
    assert repo.name not in m.REPO_MANIFEST
    monkeypatch.chdir(repo / "docs" / "sub")
    assert m.git_repo_root() == repo.resolve()


def test_outside_a_repository_the_answer_is_none(tmp_path, monkeypatch):
    """None is a real answer; the caller decides. Silence here was the original bug."""
    m = _common()
    monkeypatch.chdir(tmp_path)
    assert m.git_repo_root() is None


def test_tiers_are_gone():
    """TIER_A/B/C had zero readers in the tree and carried sixteen private repo names."""
    m = _common()
    for name in ("TIER_A", "TIER_B", "TIER_C"):
        assert not hasattr(m, name), f"{name} is back — grep for a reader before keeping it"


def test_gh_is_a_real_path_or_nothing():
    """The fallback named a Windows install directory, so a machine without gh got a
    path that cannot exist and failed on exec instead of on the missing tool."""
    m = _common()
    assert m.GH is None or Path(m.GH).exists()
