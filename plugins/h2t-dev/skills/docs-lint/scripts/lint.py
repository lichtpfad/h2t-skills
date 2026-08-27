#!/usr/bin/env python3
"""docs-lint: Documentation health check and fix tool.

Sub-commands:
  audit       Run all checks and show findings (default)
  plan        Show human-readable cleanup plan without writing
  fix-safe    Apply only safe mechanical fixes (dirs, frontmatter)
  fix-index   Rebuild docs/README.md navigation index
  doctor      Output machine-readable h2t_lifecycle_report/v0.1 JSON

Legacy flags (deprecated, use sub-commands instead):
  --fix                 → fix-safe (emits deprecation warning)
  --fix-frontmatter     → fix-safe --only=frontmatter (emits deprecation warning)
"""

import argparse
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

_PLUGIN_ROOT = Path(__file__).resolve().parents[3]
for _lib in [_PLUGIN_ROOT / "lib", _PLUGIN_ROOT.parent.parent / "lib"]:
    if _lib.exists():
        sys.path.insert(0, str(_lib))
        break

from docs.common import (
    DEV_ROOT,
    FRONTMATTER_RULES,
    REPO_EXTRA_DIRS,
    REPO_MANIFEST,
    REQUIRED_CORE_DIRS,
    STANDARDS_FILES,
    ensure_dir,
    excluded_predicate,
    git_repo_root,
    parse_frontmatter,
    print_header,
    repo_path,
    standards_dir,
)
from docs.config import load_config
from docs.index_builder import write_index
from docs.naming import check_naming_all_docs
from docs.orphan import find_orphan_files
from docs.reporter import build_report, finding, status_from_findings
from docs.retire import find_retire_candidates, retire_files

try:
    from docs.project_types import PROJECT_TYPES
    _PROJECT_TYPES_AVAILABLE = True
except ImportError:
    PROJECT_TYPES = {}
    _PROJECT_TYPES_AVAILABLE = False

try:
    from docs.agent_instructions import check_agent_instructions
    from docs.gitignore_hygiene import check_gitignore_hygiene, fix_gitignore_hygiene
    from docs.root_structure import check_root_readmes, check_root_structure
    _PROJECT_LAYER_AVAILABLE = True
except ImportError as _e:
    import warnings as _warnings
    _warnings.warn(
        f"docs-lint project layer unavailable (import failed: {_e}). "
        "Run: uv tool install --editable <your h2t-skills checkout>",
        RuntimeWarning, stacklevel=1,
    )
    _PROJECT_LAYER_AVAILABLE = False

try:
    from docs.misplaced_files import check_misplaced_deliverables
    _MISPLACED_FILES_AVAILABLE = True
except ImportError:
    _MISPLACED_FILES_AVAILABLE = False

_SUBCOMMANDS = frozenset(
    {"audit", "plan", "fix-safe", "fix-index", "doctor", "new", "retire"}
)

_VENDOR_EXCLUDE = {
    ".venv", "venv", "node_modules", "__pycache__", "dist", "build",
    ".git", ".mypy_cache", ".pytest_cache", ".ruff_cache",
}
_DIM_LIMIT = 50

# Every finding type the audit and doctor fold into their "Project Layer" line.
_PROJECT_TYPES = [
    "root_structure", "root_readmes", "gitignore_hygiene",
    "agent_instructions", "misplaced_deliverable",
]

_SEVERITY_MAP = {
    "error": "critical",
    "warn": "important",
    "info": "low",
    "critical": "critical",
    "important": "important",
    "low": "low",
}


def _is_vendor_path(path: str) -> bool:
    if not path:
        return False
    return any(part in _VENDOR_EXCLUDE for part in Path(path).parts)


def _is_vendor_message(message: str) -> bool:
    """Catch vendor paths embedded in message when path field is empty."""
    return any(f"/{v}/" in message or message.startswith(v + "/")
               for v in _VENDOR_EXCLUDE)


def _apply_exceptions(findings: list[dict], exceptions: list) -> list[dict]:
    """Remove findings whose path matches a documented exception.

    Handles both dict exceptions (new) and string exceptions (legacy).
    """
    exception_paths: set[str] = set()
    for exc in exceptions:
        if isinstance(exc, str):
            exception_paths.add(exc.rstrip("/"))
        elif isinstance(exc, dict):
            p = exc.get("path", "").rstrip("/")
            if p:
                exception_paths.add(p)
    if not exception_paths:
        return findings
    result = []
    for f in findings:
        fp = f.get("path", "").rstrip("/")
        covered = any(
            fp == ep or fp.startswith(ep + "/")
            for ep in exception_paths if ep
        )
        if not covered:
            result.append(f)
    return result


def _cap_by_dimension(
    findings: list[dict], limit: int = _DIM_LIMIT,
) -> tuple[list[dict], dict[str, int]]:
    """Keep at most `limit` findings per type; also return the uncapped totals.

    The cap used to be silent, and a silent cap is not a smaller report — it is
    a wrong number. This repo had 136 orphans and every surface said 50: audit,
    doctor, doctor --json, and the baseline written into .claude/rules. It also
    made the report insensitive to real change — excluding three frozen trees
    took orphans 136 → 93 and moved the printed count not at all.

    Returns (kept, totals) so callers can bound what they print while reporting
    what they found.
    """
    counts: dict[str, int] = {}
    totals: dict[str, int] = {}
    result = []
    for f in findings:
        t = f["type"]
        totals[t] = totals.get(t, 0) + 1
        if counts.get(t, 0) < limit:
            result.append(f)
            counts[t] = counts.get(t, 0) + 1
    return result, totals


def _normalize_severities(findings: list[dict]) -> list[dict]:
    """Map legacy severity values (warn/info/error) to spec values (critical/important/low)."""
    for f in findings:
        f["severity"] = _SEVERITY_MAP.get(f.get("severity", "info"), "low")
    return findings


PROJECTS_YAML_PATH = DEV_ROOT / "h2t-landings" / "projects.yaml"

_CROSS_REPO_NOTED = False


def _note_cross_repo_disabled() -> None:
    """Once per process, on stderr, so JSON on stdout stays parseable."""
    global _CROSS_REPO_NOTED
    if _CROSS_REPO_NOTED:
        return
    _CROSS_REPO_NOTED = True
    print(
        f"note: cross-repo checks are off — no registry at {PROJECTS_YAML_PATH}. "
        "Set H2T_DEV_ROOT if your sibling repositories live elsewhere.",
        file=sys.stderr,
    )

YAML_FLAG_CHECKS: dict[str, str] = {
    "docs.positioning": "docs/product/positioning.md",
    "docs.eval_report": "docs/reports",
    "docs.marketing_docs": "docs/marketing",
}


def _load_projects_yaml() -> dict:
    if not PROJECTS_YAML_PATH.exists():
        # Say it. An empty dict here turns off every cross-repo check, and the caller
        # cannot tell that from "the registry says nothing about this repo". A stranger
        # has no h2t-landings at all, so this is their normal state, not an error — but
        # a check that is off must not read as a check that passed.
        _note_cross_repo_disabled()
        return {}
    text = PROJECTS_YAML_PATH.read_text(encoding="utf-8")
    try:
        import yaml
        return yaml.safe_load(text) or {}
    except ImportError:
        return {}


