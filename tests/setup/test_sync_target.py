"""`h2t-setup`: the target release and the executor that serves it (spec §7.3.1–2, §7.4)."""
from __future__ import annotations

import http.client
import json
import os
import urllib.error

import pytest

import h2t_ops
from h2t_ops.core.errors import ConfigError, NetworkError, exit_code_for
from h2t_ops.setup import cli, manifest, state, sync

REF = "v4.1.0"
BOOT = ["uvx", "--isolated", "--python", "3.12.11", "--managed-python", "-c",
        "https://example.invalid/constraints.txt", "--from",
        "h2t-ops @ https://example.invalid/h2t_ops-4.1.0-py3-none-any.whl", "h2t-setup"]
RELEASE = {"format": 1, "version": "4.1.0", "previous": "4.0.0", "python": "3.12.11",
           "wheel": "https://example.invalid/h2t_ops-4.1.0-py3-none-any.whl",
           "constraints": "https://example.invalid/constraints.txt", "bootstrap": BOOT}


def _marketplace(source) -> bytes:
    return json.dumps({"name": "lichtpfad", "plugins": [
        {"name": "h2t-ops", "source": source}, {"name": "h2t-core", "source": source},
    ]}).encode()


def _pinned(ref=REF, url="https://github.com/lichtpfad/h2t-skills.git"):
    return {"source": "git-subdir", "url": url, "path": "plugins/h2t-core",
            "ref": ref, "sha": "0" * 40}


# The real one, before the autouse fixture below replaces it for every test.
_REAL_UV_TOOL_ROOT = sync.uv_tool_root


def _fetcher(pages: dict[str, bytes]):
    def fetch(url: str) -> bytes:
        if url not in pages:
            raise AssertionError(f"unexpected fetch {url}")
        return pages[url]
    return fetch


def _pages(release=RELEASE, source=None) -> dict[str, bytes]:
    return {manifest.MARKETPLACE_URL: _marketplace(source or _pinned()),
            manifest.release_url(REF): json.dumps(release).encode()}


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    # setenv first: delenv of an absent name records nothing, so the relaunch marker an
    # ensure_executor call sets would outlive the test.
    monkeypatch.setenv(sync.RELAUNCH_ENV, "")
    monkeypatch.delenv(sync.RELAUNCH_ENV)
    # This machine's own `uv tool dir` holds a real h2t-ops (editable, here): no test may
    # read it by accident. A test that wants a tool directory injects one.
    monkeypatch.setattr(sync, "uv_tool_root", lambda **k: None)
    return tmp_path


# --- the target ---------------------------------------------------------------------------

def test_the_target_is_the_release_json_of_the_h2t_core_ref():
    target = manifest.current(fetch=_fetcher(_pages()))
    assert target["version"] == "4.1.0"
    assert target["bootstrap"] == BOOT
    assert target["ref"] == REF
    assert manifest.release_url(REF) == (
        "https://raw.githubusercontent.com/lichtpfad/h2t-skills/v4.1.0/release.json")


def test_a_relative_source_is_not_a_release_pointer():
    pages = {manifest.MARKETPLACE_URL: _marketplace("./plugins/h2t-core")}
    with pytest.raises(ConfigError) as exc:
        manifest.current(fetch=_fetcher(pages))
    assert exc.value.hint


def test_a_shorthand_url_is_refused_because_it_goes_to_ssh():
    pages = {manifest.MARKETPLACE_URL: _marketplace(_pinned(url="lichtpfad/h2t-skills"))}
    with pytest.raises(ConfigError):
        manifest.current(fetch=_fetcher(pages))


def test_an_unknown_format_names_a_newer_h2t_setup_and_its_bootstrap():
    newer = {"format": 2, "version": "9.0.0", "bootstrap": ["uvx", "--isolated", "h2t-setup"]}
    with pytest.raises(ConfigError) as exc:
        manifest.current(fetch=_fetcher(_pages(release=newer)))
    assert "newer h2t-setup" in str(exc.value)
    assert "uvx --isolated h2t-setup sync" in exc.value.hint


