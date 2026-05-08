# h2t-editorial landing — design system extraction

**Date:** 2026-05-07
**Phase:** R2b T2 — component vocabulary extraction (NOT implementation)
**Branch:** `codex/r2b-editorial-landing`
**Sources:**
- PRIMARY: [`rejuve-appendix-competitive-report.html`](h2t-editorial-landing-golden/rejuve-appendix-competitive-report.html) (1265 LOC)
- SECONDARY: [`rejuve-appendix-elpodium-decomposition.html`](h2t-editorial-landing-golden/rejuve-appendix-elpodium-decomposition.html) (992 LOC)
**Approved by:** 2026-05-07 source arbitration ([`docs/superpowers/specs/2026-05-07-r2b-landing-source-arbitration.md`](../../superpowers/specs/2026-05-07-r2b-landing-source-arbitration.md))

> **Scope.** This document extracts the **actual primitive vocabulary** observed in the locked landing goldens, in preparation for T3 implementation. It is descriptive, not prescriptive. The extracted vocabulary becomes the closed component contract for landing recovery — generic `hero / nav / section / cta / footer` from R1 are explicitly **out of scope** unless proven by the goldens.
>
> **Why this step exists.** Without explicit DOM/CSS extraction the temptation is to map golden content onto the existing R1 component shape (cta/footer/hero/nav/section). That would produce a "landing page" that looks structurally unrelated to the rejuve appendix. The extraction here is the contract that prevents that drift.

---

## 1. Page shell architecture

Both goldens use **a tab-based single-document SPA shell**, not a scroll-based marketing page. Multiple `.page` divs coexist in the DOM; client JS toggles which one carries `.active`.

```html
<body>
  <nav class="tabs">                                  <!-- sticky top -->
    <button class="tab active" onclick="switchTab(this,'overview')">…</button>
    <button class="tab" onclick="switchTab(this,'cards')">…</button>
    …
  </nav>

  <div id="overview" class="page active">             <!-- only one active -->
    <div class="ph">                                  <!-- page header -->
      <h1>Конкурентная разведка — REjuve</h1>
      <span class="ph-meta">Апрель 2026 · Кантон Цуг + Zürich-area</span>
    </div>

    <div class="section">                             <!-- section block -->
      <h2>Воронка отбора</h2>
      …content…
    </div>

    <div class="section">…</div>
  </div>

  <div id="cards" class="page">…</div>
  …
</body>
```

| Primitive | Selector | Role |
|-----------|----------|------|
| Tab strip | `.tabs` | sticky-top, accent border-bottom 2px, var(--bg) bg, z-index 10 |
| Tab item | `.tab` / `.tab.active` | button-style, dim → accent-bordered when active, font 13px |
| Page container | `.page` / `.page.active` | display:none default; `.active` displays it; padding 28/32; max-width 1100; mx auto |
| Page header | `.ph` | flex baseline-aligned h1 + meta; bottom border 1px var(--bd); margin-bottom 24px |
| Page title | `.ph h1` | Playfair 28px, var(--ad) accent-dark, mb 6px |
| Page meta | `.ph-meta` | sans 12px var(--mu) |
| Section | `.section` | margin-bottom 36px; contains h2 + content blocks |
| Section heading | `h2` (global) | Playfair 20px var(--ad), margin 28/12 |
| Sub-heading | `h3` (global) | sans 14px bold var(--tx), m 0/6 |

---

## 2. Container + grid primitives

| Primitive | Selector | Spec |
|-----------|----------|------|
| Card | `.card` | var(--sf) bg + var(--bd) border + var(--r) radius + 16px padding |
| 2-col grid | `.g2` | grid-template-columns 1fr 1fr, gap 16 |
| 3-col grid | `.g3` | grid-template-columns 1fr 1fr 1fr, gap 16 |
| 4-col grid | `.g4` | repeat(4, 1fr), gap 12 |

These are the universal layout chrome — used inside `.section` for any side-by-side content.

---

## 3. Stat / KPI primitives

