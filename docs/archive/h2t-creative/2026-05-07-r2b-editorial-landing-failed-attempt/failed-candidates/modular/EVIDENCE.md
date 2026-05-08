# Visual evidence — h2t-editorial landing modular (post Intent Reset)

## Status: ready for Agent Visual QA

Recipe rewritten 2026-05-07 to satisfy the approved composition spec
(plan §16 Intent Reset, Amendments A + B). The previous slug
`r2b-h2t-editorial-landing-system-b-validation/` is FROZEN as Batch C
evidence and lives under `../h2t-editorial-landing-system-b-modular/`.

## File inventory

### Build (source of truth)

```
C:\dev\h2t-skills-r2b-landing\dist\r2b-h2t-editorial-landing-modular\
├── index.html      10 049 b   222 LOC   mtime 2026-05-07 21:15:27
├── profile.css     14 871 b              mtime 2026-05-07 21:15:27
└── base.css         2 319 b              mtime 2026-05-07 21:15:27
```

LOC budget per composition spec §6 G2: ≤ 250 → **222 — within budget**.

### Screenshots

| File | Captured | Synchrony |
|------|----------|-----------|
| `unknown/desktop_20260507_211611.png` | 2026-05-07 21:16:15 | 48 s after build, fresh dir |
| `unknown/mobile_20260507_211611.png`  | 2026-05-07 21:16:16 | 49 s after build, fresh dir |

## Capture command

```bash
C:/dev/h2t-tools/.venv/Scripts/python.exe \
  C:/dev/h2t-tools/scripts/screenshot/screenshot.py \
  "file:///C:/dev/h2t-skills-r2b-landing/dist/r2b-h2t-editorial-landing-modular/index.html" \
  --out C:/dev/h2t-skills-r2b-landing/docs/visual-regression/2026-05-07-r2b/h2t-editorial-landing-modular \
  --format both
```

## Acceptance gates (composition spec §6, automated as §LT-9)

| Gate | Status |
|------|--------|
| G1 — ≤ 10 non-CTA recipe sections + ≤ 1 editorial-cta | ✓ (10 + 1) |
| G2 — built index.html ≤ 250 LOC | ✓ (222) |
| G3 — no `.dt / .proh-tbl / .wave-block / .comp-box / .disc / .meta-box / .funnel` in build HTML | ✓ |
| G4 — no `<img>` tags in build HTML | ✓ |
| G5 — fresh dist path `r2b-h2t-editorial-landing-modular/` | ✓ |
| G6 — editorial-cta renders approved DOM | ✓ |

All §LT-9 tests passed (568/568 landing tests, 1088/1088 plugin, 105/105 assembler).

## Next step

Agent Visual QA — open both PNGs via `Read`, score per block (PASS/ISSUE/BLOCKER) at desktop and mobile, write `parity-notes.md` in this directory. **No fixes until notes are written.**
