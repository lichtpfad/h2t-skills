"""Every command that writes to disk, run under a temporary HOME (#548 §7.3).

Phase-C tasks append their cases here. A case gets the sandbox and monkeypatch, fakes its
provider exactly as that connector's own tests do, and runs the command in-process.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class Case:
    id: str
    run: Callable
    compat: tuple[str, ...] = ()  # legacy files this case may write via store compat
    setup: Callable | None = None  # writes the starting state before the recorder is on (R30)


def _store_replace_state(sb, mp):
    from h2t_ops.core import paths, store
    store.replace(paths.state_dir() / "probe.json", "{}", place="state")


def _google_tokens(sb, mp):
    from h2t_ops.core import paths
    local = paths.secrets_local() / "google.token.json"
    local.parent.mkdir(parents=True, exist_ok=True)
    local.write_text('{"refresh_token": "fake-r1"}')
    (paths.legacy("google.store") / "tokens.json").write_text('{"refresh_token": "fake-r1"}')


def _google_refresh(refresh_token):
    def run(sb, mp):
        import json
        from types import SimpleNamespace

        from h2t_ops.core import google_auth
        scope = "https://www.googleapis.com/auth/calendar"
        state = {"refresh_token": refresh_token, "client_id": "fake-id", "client_secret": "fake-cs",
                 "token_uri": "https://oauth2.googleapis.com/token", "scopes": [scope]}
        creds = SimpleNamespace(valid=False, expired=True, refresh_token=refresh_token,
                                scopes=[scope], refresh=lambda req: None,
                                to_json=lambda: json.dumps({"token": "fake-access", **state}))
        mp.setattr(google_auth, "_load_credentials", lambda data, client: creds)
        mp.setattr(google_auth, "_request", lambda: None)
        google_auth.resolve_google_credentials("calendar", [scope])
    return run


def _telegram_cli(argv, client_cls):
    """Run `h2t-ops telegram <argv>` in-process with a stand-in for Telethon's client."""
    def run(sb, mp):
        import argparse

        from h2t_ops.connectors.telegram import client, commands
        mp.setattr(client.TelegramClientAdapter, "_telegram_client_class", lambda self: client_cls())
        p = argparse.ArgumentParser()
        commands.register(p.add_subparsers(dest="connector"))
        commands.run(p.parse_args(["telegram", *argv]))
    return run


def _telegram_fake():
    """Telethon's TelegramClient as far as the commands use it: it opens <session>.session
    itself, as SQLiteSession does, so the write must be one store.managed handed over."""
    from pathlib import Path
    from types import SimpleNamespace

    from telethon.tl.types import auth as tl_auth

    class Fake:
        def __init__(self, session, api_id, api_hash):
            p = Path(session + ".session")
            if not p.exists():
                p.write_bytes(b"fake-session")

        def connect(self):
            pass

        def disconnect(self):
            pass

        def send_code_request(self, phone):
            return SimpleNamespace(phone_code_hash="fake-hash", type=tl_auth.SentCodeTypeSms(length=5),
                                   next_type=None, timeout=None)

        def iter_dialogs(self, limit=None):
            return []

        def iter_messages(self, entity, limit=None):
            return []

        def get_messages(self, entity, ids=None):
            f = SimpleNamespace(name="report.pdf", size=8, mime_type="application/pdf", ext=".pdf")
            return SimpleNamespace(media=SimpleNamespace(), file=f)

        def download_media(self, message, file=None):
            if isinstance(file, str):           # a directory, as 3.x passed it: Telethon names
                target = Path(file) / message.file.name   # the file and writes it itself
                target.write_bytes(b"fake-pdf")
                return str(target)
            file.write(b"fake-pdf")
            return file
    return Fake


def _telegram_keys(sb, mp):
    from h2t_ops.core import paths
    shared = paths.secrets_shared()
    shared.mkdir(parents=True, exist_ok=True)
    (shared / "telegram.env").write_text("TELEGRAM_API_ID=1\nTELEGRAM_API_HASH=fake-hash\n")


def _sqlite_session(path, rows=()):
    import sqlite3
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE entities (id INTEGER PRIMARY KEY, hash INTEGER)")
    conn.executemany("INSERT INTO entities VALUES (?, ?)", rows)
    conn.commit()
    conn.close()


def _telegram_legacy_session(sb, mp):
    import os
    import stat

    from h2t_ops.core import paths
    _telegram_keys(sb, mp)
    d = paths.legacy("telegram")
    os.chmod(d, stat.S_IRWXU)        # the sandbox closes legacy dirs; open it to plant the file
    try:
        _sqlite_session(d / "session.session", [(-1000000000010, 42)])
    finally:
        os.chmod(d, stat.S_IRUSR | stat.S_IXUSR)


def _telegram_new_session(sb, mp):
    from h2t_ops.core import paths
    _telegram_keys(sb, mp)
    _sqlite_session(paths.secrets_local() / "telegram.session", [(-1000000000010, 42)])


def _provider_key(provider, text):
    def setup(sb, mp):
        import os

        from h2t_ops.core import paths, providers
        for k in [k for k in os.environ if k.startswith(providers.key_prefix(provider))]:
            mp.delenv(k)
        shared = paths.secrets_shared()
        shared.mkdir(parents=True, exist_ok=True)
        (shared / f"{provider}.env").write_text(text)
    return setup


def _notion_empty_new_key(sb, mp):
    """notion.env carries an empty NOTION_API_TOKEN= (what the skeleton writes) and the token
    lives only in the 3.x file: the per-key fallback reads it, legitimately."""
    import os
    import stat

    from h2t_ops.core import paths
    mp.delenv("NOTION_API_TOKEN", raising=False)
    shared = paths.secrets_shared()
    shared.mkdir(parents=True, exist_ok=True)
    (shared / "notion.env").write_text("NOTION_API_TOKEN=\n")
    old = paths.legacy("notion.token")
    os.chmod(old.parent, stat.S_IRWXU)        # the sandbox closes legacy dirs; open it to plant
    try:
        old.write_text("fake-old-notion\n")
    finally:
        os.chmod(old.parent, stat.S_IRUSR | stat.S_IXUSR)


def _notion_resolve(sb, mp):
    from h2t_ops.core import secrets
    assert secrets.resolve_notion_token() == "fake-old-notion"


def _research_resolve(sb, mp):
    from h2t_ops.connectors.research import client
    assert client.resolve_secret("EXA_API_KEY") == "fake-exa"


