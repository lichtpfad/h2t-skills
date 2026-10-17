"""Installable entrypoint for session-start gather."""

from h2t_ops.lifecycle import run_main, session_start


def main(argv: list[str] | None = None) -> int:
    return run_main(session_start.main, "h2t-gather", argv)
