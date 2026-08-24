"""Tests for structure_guard.py PreToolUse hook."""
from __future__ import annotations

import importlib.util
import io
import json
from pathlib import Path


def _load_guard():
    path = Path(__file__).parents[2] / "plugins" / "h2t-core" / "hooks-handlers" / "structure_guard.py"
    spec = importlib.util.spec_from_file_location("structure_guard_under_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


# ── config fixture ──────────────────────────────────────────────────────────

SAMPLE_CONFIG = {
    "allowed_root_dirs": ["plugins/", "docs/", "h2t_ops/", "lib/", "scripts/", "tests/"],
    "forbidden_patterns": ["tmp_*", "*_tmp.*", "*_v2.*", "*_copy.*", "*_backup.*"],
    "plan_dirs": [
        {"path": "docs/superpowers/plans/", "pattern": r"^\d{4}-\d{2}-\d{2}-.+\.md$"},
    ],
}


# ── _parse_yaml ──────────────────────────────────────────────────────────────

def test_parse_yaml_allowed_root_dirs():
    guard = _load_guard()
    yaml_text = (
        "allowed_root_dirs:\n"
        "  - plugins/\n"
        "  - docs/\n"
    )
    result = guard._parse_yaml(yaml_text)
    assert result["allowed_root_dirs"] == ["plugins/", "docs/"]


def test_parse_yaml_forbidden_patterns():
    guard = _load_guard()
    yaml_text = (
        "forbidden_patterns:\n"
        '  - "tmp_*"\n'
        '  - "*_v2.*"\n'
    )
    result = guard._parse_yaml(yaml_text)
    assert result["forbidden_patterns"] == ["tmp_*", "*_v2.*"]


def test_parse_yaml_plan_dirs():
    guard = _load_guard()
    yaml_text = (
        "plan_dirs:\n"
        "  - path: docs/superpowers/plans/\n"
        r'    pattern: "^\d{4}-\d{2}-\d{2}-.+\.md$"' + "\n"
    )
    result = guard._parse_yaml(yaml_text)
    assert len(result["plan_dirs"]) == 1
    assert result["plan_dirs"][0]["path"] == "docs/superpowers/plans/"
    assert r"\d{4}" in result["plan_dirs"][0]["pattern"]


# ── check_file ───────────────────────────────────────────────────────────────

def test_forbidden_tmp_prefix_blocked():
    guard = _load_guard()
    code, msg = guard.check_file("tmp_foo.txt", SAMPLE_CONFIG)
    assert code == 2
    assert "tmp_*" in msg


def test_forbidden_v2_suffix_blocked():
    guard = _load_guard()
    code, msg = guard.check_file("plugins/h2t-core/something_v2.py", SAMPLE_CONFIG)
    assert code == 2


def test_plan_dir_bad_name_blocked():
    guard = _load_guard()
    code, msg = guard.check_file("docs/superpowers/plans/foo.md", SAMPLE_CONFIG)
    assert code == 2
    assert "YYYY-MM-DD" in msg or "pattern" in msg.lower()


def test_plan_dir_good_name_allowed():
    guard = _load_guard()
    code, msg = guard.check_file("docs/superpowers/plans/2026-06-14-foo.md", SAMPLE_CONFIG)
    assert code == 0


def test_known_root_dir_allowed():
    guard = _load_guard()
    code, msg = guard.check_file("plugins/h2t-core/foo.py", SAMPLE_CONFIG)
    assert code == 0


def test_unknown_root_dir_blocks():
    guard = _load_guard()
    code, msg = guard.check_file("random_new_dir/foo.py", SAMPLE_CONFIG)
    assert code == 2
    assert "structure.yaml" in msg
    assert "random_new_dir" in msg or "allowlist" in msg.lower()


def test_no_config_returns_zero(tmp_path):
    guard = _load_guard()
    config = guard.load_config(tmp_path)
    assert config is None


def test_unknown_tool_name_returns_zero():
    guard = _load_guard()
    payload = {"tool_name": "Bash", "tool_input": {"command": "ls"}}
    assert guard._is_write_tool(payload["tool_name"]) is False


def test_write_tool_recognized():
    guard = _load_guard()
    for name in ("Write", "Edit", "MultiEdit"):
        assert guard._is_write_tool(name) is True


def test_load_config_and_check_file_integration(tmp_path):
    """End-to-end: write a real YAML file, load it, verify check_file uses it."""
    guard = _load_guard()
    yaml_content = (
        "allowed_root_dirs:\n"
        "  - plugins/\n"
        "  - docs/\n"
        "forbidden_patterns:\n"
        '  - "tmp_*"\n'
        "plan_dirs:\n"
        "  - path: docs/superpowers/plans/\n"
        '    pattern: "^\\d{4}-\\d{2}-\\d{2}-.+\\.md$"\n'
    )
    (tmp_path / ".h2t").mkdir()
    (tmp_path / ".h2t" / "structure.yaml").write_text(yaml_content, encoding="utf-8")

    config = guard.load_config(tmp_path)
    assert config is not None

    # Forbidden pattern from real file
    code, _ = guard.check_file("tmp_analysis.txt", config)
    assert code == 2

    # Good plan dir name from real file
    code, _ = guard.check_file("docs/superpowers/plans/2026-06-14-foo.md", config)
    assert code == 0

    # Bad plan dir name from real file
    code, _ = guard.check_file("docs/superpowers/plans/foo.md", config)
    assert code == 2


def test_h2t_structure_yaml_exists():
    repo_root = Path(__file__).parents[2]
    structure_yaml = repo_root / ".h2t" / "structure.yaml"
    assert structure_yaml.exists(), ".h2t/structure.yaml not found in repo root"


def test_h2t_structure_yaml_is_valid():
    guard = _load_guard()
    repo_root = Path(__file__).parents[2]
    config = guard.load_config(repo_root)
    assert config is not None
    assert "allowed_root_dirs" in config
    assert "forbidden_patterns" in config
    assert len(config["allowed_root_dirs"]) >= 4
    assert "tmp_*" in config["forbidden_patterns"]


def test_h2t_structure_yaml_blocks_tmp(tmp_path):
    guard = _load_guard()
    repo_root = Path(__file__).parents[2]
    config = guard.load_config(repo_root)
    code, _ = guard.check_file("tmp_foo.txt", config)
    assert code == 2


def test_h2t_structure_yaml_blocks_bad_plan_name(tmp_path):
    guard = _load_guard()
    repo_root = Path(__file__).parents[2]
    config = guard.load_config(repo_root)
    code, _ = guard.check_file("docs/superpowers/plans/my-plan.md", config)
    assert code == 2


def test_h2t_structure_yaml_allows_dated_plan():
    guard = _load_guard()
    repo_root = Path(__file__).parents[2]
    config = guard.load_config(repo_root)
    code, _ = guard.check_file("docs/superpowers/plans/2026-06-14-my-plan.md", config)
    assert code == 0


# ── frontmatter presence enforcement (#264 follow-up) ────────────────────────

FM_CONFIG = {
    "frontmatter_dirs": [
        "docs/superpowers/plans/",
        "docs/superpowers/specs/",
        "docs/adr/",
    ],
}


def test_has_frontmatter_true():
    guard = _load_guard()
    assert guard._has_frontmatter("---\ntitle: X\n---\n\n# X\n") is True


def test_has_frontmatter_false_no_block():
    guard = _load_guard()
    assert guard._has_frontmatter("# X\n\nsome body\n") is False


def test_has_frontmatter_false_no_closing():
    guard = _load_guard()
    assert guard._has_frontmatter("---\ntitle: X\n\n# body no close\n") is False


def test_has_frontmatter_true_with_bom():
    guard = _load_guard()
    assert guard._has_frontmatter("﻿---\ntitle: X\n---\n") is True


def test_plan_write_without_frontmatter_blocks():
    guard = _load_guard()
    code, msg = guard.check_frontmatter_presence(
        "docs/superpowers/plans/2026-07-08-foo.md", "# Foo\n\nbody\n", FM_CONFIG
    )
    assert code == 2
    assert "frontmatter" in msg.lower() or "docs-lint new" in msg


def test_plan_write_with_frontmatter_ok():
    guard = _load_guard()
    code, msg = guard.check_frontmatter_presence(
        "docs/superpowers/plans/2026-07-08-foo.md",
        "---\ntitle: Foo\nstatus: draft\ndate: 2026-07-08\nmilestone: \"\"\n---\n\n# Foo\n",
        FM_CONFIG,
    )
    assert code == 0


def test_spec_write_without_frontmatter_blocks():
    guard = _load_guard()
    code, _ = guard.check_frontmatter_presence(
        "docs/superpowers/specs/2026-07-08-bar.md", "# Bar\n", FM_CONFIG
    )
    assert code == 2


def test_adr_write_without_frontmatter_blocks():
    guard = _load_guard()
    code, _ = guard.check_frontmatter_presence(
        "docs/adr/0007-thing.md", "# Thing\n", FM_CONFIG
    )
    assert code == 2


def test_readme_in_frontmatter_dir_exempt():
    guard = _load_guard()
    code, _ = guard.check_frontmatter_presence(
        "docs/adr/README.md", "# ADR index\n", FM_CONFIG
    )
    assert code == 0


def test_index_in_frontmatter_dir_exempt():
    guard = _load_guard()
    code, _ = guard.check_frontmatter_presence(
        "docs/superpowers/plans/index.md", "# Plans\n", FM_CONFIG
    )
    assert code == 0


def test_non_markdown_not_checked():
    guard = _load_guard()
    code, _ = guard.check_frontmatter_presence(
        "docs/superpowers/plans/data.json", "{}", FM_CONFIG
    )
    assert code == 0


def test_path_outside_frontmatter_dirs_not_checked():
    guard = _load_guard()
    code, _ = guard.check_frontmatter_presence(
        "docs/reports/2026-07-08-report.md", "# Report\n", FM_CONFIG
    )
    assert code == 0


def test_frontmatter_check_no_config_key_returns_zero():
    guard = _load_guard()
    code, _ = guard.check_frontmatter_presence(
        "docs/superpowers/plans/2026-07-08-foo.md", "# Foo\n", {}
    )
    assert code == 0


def test_repo_structure_yaml_has_frontmatter_dirs():
    guard = _load_guard()
    repo_root = Path(__file__).parents[2]
    config = guard.load_config(repo_root)
    assert "frontmatter_dirs" in config
    assert "docs/superpowers/plans/" in config["frontmatter_dirs"]


def test_hooks_json_has_structure_guard_entry():
    import json as _json
    hooks_path = Path(__file__).parents[2] / "plugins" / "h2t-core" / "hooks" / "hooks.json"
    data = _json.loads(hooks_path.read_text(encoding="utf-8"))
    pre_tool = data.get("hooks", {}).get("PreToolUse", [])
    commands = [
        hook["command"]
        for entry in pre_tool
        for hook in entry.get("hooks", [])
        if hook.get("type") == "command"
    ]
    assert any("structure-guard" in cmd for cmd in commands), (
        f"structure-guard not found in PreToolUse hooks. Commands: {commands}"
    )


# ── warn → block: the two axes that actually produced the drift ──────────────


def test_main_exits_2_when_frontmatter_missing(tmp_path, monkeypatch, capsys):
    """main() must honour the frontmatter verdict — it used to discard the code."""
    guard = _load_guard()
    (tmp_path / ".h2t").mkdir()
    (tmp_path / ".h2t" / "structure.yaml").write_text(
        "allowed_root_dirs:\n  - docs/\n"
        "frontmatter_dirs:\n  - docs/superpowers/plans/\n"
    )
    target = tmp_path / "docs" / "superpowers" / "plans" / "2026-01-01-x.md"
    target.parent.mkdir(parents=True)
    monkeypatch.chdir(tmp_path)
    payload = {
        "tool_name": "Write",
        "tool_input": {"file_path": str(target), "content": "# X\n"},
    }
    monkeypatch.setattr(guard.sys, "stdin", io.StringIO(json.dumps(payload)))
    assert guard.main() == 2


def test_allowlist_covers_every_tracked_root_dir():
    """The allowlist blocks now, so a drifted list breaks legitimate writes.

    It had drifted six entries behind (.github, evals, tools, hooks,
    hooks-handlers, .claude-plugin) while the check was only a warning.
    """
    import subprocess
    guard = _load_guard()
    repo = Path(__file__).parents[2]
    tracked = subprocess.run(
        ["git", "ls-files"], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.splitlines()
    roots = {p.split("/")[0] for p in tracked if "/" in p}
    config = guard.load_config(repo)
    allowed = {a.rstrip("/") for a in config["allowed_root_dirs"]}
    assert not (roots - allowed), f"not in allowlist: {sorted(roots - allowed)}"


# --- docs/ deny-by-default ------------------------------------------------
#
# The root allowlist keeps the repo root at 14 deliberate directories. One level
# down there was no such rule, and docs/ grew twelve sections nobody planned:
# wireframes, library, protocols, visual-regression, agent-instructions,
# architecture, research, and a docs/plans/ next to docs/superpowers/plans/.
# Enumerating what an agent might invent is unwinnable; enumerating what is
# legitimate is a short, closed list — and existing directories need no listing
# at all, because their existence is the evidence.

_DOCS_CFG = {
    "allowed_root_dirs": ["docs/", "plugins/"],
    "allowed_doc_dirs": ["superpowers/", "adr/", "reports/", "archive/"],
}


def test_canonical_doc_section_is_allowed(tmp_path):
    code, _ = _load_guard().check_file("docs/superpowers/specs/2026-08-24-x.md", _DOCS_CFG, tmp_path)
    assert code == 0


def test_new_doc_section_is_blocked(tmp_path):
    code, msg = _load_guard().check_file("docs/wireframes/sketch.md", _DOCS_CFG, tmp_path)
    assert code == 2
    assert "wireframes" in msg


def test_existing_doc_section_is_allowed_without_being_listed(tmp_path):
    """A section that already holds a document is grandfathered by holding it."""
    (tmp_path / "docs" / "wireframes").mkdir(parents=True)
    (tmp_path / "docs" / "wireframes" / "README.md").write_text("x", encoding="utf-8")
    code, _ = _load_guard().check_file("docs/wireframes/sketch.md", _DOCS_CFG, tmp_path)
    assert code == 0


def test_nested_dir_inside_an_existing_section_is_allowed(tmp_path):
    """Only the first level is governed — dated subdirs are normal inside a section."""
    (tmp_path / "docs" / "visual-regression" / "2026-05-03").mkdir(parents=True)
    (tmp_path / "docs" / "visual-regression" / "2026-05-03" / "x.md").write_text(
        "x", encoding="utf-8"
    )
    code, _ = _load_guard().check_file("docs/visual-regression/2026-09-01/checklist.md", _DOCS_CFG, tmp_path)
    assert code == 0


def test_new_loose_file_at_docs_root_is_blocked(tmp_path):
    code, msg = _load_guard().check_file("docs/notes.md", _DOCS_CFG, tmp_path)
    assert code == 2
    assert "секц" in msg.lower()


def test_existing_loose_file_at_docs_root_stays_editable(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "h2t-ops-roadmap.md").write_text("x", encoding="utf-8")
    code, _ = _load_guard().check_file("docs/h2t-ops-roadmap.md", _DOCS_CFG, tmp_path)
    assert code == 0


def test_docs_readme_is_always_allowed(tmp_path):
    """The index is generated by docs-index into a repo that may not have it yet."""
    code, _ = _load_guard().check_file("docs/README.md", _DOCS_CFG, tmp_path)
    assert code == 0


def test_rule_is_off_when_allowed_doc_dirs_is_absent(tmp_path):
    """Other repos carry a structure.yaml without the key — they must not break."""
    code, _ = _load_guard().check_file("docs/anything/x.md", {"allowed_root_dirs": ["docs/"]}, tmp_path)
    assert code == 0


def test_empty_dir_does_not_grandfather_a_new_section(tmp_path):
    """`mkdir docs/kb` must not be the way past the rule.

    Grandfathering reads an existing section as evidence that somebody meant it.
    An empty directory is no evidence: it is created by the very write it would
    authorise, and `mkdir -p` before a write is a reflex, not a decision.
    """
    (tmp_path / "docs" / "kb").mkdir(parents=True)
    code, msg = _load_guard().check_file("docs/kb/index.md", _DOCS_CFG, tmp_path)
    assert code == 2
    assert "kb" in msg


def test_section_with_a_file_still_grandfathers(tmp_path):
    (tmp_path / "docs" / "kb").mkdir(parents=True)
    (tmp_path / "docs" / "kb" / "existing.md").write_text("x", encoding="utf-8")
    code, _ = _load_guard().check_file("docs/kb/another.md", _DOCS_CFG, tmp_path)
    assert code == 0


def test_file_nested_deeper_also_grandfathers_the_section(tmp_path):
    """docs/visual-regression/ holds only dated subdirectories, no loose file."""
    (tmp_path / "docs" / "vr" / "2026-05-03").mkdir(parents=True)
    (tmp_path / "docs" / "vr" / "2026-05-03" / "checklist.md").write_text("x", encoding="utf-8")
    code, _ = _load_guard().check_file("docs/vr/2026-09-01/checklist.md", _DOCS_CFG, tmp_path)
    assert code == 0
