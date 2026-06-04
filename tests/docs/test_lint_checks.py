"""Unit tests for docs-lint check functions."""
import sys
from pathlib import Path

# Make lint.py importable
_LINT_DIR = Path(__file__).parents[2] / "plugins/h2t-dev/skills/docs-lint/scripts"
sys.path.insert(0, str(_LINT_DIR))
_LIB = Path(__file__).parents[2] / "plugins/h2t-dev/lib"
sys.path.insert(0, str(_LIB))

from lint import check_legacy_dirs


def test_check_legacy_dirs_clean(tmp_path):
    """No legacy dirs → no failures."""
    (tmp_path / "docs" / "superpowers" / "specs").mkdir(parents=True)
    assert check_legacy_dirs(tmp_path) == []


def test_check_legacy_dirs_plans(tmp_path):
    """docs/plans/ present → failure."""
    (tmp_path / "docs" / "plans").mkdir(parents=True)
    result = check_legacy_dirs(tmp_path)
    assert any("docs/plans" in f for f in result)


def test_check_legacy_dirs_specs(tmp_path):
    """docs/specs/ present → failure."""
    (tmp_path / "docs" / "specs").mkdir(parents=True)
    result = check_legacy_dirs(tmp_path)
    assert any("docs/specs" in f for f in result)


def test_check_legacy_dirs_handoff(tmp_path):
    """docs/handoff/ present → failure."""
    (tmp_path / "docs" / "handoff").mkdir(parents=True)
    result = check_legacy_dirs(tmp_path)
    assert any("handoff" in f for f in result)


def test_check_legacy_dirs_eval(tmp_path):
    """docs/eval/ present → failure."""
    (tmp_path / "docs" / "eval").mkdir(parents=True)
    result = check_legacy_dirs(tmp_path)
    assert any("eval" in f for f in result)


def test_check_legacy_dirs_skips_whitelisted(tmp_path):
    """Dir in extra_dirs whitelist is not flagged."""
    (tmp_path / "docs" / "eval").mkdir(parents=True)
    result = check_legacy_dirs(tmp_path, extra_dirs=["eval"])
    assert result == []


def test_check_legacy_dirs_handoffs_plural(tmp_path):
    """docs/handoffs/ (plural) present → failure."""
    (tmp_path / "docs" / "handoffs").mkdir(parents=True)
    result = check_legacy_dirs(tmp_path)
    assert any("handoffs" in f for f in result)


from lint import check_naming_conventions


def test_naming_clean(tmp_path):
    """Dated specs and plans → no failures."""
    specs = tmp_path / "docs" / "superpowers" / "specs"
    specs.mkdir(parents=True)
    (specs / "2026-05-27-my-feature-design.md").write_text("# x")
    plans = tmp_path / "docs" / "superpowers" / "plans"
    plans.mkdir(parents=True)
    (plans / "2026-05-27-my-feature-plan.md").write_text("# x")
    assert check_naming_conventions(tmp_path) == []


def test_naming_spec_missing_date(tmp_path):
    """Spec without date prefix → failure."""
    specs = tmp_path / "docs" / "superpowers" / "specs"
    specs.mkdir(parents=True)
    (specs / "my-feature-design.md").write_text("# x")
    result = check_naming_conventions(tmp_path)
    assert any("my-feature-design.md" in f for f in result)


def test_naming_plan_missing_date(tmp_path):
    """Plan without date prefix → failure."""
    plans = tmp_path / "docs" / "superpowers" / "plans"
    plans.mkdir(parents=True)
    (plans / "my-feature-plan.md").write_text("# x")
    result = check_naming_conventions(tmp_path)
    assert any("my-feature-plan.md" in f for f in result)


def test_naming_readme_ignored(tmp_path):
    """README.md in specs dir → not flagged."""
    specs = tmp_path / "docs" / "superpowers" / "specs"
    specs.mkdir(parents=True)
    (specs / "README.md").write_text("# index")
    assert check_naming_conventions(tmp_path) == []


from lint import check_repo_root


def test_repo_root_clean(tmp_path):
    """Minimal clean root → no failures."""
    for name in ["README.md", "pyproject.toml", ".gitignore", "CLAUDE.md"]:
        (tmp_path / name).write_text("")
    for d in ["src", "tests", "docs", "scripts"]:
        (tmp_path / d).mkdir()
    assert check_repo_root(tmp_path) == []