### 3.1 Compact stat (both goldens)
```html
<div class="stat">
  <span class="stat-n">143</span>
  <span class="stat-l">национальности в кантоне</span>
</div>
```
| Selector | Spec |
|----------|------|
| `.stat` | var(--sf) card, text-align:center, padding 14/16 |
| `.stat-n` | Playfair 26px var(--ad), block, lh 1.1 |
| `.stat-l` | sans 11px var(--mu), block, lh 1.4, mt 4 |

### 3.2 Funnel-style hero (competitive-report only)
```html
<div class="funnel">
  <div class="fn-box">
    <span class="fn-n">70</span>
    <span class="fn-l">сканированный долгожитель-рынок CH</span>
  </div>
  <span class="fn-arr">→</span>
  <div class="fn-box">
    <span class="fn-n">16</span>
    <span class="fn-l">…</span>
  </div>
  …
</div>

<div class="g3">                <!-- companion 3-col detail row -->
  <div class="fn-detail"><h3>…</h3><ul><li>→ …</li></ul></div>
  …
</div>
```
| Selector | Spec |
|----------|------|
| `.funnel` | flex row align-items:center, mb 20 |
| `.fn-box` | var(--sf) card, text-align:center, padding 20/24 |
| `.fn-n` | Playfair **40px** var(--ad), block (hero scale, larger than `.stat-n`) |
| `.fn-l` | sans 11px var(--mu), mt 6 |
| `.fn-arr` | flex:1, text-center, var(--ac), 28px |
| `.fn-detail` | var(--sf) card with `<h3>` + `<ul>` (→-prefixed bullets) |

---

## 4. Categorized cards (competitive-report)

### 4.1 Market map — type-categorized
```html
<div class="mmap">
  <div class="mmap-cell">
    <div class="mmap-type">Премиум-ретриты CH</div>
    <div class="mmap-brands">Clinique La Prairie, Kusnacht Practice…</div>
    <div class="mmap-note">CHF 20 000 – 100 000+</div>
  </div>
  …
</div>
```
| Selector | Spec |
|----------|------|
| `.mmap` | grid 2-col gap 12 |
| `.mmap-cell` | var(--sf) card padding 14 |
| `.mmap-type` | 11px bold var(--ad) uppercase letter-spaced 0.05em, mb 6 |
| `.mmap-brands` | 12px var(--tx) lh 1.8 |
| `.mmap-note` | 11px var(--mu) mt 6 |

### 4.2 Positioning grid — accent-bordered
```html
<div class="pos-grid">
  <div class="pos">
    <div class="pos-title">English-first в Цуге</div>
    <div class="pos-desc">Ближайший англоязычный конкурент — в 28 км</div>
  </div>
  …
</div>
```
| Selector | Spec |
|----------|------|
| `.pos-grid` | grid 2-col gap 12 |
| `.pos` | var(--sf), border + 3px var(--ac) left, radius 0/r/r/0 (right-only), padding 12/14 |
| `.pos-title` | bold 13px var(--tx) mb 4 |
| `.pos-desc` | 12px var(--mu) |

---

## 5. Tables — System B-Landing has FOUR distinct table primitives

This is the heart of System B-Landing — pitch-deck-grade dense tables with semantic row coding.

### 5.1 Brand-comparison table `.bt` (competitive-report; basis pattern)
```html
<table class="bt">
  <thead>
    <tr><th>Бренд</th><th>City</th><th>Цена</th><th>Pillars</th>…</tr>
  </thead>
  <tbody>
    <tr class="rejuve"><td>REjuve</td>…</tr>           <!-- self-row, saturated gold -->
    <tr class="deep"><td>AYUN</td>…</tr>               <!-- highlighted, faint gold -->
    <tr><td>Cryoxon</td>…</tr>                          <!-- normal -->
    …
  </tbody>
</table>
```
| Selector | Spec |
|----------|------|
| `.bt` | full-width, border-collapse:collapse, font 12px |
| `.bt th` | var(--sf) bg + border var(--bd) + 8/10 padding + 11px **bold** var(--ad) uppercase, white-space nowrap |
| `.bt td` | border + 8/10 padding, valign middle |
| `.bt tr:hover td` | hover bg `#f0ede6` |
| `.bt tr.deep td` | bg `#c9a96e14` (8% accent tint) |
| `.bt tr.rejuve td` | bg `#c9a96e30` (19% accent tint) + bold |