def _get_flag(project_data: dict, dotted_key: str) -> bool:
    parts = dotted_key.split(".")
    node = project_data
    for p in parts:
        if not isinstance(node, dict):
            return False
        node = node.get(p, False)
    return bool(node)


def check_projects_yaml(rp: Path, name: str, projects: dict) -> list[str]:
    if not projects:
        return []
    project_data = projects.get(name, {})
    if not project_data:
        return []
    failures = []
    for flag, required_path in YAML_FLAG_CHECKS.items():
        if _get_flag(project_data, flag):
            target = rp / required_path
            if not target.exists():
                failures.append(f"projects.yaml {flag}=true but missing: {required_path}")
    return failures


def check_structure(rp: Path) -> list[str]:
    failures = []
    for rel_dir in REQUIRED_CORE_DIRS:
        if not (rp / rel_dir).exists():
            failures.append(f"missing dir: {rel_dir}/")
    for name, path in [
        ("docs/README.md", rp / "docs" / "README.md"),
        (".claude/rules/documentation.md", rp / ".claude" / "rules" / "documentation.md"),
        (".pymarkdown.yaml", rp / ".pymarkdown.yaml"),
        (".vale.ini", rp / ".vale.ini"),
    ]:
        if not path.exists():
            failures.append(f"missing: {name}")
    return failures


def check_adr_naming(rp: Path, exclude_dirs: list[str] | None = None) -> list[str]:
    failures = []
    adr_dir = rp / "docs" / "adr"
    if not adr_dir.exists():
        return failures
    is_excluded = excluded_predicate(rp, exclude_dirs)
    for adr in adr_dir.glob("[0-9]*.md"):
        if is_excluded(adr):
            continue
        if not re.match(r"^\d{4}-", adr.name):
            failures.append(f"ADR naming: {adr.name} (expected 4-digit prefix)")
    return failures


LEGACY_DIRS = ["docs/plans", "docs/specs", "docs/handoff", "docs/handoffs", "docs/eval"]


def check_legacy_dirs(rp: Path, extra_dirs: list[str] | None = None) -> list[str]:
    skip = set(extra_dirs or [])
    failures = []
    for rel in LEGACY_DIRS:
        dir_name = rel.split("/")[-1]
        if dir_name in skip:
            continue
        if (rp / rel).exists():
            failures.append(f"legacy dir: {rel}/ — migrate to docs/superpowers/ or docs/archive/")
    return failures


_BANNED_ROOT_DIRS = {"temp", "old", "backup", "tmp", "archive_old"}
_ROOT_MAX_ITEMS = 12
_ROOT_SKIP = {".git", ".venv", "venv", "__pycache__", ".mypy_cache", ".pytest_cache",
              "node_modules", ".ruff_cache", ".vscode", ".idea"}


