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


# --- Landing ---

_HTML_LANDING = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <link rel="stylesheet" href="base.css">
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
    component_dir = profile_dir / "components" / component_name
    if not component_dir.exists():
        raise ValueError(f"Component '{component_name}' not found in profile at {component_dir}")
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
            css_path = profile_dir / "components" / name / f"{name}.css"
            if css_path.exists():
                parts.append(css_path.read_text(encoding="utf-8"))
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
    if base_dir is None:
        base_dir = BASE_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    sections = recipe.get("sections", [])
    body = "\n".join(_build_section_html(s, profile_dir) for s in sections)
    has_fx = _has_fx(profile_dir)
    fx_canvas = '<canvas id="bg-canvas"></canvas>' if has_fx else ""
    fx_script = _FX_SCRIPT_LANDING if has_fx else ""
    index_html = _HTML_LANDING.format(
        title=html.escape(str(recipe.get("title", ""))),
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
  <link rel="stylesheet" href="base.css">
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
    index_html = _HTML_DECK.format(
        title=html.escape(str(recipe.get("title", ""))),
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
