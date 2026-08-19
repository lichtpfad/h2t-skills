"""Tests for h2t_ops.connectors.granola.sync — files, manifest, updated_at cursor."""
from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from h2t_ops.connectors.granola import sync as S
from h2t_ops.core.errors import UsageError


NOTE_V1 = {
    "id": "not_1", "title": "Call", "created_at": "2026-08-17T15:00:00.000Z",
    "updated_at": "2026-08-17T16:00:00.000Z", "summary_markdown": "## v1\n",
    "attendees": [{"name": "Alex", "email": "a@example.com"}],
}
FRAG = {"text": "hello", "start_time": "2026-08-17T15:02:01.000Z",
        "end_time": "2026-08-17T15:02:03.000Z",
        "speaker": {"source": "speaker", "attribution": "them", "name": "Alex"}}


def _client(notes=None, note=None, transcript=None):
    c = MagicMock()
    c.list_notes.return_value = {"rows": notes if notes is not None else [NOTE_V1],
                                "next_cursor": None, "has_more": False}
    c.get_note.return_value = note or NOTE_V1
    c.get_transcript.return_value = transcript or {"transcript": [FRAG], "truncated": False}
    return c


def test_sync_writes_markdown_and_raw_json_pairs(tmp_path):
    out = S.sync_notes(_client(), to=tmp_path, include={"summaries", "transcripts"},
                       cursor_file=tmp_path / "cursor.json")
    assert out["synced"] == 1
    assert (tmp_path / "summaries" / "not_1.md").is_file()
    assert (tmp_path / "summaries" / "not_1.json").is_file()
    assert (tmp_path / "transcripts" / "not_1.md").is_file()
    raw = json.loads((tmp_path / "transcripts" / "not_1.json").read_text(encoding="utf-8"))
    assert raw["transcript"][0]["text"] == "hello"  # verbatim provider payload preserved


def test_sync_markdown_contains_merged_speaker_block(tmp_path):
    S.sync_notes(_client(), to=tmp_path, include={"transcripts"}, cursor_file=tmp_path / "c.json")
    md = (tmp_path / "transcripts" / "not_1.md").read_text(encoding="utf-8")
    assert "**Alex** [15:02:01] — hello" in md


def test_sync_skips_note_already_synced_at_same_updated_at(tmp_path):
    args = dict(to=tmp_path, include={"summaries"}, cursor_file=tmp_path / "c.json")
    S.sync_notes(_client(), **args)
    second = S.sync_notes(_client(), **args)
    assert second["synced"] == 0
    assert second["skipped"] == 1


def test_sync_rewrites_note_when_summary_was_edited(tmp_path):
    """note.edited only changes summary — created_at cursors would miss this."""
    args = dict(to=tmp_path, include={"summaries"}, cursor_file=tmp_path / "c.json")
    S.sync_notes(_client(), **args)
    v2 = {**NOTE_V1, "updated_at": "2026-08-18T09:00:00.000Z", "summary_markdown": "## v2 edited\n"}
    out = S.sync_notes(_client(notes=[v2], note=v2), **args)
    assert out["synced"] == 1
    assert "v2 edited" in (tmp_path / "summaries" / "not_1.md").read_text(encoding="utf-8")


