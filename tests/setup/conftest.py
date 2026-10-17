"""Setup tests never reach the network: `h2t-setup` reads its target from raw GitHub, and a
test that forgets to inject `fetch` must meet this refusal rather than the real pointer
(the research suite learned it in Task 12c). A test that needs a response injects one.
The same holds for the real `uv` and `claude`: `sync.run` mutates the machine through them."""
import pytest


def refuse_network(*args, **kwargs):
    raise AssertionError("a setup test reached the real network")


def refuse_tool(*args, **kwargs):
    raise AssertionError("a setup test ran the real uv or claude")


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    monkeypatch.setattr("urllib.request.urlopen", refuse_network)
    # sync.run mutates through these two; a test injects fakes (tests/setup/fake_claude.py).
    monkeypatch.setattr("h2t_ops.setup.sync.run_uv", refuse_tool)
    monkeypatch.setattr("h2t_ops.setup.harness_claude._run_process", refuse_tool)
