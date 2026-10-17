"""Every verb the plugin connector scripts offered has an `h2t-ops <connector> <verb>` (#541).

Task 12 deleted drive_cli.py, meetgeek_cli.py, exa_search.py and fetch_url.py. Each verb
they parsed had to exist in the package CLI with the same flags, or deleting a script
deleted a capability. While the scripts existed, this test read the verbs from their own
argparse parsers. Before they were deleted, that inventory was frozen into INVENTORY
below, generated from the parsers at d857c128, so the CLI still answers to it.

The contract scenarios ran the same input through the script and through the CLI on a fake
API. The script halves were recorded once, at the same commit, into
tests/fixtures/connectors/script_contract/goldens.json, and the CLI must still produce them.
A path under the scenario's tmp dir is recorded as `<tmp>`, today's date as `<today>`.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parents[2]
GOLDENS = json.loads((ROOT / "tests" / "fixtures" / "connectors" / "script_contract"
                      / "goldens.json").read_text(encoding="utf-8"))

# script name -> connector
CONNECTOR = {"drive_cli": "drive", "meetgeek_cli": "meetgeek", "exa_search": "research",
             "fetch_url": "research"}

# script -> verb -> (options, positionals). An option is flag -> (takes a value, int/float
# type or None, choices or None); a positional is (dest, optional).
INVENTORY: dict[str, dict[str, tuple[dict, list]]] = {
    "drive_cli": {
        "download": ({}, [("file_id", False), ("dest", True)]),
        "export": ({
            "--format": (True, None, None),
            "--print": (False, None, None),
        }, [("file_id", False), ("dest", True)]),
        "folders": ({}, [("parent", True)]),
        "list": ({
            "--max": (True, "int", None),
        }, [("folder", True)]),
        "search": ({
            "--max": (True, "int", None),
            "--type": (True, None, ("docx", "folder")),
        }, [("query", False)]),
        "sync-meetings": ({
            "--dry-run": (False, None, None),
            "--folder": (True, None, None),
        }, []),
        "upload": ({
            "--folder": (True, None, None),
            "--no-convert": (False, None, None),
        }, [("file", False)]),
    },
    "exa_search": {
        "crawl": ({
            "--output-dir": (True, None, None),
            "--project": (True, None, None),
            "--url": (True, None, None),
        }, []),
        "preflight": ({}, []),
        "search": ({
            "--additional-queries": (True, None, None),
            "--country": (True, None, None),
            "--depth": (True, None, ("deep", "shallow", "standard")),
            "--end-date": (True, None, None),
            "--envelope": (False, None, None),
            "--exclude-domains": (True, None, None),
            "--exclude-text": (True, None, None),
            "--full-text": (False, None, None),
            "--include-domains": (True, None, None),
            "--include-text": (True, None, None),
            "--mode": (
                True, None,
                ("academic", "competitor", "deep", "fast", "generic", "news", "people")),
            "--no-retry": (False, None, None),
            "--num-results": (True, "int", None),
            "--output-dir": (True, None, None),
            "--project": (True, None, None),
            "--query": (True, None, None),
            "--start-date": (True, None, None),
        }, []),
    },
    "fetch_url": {
        "fetch": ({
            "--config": (True, None, None),
            "--format": (True, None, ("html", "markdown", "text")),
            "--json": (False, None, None),
            "--keep-raw": (False, None, None),
            "--min-body-chars": (True, "int", None),
            "--output-dir": (True, None, None),
            "--project": (True, None, None),
            "--provider": (
                True, None,
                ("auto", "browserless", "crawl4ai", "direct", "firecrawl", "jina", "playwright")),
            "--timeout-ms": (True, "int", None),
            "--url": (True, None, None),
            "--user-agent": (True, None, None),
        }, []),
        "preflight": ({}, []),
    },
    "meetgeek_cli": {
        "auth-check": ({}, []),
        "convert": ({
            "--audio-only": (False, None, None),
            "--mix-mode": (True, None, ("amix", "first", "keep")),
            "--output": (True, None, None),
            "--probe": (False, None, None),
            "-o": (True, None, None),
        }, [("input", False)]),
        "download": ({
            "--output": (True, None, None),
            "-o": (True, None, None),
        }, [("meeting_id", False)]),
        "drive-audit": ({
            "--min-age-hours": (True, "float", None),
            "--revoke": (False, None, None),
        }, []),
        "drive-upload": ({
            "--folder": (True, None, None),
            "--make-public": (False, None, None),
            "--no-make-public": (False, None, None),
        }, [("file", False)]),
        "get": ({}, [("meeting_id", False)]),
        "highlights": ({
            "--format": (True, None, ("json", "md")),
            "--output": (True, None, None),
            "-o": (True, None, None),
        }, [("meeting_id", False)]),
        "insights": ({
            "--format": (True, None, ("json", "md")),
            "--output": (True, None, None),
            "-o": (True, None, None),
        }, [("meeting_id", False)]),
        "list": ({
            "--cursor": (True, None, None),
            "--from-date": (True, None, None),
            "--limit": (True, "int", None),
            "--to-date": (True, None, None),
        }, []),
        "staging-purge": ({
            "--dry-run": (False, None, None),
            "--min-age-hours": (True, "float", None),
            "--no-verify-drive": (False, None, None),
            "--verify-drive": (False, None, None),
        }, []),
        "summary": ({
            "--format": (True, None, ("json", "md")),
            "--output": (True, None, None),
            "-o": (True, None, None),
        }, [("meeting_id", False)]),
        "sync": ({
            "--cursor-file": (True, None, None),
            "--include": (True, None, None),
            "--limit": (True, "int", None),
            "--since": (True, None, None),
            "--since-cursor": (False, None, None),
            "--to": (True, None, None),
            "--to-date": (True, None, None),
            "--watch": (True, "int", None),
        }, []),
        "teams": ({}, []),
        "transcript": ({
            "--format": (True, None, ("json", "md")),
            "--output": (True, None, None),
            "-o": (True, None, None),
        }, [("meeting_id", False)]),
        "upload": ({
            "--audio-only": (False, None, None),
            "--download-url": (True, None, None),
            "--dry-run": (False, None, None),
            "--from-file": (True, None, None),
            "--housekeeping": (False, None, None),
            "--language": (True, None, None),
            "--mix-mode": (True, None, ("amix", "first", "keep")),
            "--no-housekeeping": (False, None, None),
            "--no-skip-existing": (False, None, None),
            "--skip-existing": (False, None, None),
            "--title": (True, None, None),
        }, []),
        "webhook-server": ({
            "--bind": (True, None, None),
            "--out": (True, None, None),
            "--port": (True, "int", None),
            "--secret": (True, None, None),
        }, []),
    },
}


# Verbs deliberately not carried into h2t-ops, each with the reason.
EXCLUDED = {
    ("drive_cli", "sync-meetings"): (
        "retired compatibility stub: it prints a pointer to `h2t-ops drive export` / "
        "`h2t-ops meetgeek` and exits 2 whatever it is given; there is no capability to carry"
    ),
}

# A script verb whose CLI form carries a fixed extra argument. fetch_url.py and
# exa_search.py both call their connectivity probe `preflight` and both land in the
# research connector; fetch_url's probes Jina, exa_search's probes Exa.
CLI_FORM = {
    ("fetch_url", "preflight"): ("preflight", ["--provider", "jina"]),
}


def _subcommands(parser: argparse.ArgumentParser) -> dict[str, argparse.ArgumentParser]:
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return dict(action.choices)
    return {}


def _options(parser: argparse.ArgumentParser) -> dict[str, argparse.Action]:
    return {
        opt: action
        for action in parser._actions
        if not isinstance(action, (argparse._HelpAction, argparse._VersionAction))
        for opt in action.option_strings
    }


def _positionals(parser: argparse.ArgumentParser) -> list[argparse.Action]:
    return [a for a in parser._actions
            if not a.option_strings and not isinstance(a, argparse._SubParsersAction)]


def _script_verbs() -> list[tuple[str, str]]:
    return [(name, verb) for name, verbs in INVENTORY.items() for verb in verbs]


def _cli_verb(connector: str, verb: str) -> argparse.ArgumentParser | None:
    from h2t_ops.cli import build_parser

    conn = _subcommands(build_parser()).get(connector)
    return _subcommands(conn).get(verb) if conn is not None else None


def _mismatches(script: tuple[dict, list], cli_p: argparse.ArgumentParser) -> list[str]:
    options, positionals = script
    problems = []
    cli_opts = _options(cli_p)
    for opt, (takes_value, type_name, choices) in options.items():
        ca = cli_opts.get(opt)
        if ca is None:
            problems.append(f"missing flag {opt}")
            continue
        if takes_value != (ca.nargs != 0):
            problems.append(f"{opt}: takes a value in one and not the other")
        if type_name and getattr(ca.type, "__name__", None) != type_name:
            problems.append(f"{opt}: type {type_name} vs {getattr(ca.type, '__name__', ca.type)}")
        if choices and ca.choices is not None and not set(choices) <= set(ca.choices):
            problems.append(f"{opt}: choices {sorted(set(choices) - set(ca.choices))} refused")
    cli_pos = _positionals(cli_p)
    for i, (dest, optional) in enumerate(positionals):
        if i >= len(cli_pos):
            problems.append(f"missing positional {dest}")
        elif optional and cli_pos[i].nargs != "?":
            problems.append(f"positional {dest} is optional in the script, required in the CLI")
    return problems


def test_the_inventory_is_not_empty():
    """Positive control: an empty inventory would make the next test pass vacuously."""
    verbs = _script_verbs()
    assert ("drive_cli", "list") in verbs
    assert ("meetgeek_cli", "sync") in verbs
    assert ("exa_search", "search") in verbs
    assert ("fetch_url", "fetch") in verbs
    assert set(EXCLUDED) <= set(verbs), "an exclusion names a verb that is not in the inventory"


def test_every_script_verb_has_a_cli_command_with_its_flags():
    red = []
    for name, verb in _script_verbs():
        if (name, verb) in EXCLUDED:
            continue
        connector = CONNECTOR[name]
        cli_verb = CLI_FORM.get((name, verb), (verb, []))[0]
        cli_p = _cli_verb(connector, cli_verb)
        if cli_p is None:
            red.append(f"{name} {verb}: no `h2t-ops {connector} {cli_verb}`")
            continue
        red += [f"{name} {verb}: {p}" for p in _mismatches(INVENTORY[name][verb], cli_p)]
    assert not red, "\n".join(red)


def test_the_comparison_reports_a_missing_flag():
    """Control for _mismatches: a flag the CLI lacks must be named, not passed over."""
    cli_p = _cli_verb("research", "fetch")
    assert _mismatches(({"--no-such-flag": (False, None, None)}, []), cli_p) == [
        "missing flag --no-such-flag"]


def test_cli_forms_parse():
    from h2t_ops.cli import build_parser

    for (name, _verb), (cli_verb, extra) in CLI_FORM.items():
        build_parser().parse_args([CONNECTOR[name], cli_verb, *extra])


@pytest.mark.parametrize("argv", [
    ["drive", "download", "FILE", "out.bin"],
    ["drive", "export", "FILE", "out.txt", "--format", "text"],
    ["meetgeek", "transcript", "M1", "--format", "json", "-o", "t.json"],
    ["meetgeek", "upload", "--download-url", "https://example.com/a.mp4", "--no-housekeeping"],
    ["meetgeek", "drive-upload", "a.mp4", "--no-make-public"],
    ["meetgeek", "staging-purge", "--no-verify-drive", "--dry-run"],
    ["research", "search", "--query", "q", "--project", "p", "--envelope", "--depth", "deep"],
    ["research", "fetch", "--url", "https://example.com", "--format", "text", "--json"],
])
def test_script_style_invocations_parse(argv):
    """The flag check reads the parsers; this feeds them a script's actual argv."""
    from h2t_ops.cli import build_parser

    build_parser().parse_args(argv)


