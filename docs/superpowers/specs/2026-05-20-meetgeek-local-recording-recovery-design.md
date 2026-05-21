# MeetGeek Local Recording Recovery — Design

**Issue:** #149
**Date:** 2026-05-20
**Status:** DRAFT — awaiting review before implementation

---

## 1. Current Workflow Inventory

All recovery logic lives in one file:
`plugins/h2t-ops/skills/meetgeek/scripts/meetgeek_cli.py`

### 1.1 `convert`

| Aspect | Detail |
|--------|--------|
| Input | Any ffmpeg-readable media (webm, mp4, mkv, mov, …) |
| Output | `.mp4` (default) or `.m4a` (`--audio-only`) |
| Probe | `ffmpeg -i <path> -f null -` → parses stderr for audio_streams, has_video, duration |
| Mix modes | `amix` (default, mixes all audio tracks), `first` (use stream 0:a:0 only), `keep` (pass all tracks through unchanged) |
| Default output path | `~/.dor/lake/meetgeek/uploads-staging/{YYYY-MM-DD}/{stem}.{mp4,m4a}` |
| Skip-if-cached | If output exists and `> 1024` bytes, skip silently and return path |
| ffmpeg binary | Via `imageio_ffmpeg.get_ffmpeg_exe()` — no system ffmpeg required |
| `--probe` mode | Print JSON probe result and exit 0 |

Multi-track logic detail:
- `≤1 audio stream OR mix_mode=first` → `-map 0:v? -map 0:a:0?` (single-stream fast path)
- `mix_mode=keep` → `-map 0` (pass-through all tracks)
- `mix_mode=amix` (default for ≥2 streams) → `-filter_complex "amix=inputs=N:..."`

Critical note: when any `-map` is given, ffmpeg auto-mapping is disabled. The code explicitly maps both video and audio to avoid silent video-only output.

### 1.2 `drive-upload`

| Aspect | Detail |
|--------|--------|
| Auth | Shared OAuth token at `~/.config/google-calendar-mcp/tokens.json` — same as Google Calendar MCP and `drive_cli.py` |
| Folder creation | Hierarchical `find-or-create` by name; default path: `"MeetGeek Uploads/{YYYY-MM-DD}"` |
| Idempotency | Checks file by name within folder; if exists, returns existing entry without re-uploading |
| Public sharing | `anyone/reader` permission set on every upload (idempotent re-apply on existing) |
| Download URL | `drive.usercontent.google.com/download?id=...&export=download&confirm=t` — avoids virus-scan HTML interstitial for files >100 MB |
| Output | JSON: `{drive_id, web_url, download_url, created: bool}` |

### 1.3 `upload --download-url` (compatibility path)

Already migrated in #134. Calls `_submit_url_via_h2t_ops(download_url, title, language)` → subprocess `h2t-ops meetgeek submit-url <URL> --json`. No local file handling. Thin compatibility shim.

### 1.4 `upload --from-file` (recovery pipeline orchestrator)

Three-stage pipeline with manifest-based resume:

**Input expansion:**
- Directory → `rglob("*.webm")` (recursive)
- Direct file → single file
- Otherwise → `glob.glob(str(path), recursive=True)`

**Stage machine per file:**

| Stage | Skip condition | Manifest status on success | Manifest status on failure |
|-------|---------------|---------------------------|---------------------------|
| 1: Convert | `rec.status ∈ {converted, in-drive, submitted} AND mp4_path exists AND size > 1024` | `converted` | `convert-failed` |
| 2: Drive upload | `rec.status ∈ {in-drive, submitted} AND drive_id AND drive_download_url` | `in-drive` | `drive-failed` |
| 3: Submit (via h2t-ops) | — | `submitted` | `upload-rejected` |

**Manifest:** `~/.dor/lake/meetgeek/uploads-staging/manifest.jsonl`
Key: `source_webm` (resolved absolute path). Last-line-wins per key.
`--skip-existing` (default on): checks `status=submitted AND same size AND same mtime`.
`--dry-run`: prints intent without executing.

**Title inference:** `meetgeek-recording-YYYY-MM-DDTHH-MM-ss-NZ` → `"Meeting YYYY-MM-DD HH:MM UTC"`.
Fallback: `"Meeting {stem}"`.

**Drive URL regeneration:** On resume, `download_url` is recomputed from `drive_id` rather than reusing cached value — lets old manifest entries pick up URL fixes without re-uploading.

### 1.5 `sync`

Bulk pull from MeetGeek API → local lake directory. **Not part of local recording recovery** — pulls already-processed meetings from the API. Documents for completeness.

