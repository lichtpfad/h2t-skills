"""Installable entrypoint for project audit scanning."""

from h2t_ops.lifecycle import project_audit_scan, run_main


def main(argv: list[str] | None = None) -> int:
    return run_main(project_audit_scan.main, "h2t-project-audit-scan", argv)
