import json

import pytest

from h2t_ops.connectors.social import insights
from h2t_ops.connectors.social.journal import journal_path
from h2t_ops.core.errors import AuthError, ConfigError, NetworkError, ProviderError


def _post(ts, reach, link="https://x/p"):
    return {"id": ts, "timestamp": ts, "permalink": link, "metrics": {"reach": reach}}


def test_summarize_bands_and_weekdays():
    posts = [
        _post("2026-11-02T09:00:00+0000", 100),   # Mon 00-10
        _post("2026-11-02T10:30:00+0000", 200),   # Mon 10-13
        _post("2026-11-03T14:00:00+0000", 300),   # Tue 13-16
        _post("2026-11-04T17:00:00+0000", 400),   # Wed 16-19
        _post("2026-11-05T20:00:00+0000", 500),   # Thu 19-22
        _post("2026-11-06T23:00:00+0000", 600),   # Fri 22-24
    ]
    s = insights.summarize(posts, "UTC")
    assert s["posts"] == 6 and s["skipped"] == 0
    assert s["median_reach"] == 350
    assert s["by_weekday"]["Mon"] == {"n": 2, "median": 150, "ratio": round(150 / 350, 2)}
    assert s["by_weekday"]["Fri"] == {"n": 1, "median": 600, "ratio": round(600 / 350, 2)}
    assert s["by_hour_band"]["10-13"] == {"n": 1, "median": 200, "ratio": round(200 / 350, 2)}
    assert s["by_hour_band"]["22-24"]["median"] == 600
    assert [p["reach"] for p in s["top"]] == [600, 500, 400, 300, 200]
    assert s["top"][0]["permalink"] == "https://x/p"
    assert list(s["by_weekday"]) == ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    assert list(s["by_hour_band"]) == ["00-10", "10-13", "13-16", "16-19", "19-22", "22-24"]
    assert s["by_weekday"]["Sat"] == {"n": 0, "median": None, "ratio": None}


def test_summarize_uses_timezone():
    s = insights.summarize([_post("2026-11-02T23:30:00+0000", 10)], "Asia/Tokyo")   # Tue 08:30 local
    assert "Tue" in s["by_weekday"] and "00-10" in s["by_hour_band"]


def test_summarize_threads_uses_views():
    post = {"id": "1", "network": "threads", "timestamp": "2026-11-02T09:00:00+0000", "permalink": "p",
            "metrics": {"views": 42, "reach": 1}}
    assert insights.summarize([post], "UTC")["median_reach"] == 42


def test_instagram_post_without_reach_is_skipped_not_taken_from_views():
    post = {"id": "1", "network": "instagram", "timestamp": "2026-11-02T09:00:00+0000", "permalink": "p",
            "metrics": {"views": 42}}
    s = insights.summarize([post], "UTC")
    assert s["posts"] == 0 and s["skipped"] == 1


def test_threads_post_without_views_is_skipped_not_taken_from_reach():
    post = {"id": "1", "network": "threads", "timestamp": "2026-11-02T09:00:00+0000", "permalink": "p",
            "metrics": {"reach": 42}}
    s = insights.summarize([post], "UTC")
    assert s["posts"] == 0 and s["skipped"] == 1


def test_media_without_insights_is_skipped_and_counted():
    posts = [_post(f"2026-11-0{d}T09:00:00+0000", d * 10) for d in range(1, 6)]
    posts.append({"id": "9", "timestamp": "2026-11-09T09:00:00+0000", "permalink": "p", "metrics": None})
    s = insights.summarize(posts, "UTC")
    assert s["skipped"] == 1 and s["posts"] == 5


class FakeMeta:
    def __init__(self, media, metrics=None, online=None):
        self.media, self.metrics, self.online = media, metrics or {}, online or {}

    def pages(self):
        return [{"page_id": "page_222", "page_token": "PT", "ig_id": "ig_111"}], [{"data": ["pages"]}]

    def ig_media(self, ig_id, page_token, limit):
        assert page_token == "PT"
        return self.media, [{"data": ["media"]}]

    def ig_media_insights(self, media_id, page_token):
        return self.metrics.get(media_id), [{"data": [media_id]}]

    def ig_online_followers(self, ig_id, page_token, days=29):
        return self.online, [{"data": ["online"]}]


class FakeThreads:
    def posts(self, limit):
        return [{"id": "t1", "timestamp": "2026-11-02T09:00:00+0000", "permalink": "tp"}], [{"data": ["posts"]}]

    def post_insights(self, post_id):
        return {"views": 7}, [{"data": [post_id]}]


def _accounts(*extra):
    base = {"network": "instagram", "handle": "acme", "remote_id": "ig_111", "page_id": "page_222",
            "token_key": "META_USER_TOKEN"}
    return {"accounts": [base, *extra]}


def _media(n):
    return [{"id": f"m{i}", "timestamp": f"2026-11-0{i}T09:00:00+0000", "permalink": f"p{i}"}
            for i in range(1, n + 1)]


@pytest.fixture
def tz(monkeypatch):
    monkeypatch.setattr("h2t_ops.core.user_config.get", lambda key, *a: "UTC" if key == "timezone" else None)


def _journal():
    return [json.loads(line) for line in journal_path().read_text(encoding="utf-8").splitlines()]


def test_empty_media_fails_loud(social_config, social_data, tz):
    social_config(accounts=_accounts())
    with pytest.raises(ProviderError, match="no data.*instagram:acme"):
        insights.run(None, 10, client_factory=lambda n, a: FakeMeta([]))
    recs = _journal()
    assert [r["step"] for r in recs if r["step"] != 2] == [1, 3, 4, 6]
    raw_ids = [r["source_ids"][0] for r in recs if r["step"] == 2]
    step3 = next(r for r in recs if r["step"] == 3)
    assert step3["source_ids"] == raw_ids and step3["finding"] == "no data"
    assert next(r for r in recs if r["step"] == 4)["decision"] == "noop"
    assert next(r for r in recs if r["step"] == 6)["result"]["error"] == "ProviderError: no data for instagram:acme: no posts with metrics"


