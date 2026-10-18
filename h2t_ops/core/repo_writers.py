"""What each command may write into the user's repository (#548 §7.1, table «repo»).

Globs are fnmatch on the POSIX path relative to the repository root; `*` crosses `/`.
The set is the measured one: every command ran in a scratch repository and these are the
paths it changed (docs/reports/2026-10-18-storage-repo-writers.md). The test
tests/governance/test_repo_writers.py runs them again and fails on a path not listed here.

A path the user named (`h2t-drawio`, `h2t-creative assemble`, `h2t-runbook new`,
`h2t-docs-lint plan --save`, the agent-profile catalog, `h2t-project-audit-report`'s
projects.yaml) is not a repository write: it goes through store with dest=True (plan R7).
fix-safe's rename target also takes the repository's own `deliverables_dir`
(tools/docs/lint.py _deliverables_writer, store.repo(extra=...)).
"""
# Directories a project type lays out at the root (tools/docs/project_types.py root_dirs);
# tests/governance/test_repo_writers.py keeps the two lists equal.
_TYPE_ROOT_DIRS = ("assets", "data", "deliverables", "docs", "exports", "scripts", "src", "tests")

_LINT_APPLY = ".h2t/lint-apply-*.json"
_LIFECYCLE_DOCS = ("docs/superpowers/plans/*", "docs/superpowers/specs/*")

REPO_WRITERS: dict[str, dict[str, tuple[str, ...]]] = {
    # §7.1: .claude/project-id — "create if absent"; an existing file is kept (plan R32).
    "init-project": {"create": (".claude/project-id",)},
    "h2t-project-register": {"create": (".claude/project-id",)},
    # Templates are created if absent; settings.json is merged; docs/ comes from the
    # h2t-docs-init it runs in a child process.
    "h2t-scaffold-project": {
        "mkdir": _TYPE_ROOT_DIRS,
        "create": (".gitignore", "README.md", "CLAUDE.md", "docs/.artifacts/.gitkeep",
                   ".h2t/structure.yaml"),
        "replace": (".claude/settings.json", ".h2t/project-setup-report.json"),
        "append": (".git/info/exclude",),
    },
    "h2t-docs-init": {
        "create": ("docs/*/.gitkeep", "docs/README.md", ".claude/rules/documentation.md",
                   ".claude/rules/docs-lint.yaml", ".pymarkdown.yaml", ".vale.ini",
                   ".h2t/lint-state.jsonl"),
        "append": (".gitignore",),
    },
    # docs-lint changes docs/** only on an explicit command (§7.1).
    "h2t-docs-lint fix-safe": {
        "mkdir": (*_TYPE_ROOT_DIRS, "docs/*"),
        "create": ("docs/*/.gitkeep",),
        "replace": ("docs/*.md", ".gitignore", _LINT_APPLY),
        "rename": ("docs/*", "deliverables/*"),
    },
    "h2t-docs-lint fix-index": {"replace": ("docs/README.md", _LINT_APPLY)},
    "h2t-docs-lint retire": {"rename": (*_LIFECYCLE_DOCS, "docs/archive/*")},
    "h2t-docs-lint new": {"create": ("docs/superpowers/plans/*.md", "docs/superpowers/specs/*.md",
                                     "docs/adr/*.md")},
    "docs-index": {"replace": ("docs/README.md",)},
    "h2t-milestone-closure": {"replace": (".h2t/lifecycle/milestone-closure-*.json",)},
    "h2t-agent-profile": {"replace": (".claude/agent-profile.json", ".claude/settings.json")},
    # Hooks: plan_closer stamps status on the plans and specs a merged PR carried; the
    # post-commit hook leaves its report.
    "plan-closer": {"replace": _LIFECYCLE_DOCS},
    "post-git-commit-docs-lint": {"replace": (".h2t/lifecycle/post-git-commit-docs-lint.json",)},
}
