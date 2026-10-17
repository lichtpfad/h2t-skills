"""inject-h2t-context (SessionStart): the compact h2t skill index, into every session.

Port of the 3.x bash handler. Its Cursor (`additional_context`) and Copilot / no-plugin-root
(`additionalContext` at top level) envelope variants are dropped: spec §4 supports Claude
Code and Codex only, and the channel is chosen by `emit` from the event alone.
"""
from __future__ import annotations

from h2t_ops.hooks.emit import Reply

INDEX = """H2T SKILLS — invoke with the Skill tool when relevant:

Session:   h2t-core:session-start | h2t-core:handoff | h2t-core:init-project | h2t-core:scaffold-project
Setup:     h2t-core:setup           (install, repair, doctor, connector readiness)
Report:    h2t-core:report-issue    (an h2t skill, hook or command is broken → upstream issue, never a local patch)
Research:  h2t-ops:research        (Exa semantic search — use for any web/news/paper lookup)
Connectors: h2t-ops:connectors     (Google, Notion, Telegram, MeetGeek command map and safety)
Daily:     h2t-ops:daily-brief     (daily ops brief from connected sources)
Docs:      h2t-dev:docs-lint | h2t-dev:docs-sync-labels
Diagrams:  h2t-arch:drawio | h2t-arch:diagram-node

Commands:  h2t-ops | h2t-gather | h2t-handoff | h2t-activity-log  (on PATH after 'uv tool install')
Python:    skills resolve their own interpreter — never build a path to one
Config:    ~/.h2t/config/  (domains.yaml, repo-mapping.yaml, secrets/)
Standards: bundled in h2t-dev skill references — load via Read when needed"""

CONTEXT = f"<h2t-context>\n{INDEX}\n</h2t-context>"


def handle(event: dict) -> Reply:
    del event  # the same index for every session
    return Reply(CONTEXT)
