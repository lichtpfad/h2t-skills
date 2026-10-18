"""`scripts/release.py prepare <ver>`: one version everywhere, one bootstrap literal (spec §7.1, §7.2).

Every test works on a copy of the shipped tree under tmp_path — prepare never runs on the
real checkout here. The copy's marketplace is pinned to `v3.9.0`, the state the owner's
freeze leaves it in; the real one is not pinned yet.
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import REAL_HOME

ROOT = Path(__file__).resolve().parents[2]
SHIPPED = ("pyproject.toml", "uv.lock", "README.md", ".claude-plugin/", "plugins/", "scripts/", "h2t_ops/")
PY = "3.12.11"
BASE = "https://github.com/lichtpfad/h2t-skills/releases/download"
UV = shutil.which("uv")
BASH = shutil.which("bash")


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _urls(ver):
    return (f"{BASE}/v{ver}/h2t_ops-{ver}-py3-none-any.whl", f"{BASE}/v{ver}/constraints.txt")


def _copy(dest: Path, prefixes: tuple[str, ...] | None) -> Path:
    """The tracked and untracked-but-not-ignored files under prefixes, pinned at v3.9.0."""
    listed = subprocess.run(["git", "ls-files", "-co", "--exclude-standard", "-z"], cwd=ROOT,
                            capture_output=True, check=True).stdout.decode().split("\0")
    for rel in listed:
        if rel and (prefixes is None or rel.startswith(prefixes)) and (ROOT / rel).is_file():
            (dest / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / rel, dest / rel)
    pointer = _load(dest / "scripts" / "release_pointer.py", "release_pointer_copy")
    market = dest / ".claude-plugin" / "marketplace.json"
    data = pointer.set_pointer(json.loads(market.read_text(encoding="utf-8")), "v3.9.0", "a" * 40)
    market.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (dest / "CHANGELOG.md").write_text("# Changelog\n\n## 4.0.1\n\n## 4.0.0\n", encoding="utf-8")
    return dest


@pytest.fixture
def repo(tmp_path):
    return _copy(tmp_path / "repo", SHIPPED)


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=repo,
                          capture_output=True, text=True, check=True).stdout


@pytest.fixture
def rel(repo):
    return _load(repo / "scripts" / "release.py", "release_copy")


def _versions(repo: Path) -> set[str]:
    found = {re.search(r'^version = "([^"]*)"$', (repo / "pyproject.toml").read_text(), re.M)[1],
             re.search(r'^__version__ = "([^"]*)"$', (repo / "h2t_ops/__init__.py").read_text(), re.M)[1]}
    for pj in (repo / "plugins").glob("*/.claude-plugin/plugin.json"):
        found.add(json.loads(pj.read_text(encoding="utf-8"))["version"])
    for env in (repo / "plugins").glob("*/release.env"):
        found.add(env.read_text().strip().removeprefix("VERSION="))
    for md in (repo / "plugins").rglob("*.md"):
        found.update(re.findall(r"h2t-ops version --expect (?!<ver> )(\S+) --json", md.read_text(encoding="utf-8")))
    return found


def _bootstrap_copies(repo: Path) -> dict[str, list[str]]:
    """Every generated copy of the bootstrap, parsed back to argv."""
    copies = {"release.json": json.loads((repo / "release.json").read_text())["bootstrap"]}
    module = _load(repo / "h2t_ops/setup/_release.py", "release_data_copy")
    copies["_release.BOOTSTRAP"] = module.BOOTSTRAP
    copies["_release.BOOTSTRAP_COMMAND"] = shlex.split(module.BOOTSTRAP_COMMAND)
    for run in (repo / "plugins").glob("*/hooks/run"):
        line = re.search(r"^BOOTSTRAP='([^']*)'", run.read_text(encoding="utf-8"), re.M)[1]
        copies[run.relative_to(repo).as_posix()] = shlex.split(line)
    for md in (repo / "plugins").rglob("*.md"):
        for i, cmd in enumerate(re.findall(r"`(uvx --isolated [^`]*) sync`", md.read_text(encoding="utf-8"))):
            copies[f"{md.relative_to(repo).as_posix()}#{i}"] = shlex.split(cmd)
    for i, cmd in enumerate(re.findall(r"^(uvx --isolated .*) sync$", (repo / "README.md").read_text(encoding="utf-8"), re.M)):
        copies[f"README.md#{i}"] = shlex.split(cmd)
    return copies


def test_bootstrap_argv_is_the_spec_literal(rel):
    assert rel.bootstrap_argv("4.0.0", "W", "C", PY) == [
        "uvx", "--isolated", "--python", PY, "--managed-python", "-c", "C",
        "--from", "h2t-ops @ W", "h2t-setup"]


def test_stamp_twice_sets_one_version_and_one_bootstrap_everywhere(repo, rel):
    rel.stamp(repo, "4.0.0")
    assert _versions(repo) == {"4.0.0"}
    counts = rel.stamp(repo, "4.0.1")  # the slots of 4.0.0 are slots again
    assert _versions(repo) == {"4.0.1"}
    assert counts["plugins/h2t-core/hooks/run"] == 1
    assert counts["plugins/h2t-core/references/version-check.md"] == 3

    rel.write_manifest(repo, "4.0.1")
    wheel, constraints = _urls("4.0.1")
    expected = rel.bootstrap_argv("4.0.1", wheel, constraints, PY)
    assert expected[:6] == ["uvx", "--isolated", "--python", PY, "--managed-python", "-c"]
    assert expected[-1] == "h2t-setup"
    copies = _bootstrap_copies(repo)
    md_copies = [k for k in copies if k.startswith("plugins/") and k.endswith((".md#0", ".md#1"))]
    assert len(md_copies) == 2 * 23  # 22 SKILL.md + the reference, two per block
    assert [k for k in copies if k.startswith("README.md#")] == ["README.md#0"]
    assert counts["README.md"] == 1
    assert {k: v for k, v in copies.items() if v != expected} == {}
    for path in [*(repo / "plugins").rglob("*"), *(repo / "h2t_ops").rglob("*.py")]:
        if path.is_file():
            text = path.read_text(encoding="utf-8", errors="replace")
            assert "@BOOTSTRAP@" not in text and "@VERSION@" not in text, path


def test_manifest_fields_and_previous_is_the_pointer(repo, rel):
    rel.write_manifest(repo, "4.0.0")
    wheel, constraints = _urls("4.0.0")
    data = json.loads((repo / "release.json").read_text())
    assert data == {"format": 1, "version": "4.0.0", "previous": "3.9.0", "python": PY,
                    "wheel": wheel, "constraints": constraints,
                    "bootstrap": rel.bootstrap_argv("4.0.0", wheel, constraints, PY)}


def test_stamp_leaves_marketplace_json_alone(repo, rel):
    """Its versions move with the pointer (release_pointer.py set), never before it: between
    the release commit and the pointer move main would label the previous tag's content with
    the new version."""
    market = repo / ".claude-plugin/marketplace.json"
    before = market.read_bytes()
    counts = rel.stamp(repo, "4.0.0")
    assert market.read_bytes() == before
    assert ".claude-plugin/marketplace.json" not in counts


def test_marketplace_sync_hook_still_passes_after_stamp(repo, rel):
    """The release commit is on main before the pointer moves: the check compares each pinned
    entry with plugin.json at the pinned commit, not with the stamped working tree."""
    _git(repo, "init", "-q")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "the previous release")
    sha = _git(repo, "rev-parse", "HEAD").strip()
    pointer = _load(repo / "scripts" / "release_pointer.py", "release_pointer_pin")
    market = repo / ".claude-plugin" / "marketplace.json"
    market.write_text(json.dumps(pointer.set_pointer(json.loads(market.read_text()), "v3.9.0", sha),
                                 indent=2) + "\n", encoding="utf-8")
    rel.stamp(repo, "4.0.0")
    result = subprocess.run([sys.executable, str(repo / "scripts/check_marketplace_sync.py")],
                            capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 0, result.stderr


def test_a_slot_count_mismatch_fails_and_writes_nothing(repo, rel):
    skill = repo / "plugins/h2t-dev/skills/docs-lint/SKILL.md"
    skill.write_text(skill.read_text(encoding="utf-8").replace("`@BOOTSTRAP@ sync`", "`it`", 1),
                     encoding="utf-8")
    before = (repo / "pyproject.toml").read_text()
    with pytest.raises(rel.ReleaseError, match="docs-lint/SKILL.md"):
        rel.stamp(repo, "4.0.0")
    assert (repo / "pyproject.toml").read_text() == before


def test_stamp_keeps_each_files_line_endings(tmp_path):
    """A Windows checkout (autocrlf=true) has CRLF files; an owner there may run prepare.
    Stamping changes the slots and no other byte: CRLF stays CRLF, a bare LF stays LF."""
    lf_repo, crlf_repo = _copy(tmp_path / "lf", SHIPPED), _copy(tmp_path / "crlf", SHIPPED)
    lf_rel = _load(lf_repo / "scripts" / "release.py", "release_lf")
    generated = Path("h2t_ops/setup/_release.py")
    edited = [p.relative_to(lf_repo) for p in lf_rel._plan(lf_repo, "4.0.0") if p.relative_to(lf_repo) != generated]
    mixed = Path("pyproject.toml")  # one file with both endings: the first line keeps LF
    for rel_path in edited:  # LF in one copy, CRLF in the other, whatever the checkout has
        lf = (lf_repo / rel_path).read_bytes().replace(b"\r\n", b"\n")
        (lf_repo / rel_path).write_bytes(lf)
        data = lf.replace(b"\n", b"\r\n")
        if rel_path == mixed:
            data = data.replace(b"\r\n", b"\n", 1)
        (crlf_repo / rel_path).write_bytes(data)
    before = {p: (crlf_repo / p).read_bytes() for p in edited}

    lf_counts = lf_rel.stamp(lf_repo, "4.0.0")
    assert _load(crlf_repo / "scripts" / "release.py", "release_crlf").stamp(crlf_repo, "4.0.0") == lf_counts
    for rel_path in edited:
        got = (crlf_repo / rel_path).read_bytes()
        assert got.count(b"\r\n") == before[rel_path].count(b"\r\n"), rel_path
        assert got.count(b"\n") == before[rel_path].count(b"\n"), rel_path
        expected = (lf_repo / rel_path).read_bytes().replace(b"\n", b"\r\n")
        if rel_path == mixed:
            expected = expected.replace(b"\r\n", b"\n", 1)
        assert got == expected, rel_path


def test_the_readme_carries_exactly_one_bootstrap_slot():
    """README's install section is the bootstrap of the current release, stamped like the
    skills; in a checkout it holds the placeholder, after prepare the literal."""
    rel = _load(ROOT / "scripts" / "release.py", "release_readme")
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert len(rel.BOOTSTRAP_SLOT.findall(text)) == rel.README_BOOTSTRAPS == 1


def test_a_second_readme_slot_fails_and_writes_nothing(repo, rel):
    readme = repo / "README.md"
    readme.write_text(readme.read_text(encoding="utf-8") + "\n@BOOTSTRAP@ update\n", encoding="utf-8")
    before = (repo / "pyproject.toml").read_text()
    with pytest.raises(rel.ReleaseError, match="README.md"):
        rel.stamp(repo, "4.0.0")
    assert (repo / "pyproject.toml").read_text() == before


def test_unpinned_pointer_is_a_clear_error(repo, rel):
    market = repo / ".claude-plugin/marketplace.json"
    data = json.loads(market.read_text())
    data["plugins"][0]["source"] = "./plugins/h2t-core"
    market.write_text(json.dumps(data))
    with pytest.raises(rel.ReleaseError, match="not pinned"):
        rel.prepare(repo, "4.0.0")


def test_missing_changelog_heading_is_an_error(repo, rel):
    with pytest.raises(rel.ReleaseError, match="## 4.2.0"):
        rel.prepare(repo, "4.2.0")


def test_bad_version_is_an_error(repo, rel):
    with pytest.raises(rel.ReleaseError, match="X.Y.Z"):
        rel.prepare(repo, "v4.0.0")


def test_version_check_hint_is_the_stamped_bootstrap(monkeypatch):
    from h2t_ops.setup import _release, state, version_check
    monkeypatch.setattr(_release, "BOOTSTRAP_COMMAND", "uvx --isolated X h2t-setup")
    monkeypatch.setattr(state, "read", lambda: None)
    assert version_check.check("4.0.0")["hint"].endswith("uvx --isolated X h2t-setup sync")


@pytest.mark.skipif(BASH is None, reason="bash is not on PATH")
def test_stamped_hooks_run_notice_is_valid_json(repo, rel, tmp_path):
    rel.stamp(repo, "4.0.0")
    plugin = repo / "plugins/h2t-core"
    env = {"PATH": os.environ.get("PATH", ""), "HOME": str(tmp_path / "home"),
           "CLAUDE_PLUGIN_ROOT": str(plugin)}
    payload = json.dumps({"hook_event_name": "SessionStart", "session_id": "s1"}).encode()
    result = subprocess.run([BASH, str(plugin / "hooks/run"), "probe"], input=payload,
                            capture_output=True, env=env, check=False)
    wheel, constraints = _urls("4.0.0")
    message = json.loads(result.stdout)["systemMessage"]
    assert shlex.split(message.rsplit(": ", 1)[1]) == [
        *rel.bootstrap_argv("4.0.0", wheel, constraints, PY), "sync"]


@pytest.mark.skipif(UV is None, reason="uv is not on PATH (CI installs with pip); prepare exports through uv")
def test_prepare_cli_twice_exports_constraints_and_locks_the_version(repo, monkeypatch):
    # uv lock --offline resolves from the real uv cache under the real HOME (#548 R5)
    monkeypatch.setenv("HOME", str(REAL_HOME))
    for ver in ("4.0.0", "4.0.1"):
        result = subprocess.run([sys.executable, str(repo / "scripts/release.py"), "prepare", ver],
                                capture_output=True, text=True, encoding="utf-8")
        assert result.returncode == 0, result.stderr
    assert json.loads((repo / "release.json").read_text())["version"] == "4.0.1"
    lines = (repo / "constraints.txt").read_text().splitlines()
    assert any(line.startswith("httpx==") for line in lines)
    assert not [line for line in lines if re.match(r"h2t[-_]ops", line, re.I)]
    lock = (repo / "uv.lock").read_text()
    assert re.search(r'name = "h2t-ops"\nversion = "4.0.1"', lock)


def test_the_suites_that_read_the_slots_pass_on_a_stamped_tree(tmp_path):
    """The release commit has to pass its own CI: the tests over SKILL.md and hooks/run read
    the slots through release.py's patterns, not through the placeholders."""
    copy = _copy(tmp_path / "copy", None)
    _load(copy / "scripts" / "release.py", "release_seam").stamp(copy, "4.0.0")
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "--rootdir", str(copy),
         "tests/skills/test_skill_commands_exist.py", "tests/hooks/test_hooks_run.py"],
        cwd=copy, capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert result.returncode == 0, result.stdout[-3000:]


def test_a_failure_after_stamp_restores_the_tree(repo, rel, monkeypatch):
    _git(repo, "init", "-q")
    (repo / "release.json").write_text("{}\n")  # an earlier release's manifest
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "base")

    def uv(root, *args):
        if args[0] == "lock":
            (root / "uv.lock").write_text("changed by lock\n")
            (root / "constraints.txt").write_text("partial\n")
            return
        raise rel.ReleaseError("uv export failed: drawpyo was not found in the cache")

    monkeypatch.setattr(rel, "_uv", uv)
    with pytest.raises(rel.ReleaseError, match="restored") as caught:
        rel.prepare(repo, "4.0.0")
    assert "drawpyo" in str(caught.value)
    assert _git(repo, "status", "--porcelain", "--untracked-files=all") == ""