def test_repo_root_temp_dir(tmp_path):
    """temp/ in root → failure."""
    (tmp_path / "temp").mkdir()
    result = check_repo_root(tmp_path)
    assert any("temp" in f for f in result)


def test_repo_root_old_dir(tmp_path):
    """old/ in root → failure."""
    (tmp_path / "old").mkdir()
    result = check_repo_root(tmp_path)
    assert any("old" in f for f in result)


def test_repo_root_backup_dir(tmp_path):
    """backup/ in root → failure."""
    (tmp_path / "backup").mkdir()
    result = check_repo_root(tmp_path)
    assert any("backup" in f for f in result)


def test_repo_root_too_many_items(tmp_path):
    """More than 12 items in root → failure."""
    for i in range(13):
        (tmp_path / f"item_{i}.txt").write_text("")
    result = check_repo_root(tmp_path)
    assert any("root has" in f for f in result)


from lint import check_data_docs_boundary


def test_data_docs_boundary_clean(tmp_path):
    """Markdown in docs/, JSON in data/ → no failures."""
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "README.md").write_text("# x")
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "registry.json").write_text("{}")
    assert check_data_docs_boundary(tmp_path) == []


def test_json_in_docs(tmp_path):
    """JSON file in docs/ → failure."""
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "data.json").write_text("{}")
    result = check_data_docs_boundary(tmp_path)
    assert any("data.json" in f for f in result)


def test_yaml_in_docs(tmp_path):
    """YAML file in docs/ → failure."""
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "config.yaml").write_text("key: value")
    result = check_data_docs_boundary(tmp_path)
    assert any("config.yaml" in f for f in result)


def test_markdown_in_data(tmp_path):
    """Markdown file in data/ → failure."""
    data = tmp_path / "data"
    data.mkdir()
    (data / "notes.md").write_text("# notes")
    result = check_data_docs_boundary(tmp_path)
    assert any("notes.md" in f for f in result)


def test_data_docs_boundary_no_dirs(tmp_path):
    """No docs/ or data/ dirs → no failures."""
    assert check_data_docs_boundary(tmp_path) == []


def test_data_docs_boundary_readme_in_data_not_flagged(tmp_path):
    """README.md in data/ is a directory index, not a misplaced doc — should not be flagged."""
    data = tmp_path / "data"
    data.mkdir()
    (data / "README.md").write_text("# Data\n")
    result = check_data_docs_boundary(tmp_path)
    assert result == [], f"README.md in data/ should not be flagged, got: {result}"


def test_legacy_main_unknown_repo_uses_cwd_not_all_repos(tmp_path, monkeypatch):
    """When called without args from an unknown repo, must NOT fall back to all 16 repos."""
    import argparse
    import lint as _lint

    audit_calls = []

    def fake_run_audit(rp, **kwargs):
        audit_calls.append(rp)

    monkeypatch.setattr(_lint, "_run_audit", fake_run_audit)
    monkeypatch.chdir(tmp_path)

    args = argparse.Namespace(
        repos=[],
        all=False,
        fix=False,
        fix_frontmatter=False,
        fix_labels=False,
        no_pymarkdown=False,
        repo_root=False,
        root=None,
    )
    _lint._legacy_main(args)

    assert len(audit_calls) == 1
    assert audit_calls[0] == tmp_path.resolve()


import subprocess
from unittest.mock import patch, MagicMock
from lint import fix_labels


def test_fix_labels_calls_sync(tmp_path):
    """fix_labels runs sync_labels.py for the given repo."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="synced 3", stderr="")
        result = fix_labels(tmp_path, "h2t-skills")
    mock_run.assert_called_once()
    cmd = mock_run.call_args[0][0]
    assert "sync_labels.py" in " ".join(str(c) for c in cmd)


def test_fix_labels_returns_message(tmp_path):
    """fix_labels returns a non-empty message on success."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="synced 3", stderr="")
        result = fix_labels(tmp_path, "h2t-skills")
    assert result != ""


