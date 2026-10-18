"""Layout 1, phase secrets and its verification (#548 §8 п. 2, п. 6; plan R6, R19, R25, R37,
R38, R41).

HOME is a temporary directory in every test (root conftest). Every value is a fake-<name>;
nothing here prints or asserts on a value outside the sandbox.
"""
from __future__ import annotations

import hashlib
import itertools
import json
import os
import sys
from pathlib import Path

import pytest

from h2t_ops.core import paths, secrets, store
from h2t_ops.setup.layout import engine, secrets_phase, verify
from h2t_ops.setup.layout import journal as journal_mod
from h2t_ops.setup.layout.journal import Journal
from h2t_ops.setup.sync import Report
from tests.governance import audit


@pytest.fixture(autouse=True)
def _machine(monkeypatch):
    monkeypatch.setenv("H2T_MACHINE_NAME", "m")
    monkeypatch.delenv("DOR_MACHINE_NAME", raising=False)
    for k in paths.OLD_ENV:
        monkeypatch.delenv(k, raising=False)


def _noop(ctx):
    return None


def _migrate() -> Report:
    table = {p: _noop for p in engine.PHASES}
    table.update(engine._phase_funcs())
    report = Report()
    engine.migrate(report, funcs=table)
    return report


def _ctx() -> engine.PhaseContext:
    return engine.PhaseContext(journal=Journal(journal_mod.new_run_id()), machine="m",
                               machine_explicit=False, report=Report())


def _write(p: Path, data: str | bytes) -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, bytes):
        p.write_bytes(data)
    else:
        p.write_text(data, encoding="utf-8")
    return p


def _old_dir() -> Path:
    return paths.legacy("secrets.h2t")


def _env(p: Path) -> dict[str, str]:
    return secrets.parse_env(p.read_text(encoding="utf-8"))


def _sha(v: str) -> str:
    return hashlib.sha256(v.encode()).hexdigest()


def _shared() -> Path:
    return paths.secrets_shared()


def _local() -> Path:
    return paths.secrets_local()


# --- precedence -----------------------------------------------------------------------------

_LADDER = ["existing", "secretsfile", "h2t-config", "h2t-config-jina", "h2t-config-meetgeek",
           "dor-secrets", "dor"]


def _plant_ladder(names, monkeypatch, tmp_path) -> None:
    where = {"existing": lambda: _shared() / "meetgeek.env",
             "secretsfile": lambda: tmp_path / "override.env",
             "h2t-config": lambda: _old_dir() / "secrets.env",
             "h2t-config-jina": lambda: _old_dir() / "jina.env",
             "h2t-config-meetgeek": lambda: _old_dir() / "meetgeek.env",
             "dor-secrets": lambda: paths.legacy("secrets.dor"),
             "dor": lambda: paths.legacy("secrets.dor_old")}
    for n in names:
        _write(where[n](), f"MEETGEEK_API_KEY=fake-meetgeek-{n}\n")
    if "secretsfile" in names:
        monkeypatch.setenv("H2T_SECRETS_FILE", str(tmp_path / "override.env"))


@pytest.mark.parametrize("top", range(len(_LADDER)))
def test_full_precedence_order(top, monkeypatch, tmp_path):
    present = _LADDER[top:]
    _plant_ladder(present, monkeypatch, tmp_path)
    report = _migrate()
    assert report.failed == []
    winner, losers = present[0], present[1:]
    assert _env(_shared() / "meetgeek.env") == {"MEETGEEK_API_KEY": f"fake-meetgeek-{winner}"}
    copies = sorted(p.name for p in _shared().iterdir() if ".from-" in p.name)
    assert copies == sorted(f"meetgeek.env.from-{n}" for n in losers)
    for n in losers:
        assert _env(_shared() / f"meetgeek.env.from-{n}") == {"MEETGEEK_API_KEY": f"fake-meetgeek-{n}"}
    if top == 0:
        assert len(losers) == 6


def test_evals_prefers_dor_secrets_env():
    _write(_old_dir() / "secrets.env", "H2T_EVALS_TOKEN=fake-evals-h2t\n")
    _write(paths.legacy("secrets.dor"), "H2T_EVALS_TOKEN=fake-evals-dorsecrets\n")
    _write(paths.legacy("secrets.dor_old"), "H2T_EVALS_TOKEN=fake-evals-dor\n")
    assert _migrate().failed == []
    assert _env(_shared() / "h2t-evals.env") == {"H2T_EVALS_TOKEN": "fake-evals-dor"}
    assert sorted(p.name for p in _shared().iterdir() if ".from-" in p.name) == [
        "h2t-evals.env.from-dor-secrets", "h2t-evals.env.from-h2t-config"]


