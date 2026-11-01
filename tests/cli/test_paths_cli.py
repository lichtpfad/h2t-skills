"""`h2t-ops paths` and `h2t-ops index` (#548 Task 19)."""
import json

import pytest

from h2t_ops.cli import dispatch
from h2t_ops.core import paths
from h2t_ops.lifecycle import session_record


def _run(capsys, *argv):
    rc = dispatch(list(argv))
    out, err = capsys.readouterr()
    return rc, out, err


def _json(capsys, *argv):
    rc, out, err = _run(capsys, *argv, "--json")
    assert rc == 0, err
    return json.loads(out)["result"]


def _write_paths(text: str):
    f = paths.paths_yaml()
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(text, encoding="utf-8")
    return f


# --- paths list ---------------------------------------------------------------------------

def test_list_has_a_row_per_place_with_its_source(capsys, tmp_path, monkeypatch):
    lake, vault = tmp_path / "lake", tmp_path / "vault"
    lake.mkdir()
    monkeypatch.setenv("H2T_PATH_VAULT", str(vault))
    monkeypatch.setenv("H2T_LAKE_ROOT", str(tmp_path / "old"))
    _write_paths(f"version: 1\nplaces:\n  lake: {lake}\n")

    got = _json(capsys, "paths", "list")
    rows = {r["id"]: r for r in got["places"]}
    assert list(rows) == [p.id for p in paths.PLACES]
    assert rows["lake"] == {"id": "lake", "path": str(lake), "kind": "place", "sync": "owner",
                            "exists": True, "source": "paths.yaml"}
    assert rows["inbox"]["path"] == str(paths.data_dir() / "inbox")
    assert rows["inbox"]["source"] == "default (not set)"
    assert rows["vault"]["path"] == str(vault) and rows["vault"]["source"] == "H2T_PATH_VAULT"
    assert rows["vault"]["exists"] is False
    assert rows["repo"]["path"] is None
    assert rows["repo"]["source"] == "cwd or --repo-root of each command"
    assert rows["config"]["source"] == "default" and rows["config"]["sync"] == "user"
    assert rows["run"]["path"] == str(paths.run_dir())
    assert got["old_env"] == [{"name": "H2T_LAKE_ROOT", "note": "not read"}]
    assert got["problem"] is None


def test_list_names_h2t_path_root_but_not_for_run(capsys, tmp_path, monkeypatch):
    monkeypatch.setenv("H2T_PATH_ROOT", str(tmp_path / "root"))
    rows = {r["id"]: r for r in _json(capsys, "paths", "list")["places"]}
    assert rows["config"] == {"id": "config", "path": str(tmp_path / "root" / "config"),
                              "kind": "class", "sync": "user", "exists": False,
                              "source": "H2T_PATH_ROOT"}
    assert rows["layout"]["source"] == "H2T_PATH_ROOT"
    assert rows["run"]["source"].startswith("default") and rows["vault"]["source"] == "default"


def test_list_human_shows_a_dash_for_repo_and_old_variables(capsys, tmp_path, monkeypatch):
    monkeypatch.setenv("H2T_SESSION_ROOT", str(tmp_path))
    rc, out, _ = _run(capsys, "paths", "list")
    assert rc == 0
    repo = next(line for line in out.splitlines() if line.startswith("repo "))
    assert "—" in repo and "cwd or --repo-root" in repo
    assert "H2T_SESSION_ROOT is set: not read" in out


def test_list_shows_a_broken_paths_yaml_instead_of_failing(capsys):
    _write_paths("places: [unclosed\n")
    got = _json(capsys, "paths", "list")
    rows = {r["id"]: r for r in got["places"]}
    assert "not valid YAML" in got["problem"]
    assert rows["lake"]["path"] is None and rows["lake"]["source"] == "paths.yaml (broken)"
    assert rows["config"]["path"] == str(paths.config_dir())


# --- paths get ----------------------------------------------------------------------------

