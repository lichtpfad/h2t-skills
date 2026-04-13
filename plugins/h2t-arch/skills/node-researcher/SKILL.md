---
name: node-researcher
description: Deep researches a crypto-regime-orchestrator diagram node using Exa API. Produces research doc + draw.io annotation. Use when researching any L5-L10 node. Also triggers on: 'h2t-arch:node-researcher'.
trigger: "research node", "исследуй ноду", "/node-researcher", "изучи алгоритм", "research L7", "research L8", "research L9"
compatibility: "Claude Code"
metadata:
  author: lichtpfad
  version: 1.0.0
---

# Node Researcher — Deep Research Workflow

**Project:** crypto-regime-orchestrator
**Tool:** `scripts/research.py` (Exa API, exa-py)
**Output:** `docs/research/{category}/{node}.md` + draw.io annotation text

---

## When to Use This Skill

When the user asks to research a node from the architecture diagram (L5-L10):
- "исследуй L7_MANIP", "research manipulation detection", "изучи FORE"
- Before annotating a node in draw.io
- Before writing an ADR on algorithm choice

---

## Step 1 — Identify Node

Map the node to its category and research doc path:

| Layer | Nodes | Category path |
|-------|-------|--------------|
| L6 | FE, FS_Rb, FS_Wb | `docs/research/layers/l6-*.md` |
| L7 | REG, EVT, FORE, MANIP, TAIL, FSD, PRIM | `docs/research/models/` or `layers/` |
| L8 | G0, G1, G2, G3, SQP, SIGR, SIGW | `docs/research/layers/l8-*.md` |
| L9 | BANDIT, KILL, OM, PS, RM | `docs/research/models/` or `layers/` |
| L10 | BT, PASS, RECON | `docs/research/layers/l10-*.md` |

Check `docs/plans/research-execution-plan.md` for pre-defined research questions and Exa queries for this node.

---

## Step 2 — Decompose into Research Questions

Before searching, define 4-5 specific questions. Always include:
1. **What:** Core algorithm/mechanism — what does science say is the best approach?
2. **Why this vs alternatives:** Compare with 1-2 alternatives (e.g. LinUCB vs RL)
3. **Crypto-specific:** Does the approach hold for crypto (fat tails, 24/7, manipulation)?
4. **Implementation:** Feasibility in Python, available libraries, known pitfalls
5. **Freshness:** What do papers from 2023-2025 add?

---

## Step 3 — Parallel Exa Searches

**MUST dispatch 3-4 Agent searches in parallel** (one message, multiple Agent tool calls):

Each agent runs:
```bash
python3 ${PROJECT_ROOT}/scripts/research.py "<query>" --n 6 --type auto
# where PROJECT_ROOT = root of the target project being researched
```

Standard query set per node (adapt from research-execution-plan.md):
- **Query A:** Academic foundation — `"<algorithm> <problem> financial time series"`
- **Query B:** Crypto-specific — `"<algorithm> cryptocurrency perpetual futures"`
- **Query C:** Implementation — `"<algorithm> Python implementation comparison <library>"`
- **Query D:** Recent — `"<topic> 2024 2025 deep learning survey"`

For deep dive on a specific paper:
```bash
python3 scripts/research.py "<specific paper title or topic>" --n 1 --type deep --full
```

---

## Step 4 — Synthesize Results

Read all agent outputs. Produce a research doc with this structure:

```markdown
# {Node Name} — Research Notes

**Node:** {node_id} in draw.io
**Date:** {date}
**Questions answered:** {list}
**Papers reviewed:** {N}

---

## Algorithm Decision

**Chosen approach:** ...
**Why not alternatives:** ...

---

## Key Findings

### Finding 1 — {title}
...

### Finding 2 — {title}
...

---

## Implementation Notes

**Library:** ...
**Known pitfalls:** ...
**Crypto-specific adjustments:** ...

---

## Open Questions

- ...

---

## Sources

| # | Title | URL | Year |
|---|-------|-----|------|
| 1 | ... | ... | ... |
```

Save to: `docs/research/{category}/{node-name}.md`

---

## Step 5 — Produce Draw.io Annotation

After synthesizing, produce a 6-line annotation for the node. Format (strict):

```
Line 1: What: <what it does in 1 sentence>
Line 2: Algorithm: <core algorithm/method>
Line 3: Input: <key inputs>
Line 4: Output: <key outputs>
Line 5: Stack: <Python library / implementation>
Line 6: Key insight: <most important finding from research>
```

This text goes into draw.io as `ann_{node_id}` node tooltip + label.

---

## Step 6 — Update Checklist

Mark node as complete in `docs/plans/research-execution-plan.md`:
- Change `☐` → `✅` for Research Doc and Draw.io Ann columns

---

## Quality Bar

Research is **sufficient** when:
- ≥ 5 academic papers reviewed (not just titles — read highlights or full text)
- Algorithm choice is justified vs at least 1 alternative
- Crypto-specific validity confirmed or caveated
- Implementation feasibility confirmed (library exists, complexity estimated)
- At least 1 paper from 2023 or later

Research is **insufficient** if:
- Only found blog posts / non-peer-reviewed sources
- No comparison with alternatives
- No crypto-specific consideration
- All sources older than 2020

---

## Example Invocation

User: "исследуй L7_MANIP"

1. Read research-execution-plan.md → find pre-defined queries for L7_MANIP
2. Dispatch 4 parallel agents with Exa queries
3. Collect results, identify top 5 papers
4. Deep read 2 most relevant (--full)
5. Synthesize → `docs/research/models/manipulation-detection.md`
6. Produce annotation text for `ann_manip`
7. Mark ✅ in checklist

---

## Notes

- API key: `EXA_API_KEY` in project `.env` (gitignored)
- `--type deep` costs more credits — use for final confirmation, not broad search
- Always cross-reference with existing `docs/research/` to avoid duplicates
- If paper is behind paywall, try `--full` on arxiv preprint version
