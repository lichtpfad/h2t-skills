import importlib.util
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
URL = "https://github.com/lichtpfad/h2t-skills.git"


def _load(name: str):
    """Load scripts/<name>.py as a module (scripts/ is not a package)."""
    spec = importlib.util.spec_from_file_location(f"{name}_under_test", ROOT / "scripts" / f"{name}.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


rp = _load("release_pointer")


def _mk(source):
    return {"name": "lichtpfad", "plugins": [{"name": "h2t-core", "source": source}]}


def test_set_pointer_turns_relative_path_into_pinned_git_subdir():
    m = rp.set_pointer(_mk("./plugins/h2t-core"), "v3.3.0", "a" * 40)
    assert m["plugins"][0]["source"] == {
        "source": "git-subdir", "url": URL, "path": "plugins/h2t-core",
        "ref": "v3.3.0", "sha": "a" * 40,
    }


def test_set_pointer_rejects_short_sha():
    with pytest.raises(ValueError, match="40"):
        rp.set_pointer(_mk("./plugins/h2t-core"), "v3.3.0", "abc1234")


def test_read_pointer_requires_one_ref_for_all_plugins():
    m = {"plugins": [
        {"name": "a", "source": {"source": "git-subdir", "url": URL, "path": "plugins/a", "ref": "v1", "sha": "a" * 40}},
        {"name": "b", "source": {"source": "git-subdir", "url": URL, "path": "plugins/b", "ref": "v2", "sha": "a" * 40}},
    ]}
    with pytest.raises(ValueError, match="one release"):
        rp.read_pointer(m)


@pytest.mark.xfail(strict=True, reason="pointer moves at the freeze (owner step, Task 3 Step 5)")
def test_repository_marketplace_is_pinned():
    m = json.loads((ROOT / ".claude-plugin/marketplace.json").read_text(encoding="utf-8"))
    pins = rp.read_pointer(m)
    assert pins, "marketplace.json has no pinned plugins"


def test_the_pointer_tag_has_a_release_with_the_wheel_and_constraints():
    """From 4.0.0 on, the tag main points at carries a Release with both assets (§9.9).

    Asked of GitHub with `gh release view`, so it runs in CI with GH_TOKEN only."""
    m = json.loads((ROOT / ".claude-plugin/marketplace.json").read_text(encoding="utf-8"))
    try:
        ref = next(iter(rp.read_pointer(m).values()))[0]
    except (ValueError, KeyError) as exc:
        pytest.skip(f"the pointer is not pinned yet ({exc})")
    ver = ref.removeprefix("v")
    if tuple(int(part) for part in ver.split(".")) < (4, 0, 0):
        pytest.skip(f"the pointer is at {ref}; releases before 4.0.0 carry no wheel")
    if not (os.environ.get("CI") and os.environ.get("GH_TOKEN")):
        pytest.skip("asks GitHub through gh; runs in CI with GH_TOKEN only")
    gh = shutil.which("gh")
    assert gh, "gh is not on PATH on this runner"
    r = subprocess.run([gh, "release", "view", ref, "--repo", "lichtpfad/h2t-skills", "--json", "assets",
                        "--jq", ".assets[].name"], capture_output=True, text=True, encoding="utf-8",
                       timeout=60)
    assert r.returncode == 0, f"no Release for {ref}: {r.stderr.strip()}"
    missing = {f"h2t_ops-{ver}-py3-none-any.whl", "constraints.txt"} - set(r.stdout.split())
    assert not missing, f"Release {ref} lacks {sorted(missing)}"


def _tree(tmp_path: Path, source) -> None:
    (tmp_path / ".claude-plugin").mkdir()
    pdir = tmp_path / "plugins" / "p" / ".claude-plugin"
    pdir.mkdir(parents=True)
    (pdir / "plugin.json").write_text(json.dumps({"name": "p", "version": "1.0.0"}), encoding="utf-8")
    market = {"plugins": [{"name": "p", "version": "1.0.0", "source": source}]}
    (tmp_path / ".claude-plugin" / "marketplace.json").write_text(json.dumps(market), encoding="utf-8")


PINNED = {"source": "git-subdir", "url": URL, "path": "plugins/p", "ref": "v1", "sha": "b" * 40}


def _git(root: Path, *args: str) -> str:
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=root,
                          capture_output=True, text=True, check=True).stdout.strip()


def _pinned_repo(tmp_path: Path) -> tuple[Path, str]:
    """A repo whose commit `sha` (tag v1) has plugins/p at 1.0.0, and marketplace.json pinned
    to it with version 1.0.0."""
    _tree(tmp_path, "./plugins/p")
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "v1")
    _git(tmp_path, "tag", "v1")
    sha = _git(tmp_path, "rev-parse", "HEAD")
    market = tmp_path / ".claude-plugin" / "marketplace.json"
    data = json.loads(market.read_text(encoding="utf-8"))
    market.write_text(json.dumps(rp.set_pointer(data, "v1", sha)), encoding="utf-8")
    return tmp_path, sha


