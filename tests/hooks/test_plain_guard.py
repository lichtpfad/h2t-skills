"""Plain-language guard: long sentences, banned slang and bureaucratic forms warn; clean text is silent."""
from __future__ import annotations

import importlib.util
import io
import json
from pathlib import Path


def _load():
    path = Path(__file__).parents[2] / "plugins" / "h2t-core" / "hooks-handlers" / "plain_guard.py"
    spec = importlib.util.spec_from_file_location("plain_guard_under_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


LONG = " ".join(["слово"] * 30) + "."
SHORT = "Закрой сессию. Потом проверь статус базы."


def _transcript(tmp_path: Path, text: str) -> str:
    p = tmp_path / "t.jsonl"
    rows = [
        json.dumps({"type": "user", "message": {"content": "hi"}}),
        json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": text}]}}, ensure_ascii=False),
    ]
    p.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return str(p)


def test_long_sentence_is_counted():
    m = _load()
    assert m.long_sentences(LONG) == [30]
    assert m.long_sentences(SHORT) == []


def test_each_line_is_its_own_unit():
    m = _load()
    lines = "\n".join(["- " + " ".join(["пункт"] * 10)] * 5)
    assert m.long_sentences(lines) == []


def test_code_tables_and_paths_are_not_counted():
    m = _load()
    text = (
        "```\n" + LONG + "\n```\n"
        "| " + " | ".join(["ячейка"] * 30) + " |\n"
        "Смотри `" + "_".join(["x"] * 40) + "` и C:/dev/a/b/c/d/e/f/g/h/i/j/k/l/m/n/o/p/q/r/s/t/u/v/w/x/y/z.py."
    )
    assert m.long_sentences(text) == []
    assert m.check("Это `entity` в коде.")["slang"] == []
    assert m.check("Пиши «Закрой сессию», а не «сессия должна быть закрыта».")["passive"] == []


def test_slang_and_passive_are_named():
    m = _load()
    r = m.check("Здесь provenance и entity. Крышка должна быть установлена, это является проблемой.")
    assert r["slang"] == ["entity", "provenance"]
    assert r["passive"] == ["должна быть", "является"]


def test_clean_answer_has_no_warning():
    m = _load()
    assert m.warning(m.check(SHORT)) is None


def test_main_warns_logs_and_never_blocks(tmp_path, monkeypatch, capsys):
    m = _load()
    log = tmp_path / "log.jsonl"
    monkeypatch.setattr(m, "LOG_PATH", log)
    path = _transcript(tmp_path, LONG)
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"transcript_path": path, "session_id": "s1"})))
    assert m.main() == 0
    out = capsys.readouterr().out
    assert "простой язык" in out and "decision" not in out
    row = json.loads(log.read_text(encoding="utf-8").splitlines()[-1])
    assert row["flagged"] is True and row["long"] == [30] and row["session_id"] == "s1"


def test_clean_answer_is_logged_silently(tmp_path, monkeypatch, capsys):
    m = _load()
    log = tmp_path / "log.jsonl"
    monkeypatch.setattr(m, "LOG_PATH", log)
    path = _transcript(tmp_path, SHORT)
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"transcript_path": path})))
    assert m.main() == 0
    assert capsys.readouterr().out == ""
    assert json.loads(log.read_text(encoding="utf-8"))["flagged"] is False


def test_stop_hook_active_is_silent(tmp_path, monkeypatch, capsys):
    m = _load()
    monkeypatch.setattr(m, "LOG_PATH", tmp_path / "log.jsonl")
    path = _transcript(tmp_path, LONG)
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"transcript_path": path, "stop_hook_active": True})))
    assert m.main() == 0
    assert capsys.readouterr().out == ""
    assert not (tmp_path / "log.jsonl").exists()
