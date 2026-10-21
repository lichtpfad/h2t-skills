"""A 1-3 line Russian summary per live session that has no handoff, by a cheap model.

Asked once per transcript state: the stamp `size:mtime_ns` of the transcript is stored with
the summary, and a session whose transcript still has that stamp is not asked again. A
failed, empty or timed-out answer skips the session and writes nothing.
"""

from __future__ import annotations

import os
import shutil
import sqlite3
import subprocess
from pathlib import Path

from h2t_ops.lifecycle.pulse import record, transcript

_TIMEOUT_S = 120
_PROMPT = ("Ниже — запись рабочей сессии. Напиши 1–3 строки по-русски: о чём сессия и чем кончилась. "
           "Без вступления.\n\n")
_CUT = "\n[…]\n"
_SQL = ("SELECT session_id, tool, transcript, summary_stamp FROM sessions "
        "WHERE origin = 'live' AND COALESCE(done, '') = '' AND COALESCE(transcript, '') != '' "
        "ORDER BY updated_at DESC, path")


def excerpt(tool: str, path: Path, limit: int = 12000) -> str:
    """User messages in order, then the last assistant text; cut from the middle to `limit`."""
    parts = [*transcript.user_messages(tool, path), transcript.last_assistant_text(tool, path)]
    text = "\n\n".join(p for p in parts if p.strip())
    if len(text) <= limit:
        return text
    keep = max(limit - len(_CUT), 0)
    head = keep // 2
    return text[:head] + _CUT + text[len(text) - (keep - head):]


def _ask_claude(prompt: str) -> str:
    """The model's answer; "" when the binary is missing, the call fails or times out."""
    exe = shutil.which("claude")
    if not exe:
        return ""
    try:
        done = subprocess.run([exe, "-p", "--model", "haiku", "--no-session-persistence"],
                              input=prompt, capture_output=True, text=True, encoding="utf-8",
                              env={**os.environ, "H2T_PULSE_SKIP": "1"}, timeout=_TIMEOUT_S)
    except (OSError, subprocess.SubprocessError):
        return ""
    return done.stdout.strip() if done.returncode == 0 else ""


def _stamp(path: Path) -> str | None:
    try:
        st = path.stat()
    except OSError:
        return None
    return f"{st.st_size}:{st.st_mtime_ns}"


def run(conn: sqlite3.Connection, *, ask=_ask_claude, cap: int = 30) -> dict:
    """Summarise up to `cap` live sessions with no `done` whose transcript changed since the
    last summary. Returns {"written": n, "skipped": m}; skipped counts failed answers."""
    written = skipped = asked = 0
    for row in conn.execute(_SQL).fetchall():
        path = Path(row["transcript"])
        stamp = _stamp(path)
        if stamp is None or stamp == row["summary_stamp"]:
            continue
        if asked >= cap:
            break
        asked += 1
        try:
            answer = (ask(_PROMPT + excerpt(row["tool"] or "claude", path)) or "").strip()
        except Exception:                     # the model is a helper; a session never fails the run
            answer = ""
        if not answer:
            skipped += 1
            continue
        record.upsert(row["session_id"], {"summary": answer, "summary_source": "model",
                                          "summary_stamp": stamp})
        written += 1
    return {"written": written, "skipped": skipped}
