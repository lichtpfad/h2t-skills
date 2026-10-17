"""Installable entrypoint for session handoff writing, and the rule scan beside it."""

import sys

from h2t_ops.lifecycle import handoff, run_main


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else list(argv)
    if args[:1] == ["rule-scan"]:
        # Its own module: handoff.py is a copy of the plugin writer, held by a parity test.
        from h2t_ops.lifecycle import rule_scan

        return rule_scan.main(args[1:])
    return run_main(handoff.main, "h2t-handoff", argv)
