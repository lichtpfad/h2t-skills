"""Setup tests never reach the network: `h2t-setup` reads its target from raw GitHub, and a
test that forgets to inject `fetch` must meet this refusal rather than the real pointer
(the research suite learned it in Task 12c). A test that needs a response injects one."""
import pytest


def refuse_network(*args, **kwargs):
    raise AssertionError("a setup test reached the real network")


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    monkeypatch.setattr("urllib.request.urlopen", refuse_network)
