---
name: snap
description: "Desktop screenshot & interact utility for AI agents. Capture windows, click, type, hover in any desktop app. Use when agent needs visual feedback from native applications (not browsers). Triggers: 'snap', 'h2t:snap', 'h2t-snap', 'screenshot desktop', 'capture window', 'click in app', 'скриншот приложения', 'кликни в окне'."
compatibility: "Requires the h2t-snap binary on PATH — prebuilt for macOS and Windows in
  lichtpfad/h2t-snap, free. On macOS it also needs Screen Recording (capture) and
  Accessibility (click, type); exit code 5 is a permission refusal, not a missing window."
metadata:
  author: lichtpfad
  version: 0.1.0
---

# h2t-snap — Desktop Visual Feedback for Agents

Eyes and hands for AI agents on the desktop. One binary, no dependencies.

## When to Use

- Need to **see** a desktop application (TouchDesigner, Houdini, Photoshop, Finder, Excel, etc.)
- Need to **interact** with native GUI (click buttons, type text, hover)
- Need visual verification of a desktop action
- NOT for browsers — use Playwright or claude-in-chrome for those

## Prerequisites

h2t-snap must be installed. Check:

```bash
h2t-snap --version
```

If not found, build from source:

```bash
# macOS
git clone https://github.com/lichtpfad/h2t-snap && cd h2t-snap
swift build -c release
cp .build/release/h2t-snap /usr/local/bin/

# Windows — download h2t-snap.exe from GitHub Releases
```

**macOS permissions:** Screen Recording (for capture) + Accessibility (for click/type). Granted on first run via system dialog. Exit code 5 = permission denied.

## Agent Workflow

The core loop: **capture → decide → act → verify**

### Step 1: See what's running

```bash
h2t-snap list
h2t-snap list --filter "TouchDesigner"
```

Returns JSON array: `[{"index":0, "window_id":12345, "title":"...", "owner":"...", "rect":[x,y,w,h]}]`

### Step 2: Capture a screenshot

```bash
h2t-snap capture --title "AppName" --json
```

Returns: `{"path":"/tmp/h2t-snap/snap_20260331.png", "width":1920, "height":1080, "window":"AppName", "timestamp":"..."}`

Then read the image with the Read tool to see it.

### Step 3: Act

```bash
# Click (coordinates are window-relative, top-left = 0,0)
h2t-snap click --title "AppName" --x 450 --y 320

# Double click
h2t-snap dclick --title "AppName" --x 450 --y 320

# Right click
h2t-snap rclick --title "AppName" --x 450 --y 320

# Type text at position (clicks first, then types)
h2t-snap type --title "AppName" --x 300 --y 200 --text "hello"

# Hover
h2t-snap hover --title "AppName" --x 200 --y 100

# Modifier keys
h2t-snap click --title "AppName" --x 100 --y 100 --ctrl
h2t-snap click --title "AppName" --x 100 --y 100 --shift
```

### Step 4: Verify

```bash
h2t-snap capture --title "AppName" --json
# Read the new screenshot to confirm the action worked
```

## Safety

### Dry-run: preview without executing

```bash
h2t-snap click --title "AppName" --x 450 --y 320 --dry-run
```

Returns JSON with action, coordinates (window-relative + screen-absolute), window info — without clicking.

### Safe-zone: restrict click area

```bash
h2t-snap click --title "AppName" --x 450 --y 320 --safe-zone "0,50,800,600"
```

Exits with code 3 if click is outside the rectangle. Use to avoid titlebar, close buttons, etc.

**Best practice:** Calculate safe-zone from window rect: skip first ~30px (titlebar), restrict to content area.

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Window not found |
| 2 | Capture failed |
| 3 | Interact failed / safe-zone violation |
| 4 | Ambiguous title (multiple windows matched) |
| 5 | Permission denied (macOS) |

## Platform Notes

| | macOS | Windows |
|---|---|---|
| Window ID flag | `--window-id` | `--hwnd` |
| Cursor | CGEvent moves real cursor | PostMessage (background) |
| Permissions | Screen Recording + Accessibility | None |
| Binary | 2.3 MB (Swift) | 17 MB (PyInstaller) |
| Display flag | `--display N` | `--monitor N` |

## Rules for Agents

1. **Always capture before and after** interaction — verify what you see
2. **Use --dry-run** when uncertain about coordinates
3. **Use --safe-zone** to prevent clicks outside intended area
4. **Never click without seeing** — always capture first
5. If exit code 5: tell user to grant permissions in System Settings
6. If exit code 4: use `list` to find exact `--window-id`