### 5.2 Decomposition table `.dt` (elpodium; same anatomy, denser)
- `.dt` font 12px first-col-centered numbered + section-collapse pattern
- `.dt-section` collapsible wrapper (`.dt-section-header / -body / -title / -meta / -chevron`)
- `.dt tr.w1 / .w2 / .w3 td` — wave-coded **left border** (3px solid var(--w1/w2/w3))

### 5.3 Specialized tables (competitive-report)
- `.proh-tbl` — prohibitions: red first-col, green second-col, dim last-col
- `.pen-tbl` — penalties: red third-col bold (fines)
- `.icp-tbl` — ICP: bold mu first-col labels at 120px width

### 5.4 Wave / phase blocks (elpodium; complement to `.dt`)
- `.wave-block / .wave-header / .wave-badge` — wave grouping (badge is 32×32 round colored)
- `.wave-title` Playfair 17px serif
- `.wb / .wb-fill / .wb-n` — horizontal weight bar (max-width 120, height 10)
- `.ab / .ab-fill` — attribution bar (max-width 80, height 8, var(--gr) fill)

---

## 6. Tag / badge primitives (very rich)

System B-Landing has **two tag families**: type-tags (color-coded by category) and chip-tags (priority/wave/automation indicators).

### 6.1 Type-tags (competitive)
```html
<span class="tag tag-fs">FUNCTIONAL</span>
<span class="tag tag-md">MEDICAL</span>
<span class="tag tag-sm">SPECIALIZED</span>
<span class="tag tag-b2">B2B</span>
```
| Selector | Hue |
|----------|-----|
| `.tag` | base — padding 2/7, radius 3, 10px bold |
| `.tag-fs` | gold tint `#c9a96e22` text `#8a6520` (functional studio) |
| `.tag-md` | blue tint `#2255aa18` text `#1a3d80` (medical) |
| `.tag-sm` | green tint `#3d6b4a18` text `#2a5035` (specialized) |
| `.tag-b2` | purple tint `#66229918` text `#440077` (B2B) |
| `.mod-tag` | modality tag — bg + border + dim color (used in card lists) |

### 6.2 Automation-level chips (elpodium)
| Selector | Hue |
|----------|-----|
| `.auto` | green tint (fully automated) |
| `.hybrid` | gold tint (AI + human) |
| `.human` | red tint (human only) |
| `.na` | grey tint (not applicable) |

### 6.3 Priority chips (elpodium)
| Selector | Hue |
|----------|-----|
| `.p0` | blue tint (highest) |
| `.p1` | purple tint |
| `.p2` | grey tint (lowest) |

### 6.4 Wave chips (elpodium)
| Selector | Hue |
|----------|-----|
| `.w1t` | green tint (wave 1) |
| `.w2t` | blue tint (wave 2) |
| `.w3t` | purple tint (wave 3) |

### 6.5 Status indicators (inline text)
| Selector | Color |
|----------|-------|
| `.yes` | var(--gr) bold |
| `.no` | var(--dn) |
| `.part` | `#aa7700` (amber) |

---

## 7. Composed brand-card row (competitive — 16-row competitor list)

This is the most complex primitive in the System B-Landing vocabulary. A side-by-side flex card with image-strip on the left + body content on the right.