def test_pipeline_parser_repeats_the_recovery_grace_period():
    """commands.py repeats HOUSEKEEPING_MIN_AGE_HOURS so building the parser imports nothing."""
    from h2t_ops.connectors.meetgeek import commands, pipeline, recovery

    assert set(pipeline.VERBS) == commands.PIPELINE_VERBS
    staging = _cli_verb("meetgeek", "staging-purge")
    assert _options(staging)["--min-age-hours"].default == recovery.HOUSEKEEPING_MIN_AGE_HOURS


# ─── Contract scenarios: the CLI against the script's recorded output, on a fake API ─────

def _cli(capsys, argv: list[str]) -> tuple[int, Any]:
    from h2t_ops import cli

    capsys.readouterr()
    code = cli.dispatch(argv)
    out = capsys.readouterr().out
    return code, (json.loads(out)["result"] if "--json" in argv and out.strip() else out)


def _recorded(value: Any, tmp_path: Path) -> Any:
    """A golden with its placeholders filled in for this run."""
    text = json.dumps(value, ensure_ascii=False)
    text = text.replace("<tmp>", json.dumps(str(tmp_path))[1:-1])
    return json.loads(text.replace("<today>", datetime.now(UTC).strftime("%Y-%m-%d")))


# MeetGeek ────────────────────────────────────────────────────────────────────────────

