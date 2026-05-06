# meetgeek upload + media conversion — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add three composable subcommands (`convert`, `drive-upload`, `upload`) to `h2t-ops:meetgeek` so user can ingest local `.webm` recordings into MeetGeek by converting → uploading to Google Drive → POSTing the public download URL to `/v1/upload`. Also batch (`upload --from-file`) and resume via append-only manifest.

**Architecture:** Single-file extension of `plugins/h2t-ops/skills/meetgeek/scripts/meetgeek_cli.py` (no new modules). Stages chain through staging files and an append-only `manifest.jsonl` ("last-line-wins" effective state). Convert uses `imageio-ffmpeg` binary; multi-track audio is detected by parsing `ffmpeg -i ... -f null -` stderr and mixed via `amix=inputs=N`. Drive uses the existing OAuth token (`~/.config/google-calendar-mcp/tokens.json`). MeetGeek `/v1/upload` is `POST application/json` with `download_url` field; `202 Accepted` (with optional `webhook_url not configured` warning) is success.

**Tech Stack:** Python 3.10+ stdlib + `requests` + `python-dotenv` + `google-api-python-client` (already in venv) + new `imageio-ffmpeg`. Tests: `pytest` + `unittest.mock` (existing patterns). No new modules; no Docker.

**Spec:** `docs/superpowers/specs/2026-05-06-meetgeek-upload-design.md` (commit `26bae7c`)
**Issue:** lichtpfad/h2t-skills#93
**Sequencing rule:** **Live verification gate (Task 8) BEFORE batch orchestration / resume (Tasks 9–11).** If `download_url` assumption fails, we don't waste effort on resume logic.

---

## File Structure

| File | Role | Action |
|---|---|---|
| `plugins/h2t-ops/skills/meetgeek/scripts/meetgeek_cli.py` | Main CLI; gets new helpers + commands | Modify |
| `plugins/h2t-ops/skills/meetgeek/tests/test_meetgeek_cli.py` | Pytest suite; gets new tests | Modify |
| `plugins/h2t-ops/skills/meetgeek/SKILL.md` | User-facing skill doc | Modify |
| `plugins/h2t-ops/.claude-plugin/plugin.json` | Plugin manifest | Bump 1.0.7 → 1.1.0 |
| `.claude-plugin/marketplace.json` | Marketplace registry | Sync version |
| `~/.h2t/venv/Lib/site-packages/imageio_ffmpeg/` | Bundled ffmpeg binary (runtime artifact) | Install via pip |

The CLI file will grow but stays single-file by design. Logical sections inside `meetgeek_cli.py` (use comment dividers like existing `# ─── HTTP ───` / `# ─── Sync pipeline ───`):

- `# ─── ffmpeg helpers ───` (probe, encode recipe builder)
- `# ─── Drive upload ───` (service factory or import, idempotent upload, public permission)
- `# ─── Uploads manifest ───` (append-only jsonl; reader with last-line-wins)
- `# ─── Upload commands ───` (cmd_convert, cmd_drive_upload, cmd_upload)

---

## Task 1: Install `imageio-ffmpeg` into h2t venv

**Files:**
- Test: smoke check via Python REPL (no test file change)

- [ ] **Step 1: Install package**

```bash
C:/Users/stani/.h2t/venv/Scripts/python.exe -m pip install imageio-ffmpeg
```

Expected: `Successfully installed imageio-ffmpeg-X.Y.Z`. Mac equivalent: `~/.h2t/venv/bin/python -m pip install imageio-ffmpeg`.

- [ ] **Step 2: Verify binary path resolves on this machine**

```bash
C:/Users/stani/.h2t/venv/Scripts/python.exe -c "import imageio_ffmpeg, os; p = imageio_ffmpeg.get_ffmpeg_exe(); print(p, os.path.exists(p))"
```

Expected: a `.exe` path (Windows) and `True`.

- [ ] **Step 3: Verify ffmpeg actually runs**

```bash
C:/Users/stani/.h2t/venv/Scripts/python.exe -c "import imageio_ffmpeg, subprocess; subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), '-version'], check=True)"
```

Expected: `ffmpeg version N.x ...` printed, exit 0.

- [ ] **Step 4: No commit yet** — package state isn't tracked in repo (it's a venv-side install; Task 13 documents it in SKILL.md and Task 14 bumps `plugin.json`).

---

## Task 2: Add `_ffmpeg_exe()` helper + audio-stream probe

**Files:**
- Modify: `plugins/h2t-ops/skills/meetgeek/scripts/meetgeek_cli.py` (add `# ─── ffmpeg helpers ───` section before `# ─── Sync pipeline ───`)
- Test: `plugins/h2t-ops/skills/meetgeek/tests/test_meetgeek_cli.py`

- [ ] **Step 1: Write failing test for probe (single audio stream)**

Append to `test_meetgeek_cli.py` after the existing `# ─── YAML safety ───` section:

```python
# ─── ffmpeg probe ──────────────────────────────────────────────────────────────

def test_ffmpeg_probe_single_audio_stream(cli, monkeypatch):
    """Single audio Stream line in stderr → audio_streams=1."""
    fake_stderr = (
        "ffmpeg version 6.0\n"
        "  Stream #0:0(eng): Video: vp9, 1280x720, 30 fps\n"
        "  Stream #0:1(eng): Audio: opus, 48000 Hz, stereo\n"
        "Duration: 00:41:23.45\n"
    )
    class R:
        returncode = 0
        stderr = fake_stderr
        stdout = ""
    monkeypatch.setattr(cli.subprocess, "run", lambda *a, **kw: R())
    info = cli._ffmpeg_probe("/fake/in.webm")
    assert info["audio_streams"] == 1
    assert info["has_video"] is True
    assert info["duration_seconds"] == 41 * 60 + 23
```

- [ ] **Step 2: Run test — should fail with AttributeError**

```bash
cd C:/dev/h2t-skills/plugins/h2t-ops/skills/meetgeek && C:/Users/stani/.h2t/venv/Scripts/python.exe -m pytest tests/test_meetgeek_cli.py::test_ffmpeg_probe_single_audio_stream -v
```

Expected: `AttributeError: module ... has no attribute '_ffmpeg_probe'` or `module 'meetgeek_cli_under_test' has no attribute 'subprocess'`.

- [ ] **Step 3: Add `subprocess` import + helpers to `meetgeek_cli.py`**

Add `import subprocess` to imports block (after `import time`).

Add a new section directly before `# ─── Sync pipeline ───`:

```python
# ─── ffmpeg helpers ───────────────────────────────────────────────────────────

import re

try:
    import imageio_ffmpeg
except ImportError:
    imageio_ffmpeg = None  # late-checked in _ffmpeg_exe()


def _ffmpeg_exe() -> str:
    if imageio_ffmpeg is None:
        raise ApiError(
            "imageio-ffmpeg not installed; run: "
            "~/.h2t/venv/Scripts/python.exe -m pip install imageio-ffmpeg",
            exit_code=2,
        )
    return imageio_ffmpeg.get_ffmpeg_exe()


_DURATION_RE = re.compile(r"Duration:\s*(\d+):(\d+):(\d+)(?:\.(\d+))?")
_STREAM_AUDIO_RE = re.compile(r"Stream\s+#\d+:\d+(?:\([^)]+\))?: Audio:")
_STREAM_VIDEO_RE = re.compile(r"Stream\s+#\d+:\d+(?:\([^)]+\))?: Video:")


def _ffmpeg_probe(path: str) -> dict:
    """Run `ffmpeg -i path -f null -` and parse stderr for streams + duration."""
    r = subprocess.run(
        [_ffmpeg_exe(), "-hide_banner", "-i", path, "-f", "null", "-"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    # ffmpeg returns nonzero when there's no real output (null muxer); stderr is what we want
    stderr = r.stderr or ""
    audio = len(_STREAM_AUDIO_RE.findall(stderr))
    video = len(_STREAM_VIDEO_RE.findall(stderr))
    dur_match = _DURATION_RE.search(stderr)
    duration = None
    if dur_match:
        h, m, s, _ = dur_match.groups()
        duration = int(h) * 3600 + int(m) * 60 + int(s)
    if audio == 0 and r.returncode != 0:
        raise ApiError(f"ffmpeg cannot probe {path}: {stderr[:300]}", exit_code=1)
    return {
        "audio_streams": audio,
        "has_video": video > 0,
        "duration_seconds": duration,
        "raw_stderr_tail": stderr[-500:],
    }
```

- [ ] **Step 4: Run test — should pass**

```bash
cd C:/dev/h2t-skills/plugins/h2t-ops/skills/meetgeek && C:/Users/stani/.h2t/venv/Scripts/python.exe -m pytest tests/test_meetgeek_cli.py::test_ffmpeg_probe_single_audio_stream -v
```

Expected: PASS.

- [ ] **Step 5: Add multi-track + corrupted source tests**

Append:

```python
def test_ffmpeg_probe_multi_audio_streams(cli, monkeypatch):
    fake_stderr = (
        "  Stream #0:0: Video: h264, 1920x1080\n"
        "  Stream #0:1(eng): Audio: aac, 48000 Hz, stereo\n"
        "  Stream #0:2(rus): Audio: aac, 48000 Hz, stereo\n"
        "  Stream #0:3: Audio: aac, 44100 Hz, mono\n"
        "Duration: 01:00:00.00\n"
    )
    class R:
        returncode = 0
        stderr = fake_stderr
        stdout = ""
    monkeypatch.setattr(cli.subprocess, "run", lambda *a, **kw: R())
    info = cli._ffmpeg_probe("/fake.mp4")
    assert info["audio_streams"] == 3
    assert info["has_video"] is True
    assert info["duration_seconds"] == 3600


def test_ffmpeg_probe_corrupted_raises(cli, monkeypatch):
    class R:
        returncode = 1
        stderr = "Invalid data found when processing input\n"
        stdout = ""
    monkeypatch.setattr(cli.subprocess, "run", lambda *a, **kw: R())
    import pytest as _pytest
    with _pytest.raises(cli.ApiError):
        cli._ffmpeg_probe("/broken.webm")
```

- [ ] **Step 6: Run all 3 tests**

```bash
C:/Users/stani/.h2t/venv/Scripts/python.exe -m pytest tests/test_meetgeek_cli.py -k ffmpeg_probe -v
```

Expected: 3 passed.

- [ ] **Step 7: Commit**