def check_repo_root(rp: Path) -> list[str]:
    failures = []
    items = [p for p in rp.iterdir() if p.name not in _ROOT_SKIP]
    for item in items:
        if item.is_dir() and item.name.lower() in _BANNED_ROOT_DIRS:
            failures.append(f"repo root: banned dir '{item.name}/' — remove or archive via git mv")
    # Count only git-tracked top-level items; fall back to filesystem if not a git repo
    try:
        result = subprocess.run(
            ["git", "ls-files", "--cached", "--", "."],
            cwd=str(rp),
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            # Count unique top-level names (first path component) of tracked files
            tracked = {
                line.split("/")[0]
                for line in result.stdout.splitlines()
                if line and not line.startswith(".")
            }
            visible_count = len(tracked)
        else:
            raise RuntimeError("git failed")
    except Exception:
        # Not a git repo or git unavailable — fall back to filesystem count
        visible_count = len([p for p in items if not p.name.startswith(".")])
    if visible_count > _ROOT_MAX_ITEMS:
        failures.append(
            f"repo root has {visible_count} items (max {_ROOT_MAX_ITEMS}) — consider consolidating"
        )
    return failures


def check_project_structure_typed(rp: Path, template: str) -> list[str]:
    """Check type-specific root + docs dirs from PROJECT_TYPES (dirs only).

    Scope: directory existence only. root_files_required is not checked here.
    Only called when docs-lint.yaml has an explicit non-empty str template field.
    Returns [] for unknown templates (graceful no-op).

    Findings include '(template: X)' suffix in message AND are tagged with
    a 'template' key on the finding dict — filterable by machine consumers.

    Note: root_dirs/docs_dirs don't overlap with REQUIRED_CORE_DIRS by design.
    If a future template entry adds a dir already in REQUIRED_CORE_DIRS,
    check_structure() will already report it and this function will produce
    a duplicate. Fix: dedup by message in _collect_all_findings() at that time.

    Assumes PROJECT_TYPES entries contain trusted internal POSIX relative paths.
    """
    spec = PROJECT_TYPES.get(template)
    if spec is None:
        return []
    failures = []
    for d in spec.get("root_dirs", []):
        p = rp / d
        if p.is_dir():
            continue
        if p.exists():
            failures.append(f"path exists but is not a dir: {d}/ (template: {template})")
        else:
            failures.append(f"missing required dir: {d}/ (template: {template})")
    for d in spec.get("docs_dirs", []):
        p = rp / d
        if p.is_dir():
            continue
        if p.exists():
            failures.append(f"path exists but is not a dir: {d}/ (template: {template})")
        else:
            failures.append(f"missing template dir: {d}/ (template: {template})")
    return failures


_DATA_EXTS_IN_DOCS = {".json", ".yaml", ".yml", ".csv"}
_DOC_EXTS_IN_DATA = {".md"}
_DATA_DOCS_SKIP = {".pymarkdown.yaml", ".vale.ini"}


def check_data_docs_boundary(rp: Path, exclude_dirs: list[str] | None = None) -> list[str]:
    failures = []
    is_excluded = excluded_predicate(rp, exclude_dirs)
    docs_dir = rp / "docs"
    if docs_dir.exists():
        for f in docs_dir.rglob("*"):
            if is_excluded(f):
                continue
            if f.is_file() and f.suffix in _DATA_EXTS_IN_DOCS and f.name not in _DATA_DOCS_SKIP:
                rel = str(f.relative_to(rp)).replace("\\", "/")
                failures.append(f"data in docs: {rel} — move to data/")
    data_dir = rp / "data"
    if data_dir.exists():
        for f in data_dir.rglob("*"):
            if f.is_file() and f.suffix in _DOC_EXTS_IN_DATA and f.name.lower() != "readme.md":
                rel = str(f.relative_to(rp)).replace("\\", "/")
                failures.append(f"doc in data: {rel} — move to docs/")
    return failures


def check_naming_conventions(rp: Path) -> list[str]:
    """Legacy naming check (specs/plans date prefix only). Preserved for existing tests."""
    failures = []
    for rel_dir in ["docs/superpowers/specs", "docs/superpowers/plans"]:
        d = rp / rel_dir
        if not d.exists():
            continue
        for md in d.glob("*.md"):
            if md.name in {"README.md", "index.md"}:
                continue
            if not re.match(r"^\d{4}-\d{2}-\d{2}-", md.name):
                failures.append(
                    f"naming: {rel_dir}/{md.name} — expected YYYY-MM-DD- prefix"
                )
    return failures


def check_frontmatter(rp: Path, exclude_dirs: list[str] | None = None) -> list[str]:
    failures = []
    docs_dir = rp / "docs"
    if not docs_dir.exists():
        return failures
    is_excluded = excluded_predicate(rp, exclude_dirs)
    for md_file in docs_dir.rglob("*.md"):
        if is_excluded(md_file):
            continue
        rel = str(md_file.relative_to(rp)).replace("\\", "/")
        for dir_pattern, required_fields in FRONTMATTER_RULES.items():
            if dir_pattern not in rel or not required_fields:
                continue
            text = md_file.read_text(encoding="utf-8", errors="replace")
            fm = parse_frontmatter(text)
            if fm is None:
                failures.append(f"{rel}: missing frontmatter")
                break
            for field in required_fields:
                if field not in fm:
                    failures.append(f"{rel}: missing field '{field}'")
    return failures


_PYMD_LIMIT = 20


def run_pymarkdownlnt(rp: Path, exclude_dirs: list[str] | None = None) -> list[str]:
    """Markdown lint over docs/, minus the frozen trees.

    pymarkdownlnt scans the directory it is handed, so the exclusion is applied
    to its output. Matched on the path rather than parsed out of the line: the
    format is `path:line:col: RULE: text` and a Windows drive letter makes the
    first colon ambiguous. The needle carries a trailing separator, because
    `docs/archive` without one also swallows `docs/archive-old/` — an exclusion
    wider than the one configured, hiding findings from a live tree (codex [P2]).

    Nothing is installed on some machines and this returns [] — which reads
    exactly like a clean tree, so a zero here is not evidence of one.
    """
    pymdl = shutil.which("pymarkdownlnt") or shutil.which("pymarkdown")
    if not pymdl:
        return []
    docs_dir = rp / "docs"
    if not docs_dir.exists():
        return []
    result = subprocess.run(
        [pymdl, "scan", str(docs_dir)],
        capture_output=True, text=True, cwd=str(rp),
    )
    if result.returncode == 0:
        return []
    needles = []
    for d in (exclude_dirs or []):
        for form in (str((rp / d).resolve()), d):
            form = form.replace("\\", "/").rstrip("/")
            if form:
                needles.append(form + "/")
    out = result.stdout + result.stderr
    lines = []
    for ln in out.splitlines():
        if not ln.strip():
            continue
        norm = ln.replace("\\", "/")
        if any(n and n in norm for n in needles):
            continue
        lines.append(ln)
    msgs = [f"pymarkdownlnt: {ln}" for ln in lines[:_PYMD_LIMIT]]
    if len(lines) > _PYMD_LIMIT:
        # Same rule as the dimension cap: bound the list, name the remainder.
        msgs.append(
            f"pymarkdownlnt: ... {len(lines) - _PYMD_LIMIT} more not listed "
            f"(cap {_PYMD_LIMIT})"
        )
    return msgs


def fix_structure(rp: Path) -> list[str]:
    """Create missing dirs (scaffolding only). Does NOT move files — use git mv for that.

    Creates REQUIRED_CORE_DIRS always, plus PROJECT_TYPES[template] dirs when template: is set.
    Idempotent: existing dirs are left unchanged.
    Returns list of "created: <path>/" strings for newly created dirs only.
    """
    fixes = []
    for rel_dir in REQUIRED_CORE_DIRS:
        d = rp / rel_dir
        if ensure_dir(d):
            fixes.append(f"created: {rel_dir}/")
    cfg = load_config(rp)
    _raw = cfg.get("template")
    template = _raw if isinstance(_raw, str) and _raw.strip() else None
    if template:
        spec = PROJECT_TYPES.get(template)
        if spec:
            for rel_dir in spec.get("root_dirs", []) + spec.get("docs_dirs", []):
                d = rp / rel_dir
                if d.exists() and not d.is_dir():
                    # File collision — skip silently (check_project_structure_typed reports it)
                    continue
                already_exists = d.is_dir()
                d.mkdir(parents=True, exist_ok=True)
                if not already_exists:
                    fixes.append(f"created: {rel_dir}/ (template: {template})")
    return fixes


def _extract_title(text: str, filename: str) -> str:
    for line in text.splitlines():
        m = re.match(r"^#\s+(.+)", line)
        if m:
            return m.group(1).strip()
    name = re.sub(r"^\d{4}-\d{2}-\d{2}-?", "", filename)
    return name.replace("-", " ").replace("_", " ").strip(".md")


def _extract_date(filename: str) -> str:
    m = re.match(r"(\d{4}-\d{2}-\d{2})", filename)
    return m.group(1) if m else "unknown"


def _extract_milestone(filename: str) -> str:
    m = re.search(r"-(m\d+)-", filename, re.IGNORECASE)
    return m.group(1).upper() if m else ""


def _git_author(rp: Path, filepath: Path) -> str:
    rel = str(filepath.relative_to(rp))
    result = subprocess.run(
        ["git", "-C", str(rp), "log", "--diff-filter=A", "--format=%an", "--", rel],
        capture_output=True, text=True,
    )
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return lines[0] if lines else "lichtpfad"


def _frontmatter_value(field: str, md_file: Path, text: str, rp: Path) -> str:
    """Derive a default value for a single missing frontmatter field."""
    if field == "title":
        return f'"{_extract_title(text, md_file.stem)}"'
    if field == "status":
        return '"draft"'
    if field == "owner":
        return f'"{_git_author(rp, md_file)}"'
    if field == "date":
        return f'"{_extract_date(md_file.name)}"'
    if field == "milestone":
        return f'"{_extract_milestone(md_file.name)}"'
    return '""'


def fix_frontmatter_action(rp: Path, exclude_dirs: list[str] | None = None) -> list[str]:
    """Add only missing required frontmatter fields. Preserves existing keys.

    Takes the same exclusions as check_frontmatter. A fixture kept without
    frontmatter on purpose — because a test asserts what happens when it is
    absent — must not be handed one by fix-safe just because the audit went
    quiet about it (codex [P2]).
    """
    fixes = []
    docs_dir = rp / "docs"
    if not docs_dir.exists():
        return fixes
    is_excluded = excluded_predicate(rp, exclude_dirs)
    for md_file in docs_dir.rglob("*.md"):
        if is_excluded(md_file):
            continue
        rel = str(md_file.relative_to(rp)).replace("\\", "/")
        matched_pattern = None
        required_fields_for_pattern: list[str] = []
        for dir_pattern, required_fields in FRONTMATTER_RULES.items():
            if dir_pattern in rel and required_fields:
                matched_pattern = dir_pattern
                required_fields_for_pattern = required_fields
                break
        if not matched_pattern:
            continue
        text = md_file.read_text(encoding="utf-8", errors="replace")
        fm = parse_frontmatter(text)
        if fm is not None and all(f in fm for f in required_fields_for_pattern):
            continue

        missing = [f for f in required_fields_for_pattern if not (fm and f in fm)]

        if fm is not None and text.startswith("---"):
            parts = text.split("---", 2)
            if len(parts) >= 3:
                fm_block = parts[1].rstrip("\n")
                body = parts[2]
                extra = "\n".join(
                    f"{f}: {_frontmatter_value(f, md_file, text, rp)}"
                    for f in missing
                )
                new_text = "---\n" + fm_block.lstrip("\n") + "\n" + extra + "\n---" + body
            else:
                continue
        else:
            lines = ["---"]
            for f in required_fields_for_pattern:
                lines.append(f"{f}: {_frontmatter_value(f, md_file, text, rp)}")
            lines += ["---", ""]
            body_text = text if not text.startswith("---") else text
            new_text = "\n".join(lines) + body_text

        import tempfile as _tmpmod
        dir_ = md_file.parent
        with _tmpmod.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=dir_, delete=False, suffix=".tmp"
        ) as tf:
            tf.write(new_text)
            tmp = tf.name
        try:
            os.replace(tmp, md_file)
        except Exception:
            try:
                Path(tmp).unlink(missing_ok=True)
            except OSError:
                pass
            raise
        fixes.append(f"added frontmatter fields {missing}: {rel}")
    return fixes