MG_BASE = "https://api.meetgeek.test"
MG_MEETINGS = [
    {"id": "m1", "title": "Weekly sync", "timestamp_start_utc": "2026-10-01T10:00:00Z",
     "timestamp_end_utc": "2026-10-01T10:30:00Z", "language": "en",
     "participants": [{"name": "Ann"}, {"email": "bob@example.org"}]},
    {"id": "m2", "title": "Retro", "timestamp_start_utc": "2026-10-02T12:00:00Z"},
]
MG_MEDIA_URL = "https://media.meetgeek.example/rec.mp4?token=signed"


class _MgResp:
    def __init__(self, status: int, payload: Any = None, body: bytes = b""):
        self.status_code = status
        self._payload = payload
        self.headers: dict[str, str] = {}
        self.text = json.dumps(payload) if payload is not None else ""
        self._body = body

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload

    def iter_content(self, chunk_size: int):
        yield self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


@pytest.fixture
def fake_meetgeek(monkeypatch):
    """One fake MeetGeek API behind requests.request/get, for the script and the client."""
    import requests

    monkeypatch.setenv("MEETGEEK_API_KEY", "fake-key-for-tests")
    monkeypatch.setenv("MEETGEEK_BASE_URL", MG_BASE)
    by_id = {m["id"]: m for m in MG_MEETINGS}
    media_headers: list[dict] = []

    def request(method, url, headers=None, params=None, json=None, timeout=None):
        path = url.removeprefix(MG_BASE)
        parts = path.strip("/").split("/")
        if method == "GET" and path == "/v1/meetings":
            return _MgResp(200, {"meetings": MG_MEETINGS, "pagination": {"next_cursor": None}})
        if method == "GET" and parts[:2] == ["v1", "meeting"]:
            return _MgResp(200, by_id[parts[2]])
        if parts[:2] == ["v1", "meetings"] and len(parts) == 4:
            mid, leaf = parts[2], parts[3]
            if method == "POST" and leaf == "download":
                return _MgResp(200, {"download_link": MG_MEDIA_URL})
            payloads = {
                "transcript": {"language": "en", "sentences": [
                    {"speaker": "Ann", "timestamp": 5, "transcript": f"hello from {mid}"},
                    {"speaker": "Bob", "timestamp": 65, "transcript": "привет"},
                ]},
                "summary": {"summary": f"summary of {mid}",
                            "action_items": [{"owner": "Ann", "text": "ship it"}]},
                "highlights": {"highlights": [{"text": "key moment", "timestamp": "00:01"}]},
                "insights": {"topics": ["release"]},
            }
            return _MgResp(200, payloads[leaf])
        return _MgResp(404, {"error": path})

    def get(url, headers=None, stream=False, timeout=None):
        media_headers.append(dict(headers or {}))
        return _MgResp(200, body=b"RECORDING-BYTES")

    monkeypatch.setattr(requests, "request", request)
    monkeypatch.setattr(requests, "get", get)
    return media_headers


