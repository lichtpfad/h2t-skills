"""Telegram login paths learned from the first external rollout (2026-10-14).

A code requested by `request-code` went to `SentCodeTypeApp`, was never found, and
`auth.resendCode` answered SEND_CODE_UNAVAILABLE; the user got in only by QR. The CLI had
reported `code_requested: true` and nothing else.
"""
from __future__ import annotations

import asyncio
import json
import stat
import sys
from types import SimpleNamespace

import pytest
from telethon.tl.types import auth as tl_auth

from h2t_ops.core.errors import AuthError


def _adapter(tmp_path, monkeypatch, fake_cls):
    from h2t_ops.connectors.telegram import client as tmod

    (tmp_path / "config.json").write_text(json.dumps({"api_id": 1, "api_hash": "h"}), encoding="utf-8")
    monkeypatch.setattr(tmod.TelegramClientAdapter, "_telegram_client_class", lambda self: fake_cls)
    return tmod.TelegramClientAdapter(config_dir=tmp_path)


def _sent(code_type, next_type=None, timeout=None):
    return SimpleNamespace(phone_code_hash="hash1", type=code_type, next_type=next_type, timeout=timeout)


class _Base:
    def __init__(self, *a):
        self.loop = asyncio.new_event_loop()

    def connect(self):
        pass

    def disconnect(self):
        pass


# --- request-code says where the code went -------------------------------------------

@pytest.mark.parametrize("code_type, channel", [
    (tl_auth.SentCodeTypeApp(length=5), "app"),
    (tl_auth.SentCodeTypeSms(length=5), "sms"),
    (tl_auth.SentCodeTypeCall(length=5), "call"),
    (tl_auth.SentCodeTypeEmailCode(email_pattern="l***@g***.com", length=6), "email"),
])
def test_request_code_reports_the_delivery_channel(tmp_path, monkeypatch, code_type, channel):
    class Fake(_Base):
        def send_code_request(self, phone):
            return _sent(code_type, tl_auth.CodeTypeSms(), 60)

    result = _adapter(tmp_path, monkeypatch, Fake).request_code("+100")

    assert result["code_requested"] is True
    assert result["channel"] == channel
    assert result["where"]
    assert result["next_channel"] == "sms"
    assert result["resend_after_s"] == 60
    if channel == "email":
        assert result["email_pattern"] == "l***@g***.com"
    assert json.loads((tmp_path / "auth_state.json").read_text())["phone_code_hash"] == "hash1"


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX mode bits")
def test_auth_state_without_config_dir_is_a_secret_in_local(monkeypatch):
    """4.0 layout: the pending code hash is secrets/local/telegram.auth-state.json, 0600,
    and resend reads it back from there (#548 Task 9)."""
    from h2t_ops.connectors.telegram import client as tmod
    from h2t_ops.core import paths

    monkeypatch.setenv("TELEGRAM_API_ID", "1")
    monkeypatch.setenv("TELEGRAM_API_HASH", "fake-hash")

    class Fake(_Base):
        def send_code_request(self, phone):
            return _sent(tl_auth.SentCodeTypeSms(length=5))

        def __call__(self, request):
            assert request.phone_code_hash == "hash1"
            return SimpleNamespace(phone_code_hash="hash2", type=tl_auth.SentCodeTypeSms(length=5),
                                   next_type=None, timeout=None)

    monkeypatch.setattr(tmod.TelegramClientAdapter, "_telegram_client_class", lambda self: Fake)
    adapter = tmod.TelegramClientAdapter()
    adapter.request_code("+100")

    state = paths.secrets_local() / "telegram.auth-state.json"
    assert json.loads(state.read_text())["phone_code_hash"] == "hash1"
    assert stat.S_IMODE(state.stat().st_mode) == 0o600
    adapter.resend_code()
    assert json.loads(state.read_text())["phone_code_hash"] == "hash2"
    assert not paths.legacy("telegram").exists()


def test_request_code_that_sent_nothing_is_an_error_pointing_at_qr(tmp_path, monkeypatch):
    class Fake(_Base):
        def send_code_request(self, phone):
            return _sent(tl_auth.SentCodeTypeSetUpEmailRequired())

    with pytest.raises(AuthError) as ei:
        _adapter(tmp_path, monkeypatch, Fake).request_code("+100")
    assert "auth qr" in ei.value.hint


# --- resend ---------------------------------------------------------------------------

def test_resend_uses_the_saved_hash_and_stores_the_new_one(tmp_path, monkeypatch):
    seen = {}

    class Fake(_Base):
        def __call__(self, request):
            seen["phone"], seen["hash"] = request.phone_number, request.phone_code_hash
            return SimpleNamespace(phone_code_hash="hash2", type=tl_auth.SentCodeTypeSms(length=5),
                                   next_type=None, timeout=None)

    adapter = _adapter(tmp_path, monkeypatch, Fake)
    adapter.auth_state_file.write_text(json.dumps({"phone": "+100", "phone_code_hash": "hash1"}))

    result = adapter.resend_code()

    assert seen == {"phone": "+100", "hash": "hash1"}
    assert result["channel"] == "sms"
    assert result["next_channel"] is None
    assert json.loads(adapter.auth_state_file.read_text())["phone_code_hash"] == "hash2"