# Legacy alias used by existing --fix-frontmatter flag path
def fix_frontmatter(rp: Path, exclude_dirs: list[str] | None = None) -> list[str]:
    """Legacy wrapper: delegates to fix_frontmatter_action."""
    return fix_frontmatter_action(rp, exclude_dirs=exclude_dirs)


_SYNC_LABELS_SCRIPT = Path(__file__).parents[2] / "docs-sync-labels" / "scripts" / "sync_labels.py"
_H2T_PYTHON = (
    Path.home() / ".h2t" / "venv" / "Scripts" / "python.exe"
    if sys.platform == "win32"
    else Path.home() / ".h2t" / "venv" / "bin" / "python"
)


def fix_labels(rp: Path, repo_name: str) -> str:
    python = str(_H2T_PYTHON) if _H2T_PYTHON.exists() else sys.executable
    result = subprocess.run(
        [python, str(_SYNC_LABELS_SCRIPT), repo_name, "--apply"],
        capture_output=True, text=True, cwd=str(rp),
    )
    if result.returncode == 0:
        return f"labels synced for {repo_name}"
    return f"label sync failed: {result.stderr.strip()[:120]}"


def _get_git_head(rp: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(rp), "rev-parse", "--short", "HEAD"],
        capture_output=True, text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def _resolve_root(root_arg: str | None) -> Path:
    if root_arg:
        return Path(root_arg).resolve()
    root = git_repo_root()
    if root:
        return root
    # No git, or not a repository. The name walk stays as a second answer, because a
    # plain directory tree can still be one of the known repositories.
    cwd = Path.cwd()
    for part in [cwd] + list(cwd.parents):
        if part.name in REPO_MANIFEST:
            return part
    return cwd


def _repo_name_from_root(rp: Path) -> str:
    return rp.name


def _extra_doc_dirs(rp: Path, cfg: dict) -> list[str]:
    """Doc directories this repository is allowed beyond the required set.

    The repository answers first, through `extra_doc_dirs` in its own docs-lint config.
    The bundled table is consulted only for the three private repositories that predate
    the key — a stranger's repository could not appear in it at any value, so the table
    alone made the question unanswerable for everyone else.
    """
    declared = cfg.get("extra_doc_dirs") or []
    if declared:
        return [str(d) for d in declared]
    return REPO_EXTRA_DIRS.get(_repo_name_from_root(rp), [])


def _collect_all_findings(rp: Path, no_pymarkdown: bool = False) -> list[dict]:
    """Run all checks and return findings list (navigation first, metadata last)."""
    cfg = load_config(rp)
    exclude_dirs = cfg.get("exclude_dirs") or []
    naming_exceptions = cfg.get("naming_exceptions") or []
    all_findings = []
    all_findings.extend(find_orphan_files(rp, exclude_dirs=exclude_dirs))
    all_findings.extend(check_naming_all_docs(rp, exclude_dirs=exclude_dirs, naming_exceptions=naming_exceptions))
    extra = _extra_doc_dirs(rp, cfg)
    # Coerce to str | None — YAML could set template to a non-string value
    _raw = cfg.get("template")
    template = _raw if isinstance(_raw, str) and _raw.strip() else None
    typed_msgs = check_project_structure_typed(rp, template) if template else []
    for msg in (
        check_structure(rp)
        + typed_msgs
        + check_adr_naming(rp, exclude_dirs=exclude_dirs)
        + check_legacy_dirs(rp, extra_dirs=extra)
        + check_data_docs_boundary(rp, exclude_dirs=exclude_dirs)
        + check_repo_root(rp)
        + ([] if no_pymarkdown else run_pymarkdownlnt(rp, exclude_dirs=exclude_dirs))
    ):
        f = finding("structure", "warn", "", msg)
        if template and "(template:" in msg:
            f["template"] = template
        all_findings.append(f)
    for msg in check_frontmatter(rp, exclude_dirs=exclude_dirs):
        path = msg.split(":")[0].strip() if ":" in msg else ""
        all_findings.append(finding("frontmatter", "info", path, msg))

    if _PROJECT_LAYER_AVAILABLE and cfg.get("project_checks"):
        custom_root_dirs = cfg.get("custom_root_dirs") or []
        all_findings.extend(check_root_structure(rp, template=template, custom_root_dirs=custom_root_dirs))
        if template:
            all_findings.extend(check_root_readmes(rp, template))
        all_findings.extend(check_gitignore_hygiene(rp))
        all_findings.extend(check_agent_instructions(rp))

    if _MISPLACED_FILES_AVAILABLE and cfg.get("project_checks"):
        deliverables_dir = cfg.get("deliverables_dir", "deliverables")
        all_findings.extend(
            check_misplaced_deliverables(rp, deliverables_dir, exclude_dirs=exclude_dirs)
        )

    # Post-processing pipeline
    # 1. Severity normalization (warn/info → important/low)
    _normalize_severities(all_findings)
    # 2. Vendor path filter — by path field AND by message content
    all_findings = [
        f for f in all_findings
        if not _is_vendor_path(f.get("path", ""))
        and not (not f.get("path") and _is_vendor_message(f.get("message", "")))
    ]
    # 3. Exception filter (dict and string exceptions)
    cfg_exceptions = cfg.get("exceptions") or []
    all_findings = _apply_exceptions(all_findings, cfg_exceptions)
    # 4. Dimension cap (exception warnings appended after cap so they survive)
    all_findings, totals = _cap_by_dimension(all_findings)
    # 5. Truncation notices — one finding per capped dimension, so a partial list
    #    says so in every surface, the JSON envelope included.
    for dim, total in sorted(totals.items()):
        shown = sum(1 for f in all_findings if f["type"] == dim)
        if total > shown:
            note = finding(
                "truncated", "low", "",
                f"{dim}: {total} found, {shown} listed — "
                f"{total - shown} not shown (per-dimension cap {_DIM_LIMIT})",
            )
            note["dimension"] = dim
            note["total"] = total
            note["shown"] = shown
            all_findings.append(note)
    # 6. Exception warnings — appended AFTER cap so they are never dropped
    from docs.config import get_exception_warnings
    all_findings.extend(get_exception_warnings(cfg_exceptions, rp))
    return all_findings