def test_fix_labels_failure_message(tmp_path):
    """fix_labels returns error message on sync failure."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="repo not found")
        result = fix_labels(tmp_path, "h2t-unknown")
    assert "failed" in result.lower() or "label sync" in result.lower()


# --- Backward compatibility ---

import subprocess as _sp
import sys as _sys

_LINT_SCRIPT = str(
    Path(__file__).parents[2]
    / "plugins/h2t-dev/skills/docs-lint/scripts/lint.py"
)


def test_legacy_fix_with_root_is_rejected(tmp_path):
    """--fix combined with --root is rejected (ambiguous target). Exits non-zero."""
    result = _sp.run(
        [_sys.executable, _LINT_SCRIPT, "--root", str(tmp_path), "--fix"],
        capture_output=True, text=True,
    )
    assert result.returncode != 0
    assert "--root" in result.stderr or "incompatible" in result.stderr.lower()


def test_new_audit_subcommand_exits_cleanly(tmp_path):
    """audit subcommand with --root on empty repo exits without crash."""
    result = _sp.run(
        [_sys.executable, _LINT_SCRIPT, "audit", "--root", str(tmp_path)],
        capture_output=True, text=True,
    )
    assert result.returncode in (0, 1)


def test_doctor_json_produces_schema(tmp_path):
    """doctor --json outputs valid h2t_lifecycle_report/v0.1 schema."""
    import json as _json
    result = _sp.run(
        [_sys.executable, _LINT_SCRIPT, "doctor", "--root", str(tmp_path), "--json"],
        capture_output=True, text=True,
    )
    assert result.returncode in (0, 1)
    data = _json.loads(result.stdout)
    assert data["schema"] == "h2t_lifecycle_report/v0.1"


def test_fix_index_dry_run_no_file_created(tmp_path):
    """fix-index without --apply does not create README.md."""
    (tmp_path / "docs").mkdir()
    result = _sp.run(
        [_sys.executable, _LINT_SCRIPT, "fix-index", "--root", str(tmp_path)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert not (tmp_path / "docs" / "README.md").exists()


def test_fix_safe_preserves_existing_frontmatter_keys(tmp_path):
    """fix-safe does not drop custom/unknown frontmatter keys when adding missing required ones."""
    specs = tmp_path / "docs" / "superpowers" / "specs"
    specs.mkdir(parents=True)
    md = specs / "2026-05-28-test-spec.md"
    md.write_text(
        '---\ntitle: "My Spec"\ncustom_tag: "keep-me"\n---\n# Content\n'
    )
    _sp.run(
        [_sys.executable, _LINT_SCRIPT, "fix-safe", "--root", str(tmp_path),
         "--only", "frontmatter"],
        capture_output=True, text=True,
    )
    result = md.read_text(encoding="utf-8")
    assert 'custom_tag: "keep-me"' in result
    assert "status:" in result


def test_fix_safe_moves_tracked_html(tmp_path, monkeypatch):
    """fix-safe with project_checks=true moves tracked HTML via git mv."""
    import lint
    from unittest.mock import patch, MagicMock
    from pathlib import Path

    (tmp_path / ".claude" / "rules").mkdir(parents=True)
    (tmp_path / ".claude" / "rules" / "docs-lint.yaml").write_text(
        "schema: h2t_docs_lint_config/v0.2\nproject_checks: true\n"
    )
    (tmp_path / "docs" / "research").mkdir(parents=True)
    html = tmp_path / "docs" / "research" / "deck.html"
    html.write_text("<html/>")
    (tmp_path / "deliverables").mkdir()
    dst = tmp_path / "deliverables" / "deck.html"

    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        if isinstance(cmd, list) and len(cmd) >= 4 and cmd[0] == "git" and cmd[1] == "mv":
            src = Path(cmd[2])
            dst_p = Path(cmd[3])
            dst_p.write_bytes(src.read_bytes())
            src.unlink()
        m = MagicMock()
        m.returncode = 0
        m.stderr = ""
        return m

    with patch("docs.misplaced_files._is_tracked", return_value=True):
        with patch("subprocess.run", side_effect=fake_run):
            lint._run_fix_safe(tmp_path, only="all")

    assert dst.exists()
    assert not html.exists()


from lint import check_project_structure_typed


def test_check_typed_code_repo_missing_src(tmp_path):
    result = check_project_structure_typed(tmp_path, "code_repo")
    assert any("src" in m for m in result), result


def test_check_typed_code_repo_all_present(tmp_path):
    for d in ["src", "tests", "docs", "scripts"]:
        (tmp_path / d).mkdir()
    assert check_project_structure_typed(tmp_path, "code_repo") == []


def test_check_typed_client_project_missing_deliverables(tmp_path):
    for d in ["docs", "data", "scripts"]:
        (tmp_path / d).mkdir()
    result = check_project_structure_typed(tmp_path, "client_project")
    assert any("deliverables" in m for m in result), result


def test_check_typed_unknown_template_returns_empty(tmp_path):
    assert check_project_structure_typed(tmp_path, "nonexistent_type") == []


def test_check_typed_research_project_missing_docs_subdir(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "data").mkdir()
    result = check_project_structure_typed(tmp_path, "research_project")
    assert any("docs/research" in m for m in result), result


def test_check_typed_research_project_fully_present(tmp_path):
    for d in ["docs", "data", "docs/research"]:
        (tmp_path / d).mkdir(parents=True)
    assert check_project_structure_typed(tmp_path, "research_project") == []


def test_check_typed_creative_project_missing_assets(tmp_path):
    result = check_project_structure_typed(tmp_path, "creative_project")
    assert any("assets" in m for m in result), result


def test_check_typed_messages_include_template_name(tmp_path):
    result = check_project_structure_typed(tmp_path, "code_repo")
    assert all("code_repo" in m for m in result), result


def test_check_typed_file_at_dir_path_is_collision(tmp_path):
    """A file occupying a required dir path → 'not a dir' message, not 'missing'."""
    (tmp_path / "src").write_text("oops")  # file, not dir
    result = check_project_structure_typed(tmp_path, "code_repo")
    src_msgs = [m for m in result if "src" in m]
    assert any("not a dir" in m for m in src_msgs), src_msgs


import lint as _lint_module


def test_collect_findings_no_typed_check_without_template(tmp_path):
    """Without docs-lint.yaml, no typed findings appear."""
    findings = _lint_module._collect_all_findings(tmp_path, no_pymarkdown=True)
    typed = [f for f in findings if f.get("template")]
    assert typed == []


def test_collect_findings_typed_check_fires_when_template_set(tmp_path):
    """template: code_repo in yaml → missing src/ appears as a typed structure finding."""
    (tmp_path / ".claude" / "rules").mkdir(parents=True)
    (tmp_path / ".claude" / "rules" / "docs-lint.yaml").write_text(
        "schema: h2t_docs_lint_config/v0.1\ntemplate: code_repo\n",
        encoding="utf-8",
    )
    findings = _lint_module._collect_all_findings(tmp_path, no_pymarkdown=True)
    typed = [f for f in findings if f.get("template") == "code_repo"]
    assert any("src" in f["message"] for f in typed), [f["message"] for f in typed]


def test_collect_findings_typed_check_has_template_field(tmp_path):
    """Typed findings have 'template' key set — machine-readable, not just in message."""
    (tmp_path / ".claude" / "rules").mkdir(parents=True)
    (tmp_path / ".claude" / "rules" / "docs-lint.yaml").write_text(
        "schema: h2t_docs_lint_config/v0.1\ntemplate: code_repo\n",
        encoding="utf-8",
    )
    findings = _lint_module._collect_all_findings(tmp_path, no_pymarkdown=True)
    typed = [f for f in findings if f.get("template")]
    assert typed, "expected at least one typed finding"
    for f in typed:
        assert f["template"] == "code_repo"


def test_collect_findings_typed_check_silent_when_all_present(tmp_path):
    """code_repo with all root_dirs present → no typed findings."""
    (tmp_path / ".claude" / "rules").mkdir(parents=True)
    (tmp_path / ".claude" / "rules" / "docs-lint.yaml").write_text(
        "schema: h2t_docs_lint_config/v0.1\ntemplate: code_repo\n",
        encoding="utf-8",
    )
    for d in ["src", "tests", "docs", "scripts"]:
        (tmp_path / d).mkdir()
    findings = _lint_module._collect_all_findings(tmp_path, no_pymarkdown=True)
    typed = [f for f in findings if f.get("template") == "code_repo"]
    assert typed == []


def test_collect_findings_unknown_template_no_crash(tmp_path):
    """template: nonexistent_type in yaml → no typed findings, no exception."""
    (tmp_path / ".claude" / "rules").mkdir(parents=True)
    (tmp_path / ".claude" / "rules" / "docs-lint.yaml").write_text(
        "schema: h2t_docs_lint_config/v0.1\ntemplate: nonexistent_type\n",
        encoding="utf-8",
    )
    findings = _lint_module._collect_all_findings(tmp_path, no_pymarkdown=True)
    typed = [f for f in findings if f.get("template")]
    assert typed == []


import json as _json_module
import subprocess as _subprocess

from lint import fix_structure


def test_fix_structure_creates_typed_dirs_for_code_repo(tmp_path):
    """fix_structure creates root_dirs from PROJECT_TYPES when template is set."""
    (tmp_path / ".claude" / "rules").mkdir(parents=True)
    (tmp_path / ".claude" / "rules" / "docs-lint.yaml").write_text(
        "schema: h2t_docs_lint_config/v0.1\ntemplate: code_repo\n",
        encoding="utf-8",
    )
    fixes = fix_structure(tmp_path)
    assert (tmp_path / "src").is_dir()
    assert (tmp_path / "tests").is_dir()
    assert any("src" in f for f in fixes), fixes


def test_fix_structure_noop_without_template(tmp_path):
    """fix_structure without template creates only REQUIRED_CORE_DIRS, no typed dirs."""
    fixes = fix_structure(tmp_path)
    assert not any("template:" in f for f in fixes), fixes


def test_fix_structure_noop_unknown_template(tmp_path):
    """fix_structure with unknown template doesn't crash, creates no typed dirs."""
    (tmp_path / ".claude" / "rules").mkdir(parents=True)
    (tmp_path / ".claude" / "rules" / "docs-lint.yaml").write_text(
        "schema: h2t_docs_lint_config/v0.1\ntemplate: nonexistent_type\n",
        encoding="utf-8",
    )
    fixes = fix_structure(tmp_path)
    assert not any("template:" in f for f in fixes), fixes


