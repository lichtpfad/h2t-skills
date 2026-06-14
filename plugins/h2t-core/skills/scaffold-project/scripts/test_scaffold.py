import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).parent / "scaffold_project.py"
PY = sys.executable


def _run(*args):
    r = subprocess.run([PY, str(SCRIPT), *args], capture_output=True, text=True)
    return json.loads(r.stdout)


def test_create_new_dir(tmp_path):
    result = _run("create", "--id", "myproj", "--type", "code-local",
                  "--stack", "python", "--dir", str(tmp_path))
    assert result["status"] == "ok"
    assert (tmp_path / "myproj" / "src").exists()
    assert (tmp_path / "myproj" / "README.md").exists()


def test_existing_dir_without_merge_returns_exists(tmp_path):
    (tmp_path / "myproj").mkdir()
    result = _run("create", "--id", "myproj", "--type", "code-local",
                  "--stack", "python", "--dir", str(tmp_path))
    assert result["status"] == "exists"


def test_merge_on_existing_dir(tmp_path):
    (tmp_path / "myproj").mkdir()
    (tmp_path / "myproj" / "docs").mkdir()
    result = _run("create", "--id", "myproj", "--type", "code-local",
                  "--stack", "python", "--dir", str(tmp_path), "--merge")
    assert result["status"] == "merged"
    assert (tmp_path / "myproj" / "src").exists()
    assert (tmp_path / "myproj" / "docs").exists()


def test_merge_does_not_overwrite_existing_readme(tmp_path):
    proj = tmp_path / "myproj"
    proj.mkdir()
    (proj / "README.md").write_text("# MY CUSTOM README", encoding="utf-8")
    _run("create", "--id", "myproj", "--type", "code-local",
         "--stack", "python", "--dir", str(tmp_path), "--merge")
    assert (proj / "README.md").read_text(encoding="utf-8") == "# MY CUSTOM README"


def test_dry_run_merge_shows_merge_flag(tmp_path):
    proj = tmp_path / "myproj"
    proj.mkdir()
    result = _run("create", "--id", "myproj", "--type", "code-local",
                  "--stack", "python", "--dir", str(tmp_path), "--merge", "--dry-run")
    assert result["status"] == "dry-run"
    assert result.get("merge") is True
    # dry-run must not create any files
    assert not (proj / "src").exists()
    assert not (proj / "README.md").exists()


def test_merge_does_not_commit_preexisting_files(tmp_path):
    """In merge mode: only newly scaffolded files are committed, not pre-existing ones."""
    import subprocess as sp
    proj = tmp_path / "myproj"
    proj.mkdir()
    secret = proj / "secret.txt"
    secret.write_text("do not commit", encoding="utf-8")
    _run("create", "--id", "myproj", "--type", "code-local",
         "--stack", "python", "--dir", str(tmp_path), "--merge")
    git_dir = proj / ".git"
    assert git_dir.exists(), "code-local type must always run git init"
    r = sp.run(["git", "-C", str(proj), "show", "--name-only", "HEAD"],
               capture_output=True, text=True)
    assert "secret.txt" not in r.stdout


def test_merge_skips_dir_that_is_a_file(tmp_path):
    """If expected dir exists as a file, merge logs it and continues instead of crashing."""
    proj = tmp_path / "myproj"
    proj.mkdir()
    (proj / "src").write_text("I am a file", encoding="utf-8")
    result = _run("create", "--id", "myproj", "--type", "code-local",
                  "--stack", "python", "--dir", str(tmp_path), "--merge")
    assert result["status"] == "merged"
    assert any("src" in a and "file" in a.lower() for a in result["actions"])


def test_create_generates_structure_yaml(tmp_path):
    result = _run("create", "--id", "myproj", "--type", "code-local",
                  "--stack", "python", "--dir", str(tmp_path))
    structure_yaml = tmp_path / "myproj" / ".h2t" / "structure.yaml"
    assert structure_yaml.exists(), f"Expected .h2t/structure.yaml at {structure_yaml}"
    content = structure_yaml.read_text(encoding="utf-8")
    assert "allowed_root_dirs" in content
    assert "forbidden_patterns" in content
    assert "tmp_*" in content


def test_merge_generates_structure_yaml_if_missing(tmp_path):
    (tmp_path / "myproj").mkdir()
    result = _run("create", "--id", "myproj", "--type", "code-local",
                  "--stack", "python", "--dir", str(tmp_path), "--merge")
    structure_yaml = tmp_path / "myproj" / ".h2t" / "structure.yaml"
    assert structure_yaml.exists()


def test_structure_yaml_idempotent_on_merge(tmp_path):
    # First scaffold
    _run("create", "--id", "myproj", "--type", "code-local",
         "--stack", "python", "--dir", str(tmp_path))
    # Read original content
    yaml_path = tmp_path / "myproj" / ".h2t" / "structure.yaml"
    original = yaml_path.read_text(encoding="utf-8")
    # Second merge — should not overwrite
    _run("create", "--id", "myproj", "--type", "code-local",
         "--stack", "python", "--dir", str(tmp_path), "--merge")
    assert yaml_path.read_text(encoding="utf-8") == original