```bash
git -C C:/dev/h2t-skills add plugins/h2t-ops/skills/meetgeek/scripts/meetgeek_cli.py plugins/h2t-ops/skills/meetgeek/tests/test_meetgeek_cli.py
git -C C:/dev/h2t-skills commit -m "feat(h2t-ops): meetgeek ffmpeg probe helper (#93)"
```

---

## Task 3: Add `cmd_convert` for single-track audio path

**Files:**
- Modify: `plugins/h2t-ops/skills/meetgeek/scripts/meetgeek_cli.py`
- Test: `plugins/h2t-ops/skills/meetgeek/tests/test_meetgeek_cli.py`

- [ ] **Step 1: Write failing test — single track convert**

```python
# ─── convert ───────────────────────────────────────────────────────────────────

def test_convert_single_track_builds_simple_recipe(cli, tmp_path, monkeypatch):
    src = tmp_path / "in.webm"
    src.write_bytes(b"x")  # presence-only; ffmpeg is mocked

    # probe → 1 audio stream, has_video
    monkeypatch.setattr(cli, "_ffmpeg_probe",
                        lambda p: {"audio_streams": 1, "has_video": True,
                                   "duration_seconds": 60, "raw_stderr_tail": ""})

    captured: dict = {}

    def fake_run(cmd, **kw):
        captured["cmd"] = cmd
        # write a fake mp4 so size>1KB check passes
        out_idx = cmd.index("-y") + 1 if "-y" in cmd else len(cmd) - 1
        out_path = cmd[-1]
        from pathlib import Path as P
        P(out_path).write_bytes(b"M" * 2048)
        class R:
            returncode = 0; stderr = ""; stdout = ""
        return R()

    monkeypatch.setattr(cli.subprocess, "run", fake_run)

    out = tmp_path / "out.mp4"
    rc = cli.main(["convert", str(src), "-o", str(out)])
    assert rc == 0
    assert out.exists() and out.stat().st_size > 1024
    cmd = captured["cmd"]
    assert "-c:v" in cmd and "libx264" in cmd
    assert "-c:a" in cmd and "aac" in cmd
    # single-track path should NOT use amix filter
    assert not any("amix=" in a for a in cmd)
```

- [ ] **Step 2: Run — fails (cmd_convert not registered)**

```bash
C:/Users/stani/.h2t/venv/Scripts/python.exe -m pytest tests/test_meetgeek_cli.py::test_convert_single_track_builds_simple_recipe -v
```

Expected: SystemExit / argparse error "invalid choice: 'convert'".

- [ ] **Step 3: Implement `cmd_convert` (single-track path only this task)**

Add to `meetgeek_cli.py`, in the new `# ─── ffmpeg helpers ───` section (after `_ffmpeg_probe`):

```python
def _staging_dir() -> Path:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return Path.home() / ".dor" / "lake" / "meetgeek" / "uploads-staging" / today


def _build_convert_cmd(input_path: str, output_path: str, *,
                       probe: dict, audio_only: bool, mix_mode: str) -> list[str]:
    """Construct ffmpeg argv. Multi-track logic lands in Task 4."""
    exe = _ffmpeg_exe()
    if probe["audio_streams"] <= 1 or mix_mode == "first":
        argv = [exe, "-y", "-hide_banner", "-i", input_path]
        if audio_only:
            argv += ["-vn"]
        else:
            argv += ["-map", "0:v?"]
        argv += ["-map", "0:a:0"] if mix_mode == "first" else []
        argv += [
            "-c:v", "libx264", "-preset", "medium", "-crf", "23",
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
            output_path,
        ]
        # remove video codec args if audio_only
        if audio_only:
            for k in ("-c:v", "libx264", "-preset", "medium", "-crf", "23"):
                if k in argv:
                    argv.remove(k)
        return argv
    # Multi-track amix: implemented in Task 4
    raise ApiError("multi-track convert not yet implemented", exit_code=2)


def cmd_convert(args: argparse.Namespace) -> int:
    src = Path(args.input).expanduser().resolve()
    if not src.exists():
        raise ApiError(f"input not found: {src}", exit_code=1)

    probe = _ffmpeg_probe(str(src))
    if args.probe:
        _print_json(probe)
        return 0

    if args.output:
        out = Path(args.output).expanduser()
    else:
        suffix = ".m4a" if args.audio_only else ".mp4"
        out = _staging_dir() / (src.stem + suffix)

    out.parent.mkdir(parents=True, exist_ok=True)

    if out.exists() and out.stat().st_size > 1024:
        print(f"INFO: cached {out} (skip)", file=sys.stderr)
        print(out)
        return 0

    cmd = _build_convert_cmd(
        str(src), str(out),
        probe=probe, audio_only=args.audio_only, mix_mode=args.mix_mode,
    )
    print(f"INFO: ffmpeg {len(cmd)} args (audio_streams={probe['audio_streams']})",
          file=sys.stderr)
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        if out.exists():
            out.unlink()
        raise ApiError(f"ffmpeg encode failed: {r.stderr[:500]}", exit_code=1)
    if not out.exists() or out.stat().st_size <= 1024:
        if out.exists():
            out.unlink()
        raise ApiError(f"ffmpeg produced empty output: {out}", exit_code=1)
    print(out)
    return 0
```

Register the subparser inside `build_parser()` (find the section after `s = sub.add_parser("download", ...)` block, before `s = sub.add_parser("sync", ...)`):

```python
    s = sub.add_parser("convert", help="Convert media file (webm→mp4 default)")
    s.add_argument("input")
    s.add_argument("-o", "--output", default=None,
                   help="Output path; default: ~/.dor/lake/meetgeek/uploads-staging/{YYYY-MM-DD}/{name}.mp4")
    s.add_argument("--audio-only", action="store_true",
                   help="Strip video; output .m4a")
    s.add_argument("--mix-mode", choices=["amix", "first", "keep"], default="amix",
                   help="Multi-track audio strategy (default: amix — sums all tracks)")
    s.add_argument("--probe", action="store_true",
                   help="Print probe info as JSON and exit")
    s.set_defaults(func=cmd_convert)
```

- [ ] **Step 4: Run test — passes**

```bash
C:/Users/stani/.h2t/venv/Scripts/python.exe -m pytest tests/test_meetgeek_cli.py::test_convert_single_track_builds_simple_recipe -v
```

Expected: PASS.

- [ ] **Step 5: Add cached-skip + corrupted-source tests**

```python
def test_convert_skip_if_cached(cli, tmp_path, monkeypatch):
    src = tmp_path / "in.webm"; src.write_bytes(b"x")
    out = tmp_path / "out.mp4"; out.write_bytes(b"M" * 2048)  # already big enough

    monkeypatch.setattr(cli, "_ffmpeg_probe",
                        lambda p: {"audio_streams": 1, "has_video": True,
                                   "duration_seconds": 60, "raw_stderr_tail": ""})
    called = {"n": 0}
    def no_run(*a, **kw):
        called["n"] += 1
        raise AssertionError("ffmpeg should not run when cache hit")
    monkeypatch.setattr(cli.subprocess, "run", no_run)

    rc = cli.main(["convert", str(src), "-o", str(out)])
    assert rc == 0
    assert called["n"] == 0


def test_convert_corrupted_raises(cli, tmp_path, monkeypatch):
    src = tmp_path / "broken.webm"; src.write_bytes(b"x")
    def bad_probe(p): raise cli.ApiError("ffmpeg cannot probe", exit_code=1)
    monkeypatch.setattr(cli, "_ffmpeg_probe", bad_probe)
    rc = cli.main(["convert", str(src), "-o", str(tmp_path / "out.mp4")])
    assert rc == 1
```

- [ ] **Step 6: Run all convert tests**

```bash
C:/Users/stani/.h2t/venv/Scripts/python.exe -m pytest tests/test_meetgeek_cli.py -k convert -v
```

Expected: 3 passed.

- [ ] **Step 7: Commit**

```bash
git -C C:/dev/h2t-skills add plugins/h2t-ops/skills/meetgeek/
git -C C:/dev/h2t-skills commit -m "feat(h2t-ops): meetgeek convert command (single-track) (#93)"
```

---

## Task 4: Extend `cmd_convert` with multi-track `amix` filtergraph

**Files:**
- Modify: same two files

- [ ] **Step 1: Write failing test for multi-track amix**

```python
def test_convert_multi_track_uses_amix(cli, tmp_path, monkeypatch):
    src = tmp_path / "in.webm"; src.write_bytes(b"x")
    monkeypatch.setattr(cli, "_ffmpeg_probe",
                        lambda p: {"audio_streams": 3, "has_video": True,
                                   "duration_seconds": 60, "raw_stderr_tail": ""})
    captured: dict = {}
    def fake_run(cmd, **kw):
        captured["cmd"] = cmd
        from pathlib import Path as P
        P(cmd[-1]).write_bytes(b"M" * 2048)
        class R: returncode = 0; stderr = ""; stdout = ""
        return R()
    monkeypatch.setattr(cli.subprocess, "run", fake_run)

    out = tmp_path / "out.mp4"
    rc = cli.main(["convert", str(src), "-o", str(out)])
    assert rc == 0
    cmd = captured["cmd"]
    fc_idx = cmd.index("-filter_complex")
    filtergraph = cmd[fc_idx + 1]
    assert "amix=inputs=3" in filtergraph
    assert "[0:a:0][0:a:1][0:a:2]" in filtergraph
    assert "duration=longest" in filtergraph
    assert "aresample=48000" in filtergraph
    # output map points at named filter output
    assert '[a]' in cmd
```

- [ ] **Step 2: Run — fails (multi-track raises ApiError currently)**

```bash
C:/Users/stani/.h2t/venv/Scripts/python.exe -m pytest tests/test_meetgeek_cli.py::test_convert_multi_track_uses_amix -v
```

Expected: FAIL — `ApiError("multi-track convert not yet implemented")`.

- [ ] **Step 3: Implement multi-track branch in `_build_convert_cmd`**

Replace the `raise ApiError("multi-track convert not yet implemented")` line with:

