"""Single source of truth: skill name → class → eval_set_id.

Classes: gather | integration | prompt. Used by SkillEval to pick the per-class
eval_set. Free-string eval_set (no registration) → no VPS precondition (#309).
"""

_GATHER = {
    "session-start", "handoff", "init-project",
    "scaffold-project", "project-audit", "setup", "agent-profile", "autonomous-run",
}
_INTEGRATION = {
    "connectors", "drive", "meetgeek", "research", "telegram",
    "docs-lint", "docs-init", "docs-index", "docs-sync-labels",
    "milestone-closure", "drawio",
    "convert-meeting-transcript", "process-transcripts", "youtube-transcript",
    "gmail", "notion", "calendar", "daily-brief",
}


def skill_class(skill: str) -> str:
    if skill in _GATHER:
        return "gather"
    if skill in _INTEGRATION:
        return "integration"
    return "prompt"


def eval_set_for(skill: str) -> str:
    return f"skills-{skill_class(skill)}-baseline-v1"
