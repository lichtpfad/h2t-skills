#!/usr/bin/env python
"""Deterministic per-slide screenshot tool for h2t-creative deck-form output.

Drives `window.showSlide(idx)` (exposed by `deck-nav.js`) to step through every
slide in a built single-file deck and captures one PNG per slide at desktop
and/or mobile viewports. Used by T12 of the R2a recovery flow.

Role boundaries (see plan §6):
  - This is a deterministic capture utility, NOT a parity gate.
  - The agent does NOT use this tool's output to declare "passes golden"; that
    decision belongs to a human reviewer (T13/T14).
  - Mobile screenshots are baseline material for #92, not a parity gate.

Runtime:
  - Requires Playwright. The repo's own venv does not ship it; run via the
    shared h2t-tools venv:
      C:/dev/h2t-tools/.venv/Scripts/python.exe tools/deck-screenshot-all.py ...

Usage:
  deck-screenshot-all.py <index.html> --out <out-dir> [--viewport desktop|mobile|both]

Output naming (stable, filesystem-sorted):
  {out_dir}/{viewport}/slide-NN-<layout>.png
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sys.stderr.write(
        "ERROR: Playwright is not available in this Python.\n"
        "Run via the h2t-tools venv:\n"
        "  C:/dev/h2t-tools/.venv/Scripts/python.exe "
        "tools/deck-screenshot-all.py ...\n"
    )
    sys.exit(2)


VIEWPORTS = {
    "desktop": {"viewport": {"width": 1440, "height": 900}, "device_scale_factor": 1},
    "mobile":  {
        "viewport": {"width": 390, "height": 844},
        "device_scale_factor": 2,
        "is_mobile": True,
        "has_touch": True,
        "user_agent": (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 "
            "Mobile/15E148 Safari/604.1"
        ),
    },
}

# Per-slide-inner block class -> layout name mapping. Used to derive a stable,
# human-readable suffix in filenames. Falls back to `slide` when unrecognized.
_INNER_CLASS_TO_LAYOUT = {
    "title-block":      "title",
    "title-body-block": "title-body",
    "stats-block":      "stats",
    "quote-slide":      "quote",
    "cards-block":      "cards",
    "layers-block":     "layers",
    "split-block":      "split",
    "code-slide":       "code",
    "table-block":      "table",
    "divider-block":    "divider",
    "final-block":      "final",
}


def _safe_layout_name(inner_class: str) -> str:
    """Map slide-inner secondary class to layout name; sanitize for filenames."""
    name = _INNER_CLASS_TO_LAYOUT.get(inner_class, inner_class or "slide")
    return re.sub(r"[^\w-]+", "-", name).strip("-") or "slide"


def _capture_viewport(
    pw, html_path: Path, out_dir: Path, viewport_name: str
) -> int:
    """Capture every slide at the given viewport; returns number of PNGs written."""
    out_dir.mkdir(parents=True, exist_ok=True)
    ctx_kwargs = dict(VIEWPORTS[viewport_name])

    browser = pw.chromium.launch(
        headless=True,
        args=["--disable-blink-features=AutomationControlled"],
    )
    context = browser.new_context(**ctx_kwargs)
    # Hide webdriver flag (anti-detection parity with screenshot.py).
    context.add_init_script(
        "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"
    )
    page = context.new_page()

    # file:// URL on Windows: pathlib gives the right shape.
    page.goto(html_path.resolve().as_uri(), wait_until="networkidle")
    # Wait for fonts (JetBrains Mono via Google Fonts) so capture is stable.
    page.evaluate("() => document.fonts && document.fonts.ready")

    # Discover slide count + per-slide inner classes deterministically.
    info = page.evaluate(
        """
        () => {
          const slides = Array.from(document.querySelectorAll('.slide'));
          return slides.map((s) => {
            const inner = s.querySelector('.slide-inner');
            // Pick the secondary class on .slide-inner (after the literal
            // 'slide-inner' base class) — that is the layout marker.
            let cls = '';
            if (inner) {
              const list = Array.from(inner.classList).filter((c) => c !== 'slide-inner');
              cls = list[0] || '';
            }
            return { cls };
          });
        }
        """
    )
    total = len(info)
    if total == 0:
        sys.stderr.write(f"  WARN: no .slide elements found in {html_path}\n")
        browser.close()
        return 0

    # Sanity-check tooling hook before driving navigation.
    has_show = page.evaluate("() => typeof window.showSlide === 'function'")
    if not has_show:
        sys.stderr.write(
            "  ERROR: window.showSlide is not exposed; deck-nav.js must assign it. "
            "Aborting capture.\n"
        )
        browser.close()
        return 0

    written = 0
    for i, meta in enumerate(info):
        page.evaluate("(i) => window.showSlide(i)", i)
        # Allow opacity-fade transition (0.35s) + entry stagger (≈0.56s) to settle.
        page.wait_for_timeout(900)
        # And confirm the slide actually carries .active before snapping.
        page.wait_for_selector(
            f'.slide[data-index="{i}"].active', state="attached", timeout=2000
        )
        layout_name = _safe_layout_name(meta.get("cls", ""))
        fname = f"slide-{i + 1:02d}-{layout_name}.png"
        out_path = out_dir / fname
        page.screenshot(path=str(out_path), full_page=False)
        print(f"  + {viewport_name}: {out_path.relative_to(out_dir.parent)}")
        written += 1

    browser.close()
    return written


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "html",
        type=Path,
        help="Path to the assembled deck index.html",
    )
    parser.add_argument(
        "--out",
        type=Path,
        required=True,
        help="Output directory; subfolders desktop/ and/or mobile/ are created here.",
    )
    parser.add_argument(
        "--viewport",
        choices=["desktop", "mobile", "both"],
        default="both",
        help="Which viewport(s) to capture (default: both).",
    )
    args = parser.parse_args()

    if not args.html.exists():
        sys.stderr.write(f"ERROR: html not found: {args.html}\n")
        return 2

    targets = (
        ["desktop", "mobile"] if args.viewport == "both" else [args.viewport]
    )
    args.out.mkdir(parents=True, exist_ok=True)
    total_written = 0
    print(f"-> source: {args.html}")
    print(f"-> out:    {args.out}")
    with sync_playwright() as pw:
        for vp in targets:
            print(f"-- {vp} ({VIEWPORTS[vp]['viewport']['width']}x"
                  f"{VIEWPORTS[vp]['viewport']['height']}) --")
            n = _capture_viewport(pw, args.html, args.out / vp, vp)
            total_written += n
            if n == 0:
                sys.stderr.write(f"  FAIL: no screenshots written for {vp}\n")
                return 3
    print(f"OK: {total_written} screenshots written.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