def _dropbox_init(sb, mp):
    from h2t_ops.connectors.dropbox.client import DropboxClient
    assert DropboxClient()._token == "fake-dropbox"


def _evals_load(sb, mp):
    from h2t_ops.lifecycle.eval.session import SkillEval
    from h2t_ops.lifecycle.eval.status import get_status
    assert SkillEval("session-start", domain="dev", project="p")._env["H2T_EVALS_TOKEN"] == "fake-evals"
    assert get_status()["token_present"] is True


def _granola_sync(sb, mp):
    """`granola sync` with no --to, the stand-in client of tests/connectors/granola."""
    from h2t_ops.connectors.granola import sync
    from tests.connectors.granola.test_sync import _client
    sync.sync_notes(_client(), include={"summaries", "transcripts"})


def _granola_foreign_file(sb, mp):
    f = sb.lake / "granola" / "summaries" / "not_1.md"
    f.parent.mkdir(parents=True)
    f.write_text("hand-made")


def _granola_sync_refuses(sb, mp):
    from h2t_ops.connectors.granola import sync
    from tests.connectors.granola.test_sync import _client
    assert sync.sync_notes(_client(), include={"summaries"})["refused"] == 1
    assert (sb.lake / "granola" / "summaries" / "not_1.md").read_text() == "hand-made"


def _no_lake_declared(sb, mp):
    """A migrated machine with no lake in paths.yaml: data/lake. Before layout 1 the 3.x
    lake would be the lake (paths._fallback), and the sandbox holds ~/.dor/lake closed."""
    from h2t_ops.core import paths
    paths.paths_yaml().write_text(f"version: 1\nplaces:\n  inbox: {sb.inbox}\n", encoding="utf-8")
    paths.layout_file().write_text('{"layout": 1}\n', encoding="utf-8")


def _granola_sync_default_lake(sb, mp):
    from h2t_ops.core import paths
    _granola_sync(sb, mp)
    assert (paths.data_dir() / "lake" / "granola" / "summaries" / "not_1.md").is_file()


def _meetgeek_key(sb, mp):
    mp.setenv("MEETGEEK_API_KEY", "fake-meetgeek")


def _meetgeek_download(sb, mp):
    """The recording stream goes through store.writer into <lake>/meetgeek (R29)."""
    import requests

    from h2t_ops.connectors.meetgeek.client import MeetGeekClient

    class Resp:
        status_code = 200

        def iter_content(self, chunk_size):
            yield b"RECORDING"

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    mp.setattr(requests, "get", lambda url, **kw: Resp())
    dest = sb.lake / "meetgeek" / "recordings" / "m1.mp4"
    MeetGeekClient().download_to("https://media.test/m1", dest, exclusive=True)
    assert dest.read_bytes() == b"RECORDING"


def _meetgeek_webhook(sb, mp):
    """One POST through the webhook handler, default --out (<lake>/meetgeek/webhooks)."""
    import argparse
    import http.server
    import io
    from types import SimpleNamespace

    from h2t_ops.connectors.meetgeek import commands, pipeline

    class Server:
        def __init__(self, addr, handler):
            self.handler = handler

        def serve_forever(self):
            body = b'{"event": "x"}'
            self.handler.do_POST(SimpleNamespace(headers={"Content-Length": str(len(body))},
                                                 path="/e", rfile=io.BytesIO(body),
                                                 _reply=lambda code, text="": None))

        def server_close(self):
            pass

    mp.setattr(http.server, "ThreadingHTTPServer", Server)
    p = argparse.ArgumentParser()
    commands.register(p.add_subparsers(dest="connector"))
    pipeline.webhook_server(p.parse_args(["meetgeek", "webhook-server", "--secret", ""]))
    assert len(list((sb.lake / "meetgeek" / "webhooks").glob("*.json"))) == 1


def _meetgeek_output_flag(sb, mp):
    """`-o PATH` of any meetgeek verb: a path the user named, through store (dest)."""
    from h2t_ops.connectors.meetgeek import commands
    out = sb.lake.parent / "named" / "t.json"
    commands._write_output({"a": 1}, str(out))
    assert out.is_file()


def _meetgeek_journal(sb, mp):
    """An upload journal row: the shard registered in the lake manifest, then appended."""
    from h2t_ops.connectors.meetgeek import recovery
    recovery.append_uploads_manifest({"source_webm": "/x/a.webm", "status": "converted"})
    assert recovery.uploads_manifest_path().is_file()


def _drive_client(mp, name="report.txt", payload=b"data"):
    """DriveClient without __init__, the stand-in service of tests/connectors/drive."""
    from unittest.mock import MagicMock

    from h2t_ops.connectors.drive import client as dmod
    c = object.__new__(dmod.DriveClient)
    c.service = MagicMock()
    files = c.service.files.return_value
    files.get.return_value.execute.return_value = {"name": name, "mimeType": "text/plain"}

    class Download:
        def __init__(self, fd, request):
            self.fd = fd

        def next_chunk(self):
            self.fd.write(payload)
            return None, True

    mp.setattr(dmod, "_media_io_base_download", lambda: Download)
    return c


def _drive_download_default(sb, mp):
    _drive_client(mp).download_file("f1")
    assert (sb.inbox / "report.txt").read_bytes() == b"data"


def _drive_download_dest(sb, mp):
    """--dest: the path the user named, replaced through store (dest=True)."""
    target = sb.home.parent / "named" / "out.txt"
    _drive_client(mp).download_file("f1", dest=str(target))
    assert target.read_bytes() == b"data"


def _gmail_attachment_default(sb, mp):
    from tests.connectors.gmail.test_client import _client_with, _MsgSvc
    svc = _MsgSvc([{"mimeType": "application/pdf", "filename": "../a/report.pdf",
                    "body": {"attachmentId": "att1", "size": 5}}])
    c, _ = _client_with(svc)
    c.download_attachment("m1", "att1")
    assert (sb.inbox / "report.pdf").read_bytes() == b"hello"


def _notion_export_default(sb, mp):
    import h2t_ops.connectors.notion.client as client_mod
    from h2t_ops.connectors.notion import commands
    from tests.connectors.notion.test_commands import _sync_args, _SyncStub
    mp.setattr(client_mod, "NotionClient", lambda: _SyncStub())
    commands.run(_sync_args())
    assert (sb.inbox / "P-1.md").is_file()


