"""h2t gather framework — parallel context collection for skills."""

from .briefing import format_briefing
from .git import gather_git
from .github import gather_github
from .project import identify_project
from .runner import output_json, run_parallel
from .sessions import (
    extract_session_id,
    find_latest_session_index,
    find_session_files,
    get_machine_name,
)
from .stack import detect_stack
from .user import gather_user_context

__all__ = [
    "run_parallel", "output_json",
    "gather_git", "gather_github",
    "detect_stack",
    "find_session_files", "find_latest_session_index", "extract_session_id", "get_machine_name",
    "identify_project", "gather_user_context",
    "format_briefing",
]
