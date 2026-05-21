---
title: "h2t-creative Phase 2b: Aesthetic Recovery Implementation Plan"
status: "draft"
date: "2026-05-03"
milestone: ""
---
# h2t-creative Phase 2b: Aesthetic Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Phase 2a shared components obey the legacy profile aesthetics — standardize the token vocabulary, inject web fonts, restyle shared CSS to use only canonical tokens, and produce a visual regression baseline.

**Architecture:** Phase 2b is not new design work. It is aesthetic recovery: make Phase 2a shared components obey the legacy profile aesthetics that already existed before the rewrite. Four concrete changes: (1) every profile palette exports canonical color tokens and every tokens.css exports canonical font tokens; (2) assembler reads `profile.yaml` and injects Google Fonts `<link>` tags; (3) shared component CSS uses only canonical tokens; (4) screenshots establish a visual regression baseline per profile. All work is in `plugins/h2t-creative/`. No new components. No generators.

**Tech Stack:** Python 3.11 via `py -3.11` (Windows py launcher), pytest 9.0.2, PyYAML, CSS custom properties, Google Fonts, h2t-tools screenshot (`C:/dev/h2t-tools`).

**Environment note:** All `py -3.11` commands are written for the user's terminal (Windows py launcher at `C:\Windows\py.exe`). If `py -3.11` is unavailable in the agent shell, first resolve a working Python 3.11 path with the user; do not guess or use the broken `.venv`.

---

## File Map

### New files
- `plugins/h2t-creative/tests/test_token_contract.py` — all Token Contract v2 tests
- `plugins/h2t-creative/tests/test_font_loading.py` — font link injection tests
- `plugins/h2t-creative/profiles/h2t-editorial/profile.yaml` — declares web_fonts
- `plugins/h2t-creative/profiles/h2t-graphs/profile.yaml`
- `plugins/h2t-creative/profiles/h2t-mono/profile.yaml`
- `plugins/h2t-creative/profiles/h2t-pfad/profile.yaml`
- `plugins/h2t-creative/profiles/h2t-terminal/profile.yaml`
- `docs/visual-regression/2026-05-03/checklist.md`

### Modified files
- 14 palette CSS files — add canonical color aliases
- 6 `tokens.css` files — add canonical font aliases
- `plugins/h2t-creative/assembler.py` — `_load_profile_config`, `_build_font_links`, template + caller updates
- 6 shared component CSS files — migrate to canonical tokens
- `plugins/h2t-creative/.claude-plugin/plugin.json` — 1.2.0
- `.claude-plugin/marketplace.json` — 1.2.0 (root-level registry)

---

### Task 1: Token Contract v2 — canonical aliases in every palette + tokens.css

**Token contract:**
- Color (in `palettes/*.css`): `--color-text`, `--color-text-dim`, `--color-on-accent`, `--color-accent-hover`
- Font (in `tokens.css`): `--font-display`, `--font-body`, `--font-mono`

Profiles that define `--color-fg` (default, pfad) add `--color-text: var(--color-fg)` as alias. Profiles that define `--color-muted` (default) add `--color-text-dim: var(--color-muted)`. Others already have `--color-text`/`--color-text-dim`. Profiles that use `--font` (mono, pfad, terminal) add `--font-display/body/mono: var(--font)`. h2t-graphs gets `--font-display: var(--font-sans)` + `--font-body: var(--font-mono)`.

**Files:**
- Create: `plugins/h2t-creative/tests/test_token_contract.py`
- Modify: all 14 palette CSS files + 6 tokens.css files

- [ ] **Step 1.1: Write the failing tests**

Create `plugins/h2t-creative/tests/test_token_contract.py`:

```python
"""Token Contract v2: every palette + tokens.css exports canonical token names."""
import pytest
from pathlib import Path
import assembler as asm

PROFILES = {
    "h2t-default":   ["default"],
    "h2t-editorial": ["default", "night", "warm"],
    "h2t-graphs":    ["default", "blue", "green"],
    "h2t-mono":      ["default", "blue", "white"],
    "h2t-pfad":      ["default"],
    "h2t-terminal":  ["default", "amber", "cyan"],
}


@pytest.mark.parametrize("profile,palette", [
    (p, pal) for p, pals in PROFILES.items() for pal in pals
])
def test_palette_canonical_color_tokens(profile, palette):
    css = (asm.PROFILES_DIR / profile / "palettes" / f"{palette}.css").read_text()
    assert "--color-text:" in css, f"{profile}/{palette}: missing --color-text"
    assert "--color-text-dim:" in css, f"{profile}/{palette}: missing --color-text-dim"
    assert "--color-on-accent:" in css, f"{profile}/{palette}: missing --color-on-accent"
    assert "--color-accent-hover:" in css, f"{profile}/{palette}: missing --color-accent-hover"


@pytest.mark.parametrize("profile", list(PROFILES.keys()))
def test_tokens_css_canonical_font_tokens(profile):
    css = (asm.PROFILES_DIR / profile / "tokens.css").read_text()
    assert "--font-display:" in css, f"{profile}: missing --font-display in tokens.css"
    assert "--font-body:" in css, f"{profile}: missing --font-body in tokens.css"
    assert "--font-mono:" in css, f"{profile}: missing --font-mono in tokens.css"
```

- [ ] **Step 1.2: Run tests — verify FAIL**

