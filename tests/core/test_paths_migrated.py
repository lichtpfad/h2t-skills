"""paths.migrated() and DOR_KEYS (#581)."""
import pytest

from h2t_ops.core import paths


@pytest.fixture(autouse=True)
def _home(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("H2T_PATH_ROOT", str(tmp_path / "root"))


def _layout(text):
    f = paths.layout_file()
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(text, encoding="utf-8")


@pytest.mark.parametrize("text,expected", [
    ('{"layout": 0}', False), ('{"layout": 1}', True), ('{"layout": 2}', True),
    ('{"layout": true}', False), ('{"layout": "1"}', False), ('{"layout": 1.0}', False),
    ("{not json", False), ("[1]", False), ("{}", False),
])
def test_migrated_by_layout(text, expected):
    _layout(text)
    assert paths.migrated() is expected


def test_migrated_false_without_the_file():
    assert paths.migrated() is False


def test_dor_keys_are_legacy_entries():
    assert len(paths.DOR_KEYS) == 6
    assert paths.DOR_KEYS <= set(paths.LEGACY)
    assert all(".dor" in k for k in paths.DOR_KEYS)
