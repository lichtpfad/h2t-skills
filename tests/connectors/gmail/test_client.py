"""Auth re-wrap tests for the Gmail connector client (Task 2, §4.1 enforcement).

Three behavioral assertions (per plan):
  (a) missing google libs            -> ConfigError
  (b) no creds & no refresh token    -> ConfigError AND browser never launched
  (c) creds.refresh() raising        -> AuthError

Seam note: the plan's reference test patched `_install_app_flow` and
`_load_credentials`. Implementer discretion (explicitly permitted, seam shape
only): we add a third thin seam `_request()` and patch it in test (c). Reason:
google libs are NOT installed in the `uv run h2t-ops dev pytest` env (Task 7
declares them later). Without patching `_request`, the byte-identical
`creds.refresh(_request())` would hit `from google.auth.transport.requests
import Request` and raise ImportError -> ConfigError, masking the AuthError we
mean to assert. Patching `_request` keeps test (c) exercising the *real*
refresh-failure -> AuthError code path. All three assertions still hold and
still hit real code paths.
"""
import builtins
import sys

import pytest


def test_missing_google_libs_raises_configerror(monkeypatch):
    monkeypatch.delitem(sys.modules, "h2t_ops.connectors.gmail.client", raising=False)
    real = builtins.__import__

    def guard(name, *a, **k):
        if name.startswith("google") or name == "googleapiclient":
            raise ImportError(f"No module named {name!r}")
        return real(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", guard)
    from h2t_ops.connectors.gmail.client import GmailClient
    from h2t_ops.core.errors import ConfigError
    with pytest.raises(ConfigError):
        GmailClient()


def test_no_creds_no_refresh_raises_configerror_not_browser(monkeypatch, tmp_path):
    """§4.1 enforcement: must raise ConfigError, must NOT launch run_local_server.

    After T1 helper relocation, patches target the substrate namespace
    (`h2t_ops.core.google_auth`). The `_Flow` discriminator stub remains as
    a regression guard: if some future refactor reintroduces a browser-
    launching path inside `resolve_google_credentials`, this test fails.
    """
    from h2t_ops.connectors.gmail import client as gmod
    from h2t_ops.core import google_auth as ga
    from h2t_ops.core.errors import ConfigError

    cfg = tmp_path / ".config" / "gmail"
    cfg.mkdir(parents=True)
    (cfg / "credentials.json").write_text("{}")
    monkeypatch.setattr(ga.Path, "home", staticmethod(lambda: tmp_path))
    monkeypatch.setattr(ga, "_load_credentials", lambda *a, **k: None)

    launched = {"browser": False}

    class _Flow:
        @staticmethod
        def from_client_secrets_file(*a, **k):
            launched["browser"] = True
            raise AssertionError("run_local_server must never be reached")

    monkeypatch.setattr(ga, "_install_app_flow", lambda: _Flow)
    with pytest.raises(ConfigError):
        gmod.GmailClient()
    assert launched["browser"] is False


def test_refresh_failure_raises_autherror(monkeypatch, tmp_path):
    """After T1 helper relocation, this test patches the substrate namespace
    (`h2t_ops.core.google_auth`), not the legacy gmail-local helpers (which
    no longer exist post-migration).
    """
    from h2t_ops.connectors.gmail import client as gmod
    from h2t_ops.core import google_auth as ga
    from h2t_ops.core.errors import AuthError

    # Safety: keep Path.home isolated so nothing accidentally reads real
    # ~/.config or ~/.dor during this test.
    monkeypatch.setattr(ga.Path, "home", staticmethod(lambda: tmp_path))

    class _Creds:
        valid = False
        expired = True
        refresh_token = "r"
        # scopes must satisfy _validate_scopes(_GMAIL_SCOPES) — use the exact
        # set the gmail client requires (imported from the same module).
        scopes = list(gmod._GMAIL_SCOPES)
        def refresh(self, _req):
            raise RuntimeError("invalid_grant")

    monkeypatch.setattr(ga, "_load_credentials", lambda *a, **k: _Creds())
    # Stub the lazy Request() seam — google libs absent in test env.
    monkeypatch.setattr(ga, "_request", lambda: object())
    with pytest.raises(AuthError):
        gmod.GmailClient()


# --- Task 3: read methods + HTTP error mapping ---

import types  # noqa: E402


class _FakeService:
    def __init__(self, **resp): self._r = resp
    def users(self): return self
    def messages(self): return self
    def threads(self): return self
    def labels(self): return self
    def list(self, **k): return _Exec(self._r.get("list", {}))
    def get(self, **k): return _Exec(self._r.get("get", {}))


class _Exec:
    def __init__(self, v): self._v = v
    def execute(self): return self._v


def _client_with(service):
    from h2t_ops.connectors.gmail import client as gmod
    c = gmod.GmailClient.__new__(gmod.GmailClient)  # bypass __init__/_get_service
    c.service = service
    return c, gmod


def test_list_messages_happy():
    svc = _FakeService(list={"messages": [{"id": "1"}]},
                       get={"id": "1", "threadId": "t", "labelIds": [], "snippet": "",
                            "payload": {"headers": [{"name": "Subject", "value": "S"}]}})
    c, _ = _client_with(svc)
    out = c.list_messages(max_results=1)
    assert out[0]["id"] == "1" and out[0]["subject"] == "S"
    assert out[0]["attachments"] == []


def test_get_message_404_maps_notfound(monkeypatch):
    from h2t_ops.core.errors import NotFoundError

    class _HttpErr(Exception):
        resp = types.SimpleNamespace(status=404)

    class _Svc(_FakeService):
        def get(self, **k):
            raise _HttpErr("not found")

    c, gmod = _client_with(_Svc())
    monkeypatch.setattr(gmod, "HttpError", _HttpErr)
    with pytest.raises(NotFoundError):
        c.get_message("missing")


def test_get_thread_returns_parsed_messages():
    payload = {
        "id": "thr1",
        "messages": [
            {
                "id": "m1",
                "threadId": "thr1",
                "labelIds": [],
                "snippet": "hello",
                "payload": {
                    "headers": [
                        {"name": "From", "value": "a@example.com"},
                        {"name": "To", "value": "b@example.com"},
                        {"name": "Subject", "value": "Subject"},
                        {"name": "Date", "value": "Tue"},
                    ],
                    "body": {"data": "Qm9keQ=="},
                },
            }
        ],
    }

    class _Svc(_FakeService):
        def get(self, **kwargs):
            return _Exec(payload)

    c, _ = _client_with(_Svc())
    out = c.get_thread("thr1")
    assert out["id"] == "thr1"
    assert out["messages"][0]["id"] == "m1"
    assert out["messages"][0]["body"] == "Body"


def test_list_threads_returns_thread_summaries():
    class _Svc(_FakeService):
        def list(self, **kwargs):
            return _Exec({"threads": [{"id": "thr1"}]})

        def get(self, **kwargs):
            return _Exec({"id": "thr1", "messages": []})

    c, _ = _client_with(_Svc())
    out = c.list_threads(max_results=5, query="label:inbox")
    assert out == [{"id": "thr1", "messages": []}]


@pytest.mark.parametrize("status,exc_name", [
    (401, "AuthError"), (403, "AuthError"), (404, "NotFoundError"),
    (500, "ProviderError"), (503, "ProviderError"), (0, "ProviderError"),
])
def test_map_http_error_status_branches(status, exc_name):
    import h2t_ops.core.errors as errs
    from h2t_ops.connectors.gmail import client as gmod
    e = type("_E", (Exception,), {"resp": types.SimpleNamespace(status=status)})("boom")
    assert isinstance(gmod._map_http_error(e, op="x"), getattr(errs, exc_name))


def test_map_http_error_network_substring():
    from h2t_ops.connectors.gmail import client as gmod
    from h2t_ops.core.errors import NetworkError
    assert isinstance(gmod._map_http_error(Exception("connection timed out"), op="x"),
                      NetworkError)


def test_map_http_error_passthrough_does_not_downgrade():
    """ТЗ-0 CRITICAL: an already-typed H2TError must pass through unchanged."""
    from h2t_ops.connectors.gmail import client as gmod
    from h2t_ops.core.errors import NotFoundError
    nf = NotFoundError("x")
    assert gmod._map_http_error(nf, op="y") is nf


# --- Task 4: write methods + attachment error ---


def test_send_message_happy():
    sent = {}

    class _Svc(_FakeService):
        def send(self, userId, body): sent.update(body); return _Exec({"id": "m1"})
        def messages(self): return self
        def users(self): return self

    c, _ = _client_with(_Svc())
    out = c.send_message(to="a@b.com", subject="S", body="B")
    assert out["id"] == "m1" and "raw" in sent


def test_draft_with_thread_and_reply_header():
    created = {}

    class _Svc(_FakeService):
        def drafts(self): return self
        def create(self, userId, body): created.update(body); return _Exec({"id": "d1"})

    c, _ = _client_with(_Svc())
    out = c.send_message(to="a@b.com", subject="S", body="B", as_draft=True,
                         thread_id="T", reply_to_message_id="<mid@x>")
    assert out["id"] == "d1" and created["message"]["threadId"] == "T"
    import base64
    raw = base64.urlsafe_b64decode(created["message"]["raw"]).decode()
    assert "In-Reply-To: <mid@x>" in raw and "References: <mid@x>" in raw


def test_send_with_thread_id_uses_public_send_body():
    sent = {}

    class _Svc(_FakeService):
        def send(self, userId, body):
            sent.update(body)
            return _Exec({"id": "m2"})

        def messages(self):
            return self

        def users(self):
            return self

    c, _ = _client_with(_Svc())
    out = c.send_message(to="a@b.com", subject="S", body="B", thread_id="T2")
    assert out["id"] == "m2"
    assert sent["threadId"] == "T2"


def test_attachment_not_found_raises_usageerror():
    from h2t_ops.core.errors import UsageError
    c, _ = _client_with(_FakeService())
    with pytest.raises(UsageError):
        c.send_message(to="a@b.com", subject="S", body="B",
                       attachments=["/no/such/file.bin"])


def test_parse_message_collects_attachment_metadata():
    svc = _FakeService(get={
        "id": "1",
        "threadId": "t",
        "labelIds": [],
        "snippet": "",
        "payload": {
            "headers": [{"name": "Subject", "value": "S"}],
            "parts": [
                {
                    "mimeType": "application/pdf",
                    "filename": "report.pdf",
                    "body": {"attachmentId": "att1", "size": 123},
                }
            ],
        },
    })
    c, _ = _client_with(svc)
    out = c.get_message("1")
    assert out["attachments"] == [{
        "attachmentId": "att1",
        "filename": "report.pdf",
        "mimeType": "application/pdf",
        "size": 123,
    }]


def test_download_attachment_writes_bytes(tmp_path):
    class _AttSvc(_FakeService):
        def attachments(self):
            return self

        def get(self, **kwargs):
            return _Exec({"data": "aGVsbG8"})

    c, _ = _client_with(_AttSvc())
    target = tmp_path / "hello.bin"
    out = c.download_attachment("m1", "att1", target)
    assert out["saved_path"] == str(target)
    assert target.read_bytes() == b"hello"
    assert out["size"] == 5


# --- Task 7: google deps declared in pyproject.toml ---


def _thread_payload(thread_id, subject):
    return {
        "id": thread_id,
        "messages": [{
            "id": "m1", "threadId": thread_id, "labelIds": [], "snippet": "",
            "payload": {"headers": [
                {"name": "Subject", "value": subject},
                {"name": "From", "value": "a@x.com"},
                {"name": "To", "value": "b@x.com"},
                {"name": "Date", "value": "Mon"},
            ], "body": {"data": ""}},
        }],
    }


def test_trash_thread_validates_subject_match():
    calls = []

    class _Svc(_FakeService):
        def get(self, **k): return _Exec(_thread_payload("thr1", "Weekly Sync"))
        def trash(self, **k): calls.append(k); return _Exec({})

    c, _ = _client_with(_Svc())
    result = c.trash_thread("thr1", "Weekly Sync")
    assert result == {"thread_id": "thr1", "subject": "Weekly Sync", "trashed": True}
    assert calls[0]["id"] == "thr1"


def test_trash_thread_subject_case_insensitive():
    calls = []

    class _Svc(_FakeService):
        def get(self, **k): return _Exec(_thread_payload("thr1", "Weekly Sync"))
        def trash(self, **k): calls.append(k); return _Exec({})

    c, _ = _client_with(_Svc())
    c.trash_thread("thr1", "  weekly sync  ")
    assert calls


def test_trash_thread_subject_mismatch_raises():
    from h2t_ops.core.errors import UsageError

    class _Svc(_FakeService):
        def get(self, **k): return _Exec(_thread_payload("thr1", "Weekly Sync"))

    c, _ = _client_with(_Svc())
    with pytest.raises(UsageError, match="subject mismatch"):
        c.trash_thread("thr1", "Wrong Subject")


def test_untrash_thread_no_subject_check():
    calls = []

    class _Svc(_FakeService):
        def untrash(self, **k): calls.append(k); return _Exec({})

    c, _ = _client_with(_Svc())
    result = c.untrash_thread("thr1")
    assert result == {"thread_id": "thr1", "trashed": False}
    assert calls[0]["id"] == "thr1"


def test_delete_thread_validates_subject_and_deletes():
    calls = []

    class _Svc(_FakeService):
        def get(self, **k): return _Exec(_thread_payload("thr1", "Smoke Test"))
        def delete(self, **k): calls.append(k); return _Exec(None)

    c, _ = _client_with(_Svc())
    result = c.delete_thread("thr1", "Smoke Test")
    assert result == {"thread_id": "thr1", "subject": "Smoke Test", "deleted": True}
    assert calls[0]["id"] == "thr1"


def test_delete_thread_subject_mismatch_raises():
    from h2t_ops.core.errors import UsageError

    class _Svc(_FakeService):
        def get(self, **k): return _Exec(_thread_payload("thr1", "Smoke Test"))

    c, _ = _client_with(_Svc())
    with pytest.raises(UsageError, match="subject mismatch"):
        c.delete_thread("thr1", "Wrong")


def test_google_deps_declared_in_pyproject():
    import tomllib
    from pathlib import Path
    # test_client.py is <root>/tests/connectors/gmail/ → parents[3] = <root>
    # (parents[2] = tests/, which has no pyproject.toml).
    root = Path(__file__).resolve().parents[3]
    data = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    # Match on parsed dep NAMES, not substring-in-joined-string: a bare
    # `"google-auth" in joined` falsely passes when only the longer
    # `google-auth-oauthlib` is present (substring match).
    names = {d.split(">=")[0].split("==")[0].strip().lower()
             for d in data["project"]["dependencies"]}
    assert "google-api-python-client" in names
    assert "google-auth" in names
    assert "google-auth-oauthlib" in names


# --- Task 3 P0: reply / forward / label lifecycle ---


def _thread_with_message(thread_id, msg_id, subject, from_addr):
    return {
        "id": thread_id,
        "messages": [{
            "id": msg_id,
            "threadId": thread_id,
            "labelIds": [],
            "snippet": "",
            "from": from_addr,
            "to": "me@example.com",
            "subject": subject,
            "date": "Mon",
            "body": "Original body",
            "attachments": [],
        }],
    }


def _msg_payload(msg_id, thread_id, subject, from_addr, body_b64=""):
    return {
        "id": msg_id,
        "threadId": thread_id,
        "labelIds": [],
        "snippet": "",
        "payload": {
            "headers": [
                {"name": "Subject", "value": subject},
                {"name": "From", "value": from_addr},
                {"name": "To", "value": "me@example.com"},
                {"name": "Date", "value": "Mon"},
            ],
            "body": {"data": body_b64},
        },
    }


def test_reply_reads_thread_and_calls_send_with_thread_headers():
    """Reply defaults to draft; check subject prefix and thread_id forwarded."""
    import base64
    created = {}

    class _Svc(_FakeService):
        def get(self, **k):
            return _Exec(_thread_payload("thr1", "Hello"))

        def drafts(self):
            return self

        def create(self, userId, body):
            created.update(body)
            return _Exec({"id": "d1"})

    c, _ = _client_with(_Svc())
    result = c.reply_to_thread("thr1", body="My reply")
    assert result["id"] == "d1"
    # subject should be prefixed with "Re: "
    raw = base64.urlsafe_b64decode(created["message"]["raw"]).decode()
    assert "Re: Hello" in raw
    assert created["message"]["threadId"] == "thr1"


def test_reply_prefixes_subject_with_re():
    import base64
    created = {}

    class _Svc(_FakeService):
        def get(self, **k):
            return _Exec(_thread_payload("t1", "Standup"))

        def drafts(self):
            return self

        def create(self, userId, body):
            created.update(body)
            return _Exec({"id": "d2"})

    c, _ = _client_with(_Svc())
    c.reply_to_thread("t1", body="OK")
    raw = base64.urlsafe_b64decode(created["message"]["raw"]).decode()
    assert raw.count("Re: ") == 1  # no double Re: Re:


def test_reply_does_not_double_prefix_re():
    import base64
    created = {}

    class _Svc(_FakeService):
        def get(self, **k):
            return _Exec(_thread_payload("t1", "Re: Standup"))

        def drafts(self):
            return self

        def create(self, userId, body):
            created.update(body)
            return _Exec({"id": "d3"})

    c, _ = _client_with(_Svc())
    c.reply_to_thread("t1", body="OK")
    raw = base64.urlsafe_b64decode(created["message"]["raw"]).decode()
    # Subject should be "Re: Standup", not "Re: Re: Standup"
    assert "Re: Re:" not in raw
    assert "Re: Standup" in raw


def test_reply_defaults_to_draft():
    created = {}

    class _Svc(_FakeService):
        def get(self, **k):
            return _Exec(_thread_payload("t1", "Ping"))

        def drafts(self):
            return self

        def create(self, userId, body):
            created.update(body)
            return _Exec({"id": "d1"})

    c, _ = _client_with(_Svc())
    result = c.reply_to_thread("t1", body="Pong")
    # Draft created, not sent
    assert result["id"] == "d1"
    assert "message" in created


def test_reply_send_requires_confirm_send():
    from h2t_ops.core.errors import UsageError

    class _Svc(_FakeService):
        def get(self, **k):
            return _Exec(_thread_payload("t1", "Ping"))

    c, _ = _client_with(_Svc())
    with pytest.raises(UsageError, match="--confirm-send"):
        c.reply_to_thread("t1", body="Pong", send=True, confirm_send=False)


def test_forward_reads_message_and_sends_new_message():
    import base64
    created = {}

    # Build a fake payload for get_message (returns a parsed dict via _parse_message)
    _body_b64 = base64.urlsafe_b64encode(b"Original body").decode()

    class _Svc(_FakeService):
        def get(self, **k):
            return _Exec(_msg_payload("m1", "t1", "Project Update", "sender@x.com", _body_b64))

        def drafts(self):
            return self

        def create(self, userId, body):
            created.update(body)
            return _Exec({"id": "d2"})

    c, _ = _client_with(_Svc())
    result = c.forward_message("m1", to="colleague@example.com")
    assert result["id"] == "d2"
    raw = base64.urlsafe_b64decode(created["message"]["raw"]).decode()
    assert "Fwd: Project Update" in raw
    assert "colleague@example.com" in raw


def test_forward_defaults_to_draft():
    created = {}

    class _Svc(_FakeService):
        def get(self, **k):
            return _Exec(_msg_payload("m1", "t1", "Topic", "a@x.com"))

        def drafts(self):
            return self

        def create(self, userId, body):
            created.update(body)
            return _Exec({"id": "d3"})

    c, _ = _client_with(_Svc())
    result = c.forward_message("m1", to="b@x.com")
    assert result["id"] == "d3"
    assert "message" in created


def test_forward_does_not_pass_thread_id():
    """Forward creates a new thread — thread_id must NOT be forwarded."""
    import base64  # noqa: F401
    created = {}

    class _Svc(_FakeService):
        def get(self, **k):
            return _Exec(_msg_payload("m1", "t1", "Topic", "a@x.com"))

        def drafts(self):
            return self

        def create(self, userId, body):
            created.update(body)
            return _Exec({"id": "d4"})

    c, _ = _client_with(_Svc())
    c.forward_message("m1", to="b@x.com")
    # The draft message body should not contain threadId
    assert "threadId" not in created.get("message", {})


def test_forward_send_requires_confirm_send():
    from h2t_ops.core.errors import UsageError

    class _Svc(_FakeService):
        def get(self, **k):
            return _Exec(_msg_payload("m1", "t1", "Topic", "a@x.com"))

    c, _ = _client_with(_Svc())
    with pytest.raises(UsageError, match="--confirm-send"):
        c.forward_message("m1", to="b@x.com", send=True, confirm_send=False)


def test_label_create_calls_gmail_labels_create():
    created_body = {}

    class _Svc(_FakeService):
        def create(self, userId, body):
            created_body.update(body)
            return _Exec({"id": "Label_new", "name": "My Label"})

        def labels(self):
            return self

        def users(self):
            return self

    c, _ = _client_with(_Svc())
    result = c.create_label("My Label")
    assert result["id"] == "Label_new"
    assert created_body["name"] == "My Label"
    assert created_body["labelListVisibility"] == "labelShow"


def test_label_delete_requires_name_match_before_delete():
    deleted = []

    class _Svc(_FakeService):
        def list(self, **k):
            return _Exec({"labels": [{"id": "Label_1", "name": "Project X"}]})

        def delete(self, **k):
            deleted.append(k)
            return _Exec(None)

        def labels(self):
            return self

        def users(self):
            return self

    c, _ = _client_with(_Svc())
    result = c.delete_label("Label_1", confirm_name="Project X")
    assert result == {"label_id": "Label_1", "name": "Project X", "deleted": True}
    assert deleted[0]["id"] == "Label_1"


def test_label_delete_mismatch_raises_usageerror():
    from h2t_ops.core.errors import UsageError

    class _Svc(_FakeService):
        def list(self, **k):
            return _Exec({"labels": [{"id": "Label_1", "name": "Project X"}]})

        def labels(self):
            return self

        def users(self):
            return self

    c, _ = _client_with(_Svc())
    with pytest.raises(UsageError, match="label mismatch"):
        c.delete_label("Label_1", confirm_name="Wrong Name")
