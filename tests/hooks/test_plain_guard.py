"""Plain-language guard: long sentences, banned slang and bureaucratic forms warn; clean text is silent."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from h2t_ops.hooks.emit import Reply


def _load():
    path = Path(__file__).parents[2] / "h2t_ops" / "hooks" / "plain_guard.py"
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


def test_a_long_answer_is_logged_and_never_blocks(tmp_path):
    """Silent with a log row since Task 9b: the one-week trial's data is the log."""
    m = _load()
    log = m.log_path()
    path = _transcript(tmp_path, LONG)
    assert m.handle({"transcript_path": path, "session_id": "s1"}) == Reply()
    row = json.loads(log.read_text(encoding="utf-8").splitlines()[-1])
    assert row["flagged"] is True and row["long"] == [30] and row["session_id"] == "s1"


def test_clean_answer_is_logged_silently(tmp_path):
    m = _load()
    log = m.log_path()
    path = _transcript(tmp_path, SHORT)
    assert m.handle({"transcript_path": path}) == Reply()
    assert json.loads(log.read_text(encoding="utf-8"))["flagged"] is False


def test_stop_hook_active_is_silent(tmp_path):
    m = _load()
    path = _transcript(tmp_path, LONG)
    assert m.handle({"transcript_path": path, "stop_hook_active": True}) == Reply()
    assert not m.log_path().exists()


def test_the_log_follows_home_at_call_time(tmp_path, monkeypatch):
    """Resolved per call, not at import: the HOME of the run is the one written (Task 18)."""
    m = _load()
    later = tmp_path / "later"
    monkeypatch.setenv("HOME", str(later))
    monkeypatch.setenv("USERPROFILE", str(later))
    path = _transcript(tmp_path, LONG)
    assert m.handle({"transcript_path": path, "session_id": "s1"}) == Reply()
    assert (later / ".h2t" / "logs" / "plain-guard.jsonl").is_file()


def test_a_log_row_that_cannot_be_written_is_said_not_raised(tmp_path, capsys):
    """A silent hook is a failure (hooks.md): the Stop still passes, stderr says why."""
    m = _load()
    m.log_path().parent.parent.mkdir(parents=True, exist_ok=True)
    m.log_path().parent.write_text("a file where logs/ should be")
    path = _transcript(tmp_path, LONG)
    assert m.handle({"transcript_path": path, "session_id": "s1"}) == Reply()
    assert "plain-guard: log row not written" in capsys.readouterr().err
