

def test_structure_template_allows_github_dir():
    """Blocking on an unlisted root dir would stop a new project's first workflow."""
    import importlib.util
    from pathlib import Path
    path = (Path(__file__).parents[2] / "plugins" / "h2t-core" / "skills"
            / "scaffold-project" / "scripts" / "scaffold_project.py")
    spec = importlib.util.spec_from_file_location("scaffold_under_test", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert "  - .github/" in mod._STRUCTURE_YAML_TEMPLATE
