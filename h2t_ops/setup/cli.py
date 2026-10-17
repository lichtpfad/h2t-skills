"""`h2t-setup <sync|update|dev-sync>` (spec §7.3, §7.4).

The order is the contract: an editable install stops `sync`/`update` before anything else;
then the target is resolved, and a network failure ends the run with nothing touched; then
the process makes sure it is the target's own isolated executor; only then do the steps run.
`dev-sync` installs from the checkout, so it reads no target and needs no re-launch.
`update` without a terminal is refused first: its question has nobody to answer it.
"""
from __future__ import annotations

import argparse
import sys

from h2t_ops.core.errors import ConfigError, H2TError, ProviderError
from h2t_ops.core.output import emit
from h2t_ops.setup import manifest, state, sync

MODES = ("sync", "update", "dev-sync")


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    # On the mode, not the top level: the re-launch passes the mode first and the original
    # arguments after it, and those must parse the same way in the target.
    common.add_argument("--json", action="store_true", help="the standard envelope")
    parser = argparse.ArgumentParser(prog="h2t-setup")
    sub = parser.add_subparsers(dest="mode", required=True)
    sub.add_parser("sync", parents=[common], help="bring the install to the current release")
    sub.add_parser("update", parents=[common], help="sync, after showing what changes")
    sub.add_parser("dev-sync", parents=[common], help="install the CLI from this checkout")
    return parser


def _editable_stop(mode: str) -> None:
    if mode == "dev-sync":
        return
    install = state.read()
    # A 3.x install has no install.json; uv's receipt still says whether it is editable.
    checkout = install.editable if install is not None else sync.receipt_editable()
    if checkout:
        raise ConfigError(
            f"the CLI is installed editable from the checkout {checkout}; "
            f"`h2t-setup {mode}` does not touch it",
            hint="update the checkout yourself, then run `h2t-setup dev-sync`",
            details={"reason": "editable", "checkout": checkout})


def _consent_stop(mode: str) -> None:
    # Consent is a person at a terminal. No flag gives it, and neither does a pipe:
    # `echo да | h2t-setup update` is an agent answering for the user. The target executor
    # runs this same check after a re-launch (§7.3.2).
    if mode == "update" and not sys.stdin.isatty():
        raise ConfigError(
            "h2t-setup update asks before it changes anything, and with no terminal "
            "there is nobody to answer",
            hint="run `h2t-setup update` in a terminal; "
                 "`h2t-setup sync` brings the install to the target without asking",
            details={"reason": "confirmation_required"})


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else list(argv)
    ns = build_parser().parse_args(argv)
    rest = argv[1:]  # everything after the mode; options live on the mode only
    fmt = "json" if ns.json else "human"
    try:
        _editable_stop(ns.mode)
        _consent_stop(ns.mode)
        target = None
        if ns.mode != "dev-sync":
            target = manifest.current()
            sync.ensure_executor(target, ns.mode, rest)
        result = sync.run(ns.mode, target, rest)
        if isinstance(result, sync.Report):
            if result.failed:
                # Not a success with a list attached: a run that left something off target
                # exits non-zero, and the hint is the command that continues it.
                raise ProviderError(
                    "h2t-setup {}: not everything reached the target: {}".format(
                        ns.mode, "; ".join(subject for subject, _ in result.failed)),
                    hint=result.failed[0][1], details=result.as_dict())
            result = result.as_dict() if ns.json else result.text()
    except H2TError as exc:
        return emit("setup", exc=exc, fmt=fmt)
    return emit("setup", result=result, fmt=fmt)


if __name__ == "__main__":
    raise SystemExit(main())