def test_fix_structure_does_not_move_existing_files(tmp_path):
    """fix_structure never moves or deletes files — even in wrong-location dirs."""
    (tmp_path / ".claude" / "rules").mkdir(parents=True)
    (tmp_path / ".claude" / "rules" / "docs-lint.yaml").write_text(
        "schema: h2t_docs_lint_config/v0.1\ntemplate: code_repo\n",
        encoding="utf-8",
    )
    # Pre-create a file at an unexpected location
    old_dir = tmp_path / "old_scripts"
    old_dir.mkdir()
    sentinel = old_dir / "important.py"
    sentinel.write_text("# do not touch", encoding="utf-8")
    fix_structure(tmp_path)
    # File must still be exactly where it was
    assert sentinel.exists()
    assert sentinel.read_text(encoding="utf-8") == "# do not touch"
    assert (tmp_path / "old_scripts").is_dir()


def test_fix_structure_creates_parents_for_docs_dirs(tmp_path):
    """fix_structure creates parent dirs recursively for docs_dirs like docs/research."""
    (tmp_path / ".claude" / "rules").mkdir(parents=True)
    (tmp_path / ".claude" / "rules" / "docs-lint.yaml").write_text(
        "schema: h2t_docs_lint_config/v0.1\ntemplate: research_project\n",
        encoding="utf-8",
    )
    fix_structure(tmp_path)
    assert (tmp_path / "docs" / "research").is_dir()


