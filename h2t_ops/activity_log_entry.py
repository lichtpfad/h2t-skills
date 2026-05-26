"""Installable entrypoint for activity spool logging."""

from h2t_ops.plugin_entrypoints import run_plugin_main


def main() -> int:
    return run_plugin_main("lib/activity/writer.py")
