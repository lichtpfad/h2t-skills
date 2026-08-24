#!/usr/bin/env python3
"""PostToolUse hook: a merged PR closes the plans and specs it carried.

Retrospectively this link cannot be recovered. Measured on h2t-skills: a plan
slug appears in 7 of 60 merged PR bodies, and commit counts cannot separate
"done and never updated" from "abandoned" — which is why `docs-lint retire`
leaves the judgement to a person. At the moment of the merge nothing has to be
inferred: `gh pr view` lists the PR's own files, and a plan among them is a plan
that shipped. The link was never hard to compute; it was never written down
while it was still free.

Exit code is always 0. This is bookkeeping after the fact — a failure here must
never look like a failed merge.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

# Only these carry a lifecycle. A report records a moment and is done when
# written; an ADR is a permanent record whose status means something else.
_LIFECYCLE_DIRS = ("docs/superpowers/plans/", "docs/superpowers/specs/")

_CLOSED = {
    "done", "complete", "completed", "accepted", "approved",
    "superseded", "deprecated", "rejected", "archived",
}

# `gh pr merge 408 ...` — the number is the first bare argument after `merge`.
_MERGE = re.compile(r"(?:^|[;&|]\s*)gh\s+pr\s+merge\b(?P<rest>[^;&|]*)")
_STATUS_LINE = re.compile(r"^status:\s*.*$", re.MULTILINE)
_PR_LINE = re.compile(r"^pr:\s*.*$\n?", re.MULTILINE)


def extract_pr_number(command: str) -> int | None:
    """The PR number in a `gh pr merge` command, or None if there is none.

    None also covers `gh pr merge` with no number (the current branch's PR):
    resolving that after the merge is a guess, and the branch may already be
    deleted. A guess here would stamp `status: done` on the wrong plan.
    """
    m = _MERGE.search(command)
    if not m:
        return None
    for token in m.group("rest").split():
        if token.startswith("-"):
            continue
        if token.isdigit():
            return int(token)
        return None
    return None


def _split_frontmatter(text: str) -> tuple[str, str] | None:
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end == -1:
        return None
    close = text.find("\n", end + 1)
    return text[: close + 1], text[close + 1 :]


def close_plans_for_pr(repo_root: Path, pr_number: int, view: dict) -> list[dict]:
    """Stamp `status: done` and `pr: N` on every plan/spec the PR carried.

    Returns what actually changed. An unmerged PR, a file the PR deleted, a doc
    with no frontmatter, and a doc already closed all yield nothing — this runs
    unattended, so every uncertain case must be a no-op rather than a guess.
    """
    if str(view.get("state", "")).upper() != "MERGED":
        return []

    changed: list[dict] = []
    for entry in view.get("files") or []:
        rel = entry.get("path") if isinstance(entry, dict) else str(entry)
        if not rel or not rel.startswith(_LIFECYCLE_DIRS):
            continue
        path = repo_root / rel
        if not path.is_file():
            continue  # the PR deleted or moved it — e.g. retired into archive
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        parts = _split_frontmatter(text)
        if not parts:
            continue
        fm, body = parts

        m = _STATUS_LINE.search(fm)
        if not m:
            continue
        current = m.group(0).split(":", 1)[1].strip().strip('"').strip("'").lower()
        if current in _CLOSED:
            continue

        fm = _STATUS_LINE.sub('status: "done"', fm, count=1)
        fm = _PR_LINE.sub("", fm)
        fm = fm.replace('status: "done"', f'status: "done"\npr: {pr_number}', 1)
        try:
            path.write_text(fm + body, encoding="utf-8")
        except OSError:
            continue
        changed.append({"path": rel, "was": current})
    return changed


def _pr_view(repo_root: Path, pr_number: int) -> dict:
    try:
        out = subprocess.run(
            ["gh", "pr", "view", str(pr_number), "--json", "state,files"],
            capture_output=True, text=True, timeout=30, cwd=str(repo_root),
        )
    except (OSError, subprocess.SubprocessError):
        return {}
    if out.returncode != 0:
        return {}
    try:
        return json.loads(out.stdout)
    except json.JSONDecodeError:
        return {}


def _load_payload() -> dict:
    try:
        raw = sys.stdin.read()
        return json.loads(raw) if raw.strip() else {}
    except Exception:
        return {}


def main() -> int:
    payload = _load_payload()
    if payload.get("tool_name") != "Bash":
        return 0

    command = (payload.get("tool_input") or {}).get("command", "")
    pr_number = extract_pr_number(command)
    if pr_number is None:
        return 0

    repo_root = Path.cwd().resolve()
    changed = close_plans_for_pr(repo_root, pr_number, _pr_view(repo_root, pr_number))
    if not changed:
        return 0

    # Last two segments, not the basename: a plan and its spec share a stem,
    # so basenames alone print the same name twice.
    names = ", ".join("/".join(Path(c["path"]).parts[-2:]) for c in changed)
    lines = [f"  {c['path']}: {c['was']} → done" for c in changed]
    # Two channels, two readers: additionalContext reaches the model, systemMessage
    # is the line the user sees in the TUI.
    print(json.dumps({
        "systemMessage": (
            f"PR #{pr_number} закрыл {len(changed)} документ(ов): {names}. "
            f"Изменения не закоммичены."
        ),
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": (
                f"PR #{pr_number} merged. Статус проставлен автоматически:\n"
                + "\n".join(lines)
                + "\nФайлы изменены локально и не закоммичены — включите их в "
                  "следующий коммит или закоммитьте отдельно."
            ),
        },
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