@pytest.fixture
def meetgeek_env(fake_meetgeek, monkeypatch, tmp_path):
    monkeypatch.setenv("H2T_LAKE_ROOT", str(tmp_path / "lake"))
    return fake_meetgeek


@pytest.mark.parametrize("verb", ["transcript", "summary", "highlights", "insights"])
def test_meetgeek_json_payloads_match(meetgeek_env, capsys, verb):
    cli_code, result = _cli(capsys, ["meetgeek", verb, "m1", "--format", "json", "--json"])
    assert cli_code == 0
    assert result == GOLDENS["meetgeek_payloads"][verb]


def test_meetgeek_output_flag_writes_the_same_file(meetgeek_env, capsys, tmp_path):
    b = tmp_path / "cli" / "t.json"
    cli_code, result = _cli(capsys, ["meetgeek", "transcript", "m1", "--format", "json",
                                     "-o", str(b), "--json"])
    assert (cli_code, result) == (0, str(b))
    assert b.read_text(encoding="utf-8") == GOLDENS["meetgeek_output_file"]


def test_meetgeek_download_url_and_file(meetgeek_env, capsys, tmp_path):
    assert _cli(capsys, ["meetgeek", "download", "m1", "--json"]) == (0, MG_MEDIA_URL)

    b = tmp_path / "b.mp4"
    assert _cli(capsys, ["meetgeek", "download", "m1", "-o", str(b), "--json"]) == (0, str(b))
    assert b.read_bytes() == b"RECORDING-BYTES"
    # A signed media URL carries its own token: the API key is not sent to it.
    assert all("Authorization" not in h for h in meetgeek_env)


