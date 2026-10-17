"""The lifecycle commands run the package's code, not a script found in a plugin tree.

Until D2 each of these modules was one line, `run_plugin_main("<plugin path>")`: the code
lived in the plugin and was located at run time through `plugin_entrypoints`' ladder. On a
host where the ladder resolved nothing the command could not even print its usage.
"""
import ast
import importlib
from pathlib import Path

import pytest

from h2t_ops import plugin_entrypoints

ROOT = Path(__file__).resolve().parents[2]

# Every console script that went through `run_plugin_main`. `h2t-hook` is not here: it
# launches a handler by name as a process and moves with the hooks (Task 9).
LIFECYCLE_ENTRIES = {
    "h2t-gather": "h2t_ops.gather_entry",
    "h2t-handoff": "h2t_ops.handoff_entry",
    "h2t-activity-log": "h2t_ops.activity_log_entry",
    "h2t-project-audit-scan": "h2t_ops.project_audit_scan_entry",
    "h2t-project-audit-report": "h2t_ops.project_audit_report_entry",
    "h2t-project-register": "h2t_ops.project_register_entry",
    "h2t-scaffold-project": "h2t_ops.scaffold_project_entry",
}


def _imported_names(path: Path) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
            names |= {f"{node.module}.{alias.name}" for alias in node.names}
    return names


def test_the_inventory_matches_pyproject():
    """A new `*_entry` console script must be classified here, or it escapes the check."""
    import tomllib

    with (ROOT / "pyproject.toml").open("rb") as f:
        scripts = tomllib.load(f)["project"]["scripts"]
    entries = {name: target.split(":")[0] for name, target in scripts.items()
               if target.split(":")[0].endswith("_entry")}
    entries.pop("h2t-hook")
    assert entries == LIFECYCLE_ENTRIES


@pytest.mark.parametrize("module", sorted(LIFECYCLE_ENTRIES.values()))
def test_entry_does_not_import_the_plugin_ladder(module):
    path = ROOT / (module.replace(".", "/") + ".py")
    imported = _imported_names(path)
    assert "h2t_ops.plugin_entrypoints" not in imported, f"{module} still loads a plugin script"
    assert any(name.startswith("h2t_ops.lifecycle") for name in imported), (
        f"{module} imports nothing from h2t_ops.lifecycle: {sorted(imported)}"
    )


@pytest.mark.parametrize("module", sorted(LIFECYCLE_ENTRIES.values()))
def test_help_needs_no_plugin_tree(module, tmp_path, monkeypatch):
    """`--help` exits 0 when every place the ladder looks is empty.

    H2T_PLUGIN_ROOT alone is not enough to prove it: the ladder falls through to the
    checkout's own plugins/ after it, so the old one-liners passed that half too. The
    ladder itself is emptied as well.
    """
    empty = tmp_path / "empty-plugin-root"
    empty.mkdir()
    monkeypatch.setenv("H2T_PLUGIN_ROOT", str(empty))
    monkeypatch.delenv("CLAUDE_PLUGIN_ROOT", raising=False)
    monkeypatch.setattr(plugin_entrypoints, "candidate_roots", lambda: [empty])

    entry = importlib.import_module(module)
    try:
        code = entry.main(["--help"])
    except SystemExit as exc:
        code = exc.code
    assert code in (0, None), f"{module} --help exited {code!r}"
