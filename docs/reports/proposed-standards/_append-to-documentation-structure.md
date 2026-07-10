# Proposed additions to `C:/dev/docs/standards/documentation-structure.md`

Harvested practices that belong in the existing standard rather than a new one.

## Pre-write artifact checklist: answer class/path/approval questions before creating or moving any file

- **Evidence:** lineages POS, rejuve, crypto-regime-spike · recurrence 3 · domain-indep high
- **Source:** `C:/dev/POS/.claude/rules/governance.md`, `C:/work/rejuve/.claude/rules/repo-hygiene.md`, `C:/dev/crypto-regime-spike/.claude/rules/project-workflow.md`
- **What to add:** Before creating or moving any file, answer: (1) What artifact class is this — source, generated output, or ephemeral? (2) Does the destination path conform to the SSOT boundary for that class? (3) Does a human need to approve this path or name? Generated output must never masquerade as a source file. SSOT boundaries must be enforced preventively, not detected after the fact.

## Document status lifecycle: draft → reviewed → approved → deprecated/superseded, tracked in frontmatter and GitHub issue

- **Evidence:** lineages rejuve · recurrence 1 · domain-indep high
- **Source:** `C:/work/rejuve/.claude/rules/status-lifecycle.md`
- **What to add:** Every formal document (spec, plan, ADR, report) must carry a `status:` field in its frontmatter. Valid states are: `draft`, `reviewed`, `approved`, `deprecated`, `superseded`. The GitHub issue linked to the document is the source of truth for status; frontmatter must be kept in sync. Status transitions require a reviewer sign-off — frontmatter cannot be advanced unilaterally by the agent.
