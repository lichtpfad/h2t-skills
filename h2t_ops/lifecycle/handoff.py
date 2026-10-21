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
from datetime import UTC, datetime
from pathlib import Path

from h2t_ops.core import paths, store
from h2t_ops.core.errors import H2TError
from h2t_ops.lifecycle import session_record
from h2t_ops.lifecycle.activity.writer import log_session_end
from h2t_ops.lifecycle.eval.session import SkillEval
from h2t_ops.lifecycle.gather.runner import _run_one
from h2t_ops.lifecycle.pulse import record


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
        from h2t_ops.lifecycle.gather.project import identify_project
        resolved = identify_project(cwd) or {}
    except Exception:  # noqa: BLE001 - a resolver that fails must not cost the record
        resolved = {}
    found = str(resolved.get("id") or "")
    if not found or found == "unknown":
        found = Path(cwd).resolve().name
    return project or found, domain or str(resolved.get("domain") or "dev")


def _machine() -> str:
    # The reader's own rule, so writer and gather cannot disagree on the directory (#491).
    from h2t_ops.lifecycle.gather.sessions import get_machine_name
    return get_machine_name()


def default_markdown_dir(project: str, machine: str | None = None) -> Path:
    return paths.records("sessions", machine or _machine()) / project


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


def _git_context() -> tuple[str, list[str]]:
    """Branch and the last five commits of cwd; a git that fails gives empty fields, never
    an exception — nothing may stand between the session and its record (gates.md)."""
    branch = _run_one(["git", "rev-parse", "--abbrev-ref", "HEAD"], timeout=5)
    log = _run_one(["git", "log", "-5", "--format=%h"], timeout=5)
    return (branch or "").strip(), (log or "").split()


def _write_record(md_path: Path, meta: dict, body: bytes, *, dest: bool) -> tuple[Path, list[str]]:
    """New records are created, never overwritten (§7.2). A file already at the name is
    replaced only when its frontmatter says it is this session's record; any other file —
    a hand-written note, a sync conflict, no frontmatter — is left as it is, and the record
    takes the next free name. Returns the path written and notes for the response."""
    data = session_record.render(meta, body)
    foreign: list[Path] = []
    for candidate in store.unique_name(md_path):
        try:
            written = store.create(candidate, data, place="records.sessions", dest=dest)
            break
        except store.AlreadyExists:
            pass
        try:
            theirs, _ = session_record.parse(candidate.read_bytes())
        except (OSError, ValueError):   # unreadable (a directory, no permission) is foreign too
            theirs = {}
        if all(theirs.get(k) == meta[k] for k in ("session_id", "machine", "project")):
            written = store.replace(candidate, data, place="records.sessions", dest=dest)
            break
        foreign.append(candidate)
    return written, [f"{f} is not this session's record and was left untouched; "
                     f"the record is {written}" for f in foreign]


def _program_session() -> tuple[str, str] | None:
    """record.program_session, but a failing lookup means "unknown": the handoff still writes."""
    try:
        return record.program_session()
    except Exception:  # noqa: BLE001 - nothing may stand between the session and its record
        return None


def _in_codex_shell() -> bool:
    return record.in_codex_shell()


def _open_codex_ids(cwd: str) -> list[str]:
    try:
        return record.open_ids("codex", cwd)
    except Exception:  # noqa: BLE001 - candidates are a hint, never a reason to drop the record
        return []


def _degraded(session_id: str, spool_path, distinct_artifacts: list, exc: Exception) -> dict:
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
        "artifacts": len(distinct_artifacts),
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

    # Deduped once, here: a repeated ref is not a second artifact, and the response,
    # the index and every _degraded exit must agree on that one number.
    distinct_artifacts = _dedupe_artifacts(parsed_artifacts)

    # Resolved once: the spool row, the frontmatter and the directory must name one machine.
    machine = _machine()
    spool_path = log_session_end(
        session_id=session_id,
        domain=domain,
        project=project,
        artifacts=parsed_artifacts,
        machine=machine,
    )

    now = datetime.now(UTC)
    branch, commits = _git_context()
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
    meta = {
        "session_id": session_id,
        "machine": machine,
        "project": project,
        "domain": domain,
        "date": now.strftime("%Y-%m-%d"),
        "updated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "branch": branch,
        "commits": commits,
        "done": what_done,
        "remains": what_remains,
        "artifacts": distinct_artifacts,
    }
    dest = markdown_dir is not None
    session_uuid = ""
    notes: list[str] = []
    program = None if dest else _program_session()
    if program is not None:
        # The program's own id is known: the handoff enriches the record the hook started.
        session_uuid = program[1]
        meta.update(name=session_id, tool=program[0])
        meta.pop("session_id")
        try:
            persisted_md_path = record.upsert(session_uuid, meta, body=md_content.encode("utf-8"))
        except (OSError, H2TError, ValueError) as exc:
            return _degraded(session_id, spool_path, distinct_artifacts, exc)
    else:
        if not dest and _in_codex_shell():
            # A Codex shell with no unique open session: keep the slug record, marked so the
            # view can place it; the open ids are the candidates it may belong to.
            cwd = os.getcwd()
            meta.update(tool="codex", cwd=cwd, origin="live", user_msgs=1)
            candidates = _open_codex_ids(cwd)
            if candidates:
                meta["candidates"] = candidates
        md_dir = Path(markdown_dir) if markdown_dir else default_markdown_dir(project, machine)
        try:
            # The first operation on this path: a --markdown-dir into a package place (secrets,
            # say) is refused here, after the spool, so it degrades like any other mirror failure.
            store.mkdir(md_dir, place="records.sessions", dest=dest)
        except (OSError, H2TError) as exc:
            return _degraded(session_id, spool_path, distinct_artifacts, exc)
        md_path = md_dir / f"{session_id}.md"

        # No latest.json (R10): the index answers "the last session of this project".
        try:
            persisted_md_path, notes = _write_record(md_path, meta, md_content.encode("utf-8"), dest=dest)
        except (OSError, H2TError) as exc:
            return _degraded(session_id, spool_path, distinct_artifacts, exc)

    try:
        with SkillEval("handoff", domain=domain, project=project):
            pass
    except Exception:
        pass

    result = {
        "status": "ok",
        "session_id": session_id,
        "spool": spool_path,
        "markdown": str(persisted_md_path),
        # R10: the record is the latest; session-start finds it through the index.
        "latest": str(persisted_md_path),
        # The distinct artifacts recorded (#438); the markdown and the spool carry every one.
        "artifacts": len(distinct_artifacts),
        "mirror_write_failed": False,
    }
    if session_uuid:
        result["session_uuid"] = session_uuid
    if notes:
        result["notes"] = notes
    return result


def main() -> None:
    # Windows encodes a piped stdout with the ANSI codepage, whatever chcp says, so
    # a non-ASCII payload reaches the caller as cp1252 — or kills the write outright
    # where cp1252 has no byte for the character. Every caller decodes UTF-8 (#428).
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
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