def _dropbox_download_default(sb, mp):
    """`dropbox download <path>` with --gunzip: raw bytes in scratch, plain ones in the inbox."""
    import gzip
    import sys

    from h2t_ops.connectors.dropbox.client import DropboxClient
    from tests.connectors.dropbox.test_client import _fake_requests, _Resp
    c = object.__new__(DropboxClient)
    c._token, c._timeout, c._path_root = "fake-dropbox", 10, ""
    fake, _ = _fake_requests(lambda *a, **k: _Resp(200, chunks=[gzip.compress(b"<P/>")]))
    mp.setitem(sys.modules, "requests", fake)
    c.download("/x/seq.prproj", gunzip=True)
    assert (sb.inbox / "seq.prproj").read_bytes() == b"<P/>"


def _research_off(mp):
    mp.setenv("H2T_EVALS_MODE", "off")
    mp.setenv("H2T_RESEARCH_TELEMETRY_DISABLE", "0")


def _research_save(sb, mp):
    """A search with no --output-dir: artifacts, objects, indexes, telemetry in data/research."""
    from h2t_ops.connectors.research import client
    from h2t_ops.core import paths
    from tests.connectors.research.test_client import (
        _patch_exa_search,
        _provider_envelope,
    )
    _research_off(mp)
    mp.setattr(client, "resolve_secret", lambda name: "fake-exa")
    _patch_exa_search(mp, provider_envelope=_provider_envelope("OK"), exit_code=0)
    client.ResearchClient().search(query="q", project="p", no_retry=True)
    assert (paths.data_dir() / "research" / "telemetry.jsonl").is_file()


def _research_fetch_save(sb, mp):
    """`research fetch --keep-raw`, no --output-dir: the raw page through research.fetch."""
    from unittest.mock import patch

    from h2t_ops import cli
    from h2t_ops.core import paths
    from tests.connectors.research.test_fetch_script_cases import (
        _load_fixture,
        _make_http_response,
    )
    _research_off(mp)
    for k in ("JINA_API_KEY", "EXA_API_KEY"):
        mp.delenv(k, raising=False)
    html = _load_fixture("public_article.html").encode("utf-8")
    with patch("urllib.request.urlopen", return_value=_make_http_response(html)):
        cli.dispatch(["research", "fetch", "--url", "https://example.com/x", "--keep-raw",
                      "--project", "p"])
    assert list((paths.data_dir() / "research").glob("*.raw.html"))


def _research_corrupt_alias_index(sb, mp):
    from h2t_ops.connectors.research import store
    from tests.connectors.research.test_maintenance import _demo_document
    root = store.default_root()
    _demo_document(root)
    index = store.index_path(root, "aliases")
    index.parent.mkdir(parents=True, exist_ok=True)
    index.write_text("[null]\n", encoding="utf-8")


def _research_maintenance(sb, mp):
    """rebuild-indexes over a corrupt alias index: the copy aside and four indexes, via store."""
    from h2t_ops.connectors.research import client, store
    assert client.ResearchClient().rebuild_research_indexes()["status"] == "ok"
    assert store.index_path(store.default_root(), "aliases").with_suffix(".json.corrupt").is_file()


def _visual_ocr_shot(sb, mp):
    (sb.home.parent / "shot.png").write_bytes(b"fake-png")


def _research_visual_ocr(sb, mp):
    """visual-ocr --auto: h2t-screenshot into a store.scratch dir, the capture copied into
    data/research through a store handle, the sidecar through store."""
    import shutil
    import subprocess
    from types import SimpleNamespace

    from h2t_ops.connectors.research import visual_ocr
    from h2t_ops.core import paths
    shot = sb.home.parent / "shot.png"
    mp.setattr(shutil, "which", lambda name: "/bin/h2t-screenshot")
    mp.setattr(subprocess, "run", lambda *a, **k: SimpleNamespace(
        returncode=0, stdout=f"✓ desktop: {shot}\n", stderr=""))
    mp.setattr(visual_ocr, "extract_text_from_image", lambda p: ("text", [], "high"))
    visual_ocr.capture_and_ocr("https://example.com/x", output_dir=paths.data_dir() / "research",
                               project="p")
    assert list((paths.data_dir() / "research").glob("*.capture.png"))


def _evals_write_local(sb, mp):
    from h2t_ops.core import paths
    from h2t_ops.lifecycle.eval.session import SkillEval
    mp.setenv("H2T_EVALS_MODE", "local")
    with SkillEval("handoff", domain="dev", project="p"):
        pass
    assert list((paths.records("evals", paths.machine_name()) / "handoff").glob("*.json"))


def _evals_spool(sb, mp):
    """push: the stand-in SDK opens the spool with sqlite3 itself, inside store.managed."""
    import sqlite3
    import sys
    import types

    from h2t_ops.core import paths
    from h2t_ops.lifecycle.eval.session import SkillEval

    class Client:
        def __init__(self, *, service_url, token, spool_path):
            sqlite3.connect(spool_path).close()

        def flush(self, **kw):
            pass

    class Session:
        def __init__(self, **kw):
            pass

        def start(self):
            pass

        def metric(self, key, **kw):
            pass

        def finish(self, **kw):
            pass

    sdk = types.ModuleType("h2t_evals.sdk")
    sdk.EvalClient, sdk.EvalSession = Client, Session
    mp.setitem(sys.modules, "h2t_evals", types.ModuleType("h2t_evals"))
    mp.setitem(sys.modules, "h2t_evals.sdk", sdk)
    mp.setenv("H2T_EVALS_MODE", "push")
    with SkillEval("research", domain="ops", project="p"):
        pass
    assert paths.evals_spool().is_file()


def _creative_profiles_dir(sb, mp):
    import contextlib
    import io

    from h2t_ops.core import paths
    from h2t_ops.tools.creative import cli
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        assert cli.main(["profiles-dir"]) == 0
    assert out.getvalue().strip() == str(paths.data_dir() / "creative" / "profiles")


def _handoff(done):
    def run(sb, mp):
        from pathlib import Path

        from h2t_ops.core import paths
        from h2t_ops.lifecycle import handoff
        mp.setenv("H2T_MACHINE_NAME", "sandbox")
        mp.setenv("H2T_EVALS_MODE", "off")
        out = handoff.write_handoff(session_id="dev-p-sandbox", domain="dev", project="p",
                                    what_done=done, what_remains="- [ ] next", artifacts=["pr:1"])
        assert out["status"] == "ok", out
        assert paths.records("sessions", "sandbox") in Path(out["markdown"]).parents
    return run


