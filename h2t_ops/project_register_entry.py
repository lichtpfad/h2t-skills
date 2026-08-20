"""Installable entrypoint for project registration in the h2t config."""

from h2t_ops.plugin_entrypoints import run_plugin_main


def main() -> int:
    return run_plugin_main("skills/init-project/scripts/apply_registration.py")
