# plugins/h2t-dev/lib/docs/project_types.py
"""Per-project-type directory structure definitions.

Single source of truth consumed by:
  - docs-init (docs/ subdirs to scaffold per template)
  - scaffold-project (root dirs to create per type)
  - docs-lint (structure compliance checks, future)
"""
from __future__ import annotations
from pathlib import Path
from typing import TypedDict


class ProjectTypeSpec(TypedDict):
    root_dirs: list[str]        # dirs to create at project root
    docs_dirs: list[str]        # dirs inside docs/ beyond REQUIRED_CORE_DIRS
    root_files_required: list[str]


PROJECT_TYPES: dict[str, ProjectTypeSpec] = {
    "code_repo": {
        "root_dirs": ["src", "tests", "docs", "scripts"],
        "docs_dirs": [],
        "root_files_required": ["README.md", "CLAUDE.md"],
    },
    "client_project": {
        "root_dirs": ["docs", "data", "deliverables", "scripts"],
        "docs_dirs": ["docs/ops", "docs/research"],
        "root_files_required": ["README.md", "CLAUDE.md"],
    },
    "research_project": {
        "root_dirs": ["docs", "data"],
        "docs_dirs": ["docs/research"],
        "root_files_required": ["README.md", "CLAUDE.md"],
    },
    "creative_project": {
        "root_dirs": ["assets", "scripts", "exports", "docs"],
        "docs_dirs": ["docs/assets", "docs/briefs", "docs/reviews"],
        "root_files_required": ["README.md", "CLAUDE.md"],
    },
    "personal_os": {
        "root_dirs": ["docs"],
        "docs_dirs": ["docs/notes", "docs/sessions"],
        "root_files_required": [],
    },
    "ops_workflow": {
        "root_dirs": ["docs", "scripts"],
        "docs_dirs": ["docs/runbooks", "docs/logs"],
        "root_files_required": ["README.md"],
    },
}

# Maps scaffold --type arg to template name
SCAFFOLD_TYPE_TO_TEMPLATE: dict[str, str] = {
    "code-github": "code_repo",
    "code-local": "code_repo",
    "docs": "research_project",
    "dcc": "creative_project",
    "directory": "ops_workflow",
}


def detect_template(repo_root: Path) -> str:
    """Detect project template name for an existing repo.

    Priority:
    1. .claude/rules/docs-lint.yaml template field (written by docs-init)
    2. File-presence heuristics
    3. Default: code_repo
    """
    cfg = repo_root / ".claude" / "rules" / "docs-lint.yaml"
    if cfg.exists():
        # Minimal parse: handles plain/quoted values and inline comments
        for line in cfg.read_text(encoding="utf-8").splitlines():
            if line.startswith("template:"):
                name = line.split(":", 1)[1].strip()
                name = name.split("#")[0].strip().strip('"\'')
                if name in PROJECT_TYPES:
                    return name

    if (repo_root / "pyproject.toml").exists() or (repo_root / "setup.py").exists():
        return "code_repo"
    if (repo_root / "package.json").exists():
        return "code_repo"
    if (repo_root / "deliverables").exists():
        return "client_project"
    if (repo_root / "assets").exists() and (repo_root / "scripts").exists():
        return "creative_project"

    return "code_repo"
