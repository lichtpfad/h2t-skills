---
name: ceo-council
description: "Strategic council of AI advisors — real people or abstract roles, with persona profiles and confidence scores. Modes: strategic, brainstorm, critic, realism. Triggers: 'ceo council', 'council', 'стратегический анализ', 'совет', 'build-persona', 'council research'."
compatibility: "Claude Code"
metadata:
  author: lichtpfad
  version: 2.2.0
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

## Command: council research

When user says `council research <topic>`, `найди экспертов по <теме>`, `research experts`:

### Step 1: Web Search
Run **parallel** WebSearch queries:
- `"<topic> leading experts thinkers 2024 2025"`
- `"<topic> best practitioners interviews"`
- `"<topic> contrarian views critics"`
- `"<topic> emerging voices researchers"`

Goal: find 8-12 candidate names across different schools of thought.

### Step 2: Enrich Candidates
For each candidate (parallel WebFetch / WebSearch):
- Find their key positions on the topic
- Find available sources: interviews, articles, talks, podcasts
- Note their stance: mainstream / contrarian / practitioner / theorist

### Step 3: Rank and Present
Present candidates ranked by:
1. **Relevance** — depth of expertise on the topic
2. **Diversity** — different viewpoints represented
3. **Source availability** — how much material exists to build a persona

Output format:
```
Found 9 experts on "<topic>":

1. Kate Crawford (contrarian, AI critic) — 12 sources available
   Known for: algorithmic bias, power structures in AI, Atlas of AI
   → build persona?

2. Andrej Karpathy (practitioner, optimist) — 8 sources available
   Known for: LLM internals, scaling laws, practical AI education
   → build persona?

3. Gary Marcus (skeptic) — 6 sources available
   Known for: critiques of deep learning hype, neurosymbolic AI
   → build persona?
...
```

### Step 4: Offer Actions
After presenting the list, ask (multiSelect):
- Which experts to add to council immediately (without full persona)
- Which to build full persona profiles for (triggers `build-persona` flow)
- Whether to proceed to council session now or build personas first

### Step 5: Auto-enrich Selected Personas
For each expert selected for persona building:
1. WebFetch their most cited/relevant article or interview
2. Extract: key positions, communication style, notable quotes
3. Create or update `~/.h2t/config/personas/{slug}.md`
4. Set `confidence` based on source count and depth
5. Report: `Persona created: Kate Crawford — confidence 42% (3 sources)`

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

### Step 0: Choose Launch Mode and Scope

**First thing after invocation** — ask TWO questions with `AskUserQuestion`:

**Question 1 — Launch mode:**
- `quick` — minimal setup: topic + advisors → launch immediately (defaults to `strategic`)
- `guided` — step-by-step: mode → scope → research → compose → data review → launch

**Question 2 — Scope** (CRITICAL — determines what goes into data block):
- `personal` — advice is for the user themselves; inject user profile from `~/.h2t/config/about-me/` if it exists (psychology, thinking style, ADHD patterns, working context). Advisors adapt how they communicate, not just what they advise.
- `work/client` — advice is for a specific project or client; inject project context only, NOT user personal profile
- `generic` — universal question not tied to anyone; no personal or project context injected

**If scope is ambiguous from the request, always ask. Do not assume.**

Examples:
- "как мне выстроить систему" → probably personal, confirm
- "как построить систему для художника" → generic or work/client, confirm
- "помоги с маркетингом для проекта X" → work/client, confirm

**Quick mode** skips mode selection (defaults to `strategic`) but still asks scope.
**Guided mode** runs all steps below with explicit confirmation at each stage.

---

### Step 1: Understand Context
Scan `CLAUDE.md`, `.claude/rules/`, recent decisions, and strategy docs.
Identify domain (art, dev, education, business, etc.) to suggest relevant experts.

### Step 2: Ask Mode *(guided only)*
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

**Option: Research mode**
If the topic is niche or user wants to discover new experts — offer:
> "Run `council research` to find and enrich experts on this topic before composing the council?"
This triggers the `council research` flow, then returns to council composition with enriched candidates.

### Step 4: Gather Data

Prepare ONE identical data block for all experts — avoid vanity metrics.

**What goes into the data block depends on scope:**

| Scope | Data block contents |
|-------|-------------------|
| `personal` | Topic + user profile from `~/.h2t/config/about-me/` (psychology, ADHD, thinking style, working context) + project context if relevant |
| `work/client` | Topic + project/client context only. No user personal profile. |
| `generic` | Topic only. No user profile, no specific project. |

**User profile location:** `~/.h2t/config/about-me/core.md` (and `psychology.md` for deeper profile).
If these files don't exist, skip personal profile — do not make assumptions about the user.

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
