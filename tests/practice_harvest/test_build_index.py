import json  # noqa: F401
from pathlib import Path

from lib.practice_harvest.build_index import build_corpus


def _touch(p: Path, text="x"):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")

def test_build_corpus_collects_and_counts(tmp_path):
    # repo A: rules + documentation (excluded)
    _touch(tmp_path / "repoA/.claude/rules/git.md", "GIT")
    _touch(tmp_path / "repoA/.claude/rules/documentation.md", "TEMPLATE")
    _touch(tmp_path / "repoA/CLAUDE.md", "CA")
    corpus = build_corpus(
        repo_roots=[tmp_path / "repoA"],
        session_roots=[],
        memory_roots=[],
        lineage_of=lambda name: "repoA",
    )
    kinds = sorted(r["kind"] for r in corpus["records"])
    assert kinds == ["claude_md", "rules"]  # documentation.md исключён
    assert corpus["lineage_counts"]["repoA"] >= 1
    assert all("text" in r and "path" in r for r in corpus["records"])

def test_session_text_stripped_to_meaningful_sections(tmp_path):
    md = ("# Session: s\n\n## Meta\n- **Project:** repoA\n"
          "## What Was Done\n- Did X.\n## Artifacts\n- commit: abc\n")
    sess = tmp_path / "sessions/AUTOMATA/repoA/s.md"
    _touch(sess, md)
    corpus = build_corpus(
        repo_roots=[], memory_roots=[],
        session_roots=[tmp_path / "sessions/AUTOMATA"],
        lineage_of=lambda name: "repoA",
        start="2000-01-01", end="2100-01-01",  # окно заведомо покрывает mtime
    )
    rec = next(r for r in corpus["records"] if r["kind"] == "session")
    assert rec["text"] == "Did X."          # только What Was Done
    assert "commit" not in rec["text"]      # Artifacts/Meta отброшены

def test_empty_session_not_emitted(tmp_path):
    # session без What Was Done/Remains → пустой text → НЕ в корпусе
    # (иначе coverage-гейт сертифицирует пустышку; council Lens 1)
    md = "# Session: s\n\n## Meta\n- **Project:** repoA\n\n## Artifacts\n- commit: abc\n"
    _touch(tmp_path / "sessions/AUTOMATA/repoA/empty.md", md)
    corpus = build_corpus(
        repo_roots=[], memory_roots=[],
        session_roots=[tmp_path / "sessions/AUTOMATA"],
        lineage_of=lambda name: "repoA",
        start="2000-01-01", end="2100-01-01",
    )
    assert not any(r["kind"] == "session" for r in corpus["records"])
    assert "repoA" not in corpus["lineage_counts"]