```python
    # Multi-track amix
    if mix_mode == "keep":
        argv = [exe, "-y", "-hide_banner", "-i", input_path,
                "-map", "0", "-c:v", "libx264", "-preset", "medium", "-crf", "23",
                "-c:a", "aac", "-b:a", "192k", output_path]
        if audio_only:
            argv = [a for a in argv if a not in ("-c:v", "libx264", "-preset", "medium", "-crf", "23")]
            argv.insert(argv.index("-i") + 2, "-vn")
        return argv

    # mix_mode == "amix"
    n = probe["audio_streams"]
    inputs = "".join(f"[0:a:{i}]" for i in range(n))
    filtergraph = (
        f"{inputs}amix=inputs={n}:duration=longest:dropout_transition=0,"
        f"aresample=48000[a]"
    )
    argv = [exe, "-y", "-hide_banner", "-i", input_path,
            "-filter_complex", filtergraph]
    if audio_only:
        argv += ["-map", "[a]", "-c:a", "aac", "-b:a", "192k", "-ac", "2", output_path]
    else:
        argv += ["-map", "0:v?", "-map", "[a]",
                 "-c:v", "libx264", "-preset", "medium", "-crf", "23",
                 "-c:a", "aac", "-b:a", "192k", "-ac", "2", output_path]
    return argv
```

- [ ] **Step 4: Run multi-track test — passes**

```bash
C:/Users/stani/.h2t/venv/Scripts/python.exe -m pytest tests/test_meetgeek_cli.py::test_convert_multi_track_uses_amix -v
```

Expected: PASS.

- [ ] **Step 5: Add `--mix-mode first` and `--audio-only` tests**

```python
def test_convert_mix_mode_first_picks_first_stream(cli, tmp_path, monkeypatch):
    src = tmp_path / "in.webm"; src.write_bytes(b"x")
    monkeypatch.setattr(cli, "_ffmpeg_probe",
                        lambda p: {"audio_streams": 3, "has_video": True,
                                   "duration_seconds": 60, "raw_stderr_tail": ""})
    captured = {}
    def fake_run(cmd, **kw):
        captured["cmd"] = cmd
        from pathlib import Path as P
        P(cmd[-1]).write_bytes(b"M" * 2048)
        class R: returncode = 0; stderr = ""; stdout = ""
        return R()
    monkeypatch.setattr(cli.subprocess, "run", fake_run)

    cli.main(["convert", str(src), "-o", str(tmp_path / "out.mp4"), "--mix-mode", "first"])
    cmd = captured["cmd"]
    assert "-filter_complex" not in cmd
    assert "0:a:0" in cmd


def test_convert_audio_only_strips_video_codec_flags(cli, tmp_path, monkeypatch):
    src = tmp_path / "in.webm"; src.write_bytes(b"x")
    monkeypatch.setattr(cli, "_ffmpeg_probe",
                        lambda p: {"audio_streams": 1, "has_video": True,
                                   "duration_seconds": 60, "raw_stderr_tail": ""})
    captured = {}
    def fake_run(cmd, **kw):
        captured["cmd"] = cmd
        from pathlib import Path as P
        P(cmd[-1]).write_bytes(b"M" * 2048)
        class R: returncode = 0; stderr = ""; stdout = ""
        return R()
    monkeypatch.setattr(cli.subprocess, "run", fake_run)

    cli.main(["convert", str(src), "-o", str(tmp_path / "out.m4a"), "--audio-only"])
    cmd = captured["cmd"]
    assert "libx264" not in cmd
    assert "-vn" in cmd
    assert "aac" in cmd
```

- [ ] **Step 6: Run all convert tests (5 total)**

```bash
C:/Users/stani/.h2t/venv/Scripts/python.exe -m pytest tests/test_meetgeek_cli.py -k convert -v
```

Expected: 5 passed.

- [ ] **Step 7: Commit**

```bash
git -C C:/dev/h2t-skills add plugins/h2t-ops/skills/meetgeek/
git -C C:/dev/h2t-skills commit -m "feat(h2t-ops): meetgeek convert multi-track amix + audio-only (#93)"
```

---

## Task 5: Add `_drive_service()` factory (mirror of drive_cli pattern)

**Files:**
- Modify: `plugins/h2t-ops/skills/meetgeek/scripts/meetgeek_cli.py`
- Test: `plugins/h2t-ops/skills/meetgeek/tests/test_meetgeek_cli.py`

- [ ] **Step 1: Write failing test — Drive service builder uses tokens.json**

```python
# ─── drive upload ──────────────────────────────────────────────────────────────

def test_drive_service_raises_when_token_missing(cli, tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "DRIVE_TOKEN_FILE", tmp_path / "missing.json")
    import pytest as _p
    with _p.raises(cli.ApiError) as e:
        cli._drive_service()
    assert "tokens.json" in str(e.value).lower() or "drive auth" in str(e.value).lower()
```

- [ ] **Step 2: Run — fails (no `_drive_service`, no `DRIVE_TOKEN_FILE`)**

```bash
C:/Users/stani/.h2t/venv/Scripts/python.exe -m pytest tests/test_meetgeek_cli.py::test_drive_service_raises_when_token_missing -v
```

Expected: AttributeError.

- [ ] **Step 3: Add helpers and module-level constants**

In `meetgeek_cli.py`, add a `# ─── Drive upload ───` section after the ffmpeg helpers:

```python
# ─── Drive upload ─────────────────────────────────────────────────────────────

DRIVE_CONFIG_DIR = Path.home() / ".config" / "google-calendar-mcp"
DRIVE_TOKEN_FILE = DRIVE_CONFIG_DIR / "tokens.json"
DRIVE_CREDENTIALS_FILE = DRIVE_CONFIG_DIR / "credentials.json"
DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive"]
DRIVE_ROOT_FOLDER_NAME = "MeetGeek Uploads"


def _drive_service():
    """Build a Drive v3 service. Mirrors drive_cli.get_drive_service() so OAuth is shared."""
    if not DRIVE_TOKEN_FILE.exists():
        raise ApiError(
            f"Drive auth missing — token not at {DRIVE_TOKEN_FILE}. "
            "Run /h2t-ops:drive list to trigger OAuth.",
            exit_code=1,
        )
    try:
        from google.auth.transport.requests import Request as _GReq
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
    except ImportError as e:
        raise ApiError(
            f"google-api-python-client not installed: {e}. "
            "pip install google-api-python-client google-auth-httplib2",
            exit_code=2,
        )

    with DRIVE_TOKEN_FILE.open(encoding="utf-8") as f:
        token_data = json.load(f)
    if "normal" in token_data:
        token_data = token_data["normal"]

    if "client_id" not in token_data:
        if not DRIVE_CREDENTIALS_FILE.exists():
            raise ApiError(f"Drive credentials missing: {DRIVE_CREDENTIALS_FILE}", exit_code=1)
        with DRIVE_CREDENTIALS_FILE.open(encoding="utf-8") as f:
            creds_data = json.load(f)
        installed = creds_data.get("installed", creds_data)
        token_data["client_id"] = installed.get("client_id")
        token_data["client_secret"] = installed.get("client_secret")
        token_data["token_uri"] = installed.get("token_uri", "https://oauth2.googleapis.com/token")

    existing_scopes = token_data.get("scopes") or []
    if isinstance(existing_scopes, str):
        existing_scopes = existing_scopes.split()
    creds = Credentials.from_authorized_user_info(
        token_data, scopes=existing_scopes or DRIVE_SCOPES
    )
    if creds.expired and creds.refresh_token:
        creds.refresh(_GReq())
        DRIVE_TOKEN_FILE.write_text(creds.to_json())
    return build("drive", "v3", credentials=creds)
```

- [ ] **Step 4: Run test — passes**

```bash
C:/Users/stani/.h2t/venv/Scripts/python.exe -m pytest tests/test_meetgeek_cli.py::test_drive_service_raises_when_token_missing -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git -C C:/dev/h2t-skills add plugins/h2t-ops/skills/meetgeek/
git -C C:/dev/h2t-skills commit -m "feat(h2t-ops): meetgeek drive service factory (#93)"
```

---

## Task 6: Add `cmd_drive_upload` (idempotent + public)

**Files:**
- Modify: same

- [ ] **Step 1: Write failing test — idempotent search returns existing**

```python
class _FakeDriveCall:
    """Helper to fluently chain googleapiclient .files().list().execute()-style calls."""
    def __init__(self, returns):
        self._returns = returns
    def files(self): return self
    def list(self, **kw): self._last_q = kw.get("q"); return self
    def create(self, **kw): self._last_create = kw; return self
    def execute(self): return self._returns
    def permissions(self): return self


def test_drive_upload_idempotent_returns_existing(cli, tmp_path, monkeypatch):
    file_path = tmp_path / "test.mp4"; file_path.write_bytes(b"M" * 1024)

    # First .files().list().execute() returns the parent folder; second returns existing file
    folder_resp = {"files": [{"id": "FOLDER123", "name": "MeetGeek Uploads"}]}
    dated_resp = {"files": [{"id": "DATED456", "name": "2026-05-06"}]}
    file_resp = {"files": [{"id": "EXISTING789", "name": "test.mp4",
                            "webViewLink": "https://drive.google.com/file/d/EXISTING789"}]}
    responses = [folder_resp, dated_resp, file_resp]

    class FakeService:
        def files(self): return self
        def list(self, **kw):
            self._resp = responses.pop(0); return self
        def execute(self): return self._resp

    monkeypatch.setattr(cli, "_drive_service", lambda: FakeService())

    rc = cli.main(["drive-upload", str(file_path)])
    assert rc == 0
```

- [ ] **Step 2: Run — fails (no cmd_drive_upload registered)**

Expected: argparse "invalid choice".

- [ ] **Step 3: Implement folder helpers + cmd_drive_upload**

Append to the `# ─── Drive upload ───` section:

