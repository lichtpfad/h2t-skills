# test_runner.py
import json
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from gather.runner import run_parallel, output_json

def test_run_parallel_basic():
    """Two independent commands run and return stdout."""
    results = run_parallel({
        "echo_a": ["echo", "hello"],
        "echo_b": ["echo", "world"],
    })
    assert results["echo_a"].strip() == "hello"
    assert results["echo_b"].strip() == "world"

def test_run_parallel_failing_command():
    """Failing command returns empty string, doesn't crash others."""
    results = run_parallel({
        "good": ["echo", "ok"],
        "bad": ["false"],
    })
    assert results["good"].strip() == "ok"
    assert results["bad"] == ""

if __name__ == "__main__":
    test_run_parallel_basic()
    test_run_parallel_failing_command()
    print("All runner tests passed")
