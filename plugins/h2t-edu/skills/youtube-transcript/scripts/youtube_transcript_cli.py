#!/usr/bin/env python3
"""YouTube Transcript Fetcher — extracts transcript + chapters from YouTube."""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path.home() / '.dor' / 'secrets.env', override=False)

DOR_ROOT = Path(os.environ.get('DOR_ROOT', Path.home() / 'Projects' / 'DOR'))
VAULT_ROOT = Path(os.environ.get('VAULT_ROOT',
    DOR_ROOT / 'vault' if DOR_ROOT.exists() else Path.home() / '.dor' / 'vault'))


def get_video_id(url_or_id: str) -> str:
    """Extract video ID from URL or return as-is if already an ID."""
    patterns = [
        r'(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})',
        r'^([a-zA-Z0-9_-]{11})$',
    ]
    for pattern in patterns:
        m = re.search(pattern, url_or_id)
        if m:
            return m.group(1)
    raise ValueError(f"Cannot extract video ID from: {url_or_id}")


def get_video_metadata(video_id: str) -> dict:
    """Get title and author via oEmbed API (no API key needed)."""
    url = f'https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json'
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
            return {
                'title': data.get('title', 'Unknown'),
                'author': data.get('author_name', 'Unknown'),
            }
    except Exception as e:
        print(f"Warning: could not fetch metadata: {e}", file=sys.stderr)
        return {'title': 'Unknown', 'author': 'Unknown'}


def get_chapters(video_id: str) -> list:
    """Scrape chapters from YouTube page ytInitialData. Returns [] if none found."""
    url = f'https://www.youtube.com/watch?v={video_id}'
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            html = r.read().decode('utf-8')
    except Exception as e:
        print(f"Warning: could not fetch page for chapters: {e}", file=sys.stderr)
        return []

    match = re.search(r'var ytInitialData = ({.+?});</script>', html, re.DOTALL)
    if not match:
        print("Warning: ytInitialData not found", file=sys.stderr)
        return []

    try:
        data = json.loads(match.group(1))
        markers_map = (
            data['playerOverlays']['playerOverlayRenderer']
            ['decoratedPlayerBarRenderer']['decoratedPlayerBarRenderer']
            ['playerBar']['multiMarkersPlayerBarRenderer']['markersMap']
        )
        for item in markers_map:
            if item.get('key') == 'DESCRIPTION_CHAPTERS':
                chapters = []
                for c in item['value']['chapters']:
                    try:
                        chapters.append({
                            'title': c['chapterRenderer']['title']['simpleText'],
                            'start_ms': c['chapterRenderer']['timeRangeStartMillis'],
                        })
                    except (KeyError, TypeError):
                        continue
                return chapters
    except (KeyError, TypeError):
        pass

    return []


def get_transcript(video_id: str, preferred_lang: str | None = None) -> list:
    """Fetch transcript segments. Priority: preferred_lang → ru → en → any."""
    from youtube_transcript_api import YouTubeTranscriptApi

    api = YouTubeTranscriptApi()
    lang_priority = []
    if preferred_lang:
        lang_priority.append([preferred_lang])
    for default_lang in ['ru', 'en']:
        if default_lang != preferred_lang:
            lang_priority.append([default_lang])

    for langs in lang_priority:
        try:
            return list(api.fetch(video_id, languages=langs))
        except Exception:
            continue

    # Fallback: try any available transcript
    try:
        transcript_list = api.list(video_id)
        transcript = next(iter(transcript_list))
        print(f"Warning: using fallback transcript language: {transcript.language_code}", file=sys.stderr)
        return list(transcript.fetch())
    except Exception as e:
        raise RuntimeError(f"No transcript available for video {video_id}: {e}")


def format_time(ms: int) -> str:
    """Format milliseconds as HH:MM:SS or MM:SS."""
    s = ms // 1000
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    if h:
        return f"{h:02d}:{m:02d}:{sec:02d}"
    return f"{m:02d}:{sec:02d}"


def slugify(text: str, max_len: int = 40) -> str:
    """Convert text to filesystem-safe slug."""
    text = re.sub(r'[^\w\s-]', '', text).strip()
    text = re.sub(r'\s+', '-', text).lower()
    return text[:max_len]


