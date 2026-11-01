"""contracts/pos-interop.json holds against the code (#582).

Each entry is checked by what the code does, not by what the file says: the CLI is run, the
env var is set, the mirror is written. A stable entry that changes needs a new major version,
and the snapshot of the major's stable entries is what notices.
"""
import json
import re
from pathlib import Path

import pytest

from h2t_ops.cli import dispatch
from h2t_ops.core import google_auth, lake, paths

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = json.loads((ROOT / "contracts/pos-interop.json").read_text(encoding="utf-8"))
ENTRIES = {e["name"]: e for e in CONTRACT["interfaces"]}
MAJOR = CONTRACT["version"].split(".")[0]
SNAPSHOT = Path(__file__).with_name(f"pos_interop_v{MAJOR}_stable.json")


def _get(capsys, place):
    rc = dispatch(["paths", "get", place, "--json"])
    out, err = capsys.readouterr()
    assert rc == 0, err
    return json.loads(out)


# --- the file itself ----------------------------------------------------------------------

def test_version_is_semver_and_names_are_unique():
    assert re.fullmatch(r"\d+\.\d+\.\d+", CONTRACT["version"])
    names = [e["name"] for e in CONTRACT["interfaces"]]
    assert len(names) == len(set(names))


@pytest.mark.parametrize("name", sorted(ENTRIES))
def test_every_entry_says_who_owns_it_and_how_long_it_lives(name):
    e = ENTRIES[name]
    assert {"kind", "owner", "reader", "status", "meaning"} <= set(e)
    assert e["kind"] in ("env", "cli", "path")
    assert e["status"] in ("stable", "deprecated")
    if e["status"] == "deprecated":
        assert e.get("removal_condition"), "a deprecated entry names what removes it"


def test_stable_entries_of_this_major_are_unchanged():
    """Adding an entry is fine; changing or dropping a stable one is a new major version,
    with a new snapshot beside this test."""
    assert SNAPSHOT.is_file(), f"version {CONTRACT['version']}: add {SNAPSHOT.name}"
    frozen = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    for old in frozen:
        assert ENTRIES.get(old["name"]) == old, (
            f"stable entry {old['name']!r} changed within major {MAJOR}: bump the major "
            "and snapshot the new stable entries")


# --- each entry against the code ----------------------------------------------------------

def test_vault_comes_from_h2t_path_vault(capsys, monkeypatch, tmp_path):
    assert ENTRIES["H2T_PATH_VAULT"]["resolved_by"] == "h2t-ops paths get vault"
    monkeypatch.setenv("H2T_PATH_VAULT", str(tmp_path / "v"))
    assert _get(capsys, "vault")["result"] == str(tmp_path / "v")
    monkeypatch.delenv("H2T_PATH_VAULT")
    assert _get(capsys, "vault")["result"] == str(Path.home() / ".dor" / "vault")


@pytest.mark.parametrize("place", ENTRIES["h2t-ops paths get"]["places"])
def test_paths_get_keeps_its_envelope(capsys, place):
    entry = ENTRIES["h2t-ops paths get"]
    assert entry["argv"][:3] == ["h2t-ops", "paths", "get"]
    got = _get(capsys, place)
    assert set(got) == set(entry["envelope"])
    assert got["ok"] is True and got["provider"] == entry["envelope"]["provider"]
    assert Path(got["result"]).is_absolute()


def test_path_entries_name_places_that_exist():
    ids = {p.id for p in paths.PLACES}
    for e in ENTRIES.values():
        if "place" in e:
            assert e["place"] in ids, e["name"]


def test_lake_is_one_directory_per_connector_with_a_manifest():
    d = lake.ConnectorDir("meetgeek")
    assert d.root == paths.place_or_default("lake")[0] / "meetgeek"
    assert d.manifest == d.root / "manifest.jsonl"


def test_cursors_live_in_state():
    rel = ENTRIES["connector cursors"]["path"].replace("<provider>", "granola")
    assert lake.cursor_path("granola") == paths.state_dir() / rel


def test_token_mirror_is_written_where_the_contract_says():
    mirror = Path(ENTRIES["google token mirror"]["path"].replace("~", str(Path.home()), 1))
    assert google_auth.mirror_legacy({"token": "t"}) == "absent"   # never created
    mirror.parent.mkdir(parents=True)
    mirror.write_text("{}", encoding="utf-8")
    assert google_auth.mirror_legacy({"token": "t"}) == "written"
    assert json.loads(mirror.read_text(encoding="utf-8")) == {"token": "t"}
