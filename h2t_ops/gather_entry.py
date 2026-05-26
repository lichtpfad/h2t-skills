"""Installable entrypoint for session-start gather."""

from h2t_ops.plugin_entrypoints import run_plugin_main


def main() -> int:
    return run_plugin_main("skills/session-start/scripts/gather.py")