def test_sync_manifest_records_every_version(tmp_path):
    args = dict(to=tmp_path, include={"summaries"}, cursor_file=tmp_path / "c.json")
    S.sync_notes(_client(), **args)
    v2 = {**NOTE_V1, "updated_at": "2026-08-18T09:00:00.000Z"}
    S.sync_notes(_client(notes=[v2], note=v2), **args)
    lines = [json.loads(x) for x in (tmp_path / "manifest.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    assert [x["updated_at"] for x in lines] == ["2026-08-17T16:00:00.000Z", "2026-08-18T09:00:00.000Z"]


def test_sync_cursor_stores_latest_updated_at(tmp_path):
    cursor = tmp_path / "c.json"
    S.sync_notes(_client(), to=tmp_path, include={"summaries"}, cursor_file=cursor)
    data = json.loads(cursor.read_text(encoding="utf-8"))
    assert data["last_seen_ts"] == "2026-08-17T16:00:00.000Z"
    assert data["last_seen_id"] == "not_1"
    assert data["cursor_type"] == "updated_at"
    assert data["items_ingested"] == 1


def test_sync_since_cursor_queries_updated_after(tmp_path):
    cursor = tmp_path / "c.json"
    cursor.write_text(json.dumps({"last_seen_ts": "2026-08-17T16:00:00.000Z"}), encoding="utf-8")
    client = _client(notes=[])
    S.sync_notes(client, to=tmp_path, include={"summaries"}, cursor_file=cursor, since_cursor=True)
    assert client.list_notes.call_args.kwargs["updated_after"] == "2026-08-17T16:00:00.000Z"


def test_sync_since_flag_queries_updated_after(tmp_path):
    client = _client(notes=[])
    S.sync_notes(client, to=tmp_path, include={"summaries"},
                 cursor_file=tmp_path / "c.json", since="2026-08-01")
    assert client.list_notes.call_args.kwargs["updated_after"] == "2026-08-01"


def test_sync_one_failing_note_does_not_abort_the_run(tmp_path):
    from h2t_ops.core.errors import ProviderError
    good = {**NOTE_V1, "id": "not_2", "updated_at": "2026-08-17T17:00:00.000Z"}
    client = _client(notes=[NOTE_V1, good])
    client.get_note.side_effect = [ProviderError("boom"), good]
    out = S.sync_notes(client, to=tmp_path, include={"summaries"}, cursor_file=tmp_path / "c.json")
    assert out["errors"] == 1
    assert out["synced"] == 1
    assert (tmp_path / "summaries" / "not_2.md").is_file()


def test_sync_rejects_unknown_include_values(tmp_path):
    with pytest.raises(UsageError):
        S.sync_notes(_client(), to=tmp_path, include={"recordings"}, cursor_file=tmp_path / "c.json")


def test_sync_resolves_folder_name(tmp_path):
    client = _client(notes=[])
    client.resolve_folder_id.return_value = "fol_x"
    S.sync_notes(client, to=tmp_path, include={"summaries"},
                 cursor_file=tmp_path / "c.json", folder="Clients")
    assert client.list_notes.call_args.kwargs["folder_id"] == "fol_x"


def test_sync_backfills_transcripts_when_include_widens(tmp_path):
    """First pass took summaries only; asking for transcripts later must fetch them."""
    args = dict(to=tmp_path, cursor_file=tmp_path / "c.json")
    S.sync_notes(_client(), include={"summaries"}, **args)
    assert not (tmp_path / "transcripts" / "not_1.md").is_file()

    out = S.sync_notes(_client(), include={"summaries", "transcripts"}, **args)

    assert out["synced"] == 1
    assert out["skipped"] == 0
    assert (tmp_path / "transcripts" / "not_1.md").is_file()


def test_sync_backfill_fetches_only_the_missing_part(tmp_path):
    """Widening include must not re-download what the lake already holds."""
    args = dict(to=tmp_path, cursor_file=tmp_path / "c.json")
    S.sync_notes(_client(), include={"transcripts"}, **args)
    client = _client()

    S.sync_notes(client, include={"summaries", "transcripts"}, **args)

    assert client.get_transcript.call_count == 0  # already on disk
    assert (tmp_path / "summaries" / "not_1.md").is_file()


def test_sync_skips_when_include_narrows(tmp_path):
    """Asking for less than the lake already holds is a no-op, not a re-sync."""
    args = dict(to=tmp_path, cursor_file=tmp_path / "c.json")
    S.sync_notes(_client(), include={"summaries", "transcripts"}, **args)

    out = S.sync_notes(_client(), include={"summaries"}, **args)

    assert out["synced"] == 0
    assert out["skipped"] == 1


def test_sync_manifest_records_what_was_included(tmp_path):
    S.sync_notes(_client(), to=tmp_path, include={"summaries"}, cursor_file=tmp_path / "c.json")
    rec = json.loads((tmp_path / "manifest.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert rec["include"] == ["summaries"]


def test_sync_coverage_is_the_union_across_manifest_records(tmp_path):
    """After a backfill the version is complete; a third pass must do nothing."""
    args = dict(to=tmp_path, cursor_file=tmp_path / "c.json")
    S.sync_notes(_client(), include={"summaries"}, **args)
    S.sync_notes(_client(), include={"transcripts"}, **args)

    out = S.sync_notes(_client(), include={"summaries", "transcripts"}, **args)

    assert out["synced"] == 0
    assert out["skipped"] == 1


def test_sync_treats_legacy_manifest_record_without_include_as_complete(tmp_path):
    """Lakes written before include-tracking must not trigger a surprise full refetch."""
    (tmp_path / "manifest.jsonl").write_text(json.dumps({
        "note_id": "not_1", "title": "Call",
        "created_at": "2026-08-17T15:00:00.000Z",
        "updated_at": "2026-08-17T16:00:00.000Z",
        "synced_at": "2026-08-17T16:05:00.000Z",
    }) + "\n", encoding="utf-8")

    out = S.sync_notes(_client(), to=tmp_path, include={"summaries", "transcripts"},
                       cursor_file=tmp_path / "c.json")

    assert out["synced"] == 0
    assert out["skipped"] == 1