def test_a_missing_field_is_a_config_error():
    broken = {k: v for k, v in RELEASE.items() if k != "wheel"}
    with pytest.raises(ConfigError, match="wheel"):
        manifest.current(fetch=_fetcher(_pages(release=broken)))


def _assert_nothing_on_disk(home):
    assert state.read() is None
    assert not (home / ".h2t").exists()


def test_a_network_failure_is_code_6_and_touches_nothing(home):
    def down(url):
        raise urllib.error.URLError("no route to host")
    with pytest.raises(NetworkError) as exc:
        manifest.current(fetch=down)
    assert exit_code_for(exc.value) == 6
    assert "no route to host" in str(exc.value)
    _assert_nothing_on_disk(home)


def test_the_default_fetch_turns_urllib_failures_into_network_errors(monkeypatch):
    def down(url, timeout=None):
        assert timeout, "the default fetch must carry a timeout"
        raise TimeoutError("timed out")
    monkeypatch.setattr("urllib.request.urlopen", down)
    with pytest.raises(NetworkError, match="timed out"):
        manifest.urllib_fetch(manifest.MARKETPLACE_URL)


def test_the_cli_reports_a_network_failure_as_6_and_writes_nothing(home, monkeypatch, capsys):
    def down(url):
        raise NetworkError("offline")
    monkeypatch.setattr(manifest, "urllib_fetch", down)
    assert cli.main(["sync", "--json"]) == 6
    err = json.loads(capsys.readouterr().err)
    assert err["ok"] is False and err["error"]["type"] == "network"
    _assert_nothing_on_disk(home)


# --- the executor -------------------------------------------------------------------------

class Exec:
    def __init__(self):
        self.calls = []

    def __call__(self, file, args):
        self.calls.append((file, args))
        raise SystemExit("execvp")  # the real one never returns


def _target(version="4.1.0"):
    return dict(RELEASE, version=version, ref=REF)


def test_an_older_executor_relaunches_the_target_bootstrap_with_mode_and_argv(tmp_path):
    ex = Exec()
    with pytest.raises(SystemExit):
        sync.ensure_executor(_target(), "update", ["--json"], prefix=str(tmp_path / "uvx"),
                             version="4.0.0", tool_root=None, execvp=ex, os_name="posix")
    assert ex.calls == [("uvx", BOOT + ["update", "--json"])]
    assert os.environ[sync.RELAUNCH_ENV] == "4.1.0"


def test_the_target_version_inside_the_installed_tool_still_relaunches(tmp_path):
    tool_root = tmp_path / "tools" / "h2t-ops"
    tool_root.mkdir(parents=True)
    ex = Exec()
    with pytest.raises(SystemExit):
        sync.ensure_executor(_target(), "sync", [], prefix=str(tool_root), version="4.1.0",
                             tool_root=str(tool_root), execvp=ex, os_name="posix")
    assert ex.calls == [("uvx", BOOT + ["sync"])]


def test_the_target_version_outside_the_tool_continues(tmp_path):
    tool_root = tmp_path / "tools" / "h2t-ops"
    tool_root.mkdir(parents=True)
    ex = Exec()
    # A sibling whose name extends the root is outside it: the boundary is a separator.
    sibling = tmp_path / "tools" / "h2t-ops-cache"
    sibling.mkdir()
    assert sync.ensure_executor(_target(), "sync", [], prefix=str(sibling), version="4.1.0",
                                tool_root=str(tool_root), execvp=ex, os_name="posix") is None
    assert ex.calls == []


def test_without_install_json_a_3x_tool_is_found_through_uv_tool_dir(tmp_path):
    tool_root = tmp_path / "tools" / "h2t-ops"
    (tool_root / "lib").mkdir(parents=True)
    ex = Exec()
    with pytest.raises(SystemExit):
        sync.ensure_executor(_target(), "sync", [], prefix=str(tool_root / "lib"),
                             version="4.1.0", execvp=ex, os_name="posix",
                             detect_tool_root=lambda: str(tool_root))
    assert ex.calls


