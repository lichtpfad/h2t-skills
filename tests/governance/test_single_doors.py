"""ingest_write and remove(journal=True) have no import site outside their one module
(§7.2, plan R1, R35). Until subsystem 4 adds h2t_ops/ingest/, "exactly one" cannot hold;
it becomes `==` there."""
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _sites(rx):
    # --others: a planted, unstaged file must count, or the red control cannot go red.
    files = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard", "h2t_ops/"],
                           cwd=ROOT, capture_output=True, text=True, check=True).stdout.split()
    return [f for f in files if f.endswith(".py") and f != "h2t_ops/core/store.py"
            and (ROOT / f).is_file() and re.search(rx, (ROOT / f).read_text(encoding="utf-8"))]


def test_ingest_write_only_in_the_ingest_module():
    assert [s for s in _sites(r"\bingest_write\b") if not s.startswith("h2t_ops/ingest/")] == []


def test_journal_remove_only_in_rollback():
    assert set(_sites(r"journal\s*=\s*True")) == {"h2t_ops/setup/layout/rollback.py"}


def test_in_place_only_in_the_research_store():
    """store.replace(in_place=True) skips the atomic write; one caller has a reason (§7.2)."""
    assert set(_sites(r"\bin_place\s*=")) == {"h2t_ops/connectors/research/store.py"}
