#!/usr/bin/env python
"""Finalize a creative-think session: read active log, save session file, clean up."""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

EVAL_DIR = Path.home() / ".h2t" / "evals" / "creative-thinking"
SESSION_DIR = EVAL_DIR / "sessions"
ACTIVE_FILE = EVAL_DIR / ".active_session.jsonl"


def main():
    if not ACTIVE_FILE.exists() or ACTIVE_FILE.stat().st_size == 0:
        return

    SESSION_DIR.mkdir(parents=True, exist_ok=True)

    # Read accumulated events
    events = []
    with open(ACTIVE_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    pass

    if not events:
        ACTIVE_FILE.unlink(missing_ok=True)
        return

    # Build session
    graph_queries = [e for e in events if e.get("event") == "graph_query"]
    total_nodes = sum(e.get("result", {}).get("nodes", 0) for e in graph_queries)
    total_tokens_saved = sum(e.get("result", {}).get("tokens_estimate", 0) for e in graph_queries)

    # Generate session ID
    today = datetime.utcnow().strftime("%Y-%m-%d")
    existing = [f.name for f in SESSION_DIR.iterdir() if f.name.startswith(f"ct-{today}")]
    seq = len(existing) + 1
    session_id = f"ct-{today}-{seq:03d}"

    session = {
        "session_id": session_id,
        "timestamp": events[0].get("timestamp", ""),
        "graph_queries": [
            {
                "command": e.get("command", ""),
                "nodes_returned": e.get("result", {}).get("nodes", 0),
                "tokens_estimate": e.get("result", {}).get("tokens_estimate", 0),
            }
            for e in graph_queries
        ],
        "summary": {
            "total_queries": len(graph_queries),
            "total_nodes_returned": total_nodes,
            "total_tokens_saved": total_tokens_saved,
            "used_fallback": len(graph_queries) == 0,
        },
    }

    out_path = SESSION_DIR / f"{session_id}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(session, f, ensure_ascii=False, indent=2)

    # Clean up
    ACTIVE_FILE.unlink(missing_ok=True)
    print(f"Session saved: {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
