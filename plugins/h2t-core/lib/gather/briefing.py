"""Format gathered context into a ready-to-display briefing."""

import re
from datetime import datetime


def format_briefing(data: dict) -> tuple[str, dict]:
    """Take gather JSON, return (briefing_markdown, meta_dict).

    data keys: project, git, github, stack, sessions, machine, user, session_id
    """
    project = data.get("project", {})
    git = data.get("git", {})
    github = data.get("github", {})
    stack = data.get("stack", {})
    sessions = data.get("sessions", [])
    latest_session = data.get("latest_session")
    machine = data.get("machine", "")
    user = data.get("user", {})
    session_id = data.get("session_id", "")

    slug = _build_slug_template(project, github)
    md = _build_markdown(project, git, github, stack, sessions, latest_session)
    hints = _build_hints(data)
    if hints:
        md += "\n### Hints\n"
        for h in hints:
            md += f"- {h}\n"

    meta = {
        "slug_template": slug,
        "project": project,
        "user": user,
        "sessions": sessions,
        "machine": machine,
        "session_id": session_id,
    }

    return md.rstrip("\n") + "\n", meta


def _build_markdown(
    project: dict,
    git: dict,
    github: dict,
    stack: dict,
    sessions: list,
    latest_session: dict | None = None,
) -> str:
    branch = git.get("branch", "")
    pid = project.get("id", "unknown")
    lines: list[str] = []

    # Header
    lines.append(f"## Сессия: {pid} (`{branch}`)\n")

    # Stack
    stack_name = stack.get("name", "none")
    if stack_name and stack_name != "none":
        lines.append(f"**Stack:** {stack_name}")

    # Milestone with progress bar
    ms = github.get("current_milestone")
    if ms:
        title = ms.get("title", "")
        open_c = ms.get("open", 0)
        closed_c = ms.get("closed", 0)
        total = open_c + closed_c
        pct = int(closed_c / total * 100) if total else 0
        filled = pct // 5  # 20 chars wide
        bar = "\u2593" * filled + "\u2591" * (20 - filled)
        deadline = ms.get("dueOn") or ms.get("due_on", "")
        deadline_str = f" \u2014 due {deadline[:10]}" if deadline else ""
        lines.append(f"**Milestone:** {title}{deadline_str}")
        lines.append(f"`[{bar}]` {pct}% ({closed_c}/{total})")

    lines.append("")

    # Tasks
    tasks_md = _build_tasks_section(github)
    if tasks_md:
        lines.append(tasks_md)

    # Uncommitted
    status = git.get("status", "")
    if status:
        lines.append("### Незакоммиченное")
        lines.append(f"```\n{status}\n```")

    stash = git.get("stash", "")
    if stash:
        lines.append(f"\n**Stash:** {stash}")

    lines.append("")

    # PRs
    prs = github.get("prs", [])
    if prs:
        lines.append("### Открытые PR")
        for pr in prs:
            num = pr.get("number", "")
            title = pr.get("title", "")
            head = pr.get("headRefName", "")
            lines.append(f"- #{num} {title} (`{head}`)")
        lines.append("")

    # Sessions context
    if sessions:
        lines.append("### Контекст")
        lines.append(f"Handoff-файлы: {len(sessions)}")
        lines.append("")

    previous = _build_previous_session_section(latest_session)
    if previous:
        lines.append(previous)
        lines.append("")

    return "\n".join(lines)


def _build_previous_session_section(latest_session: dict | None) -> str:
    if not isinstance(latest_session, dict):
        return ""

    lines = ["### Previous Session"]
    summary = str(latest_session.get("summary_short", "")).strip()
    if summary:
        lines.append(f"- Summary: {summary}")

    next_actions = latest_session.get("next_actions", [])
    if isinstance(next_actions, list) and next_actions:
        lines.append("- Next:")
        for item in next_actions[:5]:
            text = str(item).strip()
            if text:
                lines.append(f"  - {text}")

    blockers = latest_session.get("blockers", [])
    if isinstance(blockers, list) and blockers:
        lines.append("- Blockers:")
        for item in blockers[:5]:
            text = str(item).strip()
            if text:
                lines.append(f"  - {text}")

    artifacts = latest_session.get("artifacts", [])
    if isinstance(artifacts, list) and artifacts:
        refs = []
        for artifact in artifacts[:10]:
            if isinstance(artifact, dict):
                typ = str(artifact.get("type", "artifact")).strip() or "artifact"
                ref = str(artifact.get("ref", "")).strip()
                if ref:
                    refs.append(f"{typ}:{ref}")
        if refs:
            lines.append(f"- Artifacts: {', '.join(refs)}")

    if len(lines) == 1:
        return ""
    text = "\n".join(lines)
    if len(text) <= 1800:
        return text
    marker = "\n- [previous session truncated]"
    return text[: 1800 - len(marker)].rstrip() + marker


