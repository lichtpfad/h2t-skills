"""Tests for h2t_ops.connectors.granola.commands (rendering + dispatch)."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from h2t_ops.connectors.granola import commands as C


def _frag(text, speaker=None, start="2026-08-17T15:02:01.000Z", end="2026-08-17T15:02:03.000Z"):
    return {"text": text, "start_time": start, "end_time": end,
            "speaker": speaker or {"source": "speaker", "attribution": "them"}}


NOTE = {
    "id": "not_6gcBxxxxxxxxxx",
    "title": "Strategy call",
    "web_url": "https://notes.granola.ai/d/not_6gcBxxxxxxxxxx",
    "owner": {"name": "Stanislav", "email": "s@example.com"},
    "created_at": "2026-08-17T15:00:00.000Z",
    "updated_at": "2026-08-17T16:30:00.000Z",
    "attendees": [{"name": "Alexander Korneev", "email": "a@example.com"},
                  {"name": None, "email": "vlad@example.com"}],
    "summary_markdown": "## Outcome\n\n- ship it\n",
    "calendar_event": {"event_title": "Strategy call",
                       "scheduled_start_time": "2026-08-17T15:00:00.000Z",
                       "scheduled_end_time": "2026-08-17T16:00:00.000Z",
                       "invitees": [{"name": "Erin Wajufos", "email": "e@example.com"}]},
    "folder_membership": [{"id": "fol_a", "name": "Clients"}],
}


# ─── Speaker merging ──────────────────────────────────────────────────────────

def test_merge_joins_consecutive_fragments_of_same_speaker():
    named = {"source": "speaker", "attribution": "them", "name": "Alexander Korneev"}
    merged = C._merge_fragments([
        _frag("we yeah.", named, start="2026-08-17T15:02:03.000Z"),
        _frag("Like, middle September fine.", named, start="2026-08-17T15:02:05.000Z"),
    ])
    assert len(merged) == 1
    assert merged[0]["label"] == "Alexander Korneev"
    assert merged[0]["text"] == "we yeah. Like, middle September fine."
    assert merged[0]["start_time"] == "2026-08-17T15:02:03.000Z"  # first fragment wins


def test_merge_starts_new_block_when_speaker_changes():
    a = {"source": "speaker", "attribution": "them", "name": "Alexander Korneev"}
    b = {"source": "speaker", "attribution": "them", "name": "Erin Wajufos"}
    merged = C._merge_fragments([_frag("Yeah. I think", a), _frag("a Sunday would be good.", b)])
    assert [m["label"] for m in merged] == ["Alexander Korneev", "Erin Wajufos"]


def test_merge_drops_repeated_identical_fragment():
    """Granola occasionally emits the same fragment twice (same text and timestamps)."""
    dup = _frag("as it was supposed to be")
    merged = C._merge_fragments([dup, dict(dup)])
    assert merged[0]["text"] == "as it was supposed to be"


def test_merge_keeps_repeated_text_at_different_timestamps():
    merged = C._merge_fragments([
        _frag("okay", start="2026-08-17T15:02:01.000Z"),
        _frag("okay", start="2026-08-17T15:09:44.000Z"),
    ])
    assert merged[0]["text"] == "okay okay"


def test_merge_labels_unnamed_speakers_by_attribution():
    mine = {"source": "microphone", "attribution": "me"}
    theirs = {"source": "speaker", "attribution": "them"}
    merged = C._merge_fragments([_frag("my line", mine), _frag("their line", theirs)])
    assert [m["label"] for m in merged] == ["Me", "Them"]


def test_merge_prefers_diarization_label_over_attribution():
    sp = {"source": "speaker", "attribution": "them", "diarization_label": "Speaker A"}
    merged = C._merge_fragments([_frag("hi", sp)])
    assert merged[0]["label"] == "Speaker A"


# ─── Transcript markdown ──────────────────────────────────────────────────────

def test_transcript_md_has_frontmatter_and_speaker_lines():
    named = {"source": "speaker", "attribution": "them", "name": "Alexander Korneev"}
    md = C._fmt_transcript_md(NOTE, [_frag("hello there", named)])
    assert md.startswith("---\n")
    assert "note_id: not_6gcBxxxxxxxxxx" in md
    assert "source: granola-api" in md
    assert "**Alexander Korneev** [15:02:01] — hello there" in md


def test_transcript_md_reports_speaker_coverage_for_old_calls():
    """Old calls predate Granola's Meet extension: names must be visibly missing."""
    named = {"source": "speaker", "attribution": "them", "name": "Alexander Korneev"}
    md = C._fmt_transcript_md(NOTE, [_frag("named line", named), _frag("anon line"), _frag("anon two")])
    assert "speakers: [\"Alexander Korneev\"]" in md
    assert "unnamed_fragments: 2" in md


