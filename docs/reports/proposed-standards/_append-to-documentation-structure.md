# Proposed additions to `C:/dev/docs/standards/documentation-structure.md`

## Answer a pre-write checklist before creating or moving any file
- **Evidence:** lineages POS, rejuve, crypto-regime-spike · recurrence 3 · domain-indep high
- **Source:** `C:/dev/POS/.claude/rules/governance.md`, `C:/work/rejuve/.claude/rules/repo-hygiene.md`, `C:/dev/crypto-regime-spike/.claude/rules/project-workflow.md`
- **What to add:** Before creating or moving a file, answer: (1) What artifact class is this? (source / generated / ephemeral) (2) Does a canonical location already exist (SSOT boundary check)? (3) Does the operator need to approve this write? Generated output must never be placed where source files live. Only after all three questions are answered should the file operation proceed.

## Enforce a document status lifecycle synced between frontmatter and the GitHub issue
- **Evidence:** lineages rejuve · recurrence 1 · domain-indep high
- **Source:** `C:/work/rejuve/.claude/rules/status-lifecycle.md`
- **What to add:** Every formal document (spec, plan, ADR) must carry a `status` field in its frontmatter (`draft` → `reviewed` → `approved` → `deprecated`/`superseded`). The linked GitHub issue is the source of truth for status transitions; the frontmatter must be kept in sync. Status may not advance without the gate prescribed for that transition (e.g., approved requires operator sign-off).
