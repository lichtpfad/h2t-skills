

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


def test_structure_template_ships_the_docs_section_allowlist():
    """A new project gets the docs/ deny-by-default rule on day one.

    Without the key the rule is off, and the twelve unplanned sections this repo
    grew are exactly what a fresh project would repeat.
    """
    import importlib.util
    from pathlib import Path
    path = (Path(__file__).parents[2] / "plugins" / "h2t-core" / "skills"
            / "scaffold-project" / "scripts" / "scaffold_project.py")
    spec = importlib.util.spec_from_file_location("scaffold_under_test_docs", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    tpl = mod._STRUCTURE_YAML_TEMPLATE
    assert "allowed_doc_dirs:" in tpl
    for section in ["superpowers/", "adr/", "reports/", "archive/"]:
        assert f"  - {section}\n" in tpl
