---
name: h2t-arch:diagram-node
description: Documents architecture diagram nodes — researching APIs, ML algorithms, or internal processes to produce a 6-line draw.io annotation and a research doc. Triggers on: "document node", "annotate [node name]", "research [API/algorithm] for diagram", TYPE_SOURCE/TYPE_ML/TYPE_PROCESS/TYPE_GATE/TYPE_CONTRACT/TYPE_SCHEMA/TYPE_PIPELINE tasks., 'h2t-arch:diagram-node'
compatibility: "Claude Code"
metadata:
  author: lichtpfad
  version: 1.0.0
---

# Diagram Node Documenter

Produces a diagram annotation (≤6 lines) + research doc for one architecture node.
Does NOT write to draw.io — returns text for the orchestrator to place.

## Pipeline (5 steps)

```
CLASSIFY → RESEARCH (subagent) → EXTRACT → DRAFT → VALIDATE
```

### Step 1 — CLASSIFY
Determine node TYPE from the table below. If unclear: read the node's spec file or diagram tooltip.

### Step 2 — RESEARCH
**Always use a Haiku subagent.** Main context fills up fast — delegate all reading/searching.

| TYPE | Subagent task |
|---|---|
| TYPE_SOURCE | Read `docs/research/sources/[api].md` (if exists, skip re-research) + `datascience/src/sources/[api]/` + `configs/sources/[api].yaml` |
| TYPE_ML | WebSearch: "[algorithm] market regime detection academic" → validate approach |
| TYPE_PROCESS | Read `docs/specs/L*.md` + relevant code |
| TYPE_GATE | Read `docs/adr/` + `configs/gate_params.yaml` |
| TYPE_SCHEMA | Read `docs/schema/sources/[source].md` (built from TYPE_SOURCE research) |
| TYPE_CONTRACT | Read `src/models/*.py` (Pydantic models) + `docs/CONVENTIONS.md` |
| TYPE_STORAGE | Read `docs/DB_SCHEMA.md` + relevant ADR |
| TYPE_PIPELINE | Read spec + code → identify sub-modules |

**Subagent prompt template:**
```
Research [NODE NAME] ([TYPE]).
Read: [specific files / search queries]
Return ONLY a structured table: [field] | [value] | [notes]
Do NOT write files, do NOT edit code.
```

### Step 3 — EXTRACT
From subagent output extract:
- Key metrics / endpoints / algorithm params
- Constraints / limitations / known risks
- Input → Output data flow

Save full findings to the correct subfolder (mandatory deliverable):
- TYPE_SOURCE → **`docs/research/sources/[api-slug].md`**
- TYPE_ML     → **`docs/research/models/[model-name].md`**
- TYPE_PROCESS / TYPE_GATE / TYPE_SCHEMA / TYPE_CONTRACT / TYPE_PIPELINE → **`docs/research/[topic].md`**

### Step 4 — DRAFT
Fill the TYPE_* template (see node-types.md). Hard limit: **≤6 lines**, HTML-formatted.

```html
<b>[Node Name]</b><br/>
[line 2]<br/>
[line 3]<br/>
[line 4]<br/>
[line 5]<br/>
[line 6 — or ⚠️ risk / → Page N reference]
```

For complex nodes: line 6 = `→ Page N: [detail page name]`

### Step 5 — VALIDATE
Check the diagram for this node's neighbors:
- Does declared Input match what upstream node outputs?
- Does declared Output match what downstream node expects?
- If mismatch → flag it, don't silently fix

## Output (return to orchestrator)

```
node_id:        [e.g. L7_REG]
parent_id:      [e.g. L7]
annotation_html: <b>...</b><br/>...<br/>...
research_doc:   docs/research/[topic].md  ← created by this skill
width:          170–220  (use 200 for TYPE_ML, 170 for simple types)
height:         80–120
```

Orchestrator then runs: `scripts/add_annotation.py` logic + git commit.

## Dependency Order (TYPE_SCHEMA blocked by TYPE_SOURCE)

```
TYPE_SOURCE (all L1 APIs) → TYPE_SCHEMA → TYPE_PROCESS → TYPE_CONTRACT
TYPE_GATE and TYPE_CONTRACT can run in parallel any time
TYPE_ML: independent, but requires L6 feature research first
```

Do not document a TYPE_SCHEMA node until the source API is fully researched.

## Common Mistakes

| Mistake | Fix |
|---|---|
| Researching in main context (not subagent) | Always delegate RESEARCH to Haiku subagent |
| Annotation > 6 lines | Cut ruthlessly — move details to research doc |
| Skipping `docs/research/[topic].md` | This is mandatory — orchestrator needs it for GitHub issue |
| Fabricating API plan/credits | Only use data from actual config files or account docs |
| Documenting TYPE_SCHEMA before TYPE_SOURCE | Blocked dependency — do SOURCE first |
| Writing annotation without VALIDATE step | Mismatched input/output propagates silently |

## Reference

Node type templates → see `node-types.md` in this directory.
Project context → `docs/plans/2026-03-09-diagram-documentation-pipeline.md`
Validated examples → `docs/research/sources/cmc.md` (TYPE_SOURCE), `docs/research/models/hmm-classifier.md` (TYPE_ML)
