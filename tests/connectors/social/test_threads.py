import json
from pathlib import Path

import pytest
import requests

from h2t_ops.connectors.social.threads import ThreadsClient
from h2t_ops.core.errors import AuthError, NetworkError, ProviderError, exit_code_for

FIX = Path(__file__).parent / "fixtures"
KEY = "THREADS_TOKEN_ACME"
TOKEN = "THAA" + "x" * 10 + "-fake-threads"


def fx(name):
    return json.loads((FIX / f"threads_{name}.json").read_text(encoding="utf-8"))


class FakeSession:
    """Replays (status, body) answers in order; records every call."""

    def __init__(self, *answers):
        self.answers = list(answers)
        self.calls = []

    def get(self, url, params=None, timeout=None):
        self.calls.append((url, params))
        status, body = self.answers.pop(0)
        if isinstance(body, Exception):
            raise body
        return type("R", (), {"status_code": status, "json": lambda self: body})()


@pytest.fixture(autouse=True)
def _secret(monkeypatch, social_data):
    monkeypatch.setattr("h2t_ops.core.secrets.get", lambda key: TOKEN if key == KEY else None)


def client(*answers, **kw):
    return ThreadsClient(KEY, session=FakeSession(*answers), sleep=lambda s: None, **kw)


def test_me():
    c = client((200, fx("me")))
    body, raw = c.me()
    assert body == {"id": "th_111", "username": "acme"} and len(raw) == 1
    url, params = c._session.calls[0]
    assert url == "https://graph.threads.net/v1.0/me"
    assert params["access_token"] == TOKEN and params["fields"] == "id,username"
    assert TOKEN not in repr(c) and TOKEN not in str(c)


def test_posts_paging_stops_at_limit():
    c = client((200, fx("posts_1")), (200, fx("posts_2")), (200, {"data": []}))
    rows, raw = c.posts(3)
    assert [r["id"] for r in rows] == ["t1", "t2", "t3"] and len(raw) == 2
    assert len(c._session.calls) == 2
    rows, raw = client((200, fx("posts_1")), (200, fx("posts_2"))).posts(1)
    assert [r["id"] for r in rows] == ["t1"] and len(raw) == 1


def test_expired_token_is_auth_error():
    with pytest.raises(AuthError) as e:
        client((400, fx("error_190"))).me()
    assert exit_code_for(e.value) == 4
    assert KEY in str(e.value) + e.value.hint and "renew the token" in e.value.hint
    assert TOKEN not in str(e.value) + e.value.hint


def test_missing_token_is_auth_error(monkeypatch):
    monkeypatch.setattr("h2t_ops.core.secrets.get", lambda key: None)
    with pytest.raises(AuthError) as e:
        client().me()
    assert exit_code_for(e.value) == 4 and KEY in str(e.value)


def test_post_insights_values():
    value, raw = client((200, fx("insights"))).post_insights("t1")
    assert value == {"views": 120, "likes": 9, "replies": 2, "reposts": 1, "quotes": 0}
    assert len(raw) == 1


def test_post_insights_unavailable_returns_none():
    value, raw = client((400, fx("error_100"))).post_insights("t1")
    assert value is None and raw[0]["error"]["code"] == 100


def test_profile_insights_reads_totals_and_followers():
    c = client((200, fx("profile_insights")), (200, fx("followers")))
    value, raw = c.profile_insights(30)
    assert value == {"views": 500, "likes": 40, "replies": 7, "followers_count": 321}
    assert len(raw) == 2
    window = c._session.calls[0][1]
    assert int(window["until"]) - int(window["since"]) == 30 * 86400
    assert "since" not in c._session.calls[1][1]


def test_rate_limit_retries_once_then_fails():
    slept = []
    c = ThreadsClient(KEY, session=FakeSession((429, {}), (429, {})), sleep=slept.append,
                      retry_after=7)
    with pytest.raises(ProviderError, match="rate limited, retry later"):
        c.me()
    assert slept == [7] and len(c._session.calls) == 2


def test_network_error_hides_the_token_url():
    exc = requests.ConnectionError(f"boom https://x/me?access_token={TOKEN}")
    with pytest.raises(NetworkError) as e:
        client((0, exc)).me()
    assert TOKEN not in str(e.value) and e.value.__suppress_context__


def test_raw_strips_tokens_from_paging_urls_but_next_request_uses_original():
    first = json.loads(json.dumps(fx("posts_1")).replace("@TOK@", TOKEN))
    c = client((200, first), (200, fx("posts_2")))
    rows, raw = c.posts(10)
    assert len(rows) == 3
    assert TOKEN not in json.dumps(raw) and "access_token" not in json.dumps(raw)
    assert "after=A" in raw[0]["paging"]["next"]
    assert TOKEN in c._session.calls[1][0]


def test_only_get_is_used():
    assert not hasattr(FakeSession, "post")
    assert not hasattr(ThreadsClient, "post")