def _without_fetched_at(text: str) -> str:
    return "\n".join(ln for ln in text.splitlines() if not ln.startswith("fetched_at:"))


def test_meetgeek_sync_writes_the_same_lake(meetgeek_env, capsys, tmp_path):
    include = "transcripts,summaries,highlights,insights,recordings"
    lake, cursor_file = tmp_path / "lake-cli", tmp_path / "cursor.json"
    cli_code, result = _cli(capsys, ["meetgeek", "sync", "--to", str(lake), "--include", include,
                                     "--cursor-file", str(cursor_file), "--json"])
    assert cli_code == 0
    golden = GOLDENS["meetgeek_sync"]
    # The script's stdout line, rebuilt from the CLI's result.
    assert (f"synced={result['synced']} skipped={result['skipped']} errors={result['errors']} "
            f"cursor=<tmp>/cursor.json") == golden["stdout"]

    files = {p.relative_to(lake).as_posix(): p for p in sorted(lake.rglob("*")) if p.is_file()}
    assert sorted(files) == sorted(golden["files"])
    assert len(files) == 2 * 9 + 1  # 4 pairs + recording per meeting, + manifest
    for rel, path in files.items():
        want = golden["files"][rel]
        if "md" in want:
            assert _without_fetched_at(path.read_text(encoding="utf-8")) == want["md"], rel
        else:
            assert path.read_text(encoding="utf-8") == want["text"], rel

    cursor = json.loads(cursor_file.read_text(encoding="utf-8"))
    cursor.pop("last_run_at")
    assert cursor == golden["cursor"]


