"""Single source of truth for the runbook artifact's structure. new_runbook (generator),
validate_runbook (validator), and runbook_state (resume) all import these, so they can
never drift (mirrors docs-lint's FRONTMATTER_RULES pattern)."""
from __future__ import annotations

# Exact H2 headings that MUST appear in a generated runbook.
REQUIRED_SECTIONS: list[str] = [
    "## Durable-spine header",
    "## Where things are",
    "## Pipeline steps",
    "## Gates",
    "## Decision-protocol",
    "## Execution principles",
    "## Blocker / fail-safe protocol",
    "## Decision-log",
]

# Safety marker -> the section it MUST appear inside. The validator checks presence
# WITHIN the mapped section (not anywhere), so a gutted section that re-appends markers
# elsewhere fails (codex-plan-gate-1 P1). Marker substrings are chosen case-stable
# (no leading-capital ambiguity).
MARKER_SECTION: dict[str, str] = {
    "hard-stop or unresolvable blocker": "## Durable-spine header",
    "Irreversible / destructive": "## Decision-protocol",
    "Money / budget": "## Decision-protocol",
    "Scope / architecture change": "## Decision-protocol",
    "Gate not fixable in": "## Decision-protocol",
    # cover the remaining safety sections so gutting them is caught too (codex-gate-M1 P1)
    "pre-merge-check": "## Gates",
    "N_gate_attempts": "## Gates",
    "One command per Bash call": "## Execution principles",
    "force a broken merge": "## Blocker / fail-safe protocol",
}

# Ordered pipeline; each renders as a CHECKBOX list item with the per-step contract.
PIPELINE_STEPS: list[str] = [
    "write-spec", "review-spec", "write-plan", "plan-gate",
    "subagent-driven-dev", "gates", "e2e", "PR", "handoff",
]

# Allowed e2e applicability states (spec § Conditional e2e).
E2E_STATES: list[str] = ["applies", "N/A", "BLOCKED-DEFERRED"]

# Token fields the model fills at generation time (matches new_runbook.render kwargs;
# `pipeline_rows` is generated, not a run field).
RUN_FIELDS: list[str] = ["title", "today", "runbook_path", "branch", "spec_path",
                         "issue", "venv_test", "e2e_state"]