def test_a_second_clash_keeps_all_three_and_verifies():
    """A synced .from-dor with another value already there: put names the third
    <stem>-2<suffix> (store.unique_name), and the reader must see that copy too."""
    _write(_shared() / "meetgeek.env", "MEETGEEK_API_KEY=fake-meetgeek-new\n")
    _write(_shared() / "meetgeek.env.from-dor", "MEETGEEK_API_KEY=fake-meetgeek-synced\n")
    _write(paths.legacy("secrets.dor_old"), "MEETGEEK_API_KEY=fake-meetgeek-dor\n")
    report = _migrate()
    assert report.failed == []
    third = list(itertools.islice(store.unique_name(_shared() / "meetgeek.env.from-dor"), 2))[1]
    assert third.name == "meetgeek.env-2.from-dor"
    assert {p.name: _env(p)["MEETGEEK_API_KEY"] for p in _shared().iterdir()} == {
        "meetgeek.env": "fake-meetgeek-new", "meetgeek.env.from-dor": "fake-meetgeek-synced",
        "meetgeek.env-2.from-dor": "fake-meetgeek-dor"}
    assert set(secrets.shared_env_values()) == {"meetgeek.env", "meetgeek.env.from-dor",
                                                "meetgeek.env-2.from-dor"}


def test_existing_new_file_wins_on_rerun():
    _write(paths.legacy("secrets.dor_old"), "MEETGEEK_API_KEY=fake-meetgeek-old\n")
    assert _migrate().failed == []
    # the user changes the key in the new file; no old place holds the new value
    _write(_shared() / "meetgeek.env", "MEETGEEK_API_KEY=fake-meetgeek-user\n")
    paths.layout_file().unlink()                 # a second run of layout 1
    report = _migrate()
    assert report.failed == []
    assert _env(_shared() / "meetgeek.env") == {"MEETGEEK_API_KEY": "fake-meetgeek-user"}
    assert _env(_shared() / "meetgeek.env.from-dor") == {"MEETGEEK_API_KEY": "fake-meetgeek-old"}


def test_secrets_file_override_is_one_more_source(monkeypatch, tmp_path):
    _write(tmp_path / "override.env", "EXA_API_KEY=fake-exa\n")
    _write(paths.legacy("secrets.dor_old"), "MEETGEEK_API_KEY=fake-meetgeek\n")
    monkeypatch.setenv("H2T_SECRETS_FILE", str(tmp_path / "override.env"))
    assert [n for n, _ in secrets_phase.ladder()] == ["secretsfile", "dor"]
    assert _migrate().failed == []
    assert _env(_shared() / "exa.env") == {"EXA_API_KEY": "fake-exa"}
    assert _env(_shared() / "meetgeek.env") == {"MEETGEEK_API_KEY": "fake-meetgeek"}


def test_secrets_file_pointing_at_a_ladder_file_counts_once(monkeypatch):
    _write(paths.legacy("secrets.dor_old"), "MEETGEEK_API_KEY=fake-meetgeek\n")
    monkeypatch.setenv("H2T_SECRETS_FILE", str(paths.legacy("secrets.dor_old")))
    assert [n for n, _ in secrets_phase.ladder()] == ["secretsfile"]
    assert _migrate().failed == []
    assert sorted(p.name for p in _shared().iterdir()) == ["meetgeek.env"]


def test_unknown_keys_go_to_other_env():
    _write(_old_dir() / "secrets.env", "SOMETHING_ELSE=fake-other\nEXA_API_KEY=fake-exa\n")
    assert _migrate().failed == []
    assert _env(_shared() / "other.env") == {"SOMETHING_ELSE": "fake-other"}
    assert _env(_shared() / "exa.env") == {"EXA_API_KEY": "fake-exa"}


def test_foreign_env_is_copied_whole_and_feeds_provider_keys():
    src = _write(_old_dir() / "getcourse.env",
                 "# getcourse\nGETCOURSE_KEY=fake-getcourse\nEXA_API_KEY=fake-exa\n")
    assert _migrate().failed == []
    assert (_shared() / "getcourse.env").read_bytes() == src.read_bytes()
    assert _env(_shared() / "exa.env") == {"EXA_API_KEY": "fake-exa"}
    assert not (_shared() / "other.env").exists()      # its own keys stay its own (R6)
    rows = [r for r in Journal.latest().entries() if r["op"] == "created"
            and r["path"] == str(_shared() / "getcourse.env")]
    assert rows and rows[0]["source_path"] == str(src)


