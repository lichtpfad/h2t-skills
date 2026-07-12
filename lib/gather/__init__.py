"""h2t gather framework — parallel context collection for skills."""

from .runner import run_parallel, output_json
from .git import gather_git
from .github import gather_github
from .stack import detect_stack
from .sessions import find_session_files, extract_session_id, get_machine_name
from .project import identify_project
from .user import gather_user_context
from .briefing import format_briefing

__all__ = [
    "run_parallel", "output_json",
    "gather_git", "gather_github",
    "detect_stack",
    "find_session_files", "extract_session_id", "get_machine_name",
    "identify_project", "gather_user_context",
    "format_briefing",
]
