#!/usr/bin/env python3
"""Handoff writer for session-end.

Usage:
  $H2T_PYTHON writer.py write \
    --session-id <id> [--domain <d>] [--project <p>] \
    --what-done "..." --what-remains "..." \
    --artifacts commit:abc123 issue:42 \
    [--markdown-dir <path>]

Writes:
  1. Activity stream entry (local JSONL spool)
  2. Markdown handoff file at markdown_dir/session_id.md

lib/ path resolution: same dev/cache fallback as gather.py.
"""

import argparse
import json
import os
import sys
from datetime import UTC, datetime, timezone
from pathlib import Path

# lib/ path: cache root (4 levels up) or repo root (6 levels up) fallback
PLUGIN_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_cache_lib = PLUGIN_ROOT / "lib"
_repo_lib = PLUGIN_ROOT.parent.parent / "lib"
for _lib in [_cache_lib, _repo_lib]:
    if _lib.exists():
        sys.path.insert(0, str(_lib))
        break

from activity.writer import log_session_end
from eval.session import SkillEval

SUMMARY_LIMIT = 1200
ITEM_LIMIT = 240
MAX_ITEMS = 5
MAX_ARTIFACTS = 10


def resolve_identity(project: str = "", domain: str = "", cwd: str = "") -> tuple[str, str]:
    """Which project a handoff belongs to is a property of the directory it was written in.

    session-start already resolves scope that way (identify_project -> repo-mapping.yaml);
    when it has run, it passes the answer down and this is a no-op. When it has not, ask
    the same resolver rather than let the caller guess: guessing produced three directories
    for one project on this machine, and an `unknown/` no reader looks in. A project that
    still does not resolve keeps the checkout name, which is at least a key the reader tries.
    """
    if project and domain:
        return project, domain
    cwd = cwd or os.getcwd()
    try:
        from gather.project import identify_project
        resolved = identify_project(cwd) or {}
    except Exception:  # noqa: BLE001 - a resolver that fails must not cost the record
        resolved = {}
    found = str(resolved.get("id") or "")
    if not found or found == "unknown":
        found = Path(cwd).resolve().name
    return project or found, domain or str(resolved.get("domain") or "dev")


def default_markdown_dir(project: str) -> Path:
    root = Path(os.environ.get("H2T_SESSION_ROOT", str(Path.home() / ".h2t" / "sessions")))
    machine = os.environ.get("H2T_MACHINE_NAME") or os.environ.get("DOR_MACHINE_NAME", "")
    if not machine:
        import platform
        machine = platform.node().lower().split(".")[0]
    return root / machine / project


def _truncate(text: str, limit: int) -> tuple[str, bool]:
    text = " ".join(text.split())
    if len(text) <= limit:
        return text, False
    marker = " ... [truncated]"
    return text[: max(0, limit - len(marker))].rstrip() + marker, True


def _clean_action(line: str) -> str:
    line = line.strip()
    prefixes = ("- [ ]", "- [x]", "- [X]", "- ", "* ", "1. ", "2. ", "3. ", "4. ", "5. ")
    for prefix in prefixes:
        if line.startswith(prefix):
            return line[len(prefix):].strip()
    return line


def _extract_items(text: str, *, max_items: int = MAX_ITEMS) -> tuple[list[str], bool]:
    items: list[str] = []
    truncated = False
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        cleaned = _clean_action(line)
        item, was_truncated = _truncate(cleaned, ITEM_LIMIT)
        truncated = truncated or was_truncated
        items.append(item)
        if len(items) >= max_items:
            remaining = [ln for ln in text.splitlines()[len(items):] if ln.strip()]
            truncated = truncated or bool(remaining)
            break
    return items, truncated


def _dedupe_preserving_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _dedupe_artifacts(values: list[dict]) -> list[dict]:
    seen: set[tuple[str, str]] = set()
    result: list[dict] = []
    for value in values:
        artifact_type = str(value.get("type", "artifact"))
        artifact_ref = str(value.get("ref", ""))
        key = (artifact_type, artifact_ref)
        if key in seen:
            continue
        seen.add(key)
        result.append({"type": artifact_type, "ref": artifact_ref})
    return result


def _build_latest_index(
    *,
    session_id: str,
    domain: str,
    project: str,
    what_done: str,
    what_remains: str,
    artifacts: list[dict],
    markdown_path: Path | None,
    updated_at: datetime,
) -> dict:
    summary_short, summary_truncated = _truncate(what_done, SUMMARY_LIMIT)
    next_actions, actions_truncated = _extract_items(what_remains)
    next_actions = _dedupe_preserving_order(next_actions)
    truncated = summary_truncated or actions_truncated
    deduped_artifacts = _dedupe_artifacts(artifacts)
    artifact_rows = deduped_artifacts[:MAX_ARTIFACTS]
    truncated = truncated or len(artifacts) > MAX_ARTIFACTS
    return {
        "version": 1,
        "session_id": session_id,
        "project": project,
        "domain": domain,
        "updated_at": updated_at.isoformat(),
        "summary_short": summary_short,
        "next_actions": next_actions,
        "blockers": [],
        "artifacts": artifact_rows,
        "markdown_path": str(markdown_path) if markdown_path else "",
        "truncated": truncated,
    }