```python
def _drive_find_or_create_folder(svc, name: str, parent_id: str | None = None) -> str:
    """Return folder id; create if missing under parent (or root if parent is None)."""
    parent_clause = f" and '{parent_id}' in parents" if parent_id else " and 'root' in parents"
    q = (
        f"name = '{name}' and mimeType = 'application/vnd.google-apps.folder' "
        f"and trashed = false{parent_clause}"
    )
    res = svc.files().list(q=q, fields="files(id,name)", pageSize=1).execute()
    files = res.get("files", [])
    if files:
        return files[0]["id"]
    body = {"name": name, "mimeType": "application/vnd.google-apps.folder"}
    if parent_id:
        body["parents"] = [parent_id]
    created = svc.files().create(body=body, fields="id").execute()
    return created["id"]


def _drive_find_file(svc, name: str, folder_id: str) -> dict | None:
    q = f"name = '{name}' and '{folder_id}' in parents and trashed = false"
    res = svc.files().list(q=q, fields="files(id,name,webViewLink)", pageSize=1).execute()
    files = res.get("files", [])
    return files[0] if files else None


def _drive_make_public(svc, file_id: str) -> None:
    svc.permissions().create(
        fileId=file_id,
        body={"type": "anyone", "role": "reader"},
        fields="id",
    ).execute()


def _drive_download_url(file_id: str) -> str:
    return f"https://drive.google.com/uc?export=download&id={file_id}"


def cmd_drive_upload(args: argparse.Namespace) -> int:
    src = Path(args.file).expanduser().resolve()
    if not src.exists():
        raise ApiError(f"file not found: {src}", exit_code=1)

    svc = _drive_service()

    # Resolve folder hierarchy: MeetGeek Uploads / {date}/
    if args.folder:
        # explicit "MeetGeek Uploads/2026-05-06" type path
        parts = [p for p in args.folder.replace("\\", "/").split("/") if p]
    else:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        parts = [DRIVE_ROOT_FOLDER_NAME, date]

    parent_id: str | None = None
    for part in parts:
        parent_id = _drive_find_or_create_folder(svc, part, parent_id)
    folder_id = parent_id  # final folder

    existing = _drive_find_file(svc, src.name, folder_id)
    if existing:
        if args.make_public:
            try:
                _drive_make_public(svc, existing["id"])
            except Exception:  # noqa: BLE001 — already public is fine
                pass
        out = {
            "drive_id": existing["id"],
            "web_url": existing.get("webViewLink"),
            "download_url": _drive_download_url(existing["id"]),
            "created": False,
        }
        _print_json(out)
        return 0

    try:
        from googleapiclient.http import MediaFileUpload
    except ImportError as e:
        raise ApiError(f"googleapiclient missing: {e}", exit_code=2)
    media = MediaFileUpload(str(src), resumable=True)
    body = {"name": src.name, "parents": [folder_id]}
    file = svc.files().create(body=body, media_body=media,
                              fields="id,webViewLink").execute()
    if args.make_public:
        _drive_make_public(svc, file["id"])
    out = {
        "drive_id": file["id"],
        "web_url": file.get("webViewLink"),
        "download_url": _drive_download_url(file["id"]),
        "created": True,
    }
    _print_json(out)
    return 0
```

Register subparser in `build_parser()` (after `convert` block):

```python
    s = sub.add_parser("drive-upload", help="Upload a file to Drive (idempotent by name)")
    s.add_argument("file")
    s.add_argument("--folder", default=None,
                   help="Path like 'MeetGeek Uploads/2026-05-06'; default: MeetGeek Uploads/{today UTC}")
    s.add_argument("--make-public", action=argparse.BooleanOptionalAction, default=True,
                   help="Set permissions to anyone-with-link reader (default on)")
    s.set_defaults(func=cmd_drive_upload)
```

- [ ] **Step 4: Run idempotent test**

```bash
C:/Users/stani/.h2t/venv/Scripts/python.exe -m pytest tests/test_meetgeek_cli.py::test_drive_upload_idempotent_returns_existing -v
```

Expected: PASS.

- [ ] **Step 5: Add folder-creation + public-permission tests**

```python
def test_drive_upload_creates_dated_folder_and_uploads(cli, tmp_path, monkeypatch):
    file_path = tmp_path / "x.mp4"; file_path.write_bytes(b"M" * 1024)
    state = {"folders": {}, "files": {}, "perm_calls": []}

    class FakeService:
        def files(self): return self
        def list(self, q, **kw):
            self._mode = ("folder" if "folder" in q else "file")
            return self
        def create(self, body, fields=None, media_body=None):
            self._create_body = body
            return self
        def permissions(self): return _FakePerms(state)
        def execute(self):
            if getattr(self, "_create_body", None):
                b = self._create_body; self._create_body = None
                if b.get("mimeType") == "application/vnd.google-apps.folder":
                    new_id = f"FOLDER_{b['name']}"
                    state["folders"][b["name"]] = new_id
                    return {"id": new_id}
                else:
                    new_id = f"FILE_{b['name']}"
                    state["files"][b["name"]] = new_id
                    return {"id": new_id, "webViewLink": f"https://drive/{new_id}"}
            # list path
            return {"files": []}

    class _FakePerms:
        def __init__(self, s): self.s = s
        def create(self, fileId, body, fields=None):
            self.s["perm_calls"].append((fileId, body))
            class _R:
                def execute(_): return {"id": "perm_x"}
            return _R()

    monkeypatch.setattr(cli, "_drive_service", lambda: FakeService())
    monkeypatch.setattr(cli, "MediaFileUpload",
                        lambda *a, **kw: object(), raising=False)
    # MediaFileUpload is imported lazily inside cmd_drive_upload; patch its import target:
    import googleapiclient.http as _ghttp
    monkeypatch.setattr(_ghttp, "MediaFileUpload", lambda *a, **kw: object())

    rc = cli.main(["drive-upload", str(file_path)])
    assert rc == 0
    assert any(f.startswith("FILE_") for f in state["files"].values())
    # public permission was set
    assert len(state["perm_calls"]) == 1
    assert state["perm_calls"][0][1] == {"type": "anyone", "role": "reader"}
```

- [ ] **Step 6: Run drive tests**

```bash
C:/Users/stani/.h2t/venv/Scripts/python.exe -m pytest tests/test_meetgeek_cli.py -k drive -v
```

Expected: 3 passed (token-missing, idempotent, create).

- [ ] **Step 7: Commit**

```bash
git -C C:/dev/h2t-skills add plugins/h2t-ops/skills/meetgeek/
git -C C:/dev/h2t-skills commit -m "feat(h2t-ops): meetgeek drive-upload command (#93)"
```

---

## Task 7: Add `cmd_upload --download-url` (direct mode only)

**Files:**
- Modify: same

- [ ] **Step 1: Write failing test — direct upload returns 202 success**

```python
# ─── upload (POST /v1/upload) ─────────────────────────────────────────────────

def test_upload_direct_url_succeeds_on_202(cli, capsys):
    fake, calls = _scripted_request([
        FakeResponse(202, {"message": "The recording has been validated and submitted "
                                       "for analysis. However, webhook_url is not configured."})
    ])
    with patch.object(cli.requests, "request", fake):
        rc = cli.main(["upload", "--download-url", "https://example.com/x.mp4",
                       "--title", "Test", "--language", "ru"])
    assert rc == 0
    body = calls[0]["json"]
    assert body["download_url"] == "https://example.com/x.mp4"
    assert body["title"] == "Test"
    assert body["language"] == "ru"
    assert calls[0]["method"] == "POST"
    assert calls[0]["url"].endswith("/v1/upload")


def test_upload_direct_url_401_aborts(cli):
    fake, _ = _scripted_request([FakeResponse(401, {"message": "unauthorized"})])
    with patch.object(cli.requests, "request", fake):
        rc = cli.main(["upload", "--download-url", "https://example.com/x.mp4"])
    assert rc == 1


def test_upload_direct_url_400_invalid(cli):
    fake, _ = _scripted_request([FakeResponse(400, {"message": "bad", "reason": "download_url field is not a valid url"})])
    with patch.object(cli.requests, "request", fake):
        rc = cli.main(["upload", "--download-url", "not-a-url"])
    assert rc == 1
```

- [ ] **Step 2: Run — fails (cmd_upload not registered)**

- [ ] **Step 3: Implement direct mode of `cmd_upload`**

Add to `meetgeek_cli.py`, in a new `# ─── Upload commands ───` section after Drive upload:

```python
# ─── Upload commands ─────────────────────────────────────────────────────────

def _post_upload(download_url: str, title: str | None, language: str | None) -> dict:
    body = {"download_url": download_url}
    if title:
        body["title"] = title
    if language:
        body["language"] = language
    r = _request("POST", "/v1/upload", json_body=body)
    if r.status_code == 401:
        raise ApiError("401: invalid MEETGEEK_API_KEY", exit_code=1)
    if r.status_code == 400:
        raise ApiError(f"400: {r.text[:300]}", exit_code=1)
    if r.status_code >= 500:
        raise ApiError(f"{r.status_code}: {r.text[:300]}", exit_code=1)
    if r.status_code not in (200, 202):
        raise ApiError(f"unexpected status {r.status_code}: {r.text[:300]}", exit_code=1)
    try:
        return r.json()
    except ValueError:
        return {"message": r.text[:500]}


def cmd_upload(args: argparse.Namespace) -> int:
    if args.download_url:
        resp = _post_upload(args.download_url, args.title, args.language)
        _print_json({"status": "submitted", "response": resp})
        return 0
    if args.from_file:
        # Implemented in Task 9
        raise ApiError("--from-file not yet implemented (planned in Task 9)", exit_code=2)
    raise ApiError("either --download-url or --from-file required", exit_code=2)
```

Register subparser (after `drive-upload` block, before `sync`):

```python
    s = sub.add_parser("upload", help="Submit URL or local file to MeetGeek /v1/upload")
    grp = s.add_mutually_exclusive_group(required=True)
    grp.add_argument("--download-url", default=None,
                     help="Public URL MeetGeek will fetch (e.g. Drive uc?export=download)")
    grp.add_argument("--from-file", default=None,
                     help="Local file path or glob; orchestrates convert + drive-upload + upload")
    s.add_argument("--title", default=None)
    s.add_argument("--language", default=None,
                   help="Language hint (ru, en, auto, etc.)")
    s.set_defaults(func=cmd_upload)
```

- [ ] **Step 4: Run upload tests**

```bash
C:/Users/stani/.h2t/venv/Scripts/python.exe -m pytest tests/test_meetgeek_cli.py -k "upload_direct" -v
```

Expected: 3 passed.

- [ ] **Step 5: Run full suite**

```bash
C:/Users/stani/.h2t/venv/Scripts/python.exe -m pytest tests/test_meetgeek_cli.py -q
```

Expected: all tests so far pass (15 prior + ~10 new).

- [ ] **Step 6: Commit**

```bash
git -C C:/dev/h2t-skills add plugins/h2t-ops/skills/meetgeek/
git -C C:/dev/h2t-skills commit -m "feat(h2t-ops): meetgeek upload --download-url direct mode (#93)"
```

---

## Task 8: 🚦 LIVE VERIFICATION GATE

Validate the `download_url = https://drive.google.com/uc?export=download&id=...` assumption end-to-end with one real `.webm` file. **Do NOT proceed to Task 9 until this passes.**

This task is manual (engineer + user) — there's no test code, only a checklist with explicit expected outputs.

**Files:** none modified.

- [ ] **Step 1: Pick one source file on the user's macOS**

