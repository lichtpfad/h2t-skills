from __future__ import annotations

from typing import Any


def register(subparsers: Any) -> None:
    p = subparsers.add_parser("google", help="Authorize Gmail, Calendar and Drive in one browser consent")
    cmds = p.add_subparsers(dest="google_cmd", required=True)

    ap = cmds.add_parser("auth", help="Create the shared Google token store (opens a browser)")
    ap.add_argument("--force", action="store_true",
                    help="consent again even when the stored token already covers every scope")
    ap.add_argument("--no-browser", action="store_true",
                    help="print the consent URL instead of opening a browser")
    ap.add_argument("--json", dest="as_json", action="store_true",
                    help="raw machine-readable envelope")
    ap.add_argument("--format", dest="fmt", choices=["md", "human"], default="human")
    p.set_defaults(_handler=run)


def run(args: Any) -> Any:
    """Dispatch a google subcommand. Returns result or raises core.errors."""
    from h2t_ops.core.errors import UsageError
    from h2t_ops.core.google_auth import bootstrap_google_token  # lazy

    if args.google_cmd == "auth":
        return bootstrap_google_token(force=args.force, open_browser=not args.no_browser)
    raise UsageError(f"unknown google subcommand: {args.google_cmd!r}")
