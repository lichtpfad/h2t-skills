"""MeetGeek tests never reach the network.

The client calls `requests.request`, the pipeline `requests.get` for media, and recovery
shells out to `h2t-ops`; a test that forgets its fake must fail here rather than talk to
api.meetgeek.ai. Same refusal as tests/connectors/research/conftest.py (Task 12c).
"""
import pytest


def refuse_network(*args, **kwargs):
    raise AssertionError("a meetgeek test reached the real network")


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