def test_resend_with_no_channel_left_points_at_qr(tmp_path, monkeypatch):
    from telethon.errors import SendCodeUnavailableError

    class Fake(_Base):
        def __call__(self, request):
            raise SendCodeUnavailableError(request=request)

    adapter = _adapter(tmp_path, monkeypatch, Fake)
    adapter.auth_state_file.write_text(json.dumps({"phone": "+100", "phone_code_hash": "hash1"}))
    with pytest.raises(AuthError) as ei:
        adapter.resend_code()
    assert "auth qr" in ei.value.hint


def test_resend_without_a_prior_request_is_a_usage_error(tmp_path, monkeypatch):
    from h2t_ops.core.errors import UsageError

    with pytest.raises(UsageError):
        _adapter(tmp_path, monkeypatch, _Base).resend_code()


# --- QR login -------------------------------------------------------------------------

class _QR:
    def __init__(self, outcomes):
        self.url = "tg://login?token=t0"
        self.outcomes = list(outcomes)
        self.recreated = 0

    async def wait(self, timeout=None):
        outcome = self.outcomes.pop(0)
        if outcome is not None:
            raise outcome

    async def recreate(self):
        self.recreated += 1
        self.url = f"tg://login?token=t{self.recreated}"


def _qr_client(qr, *, authorized_after=True, already=False):
    class Fake(_Base):
        signed = None

        def is_user_authorized(self):
            return already or (Fake.signed is not None or not qr.outcomes) and authorized_after

        def qr_login(self):
            return qr

        def sign_in(self, password=None):
            Fake.signed = password

        def get_me(self):
            return SimpleNamespace(id=7, username=None, first_name="L", last_name="")

    return Fake


def test_qr_login_shows_a_fresh_code_after_each_timeout(tmp_path, monkeypatch):
    qr = _QR([TimeoutError(), TimeoutError(), None])
    shown = []
    result = _adapter(tmp_path, monkeypatch, _qr_client(qr)).qr_login(render=shown.append)

    assert shown == ["tg://login?token=t0", "tg://login?token=t1", "tg://login?token=t2"]
    assert result["authorized"] is True


def test_qr_login_asks_for_the_2fa_password_through_the_prompt(tmp_path, monkeypatch):
    from telethon.errors import SessionPasswordNeededError

    qr = _QR([SessionPasswordNeededError(request=None)])
    fake = _qr_client(qr)
    result = _adapter(tmp_path, monkeypatch, fake).qr_login(render=lambda url: None,
                                                            password_prompt=lambda: "pw")
    assert fake.signed == "pw"
    assert result["authorized"] is True


def test_qr_login_that_is_never_scanned_fails_with_a_retry_hint(tmp_path, monkeypatch):
    qr = _QR([TimeoutError()] * 5)
    with pytest.raises(AuthError) as ei:
        _adapter(tmp_path, monkeypatch, _qr_client(qr, authorized_after=False)).qr_login(
            render=lambda url: None, attempts=5)
    assert "auth qr" in ei.value.hint


def test_qr_login_on_an_authorized_session_does_nothing(tmp_path, monkeypatch):
    qr = _QR([])
    shown = []
    result = _adapter(tmp_path, monkeypatch, _qr_client(qr, already=True)).qr_login(render=shown.append)
    assert result["authorized"] is True and shown == []


# --- 2FA password never on the command line -------------------------------------------

def test_complete_prompts_for_2fa_instead_of_failing(tmp_path, monkeypatch):
    from telethon.errors import SessionPasswordNeededError

    calls = []

    class Fake(_Base):
        def sign_in(self, phone=None, code=None, phone_code_hash=None, password=None):
            calls.append(password)
            if password is None:
                raise SessionPasswordNeededError(request=None)

        def get_me(self):
            return SimpleNamespace(id=7, username=None, first_name="L", last_name="")

    adapter = _adapter(tmp_path, monkeypatch, Fake)
    adapter.auth_state_file.write_text(json.dumps({"phone": "+100", "phone_code_hash": "hash1"}))
    result = adapter.complete_auth("+100", code="12345", password_prompt=lambda: "pw")

    assert calls == [None, "pw"]
    assert result["authorized"] is True


def test_missing_config_hint_offers_qr_first(tmp_path):
    from h2t_ops.connectors.telegram.client import TelegramClientAdapter
    from h2t_ops.core.errors import ConfigError

    with pytest.raises(ConfigError) as ei:
        TelegramClientAdapter(config_dir=tmp_path)._load_config()
    assert ei.value.hint.index("auth qr") < ei.value.hint.index("request-code")


# --- CLI ------------------------------------------------------------------------------

def _parse(argv):
    import argparse

    from h2t_ops.connectors.telegram.commands import register

    p = argparse.ArgumentParser()
    register(p.add_subparsers(dest="connector"))
    return p.parse_args(argv)


def test_cli_exposes_qr_and_resend():
    assert _parse(["telegram", "auth", "qr"]).telegram_cmd == "auth-qr"
    assert _parse(["telegram", "auth", "resend"]).telegram_cmd == "auth-resend"


def test_cli_password_flag_without_a_value_means_ask():
    ns = _parse(["telegram", "auth", "complete", "--phone", "+100", "--password"])
    assert ns.password == ""
