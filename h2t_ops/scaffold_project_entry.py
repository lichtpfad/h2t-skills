"""Installable entrypoint for new-project scaffolding."""

from h2t_ops.plugin_entrypoints import run_plugin_main


def main() -> int:
    return run_plugin_main("skills/scaffold-project/scripts/scaffold_project.py")
