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
its safety sections with a sealed section-scoped validator, and carries the resume +
decision protocols.

**Architecture:** A thin skill (`SKILL.md`) plus four deterministic Python scripts and a
token-substituted template. `new_runbook.py` renders `references/runbook-template.md`
(safety prose + `<<TOKEN>>` fields) into `docs/superpowers/plans/<date>-<slug>-runbook.md`;
`validate_runbook.py` splits the produced file into H2 sections and fails loudly if any
required section is missing, any safety marker is absent **from its own section**, or an
unresolved `<<TOKEN>>` remains; `runbook_state.py` parses pipeline **checkbox** state
(scoped to the `## Pipeline steps` section and filtered to known step names) for resume.

**Tech Stack:** Python 3.11 stdlib only (no deps), `pytest`, Claude Code skill/markdown.

**Spec:** `docs/superpowers/specs/2026-07-09-autonomous-run-orchestrator.md` (codex-round-2 PASS).

---

## Pre-execution notes

- **Branch:** `feat/autonomous-run-orchestrator` (already cut from main `a26da62`; holds spec + this plan).
- **venv:** `C:/dev/h2t-skills/.venv/Scripts/python` and `.../pytest` — do not activate.
- **Tests co-locate** with the scripts (mirrors `agent-profile/skills/.../scripts/test_*.py`).
  Run: `C:/dev/h2t-skills/.venv/Scripts/pytest plugins/h2t-core/skills/autonomous-run/scripts/ -v`
  **CI wiring is Task 1.7** — do not assume `pytest tests/` collects them.
- **Imports:** modules and tests share one dir; use plain `import runbook_schema` (pytest
  `prepend` mode + script-dir-on-path make sibling imports resolve both as test and as CLI).
- **Format invariant (codex-plan-gate-1 P1):** pipeline steps in the artifact are **checkbox
  list items** (`- [ ] **<step>** — ...`), NOT table rows. The generator, the template, and
  `runbook_state` MUST agree on this. `runbook_state` scopes to the `## Pipeline steps`
  section and only counts names in `S.PIPELINE_STEPS` (gate/decision-log checkboxes ignored).
- **Autonomous-run discipline (dogfood):** codex review-gate after each milestone; council
  finish-gate at the end; e2e at M1 (§ Task 1.6); handoff last. Per `.claude/rules/autonomous-execution.md`.

## File Structure

**Create:**
- `plugins/h2t-core/skills/autonomous-run/scripts/runbook_schema.py` — shared constants.
- `plugins/h2t-core/skills/autonomous-run/scripts/validate_runbook.py` — sealed section-scoped validator.
- `plugins/h2t-core/skills/autonomous-run/scripts/new_runbook.py` — renderer (template → artifact).
- `plugins/h2t-core/skills/autonomous-run/scripts/runbook_state.py` — pipeline checkbox parser (resume).
- `plugins/h2t-core/skills/autonomous-run/scripts/test_validate_runbook.py`
- `plugins/h2t-core/skills/autonomous-run/scripts/test_new_runbook.py`
- `plugins/h2t-core/skills/autonomous-run/scripts/test_runbook_state.py`
- `plugins/h2t-core/skills/autonomous-run/scripts/test_references.py`
- `plugins/h2t-core/skills/autonomous-run/references/runbook-template.md` — skeleton + `<<TOKEN>>`s.
- `plugins/h2t-core/skills/autonomous-run/references/decision-protocol.md` — allow-list + hard-stops.
- `plugins/h2t-core/skills/autonomous-run/references/gates.md` — codex/council gate defs.
- `plugins/h2t-core/skills/autonomous-run/SKILL.md` — trigger, launch/resume, hand-off.

**Modify:**
- `pyproject.toml` — add the skill scripts dir to `[tool.pytest.ini_options] testpaths` (Task 1.7).
- `.claude/rules/autonomous-execution.md` — point at the skill's `references/` as canonical.

---

## Milestone M1 — generator + schema + sealed validator

### Task 1.1: schema constants (single source)

**Files:**
- Create: `plugins/h2t-core/skills/autonomous-run/scripts/runbook_schema.py`

- [ ] **Step 1: Write the module**

```python
# plugins/h2t-core/skills/autonomous-run/scripts/runbook_schema.py
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
```

- [ ] **Step 2: Commit**

```
git add plugins/h2t-core/skills/autonomous-run/scripts/runbook_schema.py
git commit -m "feat(autonomous-run): runbook schema constants (single source)"
```