def test_doctor_json_output_schema(tmp_path):
    """docs-lint doctor --json produces h2t_lifecycle_report/v0.1 with expected keys."""
    import sys as _sys
    lint_script = getattr(_lint_module, "__file__", None)
    if lint_script is None:
        return  # skip if can't find script
    result = _subprocess.run(
        [_sys.executable, lint_script, "doctor", "--root", str(tmp_path),
         "--json", "--no-pymarkdown"],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert result.returncode == 0, result.stderr
    data = _json_module.loads(result.stdout)
    assert data["schema"] == "h2t_lifecycle_report/v0.1"
    assert "status" in data
    assert isinstance(data["findings"], list)


def test_doctor_json_typed_finding_has_template_field(tmp_path):
    """doctor --json with template: code_repo → typed findings have 'template' key."""
    import sys as _sys
    (tmp_path / ".claude" / "rules").mkdir(parents=True)
    (tmp_path / ".claude" / "rules" / "docs-lint.yaml").write_text(
        "schema: h2t_docs_lint_config/v0.1\ntemplate: code_repo\n",
        encoding="utf-8",
    )
    lint_script = getattr(_lint_module, "__file__", None)
    if lint_script is None:
        return
    result = _subprocess.run(
        [_sys.executable, lint_script, "doctor", "--root", str(tmp_path),
         "--json", "--no-pymarkdown"],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert result.returncode == 0, result.stderr
    data = _json_module.loads(result.stdout)
    typed = [f for f in data["findings"] if f.get("template")]
    assert typed, "expected at least one typed finding in doctor JSON output"
    for f in typed:
        assert f["template"] == "code_repo"


def test_exclude_dirs_suppresses_orphan_findings(tmp_path):
    """Files under excluded dirs don't appear as orphans."""
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "README.md").write_text("# Docs\n", encoding="utf-8")
    (tmp_path / "docs" / "superpowers").mkdir()
    (tmp_path / "docs" / "superpowers" / "plan.md").write_text(
        "# Plan\n", encoding="utf-8"
    )
    (tmp_path / ".claude" / "rules").mkdir(parents=True)
    (tmp_path / ".claude" / "rules" / "docs-lint.yaml").write_text(
        "schema: h2t_docs_lint_config/v0.1\nexclude_dirs:\n  - docs/superpowers\n",
        encoding="utf-8",
    )
    findings = _lint_module._collect_all_findings(tmp_path, no_pymarkdown=True)
    orphan_paths = [f["path"] for f in findings if f["type"] == "orphan"]
    assert not any("superpowers" in p for p in orphan_paths), orphan_paths


def test_exclude_dirs_suppresses_naming_findings(tmp_path):
    """Files under excluded dirs don't get naming-convention findings."""
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "README.md").write_text("# Docs\n", encoding="utf-8")
    (tmp_path / "docs" / "superpowers" / "plans").mkdir(parents=True)
    # Filename without date prefix — would normally trigger naming finding
    (tmp_path / "docs" / "superpowers" / "plans" / "my-log.md").write_text(
        "# Log\n", encoding="utf-8"
    )
    (tmp_path / ".claude" / "rules").mkdir(parents=True)
    (tmp_path / ".claude" / "rules" / "docs-lint.yaml").write_text(
        "schema: h2t_docs_lint_config/v0.1\nexclude_dirs:\n  - docs/superpowers\n",
        encoding="utf-8",
    )
    findings = _lint_module._collect_all_findings(tmp_path, no_pymarkdown=True)
    naming_paths = [f["path"] for f in findings if f["type"] == "naming"]
    assert not any("superpowers" in p for p in naming_paths), naming_paths