def test_all_posts_without_metrics_fails_loud(social_config, social_data, tz):
    social_config(accounts=_accounts())
    with pytest.raises(ProviderError, match="no data"):
        insights.run(None, 10, client_factory=lambda n, a: FakeMeta(_media(2)))


def test_missing_timezone_is_config_error(social_config, social_data, monkeypatch):
    social_config(accounts=_accounts())
    monkeypatch.setattr("h2t_ops.core.user_config.get", lambda key, *a: None)
    with pytest.raises(ConfigError) as e:
        insights.run(None, 10, client_factory=lambda n, a: FakeMeta(_media(1)))
    assert "user.yaml" in (e.value.hint or "")


def test_online_followers_hours_are_not_converted(social_config, social_data, tz):
    social_config(accounts=_accounts())
    client = FakeMeta(_media(1), {"m1": {"reach": 5}}, online={"0": 5, "13": 9})
    out = insights.run(None, 10, client_factory=lambda n, a: client)
    assert out["reports"]["instagram:acme"]["online_followers_hour_as_reported"] == {"0": 5, "13": 9}


def test_run_writes_provenance_chain(social_config, social_data, tz):
    social_config(accounts=_accounts())
    client = FakeMeta(_media(2), {"m1": {"reach": 5}, "m2": {"reach": 9}})
    out = insights.run(None, 10, client_factory=lambda n, a: client)
    recs = [r for r in _journal() if r["run_id"] == out["run_id"]]
    assert [r["step"] for r in recs if r["step"] != 2] == [1, 3, 4, 6]
    raw_ids = [r["source_ids"][0] for r in recs if r["step"] == 2]
    assert len(raw_ids) == 5   # pages, media, 2 insights, online followers
    step3 = next(r for r in recs if r["step"] == 3)
    assert step3["source_ids"] == raw_ids
    assert next(r for r in recs if r["step"] == 4)["decision"] == "noop"
    step6 = next(r for r in recs if r["step"] == 6)
    report = social_data / "social" / "insights" / "instagram_acme"
    assert step6["report"].startswith(str(report))
    assert json.loads(open(step6["report"], encoding="utf-8").read())["posts"] == 2


def test_threads_account_report_has_no_online_followers(social_config, social_data, tz):
    acc = {"network": "threads", "handle": "acme", "remote_id": "t_1", "token_key": "THREADS_TOKEN_ACME"}
    social_config(accounts={"accounts": [acc]})
    out = insights.run(None, 10, client_factory=lambda n, a: FakeThreads())
    r = out["reports"]["threads:acme"]
    assert r["median_reach"] == 7 and "online_followers_hour_as_reported" not in r


def test_disabled_accounts_are_skipped(social_config, social_data, tz):
    off = {"network": "instagram", "handle": "off", "remote_id": "ig_9", "token_key": "META_USER_TOKEN",
           "enabled": False}
    social_config(accounts=_accounts(off))
    client = FakeMeta(_media(1), {"m1": {"reach": 5}})
    out = insights.run(None, 10, client_factory=lambda n, a: client)
    assert list(out["reports"]) == ["instagram:acme"]


def test_facebook_account_is_skipped_with_note(social_config, social_data, tz):
    fb = {"network": "facebook", "handle": "acme", "remote_id": "page_222", "token_key": "META_USER_TOKEN"}
    social_config(accounts=_accounts(fb))
    client = FakeMeta(_media(1), {"m1": {"reach": 5}})
    out = insights.run(None, 10, client_factory=lambda n, a: client)
    assert "facebook:acme" not in out["reports"] and "facebook:acme" in out["skipped_accounts"]


class BoomMeta(FakeMeta):
    def __init__(self, exc, **kw):
        super().__init__(_media(2), **kw)
        self.exc = exc

    def ig_media_insights(self, media_id, page_token):
        raise self.exc


@pytest.mark.parametrize("exc", [AuthError("token rejected"), NetworkError("down"),
                                 ProviderError("rate limited, retry later")])
def test_failure_mid_run_ends_with_one_step6_record(social_config, social_data, tz, exc):
    social_config(accounts=_accounts())
    with pytest.raises(type(exc)):
        insights.run(None, 10, client_factory=lambda n, a: BoomMeta(exc))
    recs = _journal()
    assert [r["step"] for r in recs] == [1, 2, 2, 6]   # run, pages, media, then the failure
    assert recs[-1]["result"]["error"] == f"{type(exc).__name__}: {exc}"
    assert recs[-1]["account"] == "instagram:acme"


def test_report_write_failure_ends_with_one_step6_record(social_config, social_data, tz, monkeypatch):
    social_config(accounts=_accounts())
    def boom(*a, **k):
        raise OSError("disk full")
    monkeypatch.setattr("h2t_ops.core.store.replace", boom)
    with pytest.raises(OSError):
        insights.run(None, 10, client_factory=lambda n, a: FakeMeta(_media(1), {"m1": {"reach": 5}}))
    recs = _journal()
    assert [r["step"] for r in recs][-1] == 6
    assert sum(r["step"] == 6 for r in recs) == 1
    assert recs[-1]["result"]["error"] == "OSError: disk full"


def test_no_data_failure_has_exactly_one_step6(social_config, social_data, tz):
    social_config(accounts=_accounts())
    with pytest.raises(ProviderError):
        insights.run(None, 10, client_factory=lambda n, a: FakeMeta([]))
    assert sum(r["step"] == 6 for r in _journal()) == 1
