"""Deterministic audit of .claude/* agent instructions structure (v1 — no LLM)."""
from __future__ import annotations
import re
from pathlib import Path

_REQUIRED_RULES: frozenset[str] = frozenset({"documentation.md", "linting.md"})
_KEBAB_RE = re.compile(r'^[a-z0-9][a-z0-9-]*\.md$')
_CODE_SPAN_RE = re.compile(r'`([^`\n]{4,200})`')
_ABS_PATH_RE = re.compile(r'^[A-Za-z]:[\\/]|^//|^/[A-Za-z]')
_SECTION_RE = re.compile(r'^#{1,3}\s+(Key\s+Commands?|Commands?)\b', re.MULTILINE)


def _extract_absolute_code_span_paths(text: str) -> list[str]:
    """Extract absolute-path strings from backtick code spans."""
    results = []
    for m in _CODE_SPAN_RE.finditer(text):
        s = m.group(1).strip()
        if _ABS_PATH_RE.match(s) and ('/' in s or '\\' in s):
            # Skip POSIX single-segment paths — these are slash commands (/skill, /h2t-ops:cmd),
            # not filesystem paths. Real POSIX paths have at least two segments (/dir/file).
            if s.startswith('/') and not s.startswith('//') and s.count('/') < 2:
                continue
            s = s.rstrip('.,;:)')
            results.append(s)
    return results


def _path_exists(candidate: str) -> bool:
    """Check if an absolute path candidate exists on the filesystem."""
    from pathlib import Path as _Path
    norm = candidate.replace('\\', '/')
    try:
        return _Path(candidate).exists() or _Path(norm).exists()
    except (OSError, ValueError):
        return True  # Treat unparseable paths as non-stale


def check_agent_instructions(rp: Path) -> list[dict]:
    """Deterministic structural checks for .claude/* (v1 — no LLM clarity scoring).

    Checks:
    1. .claude/rules/documentation.md and linting.md present (only when .claude/ exists)
    2. All .claude/rules/*.md filenames are kebab-case
    3. Absolute paths in backtick spans of rules/*.md exist on fs
    4. CLAUDE.md has a 'Key Commands' or 'Commands' section (when CLAUDE.md exists)
    5. Absolute paths in backtick spans of CLAUDE.md exist on fs
    """
    from docs.reporter import finding as make_finding

    findings: list[dict] = []
    claude_dir = rp / ".claude"

    if claude_dir.exists():
        rules_dir = claude_dir / "rules"
        if not rules_dir.exists():
            for req in sorted(_REQUIRED_RULES):
                findings.append(make_finding(
                    "agent_instructions", "warn", f".claude/rules/{req}",
                    f"missing required rules file: .claude/rules/{req} (rules/ dir absent)",
                ))
        else:
            for req in sorted(_REQUIRED_RULES):
                if not (rules_dir / req).exists():
                    findings.append(make_finding(
                        "agent_instructions", "warn", f".claude/rules/{req}",
                        f"missing required rules file: .claude/rules/{req}",
                    ))
            for f in sorted(rules_dir.glob("*.md")):
                if not _KEBAB_RE.match(f.name):
                    findings.append(make_finding(
                        "agent_instructions", "warn", f".claude/rules/{f.name}",
                        f"rules file not kebab-case: {f.name}",
                    ))
            for f in sorted(rules_dir.glob("*.md")):
                text = f.read_text(encoding="utf-8", errors="replace")
                rel = str(f.relative_to(rp)).replace("\\", "/")
                for candidate in _extract_absolute_code_span_paths(text):
                    if not _path_exists(candidate):
                        findings.append(make_finding(
                            "agent_instructions", "info", rel,
                            f"stale path in {rel}: '{candidate}'",
                        ))

    claude_md = rp / "CLAUDE.md"
    if claude_md.exists():
        text = claude_md.read_text(encoding="utf-8", errors="replace")
        if not _SECTION_RE.search(text):
            findings.append(make_finding(
                "agent_instructions", "info", "CLAUDE.md",
                "CLAUDE.md missing 'Key Commands' or 'Commands' section",
            ))
        for candidate in _extract_absolute_code_span_paths(text):
            if not _path_exists(candidate):
                findings.append(make_finding(
                    "agent_instructions", "info", "CLAUDE.md",
                    f"stale path in CLAUDE.md: '{candidate}'",
                ))

    return findings
