# tests/docs/test_execution_tracking.py
import json
import sys
from pathlib import Path
import subprocess

_H2T_SKILLS = Path(__file__).parents[2]  # h2t-skills root (tests/docs/ -> repo root)
_LINT = Path(__file__).parents[2] / "plugins/h2t-dev/skills/docs-lint/scripts/lint.py"
_PYTHON = Path(sys.executable)  # the interpreter running the suite, not a Windows-only venv


def _run(args, cwd=None):
    r = subprocess.run(
        [str(_PYTHON), str(_LINT)] + args,
        capture_output=True, text=True, cwd=cwd,
    )
    return r


def test_plan_json_schema(tmp_path):
    """plan --json emits h2t_docs_fix_plan/v0.1 envelope."""
    docs = tmp_path / "docs" / "superpowers" / "specs"
    docs.mkdir(parents=True)
    (docs / "no-date-spec.md").write_text("---\ntitle: x\n---\n# x")
    r = _run(["plan", "--root", str(tmp_path), "--json"])
    assert r.returncode == 0, r.stderr
    obj = json.loads(r.stdout)
    assert obj["schema"] == "h2t_docs_fix_plan/v0.1"
    assert isinstance(obj["actions"], list)
    assert "plan_id" in obj


def test_plan_json_action_ids_stable(tmp_path):
    """Identical repo → same plan_id on repeated runs."""
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "README.md").write_text("# Docs\n")
    (tmp_path / "docs" / "stray.md").write_text("# orphan")
    r1 = _run(["plan", "--root", str(tmp_path), "--json"])
    r2 = _run(["plan", "--root", str(tmp_path), "--json"])
    assert json.loads(r1.stdout)["plan_id"] == json.loads(r2.stdout)["plan_id"]


def test_fix_safe_plan_writes_apply_report(tmp_path):
    """fix-safe --plan FILE writes h2t_docs_fix_apply_report/v0.1 to .h2t/."""
    (tmp_path / "docs" / "superpowers" / "specs").mkdir(parents=True)
    f = tmp_path / "docs" / "superpowers" / "specs" / "2026-05-28-my-spec.md"
    f.write_text("# No frontmatter here\n")

    plan_r = _run(["plan", "--root", str(tmp_path), "--json"])
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(plan_r.stdout)

    r = _run(["fix-safe", "--root", str(tmp_path), "--plan", str(plan_path)])
    assert r.returncode == 0, r.stderr

    reports = list((tmp_path / ".h2t").glob("lint-apply-*.json"))
    assert len(reports) == 1
    obj = json.loads(reports[0].read_text())
    assert obj["schema"] == "h2t_docs_fix_apply_report/v0.1"
    assert "plan_id" in obj
    assert isinstance(obj["actions"], list)


def test_fix_safe_plan_action_status_fields(tmp_path):
    """Every action in apply report has status, action_id, message."""
    (tmp_path / "docs" / "superpowers" / "specs").mkdir(parents=True)
    (tmp_path / "docs" / "superpowers" / "specs" / "2026-05-28-x.md").write_text("# x")
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(_run(["plan", "--root", str(tmp_path), "--json"]).stdout)
    _run(["fix-safe", "--root", str(tmp_path), "--plan", str(plan_path)])
    report = json.loads(list((tmp_path / ".h2t").glob("lint-apply-*.json"))[0].read_text())
    for action in report["actions"]:
        assert "action_id" in action
        assert action["status"] in {"applied", "skipped", "failed", "waived"}
        assert "message" in action


def test_fix_index_plan_apply_writes_report(tmp_path):
    """fix-index --plan FILE --apply writes apply report."""
    readme = tmp_path / "docs" / "README.md"
    (tmp_path / "docs").mkdir()
    readme.write_text("# Docs\n")
    (tmp_path / "docs" / "superpowers").mkdir()
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(_run(["plan", "--root", str(tmp_path), "--json"]).stdout)

    r = _run(["fix-index", "--root", str(tmp_path), "--plan", str(plan_path), "--apply"])
    assert r.returncode == 0, r.stderr
    reports = list((tmp_path / ".h2t").glob("lint-apply-*.json"))
    assert len(reports) == 1
    assert json.loads(reports[0].read_text())["schema"] == "h2t_docs_fix_apply_report/v0.1"


def test_waived_actions_appear_in_report(tmp_path):
    """Actions skipped due to requires_confirmation appear as waived, not missing."""
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "README.md").write_text("# Docs\n")
    (tmp_path / "docs" / "orphan.md").write_text("# Orphan\n")
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(_run(["plan", "--root", str(tmp_path), "--json"]).stdout)
    _run(["fix-safe", "--root", str(tmp_path), "--plan", str(plan_path)])
    report = json.loads(list((tmp_path / ".h2t").glob("lint-apply-*.json"))[0].read_text())
    statuses = {a["status"] for a in report["actions"]}
    assert "waived" in statuses