### Task 1.2: sealed section-scoped validator

**Files:**
- Create: `plugins/h2t-core/skills/autonomous-run/scripts/validate_runbook.py`
- Test: `plugins/h2t-core/skills/autonomous-run/scripts/test_validate_runbook.py`

- [ ] **Step 1: Write the failing test**

```python
# plugins/h2t-core/skills/autonomous-run/scripts/test_validate_runbook.py
import pytest
import runbook_schema as S
from validate_runbook import validate, validate_or_raise, RunbookInvalid, split_sections

def _good_text() -> str:
    parts = []
    for h in S.REQUIRED_SECTIONS:
        body = "content"
        for marker, sec in S.MARKER_SECTION.items():
            if sec == h:
                body += f"\n{marker}"
        parts.append(f"{h}\n{body}")
    return "\n\n".join(parts) + "\n"

def test_split_sections_maps_headings_to_bodies():
    secs = split_sections(_good_text())
    assert "## Decision-protocol" in secs
    assert "Money / budget" in secs["## Decision-protocol"]

def test_valid_text_returns_empty_problem_list():
    assert validate(_good_text()) == []

def test_missing_section_is_reported():
    text = _good_text().replace("## Decision-protocol\n", "## Nope\n")
    assert any("Decision-protocol" in p for p in validate(text))

def test_marker_moved_to_wrong_section_is_rejected():
    # gut Decision-protocol content but re-append the markers under Execution principles
    good = _good_text()
    markers = "\n".join(m for m, s in S.MARKER_SECTION.items() if s == "## Decision-protocol")
    text = good.replace("Irreversible / destructive", "").replace("Money / budget", "") \
               .replace("Scope / architecture change", "").replace("Gate not fixable in", "")
    text = text.replace("## Execution principles\ncontent",
                        "## Execution principles\ncontent\n" + markers)
    assert any("Decision-protocol" in p for p in validate(text))

def test_unresolved_token_is_rejected():
    assert any("TOKEN" in p or "<<" in p for p in validate(_good_text() + "\n<<branch>>"))

def test_validate_or_raise_raises():
    with pytest.raises(RunbookInvalid):
        validate_or_raise(_good_text().replace("## Gates\n", "## Gone\n"))
```

- [ ] **Step 2: Run to verify fail**

Run: `C:/dev/h2t-skills/.venv/Scripts/pytest plugins/h2t-core/skills/autonomous-run/scripts/test_validate_runbook.py -v`
Expected: FAIL (module `validate_runbook` not found).

- [ ] **Step 3: Implement**

```python
# plugins/h2t-core/skills/autonomous-run/scripts/validate_runbook.py
"""Sealed post-generation validator. Splits the artifact into H2 sections and reports
every missing required section, every safety marker absent FROM ITS OWN SECTION, and any
unresolved <<TOKEN>>. Run after generation AND after model weaving, so weaving cannot
silently gut a section or drop safety text (spec § Architecture step 3; codex-plan-gate-1 P1)."""
from __future__ import annotations
import re
import sys
import runbook_schema as S

class RunbookInvalid(Exception):
    pass

_H2 = re.compile(r"^## (.+?)\s*$", re.MULTILINE)

def split_sections(text: str) -> dict[str, str]:
    """Map each '## Heading' -> body text up to the next H2 (or EOF)."""
    out: dict[str, str] = {}
    matches = list(_H2.finditer(text))
    for i, m in enumerate(matches):
        heading = "## " + m.group(1).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        out[heading] = text[start:end]
    return out

def validate(text: str) -> list[str]:
    """Return human-readable problems; empty list == valid."""
    problems: list[str] = []
    secs = split_sections(text)
    for h in S.REQUIRED_SECTIONS:
        if h not in secs:
            problems.append(f"missing required section: {h}")
    for marker, section in S.MARKER_SECTION.items():
        if marker not in secs.get(section, ""):
            problems.append(f"safety marker {marker!r} missing from section {section}")
    if "<<" in text or ">>" in text:
        problems.append("unresolved <<TOKEN>> placeholder remains")
    return problems

def validate_or_raise(text: str) -> None:
    problems = validate(text)
    if problems:
        raise RunbookInvalid("; ".join(problems))

def _main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: validate_runbook.py <runbook.md>", file=sys.stderr)
        return 2
    problems = validate(open(argv[1], encoding="utf-8").read())
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
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```
git add plugins/h2t-core/skills/autonomous-run/scripts/validate_runbook.py plugins/h2t-core/skills/autonomous-run/scripts/test_validate_runbook.py
git commit -m "feat(autonomous-run): sealed section-scoped validator + tests"
```

### Task 1.3: runbook template

**Files:**
- Create: `plugins/h2t-core/skills/autonomous-run/references/runbook-template.md`

- [ ] **Step 1: Write the template.** Token fields `<<NAME>>`; H2 headings MUST match
  `REQUIRED_SECTIONS`; each safety marker MUST sit inside its `MARKER_SECTION`; pipeline
  steps are CHECKBOX items rendered from `<<pipeline_rows>>`.

```markdown
# Autonomous run — <<title>>