Run from `C:/dev/h2t-skills/`:
```
py -3.11 -m pytest plugins/h2t-creative/tests/test_token_contract.py -v
```
Expected: 20 FAILED — missing tokens in each palette/tokens file.

- [ ] **Step 1.3: Update all 14 palette CSS files**

Write the complete content of each file (existing vars + new aliases appended inside `:root {}`):

**`plugins/h2t-creative/profiles/h2t-default/palettes/default.css`:**
```css
:root {
  --color-bg: #ffffff;
  --color-fg: #0a0a0a;
  --color-accent: #1a1aff;
  --color-accent-hover: #0000cc;
  --color-muted: #6b7280;
  --color-surface: #f5f5f5;
  --color-border: #e5e7eb;
  --color-text: var(--color-fg);
  --color-text-dim: var(--color-muted);
  --color-on-accent: #ffffff;
}
```

**`plugins/h2t-creative/profiles/h2t-editorial/palettes/default.css`:**
```css
:root {
  --color-bg: #faf9f6;
  --color-bg-light: #f0eeeb;
  --color-bg-card: #ffffff;
  --color-text: #1a1a1a;
  --color-text-dim: #6b6b6b;
  --color-accent: #c45a3c;
  --color-border: #e0ddd8;
  --color-accent-hover: var(--color-accent);
  --color-on-accent: #ffffff;
}
```

**`plugins/h2t-creative/profiles/h2t-editorial/palettes/warm.css`:**
```css
:root {
  --color-bg: #fdf8f0;
  --color-bg-light: #f5ede0;
  --color-bg-card: #fffdf9;
  --color-text: #2a1f14;
  --color-text-dim: #8a7a6a;
  --color-accent: #b85c30;
  --color-border: #e8ddd0;
  --color-accent-hover: var(--color-accent);
  --color-on-accent: #ffffff;
}
```

**`plugins/h2t-creative/profiles/h2t-editorial/palettes/night.css`:**
```css
:root {
  --color-bg: #1a1614;
  --color-bg-light: #242018;
  --color-bg-card: #2a2620;
  --color-text: #e8dfd4;
  --color-text-dim: #9a9080;
  --color-accent: #d4aa50;
  --color-border: #403830;
  --color-accent-hover: var(--color-accent);
  --color-on-accent: #0a0a0a;
}
```

**`plugins/h2t-creative/profiles/h2t-graphs/palettes/default.css`:**
```css
:root {
  --color-bg: #060609;
  --color-bg2: #0a0a10;
  --color-surface: #0e0e16;
  --color-accent: #e94560;
  --color-accent-glow: rgba(233,69,96,0.4);
  --color-green: #00ff88;
  --color-blue: #4a9eff;
  --color-amber: #ffb800;
  --color-text: #a0a0b8;
  --color-text-hi: #d0d0e0;
  --color-text-dim: #3a3a50;
  --color-border: rgba(233,69,96,0.12);
  --color-accent-hover: var(--color-accent);
  --color-on-accent: #ffffff;
}
```

**`plugins/h2t-creative/profiles/h2t-graphs/palettes/blue.css`:**
```css
:root {
  --color-bg: #060609;
  --color-bg2: #0a0a10;
  --color-surface: #0e0e16;
  --color-accent: #4a9eff;
  --color-accent-glow: rgba(74,158,255,0.4);
  --color-green: #00ff88;
  --color-blue: #4a9eff;
  --color-amber: #ffb800;
  --color-text: #a0a0b8;
  --color-text-hi: #d0d0e0;
  --color-text-dim: #3a3a50;
  --color-border: rgba(74,158,255,0.12);
  --color-accent-hover: var(--color-accent);
  --color-on-accent: #ffffff;
}
```

**`plugins/h2t-creative/profiles/h2t-graphs/palettes/green.css`:**
```css
:root {
  --color-bg: #060609;
  --color-bg2: #0a0a10;
  --color-surface: #0e0e16;
  --color-accent: #00ff88;
  --color-accent-glow: rgba(0,255,136,0.4);
  --color-green: #00ff88;
  --color-blue: #4a9eff;
  --color-amber: #ffb800;
  --color-text: #a0a0b8;
  --color-text-hi: #d0d0e0;
  --color-text-dim: #3a3a50;
  --color-border: rgba(0,255,136,0.12);
  --color-accent-hover: var(--color-accent);
  --color-on-accent: #000000;
}
```

**`plugins/h2t-creative/profiles/h2t-mono/palettes/default.css`:**
```css
:root {
  --color-bg: #0d0d0d;
  --color-text: #e0e0e0;
  --color-text-dim: #666666;
  --color-accent: #e8352b;
  --color-border: #1a1a1a;
  --color-on-accent: #ffffff;
  --color-accent-hover: var(--color-accent);
}
```

**`plugins/h2t-creative/profiles/h2t-mono/palettes/blue.css`:**
```css
:root {
  --color-bg: #0d0d0d;
  --color-text: #e0e0e0;
  --color-text-dim: #666666;
  --color-accent: #2563eb;
  --color-border: #1a1a1a;
  --color-on-accent: #ffffff;
  --color-accent-hover: var(--color-accent);
}
```

**`plugins/h2t-creative/profiles/h2t-mono/palettes/white.css`:**
```css
:root {
  --color-bg: #f5f5f5;
  --color-text: #0d0d0d;
  --color-text-dim: #888888;
  --color-accent: #e8352b;
  --color-border: #e0e0e0;
  --color-on-accent: #ffffff;
  --color-accent-hover: var(--color-accent);
}
```