def _bump_working_tree(root: Path, ver: str) -> None:
    pj = root / "plugins" / "p" / ".claude-plugin" / "plugin.json"
    pj.write_text(json.dumps({"name": "p", "version": ver}), encoding="utf-8")


def _check(root: Path, monkeypatch) -> int:
    mod = _load("check_marketplace_sync")
    monkeypatch.setattr(mod, "ROOT", root)
    return mod.main()


def test_marketplace_sync_accepts_a_relative_source(tmp_path, monkeypatch):
    _tree(tmp_path, "./plugins/p")
    assert _check(tmp_path, monkeypatch) == 0


def test_marketplace_sync_relative_source_compares_the_working_tree(tmp_path, monkeypatch):
    _tree(tmp_path, "./plugins/p")
    _bump_working_tree(tmp_path, "1.0.1")
    assert _check(tmp_path, monkeypatch) == 1


def test_marketplace_sync_reads_a_pinned_entry_at_its_commit(tmp_path, monkeypatch):
    """The release commit stamps plugin.json to the new version while the pointer still names
    the previous tag: main must stay green until the pointer moves."""
    root, _ = _pinned_repo(tmp_path)
    _bump_working_tree(root, "2.0.0")
    assert _check(root, monkeypatch) == 0


def test_marketplace_sync_pinned_label_must_match_plugin_json_at_the_pin(tmp_path, monkeypatch,
                                                                       capsys):
    root, _ = _pinned_repo(tmp_path)
    market = root / ".claude-plugin" / "marketplace.json"
    data = json.loads(market.read_text(encoding="utf-8"))
    data["plugins"][0]["version"] = "2.0.0"  # the label moved ahead of the content
    market.write_text(json.dumps(data), encoding="utf-8")
    _bump_working_tree(root, "2.0.0")
    assert _check(root, monkeypatch) == 1
    assert "marketplace=2.0.0" in capsys.readouterr().err


def test_marketplace_sync_an_unreadable_pin_is_drift(tmp_path, monkeypatch, capsys):
    root, _ = _pinned_repo(tmp_path)
    market = root / ".claude-plugin" / "marketplace.json"
    data = json.loads(market.read_text(encoding="utf-8"))
    data["plugins"][0]["source"]["sha"] = "b" * 40
    market.write_text(json.dumps(data), encoding="utf-8")
    assert _check(root, monkeypatch) == 1
    assert "b" * 40 in capsys.readouterr().err


def test_pointer_set_stamps_each_version_from_plugin_json_at_the_target(tmp_path, monkeypatch):
    """The labels move with the pointer, in the same commit: `set` reads each plugin's version
    at the commit it pins (git show), not from the working tree."""
    root, _ = _pinned_repo(tmp_path)
    _bump_working_tree(root, "2.0.0")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "v2")
    sha2 = _git(root, "rev-parse", "HEAD")
    _bump_working_tree(root, "9.9.9")  # the working tree is not what gets pinned
    monkeypatch.setattr(rp, "ROOT", root)
    assert rp.main(["set", "v2", sha2]) == 0
    entry = json.loads((root / ".claude-plugin" / "marketplace.json").read_text())["plugins"][0]
    assert entry["version"] == "2.0.0"
    assert (entry["source"]["ref"], entry["source"]["sha"]) == ("v2", sha2)


def test_set_pointer_writes_given_versions():
    m = rp.set_pointer({"plugins": [{"name": "h2t-core", "version": "1.0.0",
                                     "source": "./plugins/h2t-core"}]},
                       "v4.0.0", "a" * 40, versions={"h2t-core": "4.0.0"})
    assert m["plugins"][0]["version"] == "4.0.0"


@pytest.mark.parametrize("source", ["./plugins/p", PINNED], ids=["string", "git-subdir"])
def test_bump_plugin_accepts_both_source_forms(tmp_path, monkeypatch, source):
    _tree(tmp_path, source)
    mod = _load("bump_plugin")
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    assert mod.main(["bump_plugin.py", "p", "1.0.1"]) == 0
    plugin = json.loads((tmp_path / "plugins/p/.claude-plugin/plugin.json").read_text(encoding="utf-8"))
    assert plugin["version"] == "1.0.1"
    entry = json.loads((tmp_path / ".claude-plugin/marketplace.json").read_text())["plugins"][0]
    # A pinned entry's label moves with the pointer (release_pointer.py set), not with a bump.
    assert entry["version"] == ("1.0.0" if isinstance(source, dict) else "1.0.1")