def _activity_start(sb, mp):
    from h2t_ops.core import paths
    from h2t_ops.lifecycle.activity import writer
    writer.log_session_start("s", "dev", "p", machine="sandbox")
    assert paths.activity_file("sandbox").is_file()


def _index_records(machine):
    def setup(sb, mp):
        from h2t_ops.core import paths
        from h2t_ops.lifecycle import session_record
        f = paths.records("sessions", machine) / "p" / f"{machine}-1.md"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(session_record.render({"session_id": f"{machine}-1", "machine": machine,
                                             "project": "p", "updated_at": "2026-10-18T00:00:00Z"}, b""))
        (paths.config_dir() / "domains.yaml").write_text(
            "domains:\n  dev:\n    projects:\n      - id: p\n", encoding="utf-8")
    return setup


def _index_rebuild(sb, mp):
    from h2t_ops.core import paths
    from h2t_ops.lifecycle import index
    assert index.rebuild() == {"sessions": 1, "projects": 1, "problems": 0}
    assert (paths.state_dir() / "index.sqlite").is_file()


def _index_built(sb, mp):
    from h2t_ops.lifecycle import index
    _index_records("sandbox")(sb, mp)
    index.rebuild()
    _index_records("laptop")(sb, mp)      # arrives from another machine after the build


def _index_refresh(sb, mp):
    from h2t_ops.lifecycle import index
    with index.connect(refresh=True):
        pass
    assert {s["machine"] for s in index.latest_sessions(["p"])} == {"laptop", "sandbox"}


def _cli(*argv):
    """Run `h2t-ops <argv>` in-process; exit 0 required."""
    def run(sb, mp):
        from h2t_ops.cli import dispatch
        assert dispatch(list(argv)) == 0
    return run


def _paths_set(sb, mp):
    from h2t_ops.core import paths
    _cli("paths", "set", "kb", str(sb.home.parent / "kb"))(sb, mp)
    assert paths.paths_config().places["kb"] == sb.home.parent / "kb"


def _broken_paths_yaml(sb, mp):
    from h2t_ops.core import paths
    paths.paths_yaml().write_text("places:\n  lake: [unclosed\n", encoding="utf-8")


def _paths_set_repair(sb, mp):
    """paths.yaml does not parse: the config write still goes through (R17), the old bytes
    into state/backups."""
    from h2t_ops.core import paths
    _cli("paths", "set", "lake", str(sb.lake))(sb, mp)
    assert paths.paths_config().places == {"lake": sb.lake}
    assert list(paths.backups_dir().glob("paths.yaml.*"))


def _ontology_config(sb, mp):
    from h2t_ops.core import paths
    (paths.config_dir() / "repo-mapping.yaml").write_text("# kept\nmappings: {}\n", encoding="utf-8")
    (paths.config_dir() / "domains.yaml").write_text("domains: {}\n", encoding="utf-8")
    (sb.home.parent / "repo").mkdir()


def _register_apply(sb, mp):
    """config/*.yaml replaced through store, copies in state/backups, project-id created in
    a temporary repository through store.repo."""
    from h2t_ops.core import paths
    from h2t_ops.lifecycle.apply_registration import apply_registration
    repo = sb.home.parent / "repo"
    out = apply_registration(project_id="p", domain="dev", project_type="git", label="P",
                             cwd=str(repo))
    assert out["status"] == "ok"
    assert (repo / ".claude" / "project-id").read_text(encoding="utf-8") == "dev/p\n"
    assert "# kept" in (paths.config_dir() / "repo-mapping.yaml").read_text(encoding="utf-8")
    assert len(list(paths.backups_dir().glob("*.yaml.*"))) == 2


def _detect_project(sb, mp):
    from h2t_ops.lifecycle.detect_project import detect_project
    assert detect_project(str(sb.home.parent / "repo"))["already_registered"] is False


def _session_start_briefing(*, legacy=False):
    """find_latest_session_index + format_briefing as session-start calls them; the only
    write is the index in state, through store.connect_sqlite (R18)."""
    def run(sb, mp):
        from h2t_ops.lifecycle.gather import briefing, sessions
        mp.setenv("H2T_MACHINE_NAME", "sandbox")
        latest = sessions.find_latest_session_index("p")
        files = sessions.find_session_files("p")
        md, meta = briefing.format_briefing({"project": {"id": "p"}, "sessions": files,
                                             "latest_session": latest, "machine": "sandbox"})
        assert "### Previous Session  (laptop" in md, md
        assert ("старом месте" in md) is legacy
        assert meta["latest_session"] == latest
    return run


def _laptop_session(sb, mp):
    """One session of p, written on another machine and synced here."""
    from h2t_ops.lifecycle import session_record
    f = session_record.session_path("laptop", "p", "laptop-1")
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_bytes(session_record.render({"session_id": "laptop-1", "machine": "laptop", "project": "p",
                                         "updated_at": "2026-10-18T00:00:00Z", "done": "- synced"}, b""))


def _legacy_sessions(sb, mp):
    """3.x before migration: latest.json and md under ~/.h2t/sessions, nothing in records."""
    import json

    from h2t_ops.core import paths
    leaf = paths.legacy("sessions.h2t") / "laptop" / "p"
    leaf.mkdir(parents=True, exist_ok=True)
    (leaf / "old.md").write_text("# 3.x handoff\n", encoding="utf-8")
    (leaf / "latest.json").write_text(json.dumps({"version": 1, "session_id": "old",
                                                  "summary_short": "from 3.x"}), encoding="utf-8")


def _handoff_no_latest_json(sb, mp):
    from pathlib import Path
    _handoff("- first")(sb, mp)
    from h2t_ops.core import paths
    leaf = paths.records("sessions", "sandbox") / "p"
    assert [f.name for f in Path(leaf).iterdir()] == ["dev-p-sandbox.md"]   # R10


