"""config/user.yaml: the user's values, read only (#548 R45)."""
import pytest

from h2t_ops.core import paths, user_config
from h2t_ops.core.errors import ConfigError


def _write(text: str):
    f = paths.config_dir() / "user.yaml"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(text, encoding="utf-8")
    return f


def test_no_file_is_none():
    assert not user_config.path().exists()
    assert user_config.get("timezone") is None


def test_the_file_is_in_config_dir():
    assert user_config.path() == paths.config_dir() / "user.yaml"


def test_top_level_and_nested_keys():
    _write("timezone: Europe/Paris\nnotion:\n  tasks_database_id: fake-db\n")
    assert user_config.get("timezone") == "Europe/Paris"
    assert user_config.get("notion.tasks_database_id") == "fake-db"


def test_missing_key_and_non_mapping_on_the_way_are_none():
    _write("timezone: Europe/Paris\nnotion: just-a-string\n")
    assert user_config.get("calendar") is None
    assert user_config.get("notion.tasks_database_id") is None
    assert user_config.get("timezone.x") is None


def test_empty_file_is_none():
    _write("")
    assert user_config.get("timezone") is None


def test_broken_yaml_names_the_file_and_line():
    f = _write("timezone: Europe/Paris\nnotion: [unclosed\n")
    with pytest.raises(ConfigError) as exc:
        user_config.get("timezone")
    assert str(f) in str(exc.value)
    assert "line " in str(exc.value)