def _dimension_counts(findings: list[dict], dim: str) -> tuple[int, int]:
    """(total found, actually listed) for one finding type.

    Two things make this more than len(): a dimension may be capped, and step 6
    of the collector appends exception warnings *after* the cap under the type
    `structure`. So the list can hold more entries than the notice's `shown`,
    and deriving the hidden count from len() subtracts those late arrivals from
    it — under-reporting, and once there are enough of them, dropping the "this
    list is partial" line entirely (codex [P2]).

    Hidden comes from the notice, which recorded it at cap time; listed is
    whatever is in hand now; total is the two added back together.
    """
    present = sum(1 for f in findings if f.get("type") == dim)
    for f in findings:
        if f.get("type") == "truncated" and f.get("dimension") == dim:
            hidden = int(f.get("total", present)) - int(f.get("shown", present))
            return present + hidden, present
    return present, present


def _dimension_total(findings: list[dict], dim: str) -> int:
    """Total found for one type. "Project Layer" sums five of them; a default of
    0 for the uncapped four made the group report only the capped one."""
    return _dimension_counts(findings, dim)[0]


def _run_audit(rp: Path, no_pymarkdown: bool = False) -> None:
    print_header(f"docs-lint audit: {rp}")
    all_findings = _collect_all_findings(rp, no_pymarkdown=no_pymarkdown)

    orphans   = [f for f in all_findings if f["type"] == "orphan"]
    naming    = [f for f in all_findings if f["type"] == "naming"]
    structure = [f for f in all_findings if f["type"] == "structure"]
    frontmatter = [f for f in all_findings if f["type"] == "frontmatter"]
    project   = [f for f in all_findings if f["type"] in _PROJECT_TYPES]

    def _fmt(f: dict) -> str:
        sev = f.get("severity", "low").upper()[:4]
        path = f.get("path", "")
        msg = f.get("message", "")
        return f"  [{sev}] {path}: {msg}" if path else f"  [{sev}] {msg}"

    sections = [
        ("Navigation / Orphans", orphans, ["orphan"]),
        ("Naming", naming, ["naming"]),
        ("Structure", structure, ["structure"]),
        ("Metadata / Frontmatter", frontmatter, ["frontmatter"]),
        ("Project Layer", project, _PROJECT_TYPES),
    ]
    total = 0
    for title, items, dims in sections:
        if not items:
            continue
        counts = [_dimension_counts(all_findings, d) for d in dims]
        full = sum(c[0] for c in counts)
        listed = sum(c[1] for c in counts)
        # The header carries what was found; the list carries what fits.
        print(f"\n--- {title} ({full}) ---")
        for item in items:
            print(_fmt(item))
        if full > listed:
            print(f"  ... {full - listed} more not listed (per-dimension cap {_DIM_LIMIT})")
        total += full

    print(f"\n{'=' * 60}")
    if total:
        print(f"  RESULT: {total} finding(s) — run 'docs-lint plan' for cleanup steps")
        sys.exit(1)
    else:
        print("  RESULT: all checks passed")


def _run_plan(
    rp: Path,
    json_output: bool = False,
    save_file: str | None = None,
) -> None:
    all_findings = _collect_all_findings(rp, no_pymarkdown=True)

    if json_output or save_file:
        from docs.fix_plan import build_fix_plan
        plan = build_fix_plan(repo_root=str(rp), findings=all_findings)
        output = json.dumps(plan, indent=2)
        if save_file:
            Path(save_file).write_text(output, encoding="utf-8")
            print(f"Plan saved: {save_file}")
            return
        print(output)
        return

    print_header(f"docs-lint plan: {rp}")
    orphans = [f for f in all_findings if f["type"] == "orphan"]
    naming = [f for f in all_findings if f["type"] == "naming"]
    structure = [f for f in all_findings if f["type"] == "structure"]
    misplaced = [f for f in all_findings if f["type"] == "misplaced_deliverable"]
    project = [f for f in all_findings if f["type"] in {
        "root_structure", "root_readmes", "gitignore_hygiene", "agent_instructions"
    }]

    def _elided(items: list[dict], dims: list[str]) -> None:
        """Say what the cap left out. A partial worklist that looks complete is
        worse than a long one: it is finished when it is not."""
        counts = [_dimension_counts(all_findings, d) for d in dims]
        full, listed = sum(c[0] for c in counts), sum(c[1] for c in counts)
        if full > listed:
            print(f"\n  ... {full - listed} more not listed "
                  f"(per-dimension cap {_DIM_LIMIT}) — this list is partial.")

    if orphans:
        print("\n## Orphan Files (not linked from any README/index)\n")
        for f in orphans:
            print(f"  - {f['path']}")
        _elided(orphans, ["orphan"])
        print("\n  Action: link from a relevant README, move to archive/, or delete after review.")

    if naming:
        print("\n## Naming Convention Fixes\n")
        for f in naming:
            fix = f.get("safe_fix", "")
            print(f"  - {f['path']}: {f['message']}")
            if fix:
                print(f"    -> {fix}")
        _elided(naming, ["naming"])

    if structure:
        print("\n## Structure Issues\n")
        for f in structure:
            print(f"  - {f['message']}")
        _elided(structure, ["structure"])

    if misplaced:
        print("\n## Misplaced Deliverable Files\n")
        for f in misplaced:
            tracked_note = "" if f.get("is_tracked") else " (untracked — move manually)"
            print(f"  - {f['path']} -> {f['target_path']}{tracked_note}")
        _elided(misplaced, ["misplaced_deliverable"])
        print("\n  Action: run 'docs-lint fix-safe' to git mv tracked files.")

    if project:
        print("\n## Project Layer\n")
        for f in project:
            print(f"  - [{f['type']}] {f['path']}: {f['message']}")
        _elided(project, [t for t in _PROJECT_TYPES if t != "misplaced_deliverable"])

    if not orphans and not naming and not structure and not misplaced and not project:
        print("\n  No cleanup needed.")
    else:
        print("\n  Run 'docs-lint fix-safe' for auto-fixable items.")
        print("  Run 'docs-lint fix-index' for README/index rebuild.")


