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

    # 1. Try git remote
    raw = run_parallel({"remote": ["git", "-C", cwd, "remote", "get-url", "origin"]})
    remote = raw["remote"].strip()
    repo_name = ""
    github_remote = ""

    if remote:
        m = re.search(r"[:/]([^/]+/[^/]+?)(?:\.git)?$", remote)
        if m:
            github_remote = m.group(1)
            repo_name = github_remote.split("/")[-1]

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


def _split_domain_project(value: str) -> tuple[str, str]:
    parts = value.split("/", 1)
    return (parts[0], parts[1]) if len(parts) == 2 else (parts[0], "unknown")


def _find_label(domains: dict, domain: str, project_id: str) -> str:
    domain_data = domains.get("domains", {}).get(domain, {})
    for proj in domain_data.get("projects", []):
        if proj.get("id") == project_id:
            return proj.get("label", project_id)
    return project_id