def test_meetgeek_upload_download_url_delegates_identically(meetgeek_env, capsys, monkeypatch):
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return SimpleNamespace(returncode=0, stderr="", stdout=json.dumps(
            {"ok": True, "provider": "meetgeek", "result": {"message": "Processing"}}))

    monkeypatch.setenv("H2T_OPS", "h2t-ops-under-test")
    monkeypatch.setattr(subprocess, "run", fake_run)
    argv = ["upload", "--download-url", "https://example.org/r.mp4", "--title", "T", "--language", "ru"]
    golden = GOLDENS["meetgeek_upload_delegate"]
    assert _cli(capsys, ["meetgeek", *argv, "--json"]) == (0, golden["stdout"])
    assert calls == [golden["argv"]]


def test_meetgeek_upload_dry_run_matches(meetgeek_env, capsys, tmp_path):
    rec_dir = tmp_path / "recordings"
    rec_dir.mkdir()
    (rec_dir / "meetgeek-recording-2026-10-01T10-00-00-1Z.webm").write_bytes(b"webm")
    argv = ["upload", "--from-file", str(rec_dir), "--dry-run"]
    assert _cli(capsys, ["meetgeek", *argv, "--json"]) == (
        0, _recorded(GOLDENS["meetgeek_upload_dry_run"], tmp_path))


def test_meetgeek_staging_purge_and_drive_audit_match(meetgeek_env, capsys, monkeypatch, tmp_path):
    from h2t_ops.connectors.meetgeek import recovery as pkg_recovery

    argv = ["staging-purge", "--dry-run", "--no-verify-drive", "--min-age-hours", "0"]
    assert _cli(capsys, ["meetgeek", *argv, "--json"]) == (
        0, _recorded(GOLDENS["meetgeek_staging_purge"], tmp_path))

    # drive-audit authenticates to Drive before reading the (empty) manifest.
    monkeypatch.setattr(pkg_recovery, "drive_service", lambda: object())
    assert _cli(capsys, ["meetgeek", "drive-audit", "--json"]) == (
        0, _recorded(GOLDENS["meetgeek_drive_audit"], tmp_path))


def test_meetgeek_convert_probe_matches(meetgeek_env, capsys, monkeypatch, tmp_path):
    from h2t_ops.connectors.meetgeek import recovery as pkg_recovery

    src = tmp_path / "in.webm"
    src.write_bytes(b"webm")
    stderr = ("Input #0, matroska,webm, from 'in.webm':\n  Duration: 00:01:05.00\n"
              "  Stream #0:0: Video: vp8\n  Stream #0:1: Audio: opus\n")
    monkeypatch.setattr(pkg_recovery, "ffmpeg_exe", lambda: "ffmpeg-under-test")
    monkeypatch.setattr(subprocess, "run",
                        lambda cmd, **kw: SimpleNamespace(returncode=1, stdout="", stderr=stderr))
    result = _cli(capsys, ["meetgeek", "convert", str(src), "--probe", "--json"])
    assert result == (0, _recorded(GOLDENS["meetgeek_convert_probe"], tmp_path))
    assert result[1]["duration_seconds"] == 65


# Drive ───────────────────────────────────────────────────────────────────────────────

class _DriveFiles:
    def __init__(self, files):
        self._files = files

    def list(self, **kwargs):
        return SimpleNamespace(execute=lambda: {"files": self._files})