def test_telegram_and_notion_are_translated():
    _write(paths.legacy("notion.token"), "fake-notion\n")
    _write(paths.legacy("telegram") / "config.json", json.dumps({"api_id": 12345, "api_hash": "fake-hash"}))
    assert _migrate().failed == []
    assert _env(_shared() / "notion.env") == {"NOTION_API_TOKEN": "fake-notion"}
    assert _env(_shared() / "telegram.env") == {"TELEGRAM_API_ID": "12345",
                                                "TELEGRAM_API_HASH": "fake-hash"}


def test_notion_token_is_the_most_junior():
    _write(paths.legacy("secrets.dor_old"), "NOTION_API_TOKEN=fake-notion-env\n")
    _write(paths.legacy("notion.token"), "fake-notion-file\n")
    winners, losers, _ = secrets_phase.plan_env()
    assert winners["notion.env"] == {"NOTION_API_TOKEN": "fake-notion-env"}
    assert losers["notion.env"] == {"notion-token": {"NOTION_API_TOKEN": "fake-notion-file"}}


def test_telegram_config_feeds_telegram_env():
    _write(paths.legacy("telegram") / "config.json", json.dumps({"api_id": 7, "api_hash": "fake-hash"}))
    _write(paths.legacy("secrets.dor_old"), "TELEGRAM_API_ID=8\n")
    winners, losers, _ = secrets_phase.plan_env()
    assert winners["telegram.env"] == {"TELEGRAM_API_ID": "8", "TELEGRAM_API_HASH": "fake-hash"}
    assert losers["telegram.env"] == {"telegram-config": {"TELEGRAM_API_ID": "7"}}


def test_an_empty_value_is_absent_for_its_key():
    """The skeleton's KEY= neither wins over an old value nor counts as one (Task 10)."""
    _write(_shared() / "meetgeek.env", "# kept\nMEETGEEK_API_KEY=\nMEETGEEK_OTHER=fake-kept\n")
    _write(_old_dir() / "secrets.env", "MEETGEEK_API_KEY=fake-meetgeek\n")
    _write(paths.legacy("secrets.dor_old"), "MEETGEEK_API_KEY=\n")
    assert _migrate().failed == []
    text = (_shared() / "meetgeek.env").read_text(encoding="utf-8")
    assert text == "# kept\nMEETGEEK_API_KEY=fake-meetgeek\nMEETGEEK_OTHER=fake-kept\n"
    assert not [p for p in _shared().iterdir() if ".from-" in p.name]


def test_undecodable_source_stops_with_its_name():
    bad = _write(paths.legacy("secrets.dor_old"), b"MEETGEEK_API_KEY=\xff\xfe\n")
    report = _migrate()
    assert [s for s, _ in report.failed] == ["layout 1: secrets"]
    assert str(bad) in report.failed[0][1]
    assert not _shared().exists()


# --- verification ---------------------------------------------------------------------------

def test_verify_catches_a_lost_value():
    _write(_old_dir() / "secrets.env", "EXA_API_KEY=fake-exa\n")
    ctx = _ctx()
    secrets_phase.phase_secrets(ctx)
    assert verify.verify_secrets(ctx.journal) == []
    (_shared() / "exa.env").write_text("", encoding="utf-8")
    problems = verify.verify_secrets(ctx.journal)
    assert f"lost EXA_API_KEY (sha256 {_sha('fake-exa')[:12]})" in problems


def test_verify_catches_a_junior_value_written():
    _write(_old_dir() / "secrets.env", "MEETGEEK_API_KEY=fake-meetgeek-senior\n")
    _write(paths.legacy("secrets.dor_old"), "MEETGEEK_API_KEY=fake-meetgeek-junior\n")
    ctx = _ctx()
    secrets_phase.phase_secrets(ctx)
    assert verify.verify_secrets(ctx.journal) == []
    # swap: both values are still there, so lost/appeared stay silent
    (_shared() / "meetgeek.env").write_text("MEETGEEK_API_KEY=fake-meetgeek-junior\n", encoding="utf-8")
    (_shared() / "meetgeek.env.from-dor").write_text("MEETGEEK_API_KEY=fake-meetgeek-senior\n",
                                                     encoding="utf-8")
    assert verify.verify_secrets(ctx.journal) == [
        "meetgeek.env: MEETGEEK_API_KEY is not the senior value"]


