"""Installable entrypoint for activity spool logging."""

from h2t_ops.lifecycle import run_main
from h2t_ops.lifecycle.activity import writer


def main(argv: list[str] | None = None) -> int:
    return run_main(writer.main, "h2t-activity-log", argv)
