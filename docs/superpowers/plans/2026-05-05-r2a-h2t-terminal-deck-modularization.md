# R2a — h2t-terminal deck modularization plan

**Issue:** [#86 skills: [R2a] Recover h2t-terminal deck legacy fidelity](https://github.com/lichtpfad/h2t-skills/issues/86)
**Branch:** `codex/r2a-terminal-deck-fidelity` (worktree at `C:/dev/h2t-skills-r2`)
**Acceptance gates (two-contour, T12.5 amendment):**

1. **Gate A — Desktop fidelity.** All 11 desktop slides at 1440×900 must match the design system
   and approved goldens (pos-sprint, merkazim). Verified via Agent Visual QA (T12.5/T16) followed
   by human review (T17).
2. **Gate B — Mobile usability.** All 11 mobile slides at 390×844 must render without catastrophic
   overflow, clipping, or content rendered off-canvas. Mobile is **not** a passive baseline — it has
   its own design pass (T14) and implementation (T15) inside the same terminal-deck profile.

**Forbidden:**
- Random mobile redesign that changes desktop fidelity (Gate A invariants must hold).
- Viewport-driven JS hacks (mobile must be CSS-only — `deck-nav.js` is viewport-agnostic).
- Hiding essential content on mobile (every slide ships every recipe field; layout adapts, not content).
- Claiming a mobile pass without Agent Visual QA. The agent must **open every screenshot** and report
  per-slide status before any human review. "All 22 files exist" is not visual QA.

**Allowed / required:**
- Profile-owned `@media (max-width: …)` rules in deck CSS (`tokens.css`, `frame.css`, layout files).
- Mobile-specific layout-collapse rules: `card-row → column`, `layer row → stacked`, `split → 1fr`,
  `table → overflow-x scroll wrapper`, etc.
- Mobile font-scale and padding scaling. Desktop tokens stay authoritative outside the media query.

**T12.5 history:** the original R2a plan banned all `@media (max-width:` rules and treated mobile as
baseline-only for #92. This was wrong — the resulting mobile output was unusable (5 BLOCKERs across
11 slides; see `docs/visual-regression/2026-05-05-r2/h2t-terminal-deck-modular/parity-notes.md`).
The two-gate model above replaces it. #92 retains the cross-deck mobile UX strategy decision; this
profile receives its own mobile rules now.

**T0 status:** ✅ pass — see §A T0 caller inventory addendum at end of this document.
**Inputs (already imported):**
- `docs/visual-regression/2026-05-05-r2/h2t-terminal-deck-golden/` — 4 source files
- `docs/visual-regression/2026-05-05-r2/h2t-terminal-deck-design-system.md` — approved design system

---

## 1. Assembler changes

Current `assembler.py:assemble_deck` is incompatible with the design system in three ways:

| Current behavior | Required for terminal deck |
|---|---|
| Emits `index.html` + `base.css` + `profile.css` (multi-file) | Single-file output: all CSS in `<style>`, all JS in `<script>` (per SKILL.md and both goldens) |
| `_DECK_LAYOUT_HTML` knows only 4 layouts (`title-only`, `title-body`, `title-media`, `blank`) | 11 layouts (`title`, `divider`, `title-body`, `stats`, `cards`, `layers`, `split`, `code`, `table`, `quote`, `final`) |
| Renders `<nav class="slide-menu">` sidebar, `_DECK_NAV_JS` keyboard-only, no progress bar / counter / scanlines / swipe | No sidebar; frame chrome = top-right counter + bottom progress bar + bottom-right nav-hint + opt-in prev/next buttons + scanline overlay; nav JS includes swipe + hash sync |
| `_build_profile_css(profile_dir, [], palette)` passes empty section list — no component CSS bundled | Slide layouts must contribute CSS; bundle by walking slides' layouts |
| Loads `profile_dir/tokens.css` + `profile_dir/palettes/{palette}.css` | Loads `profile_dir/deck/tokens.css` + `profile_dir/deck/palettes/{palette}.css` if present (deck tokens differ from landing tokens — see §2) |
| Layout templates are static dict literals in Python | Layout templates loaded from `profile_dir/deck/slides/<layout>/<layout>.html` (file-based, like landing components) |

### 1.1 New module surface

```python
# assembler.py — additions

DECK_FORM_DIR = "deck"  # subdir under profile when form is deck

def _deck_dir(profile_dir: Path) -> Path:
    return profile_dir / DECK_FORM_DIR

def _is_deck_form_profile(profile_dir: Path) -> bool:
    return (_deck_dir(profile_dir) / "tokens.css").exists()

def _load_slide_layout(profile_dir: Path, layout: str) -> tuple[str, dict]:
    """Return (template_html, manifest_dict) for a deck slide layout."""
    layout_dir = _deck_dir(profile_dir) / "slides" / layout
    if not layout_dir.exists():
        raise ValueError(f"Slide layout '{layout}' not found in {profile_dir.name}/deck/slides/")
    html = (layout_dir / f"{layout}.html").read_text(encoding="utf-8")
    manifest = yaml.safe_load((layout_dir / "manifest.yaml").read_text(encoding="utf-8"))
    return html, manifest

def _render_stats(stats: list[dict]) -> str: ...
def _render_cards(cards: list[dict], variant: str = "card-row") -> str: ...
def _render_layers(layers: list[dict]) -> str: ...
def _render_bullets(bullets: list[dict]) -> str: ...
def _render_table(headers: list[str], rows: list[list[str]], note: str = "") -> str: ...

def _build_deck_slide_html_v2(slide: dict, profile_dir: Path) -> str:
    """Build one <section class='slide'>...</section> for terminal-style decks."""
    layout = slide.get("layout", "title-body")
    template, manifest = _load_slide_layout(profile_dir, layout)
    content = dict(slide.get("content", {}))
    # Apply manifest defaults
    for field, schema in manifest.get("fields", {}).items():
        if field not in content and "default" in schema:
            content[field] = schema["default"]
    # Pre-render array fields per layout
    if layout == "stats" and "stats" in content:
        content["stats_html"] = _render_stats(content.pop("stats"))
    if layout == "cards" and "cards" in content:
        content["cards_html"] = _render_cards(content.pop("cards"), content.pop("cards_variant", "card-row"))
    if layout == "layers" and "layers" in content:
        content["layers_html"] = _render_layers(content.pop("layers"))
    if layout == "table":
        content["table_html"] = _render_table(
            content.pop("table_headers", []),
            content.pop("table_rows", []),
            content.pop("note", ""),
        )
    if "bullets" in content:
        content["bullets_html"] = _render_bullets(content.pop("bullets"))
    return interpolate(template, content)

def _build_deck_css_inline(profile_dir: Path, slides: list[dict], palette: str) -> str:
    deck_root = _deck_dir(profile_dir)
    parts = [(deck_root / "tokens.css").read_text(encoding="utf-8")]
    palette_path = deck_root / "palettes" / f"{palette}.css"
    if palette_path.exists():
        parts.append(palette_path.read_text(encoding="utf-8"))
    # Frame CSS (counter, progress, nav-hint, scanlines, slide base)
    frame_css = deck_root / "frame" / "frame.css"
    if frame_css.exists():
        parts.append(frame_css.read_text(encoding="utf-8"))
    # Deduped per-layout CSS
    seen = set()
    for s in slides:
        layout = s.get("layout", "title-body")
        if layout in seen:
            continue
        seen.add(layout)
        css_path = deck_root / "slides" / layout / f"{layout}.css"
        if css_path.exists():
            parts.append(css_path.read_text(encoding="utf-8"))
    return "\n".join(parts)

def _build_deck_js_inline(profile_dir: Path) -> str:
    js_path = _deck_dir(profile_dir) / "js" / "deck-nav.js"
    return js_path.read_text(encoding="utf-8")
```