| Aspect | Detail |
|--------|--------|
| Include types | `transcripts` (default), `summaries`, `highlights`, `insights`, `recordings` |
| Cursor | `~/.dor/lake/_cursors/meetgeek.json` — timestamp-based, last_seen_ts |
| Output | `{lake}/{type}/{meeting_id}.{md,json}` pairs + `manifest.jsonl` |
| Dedup | manifest IDs set; cursor timestamp filter |
| Watch mode | `--watch N` — re-run every N seconds (min 30) |

### 1.6 `webhook-server`

Minimal HTTP server. Dumps incoming POSTs as JSON to disk. **Not part of local recording recovery.** Documents for completeness.

| Aspect | Detail |
|--------|--------|
| Port | 8765 (configurable) |
| Auth | Optional `X-Webhook-Secret` header check |
| Output | `~/.dor/lake/meetgeek/webhooks/{uuid}.json` |
| GET | Health probe, returns 200 |

---

## 2. Non-Regression Requirements

1. `meetgeek_cli.py convert --help` exits 0 without errors.
2. `meetgeek_cli.py convert <file> --probe` prints valid JSON and exits 0.
3. `meetgeek_cli.py drive-upload <file> --help` exits 0.
4. `meetgeek_cli.py upload --help` exits 0.
5. `meetgeek_cli.py upload --from-file <dir> --dry-run` prints a plan and exits 0 (no network, no Drive auth required).
6. `meetgeek_cli.py upload --download-url <url>` delegates to `h2t-ops meetgeek submit-url` unchanged.
7. Manifest resume: a file in `status=in-drive` on first run reaches `status=submitted` on retry without re-converting or re-uploading to Drive.
8. `--skip-existing` skips `status=submitted` files with matching size+mtime without executing any stage.
9. `sync` and `webhook-server` remain unaffected by any extraction.
10. All existing `test_meetgeek_cli.py` tests pass.

---

## 3. Boundary Definitions

### 3.1 h2t-ops / h2t-skills owns (provider-specific recovery)

- Media conversion: probe + encode (convert)
- Drive upload as intermediate hosting (drive-upload)
- URL submission to MeetGeek (upload --download-url → submit-url)
- Recovery pipeline orchestration (upload --from-file)
- Manifest state machine + resume semantics
- Artifact emission: transcript, summary, highlights, insights in structured form
- Preserving speaker diarization labels from MeetGeek API transcript
- Emitting artifact envelope for POS intake (see §6)

### 3.2 POS owns (provider-neutral intake)

- Receiving and storing artifact envelopes by `meeting_key`
- Multiple transcript artifacts for the same meeting (e.g. MeetGeek + Granola)
- Quality and trust scoring across providers
- Reconciliation / fusion of conflicting transcripts
- Interpretation: extracting captures, tasks, decisions from transcripts
- Journal and knowledge base promotion
- Provider-neutral meeting schema

### 3.3 Hard boundary — h2t-ops must NOT

