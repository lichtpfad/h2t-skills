# test_runner.py
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from gather.runner import output_json, run_parallel


def test_run_parallel_basic():
    """Two independent commands run and return stdout."""
    results = run_parallel({
        "echo_a": [sys.executable, "-c", "print('hello')"],
        "echo_b": [sys.executable, "-c", "print('world')"],
    })
    assert results["echo_a"].strip() == "hello"
    assert results["echo_b"].strip() == "world"

def test_run_parallel_failing_command():
    """Failing command returns None, doesn't crash others."""
    results = run_parallel({
        "good": [sys.executable, "-c", "print('ok')"],
        "bad": [sys.executable, "-c", "import sys; sys.exit(1)"],
    })
    assert results["good"].strip() == "ok"
    assert results["bad"] is None

def test_run_parallel_distinguishes_failure_from_empty_output():
    """A command that succeeds with no output must not look like one that failed.

    Both used to return "", so a timed-out `gh issue list` was indistinguishable
    from a repo with no issues — and the briefing reported the latter.
    """
    results = run_parallel({
        "silent": [sys.executable, "-c", "pass"],
        "exit_1": [sys.executable, "-c", "import sys; sys.exit(1)"],
        "missing": ["h2t-no-such-binary-8b41f2"],
    })
    assert results["silent"] == ""
    assert results["exit_1"] is None
    assert results["missing"] is None

if __name__ == "__main__":
    test_run_parallel_basic()
    test_run_parallel_failing_command()
    print("All runner tests passed")