### 1.2 Rewritten `assemble_deck`

```python
_HTML_DECK_SINGLE_FILE = """\
<!DOCTYPE html>
<html lang="{lang}">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
{font_links}  <style>
{inline_css}
  </style>
</head>
<body>
  <div id="progress-bar"></div>
  <div id="slide-counter">
    <span class="current" id="cnt-current">01</span>
    <span class="dim"> / </span>
    <span id="cnt-total">{total_padded}</span>
  </div>
  <div id="nav-hint">{nav_hint_text}</div>
  {nav_buttons_html}
  <div id="deck">
{slides_html}
  </div>
  <script>
{inline_js}
  </script>
</body>
</html>
"""

def assemble_deck(recipe, profile_dir, out_dir, base_dir=None, palette="default"):
    if not _is_deck_form_profile(profile_dir):
        # Backward compat: profiles without deck/ subdir use old multi-file path
        return _assemble_deck_legacy(recipe, profile_dir, out_dir, base_dir, palette)
    out_dir.mkdir(parents=True, exist_ok=True)
    slides = recipe.get("slides", [])
    slides_html = "\n".join(
        f'<section class="slide{ " center" if s.get("align") == "center" else "" }" data-index="{i}">'
        f'{_build_deck_slide_html_v2(s, profile_dir)}'
        f'</section>'
        for i, s in enumerate(slides)
    )
    inline_css = _build_deck_css_inline(profile_dir, slides, palette)
    inline_js = _build_deck_js_inline(profile_dir)
    nav_buttons_html = _render_nav_buttons() if recipe.get("nav_buttons") else ""
    index_html = _HTML_DECK_SINGLE_FILE.format(
        lang=recipe.get("lang", "en"),
        title=html.escape(str(recipe.get("title", ""))),
        font_links=_build_font_links(profile_dir),
        inline_css=inline_css,
        inline_js=inline_js,
        slides_html=slides_html,
        total_padded=str(len(slides)).zfill(2),
        nav_hint_text=html.escape(str(recipe.get("nav_hint_text", "arrows / space / swipe"))),
        nav_buttons_html=nav_buttons_html,
    )
    (out_dir / "index.html").write_text(index_html, encoding="utf-8")
    # Single-file: NO base.css / profile.css written for deck form
```

### 1.3 Removed surfaces

- `_DECK_LAYOUT_HTML` Python literal: replaced by file-based layout loading
- `_DECK_NAV_JS` Python literal: replaced by `deck/js/deck-nav.js` per profile
- `<nav class="slide-menu">` sidebar: removed entirely (no terminal golden has it)
- `slide-menu__link` CSS expectations: removed

### 1.4 Backward compatibility

- Old multi-file deck path (`_assemble_deck_legacy`) preserved via `_is_deck_form_profile` switch — keeps existing `h2t-default`/`h2t-pfad`/`h2t-editorial` deck-smoke tests passing until each profile migrates.
- Existing `recipes/deck-edu.yaml` and `recipes/deck-pitch.yaml` continue to work (they target `h2t-default` which has no `deck/` subdir → legacy path).

### 1.5 Files modified

- `plugins/h2t-creative/assembler.py` — additions in §1.1, rewrite of `assemble_deck` per §1.2, legacy path renamed `_assemble_deck_legacy`

---

## 2. Profile files for h2t-terminal deck

```
plugins/h2t-creative/profiles/h2t-terminal/
  (existing landing files — UNCHANGED:
    components/{nav,hero,cta,footer,section}/
    palettes/{default,amber,cyan}.css
    profile.yaml
    tokens.css
    DESIGN.md
  )
  deck/                                    [NEW SUBTREE]
    tokens.css
    palettes/
      default.css
    frame/
      frame.css
    slides/
      title/{title.html, title.css, manifest.yaml}
      divider/{divider.html, divider.css, manifest.yaml}
      title-body/{title-body.html, title-body.css, manifest.yaml}
      stats/{stats.html, stats.css, manifest.yaml}
      cards/{cards.html, cards.css, manifest.yaml}
      layers/{layers.html, layers.css, manifest.yaml}
      split/{split.html, split.css, manifest.yaml}
      code/{code.html, code.css, manifest.yaml}
      table/{table.html, table.css, manifest.yaml}
      quote/{quote.html, quote.css, manifest.yaml}
      final/{final.html, final.css, manifest.yaml}
    js/
      deck-nav.js
  validation/
    recipe-deck.yaml                       [NEW — recipe-deck.yaml, separate from existing recipe.yaml landing form]
  sources/                                  [NEW]
    references.yaml                        [NEW — links to golden import]
    screenshots/
      reference-desktop.png                [NEW — copy of pos-sprint slide 01 desktop]
      reference-mobile.png                 [NEW — copy of pos-sprint slide 01 mobile, documentation only]
```

### 2.1 `deck/tokens.css`

Carries deck-form base styles. Differs from landing `tokens.css`:

- `body { cursor: default; user-select: none; overflow: hidden; font-size: 16px-17px; }` (NOT `cursor: crosshair`)
- Token names use `--bg/--text/--accent` (NOT `--color-bg/--color-text/--color-accent`)
- Defines `--font-heading`, `--font-body` (5-fallback monospace chain)
- No `--space-*` scale (deck uses ad-hoc spacing per design-system §Spacing)
- Defines slide base CSS: `.slide`, `.slide-inner`, `.slide.center`, `.slide.active`, opacity-fade transition
- Includes scanline overlay `body::after`
- Includes `@keyframes fadeUp`, `@keyframes blink`
- Slide-active fade-up animation rules for slide-inner direct children up to nth-child(8)

### 2.2 `deck/palettes/default.css`

The 7-color set per design-system §Color Tokens:

```css
:root {
  --bg: #0d1117;
  --bg-light: #161b22;
  --bg-card: #1c2129;
  --text: #e6edf3;
  --text-dim: #8b949e;
  --accent: #55aa88;
  --accent2: #d4a843;
  --accent3: #4488cc;
  --danger: #cc4444;
  --highlight: #9966cc;
  --pop: #ee6688;
  --border: #30363d;
}
```

No `amber` / `cyan` deck palette in R2a (out of scope).

### 2.3 `deck/frame/frame.css`

Combined frame styles: `#progress-bar`, `#slide-counter`, `#nav-hint`, `.nav-btn`, `.nav-btn.disabled`, `.nav-btn .chevron`, color utility classes (`.dim/.accent/.accent2/.accent3/.danger/.highlight/.pop/.bold`), eyebrow `.eyebrow`, divider `.divider`, cursor blink `.cursor::after`, primitives shared across slide layouts (quote-block, bullet-list, stat-row+stat-box, card-row+card+cards, tag chips, layers, code-block, split, table, duration-tag, disclaimer-badge, pills, meta-note).

Roughly equivalent to design-system §Component primitives + §Frame consolidated into one stylesheet.

### 2.4 `deck/js/deck-nav.js`

Required behaviors (per design-system §Navigation):
- Keyboard: ArrowRight/ArrowDown/Space/Enter → next; ArrowLeft/ArrowUp/Backspace → prev; Home → first; End → last
- Touch swipe: horizontal >40px → next/prev
- Progress bar update: `((current+1) / total) * 100`
- Slide counter update: zero-padded `01..NN`
- Hash sync: `history.replaceState(null, '', '#' + (current+1))`, read on init
- Optional nav buttons: prev/next disabled state on edges (rendered only when recipe `nav_buttons: true`)

