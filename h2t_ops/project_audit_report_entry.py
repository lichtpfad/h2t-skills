"""Installable entrypoint for project audit report rendering."""

from h2t_ops.lifecycle import project_audit_report, run_main


def main(argv: list[str] | None = None) -> int:
    return run_main(project_audit_report.main, "h2t-project-audit-report", argv)
