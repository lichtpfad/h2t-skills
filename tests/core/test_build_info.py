"""`h2t-ops --version` must name the build, not just the semver (#363).

The wheel version has not moved since 2026-05-22 while 429 commits landed, because
`uv tool install --reinstall git+...` refetches the branch head regardless of it.
`setup doctor` reports that constant, so it cannot answer the one question it exists
to answer — is this install current? uv already records the resolved commit in the
PEP 610 `direct_url.json`; these tests pin surfacing it.
"""

import json

from h2t_ops import build_info, cli


class _Dist:
    """Stands in for importlib.metadata.Distribution — only read_text is used."""

    def __init__(self, payload):
        self._payload = payload

    def read_text(self, name):
        if name != "direct_url.json":
            return None
        return self._payload


def test_git_install_reports_the_short_commit():
    dist = _Dist(json.dumps({
        "url": "https://github.com/lichtpfad/h2t-skills.git",
        "vcs_info": {"vcs": "git", "commit_id": "03197a8f6fc5e1a02514e8073bb0870522286eb7"},
    }))
    assert build_info.build_id(dist) == "git 03197a8"


def test_editable_install_reports_the_checkout_path():
    dist = _Dist(json.dumps({
        "url": "file:///Users/dev/Projects/h2t-skills",
        "dir_info": {"editable": True},
    }))
    assert build_info.build_id(dist) == "editable /Users/dev/Projects/h2t-skills"


def test_plain_directory_install_is_not_called_editable():
    dist = _Dist(json.dumps({"url": "file:///Users/dev/Projects/h2t-skills", "dir_info": {}}))
    assert build_info.build_id(dist) == ""


def test_missing_metadata_degrades_to_empty():
    assert build_info.build_id(_Dist(None)) == ""


def test_malformed_metadata_degrades_to_empty():
    assert build_info.build_id(_Dist("{not json")) == ""


def test_version_line_appends_the_build_when_known():
    dist = _Dist(json.dumps({"vcs_info": {"commit_id": "03197a8f6fc5e1a02514e8073bb0870522286eb7"}}))
    line = build_info.version_line(dist)
    assert line.startswith("h2t-ops ")
    assert line.endswith(" (git 03197a8)")


def test_version_line_is_bare_semver_without_metadata():
    assert " (" not in build_info.version_line(_Dist(None))


def test_cli_version_flag_prints_the_build_line(monkeypatch, capsys):
    """The flag doctor shells out to (setup_h2t.py:200-207) must carry the build."""
    monkeypatch.setattr(build_info, "build_id", lambda dist=None: "git deadbee")
    assert cli.dispatch(["--version"]) == 0
    assert capsys.readouterr().out.strip().endswith(" (git deadbee)")


def test_argparse_version_action_carries_the_build(monkeypatch):
    """`--version` reaches argparse whenever a subcommand parser handles it."""
    monkeypatch.setattr(build_info, "build_id", lambda dist=None: "git deadbee")
    action = next(a for a in cli.build_parser()._actions if "--version" in a.option_strings)
    assert action.version.endswith(" (git deadbee)")


def test_doctor_leads_with_the_build_line(monkeypatch, capsys):
    """`h2t-ops doctor` is the other place a human reads the version from."""
    monkeypatch.setattr(build_info, "build_id", lambda dist=None: "git deadbee")
    cli._doctor()
    assert capsys.readouterr().out.splitlines()[0].endswith(" (git deadbee)")