> **Durable spine (autonomous run, <<today>>).** Survives context compaction / blocker.
> A fresh session resumes from HERE.
> **Resume:** `autonomous-run resume <<runbook_path>>`

## Durable-spine header

Authorized: autonomous delivery through handoff. On a **hard-stop or unresolvable blocker**
→ run `h2t-core:handoff` — NOT on a default-shaped decision (those are auto-resolved, see
Decision-protocol). Verify the branch before every commit.

## Where things are

- Branch: `<<branch>>`
- Spec: `<<spec_path>>`
- Issue: <<issue>>
- Tests: `<<venv_test>>`
- e2e applicability: <<e2e_state>>

## Pipeline steps

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
- **Irreversible / destructive** (delete/force-push, merge to main, external publish/send,
  deleting/modifying pre-existing untracked files).
- **Money / budget** (paid runs, token budget over limit, council/codex beyond cost-gate).
- **Scope / architecture change** (deviation from approved spec, new invariant, redefined goal).
- **Gate not fixable in** `N_gate_attempts`.

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
git commit -m "feat(autonomous-run): durable runbook template (checkbox pipeline + sealed markers)"
```

### Task 1.4: generator renders template

**Files:**
- Create: `plugins/h2t-core/skills/autonomous-run/scripts/new_runbook.py`
- Test: `plugins/h2t-core/skills/autonomous-run/scripts/test_new_runbook.py`

- [ ] **Step 1: Write the failing test**

```python
# plugins/h2t-core/skills/autonomous-run/scripts/test_new_runbook.py
import inspect
import pytest
import runbook_schema as S
from validate_runbook import validate, validate_or_raise, RunbookInvalid
from new_runbook import render, create_runbook, PIPELINE_CONTRACT

_FIELDS = dict(title="Demo", today="2026-07-09", runbook_path="docs/x-runbook.md",
               branch="feat/x", spec_path="docs/x-spec.md", issue="#1",
               venv_test="pytest tests/", e2e_state="N/A")

def test_rendered_runbook_passes_validator():
    assert validate(render(**_FIELDS)) == []

def test_pipeline_rendered_as_checkboxes_for_every_step():
    text = render(**_FIELDS)
    for step in S.PIPELINE_STEPS:
        assert f"- [ ] **{step}**" in text

def test_tokens_are_substituted():
    text = render(**_FIELDS)
    assert "<<" not in text and ">>" not in text
    assert "feat/x" in text and "autonomous-run resume docs/x-runbook.md" in text

def test_contract_covers_every_step():
    assert set(PIPELINE_CONTRACT) == set(S.PIPELINE_STEPS)

def test_render_kwargs_match_run_fields():
    params = [p for p in inspect.signature(render).parameters]
    assert set(params) == set(S.RUN_FIELDS)

def test_invalid_e2e_state_rejected():
    with pytest.raises(ValueError):
        render(**{**_FIELDS, "e2e_state": "maybe"})

def test_tampered_output_is_rejected():
    text = render(**_FIELDS)
    with pytest.raises(RunbookInvalid):
        validate_or_raise(text.replace("Irreversible / destructive", ""))