def _apply_misplaced_moves(rp: Path, cfg: dict) -> list[str]:
    """Detect misplaced deliverable files and git mv tracked ones."""
    if not _MISPLACED_FILES_AVAILABLE:
        return []
    deliverables_dir = cfg.get("deliverables_dir", "deliverables")
    # Same exclusion as the audit. A fixer that moves what the reporter has
    # stopped reporting is worse than either behaviour on its own.
    findings = check_misplaced_deliverables(
        rp, deliverables_dir, exclude_dirs=cfg.get("exclude_dirs") or [],
    )
    fixes: list[str] = []
    for f in findings:
        if not f.get("is_tracked"):
            fixes.append(f"SKIP: {f['path']} is untracked — move manually with: git mv")
            continue
        tgt_path = f.get("target_path", "")
        dst = rp / tgt_path
        if not dst.parent.exists():
            fixes.append(f"SKIP: {f['path']} — target dir missing: {tgt_path.split('/')[0]}/")
            continue
        src = rp / f["path"]
        if dst.exists():
            fixes.append(f"SKIP: {f['path']} — destination already exists: {tgt_path}")
            continue
        result = subprocess.run(
            ["git", "mv", str(src), str(dst)],
            cwd=str(rp), capture_output=True, text=True,
        )
        if result.returncode == 0:
            fixes.append(f"git mv {f['path']} -> {tgt_path}")
        else:
            fixes.append(f"FAILED: git mv {f['path']}: {result.stderr.strip()[:80]}")
    return fixes


def _run_fix_safe(rp: Path, only: str = "all", plan_file: str | None = None) -> None:
    if plan_file:
        import time

        from docs.apply_report import action_result, build_apply_report, file_hash

        plan = json.loads(Path(plan_file).read_text())
        results = []
        for act in plan["actions"]:
            if act.get("risk") in {"review", "destructive"} or act.get("requires_confirmation"):
                results.append(action_result(act["action_id"], "waived",
                                             "skipped: requires_confirmation or risk > safe"))
                continue
            bh = file_hash(rp / act.get("path", "")) if act.get("path") else ""
            try:
                _apply_safe_action(rp, act)
                # move_file: after-hash is at target_path (src is gone after git mv)
                _hash_path = act.get("target_path") if act.get("type") == "move_file" else act.get("path", "")
                ah = file_hash(rp / _hash_path) if _hash_path else ""
                results.append(action_result(act["action_id"], "applied",
                                             before_hash=bh, after_hash=ah))
            except Exception as exc:
                results.append(action_result(act["action_id"], "failed", str(exc),
                                             before_hash=bh))
        report = build_apply_report(plan_id=plan["plan_id"],
                                    run_id=f"fix-safe-{int(time.time())}",
                                    actions=results)
        report_dir = rp / ".h2t"
        report_dir.mkdir(exist_ok=True)
        ts = int(time.time())
        report_path = report_dir / f"lint-apply-{ts}.json"
        report_path.write_text(json.dumps(report, indent=2))
        print(f"Apply report: {report_path}")
        return

    print_header(f"docs-lint fix-safe [{only}]: {rp}")
    if only in ("all", "dirs"):
        fixes = fix_structure(rp)
        for f in fixes:
            print(f"  FIX: {f}")
    if only in ("all", "frontmatter"):
        fixes = fix_frontmatter_action(
            rp, exclude_dirs=load_config(rp).get("exclude_dirs") or [],
        )
        for f in fixes:
            print(f"  FIX: {f}")
    if _PROJECT_LAYER_AVAILABLE:
        _cfg = load_config(rp)
        if _cfg.get("project_checks") and only in ("all", "moves"):
            gi_fixes = fix_gitignore_hygiene(rp)
            for fx in gi_fixes:
                print(f"  FIX: {fx}")
            move_fixes = _apply_misplaced_moves(rp, _cfg)
            for fx in move_fixes:
                print(f"  FIX: {fx}")
    print("  Done.")


def _apply_safe_action(rp: Path, act: dict) -> None:
    """Apply a single safe action from a fix plan."""
    action_type = act.get("type", "")
    path = act.get("path", "")
    if action_type == "create_dir":
        (rp / path).mkdir(parents=True, exist_ok=True)
    elif action_type == "add_frontmatter":
        target = rp / path
        if target.exists():
            fix_frontmatter_action_single(rp, target)
    elif action_type == "move_file":
        src = rp / path
        dst = rp / (act.get("target_path") or "")
        if src.exists() and dst.parent.exists() and not dst.exists():
            subprocess.run(
                ["git", "mv", str(src), str(dst)],
                cwd=str(rp), check=True, capture_output=True,
            )


def fix_frontmatter_action_single(rp: Path, md_file: Path) -> None:
    """Apply frontmatter fix to a single file (used by plan mode)."""
    rel = str(md_file.relative_to(rp)).replace("\\", "/")
    for dir_pattern, required_fields in FRONTMATTER_RULES.items():
        if dir_pattern not in rel or not required_fields:
            continue
        text = md_file.read_text(encoding="utf-8", errors="replace")
        fm = parse_frontmatter(text)
        if fm is not None and all(f in fm for f in required_fields):
            return
        missing = [f for f in required_fields if not (fm and f in fm)]
        if fm is not None and text.startswith("---"):
            parts = text.split("---", 2)
            if len(parts) >= 3:
                fm_block = parts[1].rstrip("\n")
                body = parts[2]
                extra = "\n".join(
                    f"{f}: {_frontmatter_value(f, md_file, text, rp)}" for f in missing
                )
                new_text = "---\n" + fm_block.lstrip("\n") + "\n" + extra + "\n---" + body
            else:
                return
        else:
            lines = ["---"]
            for f in required_fields:
                lines.append(f"{f}: {_frontmatter_value(f, md_file, text, rp)}")
            lines += ["---", ""]
            body_text = text if not text.startswith("---") else text
            new_text = "\n".join(lines) + body_text
        import tempfile as _tmpmod
        with _tmpmod.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=md_file.parent, delete=False, suffix=".tmp"
        ) as tf:
            tf.write(new_text)
            tmp = tf.name
        try:
            os.replace(tmp, md_file)
        except Exception:
            Path(tmp).unlink(missing_ok=True)
            raise
        break


def _safe_generate(repo_root: Path, repo_name: str) -> str:
    """Generate index content, falling back gracefully if docs-index script is unavailable."""
    # Try the canonical docs-index script first
    _index_dir = Path(__file__).resolve().parents[3] / "skills" / "docs-index" / "scripts"
    if _index_dir.exists():
        _orig_path = list(sys.path)
        try:
            if str(_index_dir) not in sys.path:
                sys.path.insert(0, str(_index_dir))
            from index import build_navigation_index  # noqa: PLC0415
            cfg = load_config(repo_root)
            return build_navigation_index(
                repo_root, repo_name, exclude_dirs=cfg.get("exclude_dirs")
            )
        except ImportError:
            # Only "the generator is not shipped here" falls back. Any other
            # error is a real defect, and swallowing it would replace a live
            # index with the two-line stub below on --apply.
            sys.path[:] = _orig_path
    # Fallback: minimal stub index
    return f"# {repo_name} Documentation Index\n\n> Auto-generated by docs-lint fix-index\n"