### 2.5 `profile.yaml` — no changes required

Existing `web_fonts` list already includes JetBrains Mono. The italic 400 weight is unused by deck (drop italic later if desired, not in R2a).

### 2.6 Test data: `validation/recipe-deck.yaml`

11-slide recipe, one slide per layout, content drawn from goldens (verbatim where possible from pos-sprint, simplified content from merkazim). See §4 for full structure.

### 2.7 Test data: `sources/references.yaml`

```yaml
references:
  - id: pos-sprint-terminal-example
    role: primary
    path: docs/visual-regression/2026-05-05-r2/h2t-terminal-deck-golden/pos-sprint-terminal-example.html
    upstream: https://github.com/ai-mindset-org/pos-sprint/blob/main/skills/deck/examples/terminal-example.html
    slides: 7
  - id: merkazim
    role: secondary
    path: docs/visual-regression/2026-05-05-r2/h2t-terminal-deck-golden/merkazim.html
    slides: 20
  - id: pos-sprint-deck-skill
    role: skill-contract
    path: docs/visual-regression/2026-05-05-r2/h2t-terminal-deck-golden/pos-sprint-deck-SKILL.md
```

---

## 3. Slide layouts → templates

Each layout has `<layout>.html`, `<layout>.css`, `manifest.yaml` under `deck/slides/<layout>/`.

### Manifest field schema

Manifest fields use the same `type: text|html` / `required: bool` / `default: <value>` schema as landing components (`assembler.validate_section_content`).

### Per-layout summary

| Layout | Required fields | Optional fields | Template skeleton |
|---|---|---|---|
| `title` | `headline` (html) | `eyebrow`, `subline`, `meta`, `align` (`center` or `left`), `cursor` (bool) | `<div class="slide-inner [center]"><div class="title-block"><div class="eyebrow">...</div><h1[ class="cursor"]>...</h1><p class="title-subtitle">...</p><p class="title-author">...</p></div></div>` |
| `divider` | `headline` (html) | `eyebrow` | `<div class="slide-inner"><div class="divider-block"><div class="divider-num">// EYEBROW</div><h1>...</h1></div></div>` |
| `title-body` | `headline` (html), `body_html` (html) | `eyebrow` | `<div class="slide-inner"><div class="eyebrow">...</div><h1>...</h1><div class="divider"></div>{{ body_html | safe }}</div>` |
| `stats` | `headline` (html), `stats` (list) | `eyebrow`, `stats_variant` (`stat-box` or `stat`) | `<div class="slide-inner"><div class="eyebrow">...</div><h2>...</h2><div class="divider"></div>{{ stats_html | safe }}</div>` — assembler renders `<div class="stat-row">...</div>` from list |
| `cards` | `headline` (html), `cards` (list) | `eyebrow`, `cards_variant` (`card-row` or `cards`) | similar; helper renders card list |
| `layers` | `headline` (html), `layers` (list) | `eyebrow` | similar; helper renders layer list |
| `split` | `headline` (html), `left_html`, `right_html` | `eyebrow` | `<div class="slide-inner"><div class="eyebrow">...</div><h1>...</h1><div class="split"><div>{{left}}</div><div>{{right}}</div></div></div>` |
| `code` | `headline` (html), `code_html` (html) | `eyebrow`, `code_title`, `caption_html` | `<div class="slide-inner"><div class="eyebrow">...</div><h2>...</h2><div class="code-block" data-title="..."><pre>{{code_html | safe}}</pre></div>{{caption_html|safe}}</div>` — **layout owns the `<pre>` wrapper**; recipe `code_html` MUST contain inner code lines / spans only (no outer `<pre>`), otherwise output produces nested `<pre><pre>` (T5.1 contract fix; guarded by `test_h2t_terminal_deck_code_layout_emits_exactly_one_pre` and `..._no_nested_pre`). |
| `table` | `headline` (html), `table_headers`, `table_rows` | `eyebrow`, `note` | similar; helper renders `<table>` |
| `quote` | `headline` (html), `quote_html` (html) | `eyebrow`, `bullets` (list of `{text, sym}`) | similar; bullet helper if `bullets` present |
| `final` | `headline` (html) | `eyebrow`, `subline`, `cursor` (bool) | `<div class="slide-inner center"><div class="eyebrow">...</div><p class="final-line[ cursor]">...</p><div class="divider"></div><p class="final-coda">...</p></div>` |

### Helper rendering — array fields

Each helper escapes plain text fields and accepts `_html` suffixed fields raw. Examples:

`_render_stats(stats)`:
```python
def _render_stats(stats):
    items = []
    for i, s in enumerate(stats, start=1):
        idx = s.get("index", f"{i:02d}")
        variant = s.get("variant", "stat-box")  # stat-box | stat
        number_class = s.get("number_class", "")  # e.g. "accent", "danger", "pop"
        if variant == "stat-box":
            items.append(
                f'<div class="stat-box" data-index="{html.escape(idx)}">'
                f'<div class="stat-number">{html.escape(s["number"])}</div>'
                f'<div class="stat-label">{s.get("label_html", html.escape(s.get("label", "")))}</div>'
                f'</div>'
            )
        else:  # stat
            num_class = f' class="num {html.escape(number_class)}"' if number_class else ' class="num"'
            items.append(
                f'<div class="stat">'
                f'<div{num_class}>{html.escape(s["number"])}</div>'
                f'<div class="label">{html.escape(s.get("label", ""))}</div>'
                f'</div>'
            )
    return f'<div class="stat-row">{"".join(items)}</div>'
```

Same pattern for `_render_cards`, `_render_layers`, `_render_table`, `_render_bullets`. Each helper unit-tested in `test_r2_legacy_fidelity.py`.

---

## 4. Recipe contract — `validation/recipe-deck.yaml`

Single 11-slide validation recipe, one per layout. Content lifted (verbatim or condensed) from goldens for fidelity.

