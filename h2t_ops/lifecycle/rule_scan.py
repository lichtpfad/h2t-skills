"""`h2t-handoff rule-scan`: candidate behavioural rules from this session's transcript.

Ported from the inline `python -c` program handoff/SKILL.md used to carry (Task 12): a
grep over the user messages of the newest transcript, for the trigger words of a rule
("не делай", "запомни", "никогда", ...). The scan only proposes; handoff's rule-promotion
gate decides.

Two properties are kept from #475. The transcript directory is named the way Claude Code
names it — every character that is not an ASCII letter or digit becomes '-', the leading
'/' and every '_' included; the old snippet kept '_' and looked where nothing exists. And a
missing transcript is reported as missing, never as "no rules".
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

TRIGGERS = re.compile(
    r"не делай|не используй|стоп|запомни|договорились|принято|всегда|никогда|правило:|"
    r"протокол:|важно:|запрет|нельзя|не надо", re.I)
HIT_CHARS = 200


def transcript_dir(cwd: str, home: Path) -> Path:
    return home / ".claude" / "projects" / re.sub(r"[^A-Za-z0-9]", "-", cwd)


def _text(obj: dict) -> str:
    content = obj.get("message", {}).get("content", "")
    if isinstance(content, list):
        content = " ".join(b.get("text", "") for b in content
                           if isinstance(b, dict) and b.get("type") == "text")
    return content if isinstance(content, str) else ""


def scan(cwd: str, home: Path) -> dict:
    proj = transcript_dir(cwd, home)
    files = sorted(proj.glob("*.jsonl"), key=os.path.getmtime, reverse=True)
    if not files:
        return {"ok": False, "error": {
            "message": f"no transcript found in {proj}",
            "hint": "Report it; it does not mean the session had no rules."}}
    hits, scanned = [], 0
    with open(files[0], encoding="utf-8", errors="replace") as f:
        for line in f:
            try:
                obj = json.loads(line)
            except ValueError:
                continue
            if not isinstance(obj, dict) or obj.get("type") != "user":
                continue
            text = _text(obj)
            if not text:
                continue
            scanned += 1
            if TRIGGERS.search(text):
                hits.append(text[:HIT_CHARS])
    return {"ok": True, "transcript": files[0].name, "scanned": scanned, "hits": hits}


def main(argv: list[str] | None = None) -> int:
    # Windows pipes default to cp1252; the triggers and the hits are Cyrillic (#428).
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(prog="h2t-handoff rule-scan", description=__doc__.splitlines()[0])
    parser.add_argument("--cwd", default=None, help="the session's directory (default: here)")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    result = scan(args.cwd or os.getcwd(), Path.home())
    if args.json:
        print(json.dumps(result, ensure_ascii=False))
    elif result["ok"]:
        print("\n---\n".join(result["hits"]))
        print(f"RULE_SCAN: scanned {result['scanned']} user messages in "
              f"{result['transcript']}, {len(result['hits'])} hits")
    else:
        print(f"RULE_SCAN: {result['error']['message']}", file=sys.stderr)
    return 0 if result["ok"] else 5
