# tests/docs/test_fix_plan.py
import sys
from pathlib import Path

_LIB = Path(__file__).parents[2] / "plugins/h2t-dev/lib"
sys.path.insert(0, str(_LIB))

from docs.fix_plan import build_fix_plan, _action_id, SCHEMA
from docs.reporter import finding


def test_build_fix_plan_schema():
    plan = build_fix_plan(repo_root="/tmp/repo", findings=[])
    assert plan["schema"] == SCHEMA
    assert plan["schema_version"] == "0.1"
    assert "plan_id" in plan
    assert "generated_at" in plan
    assert plan["generated_at"].endswith("Z")


def test_action_id_is_stable():
    """Same inputs → same action_id across calls."""
    id1 = _action_id("add_frontmatter", "docs/foo.md")
    id2 = _action_id("add_frontmatter", "docs/foo.md")
    assert id1 == id2
    assert id1.startswith("docs-action:")


def test_action_id_differs_by_type():
    id1 = _action_id("add_frontmatter", "docs/foo.md")
    id2 = _action_id("rename_file", "docs/foo.md")
    assert id1 != id2


def test_orphan_finding_maps_to_add_to_index():
    f = finding("orphan", "warn", "docs/old.md", "not reachable")
    plan = build_fix_plan(repo_root="/tmp/repo", findings=[f])
    assert len(plan["actions"]) == 1
    action = plan["actions"][0]
    assert action["type"] == "add_to_index"
    assert action["risk"] == "review"
    assert action["requires_confirmation"] is True
    assert action["path"] == "docs/old.md"


def test_naming_finding_maps_to_rename_file():
    f = finding("naming", "warn", "docs/MyDoc.md", "not kebab-case",
                safe_fix="rename to 'mydoc.md'")
    plan = build_fix_plan(repo_root="/tmp/repo", findings=[f])
    assert len(plan["actions"]) == 1
    action = plan["actions"][0]
    assert action["type"] == "rename_file"
    assert action["risk"] == "review"
    assert action["target_path"] == "mydoc.md"


def test_missing_dir_finding_maps_to_create_dir():
    f = finding("structure", "warn", "", "missing dir: docs/adr/")
    plan = build_fix_plan(repo_root="/tmp/repo", findings=[f])
    safe_actions = [a for a in plan["actions"] if a["type"] == "create_dir"]
    assert len(safe_actions) == 1
    assert safe_actions[0]["risk"] == "safe"
    assert safe_actions[0]["requires_confirmation"] is False


def test_frontmatter_finding_maps_to_add_frontmatter():
    f = finding("frontmatter", "info", "docs/foo.md", "missing title")
    plan = build_fix_plan(repo_root="/tmp/repo", findings=[f])
    action = plan["actions"][0]
    assert action["type"] == "add_frontmatter"
    assert action["risk"] == "safe"
    assert action["requires_confirmation"] is False


def test_plan_id_is_deterministic_for_same_findings():
    """Same findings → same plan_id (stable across runs)."""
    findings = [finding("orphan", "warn", "docs/x.md", "msg")]
    plan1 = build_fix_plan(repo_root="/tmp/repo", findings=findings)
    plan2 = build_fix_plan(repo_root="/tmp/repo", findings=findings)
    assert plan1["plan_id"] == plan2["plan_id"]


def test_empty_findings_empty_actions():
    plan = build_fix_plan(repo_root="/tmp/repo", findings=[])
    assert plan["actions"] == []


# --- apply_report ---

from docs.apply_report import build_apply_report, action_result, file_hash, APPLY_SCHEMA


def test_apply_report_schema():
    report = build_apply_report(plan_id="p1", run_id="r1", actions=[])
    assert report["schema"] == APPLY_SCHEMA
    assert report["schema_version"] == "0.1"
    assert "applied_at" in report


def test_action_result_applied():
    r = action_result("docs-action:abc", "applied", "created dir")
    assert r["status"] == "applied"
    assert r["action_id"] == "docs-action:abc"


def test_action_result_waived():
    r = action_result("docs-action:abc", "waived", "user declined rename")
    assert r["status"] == "waived"


def test_file_hash_empty_string_for_missing_file(tmp_path):
    assert file_hash(tmp_path / "nonexistent.md") == ""


def test_file_hash_stable(tmp_path):
    f = tmp_path / "test.md"
    f.write_text("# Hello")
    h1 = file_hash(f)
    h2 = file_hash(f)
    assert h1 == h2
    assert len(h1) == 16


def test_multiple_frontmatter_findings_have_distinct_action_ids():
    """Multiple frontmatter findings for different files → unique action_ids."""
    findings = [
        {"type": "frontmatter", "severity": "info", "path": "docs/a.md", "message": "docs/a.md: missing title"},
        {"type": "frontmatter", "severity": "info", "path": "docs/b.md", "message": "docs/b.md: missing title"},
        {"type": "frontmatter", "severity": "info", "path": "docs/c.md", "message": "docs/c.md: missing title"},
    ]
    plan = build_fix_plan(repo_root="/tmp", findings=findings)
    ids = [a["action_id"] for a in plan["actions"]]
    assert len(ids) == len(set(ids)), f"Colliding action_ids: {ids}"
