#!/usr/bin/env python3
"""Detect project type, domain, tracker for init-project skill.

Usage: $H2T_PYTHON detect_project.py --cwd <path> [--config-root <path>]
Outputs JSON to stdout. Config root: --config-root, else $H2T_CONFIG_ROOT, else ~/.h2t/config.
"""
import argparse
import io
import json
import os
import re
import subprocess
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(PLUGIN_ROOT / "lib"))

from gather.stack import detect_stack

# Domain patterns: (regex on normalized forward-slash path, domain, confidence)
DOMAIN_PATTERNS = [
    (r"[Cc]:/dev/h2t-|[Cc]:/dev/hou2touch", "hou2touch", "high", "path C:/dev/h2t-* matches hou2touch"),
    (r"[Cc]:/dev/crypto-", "crypto", "high", "path C:/dev/crypto-* matches crypto"),
    (r"HOU2TOUCH", "hou2touch", "high", "path contains HOU2TOUCH"),
    (r"[Cc]:/dev/", "dev", "medium", "path C:/dev/* suggests dev"),
    (r"Projects/DOR|Projects/newsengine", "personal-os", "high", "known personal-os project path"),
    (r"Projects/crypto-", "crypto", "high", "path ~/Projects/crypto-* matches crypto"),
]

# File extensions that hint at art domain
ART_EXTENSIONS = {".toe", ".hip", ".hiplc", ".hipnc"}


def _detect_type(cwd: str) -> tuple[str, str | None]:
    """Detect project type and github remote.

    Returns: (type, github_owner_repo_or_none)
    """
    git_dir = Path(cwd) / ".git"
    if not git_dir.exists():
        return "directory", None

    # Try to get remote
    try:
        result = subprocess.run(
            ["git", "-C", cwd, "remote", "get-url", "origin"],
            capture_output=True, text=True, timeout=5,
        )
        remote = result.stdout.strip() if result.returncode == 0 else ""
    except (subprocess.TimeoutExpired, FileNotFoundError):
        remote = ""

    if not remote:
        return "git-local", None

    # Parse owner/repo
    m = re.search(r"[:/]([^/]+/[^/]+?)(?:\.git)?$", remote)
    github = m.group(1) if m else None
    return "git", github


def _detect_domain(cwd: str) -> tuple[str | None, str, str]:
    """Detect domain from path patterns.

    Returns: (domain_or_none, confidence, reason)
    """
    # Normalize to forward slashes
    normalized = cwd.replace("\\", "/")

    for pattern, domain, confidence, reason in DOMAIN_PATTERNS:
        if re.search(pattern, normalized):
            return domain, confidence, reason

    # Check for art file extensions
    cwd_path = Path(cwd)
    if cwd_path.is_dir():
        for ext in ART_EXTENSIONS:
            if list(cwd_path.glob(f"*{ext}"))[:1]:
                return "art", "medium", f"found {ext} files suggesting art project"

    return None, "low", f"path {normalized} — no pattern match"


def _detect_tracker(
    github: str | None, domain: str | None, domains_data: dict,
) -> tuple[str | None, str, str]:
    """Detect task tracker. Returns (tracker, confidence, reason).

    If domain is unknown, tracker is deferred.
    """
    if domain is None:
        return None, "deferred", "domain unknown — tracker will be resolved after domain selection"

    # Check if domain has notion_db_id
    domain_info = domains_data.get("domains", {}).get(domain, {})
    has_notion = bool(domain_info.get("notion_db_id"))

    # Check GitHub accessibility
    has_github = False
    if github:
        try:
            result = subprocess.run(
                ["gh", "repo", "view", github, "--json", "name"],
                capture_output=True, text=True, timeout=10,
            )
            has_github = result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            has_github = False

    if has_github and not has_notion:
        return "github", "high", "GitHub remote exists and accessible"
    if has_notion and not has_github:
        return "notion", "high", f"domain {domain} has notion_db_id"
    if has_github and has_notion:
        return None, "low", f"both GitHub and Notion available for domain {domain} — ask user"
    return "none", "high", "no GitHub, no Notion for this domain"


