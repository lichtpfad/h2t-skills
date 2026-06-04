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
    DEV_ROOT, REPO_MANIFEST, REQUIRED_CORE_DIRS, REPO_EXTRA_DIRS, STANDARDS_FILES,
    FRONTMATTER_RULES, ensure_dir, print_header, repo_path, parse_frontmatter,
)
from docs.orphan import find_orphan_files
from docs.naming import check_naming_all_docs
from docs.reporter import build_report, status_from_findings, finding
from docs.config import load_config
from docs.index_builder import write_index

try:
    from docs.project_types import PROJECT_TYPES
    _PROJECT_TYPES_AVAILABLE = True
except ImportError:
    PROJECT_TYPES = {}
    _PROJECT_TYPES_AVAILABLE = False

try:
    from docs.root_structure import check_root_structure, check_root_readmes
    from docs.gitignore_hygiene import check_gitignore_hygiene, fix_gitignore_hygiene
    from docs.agent_instructions import check_agent_instructions
    _PROJECT_LAYER_AVAILABLE = True
except ImportError as _e:
    import warnings as _warnings
    _warnings.warn(
        f"docs-lint project layer unavailable (import failed: {_e}). "
        "Run: uv tool install --editable C:/dev/h2t-skills",
        RuntimeWarning, stacklevel=1,
    )
    _PROJECT_LAYER_AVAILABLE = False

try:
    from docs.misplaced_files import check_misplaced_deliverables
    _MISPLACED_FILES_AVAILABLE = True
except ImportError:
    _MISPLACED_FILES_AVAILABLE = False

_SUBCOMMANDS = frozenset({"audit", "plan", "fix-safe", "fix-index", "doctor"})

PROJECTS_YAML_PATH = DEV_ROOT / "h2t-landings" / "projects.yaml"

YAML_FLAG_CHECKS: dict[str, str] = {
    "docs.positioning": "docs/product/positioning.md",
    "docs.eval_report": "docs/reports",
    "docs.marketing_docs": "docs/marketing",
}


def _load_projects_yaml() -> dict:
    if not PROJECTS_YAML_PATH.exists():
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


def check_adr_naming(rp: Path) -> list[str]:
    failures = []
    adr_dir = rp / "docs" / "adr"
    if not adr_dir.exists():
        return failures
    for adr in adr_dir.glob("[0-9]*.md"):
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


def check_data_docs_boundary(rp: Path) -> list[str]:
    failures = []
    docs_dir = rp / "docs"
    if docs_dir.exists():
        for f in docs_dir.rglob("*"):
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


def check_frontmatter(rp: Path) -> list[str]:
    failures = []
    docs_dir = rp / "docs"
    if not docs_dir.exists():
        return failures
    for md_file in docs_dir.rglob("*.md"):
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


def run_pymarkdownlnt(rp: Path) -> list[str]:
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
    if result.returncode != 0:
        out = result.stdout + result.stderr
        lines = [ln for ln in out.splitlines() if ln.strip()]
        return [f"pymarkdownlnt: {ln}" for ln in lines[:20]]
    return []


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
    lines = [l.strip() for l in result.stdout.splitlines() if l.strip()]
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


def fix_frontmatter_action(rp: Path) -> list[str]:
    """Add only missing required frontmatter fields. Preserves existing keys."""
    fixes = []
    docs_dir = rp / "docs"
    if not docs_dir.exists():
        return fixes
    for md_file in docs_dir.rglob("*.md"):
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
def fix_frontmatter(rp: Path) -> list[str]:
    """Legacy wrapper: delegates to fix_frontmatter_action."""
    return fix_frontmatter_action(rp)


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
    cwd = Path.cwd()
    for part in [cwd] + list(cwd.parents):
        if part.name in REPO_MANIFEST:
            return part
    return cwd


def _repo_name_from_root(rp: Path) -> str:
    return rp.name


def _collect_all_findings(rp: Path, no_pymarkdown: bool = False) -> list[dict]:
    """Run all checks and return findings list (navigation first, metadata last)."""
    cfg = load_config(rp)
    exclude_dirs = cfg.get("exclude_dirs") or []
    naming_exceptions = cfg.get("naming_exceptions") or []
    all_findings = []
    all_findings.extend(find_orphan_files(rp, exclude_dirs=exclude_dirs))
    all_findings.extend(check_naming_all_docs(rp, exclude_dirs=exclude_dirs, naming_exceptions=naming_exceptions))
    extra = REPO_EXTRA_DIRS.get(_repo_name_from_root(rp), [])
    # Coerce to str | None — YAML could set template to a non-string value
    _raw = cfg.get("template")
    template = _raw if isinstance(_raw, str) and _raw.strip() else None
    typed_msgs = check_project_structure_typed(rp, template) if template else []
    for msg in (
        check_structure(rp)
        + typed_msgs
        + check_adr_naming(rp)
        + check_legacy_dirs(rp, extra_dirs=extra)
        + check_data_docs_boundary(rp)
        + check_repo_root(rp)
        + ([] if no_pymarkdown else run_pymarkdownlnt(rp))
    ):
        f = finding("structure", "warn", "", msg)
        if template and "(template:" in msg:
            f["template"] = template
        all_findings.append(f)
    for msg in check_frontmatter(rp):
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
        all_findings.extend(check_misplaced_deliverables(rp, deliverables_dir))

    return all_findings