def test_resume_takes_the_baseline_from_the_journal(monkeypatch):
    _write(_old_dir() / "secrets.env", "EXA_API_KEY=fake-exa\nMEETGEEK_API_KEY=fake-meetgeek\n")
    _write(paths.legacy("secrets.dor_old"), "MEETGEEK_API_KEY=fake-meetgeek-dor\n")
    real_put, calls = engine.put, []

    def killed(*a, **kw):
        calls.append(1)
        if len(calls) == 2:
            raise KeyboardInterrupt
        return real_put(*a, **kw)

    monkeypatch.setattr(engine, "put", killed)
    with pytest.raises(KeyboardInterrupt):
        _migrate()
    monkeypatch.setattr(engine, "put", real_put)
    assert _migrate().failed == []
    rows = Journal.latest().entries()
    base = [(r["key"], r["sha256"]) for r in rows if r["op"] == "baseline"]
    assert sorted(base) == sorted({("EXA_API_KEY", _sha("fake-exa")),
                                   ("MEETGEEK_API_KEY", _sha("fake-meetgeek")),
                                   ("MEETGEEK_API_KEY", _sha("fake-meetgeek-dor"))})
    first_write = next(i for i, r in enumerate(rows) if r["op"] in ("intent", "source"))
    assert max(i for i, r in enumerate(rows) if r["op"] in ("baseline", "winner")) < first_write


# --- Google ---------------------------------------------------------------------------------

def _google_token() -> dict:
    return {"normal": {"token": "fake-access", "refresh_token": "fake-refresh",
                       "client_id": "fake-client-id", "client_secret": "fake-client-secret",
                       "token_uri": "https://oauth2.googleapis.com/token",
                       "scope": "https://www.googleapis.com/auth/calendar https://www.googleapis.com/auth/drive",
                       "expiry_date": 1700000000000}}


def _plant_google() -> tuple[Path, Path]:
    store_dir = paths.legacy("google.store")
    client = _write(store_dir / "credentials.json", json.dumps({"installed": {"client_id": "fake-cid"}}))
    token = _write(store_dir / "tokens.json", json.dumps(_google_token()))
    return client, token


def test_google_token_goes_to_local_per_machine():
    client, token = _plant_google()
    assert _migrate().failed == []
    assert (_local() / "google.token.json").is_file()
    assert (_shared() / "google.client.json").read_bytes() == client.read_bytes()
    assert not [p for p in _shared().iterdir() if "token" in p.name]
    assert token.read_bytes() == json.dumps(_google_token()).encode()     # the old file untouched
    if sys.platform != "win32":
        assert (_local() / "google.token.json").stat().st_mode & 0o777 == 0o600


def test_google_token_keeps_durable_fields_only():
    _plant_google()
    ctx = _ctx()
    secrets_phase.phase_secrets(ctx)
    target = _local() / "google.token.json"
    got = json.loads(target.read_text(encoding="utf-8"))
    assert set(got) == {"refresh_token", "client_id", "client_secret", "token_uri", "scopes"}
    assert got["scopes"] == ["https://www.googleapis.com/auth/calendar",
                             "https://www.googleapis.com/auth/drive"]
    assert verify.verify_transformed(ctx.journal) == []
    rows = [r for r in ctx.journal.entries() if r["op"] == "created" and r["path"] == str(target)]
    assert rows[0]["rule"] == "google-durable"
    assert not [r for r in ctx.journal.entries() if r["op"] == "created" and r["place"] == "legacy"]

    target.write_text(json.dumps({**got, "token": "fake-access"}), encoding="utf-8")
    assert verify.verify_transformed(ctx.journal) == [f"{target}: holds a short-lived field"]
    target.write_text(json.dumps({**got, "refresh_token": "fake-other"}), encoding="utf-8")
    assert verify.verify_transformed(ctx.journal) == [
        f"{target}: a durable field differs from {paths.legacy('google.store') / 'tokens.json'}"]


