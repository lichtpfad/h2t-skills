"""Installable entrypoint for session handoff writing."""

from h2t_ops.plugin_entrypoints import run_plugin_main


def main() -> int:
    return run_plugin_main("skills/handoff/scripts/writer.py")