def test_exclude_dirs_empty_list_changes_nothing(tmp_path):
    """exclude_dirs: [] (default) does not suppress any findings."""
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "README.md").write_text("# Docs\n", encoding="utf-8")
    (tmp_path / "docs" / "superpowers" / "plans").mkdir(parents=True)
    (tmp_path / "docs" / "superpowers" / "plans" / "my-log.md").write_text(
        "# Log\n", encoding="utf-8"
    )
    # No docs-lint.yaml → exclude_dirs defaults to []
    findings = _lint_module._collect_all_findings(tmp_path, no_pymarkdown=True)
    naming_paths = [f["path"] for f in findings if f["type"] == "naming"]
    assert any("superpowers" in p for p in naming_paths), "expected naming finding without exclusion"


def test_naming_exceptions_suppresses_date_prefix_finding(tmp_path):
    """Files listed in naming_exceptions skip the date-prefix check."""
    (tmp_path / "docs" / "superpowers" / "plans").mkdir(parents=True)
    (tmp_path / "docs" / "README.md").write_text("# Docs\n", encoding="utf-8")
    living_log = tmp_path / "docs" / "superpowers" / "plans" / "my-log.md"
    living_log.write_text("# Living log\n", encoding="utf-8")
    (tmp_path / ".claude" / "rules").mkdir(parents=True)
    (tmp_path / ".claude" / "rules" / "docs-lint.yaml").write_text(
        "schema: h2t_docs_lint_config/v0.1\n"
        "naming_exceptions:\n"
        "  - docs/superpowers/plans/my-log.md\n",
        encoding="utf-8",
    )
    findings = _lint_module._collect_all_findings(tmp_path, no_pymarkdown=True)
    naming = [f for f in findings if f["type"] == "naming" and "my-log" in f["path"]]
    assert naming == [], f"expected no naming finding for excepted file, got: {naming}"


def test_naming_exceptions_glob_pattern(tmp_path):
    """naming_exceptions supports fnmatch glob patterns."""
    (tmp_path / "docs" / "superpowers" / "plans").mkdir(parents=True)
    (tmp_path / "docs" / "README.md").write_text("# Docs\n", encoding="utf-8")
    (tmp_path / "docs" / "superpowers" / "plans" / "skill-log.md").write_text(
        "# Log\n", encoding="utf-8"
    )
    (tmp_path / ".claude" / "rules").mkdir(parents=True)
    (tmp_path / ".claude" / "rules" / "docs-lint.yaml").write_text(
        "schema: h2t_docs_lint_config/v0.1\n"
        "naming_exceptions:\n"
        "  - docs/superpowers/plans/*-log.md\n",
        encoding="utf-8",
    )
    findings = _lint_module._collect_all_findings(tmp_path, no_pymarkdown=True)
    naming = [f for f in findings if f["type"] == "naming" and "skill-log" in f["path"]]
    assert naming == [], f"expected glob pattern to suppress finding, got: {naming}"