def test_google_token_without_refresh_token_never_wins():
    """A senior token with no refresh_token is skipped: the usable junior one is the file."""
    _write(paths.legacy("google.store") / "tokens.json", json.dumps({"normal": {"token": "fake-access"}}))
    gmail = {k: v for k, v in _google_token()["normal"].items()}
    _write(paths.legacy("google.gmail") / "token.json", json.dumps(gmail))
    report = _migrate()
    assert report.failed == []
    got = json.loads((_local() / "google.token.json").read_text(encoding="utf-8"))
    assert got["refresh_token"] == "fake-refresh"
    assert sorted(p.name for p in _local().iterdir()) == ["google.token.json"]


def test_no_usable_google_token_writes_nothing_and_says_so():
    src = _write(paths.legacy("google.store") / "tokens.json", json.dumps({"normal": {"token": "fake-access"}}))
    report = _migrate()
    assert report.failed == []
    assert not (_local() / "google.token.json").exists()
    assert any(str(src) in n and "refresh_token" in n for n in report.notes), report.notes


@pytest.mark.parametrize("raw, want", [(b"{not json", "not valid JSON"), (b"\xff\xfe{}", "not UTF-8")])
def test_unreadable_google_token_has_its_own_hint(raw, want):
    src = _write(paths.legacy("google.store") / "tokens.json", raw)
    report = _migrate()
    assert [s for s, _ in report.failed] == ["layout 1: secrets"]
    text = report.failed[0][1]
    assert str(src) in text and want in text
    if want == "not valid JSON":
        assert "UTF-8" not in text and "line 1" in text
    else:
        assert "UTF-8" in text


def test_google_client_byte_copy_verified_by_hash():
    _plant_google()
    _write(paths.legacy("google.gmail") / "credentials.json", json.dumps({"installed": {"client_id": "fake-gm"}}))
    ctx = _ctx()
    secrets_phase.phase_secrets(ctx)
    assert (_shared() / "google.client.json.from-gmail").is_file()
    assert verify.verify_copies(ctx.journal) == []
    target = _shared() / "google.client.json"
    with open(target, "ab") as fh:
        fh.write(b" ")
    assert verify.verify_copies(ctx.journal) == [f"copy {target} does not match its journal hash"]


# --- Telegram -------------------------------------------------------------------------------

_SESSION = b"SQLite format 3\x00fake-session"


def _session_src() -> Path:
    return paths.legacy("telegram") / "session.session"


def test_telegram_session_is_a_byte_copy_verified_by_hash():
    _write(_session_src(), _SESSION)
    _write(paths.legacy("telegram") / "auth_state.json", json.dumps({"phone": "fake-phone"}))
    ctx = _ctx()
    secrets_phase.phase_secrets(ctx)
    copy = _local() / "telegram.session"
    assert copy.read_bytes() == _SESSION
    assert (_local() / "telegram.auth-state.json").read_bytes() == \
        (paths.legacy("telegram") / "auth_state.json").read_bytes()
    row = next(r for r in ctx.journal.entries() if r["op"] == "created" and r["path"] == str(copy))
    assert row["source_path"] == str(_session_src())
    if sys.platform != "win32":
        assert copy.stat().st_mode & 0o777 == 0o600
    assert verify.verify_copies(ctx.journal) == []
    with open(copy, "ab") as fh:
        fh.write(b"x")
    assert verify.verify_copies(ctx.journal) == [f"copy {copy} does not match its journal hash"]


@pytest.mark.parametrize("same", [False, True])
def test_existing_local_session_keeps_both(same):
    _write(_session_src(), _SESSION)
    mine = _SESSION if same else b"SQLite format 3\x00fake-session-changed-by-telethon"
    _write(_local() / "telegram.session", mine)
    assert _migrate().failed == []
    assert (_local() / "telegram.session").read_bytes() == mine
    extra = _local() / "telegram.session.from-telegram"
    if same:
        assert sorted(p.name for p in _local().iterdir()) == ["telegram.session"]
    else:
        assert extra.read_bytes() == _SESSION


def test_telegram_session_with_a_sidecar_stops():
    _write(_session_src(), _SESSION)
    _write(paths.legacy("telegram") / "session.session-journal", b"")
    _write(_old_dir() / "secrets.env", "EXA_API_KEY=fake-exa\n")
    report = _migrate()
    assert [s for s, _ in report.failed] == ["layout 1: secrets"]
    assert "close Telegram" in report.failed[0][1]
    assert not (_local() / "telegram.session").exists()
    assert not _shared().exists()                       # nothing written
    rows = Journal.latest().entries()
    assert not [r for r in rows if r["op"] in ("intent", "created", "source")]


