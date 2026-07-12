from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
VENDORED = ["session.py", "skill_class.py"]


@pytest.mark.parametrize("name", VENDORED)
def test_eval_vendored_parity(name):
    """The vendored plugin copy (the runtime path) must match canonical root."""
    root = (ROOT / "lib" / "eval" / name).read_text(encoding="utf-8")
    vendored = (ROOT / "plugins" / "h2t-core" / "lib" / "eval" / name).read_text(encoding="utf-8")
    assert root == vendored, f"lib/eval/{name} drifted from vendored copy; re-sync"