- Write POS journal entries
- Accept MeetGeek action items as tasks
- Decide follow-ups or decisions
- Implement transcript fusion or provider-neutral schema
- Integrate Granola, Krisp, or local ASR (out of scope for #149)

---

## 4. What Can Be Replaced by Connectors

### By #134 (MeetGeek connector) — already done

`_submit_url_via_h2t_ops` delegates to `h2t-ops meetgeek submit-url`. Stage 3 of the pipeline is already connector-backed. No further action needed for submit.

### By #133 (Drive connector) — conditional, requires parity work

#133 has shipped, but the current `h2t-ops drive upload` **does not yet cover** the semantics required by the recovery pipeline:

| Capability | Legacy `_drive_upload_file` | `h2t-ops drive upload` (current) |
|-----------|----------------------------|----------------------------------|
| Folder hierarchy `MeetGeek Uploads/{date}` | ✓ | ✗ |
| Public sharing (anyone/reader) | ✓ | ✗ |
| `drive.usercontent.google.com` download URL | ✓ | ✗ |
| Idempotent by filename within folder | ✓ | ✗ |

**Phase 2 is NOT unblocked by #133 shipping.** Delegation to `h2t-ops drive upload` requires the Drive connector to gain recovery-compatible upload semantics first. Options:

- (a) Extend `h2t-ops drive upload` with `--public --folder` flags and usercontent URL output — tracked as a follow-up to #133.
- (b) Keep `_drive_upload_file` embedded in `recovery.py` permanently; Drive connector duplication is acceptable given the scoped use case.

**Decision deferred.** Phase 2 remains a future follow-up, not a deliverable of #149. The legacy embedded Drive logic stays unchanged until parity is confirmed.

### What must stay as coordinator logic

`_process_one_for_upload` is pure orchestration — stage sequencing, manifest reads/writes, error classification, resume logic. This is not connector logic. It must remain in a recovery coordinator script regardless of whether individual stages delegate outward.

---

## 5. Staged Extraction Plan

### Phase 0 — No-op: extract design + tests (this document, #149 T0)

- Write this design doc.
- Confirm existing `--help` and `--probe` and `--dry-run` exit 0.
- Confirm test suite passes.
- No code changes.

### Phase 1 — Extract recovery coordinator into separate module

Create `plugins/h2t-ops/skills/meetgeek/scripts/recovery.py`:
- `convert_media(src, *, audio_only, mix_mode, output_path) → Path`
- `drive_upload_file(path, *, folder) → DriveResult`
- `process_one(src_path, *, language, title_override, audio_only, mix_mode, manifest_path) → dict`
- `read_manifest(path) → dict[str, dict]`
- `append_manifest(record, path) → None`

`meetgeek_cli.py` becomes a thin CLI wrapper: `cmd_convert` / `cmd_drive_upload` / `cmd_upload` delegate to `recovery.py`. No behavior change.

**Benefit:** Recovery logic is testable in isolation without argparse; makes it possible to call from skill code directly.

### Phase 2 — Drive stage → connector delegation (after #133)

Replace `_drive_upload_file(...)` call in `_process_one_for_upload` with:
```python
subprocess.run(["h2t-ops", "drive", "upload", str(mp4_path), "--json"], ...)
```

Keep internal `_drive_upload_file` as fallback (or remove once #133 is verified stable). Manifest schema unchanged.

### Phase 3 — Skill command (optional, NOT h2t-ops connector)

If useful, expose recovery as a skill command (e.g. via `meetgeek_cli.py` wrapper or a dedicated `recover.py` script) with sane defaults: `--language ru`, auto-detect staging dir.

**Explicitly forbidden:** `h2t-ops meetgeek recover` as a connector verb. Recovery = local FS + Drive + manifest + coordinator workflow. It must not live in `h2t_ops.connectors.meetgeek`. `h2t-ops meetgeek submit-url` remains the only provider-write stage delegated to the connector. All pipeline coordination stays in the skill/coordinator layer.

---

## 6. Artifact Envelope Proposal

Two distinct artifacts at different lifecycle stages:

### 6.1 Stage 3 artifact: `recording_submission_artifact`

Emitted immediately after submit succeeds. At this point there is no meeting_id from MeetGeek, no transcript, no speaker labels. The envelope captures what we know: where the recording came from and that it was submitted.

```json
{
  "schema_version": "0.1",
  "artifact_type": "recording_submission_artifact",
  "provider": "meetgeek",
  "provenance": "local-recording-recovery",
  "source_file": "<absolute path to original recording>",
  "source_size_bytes": 0,
  "source_mtime": "<ISO 8601 UTC>",
  "converted_file": "<absolute path to converted mp4/m4a>",
  "drive_id": "<Google Drive file ID>",
  "drive_download_url": "<drive.usercontent.google.com URL>",
  "title": "<inferred or user-supplied>",
  "language": "<language code or null>",
  "submitted_at": "<ISO 8601 UTC>",
  "meetgeek_meeting_id": null,
  "notes": "<free-form string for human review>"
}
```

**Location:** `~/.dor/lake/meetgeek/uploads-staging/{YYYY-MM-DD}/{stem}.submission.json`

**POS contract:** POS stores this as evidence that a recording was submitted. Does not contain transcript or decisions. POS must not act on it until a `meeting_transcript_artifact` is linked.

---

### 6.2 Post-fetch artifact: `meeting_transcript_artifact`

Emitted separately after `h2t-ops meetgeek transcript <meeting_id>` fetch succeeds (via `sync` or explicit `fetch`). This is when we have speaker diarization and full content.

```json
{
  "schema_version": "0.1",
  "artifact_type": "meeting_transcript_artifact",
  "meeting_key": "meetgeek/<meeting_id>",
  "provider": "meetgeek",
  "provenance": "local-recording-recovery",
  "submission_ref": "<path to recording_submission_artifact>",
  "fetched_at": "<ISO 8601 UTC>",
  "meeting_meta": {
    "title": "<string>",
    "date": "<YYYY-MM-DD>",
    "timestamp_start_utc": "<ISO 8601 UTC>",
    "timestamp_end_utc": "<ISO 8601 UTC>",
    "duration_seconds": 0,
    "language": "<language code>"
  },
  "speaker_model": {
    "type": "meetgeek-diarization",
    "speakers": ["<name>", "..."]
  },
  "artifact_refs": {
    "transcript_md": "<path>",
    "transcript_json": "<path>",
    "summary_md": "<path or null>",
    "highlights_md": "<path or null>"
  },
  "trust": {
    "transcript": "provider-raw",
    "summary": "provider-generated",
    "action_items": "provider-suggested-not-accepted"
  }
}
```

**Trust semantics:**
- `provider-raw` — verbatim diarized transcript, treat as evidence
- `provider-generated` — AI-generated summary, treat as evidence, not truth
- `provider-suggested-not-accepted` — action items are suggestions only; POS must not auto-accept

**Location:** `~/.dor/lake/meetgeek/artifacts/<meeting_id>.transcript-artifact.json`

**POS contract:** POS reads `artifact_refs`, uses `trust` flags to decide promotion scope. POS owns the decision of whether to promote to journal/tasks.

---

## 7. Live Validation Plan

No network or Drive auth needed for most validations.

| Check | Command | Expected |
|-------|---------|---------|
| convert help | `meetgeek_cli.py convert --help` | exit 0, shows input/output/mix-mode flags |
| upload help | `meetgeek_cli.py upload --help` | exit 0, shows --from-file/--download-url |
| drive-upload help | `meetgeek_cli.py drive-upload --help` | exit 0 |
| probe on fixture | `meetgeek_cli.py convert tests/fixtures/sample.mp4 --probe` | JSON with audio_streams, has_video |
| dry-run with fixture | Create temp dir with dummy `.webm` (e.g. `python -c "Path('/tmp/t.webm').write_bytes(b'x'*1024)"`) then: `meetgeek_cli.py upload --from-file /tmp/t.webm --dry-run` | prints "would: convert+drive+upload", exit 0 |
| test suite (legacy) | `pytest plugins/h2t-ops/skills/meetgeek/tests/test_meetgeek_cli.py -v` | all pass |
| test suite (connector) | `pytest tests/connectors/meetgeek/ -v` | all pass |

**T0 deliverable:** confirm help/probe/dry-run exits pass.

Note on dry-run: `--from-file <path>` without a real or dummy file will fail with `no files match`. The fixture must exist on disk before running dry-run. A 1-byte stub is sufficient — ffmpeg probe is not called in dry-run mode.

Note on fixture for probe/convert: a minimal 3-second silent mp4 can be generated once as `tests/connectors/meetgeek/fixtures/sample.mp4` using `ffmpeg -f lavfi -i anullsrc=r=44100:cl=mono -t 3 -c:a aac sample.mp4`.

---

## 8. Non-Goals

- No POS journal writes from h2t-ops
- No automatic acceptance of MeetGeek action items as tasks
- No transcript interpretation (decisions, follow-ups)
- No provider-neutral Granola/Krisp/localASR abstraction
- No transcript fusion or reconciliation
- No VPS/webhook production design
- No Drive connector rewrite (that is #133)
- No changes to `sync` or `webhook-server` commands
- No changes to the MeetGeek API read verbs (auth-check, teams, list, get, transcript, summary, highlights, insights, download)

---

## 9. Open Questions

1. **Artifact emission timing:** Should the envelope be emitted immediately after submit (with null transcript refs), or should recovery optionally poll until transcript is available? Recommendation: emit immediately, add a separate `recover --and-fetch` flag later.

2. **Drive fallback:** After #133 ships, should drive-upload continue to work standalone in meetgeek_cli.py (keep duplicate), or should it become a hard dependency on `h2t-ops drive upload`? Recommendation: keep internal fallback until #133 is proven in production.

3. **Recovery test location:** Where do recovery-specific tests live? Existing test files are split:
   - `plugins/h2t-ops/skills/meetgeek/tests/test_meetgeek_cli.py` — legacy API verb tests
   - `tests/connectors/meetgeek/` — connector tests (test_client, test_commands, test_legacy_upload_alias)

   Recovery tests (convert, drive-upload, upload pipeline) don't exist in either location yet. Recommendation: add `tests/connectors/meetgeek/test_recovery.py` aligned with the new connector test pattern. Legacy `test_meetgeek_cli.py` stays for API verb coverage.

4. **recovery.py namespace:** Should recovery module be in `plugins/h2t-ops/skills/meetgeek/scripts/` or in a shared `plugins/h2t-ops/lib/` for reuse? Recommendation: keep in meetgeek skills dir for now; move to lib if another skill needs it.