def _layout_legacy_home(sb, mp):
    """A 3.x home for `h2t-setup layout migrate`: one session record under ~/.dor/sessions
    and one key in ~/.dor/secrets/secrets.env, fake values only. The sandbox closes the
    3.x directories; these two are opened again, as a user's would be, so the migration
    can leave its MOVED-TO markers there (§8)."""
    import os
    import stat

    from h2t_ops.core import paths
    mp.setenv("H2T_MACHINE_NAME", "sandbox")
    leaf = paths.legacy("sessions.dor") / "sandbox" / "p"
    env = paths.legacy("secrets.dor")
    for d in (paths.legacy("sessions.dor"), env.parent):
        os.chmod(d, stat.S_IRWXU)
    leaf.mkdir(parents=True, exist_ok=True)
    (leaf / "s1.md").write_text("# Session: s1\n\n- **Date:** 2026-08-22\n- **Domain:** dev\n"
                                "- **Project:** p\n\n## What was done\nfake\n", encoding="utf-8")
    env.write_text("EXA_API_KEY=fake-exa\n", encoding="utf-8")


def _layout_migrate(sb, mp):
    from h2t_ops.core import paths
    from h2t_ops.setup import cli
    assert cli.main(["layout", "migrate", "--machine", "sandbox", "--json"]) == 0
    # it did migrate, so the audit saw the real writes (existence only: no secret is read)
    assert (paths.records("sessions", "sandbox") / "p" / "s1.md").is_file()
    assert any(paths.secrets_shared().iterdir()) and paths.layout_file().is_file()


# Task 17: every write into a user's repository (§7.1, table «repo»). A scenario is
# (setup, run) over a repository path; setup runs before the recorder is on. The same
# table drives tests/governance/test_repo_writers.py, which checks every path a command
# changed against REPO_WRITERS[command].

def _git(repo, *args):
    import subprocess
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def _git_repo(repo, files=None, untracked=None):
    """A repository with files committed, then files left untracked."""
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    for group in (files or {}, untracked or {}):
        for rel, text in group.items():
            p = repo / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text, encoding="utf-8")
        if group is files and files:
            _git(repo, "add", "-A")
            _git(repo, "commit", "-q", "-m", "seed")


_OPEN_PLAN = '---\ntitle: "x"\nstatus: draft\n---\nbody\n'


def _scaffold(repo, mp):
    import argparse

    from h2t_ops.lifecycle import scaffold_project
    out = scaffold_project.cmd_create(argparse.Namespace(
        id=repo.name, type="code-local", stack="python", dir=str(repo.parent),
        description="", dry_run=False, merge=False))
    assert out["status"] == "ok", out


def _docs_init(repo, mp):
    from h2t_ops.tools.docs import docs_init
    assert docs_init.init_repo(repo.name, repo_root=repo, dry_run=False)


def _fix_safe_setup(repo, mp):
    import json
    _git_repo(repo, {
        ".claude/rules/docs-lint.yaml": "template: code_repo\nproject_checks: true\n",
        "docs/superpowers/plans/2026-01-01-x.md": "# X\n",
        "docs/superpowers/specs/2026-01-01-y.md": "# Y\n",
        "docs/a.pdf": "pdf", "docs/b.pdf": "pdf", "deliverables/.gitkeep": "",
        "debug.log": "log\n",
    })
    (repo.parent / "fix-plan.json").write_text(json.dumps({"plan_id": "p", "actions": [
        {"action_id": "d", "type": "create_dir", "path": "docs/extra", "risk": "safe"},
        {"action_id": "f", "type": "add_frontmatter", "path": "docs/superpowers/specs/2026-01-01-y.md",
         "risk": "safe"},
        {"action_id": "m", "type": "move_file", "path": "docs/b.pdf", "target_path": "deliverables/b.pdf",
         "risk": "safe"},
    ]}), encoding="utf-8")


def _fix_safe(repo, mp):
    from h2t_ops.tools.docs import lint
    lint._run_fix_safe(repo, plan_file=str(repo.parent / "fix-plan.json"))
    lint._run_fix_safe(repo)
    assert (repo / "deliverables" / "a.pdf").exists() and (repo / "deliverables" / "b.pdf").exists()


def _fix_index_setup(repo, mp):
    import json
    _git_repo(repo, {"docs/README.md": "# Docs\n", "docs/adr/0001-x.md": "# X\n"})
    (repo.parent / "index-plan.json").write_text(json.dumps({"plan_id": "p", "actions": [
        {"action_id": "i", "type": "add_to_index"}]}), encoding="utf-8")


def _fix_index(repo, mp):
    from h2t_ops.tools.docs import lint
    lint._run_fix_index(repo, apply=True)
    lint._run_fix_index(repo, apply=True, plan_file=str(repo.parent / "index-plan.json"))


def _retire_setup(repo, mp):
    _git_repo(repo, {"docs/superpowers/plans/2020-01-05-old.md": _OPEN_PLAN},
              untracked={"docs/superpowers/specs/2020-01-05-loose.md": _OPEN_PLAN})


def _retire(repo, mp):
    from h2t_ops.tools.docs import lint
    lint._run_retire(repo, apply=True)
    assert (repo / "docs/archive/plans/2020-01-05-old.md").exists()     # git mv
    assert (repo / "docs/archive/specs/2020-01-05-loose.md").exists()   # untracked: rename


def _docs_new(repo, mp):
    from h2t_ops.tools.docs import new_doc
    new_doc.create_doc(repo, "plan", "x", today="2026-10-18", author="t", issue="none", reason="r")
    new_doc.create_doc(repo, "adr", "y", today="2026-10-18", author="t")


def _docs_index(repo, mp):
    import sys

    from h2t_ops.tools.docs import index
    mp.setattr(index, "repo_path", lambda name: repo)
    mp.setattr(sys, "argv", ["docs-index", repo.name, "--apply"])
    index.main()


def _closure(repo, mp):
    from h2t_ops.tools.docs import closure
    closure.write_report(repo, {"milestone": {"title": "M1 done"}})


def _agent_profile(repo, mp):
    from h2t_ops.tools.agent_profile import apply_agent_profile as ap
    assert ap.run_cli(["apply", "--cwd", str(repo), "--base", "dev"]).get("ok"), "apply failed"


def _plan_closer_setup(repo, mp):
    _git_repo(repo, {"docs/superpowers/plans/2026-01-01-x.md": _OPEN_PLAN})


