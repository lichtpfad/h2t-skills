"""Installable entrypoint for project audit scanning."""

from h2t_ops.plugin_entrypoints import run_plugin_main


def main() -> int:
    return run_plugin_main("skills/project-audit/scripts/scan.py")