```

- [ ] **Step 2: Run to verify fail** → FAIL (module missing).

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
    for step in S.PIPELINE_STEPS:
        skill, done, fail, reentry = PIPELINE_CONTRACT[step]
        out.append(
            f"- [ ] **{step}** — skill: `{skill}` · input: `<fill>` · "
            f"done: {done} · failure: {fail} · re-entry: {reentry}"
        )
    return "\n".join(out)

def render(*, title: str, today: str, runbook_path: str, branch: str, spec_path: str,
           issue: str, venv_test: str, e2e_state: str) -> str:
    if e2e_state.split()[0] not in S.E2E_STATES:
        raise ValueError(f"e2e_state must start with one of {S.E2E_STATES}; got {e2e_state!r}")
    text = _TEMPLATE.read_text(encoding="utf-8")
    subs = {"title": title, "today": today, "runbook_path": runbook_path,
            "branch": branch, "spec_path": spec_path, "issue": issue,
            "venv_test": venv_test, "e2e_state": e2e_state, "pipeline_rows": _rows()}
    for k, v in subs.items():
        text = text.replace(f"<<{k}>>", v)
    validate_or_raise(text)  # sealed: never emit an invalid runbook
    return text

def create_runbook(dest: str, **fields: str) -> Path:
    p = Path(dest)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(render(**fields), encoding="utf-8")
    return p
```

- [ ] **Step 4: Run to verify pass** → PASS (7 tests).

- [ ] **Step 5: Commit**

```
git add plugins/h2t-core/skills/autonomous-run/scripts/new_runbook.py plugins/h2t-core/skills/autonomous-run/scripts/test_new_runbook.py
git commit -m "feat(autonomous-run): runbook generator (checkbox pipeline, sealed on emit)"
```

### Task 1.5: 🎯 E2E — generate from the real spec, artifact passes the validator

**Files:**
- Modify: `plugins/h2t-core/skills/autonomous-run/scripts/test_new_runbook.py`

- [ ] **Step 1: Write the e2e test** (the M1 real end-to-end path — spec § Conditional e2e)

```python
def test_e2e_generate_real_runbook_and_validate(tmp_path):
    out = tmp_path / "2026-07-09-autonomous-run-orchestrator-runbook.md"
    p = create_runbook(
        str(out), title="Autonomous run orchestrator", today="2026-07-09",
        runbook_path=str(out), branch="feat/autonomous-run-orchestrator",
        spec_path="docs/superpowers/specs/2026-07-09-autonomous-run-orchestrator.md",
        issue="(none)", venv_test="pytest plugins/h2t-core/skills/autonomous-run/scripts/",
        e2e_state="applies (generate->validate)")
    text = p.read_text(encoding="utf-8")
    assert validate(text) == []
    assert "autonomous-run resume" in text
    # every pipeline step present as a checkbox (resume-parseable)
    for step in S.PIPELINE_STEPS:
        assert f"- [ ] **{step}**" in text
```

- [ ] **Step 2: Run** → PASS.

- [ ] **Step 3: Commit**

```
git add plugins/h2t-core/skills/autonomous-run/scripts/test_new_runbook.py
git commit -m "test(autonomous-run): e2e generate-then-validate a real runbook (M1)"
```

### Task 1.6: references objective tests (make M3 prose testable)

**Files:**
- Create: `plugins/h2t-core/skills/autonomous-run/scripts/test_references.py`

- [ ] **Step 1: Write tests** that lock the required content of the M3 markdown deliverables
  (they will fail until M3 writes those files — that is the point: objective acceptance).

```python
# plugins/h2t-core/skills/autonomous-run/scripts/test_references.py
from pathlib import Path
import pytest
import runbook_schema as S

_REF = Path(__file__).resolve().parents[1] / "references"
_SKILL = Path(__file__).resolve().parents[1] / "SKILL.md"

@pytest.mark.skipif(not (_REF / "decision-protocol.md").exists(), reason="M3 not built yet")
def test_decision_protocol_lists_all_hard_stops():
    text = (_REF / "decision-protocol.md").read_text(encoding="utf-8")
    for marker in S.MARKER_SECTION:
        if marker != "hard-stop or unresolvable blocker":
            assert marker in text

@pytest.mark.skipif(not (_REF / "gates.md").exists(), reason="M3 not built yet")
def test_gates_reference_has_codex_and_council():
    text = (_REF / "gates.md").read_text(encoding="utf-8").lower()
    assert "codex" in text and "council" in text and "n_gate_attempts" in text.replace(" ", "_")

@pytest.mark.skipif(not _SKILL.exists(), reason="M3 not built yet")
def test_skill_frontmatter_has_name_and_description():
    text = _SKILL.read_text(encoding="utf-8")
    assert text.startswith("---")
    head = text.split("---", 2)[1]
    assert "name:" in head and "description:" in head
```

