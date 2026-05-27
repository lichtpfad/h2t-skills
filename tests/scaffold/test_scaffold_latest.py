"""Tests for create_latest_link in setup_h2t."""
import sys
from pathlib import Path

_SETUP_DIR = Path(__file__).parents[2] / "plugins/h2t-core/skills/setup/scripts"
sys.path.insert(0, str(_SETUP_DIR))

from setup_h2t import create_latest_link, _semver_key


def test_semver_key_orders_correctly():
    """3.2.0 sorts after 3.10.0 lexicographically but semver puts 3.10.0 higher."""
    assert _semver_key("3.10.0") > _semver_key("3.2.0")


def test_semver_key_ignores_non_version_dirs():
    """Non-version strings return a zero tuple instead of raising."""
    assert _semver_key("latest") == (0, 0, 0)
    assert _semver_key("something-else") == (0, 0, 0)


def test_create_latest_link_creates_junction(tmp_path):
    """Creates latest/ pointing to versioned dir."""
    versioned = tmp_path / "1.2.3"
    versioned.mkdir()
    latest = tmp_path / "latest"
    create_latest_link(versioned, latest)
    assert latest.exists()


def test_create_latest_link_updates_existing(tmp_path):
    """Updates latest/ when called again with a new version."""
    old = tmp_path / "1.0.0"
    old.mkdir()
    new = tmp_path / "2.0.0"
    new.mkdir()
    latest = tmp_path / "latest"
    create_latest_link(old, latest)
    create_latest_link(new, latest)
    assert latest.exists()


def test_create_latest_link_returns_path(tmp_path):
    """Returns the resolved latest path."""
    versioned = tmp_path / "1.0.0"
    versioned.mkdir()
    latest = tmp_path / "latest"
    result = create_latest_link(versioned, latest)
    assert result == latest
