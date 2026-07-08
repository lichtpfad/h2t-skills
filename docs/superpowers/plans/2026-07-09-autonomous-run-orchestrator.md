---
title: "Autonomous run orchestrator"
status: "draft"
date: "2026-07-09"
milestone: ""
---

# Autonomous run orchestrator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `h2t-core:autonomous-run` — a launcher+protocol skill that generates a
durable, self-contained runbook artifact for an autonomous plan-execution run, guards
its safety sections with a sealed validator, and carries the resume + decision protocols.

**Architecture:** A thin skill (`SKILL.md`) plus three deterministic Python scripts and a
token-substituted template. `new_runbook.py` renders `references/runbook-template.md`
(safety text + `<<TOKEN>>` fields) into `docs/superpowers/plans/<date>-<slug>-runbook.md`;
`validate_runbook.py` re-parses the produced file and fails loudly if any required section
or safety marker is missing (the sealed split); `runbook_state.py` parses checkbox state
for resume. The template holds the prose; the scripts are thin and fully testable.

**Tech Stack:** Python 3.11 stdlib only (no deps), `pytest`, Claude Code skill/markdown.

**Spec:** `docs/superpowers/specs/2026-07-09-autonomous-run-orchestrator.md` (codex-round-2 PASS).

---

## Pre-execution notes

- **Branch:** `feat/autonomous-run-orchestrator` (already cut from main `a26da62`, holds the spec).
- **venv:** `C:/dev/h2t-skills/.venv/Scripts/python` and `.../pytest` — do not activate.
- **Tests co-locate** with the scripts (mirrors `agent-profile/skills/.../scripts/test_*.py`).
  Run: `C:/dev/h2t-skills/.venv/Scripts/pytest plugins/h2t-core/skills/autonomous-run/scripts/ -v`
- **Imports:** modules and tests share one dir; use plain `import runbook_schema` (pytest
  `prepend` mode + script-dir-on-path make sibling imports resolve both as test and as CLI).
- **Autonomous-run discipline (dogfood):** codex review-gate after each milestone; council
  finish-gate at the end; e2e at M1 (§ Task 1.6); handoff last. Per `.claude/rules/autonomous-execution.md`.

## File Structure