- [ ] **Step 2: Run** → PASS (all skipped until M3). Confirms the acceptance harness exists.

- [ ] **Step 3: Commit**

```
git add plugins/h2t-core/skills/autonomous-run/scripts/test_references.py
git commit -m "test(autonomous-run): objective acceptance tests for M3 references/SKILL"
```

### Task 1.7: wire the script suite into CI

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1:** Read `pyproject.toml` `[tool.pytest.ini_options]`. If `testpaths` exists and
  does not include the skill scripts dir, add it:

```toml
testpaths = ["tests", "plugins/h2t-core/skills/autonomous-run/scripts"]
```

  If there is no `testpaths`, add the block. (If the CI job invokes pytest with an explicit
  path list instead, update that job to include the scripts dir — verify which by reading
  `.github/workflows/*.yml`.)

- [ ] **Step 2:** Verify collection from the repo root (not just the explicit dir):

Run: `C:/dev/h2t-skills/.venv/Scripts/pytest --collect-only -q | findstr autonomous-run`
Expected: the autonomous-run script tests are listed.

- [ ] **Step 3: Commit**

```
git add pyproject.toml
git commit -m "chore(autonomous-run): collect skill script tests in CI (testpaths)"
```

### 🚦 GATE M1 — codex review of the M1 diff
- [ ] Codex review (embedded diff, read-only, `high`) on the M1 scripts + template + tests.
  Focus: can a tampered/incomplete artifact pass the section-scoped validator? does the
  pipeline checkbox format round-trip generator→parser? token-substitution safety. Fix any
  `[P1]` (<= `N_gate_attempts` = 2).
- [ ] Full script suite green:
  `C:/dev/h2t-skills/.venv/Scripts/pytest plugins/h2t-core/skills/autonomous-run/scripts/ -v`

---

## Milestone M2 — resume + two-track state

### Task 2.1: pipeline checkbox-state parser (scoped + filtered)

**Files:**
- Create: `plugins/h2t-core/skills/autonomous-run/scripts/runbook_state.py`
- Test: `plugins/h2t-core/skills/autonomous-run/scripts/test_runbook_state.py`

- [ ] **Step 1: Write the failing test** (uses the REAL generated format + decoy checkboxes)

```python
# plugins/h2t-core/skills/autonomous-run/scripts/test_runbook_state.py
import runbook_schema as S
from new_runbook import render
from runbook_state import parse_steps, unchecked_steps

def _rendered_with_two_done() -> str:
    text = render(title="D", today="2026-07-09", runbook_path="p.md", branch="b",
                  spec_path="s.md", issue="#1", venv_test="pytest", e2e_state="N/A")
    # mark the first two pipeline checkboxes done
    text = text.replace("- [ ] **write-spec**", "- [x] **write-spec**", 1)
    return text.replace("- [ ] **review-spec**", "- [x] **review-spec**", 1)

def test_parse_only_pipeline_steps_not_gate_checkboxes():
    names = [n for n, _ in parse_steps(_rendered_with_two_done())]
    assert names == S.PIPELINE_STEPS      # gate/decision-log checkboxes excluded

def test_unchecked_steps_after_two_done():
    assert unchecked_steps(_rendered_with_two_done()) == S.PIPELINE_STEPS[2:]

def test_all_checked_returns_empty():
    text = _rendered_with_two_done()
    for step in S.PIPELINE_STEPS:
        text = text.replace(f"- [ ] **{step}**", f"- [x] **{step}**")
    assert unchecked_steps(text) == []
```

- [ ] **Step 2: Run to verify fail** → FAIL (module missing).

- [ ] **Step 3: Implement**

