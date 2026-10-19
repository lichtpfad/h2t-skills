"""Every module that wrote to disk before 4.0 is exercised by a sandbox case (#548 §7.3, R27).

Observed, not named: a case counts for a module only if the module was on the stack of a
write while the case ran."""
from pathlib import Path

import pytest

from tests.governance.sandbox_cases import CASES
from tests.governance.test_sandbox import build_sandbox, run_case

BASELINE = sorted(Path(__file__).with_name("writers_baseline.txt").read_text(encoding="utf-8").split())


@pytest.fixture(scope="module")
def observed(tmp_path_factory):
    seen: set[str] = set()
    for i, case in enumerate(CASES):
        with pytest.MonkeyPatch.context() as mp, \
                build_sandbox(tmp_path_factory.mktemp(f"case{i}"), mp) as sb:
            run_case(case, sb, mp)
            seen |= sb.recorder.writers
    return seen


def test_baseline_is_the_scanner_output():
    assert len(BASELINE) == 46 and all(m.endswith(".py") for m in BASELINE)


@pytest.mark.parametrize("module", BASELINE)
def test_every_writer_is_exercised(module, observed):
    assert module in observed, f"{module}: no sandbox case reached a write in it"
