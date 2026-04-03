"""
scan.py — Stage 1 of /project-audit pipeline.
Collects deterministic facts about a repo. No LLM needed.

Usage:
    python scan.py <repo_path> [--projects-yaml <path>]

Output: JSON to stdout (scan_result.json schema)
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


def run(cmd: list[str], cwd: str, timeout: int = 10) -> str:
    try:
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return ""


def check_file(repo: Path, *names: str) -> bool:
    for name in names:
        if (repo / name).exists():
            return True
    return False


def check_dir(repo: Path, name: str) -> bool:
    return (repo / name).is_dir()


def detect_language(repo: Path) -> str:
    markers = {
        "python": ["pyproject.toml", "setup.py", "setup.cfg", "requirements.txt"],
        "javascript": ["package.json"],
        "rust": ["Cargo.toml"],
        "go": ["go.mod"],
    }
    for lang, files in markers.items():
        for f in files:
            if (repo / f).exists():
                return lang
    return "unknown"


def count_commits(repo: Path) -> int:
    out = run(["git", "rev-list", "--count", "HEAD"], cwd=str(repo))
    return int(out) if out.isdigit() else 0


def recent_commits(repo: Path, n: int = 20) -> list[dict]:
    out = run(
        ["git", "log", f"-{n}", "--format=%H|%ai|%s"],
        cwd=str(repo),
    )
    if not out:
        return []
    commits = []
    for line in out.splitlines():
        parts = line.split("|", 2)
        if len(parts) == 3:
            commits.append({"hash": parts[0][:8], "date": parts[1][:10], "message": parts[2]})
    return commits


def open_issues(repo: Path) -> list[dict]:
    out = run(
        ["gh", "issue", "list", "--state", "open", "--limit", "10", "--json", "number,title,labels"],
        cwd=str(repo),
        timeout=15,
    )
    if not out:
        return []
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return []


def read_head(path: Path, max_lines: int = 30) -> str:
    if not path.exists():
        return ""
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()[:max_lines]
        return "\n".join(lines)
    except Exception:
        return ""


def gh_repo_slug(repo: Path) -> str:
    """Extract owner/repo from git remote."""
    out = run(["git", "remote", "get-url", "origin"], cwd=str(repo))
    if not out:
        return ""
    # Handle both HTTPS and SSH URLs
    for prefix in ["https://github.com/", "git@github.com:"]:
        if out.startswith(prefix):
            slug = out[len(prefix):]
            return slug.removesuffix(".git")
    return ""


def gh_releases(repo: Path) -> list[dict]:
    """Get GitHub releases with asset names."""
    slug = gh_repo_slug(repo)
    cmd = ["gh", "release", "list", "--limit", "5", "--json", "tagName,name,publishedAt,isLatest"]
    if slug:
        cmd.extend(["--repo", slug])
    out = run(cmd, cwd=str(repo), timeout=15)
    if not out:
        return []
    try:
        releases = json.loads(out)
    except json.JSONDecodeError:
        return []

    # Fetch assets for each release
    for r in releases:
        tag = r.get("tagName", "")
        if not tag:
            continue
        view_cmd = ["gh", "release", "view", tag, "--json", "assets"]
        if slug:
            view_cmd.extend(["--repo", slug])
        assets_out = run(view_cmd, cwd=str(repo), timeout=15)
        if assets_out:
            try:
                assets_data = json.loads(assets_out)
                r["asset_names"] = [a.get("name", "") for a in assets_data.get("assets", [])]
            except json.JSONDecodeError:
                r["asset_names"] = []
        else:
            r["asset_names"] = []
    return releases


def landing_content(repo: Path) -> str:
    """Read landing page HTML (first 80 lines) for analysis."""
    candidates = [
        repo / "landing" / "index.html",
        repo / "index.html",
    ]
    for p in candidates:
        if p.exists():
            return read_head(p, max_lines=80)
    return ""


def file_tree(repo: Path, max_depth: int = 2) -> list[str]:
    """Shallow file tree, excluding noise dirs."""
    skip = {".git", "__pycache__", ".venv", "venv", "node_modules", "dist",
            "build", ".egg-info", ".mypy_cache", ".pytest_cache", ".ruff_cache"}
    result = []

    def _walk(path: Path, depth: int, prefix: str = ""):
        if depth > max_depth:
            return
        try:
            entries = sorted(path.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower()))
        except PermissionError:
            return
        for entry in entries:
            if entry.name in skip or entry.name.endswith(".egg-info"):
                continue
            rel = str(entry.relative_to(repo))
            if entry.is_dir():
                result.append(f"{rel}/")
                _walk(entry, depth + 1)
            else:
                result.append(rel)

    _walk(repo, 0)
    return result[:60]  # cap to avoid huge output


def load_project_card(projects_yaml: Path, repo_id: str) -> dict | None:
    """Load project card from projects.yaml without PyYAML (stdlib only)."""
    if not projects_yaml.exists():
        return None
    try:
        # Попытка с PyYAML если доступен
        import yaml
        data = yaml.safe_load(projects_yaml.read_text(encoding="utf-8"))
        for proj in data.get("projects", []):
            if proj.get("id") == repo_id:
                return proj
    except ImportError:
        # Fallback: вернуть None, skill прочитает projects.yaml сам
        return None
    except Exception:
        return None
    return None


def scan(repo_path: str, projects_yaml: str | None = None) -> dict:
    repo = Path(repo_path).resolve()
    if not repo.is_dir():
        return {"error": f"Directory not found: {repo}"}

    repo_id = repo.name

    # Projects.yaml card
    card = None
    if projects_yaml:
        card = load_project_card(Path(projects_yaml), repo_id)

    result = {
        "id": repo_id,
        "path": str(repo),
        "has_claude_md": check_file(repo, "CLAUDE.md"),
        "has_readme": check_file(repo, "README.md", "readme.md"),
        "has_tests": check_dir(repo, "tests") or check_dir(repo, "test"),
        "has_docs_dir": check_dir(repo, "docs"),
        "has_examples": check_dir(repo, "examples") or check_dir(repo, "example"),
        "has_license": check_file(repo, "LICENSE", "LICENSE.md", "LICENSE.txt"),
        "has_landing": check_dir(repo, "landing") or check_file(repo, "index.html"),
        "has_ci": check_dir(repo, ".github/workflows"),
        "has_plugin": check_dir(repo, ".claude-plugin") or check_file(repo, "plugin.json"),
        "primary_language": detect_language(repo),
        "commit_count": count_commits(repo),
        "recent_commits": recent_commits(repo),
        "last_commit_date": "",
        "open_issues": open_issues(repo),
        "open_issue_count": 0,
        "readme_head": read_head(repo / "README.md"),
        "claude_md_head": read_head(repo / "CLAUDE.md"),
        "landing_head": landing_content(repo),
        "releases": gh_releases(repo),
        "file_tree": file_tree(repo),
        "existing_card": card,
    }

    # Derived
    if result["recent_commits"]:
        result["last_commit_date"] = result["recent_commits"][0]["date"]
    result["open_issue_count"] = len(result["open_issues"])

    return result


def main():
    parser = argparse.ArgumentParser(description="Scan repo for project-audit pipeline")
    parser.add_argument("repo_path", help="Path to the repository")
    parser.add_argument(
        "--projects-yaml",
        default=None,
        help="Path to projects.yaml (default: C:/dev/h2t-landings/projects.yaml)",
    )
    args = parser.parse_args()

    projects_yaml = args.projects_yaml or "C:/dev/h2t-landings/projects.yaml"
    result = scan(args.repo_path, projects_yaml)
    sys.stdout.reconfigure(encoding="utf-8")
    json.dump(result, sys.stdout, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()