@pytest.mark.parametrize("key, expected", [
    ("config", lambda: paths.config_dir()),
    ("state", lambda: paths.state_dir()),
    ("lake", lambda: paths.data_dir() / "lake"),            # not set: where the package writes
    ("secret:notion", lambda: paths.secrets_shared() / "notion.env"),
    ("secret:getcourse", lambda: paths.secrets_shared() / "getcourse.env"),
    ("data:research", lambda: paths.data_dir() / "research"),
    ("data:creative/profiles", lambda: paths.data_dir() / "creative" / "profiles"),
])
def test_get_prints_only_the_path(capsys, key, expected):
    rc, out, _ = _run(capsys, "paths", "get", key)
    assert rc == 0
    assert out == f"{expected()}\n"


@pytest.mark.parametrize("name, hint", [
    ("google.token", "h2t-ops google auth"),
    ("google.client", "Desktop OAuth client"),
    ("telegram.auth-state", "h2t-ops telegram auth"),
])
def test_get_a_missing_json_secret_is_exit_3_not_a_path(capsys, name, hint):
    """A path to a file that is not there reads as an answer, and the caller loses Google on
    a machine that still has only its 3.x files (#584)."""
    rc, out, err = _run(capsys, "paths", "get", f"secret:{name}")
    assert rc == 3 and out == ""
    assert hint in err


def test_get_a_json_secret_names_the_file_that_is_read(capsys):
    from h2t_ops.core import secrets

    old = paths.legacy("google.store") / "tokens.json"
    old.parent.mkdir(parents=True)
    old.write_text("{}", encoding="utf-8")
    assert _run(capsys, "paths", "get", "secret:google.token")[1] == f"{old}\n"   # unmigrated

    new = secrets.json_path("google.token")
    new.parent.mkdir(parents=True, exist_ok=True)
    new.write_text("{}", encoding="utf-8")
    assert _run(capsys, "paths", "get", "secret:google.token")[1] == f"{new}\n"   # 4.0 first


def test_get_lake_from_paths_yaml(capsys, tmp_path):
    _write_paths(f"places:\n  lake: {tmp_path / 'lake'}\n")
    assert _run(capsys, "paths", "get", "lake")[1] == f"{tmp_path / 'lake'}\n"


def test_get_repo_is_a_usage_error_that_says_why(capsys):
    rc, out, err = _run(capsys, "paths", "get", "repo")
    assert rc == 2 and out == ""
    assert "directory a command runs in" in err


@pytest.mark.parametrize("key", ["nowhere", "secret:../x", "data:../x", "data:a/../../b", "secret:"])
def test_get_unknown_or_unsafe_is_a_usage_error(capsys, key):
    rc, out, _ = _run(capsys, "paths", "get", key)
    assert rc == 2 and out == ""


def test_missing_argument_is_exit_2(capsys):
    assert _run(capsys, "paths", "get")[0] == 2
    assert _run(capsys, "paths")[0] == 2
    assert _run(capsys, "index", "query")[0] == 2


# --- paths set ----------------------------------------------------------------------------

def test_set_writes_paths_yaml_and_keeps_the_users_comment(capsys, tmp_path):
    inbox, lake = tmp_path / "inbox", tmp_path / "lake"
    _write_paths(f"# my places, do not lose this\nversion: 1\nplaces:\n  inbox: {inbox}  # downloads\n")
    rc, out, err = _run(capsys, "paths", "set", "lake", str(lake))
    assert rc == 0, err
    text = paths.paths_yaml().read_text(encoding="utf-8")
    assert "# my places, do not lose this" in text and "# downloads" in text
    assert paths.paths_config().places == {"inbox": inbox, "lake": lake}
    assert str(lake) in out


def test_set_saves_a_backup_of_the_file_it_edits(capsys, tmp_path):
    before = _write_paths("places: {}\n").read_bytes()
    got = _json(capsys, "paths", "set", "kb", str(tmp_path / "kb"))
    backup = paths.backups_dir() / got["backup"].rsplit("/", 1)[-1]
    assert backup.read_bytes() == before and backup.name.startswith("paths.yaml.")
    assert got["repaired"] is False


