"""Installable entrypoint for new-project scaffolding."""

from h2t_ops.lifecycle import run_main, scaffold_project


def main(argv: list[str] | None = None) -> int:
    return run_main(scaffold_project.main, "h2t-scaffold-project", argv)