**`plugins/h2t-creative/profiles/h2t-pfad/palettes/default.css`:**
```css
:root {
  --color-bg: #0c0c0c;
  --color-bg-card: #111111;
  --color-fg: #eeeeee;
  --color-fg-dim: #6e6e6e;
  --color-fg-muted: #444444;
  --color-accent: #d63030;
  --color-accent-dim: rgba(214,48,48,0.4);
  --color-accent-glow: rgba(214,48,48,0.18);
  --color-border: rgba(255,255,255,0.10);
  --color-text: var(--color-fg);
  --color-text-dim: var(--color-fg-dim);
  --color-on-accent: #ffffff;
  --color-accent-hover: var(--color-accent);
}
```

**`plugins/h2t-creative/profiles/h2t-terminal/palettes/default.css`:**
```css
:root {
  --color-bg: #0d1117;
  --color-bg-light: #161b22;
  --color-bg-card: #1c2129;
  --color-text: #e6edf3;
  --color-text-dim: #8b949e;
  --color-accent: #00ff41;
  --color-border: #30363d;
  --color-on-accent: #000000;
  --color-accent-hover: var(--color-accent);
}
```

**`plugins/h2t-creative/profiles/h2t-terminal/palettes/amber.css`:**
```css
:root {
  --color-bg: #0d1117;
  --color-bg-light: #161b22;
  --color-bg-card: #1c2129;
  --color-text: #e6edf3;
  --color-text-dim: #8b949e;
  --color-accent: #d4a843;
  --color-border: #30363d;
  --color-on-accent: #0d1117;
  --color-accent-hover: var(--color-accent);
}
```

**`plugins/h2t-creative/profiles/h2t-terminal/palettes/cyan.css`:**
```css
:root {
  --color-bg: #0d1117;
  --color-bg-light: #161b22;
  --color-bg-card: #1c2129;
  --color-text: #e6edf3;
  --color-text-dim: #8b949e;
  --color-accent: #4488cc;
  --color-border: #30363d;
  --color-on-accent: #ffffff;
  --color-accent-hover: var(--color-accent);
}
```

- [ ] **Step 1.4: Update all 6 tokens.css files**

**`plugins/h2t-creative/profiles/h2t-default/tokens.css`** — add `--font-mono` line after `--font-body`:
```css
:root {
  --space-xs: 0.25rem;
  --space-sm: 0.5rem;
  --space-md: 1rem;
  --space-lg: 2rem;
  --space-xl: 4rem;

  --radius-sm: 4px;
  --radius-md: 8px;
  --radius-lg: 16px;

  --font-display: system-ui, sans-serif;
  --font-body: system-ui, sans-serif;
  --font-mono: 'JetBrains Mono', monospace;

  --z-bg: -1;
  --z-base: 0;
  --z-nav: 100;
}

body {
  background-color: var(--color-bg);
  color: var(--color-fg);
  font-family: var(--font-body);
}
```

**`plugins/h2t-creative/profiles/h2t-editorial/tokens.css`** — add `--font-mono` line after `--font-body`:
```css
:root {
  --font-display: 'Playfair Display', 'Georgia', serif;
  --font-body: 'Inter', 'Helvetica Neue', sans-serif;
  --font-mono: 'JetBrains Mono', monospace;

  --space-xs: 0.25rem;
  --space-sm: 0.5rem;
  --space-md: 1rem;
  --space-lg: 2rem;
  --space-xl: 4rem;

  --radius-sm: 2px;
  --radius-md: 4px;
  --radius-lg: 8px;

  --z-bg: -1;
  --z-base: 0;
  --z-nav: 100;
}

body {
  font-family: var(--font-body);
  font-size: 18px;
  background-color: var(--color-bg);
  color: var(--color-text);
  -webkit-font-smoothing: antialiased;
}
```

**`plugins/h2t-creative/profiles/h2t-graphs/tokens.css`** — add canonical aliases after `--font-mono`:
```css
:root {
  --font-sans: 'Inter', system-ui, sans-serif;
  --font-mono: 'JetBrains Mono', monospace;
  --font-display: var(--font-sans);
  --font-body: var(--font-mono);

  --space-xs: 0.25rem;
  --space-sm: 0.5rem;
  --space-md: 1rem;
  --space-lg: 2rem;
  --space-xl: 4rem;

  --radius-sm: 2px;
  --radius-md: 4px;
  --radius-lg: 8px;

  --z-bg: -1;
  --z-base: 0;
  --z-nav: 100;
}

body {
  background-color: var(--color-bg);
  color: var(--color-text);
  font-family: var(--font-mono);
  -webkit-font-smoothing: antialiased;
}
```

**`plugins/h2t-creative/profiles/h2t-mono/tokens.css`** — add canonical aliases after `--font`:
```css
:root {
  --font: 'JetBrains Mono', monospace;
  --font-display: var(--font);
  --font-body: var(--font);
  --font-mono: var(--font);

  --space-xs: 0.25rem;
  --space-sm: 0.5rem;
  --space-md: 1rem;
  --space-lg: 2rem;
  --space-xl: 4rem;

  --radius-sm: 0;
  --radius-md: 0;
  --radius-lg: 0;

  --z-bg: -1;
  --z-base: 0;
  --z-nav: 100;
}

body {
  font-family: var(--font);
  font-size: 14px;
  background-color: var(--color-bg);
  color: var(--color-text);
  -webkit-font-smoothing: antialiased;
}
```