def test_set_without_a_file_creates_it(capsys, tmp_path):
    got = _json(capsys, "paths", "set", "inbox", str(tmp_path / "in"))
    assert got["backup"] is None
    assert paths.paths_config().places == {"inbox": tmp_path / "in"}


def test_set_overlap_is_config_error_and_leaves_the_file_unchanged(capsys, tmp_path):
    f = _write_paths(f"version: 1\nplaces:\n  lake: {tmp_path / 'lake'}\n")
    before = f.read_bytes()
    rc, _, err = _run(capsys, "paths", "set", "inbox", str(tmp_path / "lake" / "in"))
    assert rc == 3
    assert "overlap" in err
    assert f.read_bytes() == before
    assert not paths.backups_dir().exists()


def test_set_into_the_h2t_root_is_refused(capsys):
    rc, _, err = _run(capsys, "paths", "set", "lake", str(paths.root() / "data" / "x"))
    assert rc == 3 and "h2t root" in err
    assert not paths.paths_yaml().exists()


@pytest.mark.parametrize("place, hint", [("vault", "H2T_PATH_VAULT"), ("repo", "lake, inbox, kb"),
                                         ("config", "lake, inbox, kb")])
def test_set_only_takes_lake_inbox_kb(capsys, tmp_path, place, hint):
    rc, _, err = _run(capsys, "paths", "set", place, str(tmp_path / "x"))
    assert rc == 2 and hint in err
    assert not paths.paths_yaml().exists()


def test_paths_set_repairs_a_broken_file(capsys, tmp_path):
    """The old document does not parse: set writes a new one of this key alone, saves the
    old bytes in state/backups and says where (R14, R17, R34)."""
    broken = b"places:\n  lake: [unclosed\n"
    f = paths.paths_yaml()
    f.parent.mkdir(parents=True)
    f.write_bytes(broken)
    rc, out, err = _run(capsys, "paths", "set", "lake", str(tmp_path / "lake"))
    assert rc == 0, err
    assert paths.paths_config().places == {"lake": tmp_path / "lake"}
    copies = sorted(paths.backups_dir().glob("paths.yaml.*"))
    assert [c.read_bytes() for c in copies] == [broken]
    assert "did not parse" in out and str(copies[0]) in out

def test_set_repairs_places_that_is_not_a_mapping_and_says_so(capsys, tmp_path):
    _write_paths("# keep me\nplaces: just a string\n")
    rc, out, err = _run(capsys, "paths", "set", "lake", str(tmp_path / "lake"))
    assert rc == 0, err
    assert paths.paths_config().places == {"lake": tmp_path / "lake"}
    assert "dropped places: not a mapping (str)" in out
    assert "# keep me" in paths.paths_yaml().read_text(encoding="utf-8")
    assert "saved in" in out and list(paths.backups_dir().glob("paths.yaml.*"))


def test_set_keeps_valid_entries_and_drops_the_invalid_ones(capsys, tmp_path):
    """A vault key, an unknown name, a relative path, a path inside ~/.h2t: each one went
    in by hand and makes paths_config() fail; set repairs it (R17) and names each."""
    inbox = tmp_path / "inbox"
    _write_paths("places:\n"
                 f"  inbox: {inbox}  # my downloads\n"
                 f"  vault: {tmp_path / 'v'}\n"
                 f"  photos: {tmp_path / 'p'}\n"
                 "  kb: relative/kb\n"
                 "sync: syncthing\n")
    got = _json(capsys, "paths", "set", "lake", str(tmp_path / "lake"))
    assert paths.paths_config().places == {"inbox": inbox, "lake": tmp_path / "lake"}
    dropped = got["dropped"]
    assert dropped[0] == "sync: not a mapping (str)"
    assert dropped[1] == f"places.vault: {paths.VAULT_HINT}" and "H2T_PATH_VAULT" in dropped[1]
    assert dropped[2].startswith("places.photos: unknown place 'photos'")
    assert dropped[3].startswith("places.kb: place 'kb' must be an absolute path")
    assert len(dropped) == 4 and got["repaired"] is True and got["backup"]
    assert "# my downloads" in paths.paths_yaml().read_text(encoding="utf-8")


