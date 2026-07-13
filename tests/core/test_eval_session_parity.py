"""#321: the two SkillEval copies must stay byte-identical.

`session-start/scripts/gather.py` and `handoff/scripts/writer.py` do
`from eval.session import SkillEval` → the **plugin** copy, which is the live
telemetry-push path. Tests import the **root** copy (`from lib.eval.session`).
A silent drift would ship a no-op activation with a fully green suite (worse
than the gather-drift precedent #283, where staleness was inert). No sync
script — this invariant is the guard.
"""
import filecmp
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
ROOT = REPO / "lib" / "eval" / "session.py"
PLUGIN = REPO / "plugins" / "h2t-core" / "lib" / "eval" / "session.py"


def test_eval_session_copies_identical():
    assert ROOT.exists(), ROOT
    assert PLUGIN.exists(), PLUGIN
    assert filecmp.cmp(ROOT, PLUGIN, shallow=False), (
        "lib/eval/session.py and plugins/h2t-core/lib/eval/session.py diverged; "
        "keep them byte-identical (see #321 / #283)."
    )