**`plugins/h2t-creative/profiles/h2t-pfad/tokens.css`** — add canonical aliases after `--font`:
```css
:root {
  --font: 'JetBrains Mono', 'IBM Plex Mono', monospace;
  --font-display: var(--font);
  --font-body: var(--font);
  --font-mono: var(--font);

  --space-xs: 0.25rem;
  --space-sm: 0.5rem;
  --space-md: 1rem;
  --space-lg: 2rem;
  --space-xl: 4rem;

  --radius-sm: 0;
  --radius-md: 0;
  --radius-lg: 0;

  --z-bg: -1;
  --z-base: 0;
  --z-nav: 100;
}

body {
  font-family: var(--font);
  font-size: 12px;
  background-color: var(--color-bg);
  color: var(--color-fg);
  -webkit-font-smoothing: antialiased;
}
```

**`plugins/h2t-creative/profiles/h2t-terminal/tokens.css`** — add canonical aliases after `--font`:
```css
:root {
  --font: 'JetBrains Mono', 'Fira Code', 'Menlo', monospace;
  --font-display: var(--font);
  --font-body: var(--font);
  --font-mono: var(--font);

  --space-xs: 0.25rem;
  --space-sm: 0.5rem;
  --space-md: 1rem;
  --space-lg: 2rem;
  --space-xl: 4rem;

  --radius-sm: 0;
  --radius-md: 0;
  --radius-lg: 0;

  --z-bg: -1;
  --z-base: 0;
  --z-nav: 100;
}

body {
  font-family: var(--font);
  font-size: 15px;
  background-color: var(--color-bg);
  color: var(--color-text);
  cursor: crosshair;
  -webkit-font-smoothing: antialiased;
}

body::after {
  content: '';
  position: fixed; top: 0; left: 0; right: 0; bottom: 0;
  background: repeating-linear-gradient(
    0deg, transparent, transparent 2px,
    rgba(0,0,0,0.03) 2px, rgba(0,0,0,0.03) 4px
  );
  pointer-events: none;
  z-index: 9998;
}
```

- [ ] **Step 1.5: Run token contract tests — verify all PASS**

```
py -3.11 -m pytest plugins/h2t-creative/tests/test_token_contract.py -v
```
Expected: 20 passed — 14 palette × color tokens + 6 tokens.css × font tokens.

- [ ] **Step 1.6: Run full test suite — verify smoke tests still PASS**

```
py -3.11 -m pytest plugins/h2t-creative/tests/ -q
```
Expected: 48 passed (28 existing + 20 new).

- [ ] **Step 1.7: Commit**

```
git add plugins/h2t-creative/profiles/ plugins/h2t-creative/tests/test_token_contract.py
git commit -m "fix(h2t-creative): add token contract v2 canonical aliases to all profiles"
```

---

### Task 2: Font Loading — profile.yaml + assembler injection

**Architecture:** Each profile with web fonts has a `profile.yaml` declaring `web_fonts: [<url>, ...]`. The assembler reads this file and prepends Google Fonts `<link>` tags to `<head>`. If the file doesn't exist or `web_fonts` is empty, no tags are injected.

**Files:**
- Create: `plugins/h2t-creative/tests/test_font_loading.py`
- Create: 5 `profile.yaml` files
- Modify: `plugins/h2t-creative/assembler.py`

- [ ] **Step 2.1: Write the failing tests**

Create `plugins/h2t-creative/tests/test_font_loading.py`:

```python
"""Font link injection: profile.yaml web_fonts list -> <link> tags in <head>."""
import assembler as asm

_RECIPE = {
    "title": "Font Test",
    "sections": [
        {"component": "hero", "content": {"headline": "T", "subline": "S"}},
    ],
}

_DECK_RECIPE = {
    "title": "Deck Font Test",
    "slides": [{"layout": "title-only", "content": {"headline": "T"}}],
}


def test_font_links_editorial(tmp_path):
    out = tmp_path / "out"
    asm.assemble_landing(_RECIPE, asm.PROFILES_DIR / "h2t-editorial", out)
    html = (out / "index.html").read_text()
    assert "fonts.googleapis.com" in html
    assert "Playfair" in html


def test_font_links_mono(tmp_path):
    out = tmp_path / "out"
    asm.assemble_landing(_RECIPE, asm.PROFILES_DIR / "h2t-mono", out)
    html = (out / "index.html").read_text()
    assert "fonts.googleapis.com" in html
    assert "JetBrains" in html


def test_no_font_links_default(tmp_path):
    out = tmp_path / "out"
    asm.assemble_landing(_RECIPE, asm.PROFILES_DIR / "h2t-default", out)
    html = (out / "index.html").read_text()
    assert "fonts.googleapis.com" not in html


def test_font_links_deck_editorial(tmp_path):
    out = tmp_path / "out"
    asm.assemble_deck(_DECK_RECIPE, asm.PROFILES_DIR / "h2t-editorial", out)
    html = (out / "index.html").read_text()
    assert "fonts.googleapis.com" in html


def test_preconnect_hints(tmp_path):
    out = tmp_path / "out"
    asm.assemble_landing(_RECIPE, asm.PROFILES_DIR / "h2t-mono", out)
    html = (out / "index.html").read_text()
    assert 'rel="preconnect"' in html
    assert "fonts.gstatic.com" in html
```

