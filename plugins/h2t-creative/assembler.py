#!/usr/bin/env python3
"""h2t-creative assembler: base + profile + recipe -> dist/"""
import argparse
import html
import re
import shutil
import sys
import yaml
from pathlib import Path

PLUGIN_ROOT = Path(__file__).parent
BASE_DIR = PLUGIN_ROOT / "base"
PROFILES_DIR = PLUGIN_ROOT / "profiles"
SHARED_DIR = PLUGIN_ROOT / "shared"


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


def _build_head_scripts(profile_dir: Path) -> str:
    scripts = _load_profile_config(profile_dir).get("head_scripts", [])
    if not scripts:
        return ""
    return "\n".join(f'  <script src="{src}"></script>' for src in scripts) + "\n"
DECK_LAYOUTS = {"title-only", "title-body", "title-media", "blank"}
FX_SIZE_WARN_BYTES = 50 * 1024

_PLACEHOLDER_RE = re.compile(r'\{\{\s*(\w+)(?:\s*\|\s*safe)?\s*\}\}')
_SAFE_PLACEHOLDER_RE = re.compile(r'\{\{\s*(\w+)\s*\|\s*safe\s*\}\}')


def interpolate(template: str, fields: dict) -> str:
    """Substitute {{ field }} (HTML-escaped) and {{ field | safe }} (raw)."""
    safe_fields = set(_SAFE_PLACEHOLDER_RE.findall(template))

    def replacer(m):
        field_name = m.group(1)
        if field_name not in fields:
            raise ValueError(
                f"Template placeholder '{{{{ {field_name} }}}}' has no matching recipe field"
            )
        value = str(fields[field_name])
        return value if field_name in safe_fields else html.escape(value)

    return _PLACEHOLDER_RE.sub(replacer, template)


def validate_section_content(section: dict, manifest: dict) -> None:
    """Validate recipe section content keys against component manifest."""
    component_name = manifest.get("component", "?")
    content = section.get("content", {})
    manifest_fields = manifest.get("fields", {})

    for key in content:
        if key not in manifest_fields:
            raise ValueError(
                f"Component '{component_name}': unknown field '{key}' in recipe content"
            )
    for field, schema in manifest_fields.items():
        if schema.get("required", False) and field not in content:
            raise ValueError(
                f"Component '{component_name}': required field '{field}' missing from recipe"
            )