def _run_audit(rp: Path, no_pymarkdown: bool = False) -> None:
    repo_name = _repo_name_from_root(rp)
    print_header(f"docs-lint audit: {rp}")

    cfg = load_config(rp)
    exclude_dirs = cfg.get("exclude_dirs") or []
    naming_exceptions = cfg.get("naming_exceptions") or []
    orphans = find_orphan_files(rp, exclude_dirs=exclude_dirs)
    naming = check_naming_all_docs(rp, exclude_dirs=exclude_dirs, naming_exceptions=naming_exceptions)
    extra = REPO_EXTRA_DIRS.get(repo_name, [])
    _raw = cfg.get("template")
    template = _raw if isinstance(_raw, str) and _raw.strip() else None
    typed_msgs = check_project_structure_typed(rp, template) if template else []
    structure_msgs = (
        check_structure(rp)
        + typed_msgs
        + check_adr_naming(rp)
        + check_legacy_dirs(rp, extra_dirs=extra)
        + check_data_docs_boundary(rp)
        + check_repo_root(rp)
        + ([] if no_pymarkdown else run_pymarkdownlnt(rp))
    )
    frontmatter_msgs = check_frontmatter(rp)

    sections = [
        ("Navigation / Orphans", orphans, lambda f: f"  WARN: [{f['type']}] {f['path']} — {f['message']}"),
        ("Naming", naming, lambda f: f"  WARN: [{f['type']}] {f['path']} — {f['message']}"),
        ("Structure", [finding("structure", "warn", "", m) for m in structure_msgs],
         lambda f: f"  WARN: {f['message']}"),
        ("Metadata / Frontmatter", [finding("frontmatter", "info", m.split(":")[0].strip() if ":" in m else "", m) for m in frontmatter_msgs],
         lambda f: f"  INFO: {f['message']}"),
    ]

    if _PROJECT_LAYER_AVAILABLE and cfg.get("project_checks"):
        custom_root_dirs = cfg.get("custom_root_dirs") or []
        _deliverables_dir = cfg.get("deliverables_dir", "deliverables")
        project_findings = (
            check_root_structure(rp, template=template, custom_root_dirs=custom_root_dirs)
            + (check_root_readmes(rp, template) if template else [])
            + check_gitignore_hygiene(rp)
            + check_agent_instructions(rp)
            + (check_misplaced_deliverables(rp, _deliverables_dir) if _MISPLACED_FILES_AVAILABLE else [])
        )
    else:
        project_findings = []
    sections.append(
        ("Project Layer", project_findings,
         lambda f: f"  {f['severity'].upper()}: [{f['type']}] {f['path']} — {f['message']}"),
    )

    total = 0
    for section_name, items, fmt in sections:
        if items:
            print(f"\n--- {section_name} ({len(items)}) ---")
            for item in items:
                print(fmt(item))
            total += len(items)

    print(f"\n{'=' * 60}")
    if total:
        print(f"  RESULT: {total} finding(s) — run 'docs-lint plan' for cleanup steps")
        sys.exit(1)
    else:
        print("  RESULT: all checks passed")


def _run_plan(rp: Path, json_output: bool = False) -> None:
    all_findings = _collect_all_findings(rp, no_pymarkdown=True)

    if json_output:
        from docs.fix_plan import build_fix_plan
        plan = build_fix_plan(repo_root=str(rp), findings=all_findings)
        print(json.dumps(plan, indent=2))
        return

    print_header(f"docs-lint plan: {rp}")
    orphans = [f for f in all_findings if f["type"] == "orphan"]
    naming = [f for f in all_findings if f["type"] == "naming"]
    structure = [f for f in all_findings if f["type"] == "structure"]
    project = [f for f in all_findings if f["type"] in {
        "root_structure", "root_readmes", "gitignore_hygiene", "agent_instructions"
    }]

    if orphans:
        print("\n## Orphan Files (not linked from any README/index)\n")
        for f in orphans:
            print(f"  - {f['path']}")
        print("\n  Action: link from a relevant README, move to archive/, or delete after review.")

    if naming:
        print("\n## Naming Convention Fixes\n")
        for f in naming:
            fix = f.get("safe_fix", "")
            print(f"  - {f['path']}: {f['message']}")
            if fix:
                print(f"    → {fix}")

    if structure:
        print("\n## Structure Issues\n")
        for f in structure:
            print(f"  - {f['message']}")

    if project:
        print("\n## Project Layer\n")
        for f in project:
            print(f"  - [{f['type']}] {f['path']}: {f['message']}")

    if not orphans and not naming and not structure and not project:
        print("\n  No cleanup needed.")
    else:
        print(f"\n  Run 'docs-lint fix-safe' for auto-fixable items.")
        print(f"  Run 'docs-lint fix-index' for README/index rebuild.")


