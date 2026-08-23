# plugins/h2t/skills/init-project/scripts/test_apply.py
"""Tests for apply_registration.py YAML writing."""
import json
import tempfile
import shutil
from pathlib import Path

from apply_registration import apply_registration


def _make_config(tmp: Path, mapping_content: str, domains_content: str):
    """Create temp config dir with YAML files."""
    mapping_file = tmp / "repo-mapping.yaml"
    domains_file = tmp / "domains.yaml"
    mapping_file.write_text(mapping_content, encoding="utf-8")
    domains_file.write_text(domains_content, encoding="utf-8")
    return mapping_file, domains_file


MINIMAL_MAPPING = """\
# repo-mapping.yaml
mappings:
  existing-repo: dev/existing

cwd_patterns:
  "/some/path": admin/taxes

default: dev/unknown
"""

MINIMAL_DOMAINS = """\
# domains.yaml
domains:
  dev:
    label: "Dev"
    projects:
      - id: existing
        label: "Existing Project"
"""


def test_add_git_project_to_mapping(tmp_path):
    mapping_file, domains_file = _make_config(tmp_path, MINIMAL_MAPPING, MINIMAL_DOMAINS)

    result = apply_registration(
        project_id="new-project",
        domain="dev",
        project_type="git",
        label="New Project",
        task_tracker="github",
        github="lichtpfad/new-project",
        config_root=str(tmp_path),
    )

    assert result["status"] == "ok"

    # Verify mapping was added
    content = mapping_file.read_text(encoding="utf-8")
    assert "new-project:" in content
    assert "dev/new-project" in content
    # Verify comment preserved
    assert "# repo-mapping.yaml" in content

    # Verify domains entry added
    dcontent = domains_file.read_text(encoding="utf-8")
    assert "new-project" in dcontent
    assert "New Project" in dcontent


def test_add_directory_project_to_cwd_patterns(tmp_path):
    mapping_file, domains_file = _make_config(tmp_path, MINIMAL_MAPPING, MINIMAL_DOMAINS)
    project_dir = tmp_path / "DROPBOX" / "Steuer"
    project_dir.mkdir(parents=True)

    result = apply_registration(
        project_id="steuer",
        domain="admin",
        project_type="directory",
        label="Steuer Docs",
        task_tracker="none",
        cwd=str(project_dir),
        config_root=str(tmp_path),
    )

    assert result["status"] == "ok"
    content = mapping_file.read_text(encoding="utf-8")
    assert str(project_dir) in content
    assert "admin/steuer" in content


def test_update_existing_project(tmp_path):
    mapping_file, domains_file = _make_config(tmp_path, MINIMAL_MAPPING, MINIMAL_DOMAINS)

    result = apply_registration(
        project_id="existing",
        domain="dev",
        project_type="git",
        label="Updated Label",
        task_tracker="github",
        config_root=str(tmp_path),
    )

    assert result["status"] == "ok"
    dcontent = domains_file.read_text(encoding="utf-8")
    assert "Updated Label" in dcontent
    # Should not duplicate
    assert dcontent.count("id: existing") == 1


def test_backup_created(tmp_path):
    mapping_file, domains_file = _make_config(tmp_path, MINIMAL_MAPPING, MINIMAL_DOMAINS)

    apply_registration(
        project_id="test",
        domain="dev",
        project_type="git",
        label="Test",
        config_root=str(tmp_path),
    )

    assert (tmp_path / "repo-mapping.yaml.bak").exists()
    assert (tmp_path / "domains.yaml.bak").exists()


def test_project_id_file_created(tmp_path):
    mapping_file, domains_file = _make_config(tmp_path, MINIMAL_MAPPING, MINIMAL_DOMAINS)
    project_dir = tmp_path / "my-project"
    project_dir.mkdir()

    apply_registration(
        project_id="my-project",
        domain="dev",
        project_type="git",
        label="My Project",
        cwd=str(project_dir),
        config_root=str(tmp_path),
    )

    pid_file = project_dir / ".claude" / "project-id"
    assert pid_file.exists()
    assert pid_file.read_text().strip() == "dev/my-project"


def test_project_id_file_not_overwritten(tmp_path):
    mapping_file, domains_file = _make_config(tmp_path, MINIMAL_MAPPING, MINIMAL_DOMAINS)
    project_dir = tmp_path / "my-project"
    project_dir.mkdir()
    claude_dir = project_dir / ".claude"
    claude_dir.mkdir()
    (claude_dir / "project-id").write_text("old-id\n")

    apply_registration(
        project_id="new-id",
        domain="dev",
        project_type="git",
        label="New",
        cwd=str(project_dir),
        config_root=str(tmp_path),
    )

    assert (claude_dir / "project-id").read_text().strip() == "old-id"


def test_comment_preserved_in_mapping(tmp_path):
    mapping_file, domains_file = _make_config(tmp_path, MINIMAL_MAPPING, MINIMAL_DOMAINS)

    apply_registration(
        project_id="new",
        domain="dev",
        project_type="git",
        label="New",
        config_root=str(tmp_path),
    )

    content = mapping_file.read_text(encoding="utf-8")
    assert "# repo-mapping.yaml" in content


def test_new_domain_created_if_missing(tmp_path):
    mapping_file, domains_file = _make_config(tmp_path, MINIMAL_MAPPING, MINIMAL_DOMAINS)

    apply_registration(
        project_id="taxes",
        domain="admin",
        project_type="directory",
        label="Taxes",
        task_tracker="notion",
        cwd=str(tmp_path / "taxes-dir"),
        config_root=str(tmp_path),
    )

    dcontent = domains_file.read_text(encoding="utf-8")
    assert "admin:" in dcontent
    assert "taxes" in dcontent
    assert "task_tracker: notion" in dcontent or "task_tracker: 'notion'" in dcontent