def build_markdown(video_id: str, meta: dict, chapters: list, segments: list, project: str | None = None) -> str:
    """Build full markdown document with chapters-grouped transcript."""
    today = datetime.now().strftime('%Y-%m-%d')
    url = f"https://www.youtube.com/watch?v={video_id}"

    # Frontmatter
    lines = [
        "---",
        "source: youtube",
        f"video_id: {video_id}",
        'title: "' + meta["title"].replace('"', '\\"') + '"',
        'author: "' + meta["author"].replace('"', '\\"') + '"',
        f"url: {url}",
        f"date: {today}",
    ]
    if project:
        lines += [f"project: {project}", "type: ref"]
    lines += ["---", ""]

    # Chapters TOC
    if chapters:
        lines.append("## Chapters")
        lines.append("")
        for ch in chapters:
            lines.append(f"- [{format_time(ch['start_ms'])}] {ch['title']}")
        lines.append("")

    # Transcript
    lines.append("## Transcript")
    lines.append("")

    if chapters:
        import bisect
        # Assign each segment to a chapter by timestamp using binary search
        chapter_starts = [ch['start_ms'] for ch in chapters]
        chapter_buckets = [[] for _ in chapters]
        for seg in segments:
            seg_ms = int(seg.start * 1000)
            # bisect_right gives insertion point; subtract 1 to get the chapter this seg belongs to
            idx = bisect.bisect_right(chapter_starts, seg_ms) - 1
            if idx < 0:
                idx = 0
            chapter_buckets[idx].append(seg.text)

        for i, ch in enumerate(chapters):
            lines.append(f"### [{format_time(ch['start_ms'])}] {ch['title']}")
            lines.append("")
            if chapter_buckets[i]:
                lines.append(" ".join(chapter_buckets[i]))
            lines.append("")
    else:
        # No chapters — group by 2-minute intervals
        INTERVAL_MS = 120_000
        current_marker = 0
        buffer = []

        for seg in segments:
            seg_ms = int(seg.start * 1000)
            if seg_ms >= current_marker + INTERVAL_MS:
                if buffer:
                    lines.append(f"### [{format_time(current_marker)}]")
                    lines.append("")
                    lines.append(" ".join(buffer))
                    lines.append("")
                current_marker = (seg_ms // INTERVAL_MS) * INTERVAL_MS
                buffer = []
            buffer.append(seg.text)

        if buffer:
            lines.append(f"### [{format_time(current_marker)}]")
            lines.append("")
            lines.append(" ".join(buffer))
            lines.append("")

    return "\n".join(lines)


def get_output_path(video_id: str, meta: dict, project: str | None) -> Path:
    """Determine output path based on mode."""
    today = datetime.now().strftime('%Y-%m-%d')

    if project:
        out_dir = VAULT_ROOT / '100 Inbox'
        out_dir.mkdir(parents=True, exist_ok=True)
        safe_title = meta['title'][:50].replace('/', '-').rstrip(' -')
        filename = f"{{{project}}} ref {safe_title} \u2013 {today}.md"
        return out_dir / filename
    else:
        out_dir = DOR_ROOT / 'context' / 'youtube'
        out_dir.mkdir(parents=True, exist_ok=True)
        slug = slugify(meta['title'])
        filename = f"{today}-{video_id}-{slug}.md"
        return out_dir / filename


def extract_frames(
    video_url: str,
    video_id: str,
    chapters: list,
    out_dir: Path,
    interval: int | None = None,
    video_duration_ms: int | None = None,
) -> list[Path]:
    """Extract PNG frames at chapter timestamps using yt-dlp + ffmpeg.

    Args:
        video_url: YouTube URL
        video_id: YouTube video ID
        chapters: list of {'title': str, 'start_ms': int}
        out_dir: directory to save frames into (created if needed)
        interval: if set, extract a frame every N seconds within each chapter
        video_duration_ms: total video duration in ms (needed for interval mode last chapter)

    Returns:
        list of saved frame paths
    """
    for tool in ('yt-dlp', 'ffmpeg'):
        if not shutil.which(tool):
            print(f"ERROR: {tool} not found on PATH", file=sys.stderr)
            return []

    out_dir.mkdir(parents=True, exist_ok=True)
    saved: list[Path] = []

    # Build list of (timestamp_ms, label) pairs
    timestamps: list[tuple[int, str]] = []

    if interval and interval > 0:
        for i, ch in enumerate(chapters):
            start = ch['start_ms']
            if i + 1 < len(chapters):
                end = chapters[i + 1]['start_ms']
            elif video_duration_ms:
                end = video_duration_ms
            else:
                end = start + 300_000  # fallback: 5 min
            t = start
            frame_idx = 0
            while t < end:
                timestamps.append((t, f"{i:02d}-{frame_idx:03d}"))
                t += interval * 1000
                frame_idx += 1
    else:
        for i, ch in enumerate(chapters):
            timestamps.append((ch['start_ms'], f"{i:02d}"))

    if not timestamps:
        print("No timestamps for frame extraction", file=sys.stderr)
        return []

    # Download video once to temp file
    with tempfile.TemporaryDirectory() as tmp:
        tmp_video = Path(tmp) / "video.mp4"
        print("Downloading video for frame extraction...", file=sys.stderr)
        dl_cmd = [
            'yt-dlp', video_url,
            '-f', 'bestvideo[height<=720]+bestaudio/best[height<=720]',
            '--merge-output-format', 'mp4',
            '-o', str(tmp_video),
            '--no-playlist',
            '--quiet',
        ]
        result = subprocess.run(dl_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"yt-dlp error: {result.stderr}", file=sys.stderr)
            return []

        # Extract frames at each timestamp
        for ts_ms, label in timestamps:
            ts_sec = ts_ms / 1000
            h, rem = divmod(int(ts_sec), 3600)
            m, s = divmod(rem, 60)
            ts_str = f"{h:02d}:{m:02d}:{s:02d}"
            ts_filename = f"{m:02d}m{s:02d}s" if not h else f"{h}h{m:02d}m{s:02d}s"

            frame_path = out_dir / f"{video_id}-{label}-{ts_filename}.png"
            ff_cmd = [
                'ffmpeg', '-y',
                '-ss', ts_str,
                '-i', str(tmp_video),
                '-frames:v', '1',
                '-q:v', '2',
                str(frame_path),
                '-loglevel', 'error',
            ]
            result = subprocess.run(ff_cmd, capture_output=True, text=True)
            if result.returncode == 0 and frame_path.exists():
                saved.append(frame_path)
                print(f"  Frame: {frame_path.name}", file=sys.stderr)
            else:
                print(f"  Failed: {label} @ {ts_str}: {result.stderr}", file=sys.stderr)

    return saved


def get_video_duration_ms(video_url: str) -> int | None:
    """Get video duration via yt-dlp --print duration."""
    try:
        result = subprocess.run(
            ['yt-dlp', '--print', 'duration', '--no-playlist', '--quiet', video_url],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode == 0 and result.stdout.strip():
            return int(float(result.stdout.strip()) * 1000)
    except Exception:
        pass
    return None


def main():
    parser = argparse.ArgumentParser(description='YouTube Transcript Fetcher')
    parser.add_argument('url', help='YouTube URL or video ID')
    parser.add_argument('--project', help='Project ID (routes to vault/100 Inbox/ with naming convention)')
    parser.add_argument('--print', dest='print_only', action='store_true', help='Print to stdout only')
    parser.add_argument('--lang', default=None, help='Preferred language code (default: ru then en)')
    parser.add_argument('--frames', action='store_true', help='Extract PNG frames at chapter timestamps')
    parser.add_argument('--frames-interval', type=int, default=None, metavar='SEC',
                        help='Extract a frame every N seconds within each chapter (implies --frames)')
    args = parser.parse_args()

    if args.frames_interval:
        args.frames = True

    video_id = get_video_id(args.url)
    print(f"Fetching: {video_id}", file=sys.stderr)

    meta = get_video_metadata(video_id)
    print(f"Title: {meta['title']}", file=sys.stderr)

    chapters = get_chapters(video_id)
    print(f"Chapters: {len(chapters)}", file=sys.stderr)

    segments = get_transcript(video_id, args.lang)
    print(f"Segments: {len(segments)}", file=sys.stderr)

    markdown = build_markdown(video_id, meta, chapters, segments, args.project)

    if args.print_only:
        print(markdown)
        if args.frames:
            print("Warning: --frames ignored in --print mode", file=sys.stderr)
        return

    out_path = get_output_path(video_id, meta, args.project)
    out_path.write_text(markdown, encoding='utf-8')
    print(f"Saved: {out_path}", file=sys.stderr)
    print(str(out_path))

    # Frame extraction (on-demand only)
    if args.frames and chapters:
        url = f"https://www.youtube.com/watch?v={video_id}"
        frames_dir = out_path.parent / 'frames'
        duration = None
        if args.frames_interval:
            duration = get_video_duration_ms(url)
        saved_frames = extract_frames(
            url, video_id, chapters, frames_dir,
            interval=args.frames_interval,
            video_duration_ms=duration,
        )
        print(f"Frames: {len(saved_frames)} saved to {frames_dir}", file=sys.stderr)
    elif args.frames and not chapters:
        print("Warning: --frames requires chapters, none found", file=sys.stderr)


if __name__ == '__main__':
    main()