- [ ] **Step 2.2: Run tests — verify FAIL**

```
py -3.11 -m pytest plugins/h2t-creative/tests/test_font_loading.py -v
```
Expected: `test_font_links_editorial`, `test_font_links_mono`, `test_font_links_deck_editorial`, `test_preconnect_hints` FAIL. `test_no_font_links_default` PASS (no fonts yet = correct).

- [ ] **Step 2.3: Create profile.yaml for each web-font profile**

**`plugins/h2t-creative/profiles/h2t-editorial/profile.yaml`:**
```yaml
web_fonts:
  - https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,700;1,400&family=Inter:wght@400;500;700&display=swap
```

**`plugins/h2t-creative/profiles/h2t-graphs/profile.yaml`:**
```yaml
web_fonts:
  - https://fonts.googleapis.com/css2?family=Inter:wght@700;800&family=JetBrains+Mono:ital,wght@0,400;0,500&display=swap
```

**`plugins/h2t-creative/profiles/h2t-mono/profile.yaml`:**
```yaml
web_fonts:
  - https://fonts.googleapis.com/css2?family=JetBrains+Mono:ital,wght@0,400;0,500;0,700&display=swap
```

**`plugins/h2t-creative/profiles/h2t-pfad/profile.yaml`:**
```yaml
web_fonts:
  - https://fonts.googleapis.com/css2?family=JetBrains+Mono:ital,wght@0,400;0,500;0,700&display=swap
```

**`plugins/h2t-creative/profiles/h2t-terminal/profile.yaml`:**
```yaml
web_fonts:
  - https://fonts.googleapis.com/css2?family=JetBrains+Mono:ital,wght@0,400;0,500;0,700&display=swap
```

(h2t-default has no `profile.yaml` — system fonts, no loading needed.)

- [ ] **Step 2.4: Update assembler.py**

After the `SHARED_DIR` constant (line 14), add two new functions:

```python
def _load_profile_config(profile_dir: Path) -> dict:
    config_path = profile_dir / "profile.yaml"
    if not config_path.exists():
        return {}
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _build_font_links(profile_dir: Path) -> str:
    urls = _load_profile_config(profile_dir).get("web_fonts", [])
    if not urls:
        return ""
    lines = [
        '  <link rel="preconnect" href="https://fonts.googleapis.com">',
        '  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>',
    ]
    for url in urls:
        lines.append(f'  <link rel="stylesheet" href="{url}">')
    return "\n".join(lines) + "\n"
```

Replace `_HTML_LANDING` (the entire string literal):

```python
_HTML_LANDING = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
{font_links}  <link rel="stylesheet" href="base.css">
  <link rel="stylesheet" href="profile.css">
</head>
<body>
{body}
{fx_canvas}
{fx_script}
</body>
</html>
"""
```

Replace `_HTML_DECK` (the entire string literal):

```python
_HTML_DECK = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
{font_links}  <link rel="stylesheet" href="base.css">
  <link rel="stylesheet" href="profile.css">
</head>
<body class="deck">
<nav class="slide-menu">
{menu_links}
</nav>
<main class="slides">
{slides_html}
</main>
{fx_canvas}
<script>
{nav_js}
</script>
{fx_script}
</body>
</html>
"""
```

In `assemble_landing`, inside the function body, add font_links before `index_html = _HTML_LANDING.format(...)` and add it to the format call:

```python
    font_links = _build_font_links(profile_dir)
    index_html = _HTML_LANDING.format(
        title=html.escape(str(recipe.get("title", ""))),
        font_links=font_links,
        body=body,
        fx_canvas=fx_canvas,
        fx_script=fx_script,
    )
```

In `assemble_deck`, same pattern:

```python
    font_links = _build_font_links(profile_dir)
    index_html = _HTML_DECK.format(
        title=html.escape(str(recipe.get("title", ""))),
        font_links=font_links,
        menu_links=menu_links,
        slides_html=slides_html,
        fx_canvas=fx_canvas,
        nav_js=_DECK_NAV_JS,
        fx_script=fx_script,
    )
```

- [ ] **Step 2.5: Run font loading tests — verify all PASS**

```
py -3.11 -m pytest plugins/h2t-creative/tests/test_font_loading.py -v
```
Expected: 5 passed.

- [ ] **Step 2.6: Run full test suite — verify all PASS**

```
py -3.11 -m pytest plugins/h2t-creative/tests/ -q
```
Expected: 53 passed (48 + 5).

- [ ] **Step 2.7: Commit**

```
git add plugins/h2t-creative/assembler.py plugins/h2t-creative/profiles/h2t-editorial/profile.yaml plugins/h2t-creative/profiles/h2t-graphs/profile.yaml plugins/h2t-creative/profiles/h2t-mono/profile.yaml plugins/h2t-creative/profiles/h2t-pfad/profile.yaml plugins/h2t-creative/profiles/h2t-terminal/profile.yaml plugins/h2t-creative/tests/test_font_loading.py
git commit -m "feat(h2t-creative): inject web fonts from profile.yaml"
```

---

### Task 3: Shared Components Restyle — migrate to canonical tokens

Replace `--color-fg` → `--color-text`, `--color-muted` → `--color-text-dim` in all shared CSS. Add font fallback `inherit`. Fix hardcoded `color: #fff` and bare `--color-accent-hover`.

