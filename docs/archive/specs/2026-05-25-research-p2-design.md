---
title: "Research P2: YouTube Provider, Exa Extensions, Author Resolve, Visual OCR Auto-Capture"
status: "draft"
owner: "Stanislav Glazov"
date: "2026-05-25"
milestone: ""
---
# Research P2: YouTube Provider, Exa Extensions, Author Resolve, Visual OCR Auto-Capture

## Goal

Extend the `h2t-ops:research` connector with four connected capabilities that
share a common provider architecture. All four feed normalized artifacts to POS
through the existing fetch envelope contract.

## Scope

| Layer | Task | Issues |
|-------|------|--------|
| 0 (prereq) | `h2t-screenshot` CLI entry point in h2t-tools | — |
| 1 (independent) | Exa `findSimilar` + `/answer` endpoints | #182 |
| 1 (independent) | `youtube.py` provider + URL dispatch in `fetch.py` | — |
| 2 (uses Layer 1) | `author_resolve.py` — name → channel cascade | #99 |
| 3 (uses Layer 0) | `visual-ocr --url` auto-capture mode | #105 |

## Architecture

### File structure

```
h2t_ops/connectors/research/
  exa.py              ← add find_similar(), answer()
  fetch.py            ← add URL_PROVIDERS dispatch table + YouTube branch
  youtube.py          ← NEW: YouTube transcript provider
  author_resolve.py   ← NEW: author resolution cascade
  visual_ocr.py       ← add capture_and_ocr(url)
  commands.py         ← add similar, answer subcommands; extend visual-ocr with --url

C:/dev/h2t-tools/
  pyproject.toml      ← NEW: packages h2t_tools, exposes h2t-screenshot entry point
  h2t_tools/
    screenshot.py     ← moved from scripts/screenshot/screenshot.py
```

### URL dispatch table in `fetch.py`

```python
URL_PROVIDERS: list[tuple[Callable[[str], bool], Callable]] = [
    (_is_youtube_url, _fetch_youtube),
    # (_is_instagram_url, _fetch_instagram),  # future
]

def fetch_url(url, ...):
    for matcher, provider in URL_PROVIDERS:
        if matcher(url):
            return provider(url, ...)
    # fallback: generic ladder (direct → jina → visual_ocr rescue)
```

Adding a new provider = one module + one entry in `URL_PROVIDERS`. The ladder
does not change. POS calls `research fetch --url <any_url>` and receives a
normalized envelope regardless of which provider handled it.

### POS contract

Every provider returns the same envelope shape:

```json
{
  "status": "OK | DEGRADED | FAILED",
  "provider_used": "youtube_transcript | exa_similar | exa_answer | visual_ocr",
  "body_text": "...",
  "provenance": {
    "text_source": "...",
    ...provider-specific fields...
  }
}
```

POS does not need to know which provider was used. It can inspect
`provenance.text_source` if it needs to differentiate transcript vs HTML vs OCR.

## Layer 0 — h2t-tools packaging

### Problem

`capture_and_ocr(url)` needs to call the screenshot script. Hardcoded paths
are fragile across machines. The right fix is to make `h2t-screenshot` a
proper CLI entry point.

### Solution

Create `C:/dev/h2t-tools/pyproject.toml`:

```toml
[project]
name = "h2t-tools"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = ["playwright>=1.44"]

[project.scripts]
h2t-screenshot = "h2t_tools.screenshot:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

Move `scripts/screenshot/screenshot.py` → `h2t_tools/screenshot.py`.

Install: `uv tool install --editable C:/dev/h2t-tools`

After install, `capture_and_ocr` calls `h2t-screenshot <url> --format desktop
--out <tmp_dir>` with no path knowledge. `ConfigError` if `h2t-screenshot` is
not on PATH.

## Layer 1 — Exa extensions (#182)

### `exa.py`: `find_similar()`

```python
def find_similar(
    url: str,
    *,
    api_key: str,
    num_results: int = 10,
    include_domains: list[str] | None = None,
    exclude_domains: list[str] | None = None,
) -> tuple[dict, int]:
    # POST /findSimilar
    # body: {url, numResults, contents: {highlights: {maxCharacters: 4000}}}
    # reuses call_exa(), build_envelope()
    # envelope meta: source_url, num_results_requested, num_results_returned