Engineer asks user (or, if user reads this directly): pick the smallest `~/Downloads/meetgeek-recording-*.webm` (5–10 minutes ideal — fast feedback). Note the absolute path.

- [ ] **Step 2: Convert it locally**

```bash
~/.h2t/venv/bin/python ~/.../h2t-skills/plugins/h2t-ops/skills/meetgeek/scripts/meetgeek_cli.py \
  convert "<path-to-webm>"
```

Expected stdout: a path under `~/.dor/lake/meetgeek/uploads-staging/{YYYY-MM-DD}/`.
Expected: file plays in QuickTime / VLC; audio audible.

- [ ] **Step 3: Upload it to Drive**

```bash
~/.h2t/venv/bin/python .../meetgeek_cli.py drive-upload "<mp4-from-step-2>"
```

Expected stdout: JSON with `drive_id`, `web_url`, `download_url`, `created: true`.
Expected: open `web_url` in a browser → file visible in Drive.

- [ ] **Step 4: Validate `download_url` is anonymously fetchable**

In an **incognito window** (no Google login), open the `download_url` from Step 3.

- ✅ If browser starts downloading the mp4 → assumption holds, continue.
- ❌ If a Google sign-in page or 403 appears → **STOP**. The assumption fails. Do not proceed to Step 5. Capture the exact response and add a blocker comment to lichtpfad/h2t-skills#93. Possible fixes (per spec §7.5): switch to `webContentLink` from Drive metadata, or move file to a Shared Drive. Re-do Task 6 with the working URL pattern, then re-run this gate.

- [ ] **Step 5: Submit to MeetGeek**

```bash
~/.h2t/venv/bin/python .../meetgeek_cli.py upload \
  --download-url "<download_url-from-step-3>" \
  --title "live-gate-test $(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --language ru
```

Expected stdout: `{"status": "submitted", "response": {"message": "The recording has been validated..."}}`. 202 accepted.

- [ ] **Step 6: Wait 5–15 min, then verify ingestion**

```bash
~/.h2t/venv/bin/python .../meetgeek_cli.py list --limit 5
```

Expected: a new meeting with title `live-gate-test ...` appears in the list. Note its `meeting_id`.

```bash
~/.h2t/venv/bin/python .../meetgeek_cli.py transcript "<meeting_id>" --format md
```

Expected: real transcript text from the recording (not empty, not error).

- [ ] **Step 7: Document the gate result**

If all 6 steps green: continue to Task 9.
If any step fails: open a comment on lichtpfad/h2t-skills#93 with the failing step + exact output, **then revise this plan before continuing**.

No commit (no code changed).

---

## Task 9: Add `_uploads_manifest_path()` + reader (last-line-wins)

**Files:**
- Modify: `plugins/h2t-ops/skills/meetgeek/scripts/meetgeek_cli.py`
- Test: `plugins/h2t-ops/skills/meetgeek/tests/test_meetgeek_cli.py`

- [ ] **Step 1: Write failing test for last-line-wins**

```python
# ─── uploads manifest ──────────────────────────────────────────────────────────

def test_uploads_manifest_last_line_wins(cli, tmp_path):
    m = tmp_path / "manifest.jsonl"
    lines = [
        {"source_webm": "/a.webm", "status": "converted",
         "source_size_bytes": 100, "source_mtime": "2026-05-06T10:00:00Z"},
        {"source_webm": "/a.webm", "status": "in-drive",
         "source_size_bytes": 100, "source_mtime": "2026-05-06T10:00:00Z",
         "drive_id": "X"},
        {"source_webm": "/b.webm", "status": "submitted",
         "source_size_bytes": 200, "source_mtime": "2026-05-06T11:00:00Z"},
    ]
    with m.open("w", encoding="utf-8") as f:
        for r in lines:
            f.write(json.dumps(r) + "\n")
    state = cli._read_uploads_manifest(m)
    assert state["/a.webm"]["status"] == "in-drive"
    assert state["/a.webm"]["drive_id"] == "X"
    assert state["/b.webm"]["status"] == "submitted"


def test_uploads_manifest_skip_existing_size_mtime_match(cli, tmp_path):
    m = tmp_path / "manifest.jsonl"
    rec = {"source_webm": "/x.webm", "status": "submitted",
           "source_size_bytes": 100, "source_mtime": "2026-05-06T10:00:00Z"}
    m.write_text(json.dumps(rec) + "\n", encoding="utf-8")
    state = cli._read_uploads_manifest(m)
    assert cli._is_already_submitted(state, "/x.webm",
                                     size=100, mtime="2026-05-06T10:00:00Z") is True
    # changed size → not "already submitted"
    assert cli._is_already_submitted(state, "/x.webm",
                                     size=200, mtime="2026-05-06T10:00:00Z") is False
    # changed mtime → not "already submitted"
    assert cli._is_already_submitted(state, "/x.webm",
                                     size=100, mtime="2026-05-06T11:00:00Z") is False
```

- [ ] **Step 2: Run — fails (no manifest helpers)**

- [ ] **Step 3: Implement helpers**

Add to `meetgeek_cli.py` in a new `# ─── Uploads manifest ───` section (between Drive upload and Upload commands):

```python
# ─── Uploads manifest ────────────────────────────────────────────────────────

def _uploads_manifest_path() -> Path:
    return Path.home() / ".dor" / "lake" / "meetgeek" / "uploads-staging" / "manifest.jsonl"


def _read_uploads_manifest(path: Path | None = None) -> dict[str, dict]:
    """Last-line-wins per source_webm. Returns {source_path: latest_record_dict}."""
    if path is None:
        path = _uploads_manifest_path()
    state: dict[str, dict] = {}
    if not path.exists():
        return state
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            src = rec.get("source_webm")
            if src:
                state[src] = rec  # later lines overwrite earlier
    return state


def _append_uploads_manifest(record: dict, path: Path | None = None) -> None:
    if path is None:
        path = _uploads_manifest_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _is_already_submitted(state: dict[str, dict], source: str, *,
                          size: int, mtime: str) -> bool:
    rec = state.get(source)
    if not rec or rec.get("status") != "submitted":
        return False
    return (rec.get("source_size_bytes") == size
            and rec.get("source_mtime") == mtime)
```

- [ ] **Step 4: Run manifest tests**

```bash
C:/Users/stani/.h2t/venv/Scripts/python.exe -m pytest tests/test_meetgeek_cli.py -k uploads_manifest -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git -C C:/dev/h2t-skills add plugins/h2t-ops/skills/meetgeek/
git -C C:/dev/h2t-skills commit -m "feat(h2t-ops): meetgeek uploads manifest helpers (#93)"
```

---

## Task 10: Add `cmd_upload --from-file` for a single file (no glob yet)

**Files:**
- Modify: same

- [ ] **Step 1: Write failing test — orchestrator chains all 3 stages**

```python
def test_upload_from_file_chains_convert_drive_submit(cli, tmp_path, monkeypatch):
    src = tmp_path / "meetgeek-recording-2026-01-20T15-44-31-132Z.webm"
    src.write_bytes(b"x" * 1024)

    calls = []

    def fake_convert_args_namespace(input_path, output):
        # Mock cmd_convert side effect: write a fake mp4 at the staging path
        from pathlib import Path as P
        P(output).parent.mkdir(parents=True, exist_ok=True)
        P(output).write_bytes(b"M" * 2048)

    def fake_cmd_convert(ns):
        calls.append(("convert", ns.input))
        from pathlib import Path as P
        out = P(ns.output) if ns.output else (
            cli._staging_dir() / (P(ns.input).stem + ".mp4"))
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"M" * 2048)
        return 0

    def fake_cmd_drive_upload(ns):
        calls.append(("drive", ns.file))
        return 0

    posted = []
    def fake_post_upload(url, title, lang):
        posted.append({"url": url, "title": title, "lang": lang})
        return {"message": "submitted (mock)"}

    monkeypatch.setattr(cli, "cmd_convert", fake_cmd_convert)
    monkeypatch.setattr(cli, "_post_upload", fake_post_upload)
    # We need cmd_drive_upload to also produce a download_url for orchestrator;
    # so monkeypatch the helper used by from-file path instead:
    monkeypatch.setattr(cli, "_drive_upload_file",
                        lambda path, folder=None, make_public=True:
                        {"drive_id": "FAKE", "download_url": "https://example.com/dl/FAKE",
                         "web_url": "https://drive/FAKE", "created": True})

    manifest = tmp_path / "manifest.jsonl"
    monkeypatch.setattr(cli, "_uploads_manifest_path", lambda: manifest)

    rc = cli.main(["upload", "--from-file", str(src), "--language", "ru"])
    assert rc == 0
    assert len(posted) == 1
    assert posted[0]["url"] == "https://example.com/dl/FAKE"
    # title auto-generated from filename
    assert "2026-01-20" in (posted[0]["title"] or "")
    # manifest received submitted line
    lines = manifest.read_text(encoding="utf-8").strip().splitlines()
    assert any('"status": "submitted"' in ln for ln in lines)
```

- [ ] **Step 2: Run — fails (`--from-file` raises NotImplemented)**

- [ ] **Step 3: Refactor `cmd_drive_upload` to expose helper + implement `--from-file`**

In `meetgeek_cli.py`, refactor `cmd_drive_upload` to call a new helper `_drive_upload_file` (so orchestrator can reuse without going through CLI):

Replace the body of `cmd_drive_upload` with:

```python
def _drive_upload_file(path: Path, folder: str | None = None,
                      make_public: bool = True) -> dict:
    src = Path(path).expanduser().resolve()
    if not src.exists():
        raise ApiError(f"file not found: {src}", exit_code=1)
    svc = _drive_service()
    if folder:
        parts = [p for p in folder.replace("\\", "/").split("/") if p]
    else:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        parts = [DRIVE_ROOT_FOLDER_NAME, date]
    parent_id: str | None = None
    for part in parts:
        parent_id = _drive_find_or_create_folder(svc, part, parent_id)
    folder_id = parent_id

    existing = _drive_find_file(svc, src.name, folder_id)
    if existing:
        if make_public:
            try:
                _drive_make_public(svc, existing["id"])
            except Exception:  # noqa: BLE001
                pass
        return {
            "drive_id": existing["id"],
            "web_url": existing.get("webViewLink"),
            "download_url": _drive_download_url(existing["id"]),
            "created": False,
        }

    from googleapiclient.http import MediaFileUpload
    media = MediaFileUpload(str(src), resumable=True)
    body = {"name": src.name, "parents": [folder_id]}
    file = svc.files().create(body=body, media_body=media,
                              fields="id,webViewLink").execute()
    if make_public:
        _drive_make_public(svc, file["id"])
    return {
        "drive_id": file["id"],
        "web_url": file.get("webViewLink"),
        "download_url": _drive_download_url(file["id"]),
        "created": True,
    }


def cmd_drive_upload(args: argparse.Namespace) -> int:
    info = _drive_upload_file(Path(args.file), folder=args.folder, make_public=args.make_public)
    _print_json(info)
    return 0
```