def test_the_installed_tool_root_comes_from_install_json(tmp_path):
    state.commit(state.Install(version="4.0.0", generation="g", tool_root="/from/state",
                               entrypoints={}))
    assert sync.installed_tool_root(detect=lambda: "/from/uv") == "/from/state"


def test_the_installed_tool_root_falls_back_to_uv_tool_dir(tmp_path):
    assert sync.installed_tool_root(detect=lambda: "/from/uv") == "/from/uv"


def test_uv_tool_dir_detection_names_the_h2t_ops_directory(tmp_path):
    (tmp_path / "h2t-ops").mkdir()

    class Done:
        returncode, stdout = 0, f"{tmp_path}\n"
    found = _REAL_UV_TOOL_ROOT(which=lambda name: "/bin/uv", run=lambda *a, **k: Done())
    assert found == str(tmp_path / "h2t-ops")
    assert _REAL_UV_TOOL_ROOT(which=lambda name: None) is None


def test_on_windows_the_bootstrap_is_spawned_and_its_code_propagated(tmp_path):
    seen = []

    class Done:
        returncode = 7

    def spawn(args):
        seen.append(args)
        return Done()
    with pytest.raises(SystemExit) as exc:
        sync.ensure_executor(_target(), "update", ["--json"], prefix=str(tmp_path),
                             version="4.0.0", tool_root=None, os_name="nt", spawn=spawn,
                             execvp=Exec())
    assert exc.value.code == 7
    assert seen == [BOOT + ["update", "--json"]]


def test_a_bootstrap_that_does_not_reach_the_target_does_not_loop(tmp_path, monkeypatch):
    monkeypatch.setenv(sync.RELAUNCH_ENV, "4.1.0")
    ex = Exec()
    with pytest.raises(ConfigError, match="4.0.0"):
        sync.ensure_executor(_target(), "sync", [], prefix=str(tmp_path), version="4.0.0",
                             tool_root=None, execvp=ex, os_name="posix")
    assert ex.calls == []


# --- the CLI ------------------------------------------------------------------------------

def _wire(monkeypatch, *, version="4.1.0"):
    """Target from fake pages; the executor counts as the target unless told otherwise."""
    monkeypatch.setattr(manifest, "urllib_fetch", _fetcher(_pages()))
    ex = Exec()
    monkeypatch.setattr(h2t_ops, "__version__", version)
    monkeypatch.setattr(sync, "OS_NAME", "posix")
    monkeypatch.setattr(sync.os, "execvp", ex)
    monkeypatch.setattr(sync, "installed_tool_root", lambda **k: None)
    return ex


def test_update_stays_update_across_the_relaunch(monkeypatch):
    ex = _wire(monkeypatch, version="4.0.0")
    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: True)  # --json alone needs a terminal
    with pytest.raises(SystemExit):
        cli.main(["update", "--json"])
    assert ex.calls == [("uvx", BOOT + ["update", "--json"])]


def test_the_target_executor_reaches_run(monkeypatch, capsys):
    _wire(monkeypatch)
    seen = []

    def run(mode, target, argv):
        seen.append((mode, target["version"], argv))
        return {"mode": mode}
    monkeypatch.setattr(sync, "run", run)
    assert cli.main(["sync", "--json"]) == 0
    assert seen == [("sync", "4.1.0", ["--json"])]
    assert json.loads(capsys.readouterr().out)["result"] == {"mode": "sync"}


def _editable(home, *, installed=True):
    state.commit(state.Install(version="4.1.0", generation="g", tool_root=str(home / "t"),
                               entrypoints={}, editable=str(home / "checkout")))
    if installed:
        _receipt(home / "t", f'{{ name = "h2t-ops", editable = {json.dumps(str(home / "checkout"))} }}')


