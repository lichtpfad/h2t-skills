"""Parse pipeline checkbox state so a fresh session rebuilds the TodoWrite mirror from the
durable source of truth (spec § Two-track state model). Scoped to the `## Pipeline steps`
section and filtered to known step names, so gate checklists and decision-log bullets never
leak into resume state (codex-plan-gate-1 P1)."""
from __future__ import annotations
import re
import runbook_schema as S
from validate_runbook import split_sections

_STEP = re.compile(r"^- \[([ xX])\]\s+\*\*(?P<name>[^*]+)\*\*", re.MULTILINE)


def parse_steps(text: str) -> list[tuple[str, bool]]:
    # reuse the validator's H2 splitter so the boundary is anchored to a real
    # `## Pipeline steps` heading, not a stray substring (codex-plan-gate-2 P2)
    block = split_sections(text).get("## Pipeline steps", "")
    out: list[tuple[str, bool]] = []
    for m in _STEP.finditer(block):
        name = m.group("name").strip()
        if name in S.PIPELINE_STEPS:      # ignore stray checkboxes
            out.append((name, m.group(1).lower() == "x"))
    return out


def unchecked_steps(text: str) -> list[str]:
    return [name for name, checked in parse_steps(text) if not checked]