Add helper for title parsing + the orchestrator. After `cmd_upload`'s direct branch:

```python
_RECORDING_NAME_RE = re.compile(
    r"meetgeek-recording-(\d{4})-(\d{2})-(\d{2})T(\d{2})-(\d{2})-\d{2}-\d+Z"
)


def _title_from_filename(stem: str) -> str:
    m = _RECORDING_NAME_RE.search(stem)
    if m:
        y, mo, d, hh, mm = m.groups()
        return f"Meeting {y}-{mo}-{d} {hh}:{mm} UTC"
    return f"Meeting {stem}"


def _process_one_for_upload(src_path: Path, *, language: str | None,
                            title_override: str | None,
                            audio_only: bool, mix_mode: str,
                            manifest_path: Path) -> dict:
    """Run convert → drive → submit. Skips already-completed stages by
    consulting effective state in manifest. On per-stage failure writes
    `convert-failed` / `drive-failed` / `upload-rejected` then re-raises.
    """
    src = src_path.resolve()
    src_size = src.stat().st_size
    src_mtime = datetime.fromtimestamp(src.stat().st_mtime, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    base_meta = {
        "source_webm": str(src),
        "source_size_bytes": src_size,
        "source_mtime": src_mtime,
    }

    # Read effective state for resume decisions
    state = _read_uploads_manifest(manifest_path)
    rec = state.get(str(src), {}) or {}
    rec_status = rec.get("status")
    suffix = ".m4a" if audio_only else ".mp4"
    mp4_path = _staging_dir() / (src.stem + suffix)
    mp4_size: int

    # ── Stage 1: Convert ──────────────────────────────────────────────────
    cached_mp4 = rec.get("mp4_path")
    can_skip_convert = (
        rec_status in ("converted", "in-drive", "submitted")
        and cached_mp4
        and Path(cached_mp4).exists()
        and Path(cached_mp4).stat().st_size > 1024
    )
    if can_skip_convert:
        mp4_path = Path(cached_mp4)
        mp4_size = mp4_path.stat().st_size
        print(f"  [resume] convert ✓ (cached {mp4_path.name})", file=sys.stderr)
    else:
        try:
            mp4_path.parent.mkdir(parents=True, exist_ok=True)
            cmd_convert(argparse.Namespace(
                input=str(src), output=str(mp4_path),
                audio_only=audio_only, mix_mode=mix_mode, probe=False,
            ))
            mp4_size = mp4_path.stat().st_size
            _append_uploads_manifest({
                **base_meta,
                "mp4_path": str(mp4_path), "mp4_size_bytes": mp4_size,
                "status": "converted",
            }, manifest_path)
        except ApiError as e:
            _append_uploads_manifest({
                **base_meta,
                "status": "convert-failed", "error": str(e),
            }, manifest_path)
            raise

    # ── Stage 2: Drive upload ─────────────────────────────────────────────
    can_skip_drive = (
        rec_status in ("in-drive", "submitted")
        and rec.get("drive_id")
        and rec.get("drive_download_url")
    )
    if can_skip_drive:
        drive_info = {
            "drive_id": rec["drive_id"],
            "download_url": rec["drive_download_url"],
            "web_url": rec.get("drive_web_url"),
            "created": False,
        }
        print(f"  [resume] drive ✓ (cached {drive_info['drive_id']})", file=sys.stderr)
    else:
        try:
            drive_info = _drive_upload_file(mp4_path)
            _append_uploads_manifest({
                **base_meta,
                "mp4_path": str(mp4_path), "mp4_size_bytes": mp4_size,
                "drive_id": drive_info["drive_id"],
                "drive_download_url": drive_info["download_url"],
                "drive_web_url": drive_info.get("web_url"),
                "status": "in-drive",
            }, manifest_path)
        except ApiError as e:
            _append_uploads_manifest({
                **base_meta,
                "mp4_path": str(mp4_path), "mp4_size_bytes": mp4_size,
                "status": "drive-failed", "error": str(e),
            }, manifest_path)
            raise

    # ── Stage 3: Submit ───────────────────────────────────────────────────
    title = title_override or _title_from_filename(src.stem)
    try:
        resp = _post_upload(drive_info["download_url"], title, language)
    except ApiError as e:
        _append_uploads_manifest({
            **base_meta,
            "mp4_path": str(mp4_path), "mp4_size_bytes": mp4_size,
            "drive_id": drive_info["drive_id"],
            "drive_download_url": drive_info["download_url"],
            "title": title, "language": language,
            "status": "upload-rejected", "error": str(e),
        }, manifest_path)
        raise

    final = {
        **base_meta,
        "mp4_path": str(mp4_path), "mp4_size_bytes": mp4_size,
        "drive_id": drive_info["drive_id"],
        "drive_download_url": drive_info["download_url"],
        "title": title, "language": language,
        "submitted_at": _now_iso(),
        "upload_response_message": (resp.get("message") if isinstance(resp, dict) else None),
        "status": "submitted",
    }
    _append_uploads_manifest(final, manifest_path)
    return final
```

Then update the `--from-file` branch in `cmd_upload` to call this helper for a single path (glob support is Task 11):

```python
def cmd_upload(args: argparse.Namespace) -> int:
    if args.download_url:
        resp = _post_upload(args.download_url, args.title, args.language)
        _print_json({"status": "submitted", "response": resp})
        return 0

    if not args.from_file:
        raise ApiError("either --download-url or --from-file required", exit_code=2)

    src_path = Path(args.from_file).expanduser()
    if not src_path.exists() or not src_path.is_file():
        raise ApiError(f"--from-file expects an existing file (glob is Task 11): {src_path}",
                       exit_code=1)

    manifest_path = _uploads_manifest_path()
    final = _process_one_for_upload(
        src_path,
        language=args.language,
        title_override=args.title,
        audio_only=args.audio_only,
        mix_mode=args.mix_mode,
        manifest_path=manifest_path,
    )
    _print_json({"processed": 1, "skipped": 0, "errors": 0, "result": final})
    return 0
```

Add the new args to the upload subparser:

```python
    s.add_argument("--audio-only", action="store_true")
    s.add_argument("--mix-mode", choices=["amix", "first", "keep"], default="amix")
```

(insert into the existing `s = sub.add_parser("upload", ...)` block before `s.set_defaults(func=cmd_upload)`)

- [ ] **Step 4: Run orchestrator test**

```bash
C:/Users/stani/.h2t/venv/Scripts/python.exe -m pytest tests/test_meetgeek_cli.py::test_upload_from_file_chains_convert_drive_submit -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git -C C:/dev/h2t-skills add plugins/h2t-ops/skills/meetgeek/
git -C C:/dev/h2t-skills commit -m "feat(h2t-ops): meetgeek upload --from-file (single file orchestrator) (#93)"
```

---

## Task 11: Glob expansion + per-file batch progress

**Files:**
- Modify: same

- [ ] **Step 1: Write failing test — glob expanded, both files processed**

```python
def test_upload_from_file_glob_processes_all(cli, tmp_path, monkeypatch):
    a = tmp_path / "meetgeek-recording-2026-01-01T10-00-00-000Z.webm"
    b = tmp_path / "meetgeek-recording-2026-01-02T11-00-00-000Z.webm"
    a.write_bytes(b"x" * 1024); b.write_bytes(b"x" * 1024)

    posted = []
    def fake_process(src, **kw):
        posted.append(src.name)
        return {"source_webm": str(src), "status": "submitted"}
    monkeypatch.setattr(cli, "_process_one_for_upload", fake_process)

    manifest = tmp_path / "manifest.jsonl"
    monkeypatch.setattr(cli, "_uploads_manifest_path", lambda: manifest)

    pattern = str(tmp_path / "meetgeek-recording-*.webm")
    rc = cli.main(["upload", "--from-file", pattern])
    assert rc == 0
    assert sorted(posted) == [a.name, b.name]
```

- [ ] **Step 2: Run — fails (path-existence check rejects glob)**

- [ ] **Step 3: Replace single-file branch with glob expansion**

In `cmd_upload`, replace the `if not src_path.exists() ...` block with:

```python
    raw = args.from_file
    raw_path = Path(raw).expanduser()
    if raw_path.is_dir():
        # Directory mode: recursive *.webm walk
        expanded = sorted(raw_path.rglob("*.webm"))
    elif raw_path.is_file():
        # Direct file path
        expanded = [raw_path]
    else:
        # Glob fallback (string contains wildcard or path doesn't exist as-is)
        expanded = sorted(Path(p) for p in glob.glob(str(raw_path), recursive=True))
    if not expanded:
        raise ApiError(f"no files match: {raw}", exit_code=1)

    manifest_path = _uploads_manifest_path()
    state = _read_uploads_manifest(manifest_path)
    processed = 0
    skipped = 0
    errors = 0
    results: list[dict] = []
    total = len(expanded)
    for i, src_path in enumerate(expanded, 1):
        if not src_path.is_file():
            continue
        size = src_path.stat().st_size
        mtime = datetime.fromtimestamp(src_path.stat().st_mtime, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        if args.skip_existing and _is_already_submitted(state, str(src_path.resolve()),
                                                        size=size, mtime=mtime):
            print(f"[{i}/{total}] {src_path.name}  skip (already submitted)", file=sys.stderr)
            skipped += 1
            continue
        if args.dry_run:
            print(f"[{i}/{total}] {src_path.name}  would: convert+drive+upload", file=sys.stderr)
            continue
        try:
            print(f"[{i}/{total}] {src_path.name}  convert ...", file=sys.stderr)
            final = _process_one_for_upload(
                src_path,
                language=args.language,
                title_override=args.title,
                audio_only=args.audio_only,
                mix_mode=args.mix_mode,
                manifest_path=manifest_path,
            )
            results.append(final)
            processed += 1
            print(f"[{i}/{total}] {src_path.name}  ✓ submitted", file=sys.stderr)
        except ApiError as e:
            print(f"[{i}/{total}] {src_path.name}  ✗ {e}", file=sys.stderr)
            errors += 1
            # Per-stage handler in _process_one_for_upload already wrote the
            # appropriate convert-failed / drive-failed / upload-rejected entry
            # to manifest. Don't add a synthetic "upload-failed" line — it
            # would drift from the spec's status enum.
            continue

    _print_json({"processed": processed, "skipped": skipped, "errors": errors,
                 "drive_folder": f"{DRIVE_ROOT_FOLDER_NAME}/{datetime.now(timezone.utc).strftime('%Y-%m-%d')}",
                 "results_count": len(results)})
    return 0 if errors == 0 else 1
```