@pytest.mark.parametrize("mode", ["sync", "update"])
def test_an_editable_install_stops_sync_and_update_before_anything(home, monkeypatch, capsys,
                                                                   mode):
    _editable(home)
    before = {p: p.read_bytes() for p in (home / ".h2t" / "run").iterdir()}

    def no_network(url):
        raise AssertionError("the editable stop must precede the target")
    monkeypatch.setattr(manifest, "urllib_fetch", no_network)
    assert cli.main([mode, "--json"]) == 3
    err = json.loads(capsys.readouterr().err)["error"]
    assert str(home / "checkout") in err["message"]
    assert "dev-sync" in err["hint"]
    assert err["details"]["reason"] == "editable"
    assert {p: p.read_bytes() for p in (home / ".h2t" / "run").iterdir()} == before


def test_an_editable_record_without_the_installed_tool_does_not_stop_sync(home, monkeypatch,
                                                                         capsys):
    """`uv tool uninstall` removes the receipt and leaves install.json's record of the last
    dev-sync; the receipt decides (#579)."""
    _editable(home, installed=False)
    _wire(monkeypatch)
    seen = []
    monkeypatch.setattr(sync, "run", lambda mode, target, argv: seen.append(mode) or {})
    assert cli.main(["sync", "--json"]) == 0, capsys.readouterr().err
    assert seen == ["sync"]


def test_dev_sync_never_reads_the_network(home, monkeypatch):
    _editable(home)

    def no_network(url):
        raise AssertionError("dev-sync read the network")
    monkeypatch.setattr(manifest, "urllib_fetch", no_network)
    seen = []
    monkeypatch.setattr(sync, "run", lambda mode, target, argv: seen.append((mode, target)))
    assert cli.main(["dev-sync"]) == 0
    assert seen == [("dev-sync", None)]


