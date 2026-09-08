"""A state claim without evidence gets a warning; evidence or a grade tag silences it."""
from __future__ import annotations

import importlib.util
import io
import json
from pathlib import Path


def _load():
    path = Path(__file__).parents[2] / "plugins" / "h2t-core" / "hooks-handlers" / "grade_guard.py"
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


def test_main_warns_and_never_blocks(tmp_path, monkeypatch, capsys):
    m = _load()
    path = _transcript(tmp_path, "Готово.")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"transcript_path": path})))
    assert m.main() == 0
    out = capsys.readouterr().out
    assert "Готово" in out and "decision" not in out


def test_stop_hook_active_is_silent(tmp_path, monkeypatch, capsys):
    m = _load()
    path = _transcript(tmp_path, "Готово.")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"transcript_path": path, "stop_hook_active": True})))
    assert m.main() == 0
    assert capsys.readouterr().out == ""


def test_missing_transcript_is_silent(monkeypatch, capsys):
    m = _load()
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"transcript_path": "Z:/nope.jsonl"})))
    assert m.main() == 0
    assert capsys.readouterr().out == ""
