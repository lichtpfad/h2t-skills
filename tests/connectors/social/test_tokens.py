import json
from datetime import UTC, datetime, timedelta

import pytest

from h2t_ops.connectors.social import journal, tokens
from h2t_ops.connectors.social.threads import ThreadsClient
from h2t_ops.core.errors import ConfigError, NotFoundError

NOW = datetime(2026, 11, 19, 12, 0, tzinfo=UTC)
OLD_A, OLD_B, NEW = "OLDA-fake-token-aaaa", "OLDB-fake-token-bbbb", "NEWT-fake-token-cccc"


class FakeClient:
    calls: list = []

    def __init__(self, key):
        self.key = key

    def refresh(self):
        FakeClient.calls.append(self.key)
        journal.register_secret(NEW)
        return {"access_token": NEW, "expires_in": 5184000}, [
            {"access_token": NEW, "token_type": "bearer", "expires_in": 5184000}]


@pytest.fixture
def env(social_data, monkeypatch):
    """Two Threads keys in a fake shared threads.env; write_env is captured."""
    FakeClient.calls = []
    shared = {"threads.env": {"THREADS_TOKEN_A": OLD_A, "THREADS_TOKEN_B": OLD_B}}
    written = []
    monkeypatch.setattr("h2t_ops.core.secrets.keys_with_prefix",
                        lambda prefix: sorted(shared["threads.env"]))
    monkeypatch.setattr("h2t_ops.core.secrets.shared_env_values", lambda: shared)
    monkeypatch.setattr("h2t_ops.core.secrets.write_env",
                        lambda provider, values, **kw: written.append((provider, dict(values))))
    return written


def seed(expiries):
    path = tokens.expiry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(expiries), encoding="utf-8")


def test_refresh_near_expiry(env):
    seed({"THREADS_TOKEN_A": (NOW + timedelta(days=2)).isoformat(),
          "THREADS_TOKEN_B": (NOW + timedelta(days=50)).isoformat()})
    out = tokens.refresh(now=NOW, client_factory=FakeClient)
    new_exp = (NOW + timedelta(seconds=5184000)).isoformat()
    assert out["refreshed"] == [{"key": "THREADS_TOKEN_A", "expires_at": new_exp}]
    assert env == [("threads", {"THREADS_TOKEN_A": NEW, "THREADS_TOKEN_B": OLD_B})]
    assert json.loads(tokens.expiry_path().read_text(encoding="utf-8"))["THREADS_TOKEN_A"] == new_exp


def test_skip_far_from_expiry(env):
    far = (NOW + timedelta(days=50)).isoformat()
    seed({"THREADS_TOKEN_A": far, "THREADS_TOKEN_B": far})
    out = tokens.refresh(now=NOW, client_factory=FakeClient)
    assert out["refreshed"] == []
    assert out["skipped"] == [{"key": "THREADS_TOKEN_A", "expires_at": far},
                              {"key": "THREADS_TOKEN_B", "expires_at": far}]
    assert FakeClient.calls == [] and env == []


def test_unknown_expiry_is_refreshed(env):
    out = tokens.refresh(now=NOW, client_factory=FakeClient)
    assert [r["key"] for r in out["refreshed"]] == ["THREADS_TOKEN_A", "THREADS_TOKEN_B"]
    recorded = json.loads(tokens.expiry_path().read_text(encoding="utf-8"))
    assert set(recorded) == {"THREADS_TOKEN_A", "THREADS_TOKEN_B"}


def test_other_threads_keys_survive(env):
    seed({"THREADS_TOKEN_A": (NOW + timedelta(days=1)).isoformat(),
          "THREADS_TOKEN_B": (NOW + timedelta(days=60)).isoformat()})
    tokens.refresh(now=NOW, client_factory=FakeClient)
    (provider, values), = env
    assert provider == "threads" and values["THREADS_TOKEN_B"] == OLD_B
    assert values["THREADS_TOKEN_A"] == NEW


def test_token_value_never_in_journal(env, social_data):
    tokens.refresh(now=NOW, client_factory=FakeClient)
    text = journal.journal_path().read_text(encoding="utf-8")
    text += "".join(p.read_text(encoding="utf-8") for p in (social_data / "social" / "raw").rglob("*.jsonl"))
    text += tokens.expiry_path().read_text(encoding="utf-8")
    assert "THREADS_TOKEN_A" in text
    for value in (OLD_A, OLD_B, NEW):
        assert value not in text


def test_token_value_in_step6_record_is_refused(env):
    journal.register_secret(NEW)
    run = journal.new_run("tokens", "cli")
    with pytest.raises(journal.SecretInRecord):
        journal.record(run, 6, process="tokens", key="THREADS_TOKEN_A", expires_at=NEW)


def test_no_threads_keys_is_not_found(social_data, monkeypatch):
    monkeypatch.setattr("h2t_ops.core.secrets.keys_with_prefix", lambda prefix: [])
    with pytest.raises(NotFoundError):
        tokens.refresh(now=NOW, client_factory=FakeClient)


class FakeSession:
    def __init__(self, body):
        self.body, self.calls = body, []

    def get(self, url, params=None, timeout=None):
        self.calls.append((url, params))
        return type("R", (), {"status_code": 200, "json": lambda s: self.body})()


def test_threads_refresh_url(social_data, monkeypatch):
    old = "THOLD-fake-" + "x" * 8
    monkeypatch.setattr("h2t_ops.core.secrets.get", lambda key: old)
    session = FakeSession({"access_token": NEW, "token_type": "bearer", "expires_in": 5184000})
    c = ThreadsClient("THREADS_TOKEN_A", session=session)
    result, raw = c.refresh()
    url, params = session.calls[0]
    assert url == "https://graph.threads.net/refresh_access_token"
    assert params == {"grant_type": "th_refresh_token", "access_token": old}
    assert result == {"access_token": NEW, "expires_in": 5184000}
    assert NEW in c._secrets and NEW in journal._runtime_secrets
    assert len(raw) == 1


def test_env_sourced_key_refuses_before_any_call(env, monkeypatch):
    monkeypatch.setattr("h2t_ops.core.secrets.source",
                        lambda key: "env" if key == "THREADS_TOKEN_A" else "shared")
    with pytest.raises(ConfigError) as info:
        tokens.refresh(now=NOW, client_factory=FakeClient)
    assert "THREADS_TOKEN_A" in str(info.value)
    assert OLD_A not in str(info.value)
    assert FakeClient.calls == [] and env == []


def test_env_sourced_key_far_from_expiry_is_not_refused(env, monkeypatch):
    far = (NOW + timedelta(days=50)).isoformat()
    seed({"THREADS_TOKEN_A": far, "THREADS_TOKEN_B": far})
    monkeypatch.setattr("h2t_ops.core.secrets.source", lambda key: "env")
    out = tokens.refresh(now=NOW, client_factory=FakeClient)
    assert out["refreshed"] == []