**Files:**
- Modify: `plugins/h2t-creative/tests/test_token_contract.py` (add 4 tests)
- Modify: 6 shared component CSS files

- [ ] **Step 3.1: Add failing shared CSS cleanliness tests to test_token_contract.py**

Append to `plugins/h2t-creative/tests/test_token_contract.py`:

```python
import re


def test_shared_css_no_bare_color_fg():
    """Shared CSS must not reference --color-fg (not in all profiles; use --color-text)."""
    for comp_dir in sorted((asm.SHARED_DIR / "components").glob("*/")):
        css_file = comp_dir / f"{comp_dir.name}.css"
        if css_file.exists():
            css = css_file.read_text()
            assert "var(--color-fg)" not in css, \
                f"{comp_dir.name}.css: replace var(--color-fg) with var(--color-text)"


def test_shared_css_no_bare_color_muted():
    """Shared CSS must not reference --color-muted (not in all profiles; use --color-text-dim)."""
    for comp_dir in sorted((asm.SHARED_DIR / "components").glob("*/")):
        css_file = comp_dir / f"{comp_dir.name}.css"
        if css_file.exists():
            css = css_file.read_text()
            assert "var(--color-muted)" not in css, \
                f"{comp_dir.name}.css: replace var(--color-muted) with var(--color-text-dim)"


def test_shared_css_no_hardcoded_white():
    """Shared CSS must not hardcode color: #fff (breaks light-bg profiles; use --color-on-accent)."""
    for comp_dir in sorted((asm.SHARED_DIR / "components").glob("*/")):
        css_file = comp_dir / f"{comp_dir.name}.css"
        if css_file.exists():
            css = css_file.read_text()
            assert "color: #fff" not in css.lower(), \
                f"{comp_dir.name}.css: replace color:#fff with var(--color-on-accent, #fff)"


def test_shared_css_no_bare_accent_hover():
    """Shared CSS must not use bare --color-accent-hover without fallback."""
    for comp_dir in sorted((asm.SHARED_DIR / "components").glob("*/")):
        css_file = comp_dir / f"{comp_dir.name}.css"
        if css_file.exists():
            css = css_file.read_text()
            bare = re.findall(r'var\(--color-accent-hover\)', css)
            assert not bare, \
                f"{comp_dir.name}.css: use var(--color-accent-hover, var(--color-accent))"
```

- [ ] **Step 3.2: Run — verify 4 new tests FAIL**

```
py -3.11 -m pytest plugins/h2t-creative/tests/test_token_contract.py -v -k "shared_css"
```
Expected: 4 FAILED.

- [ ] **Step 3.3: Rewrite all 6 shared component CSS files**

**`plugins/h2t-creative/shared/components/features-grid/features-grid.css`:**
```css
.features-grid__heading:empty { display: none; }
.features-grid__heading { font-family: var(--font-display, inherit); margin-bottom: var(--space-lg); }
.features-grid__item { display: flex; flex-direction: column; gap: var(--space-sm); }
.features-grid__icon { font-size: 2rem; line-height: 1; }
.features-grid__title { font-family: var(--font-display, inherit); color: var(--color-text); margin: 0; }
.features-grid__body { color: var(--color-text-dim); margin: 0; }
```

**`plugins/h2t-creative/shared/components/stats/stats.css`:**
```css
.stats { text-align: center; }
.stats__item { display: flex; flex-direction: column; gap: var(--space-xs); }
.stats__value { font-family: var(--font-display, inherit); font-size: 2.5rem; font-weight: 700; color: var(--color-accent); }
.stats__label { font-size: 0.875rem; color: var(--color-text-dim); text-transform: uppercase; letter-spacing: 0.05em; }
```

**`plugins/h2t-creative/shared/components/testimonials/testimonials.css`:**
```css
.testimonials__quote { font-size: 1.25rem; color: var(--color-text); border-left: 4px solid var(--color-accent); padding-left: var(--space-lg); margin: 0 0 var(--space-md); font-style: italic; }
.testimonials__cite { display: flex; flex-direction: column; gap: var(--space-xs); padding-left: var(--space-lg); font-style: normal; }
.testimonials__author { font-weight: 700; color: var(--color-text); }
.testimonials__role:empty { display: none; }
.testimonials__role { color: var(--color-text-dim); font-size: 0.875rem; }
```

**`plugins/h2t-creative/shared/components/pricing/pricing.css`:**
```css
.pricing__card { border: 1px solid var(--color-border); border-radius: var(--radius-lg); padding: var(--space-xl); display: flex; flex-direction: column; gap: var(--space-md); }
.pricing__plan { font-family: var(--font-display, inherit); margin: 0; }
.pricing__price-row { display: flex; align-items: baseline; gap: var(--space-sm); }
.pricing__price { font-size: 2.5rem; font-weight: 700; color: var(--color-accent); }
.pricing__period { color: var(--color-text-dim); font-size: 0.875rem; }
.pricing__features { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: var(--space-sm); color: var(--color-text-dim); }
.pricing__features li::before { content: "✓ "; color: var(--color-accent); }
.pricing__cta { display: inline-block; background-color: var(--color-accent); color: var(--color-on-accent, #fff); padding: var(--space-md) var(--space-xl); border-radius: var(--radius-md); text-decoration: none; font-weight: 700; text-align: center; }
.pricing__cta:hover { background-color: var(--color-accent-hover, var(--color-accent)); }
```