```yaml
type: deck
profile: h2t-terminal
palette: default
lang: en
title: "Building Your Personal OS"
nav_buttons: false
nav_hint_text: "arrows / space / swipe"

slides:
  # 01 — title (center variant from pos-sprint slide 01)
  - layout: title
    content:
      eyebrow: "session 01"
      headline: 'Building Your<br><span class="accent">Personal OS</span>'
      subline: "from chaos to system"
      meta: '// speaker name &nbsp;&nbsp;|&nbsp;&nbsp; 2026'
      align: center
      cursor: true

  # 02 — title-body
  - layout: title-body
    content:
      eyebrow: "the problem"
      headline: 'Most knowledge workers<br>operate <span class="danger">without a system.</span>'
      body_html: |
        <p>Tools fragment, attention scatters, output becomes mood-dependent.</p>

  # 03 — stats
  - layout: stats
    content:
      eyebrow: "the problem"
      headline: 'Without a system…'
      stats:
        - { number: "73%", label: "context switching every single day", index: "01", variant: "stat-box" }
        - { number: "4.1h", label: "lost to tool fragmentation weekly", index: "02", variant: "stat-box" }
        - { number: "89%", label: "no repeatable AI methodology", index: "03", variant: "stat-box" }

  # 04 — quote (with bullets)
  - layout: quote
    content:
      eyebrow: "definition"
      headline: 'What is a <span class="accent">Personal OS</span>?'
      quote_html: |
        not a tool — an operating system.<br>
        a layer of rules, context, and constraints<br>
        that shapes how you and AI work together.
        <div class="quote-source">// working definition · 2026</div>
      bullets:
        - { text: "consistent output regardless of mood or energy", sym: "-->" }
        - { text: "AI agents that know your context by default", sym: "-->" }
        - { text: "rules you write once, apply everywhere", sym: "-->" }

  # 05 — cards (card-row 3-up)
  - layout: cards
    content:
      eyebrow: "components"
      headline: 'The <span class="accent">Building Blocks</span>'
      cards_variant: "card-row"
      cards:
        - { icon: "01 · rules", title: "CLAUDE.md", desc_html: "Persistent instructions for your AI layer.", color: "var(--accent)" }
        - { icon: "02 · actions", title: "Skills", desc_html: "Reusable prompt templates invoked by slash commands.", color: "var(--accent2)" }
        - { icon: "03 · integrations", title: "MCP", desc_html: "External connections — Linear, Notion, calendar.", color: "var(--accent3)" }

  # 06 — layers
  - layout: layers
    content:
      eyebrow: "architecture"
      headline: 'System <span class="accent">Architecture</span>'
      layers:
        - { num: "01", name: "Physical", desc_html: "hardware, files, folders, raw storage", color: "#cc6677" }
        - { num: "02", name: "Interface", desc_html: "IDE, terminal, apps", preset: "l2" }
        - { num: "03", name: "Agent", desc_html: "AI layer with rules, context, skills", preset: "l1" }

  # 07 — split (from merkazim slide 03)
  - layout: split
    content:
      eyebrow: "// 02 · format"
      headline: 'Lab session. <span class="accent">3 hours.</span>'
      left_html: |
        <h3 class="accent">// parameters</h3>
        <ul>
          <li>Group <span class="dim">—</span> <span class="accent">12–15</span> people</li>
          <li>Session <span class="dim">—</span> <span class="accent">3 hours</span></li>
        </ul>
      right_html: |
        <h3 class="accent2">// structure</h3>
        <ul>
          <li><span class="accent2">15 min</span> intro</li>
          <li><span class="accent2">45 min</span> case review</li>
          <li><span class="accent2">80 min</span> hands-on</li>
        </ul>

  # 08 — code (with title badge)
  - layout: code
    content:
      eyebrow: "getting started"
      headline: 'Ship in <span class="accent">30 minutes</span>'
      code_title: "terminal"
      # code_html carries INNER code lines only; layout owns the wrapping <pre>.
      # Adding an outer <pre> here produces nested <pre><pre> (T5.1).
      code_html: |
        <span class="code-prompt">$</span> <span class="code-cmd">mkdir</span> <span class="code-arg">~/.claude/skills</span>
          <span class="code-comment"># create your skills directory</span>

        <span class="code-prompt">$</span> <span class="code-cmd">touch</span> <span class="code-arg">~/.claude/CLAUDE.md</span>
          <span class="code-comment"># your global rules file</span>
      caption_html: '<p class="caption"><span class="accent2">//</span>&nbsp; two commands. one session. your OS is running.</p>'

  # 09 — table (from merkazim slide 10)
  - layout: table
    content:
      eyebrow: "// 04 · pilot variants"
      headline: "How tracks compose"
      table_headers: ["Variant", "Volume", "Logic"]
      table_rows:
        - ['<span class="accent">A · Narrow focus</span>', '<span class="mono">2 sessions</span>', "Intro + first 2 sessions of one track."]
        - ['<span class="accent2">B · Extended</span>', '<span class="mono">4 sessions</span>', "Intro + 2 WS from two tracks."]
        - ['<span class="accent3">C · Full track</span>', '<span class="mono">4–6 sessions</span>', "One track with Demo Day."]
      note: "Decision per host — discussed at meeting."

  # 10 — divider
  - layout: divider
    content:
      eyebrow: "// 03 · topics"
      headline: 'Four tracks <span class="dim">+</span><br><span class="accent">extended intro.</span>'

  # 11 — final
  - layout: final
    content:
      eyebrow: "principle 01"
      headline: 'start with one skill.<br><span class="accent">iterate daily.</span>'
      subline: 'systems compound. clarity compounds. <span class="accent2">start now.</span>'
      cursor: true
```

Validation recipe drives both:
- `test_r2_legacy_fidelity.py::test_terminal_deck_assembles_all_layouts`
- Desktop parity screenshot capture (§7)

---

## 5. Forbidden-pattern tests

`plugins/h2t-creative/tests/test_r2_legacy_fidelity.py` — new file, mirrors structure of `test_r1_legacy_fidelity.py`.

### Test groups

#### 5.1 Source dossier
- `test_h2t_terminal_deck_source_dossier_exists` — `profiles/h2t-terminal/sources/references.yaml` and `screenshots/reference-desktop.png` present
- `test_h2t_terminal_deck_dossier_links_legacy_sources` — references.yaml has ids `pos-sprint-terminal-example`, `merkazim`, `pos-sprint-deck-skill`

#### 5.2 Token contract (deck form)
- `test_h2t_terminal_deck_tokens_exists` — `profiles/h2t-terminal/deck/tokens.css` exists
- `test_h2t_terminal_deck_palette_default` — `palettes/default.css` declares all 12 tokens (`--bg`, `--bg-light`, `--bg-card`, `--text`, `--text-dim`, `--accent`, `--accent2`, `--accent3`, `--danger`, `--highlight`, `--pop`, `--border`) with exact values
- `test_h2t_terminal_deck_accent_is_muted_green` — `--accent: #55aa88` (NOT `#00ff41`, the landing palette value)
- `test_h2t_terminal_deck_no_color_prefix` — deck CSS does not declare `--color-*` tokens (deck uses bare `--bg/--text/--accent`)

#### 5.3 Slide layout coverage
- `test_h2t_terminal_deck_all_layouts_present` — for each of 11 layouts, `deck/slides/<layout>/{<layout>.html, <layout>.css, manifest.yaml}` exist
- `test_h2t_terminal_deck_validation_recipe_uses_all_layouts` — validation recipe contains exactly one slide per layout (11 slides total)
- `test_h2t_terminal_deck_validation_recipe_assembles` — `assemble_deck()` returns without error for validation recipe

#### 5.4 Single-file output contract

**Scope of "single-file":** the rule means **no app CSS or app JS files** beyond `index.html` itself. Specifically:
- ✅ ALLOWED: `<link rel="preconnect" href="https://fonts.googleapis.com">`, `<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>`, `<link rel="stylesheet" href="https://fonts.googleapis.com/...">` (Google Fonts only — terminal deck cannot self-host JetBrains Mono inline at acceptable size)
- ❌ FORBIDDEN: `<link rel="stylesheet" href="base.css">`, `<link rel="stylesheet" href="profile.css">`, `<link rel="stylesheet" href="*.css">` for any non-`fonts.googleapis.com` URL, `<script src="...">` for any URL (local or remote — all JS must be inline `<script>...</script>`)

Tests:
- `test_h2t_terminal_deck_single_file_only` — after `assemble_deck()`, `out_dir` contains only `index.html` (no `base.css`, no `profile.css`, no `*.js` files alongside)
- `test_h2t_terminal_deck_index_inlines_css` — `index.html` contains `<style>` block with token declarations
- `test_h2t_terminal_deck_index_inlines_js` — `index.html` contains `<script>` block with `addEventListener('keydown'`
- `test_h2t_terminal_deck_no_external_app_stylesheets` — `index.html` has no `<link rel="stylesheet" href="base.css">`, no `<link rel="stylesheet" href="profile.css">`, no `<link rel="stylesheet">` whose `href` does NOT start with `https://fonts.googleapis.com/`
- `test_h2t_terminal_deck_no_script_src` — `index.html` contains zero `<script src=` occurrences (all JS must be inline; no local script tags, no CDN script tags)

