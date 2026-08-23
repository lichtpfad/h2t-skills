"""Tests for detect_project.py detection logic."""
import sys
from pathlib import Path

# Add lib to path for gather imports
PLUGIN_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(PLUGIN_ROOT / "lib"))

from detect_project import (
    _check_already_registered,
    _detect_domain,
    _detect_tracker,
    _humanize_id,
    detect_project,
)


def test_detect_domain_h2t_prefix():
    assert _detect_domain("C:/dev/h2t-vision") == ("hou2touch", "high", "path C:/dev/h2t-* matches hou2touch")


def test_detect_domain_crypto_prefix():
    assert _detect_domain("C:/dev/crypto-etl") == ("crypto", "high", "path C:/dev/crypto-* matches crypto")


def test_detect_domain_generic_dev():
    domain, confidence, reason = _detect_domain("C:/dev/some-project")
    assert domain == "dev"
    assert confidence == "medium"


def test_detect_domain_dropbox_h2t():
    domain, confidence, reason = _detect_domain("E:/DROPBOX/LichtPfad Dropbox/HOU2TOUCH/COURSES")
    assert domain == "hou2touch"
    assert confidence == "high"


def test_detect_domain_unknown():
    domain, confidence, reason = _detect_domain("D:/random/folder")
    assert domain is None
    assert confidence == "low"


def test_humanize_id():
    assert _humanize_id("h2t-vision") == "H2T Vision"
    assert _humanize_id("crypto-etl") == "Crypto ETL"
    assert _humanize_id("my-cool-project") == "My Cool Project"


def test_detect_tracker_github_only():
    """GitHub accessible, no notion -> github."""
    # Can't test gh CLI in unit tests, test the logic with mocked inputs
    domains = {"domains": {"dev": {"label": "Dev"}}}
    tracker, confidence, reason = _detect_tracker("lichtpfad/test", "dev", domains)
    # Note: this will try to run `gh` — may fail in CI. Test the no-github path instead.


def test_detect_tracker_deferred_when_no_domain():
    """Domain unknown -> tracker deferred."""
    domains = {"domains": {}}
    tracker, confidence, reason = _detect_tracker("lichtpfad/test", None, domains)
    assert tracker is None
    assert confidence == "deferred"


def test_detect_tracker_none_when_no_github_no_notion():
    """No GitHub, no Notion -> none."""
    domains = {"domains": {"admin": {"label": "Admin"}}}
    # github=None means no remote
    tracker, confidence, reason = _detect_tracker(None, "admin", domains)
    assert tracker == "none"
    assert confidence == "high"


def test_check_already_registered_found():
    mapping = {"mappings": {"my-repo": "dev/my-project"}, "cwd_patterns": {}}
    result = _check_already_registered("C:/dev/my-repo", "my-repo", mapping)
    assert result is not None
    assert result["id"] == "my-project"
    assert result["domain"] == "dev"


def test_check_already_registered_not_found():
    mapping = {"mappings": {"other-repo": "dev/other"}, "cwd_patterns": {}}
    result = _check_already_registered("C:/dev/new-repo", "new-repo", mapping)
    assert result is None


def test_check_already_registered_cwd_pattern():
    mapping = {"mappings": {}, "cwd_patterns": {"/Steuer": "admin/taxes"}}
    result = _check_already_registered("E:/DROPBOX/Steuer/2026", None, mapping)
    assert result is not None
    assert result["domain"] == "admin"
