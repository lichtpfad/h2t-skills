"""PostToolUse git commit hook: run docs-lint doctor when docs markdown changed.

Not a hooks.json entry: scaffold-project writes `h2t-hook post-git-commit-docs-lint` into a
project's `.claude/settings.json` (h2t_ops/lifecycle/scaffold_project.py). Those files are
committed and outlive any plugin version, so the 3.x contract is kept: an empty or
unparseable stdin still runs the check, nothing is printed on stdout, and the report goes
to `.h2t/lifecycle/post-git-commit-docs-lint.json`. An expected failure (git, the disk,
a store refusal) is one stderr line and exit 0; an unexpected one is hook_entry's stderr
line and log row with exit 1 — non-blocking for PostToolUse, where only 2 blocks.

Port of the 3.x handler of the same name. One change: docs-lint is the package's
(`docs_lint_command`), not a plugin script looked up on disk.
"""
from __future__ import annotations

import datetime
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

from h2t_ops.core import store
from h2t_ops.core.errors import H2TError

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


def docs_lint_command() -> list[str]:
    """The package's docs-lint, or the lint.py that H2T_DOCS_LINT_SCRIPT names.

    3.x looked for the plugin script (in the cwd's checkout, then under a `latest/` link in
    the plugin cache) and reported "docs-lint script not found" when neither was there. The
    package carries docs-lint itself (h2t_ops/tools/docs), so there is always one to run.
    """
    env = os.environ.get("H2T_DOCS_LINT_SCRIPT")
    if env and Path(env).is_file():
        return [sys.executable, env]
    return [sys.executable, "-m", "h2t_ops.tools.docs.lint"]


def run_docs_lint_doctor(repo_root: Path, command: list[str], *, timeout: int) -> dict[str, Any]:
    try:
        result = subprocess.run(
            [*command, "doctor", "--root", str(repo_root), "--json"],
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
    rel = ".h2t/lifecycle/post-git-commit-docs-lint.json"
    store.repo(repo_root, "post-git-commit-docs-lint").replace(
        rel, json.dumps(report, ensure_ascii=False, indent=2))
    return repo_root / rel


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


def _repo_root() -> Path:
    """The repository the commit landed in, from git; the cwd outside a repository."""
    top = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True,
                         text=True, encoding="utf-8", errors="replace")
    if top.returncode == 0 and top.stdout.strip():
        return Path(top.stdout.strip()).resolve()
    return Path.cwd().resolve()


def main(argv: list[str]) -> int:
    try:
        repo_root = _repo_root()
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

        timeout = hook_timeout_seconds()
        docs_lint = run_docs_lint_doctor(repo_root, docs_lint_command(), timeout=timeout)
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
    except (OSError, subprocess.SubprocessError, H2TError) as exc:
        # Non-blocking (exit 0, the 3.x contract) but not silent: one line on stderr, the
        # stdout channel stays empty. Anything else is a defect and surfaces as one.
        print(f"h2t-hook {COMMAND}: report not written: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 0
