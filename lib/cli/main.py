"""Legacy `h2t-ops` catch-all.

`gather` used to live here as a second implementation and drifted from the plugin script
for months — it never gained `find_latest_session_index`, so a briefing produced through
`h2t-ops gather` silently lacked its `### Previous Session` block. It now routes through
`h2t_ops.plugin_entrypoints`, which runs the plugin's own
`skills/session-start/scripts/gather.py`.

Nothing is implemented here any more. The module survives because `h2t_ops/cli.py:_legacy`
falls through to it for unrecognised commands, and that fallthrough must keep exiting 2.
"""

import argparse
import sys


def main() -> None:
    parser = argparse.ArgumentParser(prog="h2t", description="h2t unified CLI")
    parser.add_subparsers(dest="command")
    args = parser.parse_args()
    if args.command is None:
        parser.print_help(sys.stderr)
        sys.exit(2)
    print(f"error: unknown command '{args.command}'", file=sys.stderr)
    sys.exit(2)


if __name__ == "__main__":
    main()
