"""Session file discovery and session ID extraction."""
import os, platform
from pathlib import Path

def find_session_files(repo_name: str) -> list[str]:
    """Find session handoff files across all machines: ~/.dor/sessions/*/{repo}/*.md"""
    sessions_root = Path.home() / ".dor" / "sessions"
    if not sessions_root.exists():
        return []
    files = []
    for machine_dir in sessions_root.iterdir():
        if not machine_dir.is_dir():
            continue
        repo_dir = machine_dir / repo_name
        if repo_dir.is_dir():
            files.extend(str(f) for f in sorted(repo_dir.glob("*.md"), key=os.path.getmtime, reverse=True))
    return files

def extract_session_id(memory_dir: str | None = None) -> str:
    """Extract Claude session ID from newest .jsonl file in memory_dir parent."""
    if not memory_dir:
        return ""
    project_dir = Path(memory_dir).parent
    if not project_dir.exists():
        return ""
    jsonl_files = sorted(project_dir.glob("*.jsonl"), key=os.path.getmtime, reverse=True)
    return jsonl_files[0].stem if jsonl_files else ""

def get_machine_name() -> str:
    name = os.environ.get("DOR_MACHINE_NAME", "")
    if not name:
        name = platform.node().lower().split(".")[0]
    return name