def test_transcript_md_flags_truncation():
    md = C._fmt_transcript_md(NOTE, [_frag("x")], truncated=True)
    assert "transcript_truncated: true" in md


def test_transcript_raw_keeps_every_fragment_unmerged():
    named = {"source": "speaker", "attribution": "them", "name": "Alexander Korneev"}
    frags = [_frag("one", named), _frag("two", named)]
    md = C._fmt_transcript_md(NOTE, frags, raw=True)
    assert md.count("**Alexander Korneev**") == 2


# ─── Summary / note markdown ──────────────────────────────────────────────────

def test_summary_md_is_provider_markdown_verbatim():
    assert C._fmt_summary_md(NOTE) == "## Outcome\n\n- ship it\n"


def test_note_md_wraps_summary_with_frontmatter_and_attendees():
    md = C._fmt_note_md(NOTE)
    assert "title: Strategy call" in md
    assert "Alexander Korneev" in md
    assert "vlad@example.com" in md  # attendee without a name falls back to email
    assert "## Outcome" in md
    assert 'web_url: "https://notes.granola.ai/d/not_6gcBxxxxxxxxxx"' in md  # quoted: value contains ":"


def test_note_md_without_summary_says_so():
    md = C._fmt_note_md({**NOTE, "summary_markdown": None})
    assert "no summary" in md.lower()


# ─── Folder tree ──────────────────────────────────────────────────────────────

def test_folders_md_renders_hierarchy():
    rows = [{"id": "fol_a", "name": "Clients", "parent_folder_id": None},
            {"id": "fol_b", "name": "LynxCap", "parent_folder_id": "fol_a"}]
    md = C._fmt_folders_md(rows)
    assert "Clients" in md
    assert "  - LynxCap" in md or "- LynxCap" in md.split("Clients", 1)[1]


# ─── Dispatch ─────────────────────────────────────────────────────────────────

def test_run_list_resolves_folder_name_to_id():
    args = argparse.Namespace(granola_cmd="list", limit=None, cursor=None, since=None,
                              until=None, updated_after=None, folder="opencall-guru",
                              fmt="human", as_json=False)
    client = MagicMock()
    client.resolve_folder_id.return_value = "fol_b"
    client.list_notes.return_value = {"rows": [], "next_cursor": None, "has_more": False}
    with patch("h2t_ops.connectors.granola.client.GranolaClient", return_value=client):
        C.run(args)
    client.resolve_folder_id.assert_called_once_with("opencall-guru")
    assert client.list_notes.call_args.kwargs["folder_id"] == "fol_b"


def test_run_transcript_md_fetches_note_for_metadata():
    args = argparse.Namespace(granola_cmd="transcript", note_id="not_1", fmt="md",
                              as_json=False, raw=False)
    client = MagicMock()
    client.get_transcript.return_value = {"transcript": [_frag("hi")], "truncated": False}
    client.get_note.return_value = NOTE
    with patch("h2t_ops.connectors.granola.client.GranolaClient", return_value=client):
        out = C.run(args)
    client.get_note.assert_called_once_with("not_1")
    assert "note_id: not_6gcBxxxxxxxxxx" in out


def test_run_transcript_survives_missing_note_metadata():
    from h2t_ops.core.errors import NotFoundError
    args = argparse.Namespace(granola_cmd="transcript", note_id="not_1", fmt="md",
                              as_json=False, raw=False)
    client = MagicMock()
    client.get_transcript.return_value = {"transcript": [_frag("hi")], "truncated": False}
    client.get_note.side_effect = NotFoundError("gone")
    with patch("h2t_ops.connectors.granola.client.GranolaClient", return_value=client):
        out = C.run(args)
    assert "not_1" in out


def test_run_unknown_subcommand_raises_usageerror():
    from h2t_ops.core.errors import UsageError
    args = argparse.Namespace(granola_cmd="teleport")
    with patch("h2t_ops.connectors.granola.client.GranolaClient", return_value=MagicMock()):
        with pytest.raises(UsageError):
            C.run(args)


# ─── Registration ─────────────────────────────────────────────────────────────

def test_register_exposes_expected_subcommands():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="connector")
    C.register(sub)
    ns = parser.parse_args(["granola", "list", "--limit", "3"])
    assert ns.granola_cmd == "list"
    assert ns.limit == 3
    assert ns._handler is C.run


def test_register_supports_transcript_raw_flag():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="connector")
    C.register(sub)
    ns = parser.parse_args(["granola", "transcript", "not_1", "--raw"])
    assert ns.raw is True