#### 5.5 Frame contract
- `test_h2t_terminal_deck_has_progress_bar` — output contains `<div id="progress-bar">`
- `test_h2t_terminal_deck_has_counter` — output contains `<div id="slide-counter">` with `current` and `cnt-total` spans
- `test_h2t_terminal_deck_has_nav_hint` — output contains `<div id="nav-hint">` with text
- `test_h2t_terminal_deck_has_scanlines` — `body::after` rule with `repeating-linear-gradient` present in inlined CSS
- `test_h2t_terminal_deck_no_slide_menu` — output does NOT contain `class="slide-menu"` (legacy sidebar removed for deck-form profiles)
- `test_h2t_terminal_deck_lang_attr` — `<html lang="...">` matches recipe `lang` field

#### 5.6 Forbidden patterns
- `test_h2t_terminal_deck_no_crosshair_cursor` — deck `tokens.css` does NOT contain `cursor: crosshair`
- `test_h2t_terminal_deck_no_mermaid` — deck profile CSS+HTML contains no `mermaid.min.js`, no `class="mermaid"`, no `mermaid-wrap`
- `test_h2t_terminal_deck_no_emoji_in_layouts` — slide layout HTML files contain no emoji codepoints (use color utility classes instead)
- `test_h2t_terminal_deck_no_radius_on_slide` — `.slide` and `.slide-inner` rules have no `border-radius` (slides are sharp; only cards/stats may use radius — checked permissively)
- ~~`test_h2t_terminal_deck_no_mobile_reflow` — deck profile CSS contains no `@media (max-width:` rules~~ — **withdrawn (T12.5)**, replaced by §5.10 Mobile adaptation contract (below).

#### 5.10 Mobile adaptation contract (T14)

**Replaces** the withdrawn T4/T5/T6 `no @media (max-width:` ban. Lives in
`tests/test_r2_legacy_fidelity.py` under the `# T14 — mobile adaptation contract`
section. T15 implementation must satisfy every test in this group; T14 only
authors the contract — no CSS lands.

**Visual acceptance criteria (drives Agent QA at T16):**

1. **No clipped text at 390×844.** Every slide renders all recipe content within
   the visible viewport — no characters truncated at viewport edges. Tested
   indirectly via the structural rules below + confirmed visually at T16.
2. **No horizontal overflow** except inside explicitly scrollable containers
   (`.code-block` and the `table` wrapper). Body content never extends past the
   right edge of the viewport.
3. **No multi-column layouts** for `.card-row`, `.split`, or `.layer` rows on
   mobile — every horizontal row primitive collapses to a single vertical stack.
4. **Text readable without zoom.** Headlines re-scale (no 1-word-per-line
   stacks); body text stays at ≥14px effective; eyebrow/caption stay readable.

**Structural rules (machine-tested):**

| Rule | Test |
|---|---|
| `@media (max-width: 480px)` block exists in deck CSS | `test_h2t_terminal_deck_mobile_breakpoint_present` |
| `.slide { padding: 56px 80px 80px }` lives outside any `@media` | `test_h2t_terminal_deck_desktop_invariant_outside_media[slide-padding]` |
| `.title-block h1 { font-size: 64px }` lives outside any `@media` | `…[title-h1-size]` |
| `.final-block h1 { font-size: 56px }` lives outside any `@media` | `…[final-h1-size]` |
| `.divider-block h1 { font-size: 48px }` lives outside any `@media` | `…[divider-h1-size]` |
| Mobile block contains a `.slide` rule changing `padding` | `…_mobile_adaptation_covers[slide-padding]` |
| Mobile block reduces `.title-block h1` `font-size` | `…[title-h1-size]` |
| Mobile block reduces `.final-block h1` `font-size` | `…[final-h1-size]` |
| Mobile block reduces `.divider-block h1` `font-size` | `…[divider-h1-size]` |
| Mobile block reduces general `h2` `font-size` | `…[h2-size]` |
| Mobile block flips `.card-row` to `flex-direction: column` | `…[card-row-stack]` |
| Mobile block flips `.layer` to `flex-direction: column` | `…[layer-stack]` |
| Mobile block sets `.split` to `grid-template-columns: 1fr` | `…[split-single-col]` |
| Mobile block declares `.code-block` policy (font-size or overflow-x or padding) | `…[code-policy]` |
| Mobile block applies `overflow-x: auto` to `.table-block` or `table` parent | `…[table-overflow]` |
| Mobile block tunes `#slide-counter` chrome (font-size / position) | `…[counter-chrome]` |
| Mobile block tunes `#nav-hint` chrome (font-size / position) | `…[nav-hint-chrome]` |
| No mobile rule uses `display: none` / `visibility: hidden` on essential content (`.slide`, `.slide-inner`, `.eyebrow`, `h1`, `h2`, `.body`, `.code-block`, `.bullet-list`, `.card`, `.layer`, `.split`, `table`); state-based hiding via `:empty` / `:not(...)` is allowed | `test_h2t_terminal_deck_mobile_no_hidden_essential_content` |
| Every selector inside the mobile block is a class/id already used outside the block, or a known HTML tag | `test_h2t_terminal_deck_mobile_rules_use_known_selectors` |
| `deck-nav.js` does not branch on viewport (`matchMedia`, `innerWidth`, embedded `max-width:`) | `test_h2t_terminal_deck_nav_js_no_viewport_branching` |

