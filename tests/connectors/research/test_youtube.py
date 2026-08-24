"""Tests for the YouTube transcript provider."""
from __future__ import annotations

from unittest.mock import MagicMock

from h2t_ops.connectors.research import youtube


def test_is_youtube_url_watch():
    assert youtube.is_youtube_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ")


def test_is_youtube_url_short():
    assert youtube.is_youtube_url("https://youtu.be/dQw4w9WgXcQ")


def test_is_youtube_url_shorts():
    assert youtube.is_youtube_url("https://youtube.com/shorts/abc123")


def test_is_youtube_url_non_youtube():
    assert not youtube.is_youtube_url("https://derivative.ca/something")
    assert not youtube.is_youtube_url("https://alltd.org/pop-starter-pack/")


def test_extract_video_id_watch():
    vid = youtube._extract_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    assert vid == "dQw4w9WgXcQ"


def test_extract_video_id_short():
    vid = youtube._extract_video_id("https://youtu.be/dQw4w9WgXcQ")
    assert vid == "dQw4w9WgXcQ"


def _fake_segment(text: str, start: float = 0.0):
    seg = MagicMock()
    seg.text = text
    seg.start = start
    return seg


def test_fetch_youtube_ok(monkeypatch):
    segments = [_fake_segment("Hello world."), _fake_segment("Second line.", 1.0)]

    mock_api = MagicMock()
    mock_api.fetch.return_value = segments

    def mock_yt_api():
        return mock_api

    # Mock YouTubeTranscriptApi constructor
    monkeypatch.setattr(youtube, "YouTubeTranscriptApi", mock_yt_api)

    # Mock oEmbed
    def mock_oembed(video_id: str) -> dict:
        return {"title": "Test Video", "author_name": "Test Channel"}

    monkeypatch.setattr(youtube, "_get_oembed", mock_oembed)

    envelope, exit_code = youtube.fetch_youtube(
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        output_dir=None,
        project="test",
    )

    assert exit_code == 0
    assert envelope["status"] == "OK"
    assert envelope["provider_used"] == "youtube_transcript"
    assert "Hello world." in envelope["body_text"]
    assert "Second line." in envelope["body_text"]
    assert envelope["provenance"]["video_id"] == "dQw4w9WgXcQ"
    assert envelope["provenance"]["title"] == "Test Video"
    assert envelope["provenance"]["author_name"] == "Test Channel"
    assert envelope["provenance"]["transcript_segments"] == 2


def test_fetch_youtube_no_transcript(monkeypatch):
    mock_api = MagicMock()
    mock_api.fetch.side_effect = Exception("No transcripts available")

    monkeypatch.setattr(youtube, "YouTubeTranscriptApi", lambda: mock_api)
    monkeypatch.setattr(youtube, "_get_oembed", lambda vid: {})

    envelope, exit_code = youtube.fetch_youtube(
        "https://www.youtube.com/watch?v=NOFOUND123",
        output_dir=None,
        project="test",
    )

    assert exit_code == 1
    assert envelope["status"] == "FAILED"
    assert envelope["provider_used"] == "youtube_transcript"
