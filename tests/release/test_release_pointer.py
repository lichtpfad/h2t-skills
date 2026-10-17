import importlib.util
import json
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


def test_repository_marketplace_is_pinned():
    m = json.loads((ROOT / ".claude-plugin/marketplace.json").read_text(encoding="utf-8"))
    pins = rp.read_pointer(m)
    assert pins, "marketplace.json has no pinned plugins"


def _tree(tmp_path: Path, source) -> None:
    (tmp_path / ".claude-plugin").mkdir()
    pdir = tmp_path / "plugins" / "p" / ".claude-plugin"
    pdir.mkdir(parents=True)
    (pdir / "plugin.json").write_text(json.dumps({"name": "p", "version": "1.0.0"}), encoding="utf-8")
    market = {"plugins": [{"name": "p", "version": "1.0.0", "source": source}]}
    (tmp_path / ".claude-plugin" / "marketplace.json").write_text(json.dumps(market), encoding="utf-8")


PINNED = {"source": "git-subdir", "url": URL, "path": "plugins/p", "ref": "v1", "sha": "b" * 40}


@pytest.mark.parametrize("source", ["./plugins/p", PINNED], ids=["string", "git-subdir"])
def test_marketplace_sync_accepts_both_source_forms(tmp_path, monkeypatch, source):
    _tree(tmp_path, source)
    mod = _load("check_marketplace_sync")
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    assert mod.main() == 0


@pytest.mark.parametrize("source", ["./plugins/p", PINNED], ids=["string", "git-subdir"])
def test_bump_plugin_accepts_both_source_forms(tmp_path, monkeypatch, source):
    _tree(tmp_path, source)
    mod = _load("bump_plugin")
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    assert mod.main(["bump_plugin.py", "p", "1.0.1"]) == 0
    plugin = json.loads((tmp_path / "plugins/p/.claude-plugin/plugin.json").read_text(encoding="utf-8"))
    assert plugin["version"] == "1.0.1"
