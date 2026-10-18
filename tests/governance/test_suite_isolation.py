"""The whole suite runs under its own HOME (#548 R5): conftest._isolate_home_writes moves it
before every test, so a test that forgets its own isolation still never reaches the real
~/.dor/secrets.env, ~/.h2t or ~/.config/google-calendar-mcp."""
import sys
from pathlib import Path

from h2t_ops.core import secrets


def _root_conftest():
    mod = sys.modules["conftest"]
    assert Path(mod.__file__).resolve() == Path(__file__).resolve().parents[2] / "conftest.py"
    return mod


def test_home_is_not_the_real_one():
    assert Path.home() != _root_conftest().REAL_HOME


def test_every_legacy_secrets_source_lies_under_the_test_home():
    home = Path.home()
    sources = secrets.legacy_sources()
    assert sources
    assert all(home in p.parents for _, p in sources), sources
