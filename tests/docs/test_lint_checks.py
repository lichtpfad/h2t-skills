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