def test_naming_exceptions_empty_list_changes_nothing(tmp_path):
    """naming_exceptions: [] (default) still enforces date prefix."""
    (tmp_path / "docs" / "superpowers" / "plans").mkdir(parents=True)
    (tmp_path / "docs" / "README.md").write_text("# Docs\n", encoding="utf-8")
    (tmp_path / "docs" / "superpowers" / "plans" / "my-log.md").write_text(
        "# Log\n", encoding="utf-8"
    )
    # No docs-lint.yaml → no exceptions
    findings = _lint_module._collect_all_findings(tmp_path, no_pymarkdown=True)
    naming = [f for f in findings if f["type"] == "naming" and "my-log" in f["path"]]
    assert naming, "expected naming finding without exception config"


def test_check_repo_root_excludes_gitignored_files(tmp_path):
    """Root item count uses git-tracked files, not raw filesystem count."""
    import subprocess as _sp
    # Init a git repo
    _sp.run(["git", "init", str(tmp_path)], capture_output=True)
    _sp.run(["git", "-C", str(tmp_path), "config", "user.email", "test@test.com"], capture_output=True)
    _sp.run(["git", "-C", str(tmp_path), "config", "user.name", "Test"], capture_output=True)
    # Create 8 tracked files
    for name in ["README.md", "CLAUDE.md", "a.md", "b.md", "c.md", "d.md", "e.md", "f.md"]:
        (tmp_path / name).write_text("x", encoding="utf-8")
        _sp.run(["git", "-C", str(tmp_path), "add", name], capture_output=True)
    _sp.run(["git", "-C", str(tmp_path), "commit", "-m", "init"], capture_output=True)
    # Create 10 gitignored temp files that push filesystem count above limit
    (tmp_path / ".gitignore").write_text("*.tmp\n", encoding="utf-8")
    for i in range(10):
        (tmp_path / f"temp_{i}.tmp").write_text("x", encoding="utf-8")
    # Should not trigger "root has N items" since tracked count is 8 (< 12)
    from lint import check_repo_root
    result = check_repo_root(tmp_path)
    count_msgs = [m for m in result if "items (max" in m]
    assert count_msgs == [], f"expected no count warning, got: {count_msgs}"


def test_check_repo_root_fallback_without_git(tmp_path):
    """Outside a git repo, check_repo_root falls back to filesystem count (no crash)."""
    from lint import check_repo_root
    # tmp_path is not a git repo — should not raise
    result = check_repo_root(tmp_path)
    # Result is a list (possibly empty), no exception
    assert isinstance(result, list)


# --- Project layer integration ---

def test_project_layer_disabled_by_default(tmp_path):
    """Without project_checks: true, no project-layer findings appear."""
    (tmp_path / "mystery-tool").mkdir()
    findings = _lint_module._collect_all_findings(tmp_path, no_pymarkdown=True)
    project = [f for f in findings if f["type"] in {
        "root_structure", "root_readmes", "gitignore_hygiene", "agent_instructions"
    }]
    assert project == [], f"Project layer should be off by default: {project}"


def test_project_layer_enabled_when_config_set(tmp_path):
    """project_checks: true in docs-lint.yaml enables project-layer findings."""
    (tmp_path / ".claude" / "rules").mkdir(parents=True)
    (tmp_path / ".claude" / "rules" / "docs-lint.yaml").write_text(
        "project_checks: true\n"
    )
    (tmp_path / "mystery-tool").mkdir()
    findings = _lint_module._collect_all_findings(tmp_path, no_pymarkdown=True)
    project = [f for f in findings if f["type"] == "root_structure"]
    assert project, "Expected root_structure finding for unknown dir"


def test_custom_root_dirs_respected_in_collect(tmp_path):
    """custom_root_dirs in config suppress root_structure findings for listed items."""
    (tmp_path / ".claude" / "rules").mkdir(parents=True)
    (tmp_path / ".claude" / "rules" / "docs-lint.yaml").write_text(
        "project_checks: true\ncustom_root_dirs:\n  - my-tool\n"
    )
    (tmp_path / "my-tool").mkdir()
    findings = _lint_module._collect_all_findings(tmp_path, no_pymarkdown=True)
    project = [f for f in findings if f["type"] == "root_structure"]
    assert project == [], f"my-tool should be allowed via custom_root_dirs: {project}"