def load_recipe(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_manifest(component_dir: Path) -> dict:
    with open(component_dir / "manifest.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _resolve_component_dir(component_name: str, profile_dir: Path, shared_dir: Path = SHARED_DIR) -> Path:
    profile_comp = profile_dir / "components" / component_name
    if profile_comp.exists():
        return profile_comp
    shared_comp = shared_dir / "components" / component_name
    if shared_comp.exists():
        return shared_comp
    raise ValueError(
        f"Component '{component_name}' not found in profile '{profile_dir.name}' or shared/"
    )


# --- Landing ---

_HTML_LANDING = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
{font_links}{head_scripts}  <link rel="stylesheet" href="base.css">
  <link rel="stylesheet" href="profile.css">
</head>
<body>
{body}
{fx_canvas}
{fx_script}
</body>
</html>
"""

_FX_SCRIPT_LANDING = (
    '<script>var c=document.getElementById("bg-canvas");'
    'import("./fx.js").then(function(m){{m.init(c);'
    'window.addEventListener("unload",function(){{m.destroy();}});}});</script>'
)


def _has_fx(profile_dir: Path) -> bool:
    fx_js = profile_dir / "fx" / "background.js"
    if not fx_js.exists():
        return False
    size = fx_js.stat().st_size
    if size > FX_SIZE_WARN_BYTES:
        print(
            f"WARNING: fx/background.js is {size // 1024}KB (>{FX_SIZE_WARN_BYTES // 1024}KB threshold)",
            file=sys.stderr,
        )
    return True


def _build_section_html(section: dict, profile_dir: Path) -> str:
    component_name = section["component"]
    component_dir = _resolve_component_dir(component_name, profile_dir)
    manifest = load_manifest(component_dir)
    validate_section_content(section, manifest)
    template = (component_dir / f"{component_name}.html").read_text(encoding="utf-8")
    content = dict(section.get("content", {}))
    for field, schema in manifest.get("fields", {}).items():
        if field not in content and "default" in schema:
            content[field] = schema["default"]
    return interpolate(template, content)


def _build_profile_css(profile_dir: Path, sections: list, palette: str = "default") -> str:
    palettes_dir = profile_dir / "palettes"
    if palettes_dir.exists():
        palette_path = palettes_dir / f"{palette}.css"
        if not palette_path.exists():
            raise ValueError(
                f"Palette '{palette}' not found in profile '{profile_dir.name}'. "
                f"Available: {[p.stem for p in palettes_dir.glob('*.css')]}"
            )
        color_css = palette_path.read_text(encoding="utf-8")
    else:
        color_css = ""

    parts = [(profile_dir / "tokens.css").read_text(encoding="utf-8")]
    if color_css:
        parts.append(color_css)

    seen: set = set()
    for section in sections:
        name = section["component"]
        if name not in seen:
            shared_css = SHARED_DIR / "components" / name / f"{name}.css"
            if shared_css.exists():
                parts.append(shared_css.read_text(encoding="utf-8"))
            profile_css = profile_dir / "components" / name / f"{name}.css"
            if profile_css.exists():
                parts.append(profile_css.read_text(encoding="utf-8"))
            seen.add(name)
    return "\n".join(parts)


def _build_base_css(base_dir: Path) -> str:
    return "\n".join(
        (base_dir / f).read_text(encoding="utf-8")
        for f in ["reset.css", "grid.css", "typography.css", "animations.css", "deck.css"]
        if (base_dir / f).exists()
    )


def assemble_landing(
    recipe: dict,
    profile_dir: Path,
    out_dir: Path,
    base_dir: Path | None = None,
    palette: str = "default",
) -> None:
    # Semantic-vs-legacy routing (T4 of semantic renderer v0 — issue #118).
    # Legacy recipes never enter this branch; their byte-output is
    # preserved verbatim by the unchanged code path below.
    has_blocks = "blocks" in recipe
    has_sections = "sections" in recipe
    if has_blocks and has_sections:
        raise ValueError(
            "landing recipe declares both 'blocks:' (semantic format) "
            "and 'sections:' (legacy format). Pick one — the formats "
            "are mutually exclusive (architecture spec §3)."
        )
    if has_blocks:
        from renderer.adapter import build_legacy_recipe_from_semantic
        recipe = build_legacy_recipe_from_semantic(recipe, profile_dir)
    if base_dir is None:
        base_dir = BASE_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    sections = recipe.get("sections", [])
    body = "\n".join(_build_section_html(s, profile_dir) for s in sections)
    has_fx = _has_fx(profile_dir)
    fx_canvas = '<canvas id="bg-canvas"></canvas>' if has_fx else ""
    fx_script = _FX_SCRIPT_LANDING if has_fx else ""
    font_links = _build_font_links(profile_dir)
    head_scripts = _build_head_scripts(profile_dir)
    index_html = _HTML_LANDING.format(
        title=html.escape(str(recipe.get("title", ""))),
        font_links=font_links,
        head_scripts=head_scripts,
        body=body,
        fx_canvas=fx_canvas,
        fx_script=fx_script,
    )
    (out_dir / "index.html").write_text(index_html, encoding="utf-8")
    (out_dir / "base.css").write_text(_build_base_css(base_dir), encoding="utf-8")
    (out_dir / "profile.css").write_text(
        _build_profile_css(profile_dir, sections, palette=palette), encoding="utf-8"
    )
    if has_fx:
        shutil.copy(profile_dir / "fx" / "background.js", out_dir / "fx.js")


# --- Deck ---

# Deck-form profile switch (R2a / issue #86):
#   When a profile contains a `deck/` subdir with `tokens.css`, `assemble_deck` routes
#   to the new single-file path (`_assemble_deck_form_v2`). Otherwise it routes to the
#   legacy multi-file path (`_assemble_deck_legacy`). T1 only wires the switch — the
#   form-v2 rendering itself is implemented in T2/T3.
DECK_FORM_DIR = "deck"


def _deck_dir(profile_dir: Path) -> Path:
    return profile_dir / DECK_FORM_DIR


def _is_deck_form_profile(profile_dir: Path) -> bool:
    """True when profile contains deck/tokens.css — switches assemble_deck to single-file path."""
    return (_deck_dir(profile_dir) / "tokens.css").exists()


# --- Deck-form rendering helpers (R2a T2) ---
# These render array fields from the deck recipe into HTML strings.
# Contract conventions (used across all helpers):
#   - Plain text fields (e.g. `label`, `desc`, `name`, `title`) are HTML-escaped.
#   - Fields with `_html` suffix (e.g. `label_html`, `desc_html`, `items_html`, `text_html`)
#     are kept raw — recipe author is responsible for escaping/quoting.
#   - Table cells and headers follow design system §Component primitives:
#     headers escaped (plain text), cells raw (per recipe convention).


def _render_stats(stats: list) -> str:
    """Render stats as <div class="stat-row">...</div>.

    Each item: {number, label OR label_html, index?, variant?, number_class?}.
    variant='stat-box' (default, pos-sprint): red top border, data-index attr.
    variant='stat' (merkazim): centered, color via .num.<number_class>.
    """
    items = []
    for i, s in enumerate(stats, start=1):
        number = html.escape(str(s.get("number", "")))
        label = s["label_html"] if "label_html" in s else html.escape(str(s.get("label", "")))
        variant = s.get("variant", "stat-box")
        if variant == "stat-box":
            index = html.escape(str(s.get("index", f"{i:02d}")), quote=True)
            items.append(
                f'<div class="stat-box" data-index="{index}">'
                f'<div class="stat-number">{number}</div>'
                f'<div class="stat-label">{label}</div>'
                f'</div>'
            )
        elif variant == "stat":
            num_class = str(s.get("number_class", "")).strip()
            num_attr = (
                f'class="num {html.escape(num_class)}"' if num_class else 'class="num"'
            )
            items.append(
                f'<div class="stat">'
                f'<div {num_attr}>{number}</div>'
                f'<div class="label">{label}</div>'
                f'</div>'
            )
        else:
            raise ValueError(
                f"Unknown stat variant: '{variant}'. Valid: stat-box, stat"
            )
    return f'<div class="stat-row">{"".join(items)}</div>'


def _render_cards(cards: list, variant: str = "card-row") -> str:
    """Render cards in one of two variants.

    variant='card-row' (pos-sprint): flex row of cards with icon/title/desc and
    optional --card-color top border.
    Each item: {icon, title, desc OR desc_html, color?}.

    variant='cards' (merkazim): auto-fit grid of cards with tag chip + h3 + items.
    Each item: {tag, tag_class?, title, items? (list[str], escaped) OR items_html (raw)
                OR body_html (raw)}.
    """
    items = []
    if variant == "card-row":
        for c in cards:
            color = c.get("color")
            style_attr = (
                f' style="--card-color: {html.escape(str(color), quote=True)};"'
                if color
                else ""
            )
            icon = html.escape(str(c.get("icon", "")))
            title = html.escape(str(c.get("title", "")))
            desc = (
                c["desc_html"]
                if "desc_html" in c
                else html.escape(str(c.get("desc", "")))
            )
            items.append(
                f'<div class="card"{style_attr}>'
                f'<div class="card-icon">{icon}</div>'
                f'<div class="card-title">{title}</div>'
                f'<div class="card-desc">{desc}</div>'
                f'</div>'
            )
        return f'<div class="card-row">{"".join(items)}</div>'
    if variant == "cards":
        for c in cards:
            tag_class = str(c.get("tag_class", "")).strip()
            tag_attr = (
                f'class="tag {html.escape(tag_class)}"' if tag_class else 'class="tag"'
            )
            tag_text = html.escape(str(c.get("tag", "")))
            title = html.escape(str(c.get("title", "")))
            if "items_html" in c:
                inner = f'<ul>{c["items_html"]}</ul>'
            elif "items" in c:
                lis = "".join(
                    f'<li>{html.escape(str(item))}</li>' for item in c["items"]
                )
                inner = f"<ul>{lis}</ul>"
            elif "body_html" in c:
                inner = c["body_html"]
            else:
                inner = ""
            items.append(
                f'<div class="card">'
                f'<span {tag_attr}>{tag_text}</span>'
                f'<h3>{title}</h3>'
                f'{inner}'
                f'</div>'
            )
        return f'<div class="cards">{"".join(items)}</div>'
    raise ValueError(f"Unknown cards variant: '{variant}'. Valid: card-row, cards")


def _render_layers(layers: list) -> str:
    """Render architecture layers as <div class="layers">...</div>.

    Each item: {num, name, desc OR desc_html, color? OR preset?}.
    `color` (inline `--layer-color: ...`) takes precedence over `preset` (CSS class
    `l1`/`l2`/`l3`/`l4`/`lh`). When both are set, `color` is applied and `preset` is ignored.
    """
    items = []
    for layer in layers:
        num = html.escape(str(layer.get("num", "")))
        name = html.escape(str(layer.get("name", "")))
        desc = (
            layer["desc_html"]
            if "desc_html" in layer
            else html.escape(str(layer.get("desc", "")))
        )
        color = layer.get("color")
        preset = layer.get("preset")
        if color:
            class_attr = 'class="layer"'
            style_attr = (
                f' style="--layer-color: {html.escape(str(color), quote=True)};"'
            )
        elif preset:
            class_attr = f'class="layer {html.escape(str(preset))}"'
            style_attr = ""
        else:
            class_attr = 'class="layer"'
            style_attr = ""
        items.append(
            f'<div {class_attr}{style_attr}>'
            f'<div class="layer-num">{num}</div>'
            f'<div class="layer-name">{name}</div>'
            f'<div class="layer-desc">{desc}</div>'
            f'</div>'
        )
    return f'<div class="layers">{"".join(items)}</div>'


def _render_table(headers: list, rows: list, note: str = "") -> str:
    """Render a dual-representation table for desktop + mobile (T15.5).

    Output structure:
      <div class="table-desktop">
        <table>...</table>
      </div>
      <div class="table-mobile">
        <article class="table-card">
          <h3>{first cell raw}</h3>
          <dl>
            <dt>{header[1] escaped}</dt><dd>{cell[1] raw}</dd>
            <dt>{header[2] escaped}</dt><dd>{cell[2] raw}</dd>
            ...
          </dl>
        </article>
        ...
      </div>
      [<p class="meta-note">{note escaped}</p> if note]

    Contract:
      - **headers** are plain text and are HTML-escaped (used as <th> on desktop
        and as <dt> labels on mobile).
      - **cells** (rows[][]) are kept raw — recipe author passes HTML strings
        like '<span class="accent">A</span>'. This is the documented convention
        (design system §Component primitives + plan §5.8 critical test).
      - **note** is plain text and is HTML-escaped, rendered as
        `<p class="meta-note">` appended after both representations when non-empty.

    Mobile mapping per row:
      - first cell  → <h3> (card title); raw HTML preserved
      - rest cells  → <dt>{header}</dt><dd>{cell}</dd> pairs

    CSS toggles which representation is visible (desktop / mobile @media); the
    DOM always carries both — no content is hidden, only one rendering is shown.
    """
    # --- Desktop representation (original <table>) ---
    head = "".join(f"<th>{html.escape(str(h))}</th>" for h in headers)
    body = "".join(
        "<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>"
        for row in rows
    )
    desktop = (
        f'<div class="table-desktop">'
        f'<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>'
        f'</div>'
    )

    # --- Mobile representation (stacked cards) ---
    rest_headers = headers[1:] if len(headers) > 1 else []
    cards = []
    for row in rows:
        if not row:
            continue
        title_cell = row[0]
        rest = row[1:]
        dl_pairs = []
        for i, cell in enumerate(rest):
            label = (
                html.escape(str(rest_headers[i]))
                if i < len(rest_headers)
                else ""
            )
            dl_pairs.append(f"<dt>{label}</dt><dd>{cell}</dd>")
        dl = f'<dl>{"".join(dl_pairs)}</dl>' if dl_pairs else ""
        cards.append(
            f'<article class="table-card">'
            f'<h3>{title_cell}</h3>'
            f'{dl}'
            f'</article>'
        )
    mobile = f'<div class="table-mobile">{"".join(cards)}</div>'

    parts = [desktop, mobile]
    if note:
        parts.append(f'<p class="meta-note">{html.escape(str(note))}</p>')
    return "".join(parts)


def _render_bullets(bullets: list) -> str:
    """Render bullets as <ul class="bullet-list">...</ul>.

    Each item: {text OR text_html, sym?}. Default `sym` = '>'.
    The `sym` value goes into a `data-sym` attribute and is escaped accordingly.
    """
    items = []
    for b in bullets:
        sym = html.escape(str(b.get("sym", ">")), quote=True)
        text = (
            b["text_html"]
            if "text_html" in b
            else html.escape(str(b.get("text", "")))
        )
        items.append(f'<li data-sym="{sym}">{text}</li>')
    return f'<ul class="bullet-list">{"".join(items)}</ul>'


_DECK_LAYOUT_HTML = {
    "title-only": '<div class="slide-inner"><h1 class="slide-headline">{{ headline }}</h1></div>',
    "title-body": (
        '<div class="slide-inner">'
        '<h1 class="slide-headline">{{ headline }}</h1>'
        '<div class="slide-body">{{ body | safe }}</div>'
        '</div>'
    ),
    "title-media": (
        '<div class="slide-inner slide-inner--media">'
        '<h1 class="slide-headline">{{ headline }}</h1>'
        '<div class="slide-media"><img src="{{ media_url }}" alt="{{ headline }}"></div>'
        '</div>'
    ),
    "blank": '<div class="slide-inner"></div>',
}

_DECK_NAV_JS = """\
(function(){
  var slides=document.querySelectorAll('.slide');
  var links=document.querySelectorAll('.slide-menu a');
  var cur=0;
  function show(i){
    slides.forEach(function(s,j){s.classList.toggle('slide--active',j===i);});
    links.forEach(function(a,j){a.classList.toggle('slide-menu__link--active',j===i);});
    window.location.hash='slide-'+(i+1); cur=i;
  }
  document.addEventListener('keydown',function(e){
    if(e.key==='ArrowRight'||e.key===' '){if(cur<slides.length-1)show(cur+1);}
    if(e.key==='ArrowLeft'){if(cur>0)show(cur-1);}
  });
  links.forEach(function(a,i){a.addEventListener('click',function(e){e.preventDefault();show(i);});});
  var h=window.location.hash;
  show(h?Math.max(0,Math.min(parseInt(h.replace('#slide-',''))-1,slides.length-1)):0);
})();"""

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


def _build_deck_slide_html(slide: dict) -> str:
    layout = slide.get("layout", "title-body")
    if layout not in DECK_LAYOUTS:
        raise ValueError(f"Unknown deck layout: '{layout}'. Valid: {sorted(DECK_LAYOUTS)}")
    template = _DECK_LAYOUT_HTML[layout]
    content = dict(slide.get("content", {}))
    note = content.pop("note", None)
    inner = interpolate(template, content) if template else ""
    note_comment = f"\n<!-- SPEAKER NOTE: {html.escape(str(note))} -->" if note else ""
    return f'<section class="slide">{inner}{note_comment}\n</section>'


def assemble_deck(
    recipe: dict,
    profile_dir: Path,
    out_dir: Path,
    base_dir: Path | None = None,
    palette: str = "default",
) -> None:
    """Dispatch to legacy multi-file or form-v2 single-file path based on profile shape.

    A profile is considered "deck-form" iff `<profile_dir>/deck/tokens.css` exists.
    See R2a plan §1.4 / §A. Public signature unchanged from prior versions.
    """
    if _is_deck_form_profile(profile_dir):
        return _assemble_deck_form_v2(
            recipe, profile_dir, out_dir, base_dir=base_dir, palette=palette
        )
    return _assemble_deck_legacy(
        recipe, profile_dir, out_dir, base_dir=base_dir, palette=palette
    )


def _assemble_deck_legacy(
    recipe: dict,
    profile_dir: Path,
    out_dir: Path,
    base_dir: Path | None = None,
    palette: str = "default",
) -> None:
    """Legacy multi-file deck output. Used for any profile without `deck/` subdir."""
    if base_dir is None:
        base_dir = BASE_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    slides_data = recipe.get("slides", [])
    slides_html = "\n".join(_build_deck_slide_html(s) for s in slides_data)
    menu_links = "\n".join(
        f'  <a href="#slide-{i+1}" class="slide-menu__link">'
        f'{html.escape(str(s.get("title", f"Slide {i+1}")))}</a>'
        for i, s in enumerate(slides_data)
    )
    has_fx = _has_fx(profile_dir)
    fx_canvas = '<canvas id="bg-canvas"></canvas>' if has_fx else ""
    fx_script = (
        '<script>var c=document.getElementById("bg-canvas");'
        'import("./fx.js").then(function(m){m.init(c);});</script>'
    ) if has_fx else ""
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
    (out_dir / "index.html").write_text(index_html, encoding="utf-8")
    (out_dir / "base.css").write_text(_build_base_css(base_dir), encoding="utf-8")
    (out_dir / "profile.css").write_text(
        _build_profile_css(profile_dir, [], palette=palette), encoding="utf-8"
    )
    if has_fx:
        shutil.copy(profile_dir / "fx" / "background.js", out_dir / "fx.js")


def _load_slide_layout(profile_dir: Path, layout: str) -> tuple:
    """Return (template_html, manifest_dict) for a deck slide layout.

    Layout files live at <profile>/deck/slides/<layout>/{<layout>.html, manifest.yaml}.
    Raises ValueError with the available layouts list when the layout dir is missing.
    """
    slides_root = _deck_dir(profile_dir) / "slides"
    layout_dir = slides_root / layout
    if not layout_dir.exists():
        available = (
            sorted([d.name for d in slides_root.iterdir() if d.is_dir()])
            if slides_root.exists()
            else []
        )
        raise ValueError(
            f"Slide layout '{layout}' not found in {profile_dir.name}/deck/slides/. "
            f"Available: {available}"
        )
    template_path = layout_dir / f"{layout}.html"
    manifest_path = layout_dir / "manifest.yaml"
    if not template_path.exists():
        raise ValueError(
            f"Slide layout '{layout}' is missing {layout}.html at {template_path}"
        )
    if not manifest_path.exists():
        raise ValueError(
            f"Slide layout '{layout}' is missing manifest.yaml at {manifest_path}"
        )
    template = template_path.read_text(encoding="utf-8")
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    return template, manifest


def _apply_manifest_defaults(content: dict, manifest: dict) -> dict:
    """Fill in default values from manifest for fields absent in content."""
    out = dict(content)
    for field, schema in manifest.get("fields", {}).items():
        if field not in out and "default" in schema:
            out[field] = schema["default"]
    return out


def _build_deck_slide_html_v2(slide: dict, profile_dir: Path, index: int = 0) -> str:
    """Build one <section class="slide">...</section> for deck-form profiles.

    Pre-renders array fields (stats/cards/layers/table/bullets) into HTML strings,
    applies manifest defaults, then interpolates the layout template via interpolate().
    """
    layout = slide.get("layout", "title-body")
    template, manifest = _load_slide_layout(profile_dir, layout)
    content = _apply_manifest_defaults(dict(slide.get("content", {})), manifest)

    # Pre-render array fields into *_html keys consumed by templates.
    if "stats" in content:
        content["stats_html"] = _render_stats(content.pop("stats"))
    if "cards" in content:
        cards_variant = content.pop("cards_variant", "card-row")
        content["cards_html"] = _render_cards(
            content.pop("cards"), variant=cards_variant
        )
    if "layers" in content:
        content["layers_html"] = _render_layers(content.pop("layers"))
    if "table_headers" in content or "table_rows" in content:
        content["table_html"] = _render_table(
            content.pop("table_headers", []),
            content.pop("table_rows", []),
            content.pop("note", ""),
        )
    if "bullets" in content:
        content["bullets_html"] = _render_bullets(content.pop("bullets"))

    inner = interpolate(template, content)
    classes = "slide center" if slide.get("align") == "center" else "slide"
    return f'<section class="{classes}" data-index="{index}">{inner}</section>'


def _build_deck_css_inline(
    profile_dir: Path, slides: list, palette: str = "default"
) -> str:
    """Concatenate deck CSS: tokens, palette, frame, deduped per-layout CSS."""
    deck_root = _deck_dir(profile_dir)
    parts = []
    tokens_path = deck_root / "tokens.css"
    if tokens_path.exists():
        parts.append(tokens_path.read_text(encoding="utf-8"))
    palettes_dir = deck_root / "palettes"
    palette_path = palettes_dir / f"{palette}.css"
    if not palette_path.exists():
        available = (
            sorted([p.stem for p in palettes_dir.glob("*.css")])
            if palettes_dir.exists()
            else []
        )
        raise ValueError(
            f"Deck palette '{palette}' not found in {profile_dir.name}/deck/palettes/. "
            f"Available: {available}"
        )
    parts.append(palette_path.read_text(encoding="utf-8"))
    frame_css = deck_root / "frame" / "frame.css"
    if frame_css.exists():
        parts.append(frame_css.read_text(encoding="utf-8"))
    seen: set = set()
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
    """Read deck nav JS for inlining into <script>."""
    js_path = _deck_dir(profile_dir) / "js" / "deck-nav.js"
    if not js_path.exists():
        raise ValueError(
            f"Deck nav script not found at {js_path}. "
            f"Profile must provide deck/js/deck-nav.js for form-v2 output."
        )
    return js_path.read_text(encoding="utf-8")


def _render_nav_buttons() -> str:
    """Optional prev/next nav buttons rendered when recipe.nav_buttons is true."""
    return (
        '  <button class="nav-btn prev" id="btn-prev">'
        '<span class="chevron">◄</span> prev</button>\n'
        '  <button class="nav-btn next" id="btn-next">'
        'next <span class="chevron">►</span></button>\n'
    )


# Single-file deck HTML template. Slot tokens use __SLOT_*__ sentinels (replaced via
# str.replace, not str.format) so inline CSS/JS containing { and } chars pass through
# verbatim. Sentinel strings do not appear in CSS/JS by convention.
_HTML_DECK_FORM_V2 = """\
<!DOCTYPE html>
<html lang="__SLOT_LANG__">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>__SLOT_TITLE__</title>
__SLOT_FONT_LINKS__  <style>
__SLOT_INLINE_CSS__
  </style>
</head>
<body>
  <div id="progress-bar"></div>
  <div id="slide-counter">
    <span class="current" id="cnt-current">01</span>
    <span class="dim"> / </span>
    <span id="cnt-total">__SLOT_TOTAL_PADDED__</span>
  </div>
  <div id="nav-hint">__SLOT_NAV_HINT__</div>
__SLOT_NAV_BUTTONS__  <div id="deck">
__SLOT_SLIDES_HTML__
  </div>
  <script>
__SLOT_INLINE_JS__
  </script>
</body>
</html>
"""


def _assemble_deck_form_v2(
    recipe: dict,
    profile_dir: Path,
    out_dir: Path,
    base_dir: Path | None = None,
    palette: str = "default",
) -> None:
    """Single-file deck output for deck-form profiles.

    Contract:
      - Output is exactly one file: out_dir/index.html
      - All app CSS inlined in <style>; Google Fonts via <link rel="stylesheet"> still allowed
      - All JS inlined in <script>; no <script src=>
      - No <link rel="stylesheet"> for base.css/profile.css/any non-fonts URL
      - No legacy slide-menu sidebar; frame chrome = progress + counter + nav-hint
        + optional prev/next buttons
      - `base_dir` accepted for signature consistency; unused (no base.css written).
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    slides = recipe.get("slides", [])
    slides_html = "\n".join(
        _build_deck_slide_html_v2(s, profile_dir, index=i)
        for i, s in enumerate(slides)
    )
    inline_css = _build_deck_css_inline(profile_dir, slides, palette=palette)
    inline_js = _build_deck_js_inline(profile_dir)
    font_links = _build_font_links(profile_dir)
    nav_buttons_html = _render_nav_buttons() if recipe.get("nav_buttons") else ""
    lang = html.escape(str(recipe.get("lang", "en")), quote=True)
    title = html.escape(str(recipe.get("title", "")))
    nav_hint = html.escape(
        str(recipe.get("nav_hint_text", "arrows / space / swipe"))
    )
    total_padded = str(len(slides)).zfill(2) if slides else "00"

    out_html = _HTML_DECK_FORM_V2
    # str.replace() avoids {} collisions with inline CSS/JS — see template comment.
    for token, value in (
        ("__SLOT_LANG__", lang),
        ("__SLOT_TITLE__", title),
        ("__SLOT_FONT_LINKS__", font_links),
        ("__SLOT_INLINE_CSS__", inline_css),
        ("__SLOT_TOTAL_PADDED__", total_padded),
        ("__SLOT_NAV_HINT__", nav_hint),
        ("__SLOT_NAV_BUTTONS__", nav_buttons_html),
        ("__SLOT_SLIDES_HTML__", slides_html),
        ("__SLOT_INLINE_JS__", inline_js),
    ):
        out_html = out_html.replace(token, value)
    (out_dir / "index.html").write_text(out_html, encoding="utf-8")


# --- Shared entry points ---

def main_assemble(
    output_type: str,
    recipe: dict,
    profile_dir: Path,
    out_dir: Path,
    base_dir: Path | None = None,
    palette: str = "default",
) -> None:
    if output_type == "landing" and "slides" in recipe:
        print("ERROR: type=landing recipe must not contain 'slides:' key", file=sys.stderr)
        sys.exit(1)
    if output_type == "deck" and "sections" in recipe:
        print("ERROR: type=deck recipe must not contain 'sections:' key", file=sys.stderr)
        sys.exit(1)
    if output_type == "landing":
        assemble_landing(recipe, profile_dir, out_dir, base_dir=base_dir, palette=palette)
    else:
        assemble_deck(recipe, profile_dir, out_dir, base_dir=base_dir, palette=palette)


def dry_run(recipe: dict, output_type: str, profile_dir: Path, out_dir: Path) -> None:
    would_create = [
        str(out_dir / "index.html"),
        str(out_dir / "base.css"),
        str(out_dir / "profile.css"),
    ]
    if _has_fx(profile_dir):
        would_create.append(str(out_dir / "fx.js"))
    print(f"DRY RUN — would create ({len(would_create)} files):")
    for path in would_create:
        print(f"  {path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="h2t-creative assembler")
    parser.add_argument("--profile", required=True, help="Profile name under profiles/")
    parser.add_argument("--type", required=True, choices=["landing", "deck"])
    parser.add_argument("--recipe", required=True, help="Path to recipe.yaml")
    parser.add_argument("--out", required=True, help="Output directory")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--palette", default=None, help="Palette override (flag > recipe.palette > 'default')")
    args = parser.parse_args()

    recipe = load_recipe(Path(args.recipe))
    profile_dir = PROFILES_DIR / args.profile
    if not profile_dir.exists():
        print(f"ERROR: profile '{args.profile}' not found at {profile_dir}", file=sys.stderr)
        sys.exit(1)

    out_dir = Path(args.out)

    palette = args.palette if args.palette else recipe.get("palette", "default")
    if args.dry_run:
        dry_run(recipe, args.type, profile_dir, out_dir)
        return

    main_assemble(args.type, recipe, profile_dir, out_dir, palette=palette)
    print(f"Built {args.type} -> {out_dir}")


if __name__ == "__main__":
    main()