def _humanize_id(project_id: str) -> str:
    """Convert kebab-case id to human label: 'h2t-vision' -> 'H2T Vision'."""
    # Known acronyms to always uppercase
    ACRONYMS = {"h2t", "etl", "api", "cli", "dcc", "lms", "mcp", "ai", "td", "os", "db", "ui", "ux", "ci", "cd"}
    parts = project_id.split("-")
    result = []
    for part in parts:
        lower = part.lower()
        has_digit = any(c.isdigit() for c in part)
        if lower in ACRONYMS or has_digit:
            result.append(part.upper())
        else:
            result.append(part.capitalize())
    return " ".join(result)


def _check_already_registered(
    cwd: str, repo_name: str | None, mapping_data: dict,
) -> dict | None:
    """Check if project is already in repo-mapping.yaml.

    Returns current config dict or None if not registered.
    """
    mappings = mapping_data.get("mappings", {})
    cwd_patterns = mapping_data.get("cwd_patterns", {})

    # Check by repo name in mappings
    if repo_name and repo_name in mappings:
        domain_project = mappings[repo_name]
        parts = domain_project.split("/", 1)
        return {
            "id": parts[1] if len(parts) == 2 else repo_name,
            "domain": parts[0],
            "source": "mappings",
        }

    # Check by cwd in cwd_patterns
    normalized = cwd.replace("\\", "/")
    for pattern, domain_project in cwd_patterns.items():
        if pattern.replace("/", "\\") in normalized or pattern in normalized:
            parts = domain_project.split("/", 1)
            return {
                "id": parts[1] if len(parts) == 2 else "unknown",
                "domain": parts[0],
                "source": "cwd_patterns",
            }

    return None


def _find_label(domains_data: dict, domain: str, project_id: str) -> str | None:
    """Find existing label in domains.yaml."""
    domain_info = domains_data.get("domains", {}).get(domain, {})
    for proj in domain_info.get("projects", []):
        if proj.get("id") == project_id:
            return proj.get("label")
    return None


def _load_yaml(path: Path) -> dict:
    """Load YAML file, return empty dict if missing or no yaml."""
    try:
        import yaml
    except ImportError:
        return {}
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _build_confirm_message(detected: dict, already_registered: bool) -> str:
    """Build the confirm message shown to user."""
    if already_registered:
        cur = detected
        return (
            f"Проект {cur['id']} уже зарегистрирован:\n"
            f"- Домен: {cur['domain']}\n"
            f"- Label: {cur.get('label', cur['id'])}\n\n"
            f"Хочешь обновить настройки?"
        )

    d = detected
    lines = ["Регистрирую проект:\n"]
    lines.append(f"- **ID:** {d['id']}")
    lines.append(f"- **Label:** {d['label']}")

    if d.get("domain"):
        lines.append(f"- **Домен:** {d['domain']}")

    type_str = d["type"]
    if d.get("github"):
        type_str += f" (GitHub: {d['github']})"
    lines.append(f"- **Тип:** {type_str}")

    if d.get("stack") and d["stack"] != "none":
        lines.append(f"- **Stack:** {d['stack']}")

    if d.get("tracker_confidence") == "deferred":
        lines.append("- **Task tracker:** определится после выбора домена")
    elif d.get("task_tracker"):
        lines.append(f"- **Task tracker:** {d['task_tracker']}")

    if d.get("domain"):
        lines.append("\nФайлы:")
        lines.append("- `~/.h2t/config/repo-mapping.yaml` → добавлю mapping")
        lines.append("- `~/.h2t/config/domains.yaml` → добавлю project entry")
        lines.append("\nВсё верно?")
    else:
        # Domain unknown — need to ask
        lines.append("\nНе могу определить домен. Варианты:")
        # List available domains
        lines.append("1. dev")
        lines.append("2. hou2touch")
        lines.append("3. crypto")
        lines.append("4. art")
        lines.append("5. personal-os")
        lines.append("6. admin")
        lines.append("7. другой")
        lines.append("\nКакой домен?")

    return "\n".join(lines)