# ─── Remaining verbs ──────────────────────────────────────────────────────────

def _run(cmd, client, **kw):
    args = argparse.Namespace(granola_cmd=cmd, **kw)
    with patch("h2t_ops.connectors.granola.client.GranolaClient", return_value=client):
        return C.run(args)


def test_run_auth_check_delegates_to_client():
    client = MagicMock()
    client.auth_check.return_value = True
    assert _run("auth-check", client, as_json=False) is True


def test_run_get_md_renders_note_markdown():
    client = MagicMock()
    client.get_note.return_value = NOTE
    out = _run("get", client, note_id="not_1", fmt="md", as_json=False)
    assert "# Strategy call" in out
    assert "## Outcome" in out


def test_run_get_json_returns_raw_note():
    client = MagicMock()
    client.get_note.return_value = NOTE
    assert _run("get", client, note_id="not_1", fmt="json", as_json=False) is NOTE


def test_run_summary_returns_provider_markdown():
    client = MagicMock()
    client.get_note.return_value = NOTE
    assert _run("summary", client, note_id="not_1", fmt="md", as_json=False) == "## Outcome\n\n- ship it\n"


def test_run_summary_raises_notfound_when_note_has_no_summary():
    from h2t_ops.core.errors import NotFoundError
    client = MagicMock()
    client.get_note.return_value = {**NOTE, "summary_markdown": None, "summary_text": None}
    with pytest.raises(NotFoundError):
        _run("summary", client, note_id="not_1", fmt="md", as_json=False)


def test_run_folders_md_renders_tree():
    client = MagicMock()
    client.list_folders.return_value = {"rows": [{"id": "fol_a", "name": "Clients", "parent_folder_id": None}]}
    out = _run("folders", client, fmt="md", as_json=False)
    assert "Clients (fol_a)" in out


def test_run_webhooks_strips_any_signing_secret():
    """Secrets must never reach stdout, even if the provider starts returning them."""
    client = MagicMock()
    client.list_webhook_endpoints.return_value = {
        "rows": [{"id": "whe_1", "url": "https://hook.example/x", "signing_secret": "whsec_abc"}]
    }
    out = _run("webhooks", client, fmt="human", as_json=False)
    assert "whsec_abc" not in json.dumps(out)
    assert out["rows"][0]["id"] == "whe_1"


def test_run_list_md_renders_table_with_note_ids():
    client = MagicMock()
    client.list_notes.return_value = {
        "rows": [{"id": "not_1", "title": "Call", "created_at": "2026-08-17T15:00:00Z"}],
        "next_cursor": None, "has_more": False,
    }
    out = _run("list", client, limit=None, cursor=None, since=None, until=None,
               updated_after=None, folder=None, fmt="md", as_json=False)
    assert "not_1" in out and "Call" in out


def test_register_exposes_every_documented_subcommand():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="connector")
    C.register(sub)
    for argv in (["granola", "auth-check"], ["granola", "get", "not_1"],
                 ["granola", "summary", "not_1"], ["granola", "folders"],
                 ["granola", "webhooks"]):
        ns = parser.parse_args(argv)
        assert ns._handler is C.run


# ─── sync wiring ──────────────────────────────────────────────────────────────

def test_register_parses_sync_arguments(tmp_path):
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="connector")
    C.register(sub)
    ns = parser.parse_args(["granola", "sync", "--to", str(tmp_path),
                            "--include", "summaries,transcripts", "--since-cursor"])
    assert ns.granola_cmd == "sync"
    assert ns.to == str(tmp_path)
    assert ns.include == "summaries,transcripts"
    assert ns.since_cursor is True


def test_sync_defaults_to_summaries_and_transcripts(tmp_path):
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="connector")
    C.register(sub)
    ns = parser.parse_args(["granola", "sync", "--to", str(tmp_path)])
    assert set(ns.include.split(",")) == {"summaries", "transcripts"}


def test_run_sync_delegates_to_sync_notes(tmp_path):
    client = MagicMock()
    args = argparse.Namespace(granola_cmd="sync", to=str(tmp_path), include="summaries",
                              since=None, since_cursor=False, folder=None, limit=None,
                              cursor_file=None, as_json=False, fmt="human")
    with patch("h2t_ops.connectors.granola.client.GranolaClient", return_value=client), \
            patch("h2t_ops.connectors.granola.sync.sync_notes",
                  return_value={"synced": 2}) as sn:
        out = C.run(args)
    assert out == {"synced": 2}
    assert sn.call_args.kwargs["include"] == {"summaries"}
    assert sn.call_args.kwargs["to"] == Path(str(tmp_path))
