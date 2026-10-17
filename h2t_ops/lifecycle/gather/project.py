"""Project identity — resolve project from any directory.

Uses ~/.h2t/config/repo-mapping.yaml for git repos and cwd pattern matching.
Uses ~/.h2t/config/domains.yaml for domain metadata.
"""

from pathlib import Path

from .runner import run_parallel

try:
    import yaml
except ImportError:
    yaml = None


def _get_config_root() -> Path:
    import os
    env = os.environ.get("H2T_CONFIG_ROOT")
    if env:
        return Path(env)
    return Path.home() / ".h2t" / "config"


def _load_yaml(path: Path) -> dict:
    if yaml is None or not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def identify_project(cwd: str = ".") -> dict:
    """Identify project from any directory.

    Resolution order:
    0. <cwd>/.claude/project-id — identity that travels with the checkout
    1. git remote → repo-mapping.yaml mappings
    2. cwd path → repo-mapping.yaml cwd_patterns
    3. default from repo-mapping.yaml

    Returns: {id, domain, label, type, github, config_root}
    """
    import re

    cwd_abs = str(Path(cwd).resolve())
    config_root = _get_config_root()
    mapping = _load_yaml(config_root / "repo-mapping.yaml")
    domains = _load_yaml(config_root / "domains.yaml")

    mappings = mapping.get("mappings", {})
    cwd_patterns = mapping.get("cwd_patterns", {})
    default = mapping.get("default", "dev/unknown")

    # The remote is parsed before every rung: rung 0 returns early, and a project
    # identified from its file still needs the GitHub slug — gather.py skips
    # gather_github entirely when project['github'] is falsy, so dropping it here
    # silently empties issues, milestones and PRs for exactly the registered repos.
    raw = run_parallel({"remote": ["git", "-C", cwd, "remote", "get-url", "origin"]})
    remote = (raw["remote"] or "").strip()
    repo_name = ""
    github_remote = ""

    if remote:
        m = re.search(r"[:/]([^/]+/[^/]+?)(?:\.git)?$", remote)
        if m:
            github_remote = m.group(1)
            repo_name = github_remote.split("/")[-1]

    # 0. .claude/project-id — written by init-project, and until now read by nobody.
    # It comes first because it is the only answer that travels with the checkout: a
    # clone on a machine with no repo-mapping.yaml, or a repo renamed since it was
    # mapped, resolves to "unknown" through every other rung.
    pid_file = _find_project_id_file(Path(cwd_abs))
    if pid_file is not None:
        try:
            pid_raw = pid_file.read_text(encoding="utf-8").strip()
        except OSError:
            pid_raw = ""
        if pid_raw:
            if "/" in pid_raw:
                domain, project_id = _split_domain_project(pid_raw)
            else:
                # Every file written so far holds a bare id; the domain is looked up.
                domain, project_id = "", pid_raw
            if not domain:
                domain = _domain_for_project(domains, project_id) or "dev"
            project_root = pid_file.parent.parent
            return {
                "id": project_id, "domain": domain,
                "label": _find_label(domains, domain, project_id),
                "type": "git" if (project_root / ".git").exists() else "directory",
                "github": github_remote or None, "config_root": str(config_root),
            }

    # 1. Map the remote through repo-mapping.yaml
    if remote:
        if repo_name in mappings:
            domain, project_id = _split_domain_project(mappings[repo_name])
            label = _find_label(domains, domain, project_id)
            return {
                "id": project_id, "domain": domain, "label": label,
                "type": "git", "github": github_remote,
                "config_root": str(config_root),
            }

    # 2. Try cwd_patterns
    for pattern, domain_project in cwd_patterns.items():
        if pattern.replace("/", "\\") in cwd_abs.replace("/", "\\"):
            domain, project_id = _split_domain_project(domain_project)
            label = _find_label(domains, domain, project_id)
            return {
                "id": project_id, "domain": domain, "label": label,
                "type": "directory", "github": github_remote or None,
                "config_root": str(config_root),
            }

    # 3. Check if cwd is a workspace (parent of known repos)
    cwd_path = Path(cwd_abs)
    child_projects = []
    if cwd_path.is_dir():
        for subdir in cwd_path.iterdir():
            if subdir.is_dir() and subdir.name in mappings:
                dp = mappings[subdir.name]
                d, p = _split_domain_project(dp)
                child_projects.append({
                    "id": p, "domain": d, "path": str(subdir),
                    "label": _find_label(domains, d, p),
                })

    if child_projects:
        return {
            "id": "workspace", "domain": "dev",
            "label": f"Workspace ({len(child_projects)} projects)",
            "type": "workspace",
            "github": None,
            "config_root": str(config_root),
            "children": child_projects,
        }

    # 4. Default
    domain, project_id = _split_domain_project(default)
    return {
        "id": project_id, "domain": domain, "label": project_id,
        "type": "git" if remote else "directory",
        "github": github_remote or None,
        "config_root": str(config_root),
    }


def _find_project_id_file(start: Path):
    """Walk up from `start` looking for `.claude/project-id`.

    Callers pass `$PWD`, which is usually a subdirectory of the checkout, so checking
    only `start` would miss the file that sits at the repository root. The walk stops at
    that root: a `project-id` above a repository describes a different project, and
    inheriting it would name the wrong one. Outside a repository the home directory is
    the ceiling, for the same reason.
    """
    home = Path.home().resolve()
    current = start
    while True:
        candidate = current / ".claude" / "project-id"
        if candidate.is_file():
            return candidate
        if (current / ".git").exists() or current == home or current == current.parent:
            return None
        current = current.parent


def _split_domain_project(value: str) -> tuple[str, str]:
    parts = value.split("/", 1)
    return (parts[0], parts[1]) if len(parts) == 2 else (parts[0], "unknown")


def _domain_for_project(domains: dict, project_id: str) -> str:
    """Which domain claims this project id, or "" when none does."""
    for domain, domain_data in (domains.get("domains") or {}).items():
        for proj in (domain_data or {}).get("projects", []):
            if proj.get("id") == project_id:
                return domain
    return ""


def _find_label(domains: dict, domain: str, project_id: str) -> str:
    domain_data = domains.get("domains", {}).get(domain, {})
    for proj in domain_data.get("projects", []):
        if proj.get("id") == project_id:
            return proj.get("label", project_id)
    return project_id
