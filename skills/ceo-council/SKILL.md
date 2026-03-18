---
name: ceo-council
description: "Strategic council of AI advisors — real people or abstract roles, with persona profiles and confidence scores. Modes: strategic, brainstorm, critic, realism. Triggers: 'ceo council', 'council', 'стратегический анализ', 'совет', 'build-persona'."
compatibility: "Claude Code"
metadata:
  author: lichtpfad
  version: 2.0.0
---

# CEO Council — Strategic Advisory System

**Purpose:** Launch isolated advisors (abstract roles or real people) to analyze problems from diverse perspectives.
Each advisor is isolated — no coordination between them produces genuine disagreement.

---

## Persona System

### Storage
Persona profiles live in `~/.h2t/config/personas/` (Syncthing-synced across machines).
Each file: `{slug}.md` with YAML frontmatter.

### Persona file format
```markdown
---
name: Lex Fridman
slug: lex-fridman
confidence: 72
sources: 8
last_updated: 2026-03-18
expertise: [AI, robotics, deep learning, long-form dialogue]
style: curious, patient, finds cross-disciplinary patterns, asks "why" repeatedly
known_views:
  ai_risk: cautiously optimistic, gradual alignment
  creativity: art and science as unified pursuit
  long_term_thinking: thinks in decades, not quarters
---

## Known positions
...

## Communication patterns
...

## Sources used
- Transcript: Lex Fridman Podcast #369 with Sam Altman
- Book excerpt: ...
```

### Confidence score logic
| Score | Meaning |
|-------|---------|
| 0-30% | Weak — public reputation only, no direct sources |
| 31-60% | Moderate — 1-3 transcripts or interviews |
| 61-85% | Good — multiple sources, direct quotes |
| 86-100% | Strong — deep corpus, personal communications |

Display format: `Lex Fridman (72% — 8 sources)`

---

## Command: build-persona

When user says `build-persona`, `create persona`, `добавить персону`:

1. Ask for source: transcript path, URL, or pasted text
2. Read/fetch the source
3. Extract: expertise, communication style, known positions, notable quotes
4. Check if persona already exists in `~/.h2t/config/personas/`
   - If yes: merge new data, recalculate confidence, increment `sources`
   - If no: create new file
5. Report: `Persona updated: Lex Fridman — confidence 58% → 72% (+14%, 3 new positions extracted)`

---

## Main Council Flow

### Step 1: Understand Context
Scan `CLAUDE.md`, `.claude/rules/`, recent decisions, and strategy docs.
Identify domain (art, dev, education, business, etc.) to suggest relevant experts.

### Step 2: Ask Mode
Use `AskUserQuestion` with `type: select`:
- `strategic` — balanced analysis, find consensus and disagreements
- `brainstorm` — pure idea generation, no critique, each expert adds without shooting down
- `critic` — each expert finds flaws, devil's advocate for every assumption
- `realism` — grounded in constraints: budget, time, market; no wishful thinking

### Step 3: Compose Council

Present two pools for selection (use `AskUserQuestion` with `multiSelect: true`):

**Pool A — Available persona profiles** (read from `~/.h2t/config/personas/`):
Show as: `Lex Fridman (72%) — AI, robotics, philosophy`

**Pool B — Suggested for this domain** (generate based on context):
Mix of:
- Abstract roles: `Chief Risk Officer`, `Head of Distribution`, `Technical Architect`
- Real public figures relevant to the domain (use knowledge of who is a recognized expert):
  - For AI art: Refik Anadol, Holly Herndon, Lev Manovich
  - For edtech: Sal Khan, Peter Diamandis, Sugata Mitra
  - For dev/infra: Kelsey Hightower, Charity Majors, DHH
  - For strategy/VC: Marc Andreessen, Benedict Evans, Packy McCormick
  - Prioritize diverse viewpoints — include at least one contrarian per domain

Minimum 2 advisors. Recommended 4-6. Allow up to 10.

### Step 4: Gather Data
Collect strategy docs, metrics, recent decisions.
Prepare ONE identical data block for all experts — avoid vanity metrics.

### Step 5: Build Expert Prompts

For **persona profiles**: inject their `known_views`, `style`, and `communication patterns` into the prompt.
Add: `"Stay in character. Your confidence level is X% — be explicit about where you are uncertain."`

For **abstract roles**: use role-specific focus areas and personality (contrarian, pragmatic, etc.).

For **real people without profile**: use general knowledge, note `(no persona profile — based on public record only, confidence ~25%)`.

**Mode-specific instructions:**
- `brainstorm`: "Generate ideas freely. Do not critique others. Build on the premise, not against it."
- `critic`: "Your job is to find what's wrong. Challenge every assumption. Be specific, not vague."
- `realism`: "Ground every suggestion in real constraints. If budget/time/market doesn't support it, say so explicitly."
- `strategic`: default balanced analysis.

### Step 6: Launch All Advisors
**MUST use Task tool** with `subagent_type: 'general-purpose'` and `model: 'opus'` in a single message.
Never use bash or shell scripts. Never coordinate between advisors.

### Step 7: Synthesize
Create synthesis document:
- Consensus points
- Key disagreements (with who holds which position)
- Actionable decisions
- Confidence-weighted recommendations (higher-confidence personas carry more interpretive weight)

Save to `docs/council-YYYY-MM-DD.md` (or vault equivalent).
Report persona confidence scores used in this session.

---

## Persona Update After Session

After each council session, offer:
> "Update persona profiles based on how advisors performed? This refines their future accuracy."

If user confirms — note any corrections to known views or style observed during the session.

---

## Critical Rules
- Isolation between advisors is mandatory — genuine diversity requires no coordination
- Always show confidence scores when using persona profiles
- Real people without profiles: always note low confidence (~25%) and knowledge cutoff
- Never invent specific quotes or positions not supported by sources