def test_telegram_session_changed_during_copy_stops(monkeypatch):
    _write(_session_src(), _SESSION)
    real = secrets.read_secret_bytes

    def touching(path, **kw):
        data = real(path, **kw)
        if Path(path).name == "session.session":
            st = os.stat(path)
            os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns + 1_000_000))
        return data

    monkeypatch.setattr(secrets, "read_secret_bytes", touching)
    report = _migrate()
    assert [s for s, _ in report.failed] == ["layout 1: secrets"]
    assert "changed while it was being read" in report.failed[0][1]
    assert not (_local() / "telegram.session").exists()


# --- reading and logging --------------------------------------------------------------------

def test_migration_reads_secrets_only_through_core_secrets(monkeypatch, tmp_path):
    _write(_old_dir() / "secrets.env", "EXA_API_KEY=fake-exa\nSOMETHING=fake-other\n")
    _write(_old_dir() / "getcourse.env", "GETCOURSE_KEY=fake-getcourse\n")
    _write(paths.legacy("secrets.dor_old"), "EXA_API_KEY=fake-exa-dor\n")
    _write(paths.legacy("notion.token"), "fake-notion\n")
    _write(paths.legacy("telegram") / "config.json", json.dumps({"api_id": 1, "api_hash": "fake-h"}))
    _write(_session_src(), _SESSION)
    _plant_google()
    secret_dirs = [paths.root() / "secrets", *(paths.legacy(n) for n in
                   ("secrets.h2t", "secrets.dor", "secrets.dor_old", "notion.token",
                    "google.store", "google.gmail", "google.dor", "telegram"))]
    rec = audit.Recorder([paths.home()], secret_dirs, paths.legacy_roots(), {})
    ctx = _ctx()
    with rec.active():
        secrets_phase.phase_secrets(ctx)
        verify.phase_verify(ctx)
    assert rec.violations == []
    assert (_local() / "telegram.session").is_file()     # the run did read and write


def _all_text() -> str:
    logs = paths.logs_dir()
    out = [p.read_text(encoding="utf-8") for p in logs.glob("writes*.jsonl")] if logs.is_dir() else []
    out += [j.file.read_text(encoding="utf-8") for j in Journal.all()]
    return "\n".join(out)


def test_no_value_in_journal_or_report():
    _write(_old_dir() / "secrets.env", "MEETGEEK_API_KEY=fake-SECRET-xyz\nOTHER_KEY=fake-SECRET-xyz-2\n")
    _write(paths.legacy("secrets.dor_old"), "MEETGEEK_API_KEY=fake-SECRET-xyz-dor\n")
    _write(_shared() / "exa.env", "EXA_API_KEY=fake-SECRET-xyz-exa\n")
    _write(paths.legacy("secrets.dor"), "EXA_X=fake-SECRET-xyz-x\n")
    report = _migrate()
    assert report.failed == []
    assert _env(_shared() / "meetgeek.env") == {"MEETGEEK_API_KEY": "fake-SECRET-xyz"}
    text = _all_text() + json.dumps(report.as_dict())
    assert "fake-SECRET" not in text
    # and a failure report names keys, not values
    (_shared() / "meetgeek.env").write_text("", encoding="utf-8")
    failed = Report()
    ctx = engine.PhaseContext(journal=Journal.latest(), machine="m", machine_explicit=False,
                              report=failed)
    with pytest.raises(engine.PhaseFailed) as exc:
        verify.phase_verify(ctx)
    assert "MEETGEEK_API_KEY" in str(exc.value) and "fake-SECRET" not in str(exc.value)


def test_put_union_logs_key_names():
    _write(_shared() / "exa.env", "EXA_API_KEY=fake-exa\n")
    _write(_old_dir() / "secrets.env", "EXA_X=fake-exa-x\n")
    ctx = _ctx()
    secrets_phase.phase_secrets(ctx)
    assert _env(_shared() / "exa.env") == {"EXA_API_KEY": "fake-exa", "EXA_X": "fake-exa-x"}
    rows = [json.loads(line) for line in
            (paths.logs_dir() / "writes.jsonl").read_text(encoding="utf-8").splitlines()]
    target = [r for r in rows if r["path"] == str(_shared() / "exa.env")]
    prev = [r for r in rows if r["path"].startswith(str(ctx.journal.dir / "prev"))]
    assert target and prev
    for r in target + prev:
        assert r.get("keys") == ["EXA_API_KEY", "EXA_X"], r
        assert r["sha256"] is None, r
    assert "fake-exa" not in json.dumps(rows)