Add `import glob` at top of file.

Add args to the `upload` subparser (before `set_defaults`):

```python
    s.add_argument("--skip-existing", action=argparse.BooleanOptionalAction, default=True,
                   help="Skip files already in manifest with status=submitted (default on)")
    s.add_argument("--dry-run", action="store_true",
                   help="Print plan; do not convert/upload")
```

- [ ] **Step 4: Run glob test**

```bash
C:/Users/stani/.h2t/venv/Scripts/python.exe -m pytest tests/test_meetgeek_cli.py::test_upload_from_file_glob_processes_all -v
```

Expected: PASS.

- [ ] **Step 5: Add skip-existing + dry-run + per-file-error-continue tests**

```python
def test_upload_from_file_skip_existing(cli, tmp_path, monkeypatch):
    src = tmp_path / "meetgeek-recording-2026-01-01T10-00-00-000Z.webm"
    src.write_bytes(b"x" * 1024)

    size = src.stat().st_size
    mtime = datetime.fromtimestamp(src.stat().st_mtime, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text(json.dumps({
        "source_webm": str(src.resolve()),
        "source_size_bytes": size, "source_mtime": mtime, "status": "submitted",
    }) + "\n", encoding="utf-8")

    monkeypatch.setattr(cli, "_uploads_manifest_path", lambda: manifest)
    called = {"n": 0}
    monkeypatch.setattr(cli, "_process_one_for_upload",
                        lambda *a, **kw: called.__setitem__("n", called["n"] + 1))

    rc = cli.main(["upload", "--from-file", str(src)])
    assert rc == 0
    assert called["n"] == 0


def test_upload_from_file_dry_run_no_calls(cli, tmp_path, monkeypatch):
    src = tmp_path / "meetgeek-recording-2026-01-01T10-00-00-000Z.webm"
    src.write_bytes(b"x" * 1024)
    monkeypatch.setattr(cli, "_uploads_manifest_path", lambda: tmp_path / "m.jsonl")
    called = {"n": 0}
    monkeypatch.setattr(cli, "_process_one_for_upload",
                        lambda *a, **kw: called.__setitem__("n", called["n"] + 1))
    rc = cli.main(["upload", "--from-file", str(src), "--dry-run"])
    assert rc == 0
    assert called["n"] == 0


def test_upload_from_file_continues_on_per_file_error(cli, tmp_path, monkeypatch):
    a = tmp_path / "meetgeek-recording-2026-01-01T10-00-00-000Z.webm"
    b = tmp_path / "meetgeek-recording-2026-01-02T10-00-00-000Z.webm"
    c = tmp_path / "meetgeek-recording-2026-01-03T10-00-00-000Z.webm"
    for f in (a, b, c): f.write_bytes(b"x" * 1024)

    def proc(src, **kw):
        if src.name == b.name:
            raise cli.ApiError("boom on B", exit_code=1)
        return {"source_webm": str(src), "status": "submitted"}
    monkeypatch.setattr(cli, "_process_one_for_upload", proc)
    monkeypatch.setattr(cli, "_uploads_manifest_path", lambda: tmp_path / "m.jsonl")

    rc = cli.main(["upload", "--from-file", str(tmp_path / "meetgeek-recording-*.webm")])
    assert rc == 1  # errors > 0
```

- [ ] **Step 6: Run all upload tests**

```bash
C:/Users/stani/.h2t/venv/Scripts/python.exe -m pytest tests/test_meetgeek_cli.py -k upload -v
```

Expected: all pass.

- [ ] **Step 7: Run full suite**

```bash
C:/Users/stani/.h2t/venv/Scripts/python.exe -m pytest tests/test_meetgeek_cli.py -q
```

Expected: all green.

- [ ] **Step 8: Commit**

```bash
git -C C:/dev/h2t-skills add plugins/h2t-ops/skills/meetgeek/
git -C C:/dev/h2t-skills commit -m "feat(h2t-ops): meetgeek upload --from-file glob + skip/dry-run + error-continue (#93)"
```

---

## Task 12: Resume tests + directory-input test

Resume logic itself was added inline in Task 10's `_process_one_for_upload` (the `can_skip_convert` / `can_skip_drive` branches and per-stage failure status writes). This task locks the behaviour down with TDD coverage and adds the directory-input case missing from the glob test in Task 11.

**Files:**
- Test: `plugins/h2t-ops/skills/meetgeek/tests/test_meetgeek_cli.py`

- [ ] **Step 1: Resume from `converted` state — convert is skipped**

```python
def test_upload_resumes_from_converted_state(cli, tmp_path, monkeypatch):
    src = tmp_path / "meetgeek-recording-2026-01-01T10-00-00-000Z.webm"
    src.write_bytes(b"x" * 1024)
    size = src.stat().st_size
    mtime = datetime.fromtimestamp(src.stat().st_mtime, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    cached_mp4 = tmp_path / "cached.mp4"
    cached_mp4.write_bytes(b"M" * 2048)

    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text(json.dumps({
        "source_webm": str(src.resolve()),
        "source_size_bytes": size, "source_mtime": mtime,
        "mp4_path": str(cached_mp4), "mp4_size_bytes": 2048,
        "status": "converted",
    }) + "\n", encoding="utf-8")
    monkeypatch.setattr(cli, "_uploads_manifest_path", lambda: manifest)

    convert_called = {"n": 0}
    def fake_convert(ns):
        convert_called["n"] += 1
        return 0
    monkeypatch.setattr(cli, "cmd_convert", fake_convert)

    monkeypatch.setattr(cli, "_drive_upload_file",
                        lambda path, **kw: {"drive_id": "DID",
                                            "download_url": "https://x/d",
                                            "web_url": "https://x/w", "created": True})
    monkeypatch.setattr(cli, "_post_upload",
                        lambda url, title, lang: {"message": "ok"})

    rc = cli.main(["upload", "--from-file", str(src), "--language", "ru", "--no-skip-existing"])
    assert rc == 0
    assert convert_called["n"] == 0  # convert skipped via resume
```

- [ ] **Step 2: Resume from `in-drive` state — both convert AND drive are skipped**

```python
def test_upload_resumes_from_in_drive_state(cli, tmp_path, monkeypatch):
    src = tmp_path / "meetgeek-recording-2026-01-01T10-00-00-000Z.webm"
    src.write_bytes(b"x" * 1024)
    size = src.stat().st_size
    mtime = datetime.fromtimestamp(src.stat().st_mtime, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    cached_mp4 = tmp_path / "cached.mp4"
    cached_mp4.write_bytes(b"M" * 2048)

    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text(json.dumps({
        "source_webm": str(src.resolve()),
        "source_size_bytes": size, "source_mtime": mtime,
        "mp4_path": str(cached_mp4), "mp4_size_bytes": 2048,
        "drive_id": "EXISTING_DID",
        "drive_download_url": "https://drive.google.com/uc?export=download&id=EXISTING_DID",
        "status": "in-drive",
    }) + "\n", encoding="utf-8")
    monkeypatch.setattr(cli, "_uploads_manifest_path", lambda: manifest)

    convert_called = {"n": 0}
    drive_called = {"n": 0}
    monkeypatch.setattr(cli, "cmd_convert",
                        lambda ns: convert_called.__setitem__("n", convert_called["n"] + 1) or 0)
    monkeypatch.setattr(cli, "_drive_upload_file",
                        lambda path, **kw: drive_called.__setitem__("n", drive_called["n"] + 1) or {})

    posted = []
    monkeypatch.setattr(cli, "_post_upload",
                        lambda url, title, lang: posted.append({"url": url}) or {"message": "ok"})

    rc = cli.main(["upload", "--from-file", str(src), "--language", "ru", "--no-skip-existing"])
    assert rc == 0
    assert convert_called["n"] == 0
    assert drive_called["n"] == 0
    assert len(posted) == 1
    assert posted[0]["url"] == "https://drive.google.com/uc?export=download&id=EXISTING_DID"
```

- [ ] **Step 3: Per-stage failure writes correct status (drive-failed, not upload-failed)**

```python
def test_upload_drive_failure_writes_drive_failed_status(cli, tmp_path, monkeypatch):
    src = tmp_path / "meetgeek-recording-2026-01-01T10-00-00-000Z.webm"
    src.write_bytes(b"x" * 1024)
    manifest = tmp_path / "manifest.jsonl"
    monkeypatch.setattr(cli, "_uploads_manifest_path", lambda: manifest)

    # convert succeeds (mock), drive raises ApiError
    def fake_convert(ns):
        from pathlib import Path as P
        out = P(ns.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"M" * 2048)
        return 0
    monkeypatch.setattr(cli, "cmd_convert", fake_convert)
    monkeypatch.setattr(cli, "_drive_upload_file",
                        lambda *a, **kw: (_ for _ in ()).throw(cli.ApiError("drive boom", exit_code=1)))

    rc = cli.main(["upload", "--from-file", str(src)])
    assert rc == 1
    lines = [json.loads(ln) for ln in manifest.read_text(encoding="utf-8").strip().splitlines()]
    statuses = [r["status"] for r in lines]
    assert "converted" in statuses
    assert "drive-failed" in statuses
    assert "upload-failed" not in statuses  # spec enum compliance
    assert "upload-rejected" not in statuses  # drive failure ≠ upload failure
```

- [ ] **Step 4: Directory input mode — recursive .webm walk**

```python
def test_upload_from_file_directory_walks_recursively(cli, tmp_path, monkeypatch):
    nested = tmp_path / "nested"
    nested.mkdir()
    a = tmp_path / "meetgeek-recording-2026-01-01T10-00-00-000Z.webm"
    b = nested / "meetgeek-recording-2026-01-02T10-00-00-000Z.webm"
    for f in (a, b):
        f.write_bytes(b"x" * 1024)

    seen = []
    monkeypatch.setattr(cli, "_process_one_for_upload",
                        lambda src, **kw: seen.append(src.name) or {"status": "submitted"})
    monkeypatch.setattr(cli, "_uploads_manifest_path", lambda: tmp_path / "m.jsonl")

    rc = cli.main(["upload", "--from-file", str(tmp_path)])
    assert rc == 0
    assert sorted(seen) == [a.name, b.name]
```