def test_an_unknown_mode_is_a_usage_error(capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main(["bogus"])
    assert exc.value.code == 2


# --- fix round 1 --------------------------------------------------------------------------

@pytest.mark.parametrize("mode", ["update", "sync"])
def test_the_relaunched_words_parse_as_the_same_mode_and_options(mode):
    command = sync.relaunch_command(_target(), mode, ["--json"])
    assert command[:len(BOOT)] == BOOT
    ns = cli.build_parser().parse_args(command[len(BOOT):])
    assert ns.mode == mode
    assert ns.json is True


def test_the_marker_does_not_outlive_a_qualifying_executor(tmp_path, monkeypatch):
    monkeypatch.setenv(sync.RELAUNCH_ENV, "4.1.0")  # set by the parent that re-launched us
    assert sync.ensure_executor(_target(), "sync", [], prefix=str(tmp_path), version="4.1.0",
                                tool_root=str(tmp_path / "elsewhere"), execvp=Exec(),
                                os_name="posix") is None
    assert sync.RELAUNCH_ENV not in os.environ


def test_windows_repair_from_inside_the_tool_hands_the_command_back(tmp_path):
    tool_root = tmp_path / "tools" / "h2t-ops"
    tool_root.mkdir(parents=True)

    def spawn(args):
        raise AssertionError("spawned from inside the environment the reinstall deletes")
    with pytest.raises(ConfigError) as exc:
        sync.ensure_executor(_target(), "update", ["--json"], prefix=str(tool_root),
                             version="4.0.0", tool_root=str(tool_root), os_name="nt",
                             spawn=spawn, execvp=Exec())
    command = BOOT + ["update", "--json"]
    assert exit_code_for(exc.value) == 3
    assert exc.value.details == {"reason": "relaunch_required", "command": command}
    assert exc.value.hint == manifest.render(command)
    assert sync.RELAUNCH_ENV not in os.environ


def test_windows_repair_reaches_the_cli_as_exit_3_with_the_reason(home, monkeypatch, capsys):
    tool_root = home / "tools" / "h2t-ops"
    tool_root.mkdir(parents=True)
    _wire(monkeypatch)
    monkeypatch.setattr(sync, "OS_NAME", "nt")
    monkeypatch.setattr(sync, "installed_tool_root", lambda **k: str(tool_root))
    monkeypatch.setattr(sync.sys, "prefix", str(tool_root))
    assert cli.main(["sync", "--json"]) == 3
    err = json.loads(capsys.readouterr().err)["error"]
    assert err["details"]["reason"] == "relaunch_required"
    assert err["hint"].startswith("uvx --isolated ") and err["hint"].endswith(" sync --json")


def _http_error(code):
    return urllib.error.HTTPError(manifest.MARKETPLACE_URL, code, "x", hdrs=None, fp=None)


@pytest.mark.parametrize("raised, kind, code", [
    (_http_error(404), ConfigError, 3),
    (_http_error(503), NetworkError, 6),
    (http.client.IncompleteRead(b"par"), NetworkError, 6),
    (http.client.RemoteDisconnected("closed"), NetworkError, 6),
])
def test_the_default_fetch_classifies_http_failures(monkeypatch, raised, kind, code):
    def fail(url, timeout=None):
        raise raised
    monkeypatch.setattr("urllib.request.urlopen", fail)
    with pytest.raises(kind) as exc:
        manifest.urllib_fetch(manifest.MARKETPLACE_URL)
    assert type(exc.value) is kind
    assert exit_code_for(exc.value) == code
    if code == 3:
        assert manifest.MARKETPLACE_URL in exc.value.hint


def test_a_missing_release_json_is_a_config_error_naming_it():
    pages = {manifest.MARKETPLACE_URL: _marketplace(_pinned())}

    def fetch(url):
        if url in pages:
            return pages[url]
        raise urllib.error.HTTPError(url, 404, "Not Found", hdrs=None, fp=None)
    with pytest.raises(ConfigError) as exc:
        manifest.current(fetch=fetch)
    assert manifest.release_url(REF) in exc.value.hint


def _receipt(root, requirement: str):
    root.mkdir(parents=True, exist_ok=True)
    (root / "uv-receipt.toml").write_text(
        "[tool]\n"
        f"requirements = [{requirement}]\n"
        'entrypoints = [{ name = "h2t-ops", install-path = "/b/h2t-ops", from = "h2t-ops" }]\n',
        encoding="utf-8")
    return root


def test_the_receipt_names_an_editable_checkout(tmp_path):
    root = _receipt(tmp_path / "h2t-ops", '{ name = "h2t-ops", editable = "/src/h2t-skills" }')
    assert sync.receipt_editable(str(root)) == "/src/h2t-skills"


@pytest.mark.parametrize("content", [
    '{ name = "h2t-ops", git = "https://github.com/lichtpfad/h2t-skills.git" }',
    '{ name = "h2t-ops", directory = "/src/h2t-skills" }',
    '{ name = "other", editable = "/src/other" }',
])
def test_a_non_editable_receipt_names_nothing(tmp_path, content):
    assert sync.receipt_editable(str(_receipt(tmp_path / "h2t-ops", content))) is None


def test_a_broken_or_absent_receipt_names_nothing(tmp_path):
    assert sync.receipt_editable(str(tmp_path)) is None
    (tmp_path / "uv-receipt.toml").write_text("[tool\n", encoding="utf-8")
    assert sync.receipt_editable(str(tmp_path)) is None


@pytest.mark.parametrize("mode", ["sync", "update"])
def test_a_3x_editable_install_takes_the_editable_stop(home, monkeypatch, capsys, mode):
    root = _receipt(home / "tools" / "h2t-ops", '{ name = "h2t-ops", editable = "/src/h2t-skills" }')
    monkeypatch.setattr(sync, "uv_tool_root", lambda **k: str(root))

    def no_network(url):
        raise AssertionError("the editable stop must precede the target")
    monkeypatch.setattr(manifest, "urllib_fetch", no_network)
    assert cli.main([mode, "--json"]) == 3
    err = json.loads(capsys.readouterr().err)["error"]
    assert err["details"] == {"reason": "editable", "checkout": "/src/h2t-skills"}
    assert "/src/h2t-skills" in err["message"] and "dev-sync" in err["hint"]
    _assert_nothing_on_disk(home)
