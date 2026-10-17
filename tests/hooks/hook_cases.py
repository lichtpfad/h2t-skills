"""Recorded hook cases: tests/fixtures/hooks/<name>/<Event>.<case>.json (spec §2.8).

One file is one event for one hook and the reply it must get. Keys:

- `event` — the payload. `{tmp}` stands for the case's working tree (also the cwd),
  `{transcript}` for the transcript JSONL built from `transcript`.
- `files` — {relative path: content}, written under the working tree first.
- `transcript` — assistant messages, oldest first, for the Stop hooks.
- `gh_view` — what `gh pr view` answers, for plan-closer.
- `expect` — the Reply: `text` (exact) or `text_startswith`, `block`, `notice`; `meta` —
  fields the GATHER_META JSON must carry.
- `after` — {relative path: [substrings]} the tree must hold after the hook ran.
- `log` — grade-guard, plain-guard: fields of the row the hook logs to
  ~/.h2t/logs/<name>.jsonl, or null for no row.
- `plain_stdout_3x` — the Stop guards: what the 3.x handler printed and the port no longer does.

Shared by test_hook_modules.py (the module, in-process) and test_hook_equivalence.py (the
3.x handler against `h2t-hook`, as subprocesses).
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
FIXTURES = REPO / "tests" / "fixtures" / "hooks"
PLUGIN = REPO / "plugins" / "h2t-core"
META_SEP = "\n\nGATHER_META: "
# Read by gather and detect_project; a developer's own value would leak into the case.
ISOLATED_ENV = ("H2T_CONFIG_ROOT", "H2T_SESSION_ROOT", "H2T_ACTIVITY_SPOOL",
                "H2T_SECRETS_FILE", "DOR_MACHINE_NAME", "H2T_KB_ROOT",
                "CURSOR_PLUGIN_ROOT", "COPILOT_CLI")


def all_cases() -> list[tuple[str, str, Path]]:
    return sorted((p.parent.name, p.stem, p) for p in FIXTURES.glob("*/*.json"))


def case_id(case: tuple[str, str, Path]) -> str:
    return f"{case[0]}/{case[1]}"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _subst(value, mapping: dict[str, str]):
    if isinstance(value, str):
        for key, real in mapping.items():
            value = value.replace(key, real)
        return value
    if isinstance(value, list):
        return [_subst(v, mapping) for v in value]
    if isinstance(value, dict):
        return {k: _subst(v, mapping) for k, v in value.items()}
    return value


def materialize(body: dict, root: Path) -> dict:
    """Build the case's tree under `root` and return the event with placeholders filled."""
    root.mkdir(parents=True, exist_ok=True)
    for rel, content in (body.get("files") or {}).items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    transcript = root.parent / f"{root.name}-transcript.jsonl"
    rows = [json.dumps({"type": "user", "message": {"content": "hi"}})]
    for text in body.get("transcript") or []:
        rows.append(json.dumps({"type": "assistant",
                                "message": {"content": [{"type": "text", "text": text}]}},
                               ensure_ascii=False))
    transcript.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return _subst(body["event"], {"{tmp}": str(root), "{transcript}": str(transcript)})


def expected(body: dict, root: Path) -> dict:
    return _subst(body["expect"], {"{tmp}": str(root)})


def check_reply(expect: dict, text: str, block: bool, notice: str) -> None:
    if "text" in expect:
        assert text == expect["text"]
    if "text_startswith" in expect:
        assert text.startswith(expect["text_startswith"]), text[:300]
    assert block == expect["block"]
    assert notice == expect["notice"]
    if "meta" in expect:
        assert META_SEP in text, text[-300:]
        meta = json.loads(text.rsplit(META_SEP, 1)[1])
        for key, value in expect["meta"].items():
            assert meta[key] == value, (key, meta.get(key))
        at = datetime.fromisoformat(meta["at"])
        assert at.tzinfo is not None, meta["at"]
        age = (datetime.now().astimezone() - at).total_seconds()
        assert -5 <= age <= 120, meta["at"]


def check_after(body: dict, root: Path) -> None:
    for rel, needles in (body.get("after") or {}).items():
        content = (root / rel).read_text(encoding="utf-8")
        for needle in needles:
            assert needle in content, (rel, needle, content)


def log_rows(home: Path, name: str) -> list[dict]:
    path = home / ".h2t" / "logs" / f"{name}.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def check_log(body: dict, home: Path, name: str) -> None:
    if "log" not in body:
        return
    rows = log_rows(home, name)
    if body["log"] is None:
        assert rows == []
        return
    assert len(rows) == 1, rows
    for key, value in body["log"].items():
        assert rows[0][key] == value, (key, rows[0])
