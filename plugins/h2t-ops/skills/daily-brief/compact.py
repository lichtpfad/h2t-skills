"""Compact h2t CLI envelopes into brief-sized rows.

Reads JSON on stdin, writes compact text on stdout.

Usage:
    ... ingest calendar list --days 3 --json | compact.py calendar
    ... ingest gmail list --json            | compact.py gmail
    ... ingest notion search --format json --resolve-relations Project | compact.py notion

Counts, truncation and span fields come from the CLI envelope; this script only
shortens rows and builds links. Its main job is gmail, whose rows carry full
message bodies (tens of KB) that must never reach the brief.
"""

import argparse
import html
import io
import json
import os
import re
import sys

GMAIL_THREAD = "https://mail.google.com/mail/u/0/#all/{}"
SNIPPET_LEN = 180
# Newsletters pad previews with invisible glyphs; they eat the whole snippet.
_INVISIBLE = re.compile(r"[­͏​-‏  ‪-‮﻿]")

# One wrapper for the whole run: a per-call wrapper closes sys.stdout.buffer
# when garbage collected, so the second write would fail.
_W = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", newline="")


def _out(text: str) -> None:
    """Write UTF-8 to stdout regardless of platform default encoding."""
    _W.write(text + "\n")
    _W.flush()


def _load() -> dict:
    """Accept an envelope, or a bare array from --bare, and normalize."""
    raw = sys.stdin.read().strip()
    if not raw:
        _out("⚠️ empty input")
        sys.exit(0)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        _out(f"⚠️ not JSON: {e}. First 200 chars: {raw[:200]}")
        sys.exit(1)
    if isinstance(data, list):
        return {"items": data, "count": len(data), "truncated": None}
    if isinstance(data, dict) and "items" in data:
        return data
    _out(f"⚠️ expected an envelope or array, got {type(data).__name__}")
    sys.exit(1)


def _clean(text: str) -> str:
    """Strip HTML entities, invisible padding glyphs and runs of whitespace."""
    return re.sub(r"\s+", " ", _INVISIBLE.sub("", html.unescape(text))).strip()


def _count_line(env: dict) -> str:
    count = env.get("count", len(env["items"]))
    truncated = env.get("truncated")
    if truncated is None:
        return f"count: {count} (truncation unknown, --bare input)"
    total = env.get("estimated_total")
    if truncated:
        of = f" of ~{total}" if total else ""
        return f"count: {count}{of} shown, MORE EXIST (raise --limit for the rest)"
    return f"count: {count} (complete)"


def _plain(prop: dict | None) -> str:
    """Flatten one Notion property to a short string, '' when absent."""
    if not prop:
        return ""
    kind = prop.get("type")
    if kind in ("status", "select"):
        node = prop.get(kind)
        return node["name"] if node else ""
    if kind == "date":
        node = prop.get("date")
        if not node:
            return ""
        return node["start"] + (f" → {node['end']}" if node.get("end") else "")
    if kind == "multi_select":
        return ", ".join(o["name"] for o in prop.get("multi_select", []))
    if kind == "people":
        return ", ".join(p.get("name", "?") for p in prop.get("people", []))
    return ""


def _title(props: dict) -> str:
    for value in props.values():
        if value.get("type") == "title":
            return "".join(t["plain_text"] for t in value["title"]) or "(untitled)"
    return "(untitled)"


def cmd_calendar(env: dict) -> None:
    _out(_count_line(env))
    _out("")
    for ev in env["items"]:
        if ev.get("multi_day") and ev.get("ongoing"):
            span = f" [ИДЁТ: день {ev['day_index']} из {ev['days_total']}, до {ev['end']}]"
        elif ev.get("multi_day"):
            span = f" [{ev['days_total']} дн., {ev['start']} → {ev['end']}]"
        else:
            span = ""
        _out(f"- {ev.get('date', '')} {ev.get('time', '')} | {ev.get('summary', '')}{span}")
        _out(f"    {ev.get('html_link', '')}")


def cmd_gmail(env: dict) -> None:
    _out(_count_line(env))
    _out("")
    for m in env["items"]:
        body = _clean(m.get("snippet") or m.get("body") or "")
        _out(f"- [{m.get('date', '')[:22]}] {m.get('from', '')} | {_clean(m.get('subject', ''))}")
        _out(f"    {body[:SNIPPET_LEN]}")
        _out(f"    {GMAIL_THREAD.format(m.get('threadId', ''))}")


def cmd_notion(env: dict) -> None:
    _out(_count_line(env))
    relations = env.get("relations") or {}
    if not relations:
        _out("⚠️ relations not resolved: rerun with --resolve-relations Project")
    _out("")
    for page in env["items"]:
        props = page.get("properties", {})
        fields = [
            ("Status", _plain(props.get("Status"))),
            ("Priority", _plain(props.get("Priority"))),
            ("Due", _plain(props.get("Due"))),
            ("Tags", _plain(props.get("Tags"))),
        ]
        meta = " · ".join(f"{k}: {v}" for k, v in fields if v) or "no properties set"
        rel = props.get("Project", {}).get("relation") or []
        named = [relations[r["id"]] for r in rel if r["id"] in relations]
        project = (
            ", ".join(f"{n['title']} ({n['url']})" for n in named)
            if named
            else ("unresolved" if rel else "(none)")
        )
        _out(f"- {_title(props)}")
        _out(f"    {meta}")
        _out(f"    Project: {project}")
        _out(f"    {page.get('url', '')}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("mode", choices=["calendar", "gmail", "notion"])
    args = ap.parse_args()
    env = _load()
    {"calendar": cmd_calendar, "gmail": cmd_gmail, "notion": cmd_notion}[args.mode](env)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except BrokenPipeError:
        # Downstream closed early (`| head`); not an error for a filter.
        # Point stdout at devnull so interpreter shutdown does not re-raise.
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        sys.exit(0)
