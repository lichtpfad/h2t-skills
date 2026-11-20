import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
import requests

from h2t_ops.connectors.social import journal
from h2t_ops.connectors.social.meta import MetaClient
from h2t_ops.core.errors import AuthError, NetworkError, ProviderError, exit_code_for

FIX = Path(__file__).parent / "fixtures"
USER_TOKEN = "EAA" + "x" * 10 + "-fake-user"


def fx(name):
    return json.loads((FIX / f"meta_{name}.json").read_text(encoding="utf-8"))


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
    monkeypatch.setattr("h2t_ops.core.secrets.get",
                        lambda key: USER_TOKEN if key == "META_H2T_SOCIAL_USER_TOKEN" else None)
    monkeypatch.setattr(journal, "_runtime_secrets", set())


def client(*answers, **kw):
    return MetaClient(session=FakeSession(*answers), sleep=lambda s: None, **kw)


def test_pages_follow_paging_and_keep_tokens_out_of_repr():
    c = client((200, fx("accounts_1")), (200, fx("accounts_2")))
    rows, raw = c.pages()
    assert [r["page_id"] for r in rows] == ["page_222", "page_223", "page_224"]
    assert rows[0]["ig_username"] == "acme" and rows[1]["ig_id"] is None
    for tok in ("PGTOK1", "PGTOK2", "PGTOK3", USER_TOKEN):
        assert tok not in repr(c) and tok not in str(c)
    assert "PGTOK1" in journal._runtime_secrets and USER_TOKEN in journal._runtime_secrets


def test_media_paging_stops_at_limit():
    def page(start, nxt):
        body = {"data": [{"id": f"m{i}"} for i in range(start, start + 100)]}
        if nxt:
            body["paging"] = {"next": "https://graph.facebook.com/v27.0/ig_111/media?after=B"}
        return 200, body

    c = client(page(0, True), page(100, True), page(200, False))
    rows, raw = c.ig_media("ig_111", "PGTOK1", 150)
    assert len(rows) == 150 and len(raw) == 2 and len(c._session.calls) == 2


def test_insights_unavailable_returns_none():
    value, raw = client((400, fx("error_100"))).ig_media_insights("m1", "PGTOK1")
    assert value is None and raw[0]["error"]["code"] == 100


def test_insights_values():
    value, _ = client((200, fx("insights"))).ig_media_insights("m1", "PGTOK1")
    assert value == {"reach": 120, "views": 300, "total_interactions": 15}


def test_expired_token_is_auth_error():
    with pytest.raises(AuthError) as e:
        client((400, fx("error_190"))).ig_profile("ig_111", "PGTOK1")
    assert exit_code_for(e.value) == 4
    assert "META_H2T_SOCIAL_USER_TOKEN" in str(e.value) + e.value.hint and "renew the token" in e.value.hint
    assert "PGTOK1" not in str(e.value) and USER_TOKEN not in str(e.value) + e.value.hint


def test_missing_user_token_is_auth_error(monkeypatch):
    monkeypatch.setattr("h2t_ops.core.secrets.get", lambda key: None)
    with pytest.raises(AuthError) as e:
        client().pages()
    assert exit_code_for(e.value) == 4 and "META_H2T_SOCIAL_USER_TOKEN" in str(e.value)


def test_raw_has_one_body_per_call():
    _, raw = client((200, fx("accounts_1")), (200, fx("accounts_2"))).pages()
    assert len(raw) == 2


def test_rate_limit_retries_once_then_fails():
    slept = []
    c = MetaClient(session=FakeSession((429, {}), (429, {})), sleep=slept.append, retry_after=7)
    with pytest.raises(ProviderError, match="rate limited, retry later"):
        c.ig_profile("ig_111", "PGTOK1")
    assert slept == [7] and len(c._session.calls) == 2


def test_rate_limit_code_then_success():
    c = client((400, fx("error_4")), (200, fx("profile")))
    body, raw = c.ig_profile("ig_111", "PGTOK1")
    assert body["username"] == "acme" and len(raw) == 2