def _run_fix_index(rp: Path, apply: bool = False, plan_file: str | None = None) -> None:
    if plan_file and apply:
        import time

        from docs.apply_report import action_result, build_apply_report

        plan = json.loads(Path(plan_file).read_text())
        index_actions = [a for a in plan["actions"] if a.get("type") == "add_to_index"]
        results = []
        repo_name = _repo_name_from_root(rp)
        try:
            report = write_index(rp, repo_name, apply=True, generate=_safe_generate)
            for act in index_actions:
                results.append(action_result(act["action_id"], "applied"))
            if not index_actions:
                results.append(action_result("index-rebuild", "applied", "README index rebuilt"))
        except Exception as exc:
            for act in index_actions:
                results.append(action_result(act["action_id"], "failed", str(exc)))

        apply_report = build_apply_report(
            plan_id=plan["plan_id"],
            run_id=f"fix-index-{int(time.time())}",
            actions=results,
        )
        report_dir = rp / ".h2t"
        report_dir.mkdir(exist_ok=True)
        ts = int(time.time())
        (report_dir / f"lint-apply-{ts}.json").write_text(json.dumps(apply_report, indent=2))
        return

    repo_name = _repo_name_from_root(rp)
    mode = "APPLY" if apply else "DRY-RUN"
    print_header(f"docs-lint fix-index [{mode}]: {rp}")
    report = write_index(rp, repo_name, apply=apply, generate=_safe_generate)
    print(f"  operation: {report['operation']}")
    print(f"  has_markers: {report['has_markers']}")
    print(f"  readme_path: {report['readme_path']}")
    print(f"  status: {report['status']}")
    if not apply and not report["has_markers"]:
        print("  Note: README has no markers — run with --apply to append index section.")


def _run_doctor(rp: Path, json_output: bool = False, no_pymarkdown: bool = False) -> None:
    all_findings = _collect_all_findings(rp, no_pymarkdown=no_pymarkdown)
    status = status_from_findings(all_findings)
    orphans = [f for f in all_findings if f["type"] == "orphan"]
    naming = [f for f in all_findings if f["type"] == "naming"]
    structure = [f for f in all_findings if f["type"] == "structure"]
    frontmatter = [f for f in all_findings if f["type"] == "frontmatter"]
    project = [f for f in all_findings if f["type"] in _PROJECT_TYPES]

    def _full(items: list[dict], dims: list[str]) -> int:
        return sum(_dimension_total(all_findings, d) for d in dims)

    n_orphans = _full(orphans, ["orphan"])
    n_naming = _full(naming, ["naming"])
    n_structure = _full(structure, ["structure"])
    n_frontmatter = _full(frontmatter, ["frontmatter"])
    n_project = _full(project, _PROJECT_TYPES)
    total = n_orphans + n_naming + n_structure + n_frontmatter + n_project
    summary = (
        f"{n_orphans} orphan(s), {n_naming} naming issue(s), "
        f"{n_structure} structure issue(s), {n_frontmatter} metadata issue(s), "
        f"{n_project} project issue(s)"
    )
    safe_next = "Run 'docs-lint plan' for cleanup plan" if total else "No issues found"
    report = build_report(
        command="docs-lint doctor",
        repo_root=str(rp),
        status=status,
        summary=summary,
        findings=all_findings,
        safe_next_action=safe_next,
        git_head=_get_git_head(rp),
    )

    if json_output:
        print(json.dumps(report, indent=2))
    else:
        print_header(f"docs-lint doctor: {rp}")
        print(f"  status: {status}")
        print(f"  {summary}")
        if total:
            sys.exit(1)


def _detect_current_repo() -> str | None:
    cwd = Path.cwd()
    for part in [cwd] + list(cwd.parents):
        if part.name in REPO_MANIFEST:
            return part.name
    return None


def _legacy_main(args: argparse.Namespace) -> None:
    if args.repos:
        targets = args.repos
    elif args.all:
        targets = REPO_MANIFEST
    else:
        detected = _detect_current_repo()
        if detected:
            targets = [detected]
        else:
            _run_audit(Path.cwd())
            return

    print_header(f"docs-lint: checking {len(targets)} repos")
    projects = _load_projects_yaml()

    print("\n--- Global Standards ---")
    std_dir = standards_dir()
    std_fails = [f for f in STANDARDS_FILES if not (std_dir / f).exists()]
    if std_fails:
        for f in std_fails:
            print(f"  FAIL: missing {f}")
    else:
        print(f"  OK: all {len(STANDARDS_FILES)} standards files present")

    total_failures = len(std_fails)

    for name in targets:
        rp = repo_path(name)
        if not rp.exists():
            print(f"\n--- {name} ---\n  SKIP: repo not found at {rp}")
            continue
        print(f"\n--- {name} ---")
        _legacy_exclude = load_config(rp).get("exclude_dirs") or []

        if args.fix:
            fixes = fix_structure(rp)
            for f in fixes:
                print(f"  FIX: {f}")
        if args.fix_frontmatter:
            fixes = fix_frontmatter_action(rp, exclude_dirs=_legacy_exclude)
            for f in fixes:
                print(f"  FIX: {f}")

        extra = _extra_doc_dirs(rp, load_config(rp))
        failures = (
            check_structure(rp)
            + check_adr_naming(rp, exclude_dirs=_legacy_exclude)
            + check_legacy_dirs(rp, extra_dirs=extra)
            + check_naming_conventions(rp)
            + check_frontmatter(rp, exclude_dirs=_legacy_exclude)
            + check_data_docs_boundary(rp, exclude_dirs=_legacy_exclude)
            + check_projects_yaml(rp, name, projects)
            + (check_repo_root(rp) if args.repo_root else [])
            + ([] if args.no_pymarkdown else run_pymarkdownlnt(rp, exclude_dirs=_legacy_exclude))
        )
        if failures:
            for f in failures:
                print(f"  FAIL: {f}")
            total_failures += len(failures)
        else:
            print("  OK: all checks passed")

        if args.fix_labels:
            msg = fix_labels(rp, name)
            print(f"  FIX-LABELS: {msg}")

    print(f"\n{'=' * 60}")
    if total_failures:
        print(f"  RESULT: {total_failures} issue(s) found")
        sys.exit(1)
    else:
        print(f"  RESULT: all {len(targets)} repos compliant")