**Recipe boundaries (from #92 / two-gate model):**

- ❌ Random mobile redesign that changes desktop fidelity (Gate A invariants must hold).
- ❌ JS viewport branching (`matchMedia`, `innerWidth` reads, `max-width` strings in JS).
- ❌ Hiding essential slide content on mobile (every recipe field still rendered; layout adapts).
- ❌ Claiming a mobile pass without Agent Visual QA at T16 reading every PNG.
- ✅ Profile-owned `@media (max-width: 480px)` rules in any deck CSS file.
- ✅ Mobile font-scale + padding tokens, layout-collapse rules, `overflow-x: auto` wrappers.

#### 5.7 Single-font contract
- `test_h2t_terminal_deck_font_is_mono` — inlined CSS has `--font-heading` and `--font-body` both set to a JetBrains Mono fallback chain; no `serif` or sans-only fallbacks

#### 5.8 Helper unit tests
- `test_render_stats_basic` — `_render_stats([{...}, ...])` produces stat-row with stat-box children and correct labels
- `test_render_stats_escapes_plain_label_but_keeps_html_label` — `label` plain field is HTML-escaped; `label_html` field is preserved raw
- `test_render_cards_card_row_variant` — produces `card-row` with explicit cards
- `test_render_cards_grid_variant` — produces `cards` grid
- `test_render_layers` — produces layer rows with preset class OR inline `--layer-color` style
- `test_render_table_with_note` — produces `<table>` followed by `<p class="meta-note">`
- `test_render_table_preserves_html_in_cells` — `_render_table(headers, rows, ...)` keeps cell HTML intact (e.g. `'<span class="accent">A · Narrow focus</span>'` renders as `<td><span class="accent">A · Narrow focus</span></td>`, NOT escaped to `&lt;span...&gt;`). Validation recipe relies on this — without it the table layout breaks. Same contract for header cells: HTML preserved.
- `test_render_table_escapes_plain_strings` — if a cell value is a `dict` like `{"text": "5 < 10", "html": false}` it's escaped; default convention: cells are passed as raw HTML strings (consistent with goldens), plain strings should not contain unescaped `<`/`>` accidentally — covered by recipe-author convention, not assembler-side escaping
- `test_render_bullets_with_data_sym` — `<li data-sym="-->">` etc.
- `test_render_bullets_default_symbol` — defaults to `>` when `sym` absent

#### 5.9 Generic test list updates
- `test_smoke.py::PROFILES` — h2t-terminal stays in landing list (h2t-terminal landing is not in scope; deck addition is parallel). Add `H2T_TERMINAL_DECK_OK = True` constant or new parametrized test `test_terminal_deck_smoke` that calls `assemble_deck` for h2t-terminal validation recipe and checks `index.html` exists.
- `test_token_contract.py::PROFILES` — h2t-terminal stays for landing tokens (existing palettes default/amber/cyan still valid for landing form). No exclusion needed since deck tokens live in `deck/` subdir, generic tests scan `tokens.css` at profile root.
- `test_font_loading.py` — no change. Existing `test_font_links_deck_editorial` covers editorial; can add `test_font_links_deck_terminal` calling `assemble_deck` and asserting JetBrains Mono link present in inlined `<head>`.

---

## 6. Desktop parity screenshots — all slides

### Role of the tool (read first, agent)

`tools/deck-screenshot-all.py` is a **deterministic per-slide capture utility**, not a parity gate, not a self-approval mechanism, and not a generic screenshot workflow.

- ✅ It exists because the existing approved h2t-tools screenshot workflow captures only the active (first) slide of a deck — it cannot iterate slide states.
- ✅ It produces evidence for the human reviewer: one PNG per slide at desktop and mobile viewports, deterministically named.
- ❌ The agent does NOT use this tool's output to declare R2a "passed". Parity is decided by **human visual review** comparing modular screenshots against goldens.
- ❌ The agent does NOT replace `h2t-tools:screenshot` with this tool for any task other than the deck-slide iteration described here.
- ❌ The agent must NEVER mark a slide as "matches golden" based on automated diff, pixel comparison, or any mechanical check. There is no automated parity gate in R2a.

### Tooling

New script `tools/deck-screenshot-all.py` (under skills repo root, NOT inside profile — reusable across deck slices).

```python
"""Iterate slides via JS-driven navigation and capture each as a PNG.

Usage:
  python tools/deck-screenshot-all.py <input-html-url> --out <dir> --format desktop|mobile|both
"""
```

Behavior:
1. Open input URL in Playwright Chromium.
2. Wait for `#deck` to be present.
3. Read total slide count from `document.querySelectorAll('.slide').length`.
4. For each `i in 0..total-1`:
   - `await page.evaluate("(idx) => showSlide(idx)", i)` — call deck's own JS function (it's exposed as IIFE local — fall back to keyboard `ArrowRight` from slide 0 if `showSlide` not global)
   - Wait for `.slide.active[data-index="${i}"]` (or fade-in animation completion, ~500ms)
   - Screenshot full viewport (NOT `full_page=True` — deck slides are absolute-positioned, full-viewport is correct)
   - Save as `slide-{i+1:02d}-{format}.png`
5. Desktop viewport: 1440×900. Mobile viewport: 390×844 with iPhone UA (matches existing `screenshot.py` mobile config).

### Output structure

```
docs/visual-regression/2026-05-05-r2/
  h2t-terminal-deck-modular/
    desktop/
      slide-01-desktop.png
      ...
      slide-11-desktop.png
    mobile/                        # documentation only
      slide-01-mobile.png
      ...
      slide-11-mobile.png
    parity-notes.md                # any non-blocking deviations from goldens, written during human review
```

### Acceptance gates (two-contour, T12.5 amendment)

**Gate A — Desktop fidelity (human-decided).** The gate is **Agent Visual QA followed by human review
of the captured PNGs against goldens**. Agent role: open every screenshot, write per-slide PASS /
ISSUE / BLOCKER status into `parity-notes.md`. Human role: final parity decision.

Reviewer checklist (per slide, desktop):
- layout (correct structural rendering)
- typography (sizes, weights, casing)
- colors (token application correct, accents land on intended elements)
- chrome (counter, progress, nav-hint visible and styled)
- animations (fade-up active, no layout shift)

**Gate B — Mobile usability (Agent QA + human-decided).** Mobile is **not** a passive baseline.
The deck profile owns mobile rules via `@media (max-width: 480px)` (T14/T15). Agent role: open every
mobile screenshot, classify per slide, fail if catastrophic overflow/clipping/unreadable layout
remains. Human role: usability sign-off.

Reviewer checklist (per slide, mobile):
- no horizontal overflow / no content clipped beyond viewport
- typography readable at 390px (no awkward 1-word-per-line on hero / final)
- horizontal multi-column primitives collapsed (cards stack, layers stack, split → single column)
- table policy applied (overflow-x scroll wrapper or card-list)
- code policy applied (font-scale + overflow-x or wrap rule)
- frame chrome visible and unobtrusive (counter/progress/nav-hint sized for narrow viewport)

Coverage:
- Per-slide layout coverage (one screenshot per declared layout) — implicit since validation recipe covers all 11.

---

## 7. Build sequence

| Step | Task | Verification |
|---|---|---|
| T0 | **Verify public signature of `assemble_deck`** — grep callers across the codebase (`Grep "assemble_deck\|main_assemble"` in `plugins/h2t-creative/`, `tests/`, `scripts/`, any consumer skill or CLI). Inventory: argument order, kwargs, return value. The §1.2 rewrite preserves `(recipe, profile_dir, out_dir, base_dir=None, palette="default")` exactly — confirm no caller relies on the multi-file output side-effect (creating `base.css`/`profile.css`) for profiles that DO have `deck/` subdir. Document inventory in plan addendum if any caller is at risk. | Caller inventory written; either confirms signature is safe or surfaces specific call-sites that need adjustment before T1 starts. |
| T1 | Add `_DECK_FORM_DIR` switch + helpers in `assembler.py` (§1.1, §1.4 backward-compat path) | Existing `test_smoke.py::test_deck_smoke` continues to pass for `h2t-default` etc. |
| T2 | Implement `_render_stats/_render_cards/_render_layers/_render_table/_render_bullets` helpers | Unit tests §5.8 pass |
| T3 | Implement `_build_deck_slide_html_v2`, `_build_deck_css_inline`, `_build_deck_js_inline`, single-file `assemble_deck` rewrite (§1.2) | `assemble_deck()` runs without error on minimal recipe |
| T4 | Create `profiles/h2t-terminal/deck/tokens.css` + `deck/palettes/default.css` + `deck/frame/frame.css` | Token contract tests §5.2 pass |
| T5 | Create 11 slide layouts under `deck/slides/<layout>/` (HTML + CSS + manifest) | Layout coverage tests §5.3 pass |
| T6 | Create `deck/js/deck-nav.js` | Frame contract tests §5.5 pass |
| T7 | Create `validation/recipe-deck.yaml` (§4) | Recipe contract test §5.3 passes |
| T8 | Create `sources/references.yaml` + reference screenshots | Source dossier tests §5.1 pass |
| T9 | Write `tests/test_r2_legacy_fidelity.py` (§5.1–5.7, 5.8) | All R2 tests green |
| T10 | Update `tests/test_smoke.py` and `tests/test_font_loading.py` (§5.9) | All pre-existing tests green |
| T11 | Build validation deck: `python -m assembler --profile h2t-terminal --type deck --recipe profiles/h2t-terminal/validation/recipe-deck.yaml --out /tmp/r2a-validation` | `index.html` produced, opens in browser, all 11 slides reachable |
| T12 | Implement `tools/deck-screenshot-all.py` and capture desktop+mobile sets | Output at `docs/visual-regression/2026-05-05-r2/h2t-terminal-deck-modular/{desktop,mobile}/` (22 PNGs) |
| **T12.5** | **Mandatory Agent Visual QA.** Open every screenshot, write `parity-notes.md` (per-slide desktop+mobile status: PASS / ISSUE / BLOCKER + visible problem). State whether mobile has a usable layout system. If widespread BLOCKERs, propose T14 mobile adaptation plan. Update plan to remove the no-`@media` ban. **No CSS fixes.** | `parity-notes.md` exists with all 22 slides classified; plan amended; explicit mobile go/no-go statement. |
| T13 | Desktop parity fixes (only if Gate A blockers exist). Recapture desktop after fixes. | Desktop slides re-captured; Agent QA re-run on changed slides only. |
| T14 | Mobile adaptation design. Add a "Mobile strategy" section to this plan covering: padding, type scale, cards, layers, split, code, table. Update tests: `_no_mobile_reflow` family withdrawn / replaced by desktop-invariant test. | Plan section landed; tests reflect new contract. |
| T15 | Mobile implementation. Add `@media (max-width: 480px)` rules in `deck/tokens.css` + `deck/frame/frame.css` + relevant `slides/<layout>/<layout>.css`. No JS viewport branching. Recapture all 11 mobile slides. | Mobile slides re-captured under new CSS. |
| T16 | Re-run Agent Visual QA on mobile. Fail if any clipped text / horizontal overflow / unreadable layout remains. | All mobile slides PASS or ISSUE-with-rationale; no BLOCKERs. |
| T17 | Human approval (Gate A + Gate B). | Human signs off both gates. |
| T18 | Commit slice (single squashed commit, per CLAUDE.md no version bump): `feat(h2t-creative): r2a — h2t-terminal deck modular profile (form: deck, single-file, 11 layouts, two-gate visual QA)` | Branch ready for PR. No version bump until live-confirmed. |

