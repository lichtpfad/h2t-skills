from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_eval_session_vendored_parity():
    """The vendored plugin copy (the runtime path) must match canonical root."""
    root = (ROOT / "lib" / "eval" / "session.py").read_text(encoding="utf-8")
    vendored = (
        ROOT / "plugins" / "h2t-core" / "lib" / "eval" / "session.py"
    ).read_text(encoding="utf-8")
    assert root == vendored, "lib/eval/session.py drifted from vendored copy; re-sync"
