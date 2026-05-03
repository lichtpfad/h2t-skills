# Visual Regression Checklist — Phase 2b — 2026-05-03

Build: `landing-course.yaml` × 6 profiles  
Screenshots: `docs/visual-regression/2026-05-03/*.png`

---

## h2t-default

- [x] White background, dark near-black text
- [x] System sans-serif font (no web font loaded)
- [x] Electric blue accent on stats + testimonial border
- [x] CTA button: blue bg, white text (contrast ok)
- [x] Mobile layout stacks correctly

## h2t-editorial

- [x] Cream/warm background
- [x] Playfair Display serif loaded (visible in headline)
- [x] Terracotta accent on stats + testimonial border
- [x] CTA button: terracotta bg, white text (contrast ok)
- [x] Mobile layout stacks correctly

## h2t-graphs

- [x] Dark near-black background
- [x] Monospace font throughout
- [x] Red accent on stats + testimonial border
- [x] CTA button: red bg, white text (contrast ok)
- [x] Mobile layout stacks correctly

## h2t-mono

- [x] Near-black background
- [x] JetBrains Mono throughout (display + body)
- [x] Red accent on stats + testimonial border
- [x] CTA button: red bg, white text (contrast ok)
- [x] border-radius: 0 (no rounded corners)
- [x] Mobile layout stacks correctly

## h2t-pfad

- [x] Dark near-black background
- [x] JetBrains Mono throughout
- [x] Red accent on stats + testimonial border
- [x] CTA button: red bg, white text (contrast ok)
- [x] Corner bracket decoration visible in hero
- [x] Mobile layout stacks correctly

## h2t-terminal

- [x] Very dark background
- [x] Monospace font throughout
- [x] ALL-CAPS headline (terminal style)
- [x] Green accent on stats + testimonial border
- [x] CTA button: bright green bg, dark text (contrast ok — `--color-on-accent: #000`)
- [x] Mobile layout stacks correctly

---

## Semver Gate

**Result: ALL INVARIANTS PASS — `[x]` everywhere, no `[!]`**

**Task 5 (v1.2.0 bump) is UNBLOCKED.**