def test_set_does_not_repair_another_version(capsys, tmp_path):
    f = _write_paths("version: 2\nplaces: {}\n")
    rc, _, err = _run(capsys, "paths", "set", "lake", str(tmp_path / "lake"))
    assert rc == 3 and "version 2" in err
    assert f.read_text(encoding="utf-8") == "version: 2\nplaces: {}\n"


def test_set_reads_again_when_the_file_changes_before_it_is_published(capsys, tmp_path, monkeypatch):
    """Read-modify-write: a save landing between the read and the publication is not
    overwritten with the stale copy; set reads again and keeps both."""
    from h2t_ops.core import backups
    f = _write_paths(f"places:\n  inbox: {tmp_path / 'inbox'}\n")
    real, calls = backups.save_backup, []

    def save_backup(path):
        calls.append(path)
        if len(calls) == 1:                       # another writer, after set has read
            f.write_text(f"places:\n  inbox: {tmp_path / 'inbox'}\n  kb: {tmp_path / 'kb'}\n",
                         encoding="utf-8")
        return real(path)

    monkeypatch.setattr(backups, "save_backup", save_backup)
    rc, _, err = _run(capsys, "paths", "set", "lake", str(tmp_path / "lake"))
    assert rc == 0, err
    assert paths.paths_config().places == {"inbox": tmp_path / "inbox", "kb": tmp_path / "kb",
                                           "lake": tmp_path / "lake"}
    assert len(calls) == 2


def test_set_gives_up_with_exit_3_when_the_file_keeps_changing(capsys, tmp_path, monkeypatch):
    from h2t_ops.core import backups
    f = _write_paths("places: {}\n")
    real, n = backups.save_backup, []

    def save_backup(path):
        n.append(1)
        f.write_text("places: {}\n" + "#" * len(n) + "\n", encoding="utf-8")
        return real(path)

    monkeypatch.setattr(backups, "save_backup", save_backup)
    rc, _, err = _run(capsys, "paths", "set", "lake", str(tmp_path / "lake"))
    assert rc == 3 and "kept changing" in err
    assert "lake" not in f.read_text(encoding="utf-8")


# --- index --------------------------------------------------------------------------------

def _session(machine, sid, updated_at):
    f = paths.records("sessions", machine) / "p" / f"{sid}.md"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_bytes(session_record.render({"session_id": sid, "machine": machine, "project": "p",
                                         "updated_at": updated_at}, b""))
    return f


def test_index_rebuild_reports_counts(capsys):
    _session("mac", "s1", "2026-10-17T00:00:00Z")
    got = _json(capsys, "index", "rebuild")
    assert got == {"path": str(paths.state_dir() / "index.sqlite"),
                   "sessions": 1, "projects": 0, "problems": 0}
    rc, out, _ = _run(capsys, "index", "rebuild")
    assert rc == 0 and "1 sessions" in out


def test_index_query_lists_sessions_of_the_project_from_every_machine(capsys):
    _session("mac", "s1", "2026-10-17T00:00:00Z")
    _session("laptop", "s2", "2026-10-18T00:00:00Z")
    got = _json(capsys, "index", "query", "--project", "p")
    assert [s["session_id"] for s in got["sessions"]] == ["s2", "s1"]
    assert got["problems"] == []
    rc, out, _ = _run(capsys, "index", "query", "--project", "nobody")
    assert rc == 0 and "no sessions of nobody" in out


def test_index_rebuild_exits_3_while_another_process_holds_the_lock(capsys, monkeypatch):
    from h2t_ops.core import store
    from h2t_ops.lifecycle.index import query
    monkeypatch.setattr(query, "LOCK_S", 0.2)
    with store.locked(query._lock_path(), place="state"):
        rc, out, err = _run(capsys, "index", "rebuild")
    assert rc == 3 and out == ""
    assert "index is locked by another process" in err
