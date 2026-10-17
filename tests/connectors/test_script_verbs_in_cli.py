"""Every verb the plugin connector scripts offer has an `h2t-ops <connector> <verb>` (#541).

Task 12 deletes drive_cli.py, meetgeek_cli.py, exa_search.py and fetch_url.py. Before that
can happen, each verb they parse must exist in the package CLI and accept the same flags,
or deleting a script deletes a capability.

The verb list is not written here by hand: it is read from each script's own argparse
parser, so a verb added to a script is checked without anyone editing this file.
Three of the scripts expose a builder (`build_parser`, `_build_parser`). drive_cli.py builds
its parser inside main(), after an import check and before parse_args; that slice of main()
is lifted out with `ast` and executed alone, so no command ever runs.
"""
from __future__ import annotations

import argparse
import ast
import importlib.util
import json
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = ROOT / "plugins" / "h2t-ops" / "skills"

# script name -> (connector, path)
SCRIPTS = {
    "drive_cli": ("drive", SCRIPTS_DIR / "drive" / "scripts" / "drive_cli.py"),
    "meetgeek_cli": ("meetgeek", SCRIPTS_DIR / "meetgeek" / "scripts" / "meetgeek_cli.py"),
    "exa_search": ("research", SCRIPTS_DIR / "research" / "scripts" / "exa_search.py"),
    "fetch_url": ("research", SCRIPTS_DIR / "research" / "scripts" / "fetch_url.py"),
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


def _load_script(name: str):
    _, path = SCRIPTS[name]
    saved_path = list(sys.path)
    spec = importlib.util.spec_from_file_location(f"_t11_{name}", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    # fetch_url.py declares dataclasses, which look their module up in sys.modules.
    sys.modules[spec.name] = mod
    try:
        spec.loader.exec_module(mod)
    finally:
        # meetgeek_cli.py puts its own directory on sys.path to import recovery.py.
        sys.path[:] = saved_path
    return mod


def _drive_parser(mod) -> argparse.ArgumentParser:
    """Execute only the parser-building statements of drive_cli.main()."""
    tree = ast.parse(Path(mod.__file__).read_text(encoding="utf-8"))
    main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main")
    body, started = [], False
    for stmt in main.body:
        src = ast.unparse(stmt)
        if src.startswith("parser = argparse.ArgumentParser("):
            started = True
        if src.startswith("args = parser.parse_args("):
            break
        if started:
            body.append(stmt)
    assert body, "drive_cli.main() no longer builds `parser` before `parse_args`"
    body.append(ast.parse("return parser").body[0])
    fn = ast.FunctionDef(name="_t11_build", args=ast.arguments(
        posonlyargs=[], args=[], kwonlyargs=[], kw_defaults=[], defaults=[]),
        body=body, decorator_list=[], returns=None, type_params=[])
    module = ast.fix_missing_locations(ast.Module(body=[fn], type_ignores=[]))
    namespace = dict(vars(mod))
    exec(compile(module, str(mod.__file__), "exec"), namespace)  # noqa: S102 — parser slice only
    return namespace["_t11_build"]()


def _script_parser(name: str) -> argparse.ArgumentParser:
    mod = _load_script(name)
    if name == "drive_cli":
        return _drive_parser(mod)
    if name == "meetgeek_cli":
        return mod.build_parser()
    return mod._build_parser()


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
    return [(name, verb) for name in SCRIPTS for verb in _subcommands(_script_parser(name))]


def _cli_verb(connector: str, verb: str) -> argparse.ArgumentParser | None:
    from h2t_ops.cli import build_parser

    conn = _subcommands(build_parser()).get(connector)
    return _subcommands(conn).get(verb) if conn is not None else None


def _mismatches(script_p: argparse.ArgumentParser, cli_p: argparse.ArgumentParser) -> list[str]:
    problems = []
    cli_opts = _options(cli_p)
    for opt, sa in _options(script_p).items():
        ca = cli_opts.get(opt)
        if ca is None:
            problems.append(f"missing flag {opt}")
            continue
        if (sa.nargs == 0) != (ca.nargs == 0):
            problems.append(f"{opt}: takes a value in one and not the other")
        if sa.type in (int, float) and ca.type is not sa.type:
            problems.append(f"{opt}: type {sa.type.__name__} vs {getattr(ca.type, '__name__', ca.type)}")
        if sa.choices and ca.choices is not None and not set(sa.choices) <= set(ca.choices):
            problems.append(f"{opt}: choices {sorted(set(sa.choices) - set(ca.choices))} refused")
    script_pos, cli_pos = _positionals(script_p), _positionals(cli_p)
    for i, sa in enumerate(script_pos):
        if i >= len(cli_pos):
            problems.append(f"missing positional {sa.dest}")
        elif sa.nargs == "?" and cli_pos[i].nargs != "?":
            problems.append(f"positional {sa.dest} is optional in the script, required in the CLI")
    return problems


def test_scripts_still_offer_verbs():
    """Positive control: an empty inventory would make the next test pass vacuously."""
    verbs = _script_verbs()
    assert ("drive_cli", "list") in verbs
    assert ("meetgeek_cli", "sync") in verbs
    assert ("exa_search", "search") in verbs
    assert ("fetch_url", "fetch") in verbs
    assert set(EXCLUDED) <= set(verbs), "an exclusion names a verb that no longer exists"


def test_every_script_verb_has_a_cli_command_with_its_flags():
    red = []
    for name, verb in _script_verbs():
        if (name, verb) in EXCLUDED:
            continue
        connector = SCRIPTS[name][0]
        cli_verb = CLI_FORM.get((name, verb), (verb, []))[0]
        cli_p = _cli_verb(connector, cli_verb)
        if cli_p is None:
            red.append(f"{name} {verb}: no `h2t-ops {connector} {cli_verb}`")
            continue
        script_p = _subcommands(_script_parser(name))[verb]
        red += [f"{name} {verb}: {p}" for p in _mismatches(script_p, cli_p)]
    assert not red, "\n".join(red)


def test_cli_forms_parse():
    from h2t_ops.cli import build_parser

    for (name, _verb), (cli_verb, extra) in CLI_FORM.items():
        build_parser().parse_args([SCRIPTS[name][0], cli_verb, *extra])


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


# ─── Contract scenarios: same inputs to the script and to the CLI, on a fake API ─────────

def _cli(capsys, argv: list[str]) -> tuple[int, Any]:
    from h2t_ops import cli

    capsys.readouterr()
    code = cli.dispatch(argv)
    out = capsys.readouterr().out
    return code, (json.loads(out)["result"] if "--json" in argv and out.strip() else out)


def _script(capsys, mod, argv: list[str] | None) -> tuple[int, str]:
    """argv None: drive_cli.main() takes none and reads sys.argv."""
    capsys.readouterr()
    try:
        code = mod.main() if argv is None else mod.main(argv)
    except SystemExit as e:  # exa_search exits on failure, drive_cli on everything
        code = e.code
    return code or 0, capsys.readouterr().out


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
def meetgeek_script(fake_meetgeek, monkeypatch, tmp_path):
    monkeypatch.setenv("H2T_LAKE_ROOT", str(tmp_path / "lake"))
    return _load_script("meetgeek_cli")  # reads MEETGEEK_* at import


@pytest.mark.parametrize("verb", ["transcript", "summary", "highlights", "insights"])
def test_meetgeek_json_payloads_match(meetgeek_script, capsys, verb):
    code, out = _script(capsys, meetgeek_script, [verb, "m1", "--format", "json"])
    assert code == 0
    cli_code, result = _cli(capsys, ["meetgeek", verb, "m1", "--format", "json", "--json"])
    assert cli_code == 0
    assert result == json.loads(out)


def test_meetgeek_output_flag_writes_the_same_file(meetgeek_script, capsys, tmp_path):
    a, b = tmp_path / "script" / "t.json", tmp_path / "cli" / "t.json"
    code, out = _script(capsys, meetgeek_script, ["transcript", "m1", "--format", "json", "-o", str(a)])
    assert (code, out.strip()) == (0, str(a))
    cli_code, result = _cli(capsys, ["meetgeek", "transcript", "m1", "--format", "json",
                                     "-o", str(b), "--json"])
    assert (cli_code, result) == (0, str(b))
    assert a.read_text(encoding="utf-8") == b.read_text(encoding="utf-8")


def test_meetgeek_download_url_and_file(meetgeek_script, capsys, fake_meetgeek, tmp_path):
    code, out = _script(capsys, meetgeek_script, ["download", "m1"])
    assert (code, out.strip()) == (0, MG_MEDIA_URL)
    assert _cli(capsys, ["meetgeek", "download", "m1", "--json"]) == (0, MG_MEDIA_URL)

    a, b = tmp_path / "a.mp4", tmp_path / "b.mp4"
    assert _script(capsys, meetgeek_script, ["download", "m1", "-o", str(a)])[0] == 0
    assert _cli(capsys, ["meetgeek", "download", "m1", "-o", str(b), "--json"]) == (0, str(b))
    assert a.read_bytes() == b.read_bytes() == b"RECORDING-BYTES"
    # A signed media URL carries its own token: neither side sends the API key to it.
    assert all("Authorization" not in h for h in fake_meetgeek)


def _without_fetched_at(text: str) -> str:
    return "\n".join(ln for ln in text.splitlines() if not ln.startswith("fetched_at:"))


def test_meetgeek_sync_writes_the_same_lake(meetgeek_script, capsys, tmp_path):
    include = "transcripts,summaries,highlights,insights,recordings"
    lake_s, lake_c = tmp_path / "lake-script", tmp_path / "lake-cli"
    cur_s, cur_c = tmp_path / "cursor-script.json", tmp_path / "cursor-cli.json"
    code, out = _script(capsys, meetgeek_script, [
        "sync", "--to", str(lake_s), "--include", include, "--cursor-file", str(cur_s)])
    assert code == 0, out
    cli_code, result = _cli(capsys, ["meetgeek", "sync", "--to", str(lake_c), "--include", include,
                                     "--cursor-file", str(cur_c), "--json"])
    assert cli_code == 0
    assert out.strip() == (f"synced={result['synced']} skipped={result['skipped']} "
                           f"errors={result['errors']} cursor={cur_s}")

    files_s = sorted(p.relative_to(lake_s) for p in lake_s.rglob("*") if p.is_file())
    files_c = sorted(p.relative_to(lake_c) for p in lake_c.rglob("*") if p.is_file())
    assert files_s == files_c and len(files_s) == 2 * 9 + 1  # 4 pairs + recording, + manifest
    for rel in files_s:
        s_bytes, c_bytes = (lake_s / rel).read_bytes(), (lake_c / rel).read_bytes()
        if rel.suffix == ".md":
            assert _without_fetched_at(s_bytes.decode()) == _without_fetched_at(c_bytes.decode()), rel
        else:
            assert s_bytes == c_bytes, rel

    def cursor(p):
        data = json.loads(p.read_text(encoding="utf-8"))
        data.pop("last_run_at")
        return data
    assert cursor(cur_s) == cursor(cur_c)


def test_meetgeek_upload_download_url_delegates_identically(meetgeek_script, capsys, monkeypatch):
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return SimpleNamespace(returncode=0, stderr="", stdout=json.dumps(
            {"ok": True, "provider": "meetgeek", "result": {"message": "Processing"}}))

    monkeypatch.setenv("H2T_OPS", "h2t-ops-under-test")
    monkeypatch.setattr(subprocess, "run", fake_run)
    argv = ["upload", "--download-url", "https://example.org/r.mp4", "--title", "T", "--language", "ru"]
    code, out = _script(capsys, meetgeek_script, argv)
    assert code == 0
    assert _cli(capsys, ["meetgeek", *argv, "--json"]) == (0, json.loads(out))
    assert calls[0] == calls[1]


def test_meetgeek_upload_dry_run_matches(meetgeek_script, capsys, tmp_path):
    rec_dir = tmp_path / "recordings"
    rec_dir.mkdir()
    (rec_dir / "meetgeek-recording-2026-10-01T10-00-00-1Z.webm").write_bytes(b"webm")
    argv = ["upload", "--from-file", str(rec_dir), "--dry-run"]
    code, out = _script(capsys, meetgeek_script, argv)
    assert code == 0
    assert _cli(capsys, ["meetgeek", *argv, "--json"]) == (0, json.loads(out))


def test_meetgeek_staging_purge_and_drive_audit_match(meetgeek_script, capsys, monkeypatch):
    from h2t_ops.connectors.meetgeek import recovery as pkg_recovery

    argv = ["staging-purge", "--dry-run", "--no-verify-drive", "--min-age-hours", "0"]
    code, out = _script(capsys, meetgeek_script, argv)
    assert code == 0
    assert _cli(capsys, ["meetgeek", *argv, "--json"]) == (0, json.loads(out))

    # drive-audit authenticates to Drive before reading the (empty) manifest.
    for mod in (sys.modules["recovery"], pkg_recovery):
        monkeypatch.setattr(mod, "drive_service", lambda: object())
    code, out = _script(capsys, meetgeek_script, ["drive-audit"])
    assert code == 0
    assert _cli(capsys, ["meetgeek", "drive-audit", "--json"]) == (0, json.loads(out))


def test_meetgeek_convert_probe_matches(meetgeek_script, capsys, monkeypatch, tmp_path):
    from h2t_ops.connectors.meetgeek import recovery as pkg_recovery

    src = tmp_path / "in.webm"
    src.write_bytes(b"webm")
    stderr = ("Input #0, matroska,webm, from 'in.webm':\n  Duration: 00:01:05.00\n"
              "  Stream #0:0: Video: vp8\n  Stream #0:1: Audio: opus\n")
    for mod in (sys.modules["recovery"], pkg_recovery):
        monkeypatch.setattr(mod, "ffmpeg_exe", lambda: "ffmpeg-under-test")
    monkeypatch.setattr(subprocess, "run",
                        lambda cmd, **kw: SimpleNamespace(returncode=1, stdout="", stderr=stderr))
    code, out = _script(capsys, meetgeek_script, ["convert", str(src), "--probe"])
    assert code == 0
    result = _cli(capsys, ["meetgeek", "convert", str(src), "--probe", "--json"])
    assert result == (0, json.loads(out))
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
    mod = _load_script("drive_cli")
    monkeypatch.setattr(mod, "get_drive_service", lambda: service)
    monkeypatch.setattr(sys, "argv", ["drive_cli.py", "list"])

    def fake_init(self):
        self.service = service
    monkeypatch.setattr(drive_client.DriveClient, "__init__", fake_init)

    code, out = _script(capsys, mod, None)
    assert code == 0
    cli_code, result = _cli(capsys, ["drive", "list", "--json"])
    assert cli_code == 0
    assert [r["name"] for r in result["rows"]] == ["Plan.docx", "Notes"]
    for row in result["rows"]:
        assert row["name"] in out and f"[{row['id'][:12]}...]" in out


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
    mod = _load_script("exa_search")
    monkeypatch.setattr(mod, "_h2t_secrets_bootstrap", lambda: None)
    monkeypatch.setattr(mod, "_emit_eval", lambda *a, **k: None)

    common = ["--query", "contract test", "--project", "t11"]
    code, out = _script(capsys, mod, ["search", *common, "--envelope",
                                      "--output-dir", str(tmp_path / "s")])
    assert code == 0
    script_env = json.loads(out)
    cli_code, result = _cli(capsys, ["research", "search", *common, "--envelope",
                                     "--output-dir", str(tmp_path / "c")])
    assert cli_code == 0, result
    result = json.loads(result)["result"]  # --envelope is --json: the CLI envelope wraps it
    assert result["status"] == script_env["status"] == "OK"
    assert result["results"] == script_env["results"]
    for key in ("query", "mode", "num_results_returned"):
        assert result["meta"][key] == script_env["meta"][key]


def test_research_fetch_matches(capsys, monkeypatch, tmp_path):
    html = (ROOT / "tests" / "connectors" / "research" / "fixtures" / "fetch"
            / "public_article.html").read_bytes()
    url = "https://example.com/pops-intro"
    monkeypatch.setattr(urllib.request, "urlopen",
                        lambda req, timeout=None: _urlopen_response(html, url=url))
    mod = _load_script("fetch_url")
    common = ["--url", url, "--provider", "direct", "--format", "text", "--project", "t11"]
    code, out = _script(capsys, mod, ["fetch", *common, "--json", "--output-dir", str(tmp_path / "s")])
    assert code == 0
    script_env = json.loads(out)
    cli_code, result = _cli(capsys, ["research", "fetch", *common, "--json",
                                     "--output-dir", str(tmp_path / "c")])
    assert cli_code == 0, result
    for key in ("status", "provider_used", "title", "body_markdown", "body_chars", "content_type"):
        assert result[key] == script_env[key], key


def test_research_preflight_jina_matches(capsys, monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=None: _urlopen_response(b""))
    mod = _load_script("fetch_url")
    assert _script(capsys, mod, ["preflight"])[0] == 0
    assert _cli(capsys, ["research", "preflight", "--provider", "jina", "--json"]) == (
        0, {"status": "OK", "provider": "jina"})

    def unreachable(req, timeout=None):
        raise urllib.error.URLError("no route")
    monkeypatch.setattr(urllib.request, "urlopen", unreachable)
    assert _script(capsys, mod, ["preflight"])[0] != 0
    assert _cli(capsys, ["research", "preflight", "--provider", "jina", "--json"])[0] == 6
