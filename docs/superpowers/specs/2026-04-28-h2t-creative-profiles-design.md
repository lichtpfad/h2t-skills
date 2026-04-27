# h2t-creative v3 · Phase 1 — Profiles Design Spec

**Date:** 2026-04-28
**Status:** Approved
**Scope:** Extraction and migration of 5 existing design systems into h2t-creative profile format. New styles are out of scope — they go through `h2t-creative:style-create` workflow.

---

## 1. Architecture

### Profile directory structure

```
profiles/{name}/
  DESIGN.md              ← brand intent, typography rules, available palettes list
  tokens.css             ← fonts, spacing, radii, z-index ONLY (no colors)
  palettes/
    default.css          ← default --color-* variables
    blue.css             ← alternative palettes (profile-specific set)
    green.css
  components/
    nav/
      nav.html           ← profile-specific markup
      nav.css            ← styles using only --color-* and font/spacing tokens
      manifest.yaml
    hero/...
    section/...
    cta/...
    footer/...
```

### Key principles

- `tokens.css` contains **zero color variables** — fonts, spacing, radii, z-index only
- `palettes/default.css` contains all `--color-*` variables for the default color scheme
- Component HTML/CSS is **fully isolated per profile** — no shared markup between profiles
- Component CSS uses only CSS custom properties from tokens.css + active palette — never hardcoded values
- Adding a new palette = one new CSS file, nothing else changes

### Assembler changes

New `--palette` flag:

```bash
python assembler.py --profile h2t-pfad --palette blue --type landing --recipe recipe.yaml --out ./dist
```

`_build_profile_css` updated:

```python
def _build_profile_css(profile_dir, sections, palette="default"):
    palette_path = profile_dir / "palettes" / f"{palette}.css"
    if not palette_path.exists():
        raise ValueError(f"Palette '{palette}' not found in profile {profile_dir.name}")
    parts = [
        (profile_dir / "tokens.css").read_text(encoding="utf-8"),   # fonts/spacing
        palette_path.read_text(encoding="utf-8"),                    # colors
    ]
    seen = set()
    for section in sections:
        name = section["component"]
        if name not in seen:
            css_path = profile_dir / "components" / name / f"{name}.css"
            if css_path.exists():
                parts.append(css_path.read_text(encoding="utf-8"))
            seen.add(name)
    return "\n".join(parts)
```

### h2t-default migration

Existing `h2t-default/tokens.css` is split:
- Colors extracted → `palettes/default.css`
- Typography + spacing stays in `tokens.css`

---

## 2. Five Profiles

### h2t-pfad

**Source:** `h2t:design` SKILL.md (PFAD Design System)
**Character:** Elegant, small, all-monospace. Tactical dashboard aesthetic with micro-animations.

**Typography:**
- `--font`: JetBrains Mono, IBM Plex Mono, monospace
- Base font-size: 12px
- Labels: 8px, small elements: 7.5px
- No sans-serif anywhere

**Default palette (red):**
- `--bg`: dark near-black
- `--accent`: red (`#d63030` PFAD variant)
- Additional palettes: TBD during implementation

**fx/ support:** Canvas2D micro-animations (oscilloscope, dot-field particle network, radar sweep, scanner). Implemented as `fx/background.js` following h2t-creative fx/ contract.

**Components:** All 5 standard components with PFAD-specific markup — corner bracket tags, `// SECTION` labels, monospace type scale.

---

### h2t-graphs

**Source:** `C:/dev/h2t-landings/graphs/index.html` (899 lines, full source on disk)
**Character:** Bold typographic hierarchy + mono labels. Data-rich product landing aesthetic.

**Typography:**
- `--sans`: Inter, system-ui (headlines, 700–800 weight)
- `--mono`: JetBrains Mono (nav, labels, code, captions)
- Large bold headlines, mono everything else

**Default palette (red):**
- `--bg`: `#060609`
- `--bg2`: `#0a0a10`
- `--surface`: `#0e0e16`
- `--accent`: `#e94560`
- `--accent-glow`: `rgba(233,69,96,0.4)`
- `--green`: `#00ff88`
- `--blue`: `#4a9eff`
- `--amber`: `#ffb800`
- `--text`: `#a0a0b8`
- `--text-hi`: `#d0d0e0`
- `--text-dim`: `#3a3a50`
- `--border`: `rgba(233,69,96,0.12)`
- Additional palettes: blue, green (swap accent color family)

**Components:** Bold hero with bracket badge tag, mono nav, data-oriented section, strong CTA, mono footer.

---

### h2t-terminal

**Source:** `h2t:deck` SKILL.md — STYLE 1
**Character:** Dark hacker aesthetic. Monospace, green accent, scanline overlay.

**Typography:**
- `--font`: JetBrains Mono (single font stack)
- Uppercase labels, code-like hierarchy

**Default palette (green):**
- Dark bg, green accent (`#00ff41` terminal green)
- Additional palettes: amber, cyan

**fx/ support:** CSS scanline overlay (no JS required). Optional: CRT glow effect.

**Components:** Terminal-styled markup — prompt-like nav (`> brand`), code-block hero, monospace section, ghost CTA button, minimal footer.

---

### h2t-editorial

**Source:** `h2t:deck` SKILL.md — STYLE 2
**Character:** Light, book-like. Serif headlines, generous whitespace, classical typography.

**Typography:**
- `--font-display`: Playfair Display (headlines, 400–800)
- `--font-body`: Inter (body, 400–500)
- Large leading, elegant spacing

**Default palette (dark ink):**
- Light bg (#fafafa), near-black fg (#1a1a1a), restrained accent
- Additional palettes: warm (cream bg), night (dark bg + gold)

**Components:** Serif hero, editorial section with pull-quotes, understated CTA, refined footer.

---

### h2t-mono

**Source:** specdesigner.netlify.app
**Character:** Ultra-minimal. Pure monospace, pure black, single red accent, zero decoration.

**Typography:**
- `--font`: monospace (system or JetBrains Mono)
- All text same weight/size — differentiation through spacing only

**Default palette (red):**
- `--bg`: `#0d0d0d`
- `--accent`: `#e8352b` (SpecDesigner red)
- Additional palettes: white (inverted), blue

**Components:** Minimal markup — no decorative elements, no bracket tags, pure content. CTA = one filled + one ghost button, uppercase text only.

---

## 3. DESIGN.md Schema (updated)

All profiles follow this schema, now with `palettes` section:

```markdown
# {Profile Name}

## Brand Intent
One paragraph.

## Color Tokens
Listed per palette. Default:
- `--color-bg`: ...

## Available Palettes
- `default` — description
- `blue` — description

## Typography
- `--font-display`: ...
- `--font-body`: ...

## Restrictions
- ...
```

---

## 4. Migration Order

Ordered by source completeness (most → least documented):

1. **h2t-graphs** — full HTML source on disk, straightforward extraction
2. **h2t-pfad** — full SKILL.md with tokens + components + fx recipes
3. **h2t-terminal** — STYLE 1 from h2t:deck SKILL.md
4. **h2t-editorial** — STYLE 2 from h2t:deck SKILL.md
5. **h2t-mono** — extract from live site + specdesigner aesthetic

Also: **h2t-default refactor** — split existing tokens.css into tokens.css + palettes/default.css (prerequisite for all profiles, done first).

---

## 5. Out of Scope

- New profiles not in the list above — use `h2t-creative:style-create` workflow
- Three.js WebGL backgrounds — fx/ uses Canvas2D for now; Three.js is future
- Deck-specific component variants — Phase 1 covers landing components only; deck gets profiles in Phase 2
- Block library (10–20 blocks) — Phase 2 spec
