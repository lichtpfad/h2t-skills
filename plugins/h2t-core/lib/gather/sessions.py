"""Session file discovery and bounded lifecycle index helpers."""
import json
import os
import platform
from pathlib import Path

SUMMARY_LIMIT = 1200
ITEM_LIMIT = 240
MAX_ITEMS = 5
MAX_ARTIFACTS = 10


def _session_root() -> Path:
    return Path(os.environ.get("H2T_SESSION_ROOT", str(Path.home() / ".h2t" / "sessions")))


def _legacy_session_root() -> Path:
    return Path.home() / ".dor" / "sessions"


def find_session_files(repo_name: str) -> list[str]:
    """Find handoff markdown files across h2t and legacy DOR session roots."""
    files = []
    seen: set[str] = set()
    for sessions_root in (_session_root(), _legacy_session_root()):
        if not sessions_root.exists():
            continue
        for machine_dir in sessions_root.iterdir():
            if not machine_dir.is_dir():
                continue
            repo_dir = machine_dir / repo_name
            if repo_dir.is_dir():
                for f in repo_dir.glob("*.md"):
                    resolved = str(f)
                    if resolved not in seen:
                        seen.add(resolved)
                        files.append(f)
    return [str(f) for f in sorted(files, key=os.path.getmtime, reverse=True)]


def _truncate(text: str, limit: int) -> str:
    text = " ".join(str(text or "").split())
    if len(text) <= limit:
        return text
    marker = " ... [truncated]"
    return text[: max(0, limit - len(marker))].rstrip() + marker


def _bounded_items(values: object, *, limit: int = MAX_ITEMS) -> list[str]:
    if not isinstance(values, list):
        return []
    result = []
    for value in values[:limit]:
        result.append(_truncate(str(value), ITEM_LIMIT))
    return result


def _bounded_artifacts(values: object) -> list[dict]:
    if not isinstance(values, list):
        return []
    result = []
    for value in values[:MAX_ARTIFACTS]:
        if isinstance(value, dict):
            result.append({
                "type": str(value.get("type", "artifact"))[:40],
                "ref": str(value.get("ref", ""))[:240],
            })
        else:
            result.append({"type": "artifact", "ref": str(value)[:240]})
    return result


def _bound_latest_index(data: dict, path: Path) -> dict:
    return {
        "version": int(data.get("version", 1)),
        "session_id": str(data.get("session_id", "")),
        "project": str(data.get("project", "")),
        "domain": str(data.get("domain", "")),
        "updated_at": str(data.get("updated_at", "")),
        "summary_short": _truncate(str(data.get("summary_short", "")), SUMMARY_LIMIT),
        "next_actions": _bounded_items(data.get("next_actions")),
        "blockers": _bounded_items(data.get("blockers")),
        "artifacts": _bounded_artifacts(data.get("artifacts")),
        "markdown_path": str(data.get("markdown_path", "")),
        "index_path": str(path),
        "truncated": bool(data.get("truncated", False)),
    }


def find_latest_session_index(repo_name: str) -> dict | None:
    """Find newest bounded latest.json across canonical h2t session root."""
    root = _session_root()
    if not root.exists():
        return None
    candidates = []
    for machine_dir in root.iterdir():
        if not machine_dir.is_dir():
            continue
        latest = machine_dir / repo_name / "latest.json"
        if latest.is_file():
            candidates.append(latest)
    if not candidates:
        return None
    path = max(candidates, key=os.path.getmtime)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    return _bound_latest_index(data, path)

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
    name = os.environ.get("H2T_MACHINE_NAME") or os.environ.get("DOR_MACHINE_NAME", "")
    if not name:
        name = platform.node().lower().split(".")[0]
    return name