def _write_json_atomic(path: Path, data: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _degraded(session_id: str, spool_path, parsed_artifacts: list, exc: Exception) -> dict:
    """The record is written; the configured mirror is not usable.

    Every mirror failure returns through here so the caller sees one shape, and so no
    OSError can escape main() after log_session_end() has already persisted the session.
    """
    return {
        "status": "degraded",
        "session_id": session_id,
        "spool": spool_path,
        "markdown": "",
        "latest": "",
        "artifacts": len(parsed_artifacts),
        "mirror_write_failed": True,
        "mirror_error": f"{type(exc).__name__}: {exc}",
    }


def write_handoff(
    session_id: str,
    domain: str,
    project: str,
    what_done: str,
    what_remains: str,
    artifacts: list[str],
    markdown_dir: str | None = None,
) -> dict:
    """Write session end to activity stream + markdown file."""

    # Unescape literal \n sequences (bash double-quote strings don't expand \n)
    what_done = what_done.replace("\\n", "\n")
    what_remains = what_remains.replace("\\n", "\n")

    parsed_artifacts = []
    for a in artifacts:
        if ":" in a:
            t, ref = a.split(":", 1)
            parsed_artifacts.append({"type": t, "ref": ref})
        else:
            parsed_artifacts.append({"type": "artifact", "ref": a})

    spool_path = log_session_end(
        session_id=session_id,
        domain=domain,
        project=project,
        artifacts=parsed_artifacts,
    )

    md_dir = Path(markdown_dir) if markdown_dir else default_markdown_dir(project)
    try:
        md_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return _degraded(session_id, spool_path, parsed_artifacts, exc)
    md_path = md_dir / f"{session_id}.md"

    now = datetime.now(UTC)
    artifacts_md = "\n".join(
        f"- {a['type']}: {a['ref']}" for a in parsed_artifacts
    ) or "None"
    md_content = f"""# Session: {session_id}

## Meta
- **Date:** {now.strftime("%Y-%m-%d")}
- **Domain:** {domain}
- **Project:** {project}

## What Was Done
{what_done}

## What Remains
{what_remains}

## Artifacts
{artifacts_md}
"""
    latest = _build_latest_index(
        session_id=session_id,
        domain=domain,
        project=project,
        what_done=what_done,
        what_remains=what_remains,
        artifacts=parsed_artifacts,
        markdown_path=None,
        updated_at=now,
    )
    latest_path = md_dir / "latest.json"
    markdown_failed = False
    persisted_md_path: Path | None = None
    try:
        _write_json_atomic(latest_path, latest)
    except OSError as exc:
        # latest.json is part of the same mirror. It used to sit outside every guard, so a
        # directory named latest.json.tmp raised IsADirectoryError out of main() — exit 1
        # and a traceback, with the spool already on disk. Same invariant, same answer.
        return _degraded(session_id, spool_path, parsed_artifacts, exc)

    try:
        md_path.write_text(md_content, encoding="utf-8")
        persisted_md_path = md_path
    except OSError:
        markdown_failed = True

    if persisted_md_path is not None:
        latest["markdown_path"] = str(persisted_md_path)
        try:
            _write_json_atomic(latest_path, latest)
        except OSError:
            # The first write landed; only the markdown_path backfill is lost.
            markdown_failed = True

    try:
        with SkillEval("handoff", domain=domain, project=project):
            pass
    except Exception:
        pass

    return {
        "status": "degraded" if markdown_failed else "ok",
        "session_id": session_id,
        "spool": spool_path,
        "markdown": str(md_path) if persisted_md_path else "",
        "latest": str(latest_path),
        "artifacts": len(latest["artifacts"]),
        "mirror_write_failed": markdown_failed,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd")
    w = sub.add_parser("write")
    w.add_argument("--session-id", required=True)
    w.add_argument("--domain", default="")
    w.add_argument("--project", default="")
    w.add_argument("--what-done", default="")
    w.add_argument("--what-remains", default="")
    w.add_argument("--artifacts", nargs="*", default=[])
    w.add_argument("--markdown-dir", default="")
    args = parser.parse_args()

    if args.cmd == "write":
        project, domain = resolve_identity(args.project, args.domain)
        result = write_handoff(
            session_id=args.session_id,
            domain=domain,
            project=project,
            what_done=args.what_done,
            what_remains=args.what_remains,
            artifacts=args.artifacts,
            markdown_dir=args.markdown_dir or None,
        )
        print(json.dumps(result, ensure_ascii=False))
        if result.get("mirror_write_failed"):
            # 3 = config, the connector taxonomy in CLAUDE.md. The record is written; the
            # mirror location is not usable. Callers that only check the exit code must be
            # told something is wrong, and callers that read the JSON get the spool path.
            print(f"handoff: record written to {result['spool']}; "
                  f"markdown mirror unavailable: {result.get('mirror_error', 'write failed')}",
                  file=sys.stderr)
            sys.exit(3)
    else:
        parser.print_help(sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
