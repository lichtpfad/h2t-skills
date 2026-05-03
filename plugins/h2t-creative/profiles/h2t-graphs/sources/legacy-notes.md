# h2t-graphs Legacy Notes

Source: h2t:landing v2.14.1 + graphs.lichtpfadstudio.com

## Visual Grammar

**Typography**
- Display: Inter 700–800, large bold headings
- Body/labels: JetBrains Mono
- Numbers: Inter 700 with `text-shadow: 0 0 15px var(--color-accent-glow)`

**Color System**
- bg: #060609, bg2: #0a0a10, surface: #0e0e16
- accent: #e94560, accent-glow: rgba(233,69,96,0.4)
- text: #a0a0b8, text-hi: #d0d0e0, text-dim: #3a3a50
- border: rgba(233,69,96,0.12)

**Layout Motifs**
- Body: `cursor: crosshair`
- Background: 40px CSS grid via repeating-linear-gradient
- HUD panels: `border: 1px solid var(--color-border)`, `background: var(--color-surface)`
- Corner brackets: L-shaped pseudo-elements using accent color

**Forbidden Substitutions**
- No border-radius anywhere
- No box-shadow (only text-shadow glow)
- No generic shared pricing/testimonials/features-grid as validation evidence
- No rounded pill chips
