"""Installable entrypoint for project registration in the h2t config."""

from h2t_ops.lifecycle import apply_registration, run_main


def main(argv: list[str] | None = None) -> int:
    return run_main(apply_registration.main, "h2t-project-register", argv)