def test_gitignore_hygiene_finding_in_collect(tmp_path):
    """Temp file at root with project_checks: true → gitignore_hygiene finding."""
    (tmp_path / ".claude" / "rules").mkdir(parents=True)
    (tmp_path / ".claude" / "rules" / "docs-lint.yaml").write_text(
        "project_checks: true\n"
    )
    (tmp_path / "scratch.tmp").write_text("")
    findings = _lint_module._collect_all_findings(tmp_path, no_pymarkdown=True)
    gi = [f for f in findings if f["type"] == "gitignore_hygiene"]
    assert gi, "Expected gitignore_hygiene finding for unignored .tmp file"


def test_agent_instructions_finding_in_collect(tmp_path):
    """Missing .claude/rules/documentation.md with project_checks: true → agent_instructions finding."""
    (tmp_path / ".claude" / "rules").mkdir(parents=True)
    (tmp_path / ".claude" / "rules" / "docs-lint.yaml").write_text(
        "project_checks: true\n"
    )
    findings = _lint_module._collect_all_findings(tmp_path, no_pymarkdown=True)
    ai = [f for f in findings if f["type"] == "agent_instructions"]
    assert ai, "Expected agent_instructions finding for missing required rules files"


def test_fix_safe_cli_adds_gitignore_patterns_when_project_checks_enabled(tmp_path):
    """fix-safe CLI with project_checks: true adds missing temp patterns to .gitignore."""
    import sys as _sys
    import subprocess as _sp3
    (tmp_path / ".claude" / "rules").mkdir(parents=True)
    (tmp_path / ".claude" / "rules" / "docs-lint.yaml").write_text(
        "project_checks: true\n"
    )
    (tmp_path / "scratch.tmp").write_text("")
    lint_script = getattr(_lint_module, "__file__", None)
    if lint_script is None:
        return
    result = _sp3.run(
        [_sys.executable, lint_script, "fix-safe", "--root", str(tmp_path)],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert result.returncode == 0, f"fix-safe should exit 0, got: {result.returncode}. stderr: {result.stderr}"
    assert (tmp_path / ".gitignore").exists(), ".gitignore should be created by fix-safe"
    content = (tmp_path / ".gitignore").read_text()
    assert "*.tmp" in content, ".gitignore should contain *.tmp pattern"


def test_doctor_json_summary_includes_project_count(tmp_path):
    """doctor --json summary string includes project issue count when project_checks enabled."""
    import json as _json
    import sys as _sys
    import subprocess as _sp2
    (tmp_path / ".claude" / "rules").mkdir(parents=True)
    (tmp_path / ".claude" / "rules" / "docs-lint.yaml").write_text(
        "project_checks: true\n"
    )
    lint_script = getattr(_lint_module, "__file__", None)
    if lint_script is None:
        return
    result = _sp2.run(
        [_sys.executable, lint_script, "doctor", "--root", str(tmp_path),
         "--json", "--no-pymarkdown"],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert result.returncode in (0, 1), (
        f"doctor should exit 0 or 1, got {result.returncode}. stderr: {result.stderr[:200]}"
    )
    data = _json.loads(result.stdout)
    assert "project issue" in data["summary"], (
        f"doctor summary should include project count: {data['summary']}"
    )
    project_findings = [f for f in data["findings"] if f["type"] in {
        "root_structure", "root_readmes", "gitignore_hygiene", "agent_instructions"
    }]
    assert project_findings, "Expected project layer findings with project_checks: true"


def test_collect_all_findings_detects_html_in_docs(tmp_path, monkeypatch):
    """_collect_all_findings returns misplaced_deliverable finding for HTML in docs/."""
    import lint
    from unittest.mock import patch

    (tmp_path / ".claude" / "rules").mkdir(parents=True)
    yaml_content = "schema: h2t_docs_lint_config/v0.2\nproject_checks: true\n"
    (tmp_path / ".claude" / "rules" / "docs-lint.yaml").write_text(yaml_content)
    (tmp_path / "docs" / "research").mkdir(parents=True)
    (tmp_path / "docs" / "research" / "report.html").write_text("<html/>")

    with patch("docs.misplaced_files._is_tracked", return_value=True):
        findings = lint._collect_all_findings(tmp_path, no_pymarkdown=True)

    types = [f["type"] for f in findings]
    assert "misplaced_deliverable" in types