def _plan_closer(repo, mp):
    from h2t_ops.hooks import plan_closer
    mp.chdir(repo)
    mp.setattr(plan_closer, "_pr_view", lambda root, n: {"state": "MERGED", "files": [
        {"path": "src/a.py"}, {"path": "docs/superpowers/plans/2026-01-01-x.md"}]})
    plan_closer.handle({"tool_name": "Bash", "tool_input": {"command": "gh pr merge 7 --squash"}})
    assert 'status: "done"' in (repo / "docs/superpowers/plans/2026-01-01-x.md").read_text(encoding="utf-8")


def _post_commit_setup(repo, mp):
    _git_repo(repo, {"docs/a.md": "# A\n"})


def _post_commit(repo, mp):
    import io
    import sys

    from h2t_ops.hooks import post_git_commit_docs_lint as hook
    mp.chdir(repo)
    mp.setattr(sys, "stdin", io.StringIO(""))
    mp.setattr(hook, "run_docs_lint_doctor", lambda *a, **k: {"status": "ok"})
    assert hook.main([]) == 0
    assert (repo / ".h2t/lifecycle/post-git-commit-docs-lint.json").exists()


def _project_audit_setup(repo, mp):
    _git_repo(repo, {"my-landings.yml": "projects:\n  - id: foo\n    docs:\n      readme: false\n"})


def _project_audit(repo, mp):
    """--projects-yaml names the file (R7): any name, written with dest=True."""
    from h2t_ops.lifecycle.project_audit_report import update_project_docs
    assert update_project_docs(repo / "my-landings.yml", "foo", {"readme": True})
    assert "readme: true" in (repo / "my-landings.yml").read_text(encoding="utf-8")


def _plain_repo(repo, mp):
    _git_repo(repo)


# command -> (setup, run, commands it runs in a child process whose writes it carries)
REPO_SCENARIOS: dict[str, tuple] = {
    "h2t-scaffold-project": (None, _scaffold, ("h2t-docs-init",)),
    "h2t-docs-init": (_plain_repo, _docs_init, ()),
    "h2t-docs-lint fix-safe": (_fix_safe_setup, _fix_safe, ()),
    "h2t-docs-lint fix-index": (_fix_index_setup, _fix_index, ()),
    "h2t-docs-lint retire": (_retire_setup, _retire, ()),
    "h2t-docs-lint new": (_plain_repo, _docs_new, ()),
    "docs-index": (_fix_index_setup, _docs_index, ()),
    "h2t-milestone-closure": (_plain_repo, _closure, ()),
    "h2t-agent-profile": (_plain_repo, _agent_profile, ()),
    "plan-closer": (_plan_closer_setup, _plan_closer, ()),
    "post-git-commit-docs-lint": (_post_commit_setup, _post_commit, ()),
}


def _in_repo(fn):
    """A scenario step as a sandbox step: the repository is <tmp_path>/repo."""
    def step(sb, mp):
        return fn(sb.home.parent / "repo", mp)
    return step


def _repo_case(case_id, command):
    setup, run, _also = REPO_SCENARIOS[command]
    return Case(case_id, _in_repo(run), setup=_in_repo(setup) if setup else None)


# Paths the user named (R7, and the same reading for --save and the runbook destination):
# written with dest=True, not through the allow-list.

def _docs_lint_save(repo, mp):
    from h2t_ops.tools.docs import lint
    lint._run_plan(repo, save_file=str(repo.parent / "plan.json"))
    assert (repo.parent / "plan.json").exists()


def _runbook(repo, mp):
    from h2t_ops.tools.runbook import cli
    dest = repo / "docs/superpowers/plans/2026-10-18-x-runbook.md"
    assert cli.main(["new", str(dest), "--title", "T", "--branch", "b", "--spec-path", "s.md",
                     "--issue", "1", "--venv-test", "pytest", "--e2e-state", "N/A"]) == 0
    assert dest.exists()


def _agent_catalog_setup(repo, mp):
    from h2t_ops.tools.agent_profile import apply_agent_profile as ap
    (repo.parent / "catalog").mkdir()
    (repo.parent / "catalog" / "agent-profiles.json").write_bytes(ap._DEFAULT_CATALOG.read_bytes())


def _agent_catalog(repo, mp):
    from h2t_ops.tools.agent_profile import apply_agent_profile as ap
    out = ap.catalog_add_profile("x", "d", [], [], catalog_path=repo.parent / "catalog" / "agent-profiles.json")
    assert out.get("ok"), out


_GRAPH = {"nodes": [{"id": "a", "label": "A", "type": "rounded_rect"}], "edges": []}


def _drawio_generate(repo, mp):
    from h2t_ops.tools.drawio.generate import generate_diagram
    out = repo.parent / "named" / "d.drawio"
    generate_diagram(_GRAPH, out)
    generate_diagram(_GRAPH, out)          # the second run reads and keeps user edits
    assert 'id="a"' in out.read_text(encoding="utf-8")


def _drawio_export_setup(repo, mp):
    src = repo.parent / "named" / "d.drawio"
    src.parent.mkdir(parents=True)
    src.write_text("<mxfile/>", encoding="utf-8")
    (repo.parent / "drawio.yaml").write_text(f"export:\n  drawio_path: {src}\n", encoding="utf-8")


def _drawio_export(repo, mp):
    """The draw.io CLI writes the output itself; the stand-in does it in-process, so the
    recorder sees whether the path was handed over (store.managed)."""
    from pathlib import Path
    from types import SimpleNamespace

    from h2t_ops.tools.drawio import export

    def fake_run(cmd, **kw):
        Path(cmd[cmd.index("--output") + 1]).write_bytes(b"fake-png")
        return SimpleNamespace(returncode=0, stdout="", stderr="")
    mp.setattr(export.subprocess, "run", fake_run)
    out = export.export_diagram(repo.parent / "named" / "d.drawio", fmt="png",
                                output_path=repo.parent / "named" / "out" / "d.png",
                                config_path=repo.parent / "drawio.yaml")
    assert Path(out).read_bytes() == b"fake-png"


def _creative_assemble(repo, mp):
    from h2t_ops.tools.creative import assembler
    recipe = {"title": "T", "sections": [{"component": "hero", "content": {"headline": "H", "subline": "S"}}]}
    out = repo.parent / "named" / "site"
    assembler.main_assemble("landing", recipe, assembler.PROFILES_DIR / "h2t-pfad", out)
    deck = {"title": "D", "slides": [{"layout": "title-only", "content": {"headline": "S1"}}]}
    assembler.main_assemble("deck", deck, assembler.PROFILES_DIR / "h2t-pfad", repo.parent / "named" / "deck")
    assert (out / "fx.js").exists()


