#!/usr/bin/env python3
"""PostToolUse git commit hook: run docs-lint doctor when docs markdown changed."""
from __future__ import annotations

import datetime
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

SCHEMA = "h2t_lifecycle_report/v0.1"
SCHEMA_VERSION = "0.1"
HOOK_NAME = "PostToolUse:git-commit:docs-lint"
COMMAND = "post-git-commit-docs-lint"


def is_git_commit_payload(payload: dict[str, Any]) -> bool:
    if payload.get("tool_name") not in {"Bash", "shell_command"}:
        return False
    tool_input = payload.get("tool_input") or payload.get("parameters") or {}
    command = str(tool_input.get("command", ""))
    try:
        parts = shlex.split(command)
    except ValueError:
        return False
    if not parts or parts[0].lower() != "git":
        return False
    i = 1
    while i < len(parts):
        token = parts[i].lower()
        if token == "commit":
            return True
        if token in {"-c", "-C", "--git-dir", "--work-tree"}:
            i += 2
            continue
        if token.startswith("-"):
            i += 1
            continue
        return False
    return False


def changed_docs_from_head(repo_root: Path) -> list[str]:
    result = subprocess.run(
        ["git", "-C", str(repo_root), "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        return []
    changed = []
    for raw in result.stdout.splitlines():
        path = raw.strip().replace("\\", "/")
        if path.startswith("docs/") and path.endswith(".md"):
            changed.append(path)
    return changed


def find_docs_lint_script() -> Path | None:
    env = os.environ.get("H2T_DOCS_LINT_SCRIPT")
    if env and Path(env).is_file():
        return Path(env)

    candidates = [
        Path.cwd() / "plugins" / "h2t-dev" / "skills" / "docs-lint" / "scripts" / "lint.py",
        Path.home() / ".claude" / "plugins" / "cache" / "lichtpfad" / "h2t-dev" / "latest" / "skills" / "docs-lint" / "scripts" / "lint.py",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def run_docs_lint_doctor(repo_root: Path, lint_script: Path, *, timeout: int) -> dict[str, Any]:
    try:
        result = subprocess.run(
            [sys.executable, str(lint_script), "doctor", "--root", str(repo_root), "--json"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "status": "error",
            "message": "hook timeout",
            "stdout": (exc.stdout or "")[-1000:],
            "stderr": (exc.stderr or "")[-1000:],
        }
    if result.returncode != 0:
        return {
            "status": "error",
            "exit_code": result.returncode,
            "stdout": result.stdout[-2000:],
            "stderr": result.stderr[-2000:],
        }
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {
            "status": "error",
            "message": "docs-lint produced invalid JSON",
            "stdout": result.stdout[-2000:],
        }


def build_hook_report(
    *,
    repo_root: Path,
    status: str,
    changed_docs: list[str],
    docs_lint: dict[str, Any] | None,
    message: str,
) -> dict[str, Any]:
    now = datetime.datetime.utcnow().isoformat() + "Z"
    return {
        "schema": SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "command": COMMAND,
        "producer": "h2t-core/post-git-commit-docs-lint",
        "produced_at": now,
        "repo_root": str(repo_root),
        "status": status,
        "summary": message,
        "findings": [],
        "safe_next_action": "Run docs-lint plan --root . if docs health warnings matter before merge",
        "evidence": {
            "hook": HOOK_NAME,
            "changed_docs": changed_docs,
            "docs_lint": docs_lint,
            "checked_at": now,
        },
    }


def write_report(repo_root: Path, report: dict[str, Any]) -> Path:
    out = repo_root / ".h2t" / "lifecycle" / "post-git-commit-docs-lint.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".tmp")
    tmp.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(out)
    return out


def hook_timeout_seconds() -> int:
    raw = os.environ.get("H2T_LINT_HOOK_TIMEOUT", "8")
    try:
        timeout = int(raw)
    except ValueError:
        return 8
    return max(1, min(timeout, 30))


def _load_payload() -> dict[str, Any]:
    try:
        raw = sys.stdin.read()
    except Exception:
        return {}
    if not raw.strip():
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def main() -> int:
    try:
        repo_root = Path.cwd().resolve()
        payload = _load_payload()
        if payload and not is_git_commit_payload(payload):
            return 0

        changed_docs = changed_docs_from_head(repo_root)
        if not changed_docs:
            write_report(
                repo_root,
                build_hook_report(
                    repo_root=repo_root,
                    status="skipped",
                    changed_docs=[],
                    docs_lint=None,
                    message="no docs markdown changed in latest commit",
                ),
            )
            return 0

        lint_script = find_docs_lint_script()
        if lint_script is None:
            write_report(
                repo_root,
                build_hook_report(
                    repo_root=repo_root,
                    status="error",
                    changed_docs=changed_docs,
                    docs_lint=None,
                    message="docs-lint script not found",
                ),
            )
            return 0

        timeout = hook_timeout_seconds()
        docs_lint = run_docs_lint_doctor(repo_root, lint_script, timeout=timeout)
        status = "ok" if docs_lint.get("status") in {"ok", "warn"} else "error"
        write_report(
            repo_root,
            build_hook_report(
                repo_root=repo_root,
                status=status,
                changed_docs=changed_docs,
                docs_lint=docs_lint,
                message="docs-lint doctor completed",
            ),
        )
        return 0
    except Exception:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