**Create:**
- `plugins/h2t-core/skills/autonomous-run/scripts/runbook_schema.py` — shared section /
  safety-marker / pipeline constants (single source; validator can't drift from generator).
- `plugins/h2t-core/skills/autonomous-run/scripts/validate_runbook.py` — sealed validator.
- `plugins/h2t-core/skills/autonomous-run/scripts/new_runbook.py` — renderer (template → artifact).
- `plugins/h2t-core/skills/autonomous-run/scripts/runbook_state.py` — checkbox-state parser (resume).
- `plugins/h2t-core/skills/autonomous-run/scripts/test_validate_runbook.py`
- `plugins/h2t-core/skills/autonomous-run/scripts/test_new_runbook.py`
- `plugins/h2t-core/skills/autonomous-run/scripts/test_runbook_state.py`
- `plugins/h2t-core/skills/autonomous-run/references/runbook-template.md` — skeleton + `<<TOKEN>>`s.
- `plugins/h2t-core/skills/autonomous-run/references/decision-protocol.md` — allow-list + hard-stops.
- `plugins/h2t-core/skills/autonomous-run/references/gates.md` — codex/council gate defs.
- `plugins/h2t-core/skills/autonomous-run/SKILL.md` — trigger, launch/resume, hand-off.

**Modify:**
- `.claude/rules/autonomous-execution.md` — point at the skill's `references/` as canonical.

---

## Milestone M1 — generator + schema + sealed validator

### Task 1.1: schema constants (single source)

**Files:**
- Create: `plugins/h2t-core/skills/autonomous-run/scripts/runbook_schema.py`

- [ ] **Step 1: Write the module** (no test yet — pure constants consumed by 1.2/1.3)

```python
# plugins/h2t-core/skills/autonomous-run/scripts/runbook_schema.py
"""Single source of truth for the runbook artifact's structure. Both new_runbook
(generator) and validate_runbook (validator) import these, so the validator can never
drift from what the generator emits (mirrors docs-lint's FRONTMATTER_RULES pattern)."""
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

# Safety strings that MUST appear verbatim. Removing any is the exact failure the
# sealed validator exists to catch (the 4 hard-stops + the fail-safe handoff clause).
REQUIRED_SAFETY_MARKERS: list[str] = [
    "Irreversible / destructive",
    "Money / budget",
    "Scope / architecture change",
    "Gate not fixable in",
    "on a hard-stop or unresolvable blocker",
]

# Ordered pipeline; each renders as a checkbox row with the per-step contract.
PIPELINE_STEPS: list[str] = [
    "write-spec", "review-spec", "write-plan", "plan-gate",
    "subagent-driven-dev", "gates", "e2e", "PR", "handoff",
]

# Token fields the model fills at generation time.
RUN_FIELDS: list[str] = ["title", "today", "runbook_path", "branch", "spec_path",
                         "issue", "venv_test"]
```

- [ ] **Step 2: Commit**

```
git add plugins/h2t-core/skills/autonomous-run/scripts/runbook_schema.py
git commit -m "feat(autonomous-run): runbook schema constants (single source)"
```

### Task 1.2: sealed validator

**Files:**
- Create: `plugins/h2t-core/skills/autonomous-run/scripts/validate_runbook.py`
- Test: `plugins/h2t-core/skills/autonomous-run/scripts/test_validate_runbook.py`

- [ ] **Step 1: Write the failing test**

```python
# plugins/h2t-core/skills/autonomous-run/scripts/test_validate_runbook.py
import pytest
import runbook_schema as S
from validate_runbook import validate, RunbookInvalid

def _good_text() -> str:
    body = "\n\n".join(h + "\ncontent" for h in S.REQUIRED_SECTIONS)
    markers = "\n".join(S.REQUIRED_SAFETY_MARKERS)
    return body + "\n" + markers + "\n"

def test_valid_text_returns_empty_problem_list():
    assert validate(_good_text()) == []

def test_missing_section_is_reported():
    text = _good_text().replace("## Decision-protocol\ncontent", "")
    problems = validate(text)
    assert any("Decision-protocol" in p for p in problems)

def test_removed_hard_stop_is_reported():
    text = _good_text().replace("Money / budget", "")
    problems = validate(text)
    assert any("Money / budget" in p for p in problems)

def test_validate_or_raise_raises_on_missing():
    from validate_runbook import validate_or_raise
    with pytest.raises(RunbookInvalid):
        validate_or_raise(_good_text().replace("Scope / architecture change", ""))
```

- [ ] **Step 2: Run to verify fail**

Run: `C:/dev/h2t-skills/.venv/Scripts/pytest plugins/h2t-core/skills/autonomous-run/scripts/test_validate_runbook.py -v`
Expected: FAIL (module `validate_runbook` not found).

- [ ] **Step 3: Implement**

```python
# plugins/h2t-core/skills/autonomous-run/scripts/validate_runbook.py
"""Sealed post-generation validator. Re-parses a produced runbook artifact and reports
every missing required section or safety marker. Run after generation AND after any model
weaving, so weaving cannot silently drop safety text (spec § Architecture step 3)."""
from __future__ import annotations
import sys
import runbook_schema as S

class RunbookInvalid(Exception):
    pass

def validate(text: str) -> list[str]:
    """Return a list of human-readable problems; empty list == valid."""
    problems: list[str] = []
    for heading in S.REQUIRED_SECTIONS:
        if heading not in text:
            problems.append(f"missing required section: {heading}")
    for marker in S.REQUIRED_SAFETY_MARKERS:
        if marker not in text:
            problems.append(f"missing required safety marker: {marker!r}")
    return problems

def validate_or_raise(text: str) -> None:
    problems = validate(text)
    if problems:
        raise RunbookInvalid("; ".join(problems))

def _main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: validate_runbook.py <runbook.md>", file=sys.stderr)
        return 2
    text = open(argv[1], encoding="utf-8").read()
    problems = validate(text)
    if problems:
        for p in problems:
            print(f"INVALID: {p}", file=sys.stderr)
        return 1
    print("OK: runbook valid")
    return 0

if __name__ == "__main__":
    raise SystemExit(_main(sys.argv))
```

- [ ] **Step 4: Run to verify pass**

Run: `C:/dev/h2t-skills/.venv/Scripts/pytest plugins/h2t-core/skills/autonomous-run/scripts/test_validate_runbook.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```
git add plugins/h2t-core/skills/autonomous-run/scripts/validate_runbook.py plugins/h2t-core/skills/autonomous-run/scripts/test_validate_runbook.py
git commit -m "feat(autonomous-run): sealed runbook validator + tests"
```

### Task 1.3: runbook template

**Files:**
- Create: `plugins/h2t-core/skills/autonomous-run/references/runbook-template.md`

- [ ] **Step 1: Write the template** (token fields `<<NAME>>`; safety text verbatim so the
  validator passes). Section headings MUST match `REQUIRED_SECTIONS` exactly.

```markdown
# Autonomous run — <<title>>

> **Durable spine (autonomous run, <<today>>).** Survives context compaction / blocker.
> A fresh session resumes from HERE.
> **Resume:** `autonomous-run resume <<runbook_path>>`

## Durable-spine header

Authorized: autonomous delivery through handoff. **On a hard-stop or unresolvable blocker
→ run `h2t-core:handoff`** — NOT on a default-shaped decision (those are auto-resolved, see
Decision-protocol). Verify the branch before every commit.

## Where things are

- Branch: `<<branch>>`
- Spec: `<<spec_path>>`
- Issue: <<issue>>
- Tests: `<<venv_test>>`
- e2e applicability: <<e2e_state>>

## Pipeline steps

Each step carries the per-step contract (skill / input / done / failure / re-entry).

| # | step | skill | input | done-criterion | failure-path | re-entry |
|---|------|-------|-------|----------------|--------------|----------|
<<pipeline_rows>>

## Gates

- Codex review-gate after each milestone/checkpoint AND at the end (embedded content,
  read-only). GATE FAIL if any `[P1]`.
- Council finish-gate at the end (codex + >=2 Opus lenses) -> SOUND / blockers.
- pre-merge-check before PR.
- `N_gate_attempts` = 2. One attempt = one fix edit + one gate/test re-run.

## Decision-protocol

Auto-resolve ONLY allow-listed, reversible decisions (library/API call shape; formatting/
naming within conventions; test-fixture values; doc wording): research best-practice ->
pick -> append to Decision-log -> continue. Escalate everything else.

Hard-stops (stop -> eligible WIP-commit -> handoff; never auto-resolve):
- Irreversible / destructive (delete/force-push, merge to main, external publish/send,
  deleting/modifying pre-existing untracked files).
- Money / budget (paid runs, token budget over limit, council/codex beyond cost-gate).
- Scope / architecture change (deviation from approved spec, new invariant, redefined goal).
- Gate not fixable in `N_gate_attempts`.

## Execution principles

Verify branch before every commit; `git mv`/`git rm` only; never delete/modify pre-existing
untracked files (creating this run's own artifacts is allowed). One command per Bash call.
Frequent small commits. Codex subagents one-at-a-time, never parallel.

## Blocker / fail-safe protocol

Record the blocker + what was tried -> eligible WIP-commit (stage only intentional files,
never `git add -A`, never commit a red suite as green, message `WIP:` + what was left) ->
`h2t-core:handoff`. Never force a broken merge or a false-green.

## Decision-log

- (append-only; auto-resolved defaults recorded here)
```

- [ ] **Step 2: Commit**

```
git add plugins/h2t-core/skills/autonomous-run/references/runbook-template.md
git commit -m "feat(autonomous-run): durable runbook template (safety text + tokens)"
```

### Task 1.4: generator renders template

**Files:**
- Create: `plugins/h2t-core/skills/autonomous-run/scripts/new_runbook.py`
- Test: `plugins/h2t-core/skills/autonomous-run/scripts/test_new_runbook.py`

- [ ] **Step 1: Write the failing test**

```python
# plugins/h2t-core/skills/autonomous-run/scripts/test_new_runbook.py
import runbook_schema as S
from validate_runbook import validate
from new_runbook import render, PIPELINE_CONTRACT

_FIELDS = dict(title="Demo", today="2026-07-09", runbook_path="docs/x-runbook.md",
               branch="feat/x", spec_path="docs/x-spec.md", issue="#1",
               venv_test="pytest tests/", e2e_state="N/A (no integration surface)")

def test_rendered_runbook_passes_validator():
    text = render(**_FIELDS)
    assert validate(text) == []

def test_all_pipeline_steps_present_as_rows():
    text = render(**_FIELDS)
    for step in S.PIPELINE_STEPS:
        assert f"| {step} |" in text

def test_tokens_are_substituted():
    text = render(**_FIELDS)
    assert "<<" not in text and ">>" not in text
    assert "feat/x" in text and "autonomous-run resume docs/x-runbook.md" in text

def test_every_step_has_a_contract_skill():
    # PIPELINE_CONTRACT must cover every step (no missing per-step contract)
    assert set(PIPELINE_CONTRACT) == set(S.PIPELINE_STEPS)
```

- [ ] **Step 2: Run to verify fail**

Run: `C:/dev/h2t-skills/.venv/Scripts/pytest plugins/h2t-core/skills/autonomous-run/scripts/test_new_runbook.py -v`
Expected: FAIL (module `new_runbook` not found).

- [ ] **Step 3: Implement**

```python
# plugins/h2t-core/skills/autonomous-run/scripts/new_runbook.py
"""Render the durable runbook artifact from references/runbook-template.md.

Token substitution uses `<<NAME>>` markers (NOT str.format) so literal braces in bash /
JSON inside the template are safe. The generator is thin; the template holds the safety
prose; validate_runbook is the guard (spec § Generation)."""
from __future__ import annotations
from pathlib import Path
import runbook_schema as S
from validate_runbook import validate_or_raise

_TEMPLATE = Path(__file__).resolve().parents[1] / "references" / "runbook-template.md"

# Per-step contract stamped by the generator (skill/done/failure/re-entry). `input` is
# filled by the model per run. Every step in S.PIPELINE_STEPS MUST have an entry.
PIPELINE_CONTRACT: dict[str, tuple[str, str, str, str]] = {
    "write-spec":          ("superpowers:brainstorming (spec tail)", "spec file exists + frontmatter", "escalate", "idempotent: overwrite spec"),
    "review-spec":         ("codex review (embedded)", "no [P1]", "fix P1 then re-run (<=N)", "idempotent: re-review"),
    "write-plan":          ("superpowers:writing-plans", "plan file exists", "escalate", "idempotent: overwrite plan"),
    "plan-gate":           ("codex review (embedded)", "no [P1]", "fix P1 then re-run (<=N)", "idempotent: re-review"),
    "subagent-driven-dev": ("superpowers:subagent-driven-development", "all tasks green", "per-task gate; escalate on repeated fail", "continue from first unchecked task"),
    "gates":               ("codex + pre-merge-check", "no [P1]; suite green", "fix then re-run (<=N)", "idempotent: re-run gate"),
    "e2e":                 ("real entrypoint run", "DONE / N/A / BLOCKED-DEFERRED", "BLOCKED->handoff; behavioral fail->fix", "idempotent: re-run"),
    "PR":                  ("superpowers:finishing-a-development-branch", "PR opened", "escalate", "continue: reuse branch"),
    "handoff":             ("h2t-core:handoff", "session record written", "n/a (terminal)", "idempotent: re-run handoff"),
}

def _rows() -> str:
    out = []
    for i, step in enumerate(S.PIPELINE_STEPS, 1):
        skill, done, fail, reentry = PIPELINE_CONTRACT[step]
        out.append(f"| {i} | {step} | {skill} | `<fill>` | {done} | {fail} | {reentry} |")
    return "\n".join(out)

def render(*, title: str, today: str, runbook_path: str, branch: str, spec_path: str,
           issue: str, venv_test: str, e2e_state: str) -> str:
    text = _TEMPLATE.read_text(encoding="utf-8")
    subs = {"title": title, "today": today, "runbook_path": runbook_path,
            "branch": branch, "spec_path": spec_path, "issue": issue,
            "venv_test": venv_test, "e2e_state": e2e_state,
            "pipeline_rows": _rows()}
    for k, v in subs.items():
        text = text.replace(f"<<{k}>>", v)
    validate_or_raise(text)  # sealed: never emit an invalid runbook
    return text

def create_runbook(dest: str, **fields: str) -> Path:
    text = render(**fields)
    p = Path(dest)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p
```

- [ ] **Step 4: Run to verify pass**

Run: `C:/dev/h2t-skills/.venv/Scripts/pytest plugins/h2t-core/skills/autonomous-run/scripts/test_new_runbook.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```
git add plugins/h2t-core/skills/autonomous-run/scripts/new_runbook.py plugins/h2t-core/skills/autonomous-run/scripts/test_new_runbook.py
git commit -m "feat(autonomous-run): runbook generator (token render + sealed on emit)"
```

### Task 1.5: sealed-split regression (validator rejects tampered generator output)

**Files:**
- Modify: `plugins/h2t-core/skills/autonomous-run/scripts/test_new_runbook.py`

- [ ] **Step 1: Add the failing test** (proves weaving cannot drop safety text)

```python
def test_tampered_output_is_rejected():
    import pytest
    from validate_runbook import validate_or_raise, RunbookInvalid
    from new_runbook import render
    text = render(**_FIELDS)
    tampered = text.replace("Irreversible / destructive", "")  # simulate model weaving damage
    with pytest.raises(RunbookInvalid):
        validate_or_raise(tampered)
```

- [ ] **Step 2: Run** → PASS (validator already rejects; this locks the invariant).

Run: `C:/dev/h2t-skills/.venv/Scripts/pytest plugins/h2t-core/skills/autonomous-run/scripts/test_new_runbook.py::test_tampered_output_is_rejected -v`

- [ ] **Step 3: Commit**

```
git add plugins/h2t-core/skills/autonomous-run/scripts/test_new_runbook.py
git commit -m "test(autonomous-run): sealed-split regression (tampered output rejected)"
```

### Task 1.6: 🎯 E2E — generate from the real spec, artifact passes the validator

**Files:**
- Modify: `plugins/h2t-core/skills/autonomous-run/scripts/test_new_runbook.py`

- [ ] **Step 1: Write the e2e test** (the M1 real end-to-end path — spec § Conditional e2e)

```python
def test_e2e_generate_real_runbook_and_validate(tmp_path):
    from new_runbook import create_runbook
    from validate_runbook import validate
    out = tmp_path / "2026-07-09-autonomous-run-orchestrator-runbook.md"
    p = create_runbook(
        str(out), title="Autonomous run orchestrator", today="2026-07-09",
        runbook_path=str(out), branch="feat/autonomous-run-orchestrator",
        spec_path="docs/superpowers/specs/2026-07-09-autonomous-run-orchestrator.md",
        issue="(none)", venv_test="pytest plugins/h2t-core/skills/autonomous-run/scripts/",
        e2e_state="applies (generate->validate)")
    assert p.exists()
    text = p.read_text(encoding="utf-8")
    assert validate(text) == []          # real artifact is valid end-to-end
    assert "autonomous-run resume" in text
```

- [ ] **Step 2: Run** → PASS.

Run: `C:/dev/h2t-skills/.venv/Scripts/pytest plugins/h2t-core/skills/autonomous-run/scripts/test_new_runbook.py::test_e2e_generate_real_runbook_and_validate -v`

- [ ] **Step 3: Commit**

```
git add plugins/h2t-core/skills/autonomous-run/scripts/test_new_runbook.py
git commit -m "test(autonomous-run): e2e generate-then-validate a real runbook (M1)"
```

### 🚦 GATE M1 — codex review of the M1 diff
- [ ] Run codex review (embedded diff, read-only, `high`) on the M1 scripts + template +
  tests. Focus: validator completeness (can a tampered artifact slip through?), token
  substitution safety, per-step contract coverage. Fix any `[P1]` (<= `N_gate_attempts`).
- [ ] Full script suite green:
  `C:/dev/h2t-skills/.venv/Scripts/pytest plugins/h2t-core/skills/autonomous-run/scripts/ -v`

---

## Milestone M2 — resume + two-track state

### Task 2.1: checkbox-state parser

**Files:**
- Create: `plugins/h2t-core/skills/autonomous-run/scripts/runbook_state.py`
- Test: `plugins/h2t-core/skills/autonomous-run/scripts/test_runbook_state.py`

- [ ] **Step 1: Write the failing test**

```python
# plugins/h2t-core/skills/autonomous-run/scripts/test_runbook_state.py
from runbook_state import parse_steps, unchecked_steps

_MD = """\
## Pipeline steps
- [x] write-spec
- [x] review-spec
- [ ] write-plan
- [ ] plan-gate
"""

def test_parse_steps_returns_checked_flags():
    steps = parse_steps(_MD)
    assert steps == [("write-spec", True), ("review-spec", True),
                     ("write-plan", False), ("plan-gate", False)]

def test_unchecked_steps_for_resume():
    assert unchecked_steps(_MD) == ["write-plan", "plan-gate"]

def test_all_checked_returns_empty():
    done = _MD.replace("- [ ]", "- [x]")
    assert unchecked_steps(done) == []
```

- [ ] **Step 2: Run to verify fail** → FAIL (module missing).

- [ ] **Step 3: Implement**

```python
# plugins/h2t-core/skills/autonomous-run/scripts/runbook_state.py
"""Parse pipeline checkbox state from a runbook artifact so a fresh session can rebuild
the TodoWrite mirror from the durable source of truth (spec § Two-track state model)."""
from __future__ import annotations
import re

_STEP = re.compile(r"^- \[([ xX])\]\s+(.+?)\s*$", re.MULTILINE)

def parse_steps(text: str) -> list[tuple[str, bool]]:
    return [(m.group(2), m.group(1).lower() == "x") for m in _STEP.finditer(text)]

def unchecked_steps(text: str) -> list[str]:
    return [name for name, checked in parse_steps(text) if not checked]
```

- [ ] **Step 4: Run to verify pass** → PASS (3 tests).

- [ ] **Step 5: Commit**

```
git add plugins/h2t-core/skills/autonomous-run/scripts/runbook_state.py plugins/h2t-core/skills/autonomous-run/scripts/test_runbook_state.py
git commit -m "feat(autonomous-run): runbook checkbox-state parser (resume rebuild)"
```

### Task 2.2: SKILL.md resume + two-track procedure (prose)

**Files:**
- Create (partial): `plugins/h2t-core/skills/autonomous-run/SKILL.md` (resume section only; launch body in M3)

- [ ] **Step 1: Write the resume + state section** with the exact ordering rule from the spec:

```markdown
## Resume & state (two-track)

On `autonomous-run resume <path>`:
1. Read the artifact (durable source of truth).
2. `unchecked_steps()` -> rebuild the TodoWrite mirror from the unchecked steps only;
   discard any stale in-session TodoWrite.
3. A step whose done-criterion is already satisfied (PR exists, tests green) is checked
   without re-running.
4. Continue from the first unchecked step, following its per-step contract row.

Update ordering (one-way): on step completion, write the artifact checkbox FIRST, then
mark the TodoWrite item. Never the reverse.
```

- [ ] **Step 2: Commit**

```
git add plugins/h2t-core/skills/autonomous-run/SKILL.md
git commit -m "docs(autonomous-run): SKILL resume + two-track ordering section"
```

### 🚦 GATE M2 — codex review of the M2 diff
- [ ] Codex review (embedded) on `runbook_state.py` + SKILL resume section. Focus: parser
  robustness (nested lists, non-step checkboxes), ordering-rule correctness. Fix `[P1]`.
- [ ] Suite green: `C:/dev/h2t-skills/.venv/Scripts/pytest plugins/h2t-core/skills/autonomous-run/scripts/ -v`

---

## Milestone M3 — orchestration + protocol wiring

### Task 3.1: decision-protocol + gates references

**Files:**
- Create: `plugins/h2t-core/skills/autonomous-run/references/decision-protocol.md`
- Create: `plugins/h2t-core/skills/autonomous-run/references/gates.md`

- [ ] **Step 1: Write `decision-protocol.md`** — the allow-list + hard-stops, lifted from
  spec § Decision-protocol (allow-list categories; the 4 hard-stops; escalate-everything-else;
  `N_gate_attempts` = 2). This is the portable copy the generator stamps into artifacts.
- [ ] **Step 2: Write `gates.md`** — codex review-gate (embedded-content command shape,
  read-only, `[P1]` = FAIL) + council finish-gate (codex + >=2 Opus lenses -> SOUND/blockers)
  + pre-merge-check, lifted from spec § Gates and the crypto `execution-protocols.md`.
- [ ] **Step 3: Commit**

```
git add plugins/h2t-core/skills/autonomous-run/references/decision-protocol.md plugins/h2t-core/skills/autonomous-run/references/gates.md
git commit -m "docs(autonomous-run): decision-protocol + gates references"
```

### Task 3.2: SKILL.md launch body + frontmatter

**Files:**
- Modify: `plugins/h2t-core/skills/autonomous-run/SKILL.md`

- [ ] **Step 1: Add frontmatter + launch procedure.** Frontmatter `name: autonomous-run`,
  `description:` triggering on "работай сам / автономно / overnight / выполни план сам /
  autonomous run" (post-brainstorm). Body = the § Architecture launch flow (preconditions ->
  generate via `new_runbook.py` -> sealed validate -> materialize TodoWrite -> hand off per
  per-step contract), plus the e2e applicability classification (applies / N/A / BLOCKED-DEFERRED)
  and pointers to `references/decision-protocol.md` and `references/gates.md`.
- [ ] **Step 2: Verify skill loads** — `pwsh scripts/claude-dev.ps1` dev session lists
  `h2t-core:autonomous-run` (or inspect plugin manifest discovery). Expected: skill present.
- [ ] **Step 3: Commit**

```
git add plugins/h2t-core/skills/autonomous-run/SKILL.md
git commit -m "feat(autonomous-run): SKILL launch body + trigger frontmatter"
```

### Task 3.3: reconcile the project rule

**Files:**
- Modify: `.claude/rules/autonomous-execution.md`

- [ ] **Step 1: Expand the thin rule** to reference the skill's `references/` as the
  canonical protocol source (gates + decision-protocol), keeping the existing 4-point
  discipline as a summary that now points at `plugins/h2t-core/skills/autonomous-run/references/`.
- [ ] **Step 2: Commit**

```
git add .claude/rules/autonomous-execution.md
git commit -m "docs(autonomous-run): point autonomous-execution rule at skill references"
```

> **Out of scope (follow-up issue):** `crypto-regime-spike-*/.claude/rules/execution-protocols.md`
> → thin pointer. That lives in a different repo; note it for a separate PR, do not edit here.

### 🚦 GATE M3 + council finish-gate
- [ ] Codex review (embedded) on the full M3 diff (references + SKILL + rule). Fix `[P1]`.
- [ ] **Council finish-gate** (spec § dogfood / `.claude/rules/autonomous-execution.md`):
  codex (correctness) + 2 Opus lenses (lens A: sealed-safety + validator soundness; lens B:
  resume/two-track invariant + North-Star alignment) -> SOUND / blockers. Artifact ->
  `docs/reports/2026-07-09-council-validation-autonomous-run.md`.
- [ ] Full suite green: `C:/dev/h2t-skills/.venv/Scripts/pytest plugins/h2t-core/skills/autonomous-run/scripts/ -v`
  and repo tests unaffected: `C:/dev/h2t-skills/.venv/Scripts/pytest tests/ -q`.

### Task 3.4: finish branch + handoff
- [ ] `superpowers:finishing-a-development-branch` — open PR for `feat/autonomous-run-orchestrator`
  (base main). Do NOT auto-merge; leave open for operator review.
- [ ] `h2t-core:handoff` (terminal step — always, success or blocker).

---

## Self-Review (completed by plan author)

- **Spec coverage:** § Architecture (launch/sealed-validate) → 1.4 + 3.2; § Resume trigger →
  2.1/2.2 + 3.2; § Per-step execution contract → 1.4 (`PIPELINE_CONTRACT`); § Conditional e2e →
  1.6 + 3.2 (state classification); § Components → all Create tasks; § Runbook schema → 1.1/1.3;
  § Two-track state model → 2.1/2.2; § Decision-protocol → 3.1 + template; § Testing → 1.2/1.4/1.5;
  § Implementation phasing → M1/M2/M3. All covered.
- **Placeholder scan:** no TBD/TODO in code steps; markdown-content tasks (1.3/2.2/3.1/3.2/3.3)
  specify exact headings + required safety markers so the validator gate is objective.
- **Type consistency:** `render(**fields)`, `create_runbook`, `validate`/`validate_or_raise`/
  `RunbookInvalid`, `parse_steps`/`unchecked_steps`, `PIPELINE_CONTRACT`, `REQUIRED_SECTIONS`/
  `REQUIRED_SAFETY_MARKERS`/`PIPELINE_STEPS` used consistently across tasks.
- **Gates present:** codex-gate after M1/M2/M3; council finish-gate at end; e2e at M1 (1.6);
  handoff terminal (3.4). Matches the autonomous-run discipline being dogfooded.