# Task 18: install state and sync snapshots in run, hook logs in logs, the gather lock in
# state (R23), the deploy input in a store.scratch() directory.
def _state_commit(sb, mp):
    from h2t_ops.setup import state
    state.commit(state.Install(version="4.0.0", generation="g1", tool_root=str(sb.home),
                               entrypoints={"h2t-hook": str(sb.home / "bin" / "h2t-hook")}))


def _sync_tools(sb, mp):
    """A uv tool dir with a receipt, install.json, and the fake claude of
    tests/setup/test_sync_converges.py: its state file is written here, recorder off."""
    from h2t_ops.core import paths
    from tests.setup.fake_claude import FakeClaude
    root = sb.home.parent / "uv-tools" / "h2t-ops"
    root.mkdir(parents=True)
    (root / "uv-receipt.toml").write_text('[tool]\nrequirements = [{ name = "h2t-ops" }]\n')
    _state_commit(sb, mp)
    sb.claude = FakeClaude(sb.home.parent / "claude-state.json", paths.dir_of("harness"), head="4.0.0")
    sb.claude.seed(plugins=[("h2t-core", "3.9.0", "user", True), ("h2t-core", "4.0.0", "user", True)])
    for v in ("3.8.0", "3.9.0"):
        (paths.dir_of("harness") / "plugins" / "cache" / "lichtpfad" / "h2t-core" / v).mkdir(parents=True, exist_ok=True)
    sb.uv_root = root


def _sync_snapshot(sb, mp):
    from h2t_ops.setup import harness_claude, sync
    harness = sync._snapshot(sb.uv_root, harness_claude.Claude(exe="claude", run=sb.claude))
    from pathlib import Path
    assert {p.name for p in Path(harness["path"]).iterdir()} == {
        "install.json", "uv-receipt.toml", "claude.json"}


def _sync_clean_cache(sb, mp):
    from h2t_ops.core import paths
    from h2t_ops.setup import sync
    removed = sync.clean_cache(paths.dir_of("harness"), [{"id": "h2t-core@lichtpfad", "version": "3.9.0"}],
                               keep=1)
    assert [p.name for p in removed] == ["3.8.0"]


def _machine_name(sb, mp):
    from h2t_ops.setup import legacy
    assert legacy.ensure_machine_name(name="sandbox")["status"] == "written"


def _plugin_cache_dir(sb, mp):
    from h2t_ops.core import paths
    (paths.dir_of("harness") / "plugins" / "cache" / "lichtpfad" / "h2t-core" / "4.0.0").mkdir(parents=True)


def _install_versions_file(sb, mp):
    import json

    from h2t_ops.core import paths
    from h2t_ops.setup import legacy
    mp.setattr(legacy, "install_h2t_ops", lambda source, dry_run=False: {"status": "ok"})
    legacy.main(["install-h2t-ops", "--json"])
    written = json.loads((paths.config_dir() / "plugin-versions.json").read_text(encoding="utf-8"))
    assert written["h2t-core"].endswith("4.0.0")


def _hook_log_failure(sb, mp):
    from h2t_ops import hook_entry
    from h2t_ops.core import paths
    assert hook_entry._failed("probe", RuntimeError("boom")) == 1
    assert (paths.logs_dir() / "hooks.jsonl").is_file()


def _guard_log(module):
    def run(sb, mp):
        import importlib
        m = importlib.import_module(f"h2t_ops.hooks.{module}")
        transcript = sb.home.parent / "t.jsonl"
        m.handle({"transcript_path": str(transcript), "session_id": "s1"})
        assert m.log_path().is_file()
    return run


def _guard_transcript(sb, mp):
    import json
    (sb.home.parent / "t.jsonl").write_text(json.dumps({"type": "assistant", "message": {
        "content": [{"type": "text", "text": "Готово. " + "слово " * 30}]}}, ensure_ascii=False))


def _gather_lock(sb, mp):
    import time

    from h2t_ops.hooks import gather
    lock = gather._lock_file("h2t-core:handoff", str(sb.home))
    gather._write_lock(lock, int(time.time()))
    assert gather._locked(lock, int(time.time()))


def _deploy_script(sb, mp):
    script = sb.home.parent / "deploy.py"
    script.write_text(
        "import json, os, pathlib\n"
        "p = json.loads(pathlib.Path(os.environ['H2T_DEPLOY_INPUT_JSON']).read_text())\n"
        "print(json.dumps({'ok': True, 'result': {'service': p['service'], 'target': 'prod', "
        "'status': 'deployed'}}))\n")
    sb.deploy_script = script


def _deploy_input(sb, mp):
    from h2t_ops.deploy import executor
    out = executor._run_script(sb.deploy_script, repo_root=sb.home.parent, payload={"service": "svc"},
                               action="deploy", dry_run=True,
                               environ={"PATH": "/usr/bin:/bin", "HOME": str(sb.home),
                                        "USERPROFILE": str(sb.home)})
    assert out["status"] == "deployed", out


