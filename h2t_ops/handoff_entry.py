"""Installable entrypoint for session handoff writing."""

from h2t_ops.lifecycle import handoff, run_main


def main(argv: list[str] | None = None) -> int:
    return run_main(handoff.main, "h2t-handoff", argv)