---

## 8. Risks / open questions

1. **Single-file output for future deck profiles.** Refactor in §1.2 introduces single-file deck output as the new norm via `_is_deck_form_profile` switch. Existing `h2t-default/h2t-pfad/h2t-editorial` decks fall into legacy multi-file path until each migrates. R2b/R3a/R3b will inherit single-file when they add `deck/` subdirs.
2. **`showSlide` is IIFE-scoped in goldens.** Screenshot script may need to fall back to keyboard simulation (`page.keyboard.press('ArrowRight')`) instead of direct function call. Acceptable; documented in script.
3. **`<html lang>` field.** Goldens differ (pos-sprint `en`, merkazim `ru`). Recipe `lang` field defaults to `en`. Modular profile honors recipe value.
4. **Touch zones (pos-sprint only) skipped.** JS swipe handler covers touch; explicit `#touch-left`/`#touch-right` divs not added. Does not affect desktop parity.
5. **Animation stagger >8 children.** If a slide has more than 8 direct children, the 9th+ have no fade-up delay. Goldens never exceed 8. Layout templates structured to keep direct-child count ≤8.
6. **Color in validation recipe.** Recipe content uses `<span class="accent">...</span>` etc. — interpolated as HTML via `| safe`. All `headline` / `body_html` / `quote_html` / `code_html` / `caption_html` / `left_html` / `right_html` / `desc_html` / `label_html` / `note_html` fields go through `| safe`. Fields like `eyebrow`, plain `subline`, `meta`, `code_title` are HTML-escaped (no markup expected).
7. **Cursor blinking on multiple slides.** Goldens use cursor on title slide and final slide. `cursor: true` recipe field on `title` and `final` layouts only — other layouts do not accept it. Manifest enforces.

---

## 9. Out of scope (deferred / blocked)