def test_network_error_hides_the_token_url():
    exc = requests.ConnectionError(f"boom https://x/me?access_token={USER_TOKEN}")
    with pytest.raises(NetworkError) as e:
        client((0, exc)).pages()
    assert USER_TOKEN not in str(e.value) and e.value.__suppress_context__


def test_online_followers_mean_per_hour():
    means, _ = client((200, fx("online_followers"))).ig_online_followers("ig_111", "PGTOK1")
    assert means == {0: 20.0, 1: 30.0}


def test_only_get_is_used():
    assert not hasattr(FakeSession, "post")
    c = client((200, fx("profile")))
    c.ig_profile("ig_111", "PGTOK1")
    assert c._session.calls[0][1]["access_token"] == "PGTOK1"


def _tokenized():
    text = (FIX / "meta_accounts_tokenized.json").read_text(encoding="utf-8")
    return json.loads(text.replace("@TOK@", USER_TOKEN))


def test_raw_strips_tokens_from_paging_urls_but_next_request_uses_original():
    c = client((200, _tokenized()), (200, fx("accounts_2")))
    rows, raw = c.pages()
    assert len(rows) == 2
    assert USER_TOKEN not in json.dumps(raw) and "deadbeef" not in json.dumps(raw)
    assert "after=A" in raw[0]["paging"]["next"]
    assert USER_TOKEN in c._session.calls[1][0]     # the original URL still carries the token


def test_tokenized_raw_body_is_journalled(social_data):
    _, raw = client((200, _tokenized()), (200, fx("accounts_2"))).pages()
    journal.write_raw("run1", "insights", "instagram:acme", "me/accounts", raw[0])
    text = journal.raw_path("insights", datetime.now(UTC).strftime("%Y-%m-%d")).read_text(encoding="utf-8")
    assert USER_TOKEN not in text and "PGTOK1" not in text


def test_find_page_matches_by_instagram_id_or_page_id():
    from h2t_ops.connectors.social.config import Account
    from h2t_ops.connectors.social.meta import find_page

    pages = [{"page_id": "page_1", "ig_id": None}, {"page_id": "page_2", "ig_id": "ig_2"}]

    def acc(remote_id, page_id):
        return Account("instagram:x", "instagram", "x", remote_id, page_id, "META_H2T_SOCIAL_USER_TOKEN", None, True)

    assert find_page(pages, acc("ig_2", None)) is pages[1]
    assert find_page(pages, acc("ig_9", "page_1")) is pages[0]
    assert find_page(pages, acc("ig_9", None)) is None


def test_page_insights_parses_dates_and_values():
    c = client((200, fx("page_insights")))
    body, raw = c.page_insights("page_222", "PGTOK1", "page_post_engagements", 1000, 2000)
    assert body == {"values": [{"date": "2026-11-18", "value": 12}, {"date": "2026-11-19", "value": 30}]}
    assert len(raw) == 1


def test_page_insights_sends_metric_period_and_window():
    c = client((200, fx("page_insights")))
    c.page_insights("page_222", "PGTOK1", "page_post_engagements", 1000, 2000)
    url, params = c._session.calls[0]
    assert url.endswith("/page_222/insights")
    assert params["metric"] == "page_post_engagements" and params["period"] == "day"
    assert params["since"] == 1000 and params["until"] == 2000 and params["access_token"] == "PGTOK1"


@pytest.mark.parametrize("name,code", [("error_10", 10), ("error_100", 100)])
def test_page_insights_soft_errors_return_the_error_not_raise(name, code):
    body, raw = client((400, fx(name))).page_insights("page_222", "PGTOK1", "page_fans", 1, 2)
    assert body["error"]["code"] == code and body["error"]["message"] and "values" not in body
    assert raw[0]["error"]["code"] == code


def test_page_insights_error_message_never_holds_a_token():
    leaked = {"error": {"message": "bad token PGTOK1 here", "code": 10}}
    body, _ = client((400, leaked)).page_insights("page_222", "PGTOK1", "m", 1, 2)
    assert "PGTOK1" not in body["error"]["message"]