- [ ] **Step 5: Run all four tests**

```bash
C:/Users/stani/.h2t/venv/Scripts/python.exe -m pytest tests/test_meetgeek_cli.py -k "resumes_from or drive_failure or directory_walks" -v
```

Expected: 4 passed.

- [ ] **Step 6: Run full suite**

```bash
C:/Users/stani/.h2t/venv/Scripts/python.exe -m pytest tests/test_meetgeek_cli.py -q
```

Expected: all green.

- [ ] **Step 7: Commit**

```bash
git -C C:/dev/h2t-skills add plugins/h2t-ops/skills/meetgeek/tests/test_meetgeek_cli.py
git -C C:/dev/h2t-skills commit -m "test(h2t-ops): meetgeek resume + directory + drive-failed status (#93)"
```

---

## Task 13: Update `SKILL.md` with new commands

**Files:**
- Modify: `plugins/h2t-ops/skills/meetgeek/SKILL.md`

- [ ] **Step 1: Open SKILL.md and add a new "Upload (one-shot or batch)" section**

Insert this section *before* the existing "Bulk sync (главная команда)" section (so reading order matches user intent: pull → upload → sync):

````markdown
### Upload local recordings

Three composable commands for `webm → mp4 → Drive → MeetGeek` flow.

```bash
# Convert (default: webm → mp4 H.264/AAC; multi-track audio → amix)
$CLI convert <in.webm> [-o out.mp4] [--audio-only] [--mix-mode amix|first|keep] [--probe]

# Upload to Drive (default folder: MeetGeek Uploads/{YYYY-MM-DD}/, share=anyone)
$CLI drive-upload <file> [--folder "MeetGeek Uploads/2026-05-06"] [--no-make-public]

# Submit one URL directly (presumes you already have a public URL)
$CLI upload --download-url URL [--title T] [--language ru|en|auto]

# Batch — convert + drive-upload + submit for many files
$CLI upload --from-file '~/Downloads/meetgeek-recording-*.webm' \
            [--audio-only] [--mix-mode amix|first|keep] \
            [--language ru] [--no-skip-existing] [--dry-run]
```

State for resume lives in `~/.dor/lake/meetgeek/uploads-staging/`:
- `{YYYY-MM-DD}/*.mp4` — converted cache (skip re-encode on retry)
- `manifest.jsonl` — append-only state log; effective state per source = last line.

Recipes:
- One file end-to-end: `$CLI upload --from-file ~/Downloads/meetgeek-recording-2026-01-20T15-44-31-132Z.webm --language ru`
- Backfill 16 files (default skip-existing keeps it idempotent): `$CLI upload --from-file '~/Downloads/meetgeek-recording-*.webm' --language ru`
- Force re-process: append `--no-skip-existing` (Drive idempotent search and cached mp4 still avoid duplicate work).

Dependencies (auto-installed once):
```bash
~/.h2t/venv/Scripts/python.exe -m pip install imageio-ffmpeg   # Windows
~/.h2t/venv/bin/python -m pip install imageio-ffmpeg           # macOS
```
````

- [ ] **Step 2: Verify SKILL.md frontmatter still parses (visual check is enough — no schema test)**

- [ ] **Step 3: Commit**

```bash
git -C C:/dev/h2t-skills add plugins/h2t-ops/skills/meetgeek/SKILL.md
git -C C:/dev/h2t-skills commit -m "docs(h2t-ops): SKILL.md — convert/drive-upload/upload commands (#93)"
```

---

## Task 14: Bump h2t-ops to 1.1.0 and sync marketplace

**Files:**
- Modify: `plugins/h2t-ops/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`

- [ ] **Step 1: Run bump script**

```bash
PYTHONIOENCODING=utf-8 C:/Users/stani/.h2t/venv/Scripts/python.exe \
  C:/dev/h2t-skills/scripts/bump_plugin.py h2t-ops 1.1.0
```

Expected: `✓ h2t-ops: 1.0.7 → 1.1.0`, two files updated.

- [ ] **Step 2: Verify marketplace sync**

```bash
PYTHONIOENCODING=utf-8 C:/Users/stani/.h2t/venv/Scripts/python.exe \
  C:/dev/h2t-skills/scripts/check_marketplace_sync.py
```

Expected: `✓ marketplace synced (7 plugins)`.

- [ ] **Step 3: Run full test suite once more**

```bash
cd C:/dev/h2t-skills/plugins/h2t-ops/skills/meetgeek && \
  C:/Users/stani/.h2t/venv/Scripts/python.exe -m pytest tests/ -q
```

Expected: all green.

- [ ] **Step 4: Commit**

```bash
git -C C:/dev/h2t-skills add .claude-plugin/marketplace.json plugins/h2t-ops/.claude-plugin/plugin.json
git -C C:/dev/h2t-skills commit -m "chore(h2t-ops): bump 1.0.7 → 1.1.0 (upload + media conversion)"
```

---

## Task 15: 🚦 LIVE FINAL — batch all 16 webm files on user's Mac

**Files:** none modified — this is a manual end-to-end gate.

- [ ] **Step 1: Push commits to origin**

```bash
git -C C:/dev/h2t-skills push origin main
```

(Engineer asks user permission before pushing if not already explicit. The push is required for the user to be able to install the new version on the Mac via `/plugin marketplace update lichtpfad`.)

- [ ] **Step 2: User reloads plugin on Mac**

In Claude Code on Mac:
```
/plugin marketplace update lichtpfad
/plugin uninstall h2t-ops
/plugin install h2t-ops@lichtpfad
/reload-plugins
```

- [ ] **Step 3: Install ffmpeg pip dep on Mac venv**

```bash
~/.h2t/venv/bin/python -m pip install imageio-ffmpeg
```

- [ ] **Step 4: Run dry-run first**

```bash
~/.h2t/venv/bin/python ~/.../h2t-skills/plugins/h2t-ops/skills/meetgeek/scripts/meetgeek_cli.py \
  upload --from-file '~/Downloads/meetgeek-recording-*.webm' --language ru --dry-run
```

Expected: prints 16 "would: convert+drive+upload" lines, exit 0.

- [ ] **Step 5: Run real batch**

```bash
~/.h2t/venv/bin/python .../meetgeek_cli.py \
  upload --from-file '~/Downloads/meetgeek-recording-*.webm' --language ru
```

Expected stderr: 16 progress lines `[N/16] meetgeek-recording-...  ✓ submitted`.
Expected stdout: JSON `{"processed": 16, "skipped": 0, "errors": 0, ...}`.

- [ ] **Step 6: Wait 30–90 minutes (depends on MeetGeek backlog), then verify**

```bash
~/.h2t/venv/bin/python .../meetgeek_cli.py list --limit 30
```

Expected: 16 new meetings with auto-generated titles `Meeting YYYY-MM-DD HH:MM UTC` appearing.

- [ ] **Step 7: Spot-check transcripts**

Pick 2 of the new `meeting_id`s and run:
```bash
~/.h2t/venv/bin/python .../meetgeek_cli.py transcript <id> --format md
```

Expected: real Russian transcript text, attendees populated from speakers.

- [ ] **Step 8: If all green — close issue #93**

```bash
gh issue comment 93 --body "Shipped in h2t-ops 1.1.0. Live batch validated on user mac with 16 webm files. Closing."
gh issue close 93
```

If any per-file error during Step 5 — open follow-up issue with the affected file(s) and the manifest entry, but the milestone is still complete (errors are file-specific, not feature-broken).

---

## Self-Review Checklist (run after writing this plan, before handoff)

- [x] **Spec coverage:** Sections 4.1 (convert) → Tasks 2–4. 4.2 (drive-upload) → Tasks 5–6. 4.3 (upload direct + file/glob/directory) → Tasks 7, 10, 11 (directory branch in 11). Section 5 (data flow) → 10–11. Section 6 (error handling) → 11 (per-stage statuses written by `_process_one_for_upload`). Manifest reader semantics + resume from `converted` / `in-drive` → Task 10 inline implementation, Task 12 tests. Status enum (`convert-failed | converted | drive-failed | in-drive | upload-rejected | submitted`) — no synthetic `upload-failed` line. Section 7 (testing) → all tasks include their tests; live baseline 15 + ~16 new ≈ 31. Section 7.5 (live gate) → Task 8 with explicit STOP-condition. Section 9 (versioning, 1.0.7 → 1.1.0) → Task 14.
- [x] **Placeholder scan:** All steps contain concrete code or commands with expected outputs. No "TBD" / "implement later" / "similar to". The only places that say "Task N" are forward references that already point to fully-spelled later tasks.
- [x] **Type/name consistency:** `_ffmpeg_probe`, `_ffmpeg_exe`, `_build_convert_cmd`, `_drive_service`, `_drive_find_or_create_folder`, `_drive_find_file`, `_drive_make_public`, `_drive_download_url`, `_drive_upload_file`, `_uploads_manifest_path`, `_read_uploads_manifest`, `_append_uploads_manifest`, `_is_already_submitted`, `_post_upload`, `_process_one_for_upload`, `_title_from_filename`, `_staging_dir`, `cmd_convert`, `cmd_drive_upload`, `cmd_upload`, `_RECORDING_NAME_RE`, `_DURATION_RE`, `_STREAM_AUDIO_RE`, `_STREAM_VIDEO_RE`, `DRIVE_TOKEN_FILE`, `DRIVE_CONFIG_DIR`, `DRIVE_CREDENTIALS_FILE`, `DRIVE_SCOPES`, `DRIVE_ROOT_FOLDER_NAME` — used consistently across tasks.
- [x] **Live gate placement:** Task 8 sits between direct `cmd_upload` (Task 7) and the manifest/orchestrator/glob work (Tasks 9–11). If the Drive `download_url` assumption fails, we discover before writing resume logic.

---

## Open follow-up (out of this plan, but worth tracking)

- Auto-cleanup of Drive folder past N days (separate issue, low priority)
- Per-file `--title` override in batch (single user-provided default → all files)
- Webhook config registration with MeetGeek so processing-completion events flow to our `webhook-server` (depends on MeetGeek API surface; needs separate probe)
- Source formats other than webm/mp4/m4a verified (currently the recipe is robust but only smoke-tested on webm)
