"""h2t-project-audit-report writes the projects.yaml it is pointed at (#548 R7).

The path is the user's (--projects-yaml, or the landings checkout under H2T_DEV_ROOT), so
it goes through store with dest=True under any file name; a path store refuses comes back
as the command's JSON error, not a traceback.
"""
import json
import sys

import pytest

from h2t_ops.core import paths
from h2t_ops.lifecycle import project_audit_report as report

_YAML = "projects:\n  - id: foo\n    docs:\n      readme: false\n"


def _run(monkeypatch, yaml_path):
    monkeypatch.setattr(sys, "argv", ["h2t-project-audit-report", "foo", "--field", "readme=true",
                                      "--projects-yaml", str(yaml_path)])
    report.main()


def test_any_file_name_is_updated(tmp_path, monkeypatch, capsys):
    target = tmp_path / "my-landings.yml"
    target.write_text(_YAML, encoding="utf-8")
    _run(monkeypatch, target)
    assert "readme: true" in target.read_text(encoding="utf-8")
    assert json.loads(capsys.readouterr().out)["success"] is True


def test_a_refused_path_is_a_json_error(monkeypatch, capsys):
    """Inside ~/.h2t no --dest write is allowed: exit 1 with the refusal in the JSON."""
    target = paths.state_dir() / "projects.yaml"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(_YAML, encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        _run(monkeypatch, target)
    assert exc.value.code == 1
    out = json.loads(capsys.readouterr().out)
    assert "points into state" in out["error"]
    assert "readme: false" in target.read_text(encoding="utf-8")
