import json
import os

import pytest

from h2t_ops.core import lake, paths, store
from h2t_ops.core.errors import ConfigError


@pytest.fixture
def lk(tmp_path, monkeypatch):
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    for k in list(os.environ):
        if k.startswith("H2T_PATH_") or k in paths.OLD_ENV:
            monkeypatch.delenv(k, raising=False)
    (home / ".h2t" / "config").mkdir(parents=True)
    (home / ".h2t" / "config" / "paths.yaml").write_text(
        f"version: 1\nplaces:\n  lake: {tmp_path / 'lake'}\n", encoding="utf-8")
    return lake.ConnectorDir("granola")


def _rows(d):
    return [json.loads(x) for x in d.manifest.read_text().splitlines()]


def test_publish_new_then_replace_own(lk):
    assert lk.publish({"n1.md": b"v1"}, op_id="a") == []
    assert lk.publish({"n1.md": b"v2"}, op_id="b") == []
    assert (lk.root / "n1.md").read_bytes() == b"v2"
    assert [r["state"] for r in _rows(lk)] == ["pending", "committed", "pending", "committed"]


def test_foreign_file_on_a_new_path_is_refused_and_untouched(lk):
    (lk.root).mkdir(parents=True)
    (lk.root / "n1.md").write_bytes(b"hand-made")
    assert lk.publish({"n1.md": b"v1"}, op_id="a") == ["n1.md"]
    assert (lk.root / "n1.md").read_bytes() == b"hand-made"
    assert "n1.md" not in lk.owned() and "n1.md" not in _rows(lk)[-1]["files"]
    assert lk.publish({"n1.md": b"v2"}, op_id="b") == ["n1.md"]       # never replaced later
    assert (lk.root / "n1.md").read_bytes() == b"hand-made"


@pytest.mark.parametrize("stop_after", ["pending", "files"])
def test_interrupted_publish_recovers_only_hash_matched(lk, monkeypatch, stop_after):
    real_create = store.create
    calls = []

    def boom(*a, **kw):
        calls.append(1)
        if stop_after == "pending":
            raise KeyboardInterrupt
        real_create(*a, **kw)
        raise KeyboardInterrupt

    monkeypatch.setattr(store, "create", boom)
    with pytest.raises(KeyboardInterrupt):
        lk.publish({"n1.md": b"v1"}, op_id="a")
    monkeypatch.setattr(store, "create", real_create)
    assert lk.recover() == (["n1.md"] if stop_after == "files" else [])
    assert ("n1.md" in lk.owned()) == (stop_after == "files")


def test_pending_does_not_own_a_file_with_another_hash(lk, monkeypatch):
    monkeypatch.setattr(store, "create", lambda *a, **kw: (_ for _ in ()).throw(KeyboardInterrupt))
    with pytest.raises(KeyboardInterrupt):
        lk.publish({"n1.md": b"v1"}, op_id="a")
    lk.root.mkdir(parents=True, exist_ok=True)
    (lk.root / "n1.md").write_bytes(b"someone else")   # appears during the outage
    assert lk.recover() == []
    assert "n1.md" not in lk.owned()


def test_legacy_granola_rows_count_as_committed(lk):
    lk.root.mkdir(parents=True)
    row = {"note_id": "n1", "title": "t", "updated_at": "2026-10-01T00:00:00Z",
           "include": ["summaries"], "synced_at": "2026-10-01T00:00:01Z"}   # 3.x shape, sync.py:131-138
    lk.manifest.write_text(json.dumps(row) + "\n")
    assert set(lk.owned()) == {"summaries/n1.md", "summaries/n1.json"}


def test_committed_rows_carry_granola_version_fields(lk):
    meta = {"note_id": "n1", "updated_at": "2026-10-01T00:00:00Z", "include": ["transcripts"]}
    lk.publish({"transcripts/n1.md": b"t", "transcripts/n1.json": b"{}"}, op_id="a", meta=meta)
    from h2t_ops.connectors.granola import sync
    assert "transcripts" in sync._synced_versions(lk.manifest)["n1@2026-10-01T00:00:00Z"]


def test_manifest_lines_are_deterministic_json(lk):
    """R39: one serialization, sorted keys, no spaces, non-ASCII kept as is."""
    lk.publish({"n1.md": b"v1"}, op_id="a", meta={"title": "Заметка", "b": 1, "a": 2})
    raw = lk.manifest.read_text(encoding="utf-8").splitlines()
    assert raw[1] == lake.manifest_line(json.loads(raw[1]))
    assert "Заметка" in raw[1] and ", " not in raw[1] and raw[1].index('"a"') < raw[1].index('"b"')


def test_summary_and_transcript_of_one_note_do_not_collide(lk):
    lk.publish({"summaries/n1.md": b"s", "transcripts/n1.md": b"t"}, op_id="a")
    assert (lk.root / "summaries" / "n1.md").read_bytes() == b"s"
    assert (lk.root / "transcripts" / "n1.md").read_bytes() == b"t"


