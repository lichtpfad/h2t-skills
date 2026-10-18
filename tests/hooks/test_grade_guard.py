"""A state claim without evidence gets a warning; evidence or a grade tag silences it."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from h2t_ops.hooks.emit import Reply


def _load():
    path = Path(__file__).parents[2] / "h2t_ops" / "hooks" / "grade_guard.py"
    spec = importlib.util.spec_from_file_location("grade_guard_under_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _transcript(tmp_path: Path, *assistant_texts: str) -> str:
    p = tmp_path / "t.jsonl"
    rows = [json.dumps({"type": "user", "message": {"content": "hi"}})]
    for t in assistant_texts:
        rows.append(json.dumps({
            "type": "assistant",
            "message": {"content": [{"type": "text", "text": t}]},
        }, ensure_ascii=False))
    p.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return str(p)


def test_claim_without_evidence_is_named():
    m = _load()
    assert m.claim_without_evidence("Тесты зелёные, задача закрыта.") == "зелёные"
    assert m.claim_without_evidence("All done.") == "done"


def test_code_block_or_grade_tag_silences():
    m = _load()
    assert m.claim_without_evidence("Done:\n```\n6 passed\n```") is None
    assert m.claim_without_evidence("Закрыто [B: прочитано, не прогнано]") is None
    assert m.claim_without_evidence("Скорее всего готово [C: не проверено]") is None


def test_no_claim_is_silent():
    m = _load()
    assert m.claim_without_evidence("Читаю файл, потом отвечу.") is None
    assert m.claim_without_evidence("") is None
    assert m.claim_without_evidence("well-done steak") is None  # hyphenated, not a claim


def test_reads_last_assistant_message_only(tmp_path):
    m = _load()
    path = _transcript(tmp_path, "готово", "смотрю дальше")
    assert m.last_assistant_text(path) == "смотрю дальше"


def test_a_claim_is_logged_and_never_blocks(tmp_path):
    """Silent with a log row since Task 9b; the TUI line is a one-line switch in handle()."""
    m = _load()
    path = _transcript(tmp_path, "Готово.")
    assert m.handle({"transcript_path": path, "session_id": "s1"}) == Reply()
    row = json.loads(m.log_path().read_text(encoding="utf-8"))
    assert row["flagged"] is True and row["word"] == "Готово" and row["session_id"] == "s1"


def test_stop_hook_active_is_silent(tmp_path):
    m = _load()
    path = _transcript(tmp_path, "Готово.")
    assert m.handle({"transcript_path": path, "stop_hook_active": True}) == Reply()
    assert not m.log_path().exists()


def test_missing_transcript_is_silent(tmp_path):
    m = _load()
    assert m.handle({"transcript_path": "Z:/nope.jsonl"}) == Reply()
    assert not m.log_path().exists()


def test_the_log_follows_home_at_call_time(tmp_path, monkeypatch):
    """Resolved per call, not at import: the HOME of the run is the one written (Task 18)."""
    m = _load()
    later = tmp_path / "later"
    monkeypatch.setenv("HOME", str(later))
    monkeypatch.setenv("USERPROFILE", str(later))
    path = _transcript(tmp_path, "Готово.")
    assert m.handle({"transcript_path": path, "session_id": "s1"}) == Reply()
    assert (later / ".h2t" / "logs" / "grade-guard.jsonl").is_file()


def test_a_log_row_that_cannot_be_written_is_said_not_raised(tmp_path, capsys):
    """A silent hook is a failure (hooks.md): the Stop still passes, stderr says why."""
    m = _load()
    m.log_path().parent.parent.mkdir(parents=True, exist_ok=True)
    m.log_path().parent.write_text("a file where logs/ should be")
    path = _transcript(tmp_path, "Готово.")
    assert m.handle({"transcript_path": path, "session_id": "s1"}) == Reply()
    assert "grade-guard: log row not written" in capsys.readouterr().err