```html
<div class="ck">
  <div class="ck-vis">
    <img src="…" alt="…">                              <!-- 240×160 site capture -->
    <hr class="ck-vis-sep">
    <img src="…" class="meta-ad">                       <!-- 240×120 ad capture -->
    <div class="ck-soc">@brand · 12k followers</div>    <!-- OR -->
    <div class="ck-meta-none">No ads detected (Meta Ad Library, 04/2026)</div>
  </div>
  <div class="ck-body">
    <div class="ck-head">
      <span class="ck-name">AYUN</span>
      <span class="ck-loc">Zürich</span>
    </div>
    <div class="ck-tags"><span class="tag tag-md">MEDICAL</span>…</div>
    <ul class="ck-bullets">
      <li>…</li>
    </ul>
  </div>
</div>
```
| Selector | Spec |
|----------|------|
| `.ck` | flex row, var(--sf) bg, var(--bd) border, radius var(--r), overflow:hidden, mb 16 |
| `.ck-vis` | 240px wide, flex-col, border-right var(--bd) |
| `.ck-vis img` | 100% width, height 160 (or 120 with `.meta-ad`), object-fit cover top |
| `.ck-vis-sep` | hr inside the column (`border-top` only) |
| `.ck-soc` | 8/12 padding, 11px var(--mu), bg var(--bg), lh 1.6 |
| `.ck-meta-none` | 10/12 padding, 11px var(--mu), bg var(--bg), lh 1.8 |
| `.ck-body` | flex:1, padding 16/20 |
| `.ck-head` | flex baseline gap 10, mb 10 |
| `.ck-name` | Playfair 17px var(--ad) |
| `.ck-loc` | 11px var(--mu) |
| `.ck-tags` | mb 10, flex wrap gap 4 |
| `.ck-bullets` | 12px lh 1.9 list-style:none |

---

## 8. Specialized blocks (compliance / discussion / meta)

### 8.1 Flow / numbered steps (competitive)
```html
<div class="flow">
  <div class="flow-step">
    <div class="flow-num">1</div>
    <div class="flow-body">
      <div class="flow-title">…</div>
      <div class="flow-desc">…</div>
    </div>
  </div>
  <div class="flow-sep"></div>
  …
</div>
```
| Selector | Spec |
|----------|------|
| `.flow-num` | 28×28 round, var(--ac) bg, white 12px bold |
| `.flow-sep` | 2px wide var(--bd) vertical separator (margin-left 13) |

### 8.2 Compliance box (competitive)
| Selector | Spec |
|----------|------|
| `.comp-box` | var(--sf) card |
| `.comp-law` | 11px bold var(--ad) uppercase letter-spaced |
| `.comp-fine` | inline pill, danger tint `#cc222215` text var(--dn), bold 11px |

### 8.3 Disclaimer / appendix note
```html
<div class="disc">…footnote / disclaimer text…</div>
```
| Selector | Spec |
|----------|------|
| `.disc` | var(--sf) card, **3px var(--ac) left border**, radius 0/r/r/0, 10/14 padding, 11px var(--mu) lh 1.7, italic-feel |

### 8.4 Meta box (highlighted, blue-tinted)
```html
<div class="meta-box">
  <h3>…</h3>
  <p>…</p>
</div>
```
| Selector | Spec |
|----------|------|
| `.meta-box` | bg `#f0f4ff` (light blue), border `#b8c8e8`, radius var(--r), padding 14 |
| `.meta-box h3` | var(--bl) heading inside |

---

## 9. JS contract observed in goldens

Both goldens carry a single `switchTab(button, pageId)` function bound to `<button class="tab" onclick="switchTab(this, 'pageId')">`. Behaviour:
1. Remove `.active` from current `.tab` and current `.page`.
2. Add `.active` to clicked `.tab` and target `.page` by id.
3. (Optionally) update `location.hash` for deep-linking.

System B-Landing JS contract for landing recovery:
- bind to `<button class="tab">` clicks
- toggle `.active` on tab + matching `.page#<id>`
- preserve hash sync (parity with deck deck-nav.js)
- NO viewport branching (CSS-only mobile)

---

## 10. Closed primitive vocabulary — vs R1 generic components