def _run_new(raw: list[str]) -> None:
    """Create a plan/spec/adr file with correct frontmatter (`docs-lint new`)."""
    from docs.new_doc import create_doc

    p = argparse.ArgumentParser(prog="docs-lint new")
    p.add_argument("_new")  # consumes the 'new' token
    p.add_argument("kind", choices=["plan", "spec", "adr"])
    p.add_argument("slug", help="short kebab/free-text name (normalized to a slug)")
    p.add_argument("--milestone", default="", help="milestone tag, e.g. M3 (plans/specs)")
    p.add_argument("--title", default=None, help="override the derived H1/title")
    p.add_argument("--root", default=None)
    args = p.parse_args(raw)
    rp = _resolve_root(args.root)
    today = datetime.date.today().isoformat()
    try:
        path = create_doc(
            rp, args.kind, args.slug,
            today=today, milestone=args.milestone, title=args.title,
        )
    except FileExistsError as e:
        print(f"ERROR: file already exists: {e}", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(2)
    rel = str(path.relative_to(rp)).replace("\\", "/")
    print(f"created: {rel}")


def _run_retire(
    rp: Path, apply: bool = False, stale_days: int = 60, json_output: bool = False,
    never_shipped: bool = False,
) -> None:
    """List stale plans/specs, and with --apply move them into docs/archive/.

    Listing exits 0 even when there are candidates: this is a maintenance
    command, not a gate. Making it exit non-zero would put it in the same class
    as `doctor` and it would end up wired into CI, where a judgement call that
    needs a person does not belong.
    """
    cfg = load_config(rp)
    candidates = find_retire_candidates(
        rp, stale_days=stale_days, exclude_dirs=cfg.get("exclude_dirs"),
        never_shipped=never_shipped,
    )

    if json_output:
        results = retire_files(rp, candidates) if apply else candidates
        print(json.dumps({"candidates": results}, ensure_ascii=False, indent=2))
        return

    if not candidates:
        print(f"retire: нет открытых plan/spec старше {stale_days} дней.")
        return

    if not apply:
        never = sum(1 for c in candidates if not c["work_commits"])
        print(f"retire: {len(candidates)} кандидатов старше {stale_days} дней\n")
        print(f"{'возраст':>8}  {'правок':>7}  {'с кодом':>8}  {'статус':<12}  файл")
        for c in candidates:
            print(
                f"{c['age_days']:>6}д  {c['commits']:>7}  {c['work_commits']:>8}  "
                f"{c['status']:<12}  {c['path']}"
            )
        print(
            f"\nс кодом = 0: документ ни разу не выходил в одном коммите с кодом — "
            f"план писали, ничего не выкатили. Таких {never} из {len(candidates)}.\n"
            f"'правок' считает и коммит создания, и массовые прогоны docs-lint, "
            f"поэтому сам по себе ничего не говорит.\n"
            f"Переместить в docs/archive/: docs-lint retire --apply"
            f"{' --never-shipped' if never_shipped else ''}"
        )
        return

    results = retire_files(rp, candidates)
    moved = [r for r in results if r["status"] == "moved"]
    for r in results:
        if r["status"] != "moved":
            print(f"  ПРОПУЩЕН {r['path']}: {r.get('reason', '')}")
    print(f"retire: перемещено {len(moved)} из {len(results)} в docs/archive/.")
    print("Файлы в индексе git — проверьте `git status` и закоммитьте.")
    if moved:
        # docs/README.md still links every moved file by its old path.
        print("docs/README.md ссылается на старые пути: docs-lint fix-index --apply")


def main() -> None:
    raw = sys.argv[1:]

    legacy_flags = {"--fix", "--fix-frontmatter"}
    is_legacy_flags = bool(set(raw) & legacy_flags)

    first_pos = next((a for a in raw if not a.startswith("-")), None)
    is_subcommand = first_pos in _SUBCOMMANDS

    if is_legacy_flags:
        if "--root" in raw:
            print(
                "ERROR: '--root' is incompatible with deprecated '--fix'/'--fix-frontmatter'. "
                "Use 'docs-lint fix-safe --root PATH' instead.",
                file=sys.stderr,
            )
            sys.exit(1)
        for flag in legacy_flags & set(raw):
            if flag == "--fix":
                print(
                    "DEPRECATED: '--fix' is deprecated. Use 'docs-lint fix-safe' instead. "
                    "Will be removed in v2.",
                    file=sys.stderr,
                )
            if flag == "--fix-frontmatter":
                print(
                    "DEPRECATED: '--fix-frontmatter' is deprecated. "
                    "Use 'docs-lint fix-safe --only=frontmatter' instead. Will be removed in v2.",
                    file=sys.stderr,
                )
        parser = argparse.ArgumentParser()
        parser.add_argument("repos", nargs="*")
        parser.add_argument("--all", action="store_true")
        parser.add_argument("--fix", action="store_true")
        parser.add_argument("--fix-frontmatter", dest="fix_frontmatter", action="store_true")
        parser.add_argument("--fix-labels", dest="fix_labels", action="store_true")
        parser.add_argument("--no-pymarkdown", dest="no_pymarkdown", action="store_true")
        parser.add_argument("--repo-root", dest="repo_root", action="store_true")
        args = parser.parse_args(raw)
        _legacy_main(args)
        return

    if first_pos == "new":
        _run_new(raw)
        return

    if is_subcommand or (first_pos is None and "--root" in raw):
        parser = argparse.ArgumentParser(prog="docs-lint")
        parser.add_argument("command", nargs="?", default="audit",
                            choices=list(_SUBCOMMANDS))
        parser.add_argument("--root", default=None)
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--only", default="all", choices=["all", "frontmatter", "dirs", "moves"])
        parser.add_argument("--json", dest="json_output", action="store_true")
        parser.add_argument("--save", default=None, metavar="FILE",
                            help="Save fix plan JSON to FILE (plan command only)")
        parser.add_argument("--no-pymarkdown", dest="no_pymarkdown", action="store_true")
        parser.add_argument("--plan", default=None, metavar="FILE")
        parser.add_argument("--older-than", dest="older_than", type=int, default=60,
                            metavar="DAYS",
                            help="retire: age above which an open doc is a candidate")
        parser.add_argument("--never-shipped", dest="never_shipped", action="store_true",
                            help="retire: only docs with no commit that touched them "
                                 "and code together")
        args = parser.parse_args(raw)
        rp = _resolve_root(args.root)

        cmd = args.command or "audit"
        if cmd == "audit":
            _run_audit(rp, no_pymarkdown=args.no_pymarkdown)
        elif cmd == "plan":
            _run_plan(rp, json_output=args.json_output, save_file=args.save)
        elif cmd == "fix-safe":
            _run_fix_safe(rp, only=args.only, plan_file=args.plan)
        elif cmd == "fix-index":
            _run_fix_index(rp, apply=args.apply, plan_file=args.plan)
        elif cmd == "doctor":
            _run_doctor(rp, json_output=args.json_output, no_pymarkdown=args.no_pymarkdown)
        elif cmd == "retire":
            _run_retire(rp, apply=args.apply, stale_days=args.older_than,
                        json_output=args.json_output,
                        never_shipped=args.never_shipped)
        return

    parser = argparse.ArgumentParser()
    parser.add_argument("repos", nargs="*")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--fix", action="store_true")
    parser.add_argument("--fix-frontmatter", dest="fix_frontmatter", action="store_true")
    parser.add_argument("--fix-labels", dest="fix_labels", action="store_true")
    parser.add_argument("--no-pymarkdown", dest="no_pymarkdown", action="store_true")
    parser.add_argument("--repo-root", dest="repo_root", action="store_true")
    parser.add_argument("--root", default=None)
    args = parser.parse_args(raw)
    _legacy_main(args)


if __name__ == "__main__":
    main()