def test_place_follows_the_origin_of_the_root(lk, tmp_path):
    """R28: configured lake -> "lake"; no paths.yaml -> data/lake as "data"; elsewhere -> dest."""
    assert (lk.place, lk.dest) == ("lake", False)
    (paths.paths_yaml()).unlink()
    d = lake.ConnectorDir("granola")
    assert d.root == paths.data_dir() / "lake" / "granola" and (d.place, d.dest) == ("data", False)
    assert d.publish({"n1.md": b"v1"}, op_id="a") == []          # no WriteRefused
    out = lake.ConnectorDir("granola", root=tmp_path / "mine")
    assert out.dest is True
    assert out.publish({"n1.md": b"v1"}, op_id="a") == []


def test_undeclared_3x_lake_is_refused_with_the_paths_set_hint(lk):
    """GC: after layout 1 the old place is not written until paths.yaml declares it (R2)."""
    (paths.paths_yaml()).unlink()
    old = paths.legacy("lake.dor") / "granola"
    old.mkdir(parents=True)
    paths.layout_file().write_text('{"layout": 1}', encoding="utf-8")
    assert lake.ConnectorDir("granola").root == paths.data_dir() / "lake" / "granola"
    with pytest.raises(store.WriteRefused) as exc:
        lake.ConnectorDir("granola", root=old)
    assert exc.value.hint == f"h2t-ops paths set lake {paths.legacy('lake.dor')}"


def test_before_layout_1_the_3x_lake_is_the_lake(lk):
    """§8: an unmigrated machine keeps syncing into the lake POS reads. A data/lake default
    there would take the notes away while the cursor advances past them."""
    (paths.paths_yaml()).unlink()
    old = paths.legacy("lake.dor")
    (old / "granola").mkdir(parents=True)
    d = lake.ConnectorDir("granola")
    assert d.root == old / "granola" and (d.place, d.dest) == ("lake", False)
    assert d.publish({"n1.md": b"v1"}, op_id="a") == []
    assert (old / "granola" / "n1.md").read_bytes() == b"v1"
    assert not (paths.data_dir() / "lake").exists()
    assert store.classify(old / "granola" / "n1.md") == "lake"
    paths.layout_file().write_text('{"layout": 1}', encoding="utf-8")
    assert lake.ConnectorDir("granola").root == paths.data_dir() / "lake" / "granola"
    assert store.classify(old / "granola" / "n1.md") == "legacy"


def test_cursor_lives_in_state_and_falls_back_to_the_3x_one(lk):
    old = paths.legacy("lake.dor") / "_cursors" / "granola.json"
    old.parent.mkdir(parents=True)
    old.write_text('{"last_seen_ts": "old"}')
    assert lake.read_cursor("granola") == {"last_seen_ts": "old"}
    assert lake.write_cursor("granola", {"last_seen_ts": "new"}) == paths.state_dir() / "cursors" / "granola.json"
    assert lake.read_cursor("granola") == {"last_seen_ts": "new"}
    assert json.loads(old.read_text()) == {"last_seen_ts": "old"}      # the 3.x file is not written


@pytest.mark.parametrize("line", ['{"op": "a", "state": "comm', '[1, 2]'])
def test_a_broken_manifest_row_is_an_error_naming_its_line(lk, line):
    """Never skipped: a skipped row would silently turn its files foreign."""
    lk.publish({"n1.md": b"v1"}, op_id="a")
    with lk.manifest.open("a") as fh:
        fh.write(line + "\n")
    with pytest.raises(ConfigError, match=r"manifest.jsonl:3 "):
        lk.owned()


@pytest.mark.parametrize("text", ['{"last_seen_ts": ', '[]'])
def test_a_broken_cursor_is_an_error_not_a_resync(lk, text):
    f = lake.cursor_path("granola")
    f.parent.mkdir(parents=True)
    f.write_text(text)
    with pytest.raises(ConfigError, match="granola.json"):
        lake.read_cursor("granola")


def test_a_chunked_value_is_streamed_hashed_and_owned(lk):
    """A recording: chunks are spooled and hashed, then published like bytes (R29)."""
    assert lk.publish({"rec/m1.mp4": iter([b"ab", b"cd"])}, op_id="a") == []
    assert (lk.root / "rec" / "m1.mp4").read_bytes() == b"abcd"
    assert lk.owned()["rec/m1.mp4"] == store.sha256(b"abcd")
    assert _rows(lk)[0]["files"]["rec/m1.mp4"]["sha256"] == store.sha256(b"abcd")
    (lk.root / "rec" / "m2.mp4").write_bytes(b"theirs")
    assert lk.publish({"rec/m2.mp4": iter([b"x"])}, op_id="b") == ["rec/m2.mp4"]
    assert (lk.root / "rec" / "m2.mp4").read_bytes() == b"theirs"
