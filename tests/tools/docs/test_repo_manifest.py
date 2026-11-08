"""REPO_MANIFEST comes from the repo mapping through the index (#548 Task 15), read on first
use. There is no bundled list: without a mapping, or with an index that cannot open, the answer
is a ConfigError (#581)."""
import sqlite3

import pytest

from h2t_ops.core import paths
from h2t_ops.core.errors import ConfigError
from h2t_ops.lifecycle import index
from h2t_ops.tools.docs import common


def test_the_mapping_is_read_through_the_index():
    cfg = paths.config_dir()
    cfg.mkdir(parents=True)
    (cfg / "repo-mapping.yaml").write_text("mappings:\n  zeta: dev/z\n  alpha: dev/a\n", encoding="utf-8")
    assert common._manifest() == ["alpha", "zeta"]
    assert (paths.state_dir() / "index.sqlite").is_file()


def test_no_mapping_is_a_config_error_not_a_list():
    with pytest.raises(ConfigError):
        common._manifest()


def test_an_index_that_cannot_open_is_a_config_error(monkeypatch):
    def broken():
        raise sqlite3.OperationalError("unable to open database file")
    monkeypatch.setattr(index, "ontology", broken)
    with pytest.raises(ConfigError):
        common._manifest()


def test_the_manifest_is_read_on_first_use_not_at_import(monkeypatch):
    """Importing common must not build the index. The suite collects under a temporary HOME
    (conftest.pytest_configure); outside it, lazy loading keeps a plain import of the docs tools
    from creating state/index.sqlite in any process that never asks for the manifest."""
    calls = []
    monkeypatch.setattr(common, "_manifest", lambda: calls.append(1) or ["one"])
    m = common._Manifest()
    assert calls == []
    assert "one" in m and list(m) == ["one"] and len(m) == 1
    assert calls == [1]