- Mobile slide UX strategy → #92 (post-recovery brainstorm)
- h2t-terminal **landing** form recovery → no golden source; not part of R2a or any existing slice
- Editorial deck (#87), editorial landing (#88), pfad dashboard (#89), graphs deck (#90), mono deck (#91) — separate slices, future PRs
- Deck palette variants (amber/cyan for terminal deck) — terminal deck uses single 7-color palette
- Speaker notes export (`note:` field exists in legacy `_build_deck_slide_html` as HTML comment; new path drops it — re-add later if needed)
- Updating `plugins/h2t-creative/skills/deck/SKILL.md` description (multi-file / slide-menu wording) — deferred until last legacy deck profile migrates; see §A.4
- Print/PDF / OBS broadcast modes
- Lazy-loaded fonts / FOUT prevention (fonts loaded via standard `<link>` only; no font-display swap optimization)

---

## 10. Acceptance summary

R2a is done when:

1. `pytest plugins/h2t-creative/tests/` is fully green (R1 fidelity + R2 fidelity + smoke + token contract + font loading)
2. All 11 desktop screenshots in `docs/visual-regression/2026-05-05-r2/h2t-terminal-deck-modular/desktop/` match goldens — **human-confirmed via review**, not by automated diff
3. Mobile baseline captured at `docs/visual-regression/2026-05-05-r2/h2t-terminal-deck-modular/mobile/` — input for #92, not part of R2a gate
4. `parity-notes.md` exists, lists: any non-blocking desktop polish, any catastrophic mobile regressions vs goldens (input for #92), confirmation that R2a introduced no mobile-specific reflow rules
5. Slice committed on `codex/r2a-terminal-deck-fidelity` — no version bump
6. Stop. Do not proceed to R2b without explicit approval.

---

## §A. T0 caller inventory addendum

**T0 verdict: pass — safe to start T1.** One known follow-up captured in T9; one stale-doc follow-up captured below. No blocker.

### Public signatures (current, must be preserved by §1.2)

```python
# plugins/h2t-creative/assembler.py:198
def assemble_landing(
    recipe: dict,
    profile_dir: Path,
    out_dir: Path,
    base_dir: Path | None = None,
    palette: str = "default",
) -> None: ...

# plugins/h2t-creative/assembler.py:309
def assemble_deck(
    recipe: dict,
    profile_dir: Path,
    out_dir: Path,
    base_dir: Path | None = None,
    palette: str = "default",
) -> None: ...

# plugins/h2t-creative/assembler.py:353
def main_assemble(
    output_type: str,
    recipe: dict,
    profile_dir: Path,
    out_dir: Path,
    base_dir: Path | None = None,
    palette: str = "default",
) -> None: ...
```

The §1.2 rewrite preserves all three signatures byte-for-byte. ✅ No caller breakage from signature change.

### Callers — full inventory

| # | File | Line(s) | Function | Profile | Side-effects assumption | Routes via §1.4 to | Risk |
|---|---|---|---|---|---|---|---|
| 1 | `plugins/h2t-creative/assembler.py` | 370 | `assemble_deck` | from CLI | none | dispatched by `_is_deck_form_profile` | none |
| 2 | `plugins/h2t-creative/assembler.py` | 409 | `main_assemble` | from `main()` | none | dispatched | none |
| 3 | `plugins/h2t-creative/skills/deck/SKILL.md` | 78 | CLI invocation `--type deck` | runtime user-chosen | description mentions "multi-file" + "fixed slide menu" | dispatched at runtime per profile | 🟡 doc drift only (see §A.4) |
| 4 | `tests/h2t_creative/test_assembler.py` | 158 | `test_assemble_deck_creates_dist_files` | `_make_minimal_profile` (no `deck/`) | asserts `base.css` + `profile.css` exist | LEGACY path | none |
| 5 | `tests/h2t_creative/test_assembler.py` | 176 | `test_assemble_deck_contains_slides_and_menu` | `_make_minimal_profile` | asserts `slide-menu`, `#slide-1`, `#slide-2`, `ArrowRight` | LEGACY path | none |
| 6 | `tests/h2t_creative/test_assembler.py` | 197 | `test_assemble_deck_speaker_note_as_html_comment` | `_make_minimal_profile` | asserts `<!-- SPEAKER NOTE:` | LEGACY path (note feature lives in `_build_deck_slide_html` legacy) | none |
| 7 | `tests/h2t_creative/test_assembler.py` | 208 | `test_schema_cross_contamination_landing_with_slides_raises` | `_make_minimal_profile` | asserts `SystemExit` | landing path | none |
| 8 | `tests/h2t_creative/test_assembler.py` | 216 | `test_schema_cross_contamination_deck_with_sections_raises` | `_make_minimal_profile` | asserts `SystemExit` | dispatched then validates | none |
| 9 | `tests/h2t_creative/test_assembler.py` | 228 | `test_deck_unknown_layout_raises` | `_make_minimal_profile` | asserts `ValueError("Unknown deck layout")` | LEGACY path uses `DECK_LAYOUTS` set | none |
| 10 | `tests/h2t_creative/test_assembler.py` | 353 | `test_assemble_deck_uses_build_profile_css_not_raw_tokens` | `_make_palette_profile` (no `deck/`) | asserts `profile.css` exists with `--color-bg: #001` | LEGACY path | none |
| 11 | `plugins/h2t-creative/tests/test_smoke.py` | 49 | `test_deck_smoke[<profile>]` | parametrized over `["h2t-default", "h2t-editorial", "h2t-pfad", "h2t-terminal"]` | asserts `(out / "profile.css").exists()` | varies — **see §A.3** | 🔴 **RISKY for `h2t-terminal` once `deck/` subdir lands** |
| 12 | `plugins/h2t-creative/tests/test_font_loading.py` | 38 | `test_font_links_deck_editorial` | `h2t-editorial` (no `deck/`) | asserts `fonts.googleapis.com` in `index.html` | LEGACY path | none today; will need update when R2b lands |

### §A.1 Why most callers are safe

The §1.4 backward-compat switch (`_is_deck_form_profile`) routes by presence of `<profile>/deck/tokens.css`:
- All 5 deck-related tests in `tests/h2t_creative/test_assembler.py` use `_make_minimal_profile` or `_make_palette_profile` — both create profiles WITHOUT a `deck/` subdir → **legacy path** → all current assertions hold (multi-file output, `slide-menu`, `<!-- SPEAKER NOTE: -->`, `Unknown deck layout` error, `_build_profile_css` call, palette propagation).
- `h2t-default`, `h2t-editorial`, `h2t-pfad` profiles have no `deck/` subdir today and R2a does not add one to them → smoke and font-loading tests for these profiles continue on legacy path.

### §A.2 Speaker-note feature — confirmed legacy-only

The legacy `_build_deck_slide_html` (`assembler.py:297-306`) extracts `note` from slide content and emits `<!-- SPEAKER NOTE: ... -->` HTML comment. The new `_build_deck_slide_html_v2` (§1.1) does NOT carry this forward — speaker notes are listed in §9 out-of-scope. Plan §1.3 already documents this. ✅ Documented and contained.

### §A.3 The one risky caller — `test_deck_smoke[h2t-terminal]`

**Risk:** Once R2a creates `profiles/h2t-terminal/deck/tokens.css`, `_is_deck_form_profile(h2t-terminal) → True`. `test_deck_smoke[h2t-terminal]` then routes to the new single-file path with `_DECK_RECIPE` (`test_smoke.py:24-30`):

```python
_DECK_RECIPE = {
    "title": "Smoke Deck",
    "slides": [
        {"layout": "title-only",  "content": {"headline": "Slide 1"}},
        {"layout": "title-body",  "content": {"headline": "Slide 2", "body": "<p>body</p>"}},
    ],
}
```

Two specific failures:
1. New path layout vocabulary (§4): `title`, `divider`, `title-body`, `stats`, `cards`, `layers`, `split`, `code`, `table`, `quote`, `final`. `_DECK_RECIPE` uses `title-only` — **not in the new vocabulary** → `_load_slide_layout` raises.
2. Assertion `assert (out / "profile.css").exists()` (`test_smoke.py:50`) — single-file path emits no `profile.css` → assertion fails.

**Required mitigation in T9 (already documented in §5.9, now made explicit and stronger):**

Update `plugins/h2t-creative/tests/test_smoke.py::test_deck_smoke` to handle deck-form profiles:

```python
@pytest.mark.parametrize("profile", list(PROFILES.keys()))
def test_deck_smoke(tmp_path, profile):
    profile_dir = asm.PROFILES_DIR / profile
    out = tmp_path / "out"
    if asm._is_deck_form_profile(profile_dir):
        # Deck-form profile uses single-file output and validation recipe vocabulary.
        # Smoke is covered by test_deck_smoke_deck_form below; skip generic smoke here.
        pytest.skip(f"{profile} is deck-form; covered by test_deck_smoke_deck_form")
    asm.assemble_deck(_DECK_RECIPE, profile_dir, out)
    assert (out / "index.html").exists()
    assert (out / "profile.css").exists()


def test_deck_smoke_deck_form_h2t_terminal(tmp_path):
    """Smoke test for deck-form profiles: single-file output, validation recipe vocabulary."""
    import yaml
    profile_dir = asm.PROFILES_DIR / "h2t-terminal"
    if not asm._is_deck_form_profile(profile_dir):
        pytest.skip("h2t-terminal not yet deck-form (R2a not landed)")
    recipe_path = profile_dir / "validation" / "recipe-deck.yaml"
    recipe = yaml.safe_load(recipe_path.read_text(encoding="utf-8"))
    out = tmp_path / "out"
    asm.assemble_deck(recipe, profile_dir, out)
    assert (out / "index.html").exists()
    # Single-file: NO base.css / profile.css written
    assert not (out / "base.css").exists()
    assert not (out / "profile.css").exists()
```

This change goes into T9 alongside the other generic test list updates.

### §A.4 Stale documentation — `plugins/h2t-creative/skills/deck/SKILL.md`

The deck skill description (line 3) reads:
> "Generates a multi-file HTML presentation deck using the h2t-creative assembler pipeline. Keyboard navigation (←/→/Space), fixed slide menu, optional fx/. Performs mandatory Playwright QA per slide at 1440px."

After R2a lands, h2t-terminal deck output is **single-file**, has **no fixed slide menu** (replaced by counter + nav-hint per design system), and **no `fx/` for terminal** (fx is for landing form). Other profiles (default/editorial/pfad) keep multi-file legacy until each migrates.

**Runtime impact:** zero. SKILL.md is descriptive prose; the assembler invocation `python assembler.py --profile X --type deck --recipe Y --out Z` works for both paths.

**Doc drift:** the description is no longer accurate for h2t-terminal. Two options:
- Option A: leave as-is (most decks remain multi-file with slide-menu until R3); revisit when last legacy profile migrates.
- Option B: update wording in T9 to "Generates an HTML presentation deck (single-file or multi-file depending on profile)..."

**Decision:** **Option A.** Touching SKILL.md description in R2a invites scope creep into the skill UX. Revisit after R3 lands when most/all profiles are deck-form. Add to plan §9 out-of-scope.

### §A.5 Verdict

- ✅ Public signatures preserved → no caller signature break
- ✅ Legacy multi-file path covers all 4 profiles without `deck/` subdir today → all existing tests hold
- ✅ Speaker-note feature deliberately deprecated only on new path; legacy path unaffected
- 🟡 One test parametrization (`test_deck_smoke[h2t-terminal]`) requires update — captured in T9 with concrete patch in §A.3
- 🟡 One SKILL.md description has minor drift — deferred (§A.4)

**T0 pass — safe to start T1.**
