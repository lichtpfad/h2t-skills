"""Tests for apply_registration.py YAML writing."""
import datetime
from pathlib import Path

import pytest

from h2t_ops.core import backups, paths, store
from h2t_ops.lifecycle.apply_registration import apply_registration


def _make_config(tmp: Path, mapping_content: str, domains_content: str):
    """Create temp config dir with YAML files."""
    tmp.mkdir(parents=True, exist_ok=True)
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
    # apply_registration.py:90 stores the key separator-normalised, and
    # lib/gather/project.py:107 reads it back the same way; asserting the native
    # string here made the test a claim about the developer's platform.
    assert str(project_dir).replace("\\", "/") in content
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


def _clock(monkeypatch, *stamps):
    """backups._now returns these, one per call, then the last one forever."""
    seq = [datetime.datetime(*s) for s in stamps]
    monkeypatch.setattr(backups, "_now", lambda: seq.pop(0) if len(seq) > 1 else seq[0])


def _register(n, **kw):
    return apply_registration(project_id=f"p{n}", domain="dev", project_type="git",
                              label=f"P{n}", **kw)


def test_backup_goes_to_state_and_keeps_ten(tmp_path, monkeypatch):
    """R14: config/ is synchronised, so no *.bak beside the file; ten copies per file."""
    cfg = paths.config_dir()
    _make_config(cfg, MINIMAL_MAPPING, MINIMAL_DOMAINS)
    # two calls per registration (mapping, domains), one second apart per registration
    _clock(monkeypatch, *[(2026, 10, 18, 12, 0, n // 2) for n in range(24)])
    for n in range(12):
        _register(n)

    assert list(cfg.glob("*.bak*")) == []
    kept = sorted(p.name for p in paths.backups_dir().glob("domains.yaml.*"))
    assert kept == [f"domains.yaml.20261018-1200{n:02d}" for n in range(2, 12)]
    assert len(list(paths.backups_dir().glob("repo-mapping.yaml.*"))) == 10


def test_two_backups_in_one_second_get_distinct_names(tmp_path, monkeypatch):
    """R46: a second edit in the same second gets -2; neither copy is overwritten."""
    cfg = paths.config_dir()
    _make_config(cfg, MINIMAL_MAPPING, MINIMAL_DOMAINS)
    _clock(monkeypatch, (2026, 10, 18, 12, 0, 0))
    _register(1)
    first = (paths.backups_dir() / "domains.yaml.20261018-120000").read_text(encoding="utf-8")
    _register(2)

    second = paths.backups_dir() / "domains.yaml.20261018-120000-2"
    assert (paths.backups_dir() / "domains.yaml.20261018-120000").read_text(encoding="utf-8") == first
    assert first == MINIMAL_DOMAINS
    assert "p1" in second.read_text(encoding="utf-8")


def test_registration_is_visible_to_identify_project_at_once(tmp_path):
    """The index sees the new YAML by stat on the next connect; no separate refresh call."""
    from h2t_ops.lifecycle.gather.project import identify_project
    _make_config(paths.config_dir(), MINIMAL_MAPPING, MINIMAL_DOMAINS)
    project = tmp_path / "fresh"
    project.mkdir()
    assert identify_project(str(project))["id"] == "unknown"     # index built before

    apply_registration(project_id="fresh", domain="admin", project_type="directory",
                       label="Fresh", cwd=str(project))
    (project / ".claude" / "project-id").unlink()   # answer from the mapping, not the file

    got = identify_project(str(project))
    assert (got["id"], got["domain"], got["label"]) == ("fresh", "admin", "Fresh")


def test_config_root_that_is_the_config_place_is_written_as_config(tmp_path):
    """R43: the caller naming config_dir() itself is the ordinary config write."""
    cfg = paths.config_dir()
    _make_config(cfg, MINIMAL_MAPPING, MINIMAL_DOMAINS)
    _register(1, config_root=str(cfg))
    assert "p1" in (cfg / "repo-mapping.yaml").read_text(encoding="utf-8")


def test_config_root_inside_another_package_place_is_refused(tmp_path):
    """R43: dest=True is no way into a package place other than config itself."""
    elsewhere = paths.state_dir() / "fake-config"
    _make_config(elsewhere, MINIMAL_MAPPING, MINIMAL_DOMAINS)
    with pytest.raises(store.WriteRefused, match="points into state"):
        _register(1, config_root=str(elsewhere))


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