def test_drive_list_shows_the_same_files(capsys, monkeypatch):
    from h2t_ops.connectors.drive import client as drive_client

    files = [
        {"id": "1AbCdEfGhIjKlMn", "name": "Plan.docx", "mimeType": "application/vnd.openxml",
         "modifiedTime": "2026-10-01T00:00:00Z"},
        {"id": "2ZyXwVuTsRqPoNm", "name": "Notes", "mimeType": "application/vnd.google-apps.document",
         "modifiedTime": "2026-09-30T00:00:00Z"},
    ]
    service = SimpleNamespace(files=lambda: _DriveFiles(files))

    def fake_init(self):
        self.service = service
    monkeypatch.setattr(drive_client.DriveClient, "__init__", fake_init)

    cli_code, result = _cli(capsys, ["drive", "list", "--json"])
    assert cli_code == 0
    assert [r["name"] for r in result["rows"]] == ["Plan.docx", "Notes"]
    script_out = GOLDENS["drive_list_stdout"]
    for row in result["rows"]:
        assert row["name"] in script_out and f"[{row['id'][:12]}...]" in script_out


# Research ────────────────────────────────────────────────────────────────────────────

def _urlopen_response(body: bytes, *, status: int = 200, url: str = "",
                      headers: dict[str, str] | None = None):
    resp = MagicMock()
    resp.read.return_value = body
    resp.status = status
    resp.headers = headers or {"Content-Type": "text/html; charset=utf-8"}
    resp.geturl.return_value = url
    resp.__enter__ = lambda self_: self_
    resp.__exit__ = lambda self_, *a: None
    return resp


def test_research_search_envelope_matches(capsys, monkeypatch, tmp_path):
    payload = {"results": [{"title": "T", "url": "https://example.com/a", "highlights": ["h"]}],
               "costDollars": {"total": 0.007}}
    monkeypatch.setenv("EXA_API_KEY", "fake-exa-key-for-tests")
    monkeypatch.setattr(urllib.request, "urlopen",
                        lambda req, timeout=None: _urlopen_response(json.dumps(payload).encode()))

    common = ["--query", "contract test", "--project", "t11"]
    cli_code, result = _cli(capsys, ["research", "search", *common, "--envelope",
                                     "--output-dir", str(tmp_path / "c")])
    assert cli_code == 0, result
    result = json.loads(result)["result"]  # --envelope is --json: the CLI envelope wraps it
    golden = GOLDENS["research_search"]
    assert result["status"] == golden["status"] == "OK"
    assert result["results"] == golden["results"]
    for key in ("query", "mode", "num_results_returned"):
        assert result["meta"][key] == golden["meta"][key]


@pytest.mark.parametrize("newline", [b"\n", b"\r\n"], ids=["lf", "crlf"])
def test_research_fetch_matches(capsys, monkeypatch, tmp_path, newline):
    # The fixture is served with both line endings: Git for Windows checks it out as CRLF.
    html = (ROOT / "tests" / "connectors" / "research" / "fixtures" / "fetch"
            / "public_article.html").read_bytes().replace(b"\r\n", b"\n").replace(b"\n", newline)
    url = "https://example.com/pops-intro"
    monkeypatch.setattr(urllib.request, "urlopen",
                        lambda req, timeout=None: _urlopen_response(html, url=url))
    common = ["--url", url, "--provider", "direct", "--format", "text", "--project", "t11"]
    cli_code, result = _cli(capsys, ["research", "fetch", *common, "--json",
                                     "--output-dir", str(tmp_path / "c")])
    assert cli_code == 0, result
    for key, value in GOLDENS["research_fetch"].items():
        assert result[key] == value, key


def test_research_preflight_jina(capsys, monkeypatch):
    # The script's preflight exited 0 when Jina answered and non-zero when it did not.
    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=None: _urlopen_response(b""))
    assert _cli(capsys, ["research", "preflight", "--provider", "jina", "--json"]) == (
        0, {"status": "OK", "provider": "jina"})

    def unreachable(req, timeout=None):
        raise urllib.error.URLError("no route")
    monkeypatch.setattr(urllib.request, "urlopen", unreachable)
    assert _cli(capsys, ["research", "preflight", "--provider", "jina", "--json"])[0] == 6