def _apply_misplaced_moves(rp: Path, cfg: dict) -> list[str]:
    """Detect misplaced deliverable files and git mv tracked ones."""
    if not _MISPLACED_FILES_AVAILABLE:
        return []
    deliverables_dir = cfg.get("deliverables_dir", "deliverables")
    findings = check_misplaced_deliverables(rp, deliverables_dir)
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
            fixes.append(f"git mv {f['path']} → {tgt_path}")
        else:
            fixes.append(f"FAILED: git mv {f['path']}: {result.stderr.strip()[:80]}")
    return fixes


def _run_fix_safe(rp: Path, only: str = "all", plan_file: str | None = None) -> None:
    if plan_file:
        from docs.fix_plan import build_fix_plan
        from docs.apply_report import build_apply_report, action_result, file_hash
        import time

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
        fixes = fix_frontmatter_action(rp)
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
            return build_navigation_index(repo_root, repo_name)
        except Exception:
            sys.path[:] = _orig_path
    # Fallback: minimal stub index
    return f"# {repo_name} Documentation Index\n\n> Auto-generated by docs-lint fix-index\n"


def _run_fix_index(rp: Path, apply: bool = False, plan_file: str | None = None) -> None:
    if plan_file and apply:
        from docs.apply_report import build_apply_report, action_result
        import time

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
    project = [f for f in all_findings if f["type"] in {
        "root_structure", "root_readmes", "gitignore_hygiene", "agent_instructions"
    }]
    total = len(all_findings)
    summary = (
        f"{len(orphans)} orphan(s), {len(naming)} naming issue(s), "
        f"{len(structure)} structure issue(s), {len(frontmatter)} metadata issue(s), "
        f"{len(project)} project issue(s)"
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
    std_dir = DEV_ROOT / "docs" / "standards"
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

        if args.fix:
            fixes = fix_structure(rp)
            for f in fixes:
                print(f"  FIX: {f}")
        if args.fix_frontmatter:
            fixes = fix_frontmatter_action(rp)
            for f in fixes:
                print(f"  FIX: {f}")

        extra = REPO_EXTRA_DIRS.get(name, [])
        failures = (
            check_structure(rp)
            + check_adr_naming(rp)
            + check_legacy_dirs(rp, extra_dirs=extra)
            + check_naming_conventions(rp)
            + check_frontmatter(rp)
            + check_data_docs_boundary(rp)
            + check_projects_yaml(rp, name, projects)
            + (check_repo_root(rp) if args.repo_root else [])
            + ([] if args.no_pymarkdown else run_pymarkdownlnt(rp))
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

    if is_subcommand or (first_pos is None and "--root" in raw):
        parser = argparse.ArgumentParser(prog="docs-lint")
        parser.add_argument("command", nargs="?", default="audit",
                            choices=list(_SUBCOMMANDS))
        parser.add_argument("--root", default=None)
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--only", default="all", choices=["all", "frontmatter", "dirs"])
        parser.add_argument("--json", dest="json_output", action="store_true")
        parser.add_argument("--no-pymarkdown", dest="no_pymarkdown", action="store_true")
        parser.add_argument("--plan", default=None, metavar="FILE")
        args = parser.parse_args(raw)
        rp = _resolve_root(args.root)

        cmd = args.command or "audit"
        if cmd == "audit":
            _run_audit(rp, no_pymarkdown=args.no_pymarkdown)
        elif cmd == "plan":
            _run_plan(rp, json_output=args.json_output)
        elif cmd == "fix-safe":
            _run_fix_safe(rp, only=args.only, plan_file=args.plan)
        elif cmd == "fix-index":
            _run_fix_index(rp, apply=args.apply, plan_file=args.plan)
        elif cmd == "doctor":
            _run_doctor(rp, json_output=args.json_output, no_pymarkdown=args.no_pymarkdown)
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
