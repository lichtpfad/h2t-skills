# Visual evidence — h2t-editorial landing System B-Landing modular

## Status: SUSPENDED for #88 Landing Intent Reset (2026-05-07)

The screenshots in this directory were captured during Batch C of the
appendix-clone implementation. That target was rejected: System B-Landing
goldens are **appendix/report pages**, not a landing layout. They are
re-classified as a **primitive source** (provide visual language) — not
as a 1:1 fidelity target. See:

- `docs/visual-regression/2026-05-07-r2b/h2t-editorial-landing-composition-spec.md`
- `docs/superpowers/plans/2026-05-07-r2b-h2t-editorial-modularization.md` §16 (Intent Reset)

No visual gate is claimed against these PNGs. They survive only as
audit trail of the intermediate build state.

## File inventory

| File | Captured | Status | Reason |
|------|----------|--------|--------|
| `unknown/desktop_20260507_204317.png` | 2026-05-07 20:43:31 | **INVALID — stale** | Captured before tokens.css typography fix. Build at 20:43 carried R1-era responsive `h1: clamp(2.5rem,…,4rem)` from `base.css` overriding System B-Landing globals; max-width:1100px wrapper missing. Visible breakage: huge h1, full-width body. Build at 20:53 has the fix layered into `tokens.css`. |
| `unknown/mobile_20260507_204317.png` | 2026-05-07 20:43:33 | **INVALID — stale** | Same root cause as desktop_204317. |
| `unknown/desktop_20260507_205339.png` | 2026-05-07 20:53:43 | VALID for the 20:53 build | Captured 13 s after the fixed build. Renders the appendix-clone version that was REJECTED on intent grounds (target mismatch). |
| `unknown/mobile_20260507_205339.png` | 2026-05-07 20:53:44 | VALID for the 20:53 build | Same as desktop_205339. |
| `unknown/desktop_20260507_210114.png` | 2026-05-07 21:01:14 | VALID for the current build | Definitive Intent Reset evidence capture — confirms screenshot/HTML correspondence one last time before the appendix-clone is set aside. Same content as `_205339`, captured against the same `index.html` mtime 2026-05-07 20:53:30. |
| `unknown/mobile_20260507_210114.png` | 2026-05-07 21:01:14 | VALID for the current build | Same as desktop_210114. |

## Source-of-truth build (frozen at intent-reset moment)

```
C:\dev\h2t-skills-r2b-landing\dist\r2b-h2t-editorial-landing-system-b-validation\
├── index.html      17 589 b   mtime 2026-05-07 20:53:30
├── profile.css     21 010 b   mtime 2026-05-07 20:53:30
└── base.css         2 319 b   mtime 2026-05-07 20:53:30
```

## Capture command (for reproducibility)

```bash
C:/dev/h2t-tools/.venv/Scripts/python.exe \
  C:/dev/h2t-tools/scripts/screenshot/screenshot.py \
  "file:///C:/dev/h2t-skills-r2b-landing/dist/r2b-h2t-editorial-landing-system-b-validation/index.html" \
  --out C:/dev/h2t-skills-r2b-landing/docs/visual-regression/2026-05-07-r2b/h2t-editorial-landing-system-b-modular \
  --format both
```

The `unknown/` subdir name comes from the screenshot tool's domain
extraction on `file://` URLs (no domain → defaults to `unknown/`). Not
a regression — leave as-is until the tool is patched separately.

## Next valid evidence

The next legitimate visual capture happens AFTER:
1. `h2t-editorial-landing-composition-spec.md` is approved by the human.
2. Recipe is rewritten to compose a landing (block inventory), not to
   clone the appendix vertical structure.
3. New build emitted to a **fresh dist/ path** so old artefacts cannot
   contaminate the audit trail.