```python
# plugins/h2t-core/skills/autonomous-run/scripts/runbook_state.py
"""Parse pipeline checkbox state so a fresh session rebuilds the TodoWrite mirror from the
durable source of truth (spec § Two-track state model). Scoped to the `## Pipeline steps`
section and filtered to known step names, so gate checklists and decision-log bullets never
leak into resume state (codex-plan-gate-1 P1)."""
from __future__ import annotations
import re
import runbook_schema as S

_SECTION = "## Pipeline steps"
_STEP = re.compile(r"^- \[([ xX])\]\s+\*\*(?P<name>[^*]+)\*\*", re.MULTILINE)

def _pipeline_block(text: str) -> str:
    start = text.find(_SECTION)
    if start == -1:
        return ""
    rest = text[start + len(_SECTION):]
    nxt = rest.find("\n## ")
    return rest if nxt == -1 else rest[:nxt]

def parse_steps(text: str) -> list[tuple[str, bool]]:
    out: list[tuple[str, bool]] = []
    for m in _STEP.finditer(_pipeline_block(text)):
        name = m.group("name").strip()
        if name in S.PIPELINE_STEPS:      # ignore stray checkboxes
            out.append((name, m.group(1).lower() == "x"))
    return out

def unchecked_steps(text: str) -> list[str]:
    return [name for name, checked in parse_steps(text) if not checked]
```

- [ ] **Step 4: Run to verify pass** → PASS (3 tests).

- [ ] **Step 5: Commit**

```
git add plugins/h2t-core/skills/autonomous-run/scripts/runbook_state.py plugins/h2t-core/skills/autonomous-run/scripts/test_runbook_state.py
git commit -m "feat(autonomous-run): scoped+filtered pipeline checkbox parser (resume)"
```

### Task 2.2: SKILL.md resume + two-track procedure (prose)

**Files:**
- Create (partial): `plugins/h2t-core/skills/autonomous-run/SKILL.md` (resume section; launch body in M3)

- [ ] **Step 1: Write the resume + state section** with the exact ordering rule from the spec:

```markdown
## Resume & state (two-track)

On `autonomous-run resume <path>`:
1. Read the artifact (durable source of truth).
2. `runbook_state.unchecked_steps()` -> rebuild the TodoWrite mirror from the unchecked
   pipeline steps only; discard any stale in-session TodoWrite.
3. A step whose done-criterion is already satisfied (PR exists, tests green) is checked
   without re-running.
4. Continue from the first unchecked step, following its per-step contract.

Update ordering (one-way): on step completion, write the artifact checkbox FIRST (durable
source of truth), then mark the TodoWrite item. The reverse is forbidden.
```

- [ ] **Step 2: Commit**

```
git add plugins/h2t-core/skills/autonomous-run/SKILL.md
git commit -m "docs(autonomous-run): SKILL resume + two-track ordering section"
```

### 🚦 GATE M2 — codex review of the M2 diff
- [ ] Codex review (embedded) on `runbook_state.py` + SKILL resume section. Focus: does the
  scoped parser round-trip against `new_runbook.render` output for all step states; any
  section-boundary edge case. Fix `[P1]`.
- [ ] Suite green: `C:/dev/h2t-skills/.venv/Scripts/pytest plugins/h2t-core/skills/autonomous-run/scripts/ -v`

---

## Milestone M3 — orchestration + protocol wiring

### Task 3.1: decision-protocol + gates references

**Files:**
- Create: `plugins/h2t-core/skills/autonomous-run/references/decision-protocol.md`
- Create: `plugins/h2t-core/skills/autonomous-run/references/gates.md`

- [ ] **Step 1: Write `decision-protocol.md`** — allow-list categories + the 4 hard-stops +
  escalate-everything-else + `N_gate_attempts` = 2, lifted from spec § Decision-protocol.
  Acceptance: `test_references.py::test_decision_protocol_lists_all_hard_stops` passes.
- [ ] **Step 2: Write `gates.md`** — codex review-gate (embedded-content command shape,
  read-only, `[P1]` = FAIL), council finish-gate (codex + >=2 Opus lenses -> SOUND/blockers),
  pre-merge-check, and `N_gate_attempts`. Acceptance:
  `test_references.py::test_gates_reference_has_codex_and_council` passes.
- [ ] **Step 3: Run** the references tests → PASS.

Run: `C:/dev/h2t-skills/.venv/Scripts/pytest plugins/h2t-core/skills/autonomous-run/scripts/test_references.py -v`

- [ ] **Step 4: Commit**

```
git add plugins/h2t-core/skills/autonomous-run/references/decision-protocol.md plugins/h2t-core/skills/autonomous-run/references/gates.md
git commit -m "docs(autonomous-run): decision-protocol + gates references"
```

### Task 3.2: SKILL.md launch body + frontmatter

**Files:**
- Modify: `plugins/h2t-core/skills/autonomous-run/SKILL.md`

- [ ] **Step 1: Add frontmatter + launch procedure.** Frontmatter `name: autonomous-run`,
  `description:` triggering post-brainstorm on "работай сам / автономно / overnight / выполни
  план сам / autonomous run". Body = § Architecture launch flow (preconditions -> generate via
  `new_runbook.create_runbook` -> sealed validate -> materialize TodoWrite -> hand off per the
  per-step contract), the e2e applicability classification (applies / N/A / BLOCKED-DEFERRED),
  and pointers to `references/decision-protocol.md` + `references/gates.md`. Acceptance:
  `test_references.py::test_skill_frontmatter_has_name_and_description` passes.
- [ ] **Step 2: Verify skill loads** — `pwsh scripts/claude-dev.ps1` dev session lists
  `h2t-core:autonomous-run`. Expected: present.
- [ ] **Step 3: Commit**

```
git add plugins/h2t-core/skills/autonomous-run/SKILL.md
git commit -m "feat(autonomous-run): SKILL launch body + trigger frontmatter"
```

### Task 3.3: reconcile the project rule

**Files:**
- Modify: `.claude/rules/autonomous-execution.md`

- [ ] **Step 1: Expand the thin rule** to reference the skill's `references/` as the canonical
  protocol source (gates + decision-protocol), keeping the existing 4-point discipline as a
  summary that now points at `plugins/h2t-core/skills/autonomous-run/references/`.
- [ ] **Step 2: Commit**

```
git add .claude/rules/autonomous-execution.md
git commit -m "docs(autonomous-run): point autonomous-execution rule at skill references"
```

> **Out of scope (follow-up issue):** `crypto-regime-spike-*/.claude/rules/execution-protocols.md`
> → thin pointer. Different repo; note it for a separate PR, do not edit here.

### 🚦 GATE M3 + council finish-gate
- [ ] Codex review (embedded) on the full M3 diff (references + SKILL + rule). Fix `[P1]`.
- [ ] **Council finish-gate** (`.claude/rules/autonomous-execution.md`): codex (correctness) +
  2 Opus lenses (A: sealed-safety + validator soundness; B: resume/two-track invariant +
  North-Star alignment) -> SOUND / blockers. Artifact ->
  `docs/reports/2026-07-09-council-validation-autonomous-run.md`.
- [ ] Full suite green from repo root:
  `C:/dev/h2t-skills/.venv/Scripts/pytest plugins/h2t-core/skills/autonomous-run/scripts/ tests/ -q`.

### Task 3.4: finish branch + handoff
- [ ] `superpowers:finishing-a-development-branch` — open PR for `feat/autonomous-run-orchestrator`
  (base main). Do NOT auto-merge; leave open for operator review.
- [ ] `h2t-core:handoff` (terminal step — always, success or blocker).

---

## Self-Review (completed by plan author)

- **Spec coverage:** § Architecture (launch/sealed-validate) → 1.4 + 3.2; § Resume trigger →
  2.1/2.2 + 3.2; § Per-step execution contract → 1.4 (`PIPELINE_CONTRACT`); § Conditional e2e
  (3 states) → 1.4 (`E2E_STATES` guard) + 1.5 + 3.2; § Components → all Create tasks;
  § Runbook schema → 1.1/1.3; § Two-track state model (ordering) → 2.1/2.2; § Decision-protocol
  → 3.1 + template; § Testing (sealed + reject-tamper) → 1.2/1.4; § Implementation phasing →
  M1/M2/M3. All covered.
- **codex-plan-gate-1 findings applied:** **P1** pipeline as checkboxes (1.3/1.4) round-tripping
  the scoped+filtered parser (2.1); **P1** section-scoped validator + token-residue check (1.2);
  **P2** `RUN_FIELDS`↔`render` kwargs test (1.4), CI wiring (1.7), e2e-state guard+test (1.4),
  objective M3 acceptance tests (1.6/3.x). Marker casing made case-stable (1.1 `MARKER_SECTION`).
- **Placeholder scan:** no TBD/TODO in code steps; markdown tasks gated by objective tests (1.6).
- **Type consistency:** `render(**S.RUN_FIELDS)`, `create_runbook`, `validate`/`validate_or_raise`/
  `RunbookInvalid`/`split_sections`, `parse_steps`/`unchecked_steps`, `PIPELINE_CONTRACT`,
  `REQUIRED_SECTIONS`/`MARKER_SECTION`/`PIPELINE_STEPS`/`E2E_STATES`/`RUN_FIELDS` consistent across tasks.
- **Gates present:** codex-gate after M1/M2/M3; council finish-gate at end; e2e at M1 (1.5);
  handoff terminal (3.4). Matches the autonomous-run discipline being dogfooded.
