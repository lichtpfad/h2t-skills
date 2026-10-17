"""Research tests never reach the network, and never push eval telemetry.

Measured 2026-10-17 (Task 12c): test_commands.py pops the research modules from
sys.modules, a patch in another file then landed on a stale copy, and seven requests went to
api.exa.ai with fake keys. A test that needs a response patches urlopen or requests itself;
everything else meets this refusal instead of the internet.

The connector now writes a SkillEval session after search and crawl (#541). SkillEval reads
H2T_EVALS_* from ~/.dor/secrets.env at import, which on a configured machine can resolve to
`push`; `off` here wins over the file, so only a test that sets the mode records anything.
"""
import pytest


def refuse_network(*args, **kwargs):
    raise AssertionError("a research test reached the real network")


def _loopback(url) -> bool:
    from urllib.parse import urlparse

    url = getattr(url, "full_url", url)
    return urlparse(str(url)).hostname in {"127.0.0.1", "localhost", "::1"}


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    import urllib.request

    import requests

    real_urlopen = urllib.request.urlopen

    def urlopen(url, *args, **kwargs):
        # A test's own local server (the meetgeek webhook) is not the network.
        if _loopback(url):
            return real_urlopen(url, *args, **kwargs)
        return refuse_network(url)

    monkeypatch.setattr("urllib.request.urlopen", urlopen)
    monkeypatch.setattr(requests.sessions.Session, "request", refuse_network)
    monkeypatch.setenv("H2T_EVALS_MODE", "off")