```

### `exa.py`: `answer()`

```python
def answer(
    query: str,
    *,
    api_key: str,
) -> tuple[dict, int]:
    # POST /answer
    # body: {query, text: true}
    # response shape: {answer: str, citations: [{url, title, ...}]}
    # envelope: status, answer_text, citations[], meta.query
```

### `commands.py` additions

```bash
h2t-ops research similar --url <url> [--num-results N] [--json]
h2t-ops research answer --query "..." [--json]
h2t-ops research resolve-author --name "..." [--keywords "..."] [--hint youtube] [--json]
```

All reuse `add_fmt()`, `ResearchClient`.

## Layer 1 — YouTube provider

### `youtube.py`

```python
def is_youtube_url(url: str) -> bool:
    # matches: youtube.com/watch?v=, youtu.be/, youtube.com/shorts/

def fetch_youtube(
    url: str,
    *,
    output_dir: Path | None,
    project: str,
) -> tuple[dict, int]:
    # 1. extract video_id
    # 2. oEmbed → author_name, title (urllib, no API key)
    # 3. YouTubeTranscriptApi → transcript segments
    #    priority: ru → en → any available
    # 4. join segments → body_text
    # 5. return fetch envelope
```

**Envelope:**

```json
{
  "status": "OK | DEGRADED | FAILED",
  "provider_used": "youtube_transcript",
  "body_text": "<full transcript as plain text>",
  "provenance": {
    "text_source": "youtube_transcript",
    "video_id": "...",
    "author_name": "...",
    "title": "...",
    "language": "ru | en | ...",
    "transcript_segments": 142
  }
}
```

DEGRADED when transcript is available but oEmbed metadata fails.
FAILED when no transcript is available for the video.

**Dependency:** `youtube-transcript-api` — hard dep in h2t-skills `pyproject.toml`.

`is_youtube_url` is registered in `fetch.py` `URL_PROVIDERS` dispatch table.

## Layer 2 — Author resolution (#99)

### `author_resolve.py`

```python
def resolve_author(
    name: str,
    *,
    api_key: str,
    hint: str | None = None,       # "youtube", "github", etc.
    keywords: list[str] | None = None,  # e.g. ["TouchDesigner", "POP", "GLSL"]
) -> dict:
```

**Resolution cascade:**

1. **Exa people search** — `"{name} TouchDesigner"` with `mode=people`. Extract
   YouTube channel URLs from result highlights.
2. **Handle guesses** — try `youtube.com/@{name}`, `youtube.com/@{name.lower()}`,
   `youtube.com/@{name.replace(" ", "")}`. Validate each via oEmbed
   (`urllib`, no API key). First 200 OK with `author_name` → confirmed.
3. **AllTD uploader page** — `https://alltd.org/uploader/{handle}/` via
   `fetch.py` ladder. Check status OK and body length > threshold.

Each step appends to `resolution_path`. Stops at first `confirmed` result.

**Output:**

```json
{
  "name": "Acidbourbon",
  "channel_url": "https://youtube.com/@acidbourbon",
  "author_confirmed": "Acidbourbon",
  "resolution_path": [
    "exa_people: no channel URL in results",
    "handle_guess @Acidbourbon: oembed confirmed"
  ],
  "confidence": "confirmed | likely | not_found"
}
```

`confidence: not_found` is **not an error** — exit 0, honest result.

**CLI:**

```bash
h2t-ops research resolve-author --name "Acidbourbon" \
  --keywords "TouchDesigner,POP,GLSL" --json
```

## Layer 3 — Visual OCR auto-capture (#105)