def _build_tasks_section(github: dict) -> str:
    """Build tasks section as table from milestone_issues or issues."""
    mi = github.get("milestone_issues", [])
    issues = mi if mi else github.get("issues", [])
    bugs_set = {b.get("number") for b in github.get("bugs", [])}

    if not issues:
        return ""

    lines = ["### Задачи", ""]
    lines.append("| # | Title | Tags |")
    lines.append("|---|-------|------|")
    for iss in issues:
        num = iss.get("number", "")
        title = iss.get("title", "")
        labels = {lab.get("name", "") if isinstance(lab, dict) else lab for lab in iss.get("labels", [])}
        tags = []
        if num in bugs_set or "bug" in labels:
            tags.append("\U0001f41b BUG")
        if "priority:p0" in labels:
            tags.append("\U0001f534 P0")
        elif "priority:p1" in labels:
            tags.append("\U0001f7e1 P1")
        for lab in sorted(labels):
            if lab.startswith("domain:"):
                tags.append(lab.replace("domain:", ""))
            elif lab.startswith("phase:"):
                tags.append(lab.replace("phase:", ""))
        tag_str = ", ".join(tags) if tags else ""
        lines.append(f"| #{num} | {title} | {tag_str} |")
    return "\n".join(lines)


def _build_slug_template(project: dict, github: dict) -> str:
    """Build slug template: {project}-{milestone}-{task}-{date}-{time}."""
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H%M")

    pid = project.get("id", "project")
    ms = github.get("current_milestone") if github else None

    parts = [pid]
    if ms:
        short = _shorten_milestone(ms.get("title", ""))
        if short:
            parts.append(short)
    parts.append("{task}")
    parts.append(date_str)
    parts.append(time_str)

    return "-".join(parts)


def _shorten_milestone(title: str) -> str:
    """Shorten milestone title for slug.

    'Phase 5' -> 'p5', 'Фаза 3' -> 'p3', 'v3.0' -> 'v3', short strings kept.
    """
    if not title:
        return ""
    # Phase N / Фаза N
    m = re.match(r"(?:phase|фаза)\s+(\d+)", title, re.IGNORECASE)
    if m:
        return f"p{m.group(1)}"
    # vX.Y -> vX
    m = re.match(r"(v\d+)", title, re.IGNORECASE)
    if m:
        return m.group(1).lower()
    # Short title — use as-is, slugified
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", title).strip("-").lower()
    return slug[:12] if slug else ""


def _build_hints(data: dict) -> list[str]:
    """Generate actionable hints for missing data."""
    hints = []
    project = data.get("project", {})
    github = data.get("github", {})
    sessions = data.get("sessions", [])
    stack = data.get("stack", {})

    ptype = project.get("type", "")

    # Workspace
    if ptype == "workspace":
        children = project.get("children", [])
        names = ", ".join(c.get("id", "") for c in children)
        hints.append(f"Workspace с {len(children)} проектами ({names}). Какой проект сегодня?")
        return hints  # workspace — no other hints relevant

    # Unknown project (default fallback)
    if project.get("id") == "unknown":
        hints.append("Repo не зарегистрирован. Запусти `/h2t:init-project` для регистрации.")

    # GitHub: a source that did not answer is not a repo without work
    if github and project.get("github"):
        if github.get("failed"):
            hints.append(
                "GitHub не ответил ({}). Задачи и PR в брифинге неполны — это отказ "
                "источника, а не пустой бэклог. Проверь `gh auth status` и повтори."
                .format(", ".join(github["failed"]))
            )
        elif not github.get("issues") and not github.get("milestone_issues"):
            hints.append("Нет открытых issues. Создай задачи через `gh issue create` или GitHub UI.")

    # No sessions
    if not sessions:
        hints.append("Нет предыдущих сессий. Свежий старт.")

    # Stack none
    if stack.get("name") == "none" or not stack.get("name"):
        hints.append("Stack не определён. Проверь наличие package.json / pyproject.toml / Cargo.toml / go.mod.")

    return hints