**`plugins/h2t-creative/shared/components/faq/faq.css`:**
```css
.faq__title:empty { display: none; }
.faq__title { font-family: var(--font-display, inherit); margin-bottom: var(--space-lg); }
.faq__list { display: flex; flex-direction: column; gap: var(--space-lg); }
.faq__list dt { font-weight: 700; color: var(--color-text); margin-bottom: var(--space-xs); }
.faq__list dd { color: var(--color-text-dim); margin-left: 0; }
```

**`plugins/h2t-creative/shared/components/logos/logos.css`:**
```css
.logos__title:empty { display: none; }
.logos__title { text-align: center; font-size: 0.875rem; color: var(--color-text-dim); text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: var(--space-md); }
.logos__strip { display: flex; flex-wrap: wrap; justify-content: center; align-items: center; gap: var(--space-xl); color: var(--color-text-dim); }
```

- [ ] **Step 3.4: Run full test suite — verify all PASS**

```
py -3.11 -m pytest plugins/h2t-creative/tests/ -q
```
Expected: 57 passed (53 + 4).

- [ ] **Step 3.5: Commit**

```
git add plugins/h2t-creative/shared/ plugins/h2t-creative/tests/test_token_contract.py
git commit -m "fix(h2t-creative): restyle shared components to use canonical tokens"
```

---

### Task 4: Visual Regression Pack — baseline screenshots per profile

Build `landing-course.yaml` for all 6 profiles, screenshot desktop (1440px) + mobile (390px), fill in the invariant checklist.

**Files:**
- Create: `docs/visual-regression/2026-05-03/checklist.md`
- Screenshots go to: `docs/visual-regression/2026-05-03/` (committed as documentation)

- [ ] **Step 4.1: Build landing-course for all 6 profiles**

Run from `C:/dev/h2t-skills/plugins/h2t-creative/`:

```
py -3.11 assembler.py --profile h2t-default   --type landing --recipe recipes/landing-course.yaml --out ../../dist/h2t-default
py -3.11 assembler.py --profile h2t-editorial --type landing --recipe recipes/landing-course.yaml --out ../../dist/h2t-editorial
py -3.11 assembler.py --profile h2t-graphs    --type landing --recipe recipes/landing-course.yaml --out ../../dist/h2t-graphs
py -3.11 assembler.py --profile h2t-mono      --type landing --recipe recipes/landing-course.yaml --out ../../dist/h2t-mono
py -3.11 assembler.py --profile h2t-pfad      --type landing --recipe recipes/landing-course.yaml --out ../../dist/h2t-pfad
py -3.11 assembler.py --profile h2t-terminal  --type landing --recipe recipes/landing-course.yaml --out ../../dist/h2t-terminal
```

Expected: `Built landing -> ../../dist/<profile>` for each.

- [ ] **Step 4.2: Screenshot all 6 profiles — desktop + mobile, rename immediately**

The screenshot tool extracts domain from file:// URLs as "unknown", so all files land in `docs/visual-regression/2026-05-03/unknown/`. Rename each file right after capture to avoid overwrites when timestamps collide.

Run from `C:/dev/h2t-skills/` (PowerShell):

```powershell
$OUT = "docs/visual-regression/2026-05-03"

foreach ($profile in @("h2t-default","h2t-editorial","h2t-graphs","h2t-mono","h2t-pfad","h2t-terminal")) {
    $url = "file:///C:/dev/h2t-skills/dist/$profile/index.html"

    # desktop
    & C:/dev/h2t-tools/.venv/Scripts/python.exe C:/dev/h2t-tools/scripts/screenshot/screenshot.py $url --format desktop --out $OUT
    Get-ChildItem "$OUT\unknown\desktop_*.png" | Sort-Object LastWriteTime -Descending | Select-Object -First 1 | Move-Item -Destination "$OUT\$profile-desktop.png"

    # mobile
    & C:/dev/h2t-tools/.venv/Scripts/python.exe C:/dev/h2t-tools/scripts/screenshot/screenshot.py $url --format mobile --out $OUT
    Get-ChildItem "$OUT\unknown\mobile_*.png" | Sort-Object LastWriteTime -Descending | Select-Object -First 1 | Move-Item -Destination "$OUT\$profile-mobile.png"
}
```

Expected result: 12 files in `docs/visual-regression/2026-05-03/`:
```
h2t-default-desktop.png    h2t-default-mobile.png
h2t-editorial-desktop.png  h2t-editorial-mobile.png
h2t-graphs-desktop.png     h2t-graphs-mobile.png
h2t-mono-desktop.png       h2t-mono-mobile.png
h2t-pfad-desktop.png       h2t-pfad-mobile.png
h2t-terminal-desktop.png   h2t-terminal-mobile.png
```

Verify: `Get-ChildItem docs\visual-regression\2026-05-03\*.png | Measure-Object` → Count: 12.

- [ ] **Step 4.4: Create the invariant checklist**

Create `docs/visual-regression/2026-05-03/checklist.md`:

