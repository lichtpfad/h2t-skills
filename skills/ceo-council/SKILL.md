---
name: ceo-council
description: "Independent strategic analysis via a council of AI advisors. Use when facing major decisions, evaluating strategies, or needing devil's advocate analysis. Triggers: 'ceo council', 'strategic analysis', 'council', 'стратегический анализ'."
compatibility: "Claude Code"
metadata:
  author: lichtpfad
  version: 1.0.0
---

# CEO Council — Independent Strategic Analysis

**Purpose:** Launch isolated C-level experts to analyze projects from diverse perspectives, reducing blind spots through genuine disagreement.

## Key Workflow

**Step 1: Understand Context**
Scan `CLAUDE.md`, `.claude/rules/`, and file structure to tailor expert roles to the actual project domain.

**Step 2: Ask User First**
Use `AskUserQuestion` with `multiSelect: true` to present 4-6 role options. Minimum 2 experts required for productive debate.

**Step 3: Gather Identical Data**
Collect strategy docs, metrics, and recent decisions. Prepare ONE data block to feed all experts equally—avoid vanity metrics like star counts.

**Step 4: Create Expert Prompts**
Each expert receives the same data block but with role-specific focus areas and personality instructions (contrarian, pragmatic, etc.).

**Step 5: Launch All Experts**
"**MUST use the Task tool** with `subagent_type: 'general-purpose'` and `model: 'opus'`" in a single message for true parallelism. Never use bash or shell scripts.

**Step 6: Synthesize Results**
Create a synthesis document capturing consensus, disagreements, and actionable decisions. Save to `docs/council-[DATE].md`.

## Critical Rule
Isolation between experts produces genuine diversity—no coordination between them.