### Extracted (System B-Landing canonical, 9 groups)
1. **Page shell:** `.tabs / .tab / .page / .ph / .ph-meta / .section`
2. **Containers + grids:** `.card / .g2 / .g3 / .g4`
3. **Stats:** `.stat + .stat-n + .stat-l` (compact); `.funnel + .fn-box + .fn-n + .fn-l + .fn-arr + .fn-detail` (hero)
4. **Categorized cards:** `.mmap / .mmap-cell / .mmap-type / .mmap-brands / .mmap-note`; `.pos-grid / .pos / .pos-title / .pos-desc`
5. **Tables:** `.bt` (brand-comparison) + `.dt` (decomposition + collapsible) + `.proh-tbl / .pen-tbl / .icp-tbl` (specialized) + `.wave-block + .wb + .ab` (phase bars)
6. **Tags / chips:** `.tag + .tag-fs / .tag-md / .tag-sm / .tag-b2`; `.mod-tag`; `.auto / .hybrid / .human / .na`; `.p0 / .p1 / .p2`; `.w1t / .w2t / .w3t`; `.yes / .no / .part`
7. **Composed brand cards:** `.ck` family (`.ck-vis / .ck-soc / .ck-meta-none / .ck-body / .ck-head / .ck-name / .ck-loc / .ck-tags / .ck-bullets`)
8. **Specialized blocks:** `.flow + .flow-step + .flow-num + .flow-body + .flow-title + .flow-desc + .flow-sep`; `.comp-box + .comp-law + .comp-desc + .comp-fine`; `.disc`; `.meta-box`
9. **Tab-switcher JS** (`switchTab(button, pageId)` — single-document SPA navigation)

### Out of scope — R1 generic components

The following exist in `profiles/h2t-editorial/components/` from R1:

| R1 component | Out-of-scope verdict |
|--------------|----------------------|
| `cta/` | **OUT** — landing pages are reports/appendices, not marketing. No CTA in either golden. |
| `footer/` | **OUT** — neither golden has a footer; closing content lives in last `.section`. |
| `hero/` | **OUT (replaced)** — System B-Landing has no marketing hero; opening block is `.ph` page header. |
| `nav/` | **OUT (replaced)** — System B-Landing uses `.tabs` (sticky tab strip, not a marketing nav). |
| `section/` | Possibly REUSED but only as a thin shell wrapping `<div class="section">`. Implementation will reset its CSS. |

R1 components stay on disk for backward compatibility (per layer-alongside token strategy in T1) but **are not extended to fit System B-Landing**. Recovery work targets the extracted vocabulary above; new components live under `profiles/h2t-editorial/components/<name>/` alongside R1 generics (the assembler's `_resolve_component_dir` does not look under a `landing/` subdir). Namespace separation is by **component name**, not by directory: distinct primitive names (`tabs / page-header / card-grid / stats`) prevent collision with R1 generics (`nav / hero / cta / footer`).

---

## 11. T3+ implementation hints (informational, NOT contract)

For the next batch (component implementation):

- **Build a per-primitive-group test set first** mirroring R2a deck per-layout tests: existence + manifest fields + render smoke + token usage + forbidden patterns.
- **Validation recipe** can be a single-page render exercising every primitive group on one page (analog of deck's 8-slide validation deck), or split per-tab as the goldens do.
- **Mobile contract** (Gate B): both goldens preserve full table layouts on mobile (no representation switch). Stats stack 1×N. Side-by-side criteria → 1fr. The complex `.ck` row likely needs to collapse image-strip width or move it above text on narrow viewports — observe in golden mobile screenshot.
- **The `.ck` primitive carries `<img>` tags** — for the validation recipe, this layout falls under the same `known_fidelity_gaps` policy as deck's `image-text`: visual gate excluded, structural test only, unless real image assets are committed alongside.

---

## 12. References

- Source dossier: `plugins/h2t-creative/profiles/h2t-editorial/sources/landing-references.yaml`
- Arbitration spec: `docs/superpowers/specs/2026-05-07-r2b-landing-source-arbitration.md`
- Deck design system (System B canonical, sibling form): no equivalent doc — extracted inline in deck arbitration spec §2 + dossier `source_conflict.systems` block
- Plan §5.2 amendment: replace generic `cta / footer / hero / nav / section` vocabulary with the closed list in §10 above (this doc)