```markdown
# Visual Regression Checklist — h2t-creative v1.2.0

Date: 2026-05-03
Build: landing-course.yaml × 6 profiles, default palette

## Instructions
- [ ] not checked  [x] preserved  [!] broken — open an issue

---

## h2t-default
- [ ] Swiss grid layout, generous whitespace
- [ ] Near-black text (#0a0a0a) on white background
- [ ] Electric blue accent (#1a1aff) on CTA button
- [ ] No shadows, no gradients, no border-radius on buttons
- [ ] System font (no Google Fonts link in source)

## h2t-editorial
- [ ] Serif headlines — Playfair Display loaded and rendering (not Georgia fallback)
- [ ] Sans-serif body — Inter loaded and rendering
- [ ] Warm cream background (#faf9f6)
- [ ] Terracotta accent (#c45a3c) on CTA button
- [ ] Body text has generous line height (visibly open)

## h2t-graphs
- [ ] Near-black background (#060609)
- [ ] Inter headlines at heavy weight (700–800), visibly different from body
- [ ] JetBrains Mono body text throughout
- [ ] Red accent (#e94560) — CTA button and decorations
- [ ] Corner bracket decorations visible on hero badge

## h2t-mono
- [ ] Near-black background (#0d0d0d)
- [ ] JetBrains Mono throughout — consistent mono rendering
- [ ] Red CTA button (#e8352b) — sharp corners (border-radius: 0)
- [ ] Zero decorative elements — no gradients, no shadows, no brackets
- [ ] Pricing card has sharp corners

## h2t-pfad
- [ ] Very dark background (#0c0c0c)
- [ ] JetBrains Mono — noticeably smaller type (12px base)
- [ ] Corner bracket decorations on hero section
- [ ] Red accent (#d63030)
- [ ] Sharp corners everywhere (border-radius: 0)

## h2t-terminal
- [ ] Dark GitHub-blue background (#0d1117)
- [ ] JetBrains Mono throughout
- [ ] Green accent (#00ff41) on CTA button with black text
- [ ] Blinking cursor after hero headline
- [ ] Scanline overlay visible (subtle horizontal line pattern across page)
- [ ] Crosshair cursor when hovering
- [ ] Sharp corners everywhere
```

- [ ] **Step 4.5: Review screenshots against checklist**

Open each screenshot. For each profile, check all items. Mark `[x]` or `[!]`.

**SEMVER GATE:** If any item is `[!]`, **Task 5 is BLOCKED**. Do NOT bump to 1.2.0 with broken invariants — stay on patch 1.1.x. Per project semver rule: minor bump only after live-confirmed aesthetics. Fix the broken invariant first, then re-run the full test suite + visual review.

For each `[!]` item, open a tracking issue:
```
gh issue create --title "creative: <profile> — <invariant broken>" --body "Visual regression: docs/visual-regression/2026-05-03/. Blocks v1.2.0 bump."
```

Proceed to Task 5 only when every item is `[x]`.

- [ ] **Step 4.6: Commit checklist + screenshots**

```
git add docs/visual-regression/2026-05-03/
git commit -m "docs(h2t-creative): visual regression baseline v1.2.0"
```

---

### Task 5: Version Bump to 1.2.0

This is the first live-confirmed minor bump for h2t-creative.

**Files:**
- Modify: `plugins/h2t-creative/.claude-plugin/plugin.json`
- Modify: `.claude-plugin/marketplace.json` (root-level registry, not inside the plugin folder)

- [ ] **Step 5.1: Run full test suite one final time**

```
py -3.11 -m pytest plugins/h2t-creative/tests/ -q
```
Expected: 57 passed, 0 failed.

- [ ] **Step 5.2: Bump version to 1.2.0**

Run from `C:/dev/h2t-skills/` (set UTF-8 first to avoid cp1252 error with ✓ characters):

```powershell
$env:PYTHONIOENCODING = "utf-8"
py -3.11 scripts/bump_plugin.py h2t-creative 1.2.0
```

Expected output: version updated in both plugin.json and marketplace.json.

- [ ] **Step 5.3: Verify version in both files**

```powershell
Select-String -Path "plugins/h2t-creative/.claude-plugin/plugin.json" -Pattern '"version"'
Select-String -Path ".claude-plugin/marketplace.json" -Pattern '"version"'
```
Expected: both show `"version": "1.2.0"`.

- [ ] **Step 5.4: Commit**

```
git add plugins/h2t-creative/.claude-plugin/plugin.json .claude-plugin/marketplace.json
git commit -m "chore(h2t-creative): bump to v1.2.0 — aesthetic recovery complete"
```

---

## Self-Review

**Spec coverage:**
- Token Contract v2 (color aliases in palettes, font aliases in tokens.css) → Task 1 ✓
- Font Loading (profile.yaml + assembler injection) → Task 2 ✓
- Shared Components Restyle (canonical token migration) → Task 3 ✓
- Visual Regression Pack (desktop + mobile screenshots + checklist) → Task 4 ✓
- Version 1.2.0 → Task 5 ✓
- Aliases in palette files not tokens.css (user's key note) → implemented in Task 1, Step 1.3 ✓
- `--color-text`/`--color-text-dim` as canonical (4/6 majority) → used throughout ✓
- No style-create v2 or content-fit in this plan → confirmed, Phase 2b is recovery only ✓

**Placeholder scan:** No TBD, no "add appropriate", no "similar to Task N". All code blocks are complete.

**Type consistency:** Token names used in tests match names added to palette/tokens files. CSS property names in shared CSS match canonical names defined in palettes. `_build_font_links` / `_load_profile_config` function names consistent across all steps.
