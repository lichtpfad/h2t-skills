"""Token Contract v2: every palette + tokens.css exports canonical token names."""
import re
from pathlib import Path  # noqa: F401

import assembler as asm
import pytest

# R1 profiles (h2t-graphs, h2t-mono) follow golden token contract — see test_r1_legacy_fidelity.py
PROFILES = {
    "h2t-default":   ["default"],
    "h2t-editorial": ["default", "night", "warm"],
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