### `visual_ocr.py`: `capture_and_ocr()`

```python
def capture_and_ocr(
    url: str,
    *,
    output_dir: Path,
    project: str,
) -> tuple[dict, int]:
    # 1. subprocess.run(["h2t-screenshot", url, "--format", "desktop", "--out", tmp_dir])
    #    ConfigError if h2t-screenshot not on PATH
    # 2. parse stdout → image_path
    # 3. extract_text_from_image(image_path) → existing OCR pipeline
    # 4. build_visual_ocr_envelope(url=url, ...)
    # 5. cleanup tmp PNG
    # 6. write artifact files via build_visual_ocr_artifact_paths()
```

No sidecar validation for `--url` mode — user explicitly requested visual
rescue.

### `commands.py` extension

```bash
# Existing (unchanged):
h2t-ops research visual-ocr --fetch-sidecar X.sources.json --image-path X.png

# New --url mode:
h2t-ops research visual-ocr --url https://alltd.org/...
```

`--fetch-sidecar` and `--image-path` become mutually exclusive with `--url`.

Output envelope is identical to existing visual-ocr: `needs_review=true`,
`quote_safe=false`, `canonical=false`.

## Dependencies

### h2t-skills `pyproject.toml` additions

```toml
dependencies = [
  ...existing...
  "youtube-transcript-api",
  "rapidocr-onnxruntime",
]
```

Both are hard deps — no `try/except ImportError` in runtime code.

### h2t-tools

New `pyproject.toml` with `h2t-screenshot` entry point (see Layer 0).
Install once: `uv tool install --editable C:/dev/h2t-tools`.

## Error handling

| Code | Meaning |
|------|---------|
| 0 | OK or DEGRADED (data present, possibly partial) |
| 1 | Provider error |
| 2 | Usage error |
| 3 | Config error (h2t-screenshot not on PATH, etc.) |
| 4 | Auth error (Exa 401/403) |
| 6 | Network error |

## Testing

All unit tests: **no network**. Fixtures / mocks only.

| Module | Mock target |
|--------|------------|
| `exa.py` similar/answer | `call_exa()` → fixed response dict |
| `youtube.py` | `YouTubeTranscriptApi.fetch()` + oEmbed `urllib.urlopen` |
| `author_resolve.py` | `call_exa()` + oEmbed urllib + AllTD fetch ladder |
| `visual_ocr.py` capture | `subprocess.run()` → fake image path; existing OCR mocks |

Smoke tests in `tests/smoke/` (network, optional CI skip):

```bash
h2t-ops research similar --url https://derivative.ca --json
h2t-ops research answer --query "TouchDesigner POP operators" --json
h2t-ops research fetch --url https://youtube.com/watch?v=<known_id> --json
h2t-ops research visual-ocr --url https://alltd.org/pop-starter-pack-touchdesigner/ --json
h2t-ops research resolve-author --name "Acidbourbon" --keywords "TouchDesigner" --json
```

## Acceptance

- [ ] `research similar` and `research answer` return standard envelopes
- [ ] `research fetch <youtube_url>` routes to `youtube_transcript` provider
- [ ] `research resolve-author --name X` returns confidence + resolution_path
- [ ] `research visual-ocr --url X` captures screenshot and runs OCR without manual image
- [ ] `h2t-screenshot` available as CLI entry point after h2t-tools install
- [ ] `youtube-transcript-api` and `rapidocr-onnxruntime` in h2t-skills deps
- [ ] All unit tests pass without network
- [ ] Smoke tests recorded for the five commands above

## Build order

1. **Layer 0**: h2t-tools `pyproject.toml` + move `screenshot.py` + install
2. **Layer 1** (parallel): Exa `find_similar`/`answer` + `youtube.py` provider
3. **Layer 2**: `author_resolve.py` (after Layer 1 Exa is done)
4. **Layer 3**: `visual-ocr --url` (after Layer 0 is done)