def _is_workspace(cwd: Path, mapping_data: dict) -> bool:
    """Check if cwd is a workspace (parent of known repos)."""
    mappings = mapping_data.get("mappings", {})
    child_count = sum(
        1 for subdir in cwd.iterdir()
        if subdir.is_dir() and subdir.name in mappings
    ) if cwd.is_dir() else 0
    return child_count >= 3  # arbitrary threshold: 3+ known children = workspace


def _resolve_config_root(config_root: str | None = None) -> Path:
    """Same precedence as gather's identify_project: explicit, env, default."""
    if config_root:
        return Path(config_root).expanduser()
    env = os.environ.get("H2T_CONFIG_ROOT")
    if env:
        return Path(env).expanduser()
    return Path.home() / ".h2t" / "config"


def detect_project(cwd: str, config_root: str | None = None) -> dict:
    """Main detection entry point. Returns full result dict."""
    config_root = _resolve_config_root(config_root)
    mapping_data = _load_yaml(config_root / "repo-mapping.yaml")
    domains_data = _load_yaml(config_root / "domains.yaml")

    cwd_path = Path(cwd).resolve()
    cwd_str = str(cwd_path)

    # Detect type + github
    proj_type, github = _detect_type(cwd_str)

    # Derive repo name from github or dir name
    repo_name = None
    if github:
        repo_name = github.split("/")[-1]
    elif proj_type in ("git", "git-local"):
        repo_name = cwd_path.name

    # Check already registered
    current = _check_already_registered(cwd_str, repo_name, mapping_data)
    if current:
        label = _find_label(domains_data, current["domain"], current["id"])
        current["label"] = label or _humanize_id(current["id"])
        return {
            "already_registered": True,
            "current": current,
            "confirm_message": _build_confirm_message(current, already_registered=True),
        }

    # Reject workspace
    if _is_workspace(cwd_path, mapping_data):
        return {
            "error": f"Это workspace ({cwd_str}), не проект. cd в конкретный проект.",
        }

    # Detect domain
    domain, domain_confidence, domain_reason = _detect_domain(cwd_str)

    # Detect stack
    stack = detect_stack(cwd_str)
    stack_name = stack.get("name", "none")

    # Project id
    project_id = repo_name or cwd_path.name

    # Label
    label = _find_label(domains_data, domain, project_id) if domain else None
    if not label:
        label = _humanize_id(project_id)

    # Detect tracker (deferred if domain unknown)
    tracker, tracker_confidence, tracker_reason = _detect_tracker(
        github, domain, domains_data,
    )

    # Build needs_input
    input_fields = []
    if domain_confidence != "high":
        input_fields.append("domain")
    if tracker_confidence == "low":
        input_fields.append("task_tracker")

    detected = {
        "id": project_id,
        "type": proj_type,
        "github": github,
        "stack": stack_name,
        "domain": domain,
        "domain_confidence": domain_confidence,
        "domain_reason": domain_reason,
        "label": label,
        "task_tracker": tracker,
        "tracker_confidence": tracker_confidence,
        "tracker_reason": tracker_reason,
    }

    return {
        "detected": detected,
        "already_registered": False,
        "needs_input": bool(input_fields),
        "input_fields": input_fields,
        "confirm_message": _build_confirm_message(detected, already_registered=False),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cwd", default=".")
    parser.add_argument("--config-root", default=None)
    args = parser.parse_args()

    result = detect_project(args.cwd, args.config_root)
    # UTF-8 output on Windows (avoid cp1252 encoding errors)
    out = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", newline="")
    json.dump(result, out, ensure_ascii=False, indent=2)
    out.write("\n")
    out.flush()
    out.detach()


if __name__ == "__main__":
    main()