CASES: list[Case] = [
    Case("store.replace.state", _store_replace_state),
    # Task 8: a refresh writes nothing; a rotated refresh token writes local and the mirror.
    Case("google.refresh", _google_refresh("fake-r1"), setup=_google_tokens),
    Case("google.refresh.new-token", _google_refresh("fake-r2"), setup=_google_tokens,
         compat=(".config/google-calendar-mcp/tokens.json",)),
    # Task 9: session and auth state in secrets/local, attachments through a store handle.
    Case("telegram.auth-request-code", _telegram_cli(["auth", "request-code", "--phone", "+100"],
                                                     _telegram_fake), setup=_telegram_keys),
    Case("telegram.download-media.inbox", _telegram_cli(["download-media", "chat", "55"], _telegram_fake),
         setup=_telegram_keys),
    Case("telegram.session.copy-from-legacy", _telegram_cli(["dialogs"], _telegram_fake),
         setup=_telegram_legacy_session),
    Case("telegram.messages", _telegram_cli(["messages", "10", "--limit", "5"], _telegram_fake),
         setup=_telegram_new_session),
    # Task 10: keys only through core.secrets — a read of a secrets file from any other
    # module is a violation.
    Case("research.resolve", _research_resolve, setup=_provider_key("exa", "EXA_API_KEY=fake-exa\n")),
    Case("dropbox.init", _dropbox_init, setup=_provider_key("dropbox", "DROPBOX_TOKEN=fake-dropbox\n")),
    Case("evals.load", _evals_load, setup=_provider_key("h2t-evals", "H2T_EVALS_TOKEN=fake-evals\n")),
    Case("notion.resolve.empty-new-key", _notion_resolve, setup=_notion_empty_new_key),
    # Task 11: the lake through core.lake (manifest protocol), cursors in state.
    Case("granola.sync", _granola_sync),
    Case("granola.sync.foreign-file", _granola_sync_refuses, setup=_granola_foreign_file),
    Case("granola.sync.default-lake", _granola_sync_default_lake, setup=_no_lake_declared),
    Case("meetgeek.download", _meetgeek_download, setup=_meetgeek_key),
    Case("meetgeek.webhooks.write", _meetgeek_webhook),
    Case("meetgeek.output-flag", _meetgeek_output_flag),
    Case("meetgeek.upload-journal", _meetgeek_journal),
    # Task 12: downloads with no path into the inbox, research into data/research, eval
    # records into records/evals, the spool handed to the SDK, creative profiles under data.
    Case("drive.download.default", _drive_download_default),
    Case("drive.download.dest", _drive_download_dest),
    Case("gmail.attachment.default", _gmail_attachment_default),
    Case("notion.export.default", _notion_export_default),
    Case("dropbox.download.default", _dropbox_download_default),
    Case("research.save", _research_save),
    Case("research.fetch.save", _research_fetch_save),
    Case("research.maintenance", _research_maintenance, setup=_research_corrupt_alias_index),
    Case("research.visual-ocr", _research_visual_ocr, setup=_visual_ocr_shot),
    Case("evals.write-local", _evals_write_local),
    Case("evals.spool", _evals_spool),
    Case("creative.profiles-dir", _creative_profiles_dir),
    # Task 13: the session md under records/sessions, activity per machine.
    Case("handoff.write", _handoff("- first")),
    Case("handoff.write.again", _handoff("- second"), setup=_handoff("- first")),
    Case("activity.start", _activity_start),
    # Task 14: the index lives in state and is opened only through store.connect_sqlite (R18).
    Case("index.rebuild", _index_rebuild, setup=_index_records("sandbox")),
    Case("index.connect.refresh", _index_refresh, setup=_index_built),
    # Task 15: the ontology through the index; registration writes config through store.
    Case("register.apply", _register_apply, setup=_ontology_config),
    Case("detect.project", _detect_project, setup=_ontology_config),
    # Task 16: session-start asks the index for the project's last session from any machine;
    # before migration it reads the 3.x roots and writes nothing there; handoff writes no
    # latest.json (R10).
    Case("gather.session-start", _session_start_briefing(), setup=_laptop_session),
    Case("gather.session-start.legacy", _session_start_briefing(legacy=True), setup=_legacy_sessions),
    Case("handoff.write.no-latest-json", _handoff_no_latest_json),
    # Task 17: writes into a user's repository through store.repo and its allow-list; a
    # path the user named through dest=True (R7).
    _repo_case("repo.scaffold", "h2t-scaffold-project"),
    _repo_case("repo.docs-init", "h2t-docs-init"),
    _repo_case("repo.docs-lint.fix-safe", "h2t-docs-lint fix-safe"),
    _repo_case("repo.docs-lint.fix-index", "h2t-docs-lint fix-index"),
    _repo_case("repo.docs-lint.retire", "h2t-docs-lint retire"),
    _repo_case("repo.docs-lint.new", "h2t-docs-lint new"),
    _repo_case("repo.docs-index", "docs-index"),
    _repo_case("repo.milestone-closure", "h2t-milestone-closure"),
    _repo_case("repo.agent-profile", "h2t-agent-profile"),
    _repo_case("repo.plan-closer", "plan-closer"),
    _repo_case("repo.post-commit-docs-lint", "post-git-commit-docs-lint"),
    Case("repo.docs-lint.save", _in_repo(_docs_lint_save), setup=_in_repo(_plain_repo)),
    Case("repo.runbook", _in_repo(_runbook), setup=_in_repo(_plain_repo)),
    Case("repo.project-audit", _in_repo(_project_audit), setup=_in_repo(_project_audit_setup)),
    Case("agent-profile.catalog.dest", _in_repo(_agent_catalog), setup=_in_repo(_agent_catalog_setup)),
    Case("drawio.generate.dest", _in_repo(_drawio_generate)),
    Case("drawio.export.dest", _in_repo(_drawio_export), setup=_in_repo(_drawio_export_setup)),
    Case("creative.assemble.dest", _in_repo(_creative_assemble)),
    # Task 18: install state, snapshots and the plugin cache through store; hook logs in
    # logs; the gather lock in state/locks (R23); the deploy input through store.scratch().
    Case("setup.state.commit", _state_commit),
    Case("setup.sync.snapshot", _sync_snapshot, setup=_sync_tools),
    Case("setup.sync.clean-cache", _sync_clean_cache, setup=_sync_tools),
    Case("setup.machine-name", _machine_name),
    Case("setup.install-h2t-ops.versions", _install_versions_file, setup=_plugin_cache_dir),
    Case("hook.log-failure", _hook_log_failure),
    Case("hook.grade-guard.log", _guard_log("grade_guard"), setup=_guard_transcript),
    Case("hook.plain-guard.log", _guard_log("plain_guard"), setup=_guard_transcript),
    Case("hook.gather.lock", _gather_lock),
    Case("deploy.executor.input", _deploy_input, setup=_deploy_script),
    # Task 19: paths.yaml through store.replace(place="config") with a copy in state/backups;
    # the index rebuilt from the command line, under state/index.lock.
    Case("paths.set", _paths_set),
    Case("paths.set.repair", _paths_set_repair, setup=_broken_paths_yaml),
    Case("index.rebuild.cli", _cli("index", "rebuild", "--json"), setup=_index_records("sandbox")),
    # Task 24 (review K3): the layout 1 migration under the audit hook — outside the 46-module
    # baseline (it did not exist at Task 2), so test_sandbox_covers_every_writer cannot ask for it.
    # Its only 3.x writes are the MOVED-TO.txt markers, through store (§8).
    Case("setup.layout.migrate", _layout_migrate, setup=_layout_legacy_home,
         compat=(".dor/sessions/MOVED-TO.txt", ".dor/secrets/MOVED-TO.txt")),
]
