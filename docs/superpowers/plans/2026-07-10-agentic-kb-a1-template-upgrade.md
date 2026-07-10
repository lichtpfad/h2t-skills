---
title: "Agentic KB — A1: configurable verdict / strength-axis in llm-kb-template"
status: "draft"
date: "2026-07-10"
milestone: ""
---

# Agentic KB — A1: configurable verdict / strength-axis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the `verdict` enum and its strength ladder configurable per-domain in `llm-kb-template`, mirroring the existing `source_types` runtime-membership pattern, add runtime enforcement of verdict-membership + council-completeness, and prove the default (legacy) config stays byte-identical.

**Architecture:** Today `verdict` is a **static enum** duplicated in `schemas/wiki-page.schema.json` (line 48) and `scripts/lint_wiki.py` (`VALID_VERDICT`, line 20), and a drift-guard test asserts they match. `source_types` already shows the target pattern: schema types it as a generic `string`, and `lint_wiki` validates membership against `kb.config.json` at runtime. This plan applies that same pattern to `verdict`, adds two **optional** config keys (`verdicts` ladder + `strength_axis`), and gates the new council-completeness rule on the presence of an explicit `verdicts` ladder so that configs without it keep legacy behavior exactly.

**Tech Stack:** Python stdlib + `pyyaml` (runtime); `pytest` + `jsonschema` (dev). All scripts stdlib-only. Tests run via `C:/dev/llm-kb-template/.venv/Scripts/pytest`.

---

## Working repo & preconditions

- **All edits in this plan are made in `C:/dev/llm-kb-template`** (NOT h2t-skills — only this plan file lives in h2t-skills).
- All git commands use `git -C C:/dev/llm-kb-template ...`.
- Precondition: `git -C C:/dev/llm-kb-template status` is clean before starting. If not, stop and surface.
- Test runner: `C:/dev/llm-kb-template/.venv/Scripts/pytest` (no venv activation).
- One Bash command per call (no `&&`), per CLAUDE.md.

## Scope note (read before executing)

- **In scope (A1):** optional `verdicts`/`strength_axis` config keys with fail-loud validation; generic-string `verdict` in the wiki schema; config-driven `VALID_VERDICT` in lint; runtime enforcement of (1) verdict-membership and (2) council-completeness (gated on explicit ladder); meta-schema for ladder shape; rewritten drift-guard; back-compat golden gate; docs.
- **Deferred to #295 (application-outcome bridge), NOT built here:** `synthesize_council.py` deriving+writing a promoted `verdict` into wiki atoms (the authored→derived flip). Rationale: in the agentic-kb MVP everything is `HYPOTHESIS` and `WORKS-IN-PRACTICE` is unreachable until the outcome bridge exists (#295), so derivation would only ever write rank-0 (a no-op) while adding the riskiest code (programmatic frontmatter mutation). A1 builds the ladder + enforcement the derivation will later feed. **This deviates from the merged spec's A1 acceptance line "synthesize_council пишет verdict" — deviation is intentional and flagged to the operator.**
- **`strength_axis` is a declared, validated config value in A1** (fail-loud membership: `source_group_convergence | domain_recurrence`). A1 does NOT change how the convergence signal is computed — swapping the actual strength *computation* to `domain_recurrence` is downstream (A2 configures it; the recurrence signal is produced by the harvest/derivation path in #295). A1 only guarantees the value is a validated first-class config field.

## Legacy vs ladder mode (the central invariant)

| Config state | `VALID_VERDICT` | Council-completeness rule | Schema `verdict` |
|---|---|---|---|
| **No `verdicts` key** (legacy, e.g. quant defaults) | `{CONFIRMED, LIKELY, HYPOTHESIS}` (built-in default) | **OFF** (unchanged behavior) | generic string (membership at runtime) |
| **Explicit `verdicts` ladder** (agentic-kb) | names from `config.verdicts[].name` | **ON**: verdict rank > 0 OR claim in tldr/decision_triggers ⇒ `judge_pass: true` required | generic string (membership at runtime) |

The default set `{CONFIRMED, LIKELY, HYPOTHESIS}` is the built-in fallback so legacy configs (no `verdicts` key) keep identical output. This is what the golden gate (Task 1) locks.

## File Structure

Files created / modified (all under `C:/dev/llm-kb-template`):

- **Modify** `scripts/_kbconfig.py` — add optional `verdicts`/`strength_axis` loading + validation + helpers `valid_verdicts(cfg)`, `verdict_ranks(cfg)`, `strength_axis(cfg)`, `has_explicit_ladder(cfg)`.
- **Modify** `scripts/lint_wiki.py` — `VALID_VERDICT` becomes a module global populated from config in `main()` (mirror `VALID_SOURCE_TYPES`); add council-completeness check gated on explicit ladder.
- **Modify** `schemas/wiki-page.schema.json` — `verdict` enum → generic `string`.
- **Modify** `schemas/kb.config.schema.json` — add optional `verdicts` (ladder shape: `name`+`rank`, `rank` integer ≥0) and `strength_axis` (enum) to `properties` (schema has `additionalProperties: false`, so unlisted keys would fail).
- **Modify** `kb.config.example.json` — add commented-by-convention example `verdicts`/`strength_axis` (kept as the legacy default shape so the example stays back-compat).
- **Create** `tests/test_backcompat_golden.py` — characterization gate: default-config lint+council output frozen.
- **Create** `tests/test_configurable_verdict.py` — new-mode tests (custom ladder accepted, non-member rejected, council-completeness enforced, ladder-shape validation).
- **Modify** `tests/test_generic_pipeline.py` — rewrite `test_schema_enums_match_runtime_validators` (verdict no longer a static schema enum).
- **Modify** `CLAUDE.template.md`, `README.md` — document `verdicts`/`strength_axis` surface.

---

### Task 1: Back-compat golden gate (characterization test — write FIRST)

Locks current legacy behavior BEFORE any production edit. Written as a characterization test: run the real pipeline on a default config (no `verdicts` key), capture actual output, freeze it as the golden assertion. Every later task must keep it green.

**Files:**
- Create: `tests/test_backcompat_golden.py`

- [ ] **Step 1: Confirm clean tree**

Run: `git -C C:/dev/llm-kb-template status --short`
Expected: no output (clean).

- [ ] **Step 2: Write the characterization test scaffold**

Create `tests/test_backcompat_golden.py`. It reuses the throwaway-KB helpers pattern from `tests/test_generic_pipeline.py` (copy `scripts/` into `tmp_path`, write `kb.config.json` WITHOUT a `verdicts` key, drive via subprocess). Golden strings start empty and are filled in Step 3.

```python
#!/usr/bin/env python3
"""Back-compat golden gate: a config WITHOUT a `verdicts` key (legacy) must
produce byte-identical lint + council output before and after the configurable-
verdict change. This is a characterization test — the GOLDEN_* constants are
captured from the current (pre-change) behavior and then frozen.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

SCRIPTS_SRC = Path(__file__).parent.parent / "scripts"


def _make_legacy_kb(tmp_path: Path) -> Path:
    shutil.copytree(SCRIPTS_SRC, tmp_path / "scripts")
    (tmp_path / "wiki").mkdir()
    (tmp_path / "filter-logs").mkdir()
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "pipeline-state.json").write_text("{}", encoding="utf-8")
    cfg = {
        "kb_name": "Legacy KB",
        "domain": "gardening",
        "source_types": ["garden-trial", "extension-guide"],
        "judges": ["Practitioner", "Architect", "Skeptic"],
        # NOTE: deliberately NO "verdicts" key -> legacy mode.
    }
    (tmp_path / "kb.config.json").write_text(json.dumps(cfg), encoding="utf-8")
    return tmp_path


def _run(kb: Path, script: str, *args):
    return subprocess.run(
        [sys.executable, str(kb / "scripts" / script), *args],
        cwd=kb, capture_output=True, text=True,
    )


_LEGACY_TOPIC = """---
topic: Companion Planting
page_status: partial
priority: P0
updated: 2026-07-03
see_also: []
tldr: >
  Interplanting basil with tomato reduces certain pest pressure in field trials.
source_quality:
  convergence: partial
evidence:
  - claim: "basil interplanting reduces tomato hornworm density"
    sources:
      - type: garden-trial
        ref: "trial:rodale-2019"
        replicated: false
      - type: extension-guide
        ref: "doc:uc-ipm-tomato"
    confidence: Medium
    verdict: LIKELY
  - claim: "marigold borders suppress root-knot nematodes"
    sources:
      - type: extension-guide
        ref: "doc:uc-ipm-marigold"
    confidence: High
    verdict: CONFIRMED
---

## Key Concepts
Companion planting.
"""

# Filled in Step 3 from captured actual output, then frozen.
GOLDEN_LINT_STDOUT = ""


def test_legacy_lint_output_frozen(tmp_path):
    kb = _make_legacy_kb(tmp_path)
    (kb / "wiki" / "companion.md").write_text(_LEGACY_TOPIC, encoding="utf-8")
    r = _run(kb, "lint_wiki.py", "wiki/companion.md")
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout == GOLDEN_LINT_STDOUT, (
        f"legacy lint output changed:\n---got---\n{r.stdout}\n---want---\n{GOLDEN_LINT_STDOUT}"
    )
```

- [ ] **Step 3: Capture the golden output and freeze it**

Run the test once to see the actual current stdout (it will fail the empty-string assertion and print the got/want diff):

Run: `C:/dev/llm-kb-template/.venv/Scripts/pytest tests/test_backcompat_golden.py -v`
Expected: FAIL, showing `---got---` with the real stdout (a single line `OK:   companion.md\n`).

Copy the exact `got` value into `GOLDEN_LINT_STDOUT` (preserve the trailing newline). Re-run:

Run: `C:/dev/llm-kb-template/.venv/Scripts/pytest tests/test_backcompat_golden.py -v`
Expected: PASS.

- [ ] **Step 4: Add a council characterization test**

Append to `tests/test_backcompat_golden.py`. This drives one full council round on the legacy KB and freezes the appended filter-log section + `pipeline-state.json`. Same capture-then-freeze method.

```python
def _judge_section(name: str, rows: list[tuple[str, str]]) -> str:
    body = "\n".join(f"| {claim} | {verdict} | reason |" for claim, verdict in rows)
    return f"### Judge: {name}\n\n| claim | verdict | reason |\n|---|---|---|\n{body}\n"


_CLAIMS = [
    ("basil interplanting reduces tomato hornworm density", "PASS"),
    ("marigold borders suppress root-knot nematodes", "PASS"),
]

# Filled in Step 5 from captured actual output, then frozen.
GOLDEN_COUNCIL_STATE = ""


def test_legacy_council_state_frozen(tmp_path):
    kb = _make_legacy_kb(tmp_path)
    log = kb / "filter-logs" / "companion.md"
    header = "## Round 1\n\n"
    sections = "".join(
        _judge_section(j, _CLAIMS)
        for j in ("Practitioner", "Architect", "Skeptic")
    )
    log.write_text(header + sections, encoding="utf-8")

    r = _run(kb, "synthesize_council.py", "companion")
    assert r.returncode == 0, r.stdout + r.stderr

    state = (kb / "data" / "pipeline-state.json").read_text(encoding="utf-8")
    assert state == GOLDEN_COUNCIL_STATE, (
        f"legacy council state changed:\n---got---\n{state}\n---want---\n{GOLDEN_COUNCIL_STATE}"
    )
```

- [ ] **Step 5: Capture + freeze the council golden**

Run: `C:/dev/llm-kb-template/.venv/Scripts/pytest tests/test_backcompat_golden.py::test_legacy_council_state_frozen -v`
Expected: FAIL, printing the real `pipeline-state.json` JSON in `---got---`.

Note: `last_judge_date` in the state is `datetime.date.today()` — non-deterministic. To keep the golden stable, normalize it in the test before comparing:

```python
    state_obj = json.loads(state)
    state_obj["companion"]["last_judge_date"] = "FROZEN"
    state = json.dumps(state_obj, indent=2, ensure_ascii=False)
```

Insert that normalization before the assert, re-capture the `got`, paste into `GOLDEN_COUNCIL_STATE`, re-run:

Run: `C:/dev/llm-kb-template/.venv/Scripts/pytest tests/test_backcompat_golden.py -v`
Expected: PASS (both tests).

- [ ] **Step 6: Commit**

```bash
git -C C:/dev/llm-kb-template add tests/test_backcompat_golden.py
git -C C:/dev/llm-kb-template commit -m "test: back-compat golden gate for legacy verdict config"
```

---

### Task 2: `_kbconfig.py` — optional `verdicts` / `strength_axis` loading + helpers

**Files:**
- Modify: `scripts/_kbconfig.py`
- Test: `tests/test_configurable_verdict.py` (create)

- [ ] **Step 1: Write failing tests for config helpers**

Create `tests/test_configurable_verdict.py`:

```python
#!/usr/bin/env python3
"""Configurable verdict ladder + strength_axis: loader helpers and lint behavior."""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS_SRC = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_SRC))

import _kbconfig  # noqa: E402

DEFAULT_VERDICTS = {"CONFIRMED", "LIKELY", "HYPOTHESIS"}

_LADDER = [
    {"name": "HYPOTHESIS", "rank": 0, "promote_when": "start"},
    {"name": "WORKS-IN-PRACTICE", "rank": 1, "promote_when": "council PASS + 2 domains"},
]


def _cfg(**overrides) -> dict:
    base = {
        "kb_name": "K",
        "domain": "d",
        "source_types": ["x"],
        "judges": ["A", "B"],
    }
    base.update(overrides)
    return base


def test_valid_verdicts_defaults_when_absent():
    assert _kbconfig.valid_verdicts(_cfg()) == DEFAULT_VERDICTS


def test_has_explicit_ladder_false_when_absent():
    assert _kbconfig.has_explicit_ladder(_cfg()) is False


def test_valid_verdicts_from_explicit_ladder():
    assert _kbconfig.valid_verdicts(_cfg(verdicts=_LADDER)) == {
        "HYPOTHESIS", "WORKS-IN-PRACTICE"
    }


def test_verdict_ranks_from_ladder():
    assert _kbconfig.verdict_ranks(_cfg(verdicts=_LADDER)) == {
        "HYPOTHESIS": 0, "WORKS-IN-PRACTICE": 1
    }


def test_strength_axis_defaults_to_convergence():
    assert _kbconfig.strength_axis(_cfg()) == "source_group_convergence"


def test_strength_axis_reads_configured_value():
    assert _kbconfig.strength_axis(_cfg(strength_axis="domain_recurrence")) == "domain_recurrence"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `C:/dev/llm-kb-template/.venv/Scripts/pytest tests/test_configurable_verdict.py -v`
Expected: FAIL with `AttributeError: module '_kbconfig' has no attribute 'valid_verdicts'`.

- [ ] **Step 3: Implement the helpers in `_kbconfig.py`**

Add these constants and functions to `scripts/_kbconfig.py` (after `vote_threshold`). `load_config()` gains validation of the two optional keys near its end (before `return cfg`).

```python
DEFAULT_VERDICTS = ("CONFIRMED", "LIKELY", "HYPOTHESIS")
VALID_STRENGTH_AXES = ("source_group_convergence", "domain_recurrence")


def _validate_optional_verdict_config(cfg: dict) -> None:
    """Fail-loud validation for the optional `verdicts` ladder and `strength_axis`."""
    axis = cfg.get("strength_axis")
    if axis is not None and axis not in VALID_STRENGTH_AXES:
        sys.exit(
            f"ERROR: strength_axis must be one of {list(VALID_STRENGTH_AXES)}, got: {axis!r}"
        )

    ladder = cfg.get("verdicts")
    if ladder is None:
        return
    if not isinstance(ladder, list) or not ladder:
        sys.exit("ERROR: verdicts must be a non-empty list of {name, rank} objects")
    names, ranks = [], []
    for i, v in enumerate(ladder):
        if not isinstance(v, dict) or "name" not in v or "rank" not in v:
            sys.exit(f"ERROR: verdicts[{i}] must be an object with 'name' and 'rank'")
        if not isinstance(v["name"], str) or not v["name"].strip():
            sys.exit(f"ERROR: verdicts[{i}].name must be a non-empty string")
        if not isinstance(v["rank"], int) or isinstance(v["rank"], bool) or v["rank"] < 0:
            sys.exit(f"ERROR: verdicts[{i}].rank must be an integer >= 0")
        names.append(v["name"])
        ranks.append(v["rank"])
    if len(set(names)) != len(names):
        sys.exit("ERROR: verdicts[].name values must be unique")
    if len(set(ranks)) != len(ranks):
        sys.exit("ERROR: verdicts[].rank values must be unique")
    if sorted(ranks) != list(range(min(ranks), min(ranks) + len(ranks))):
        sys.exit("ERROR: verdicts[].rank must be a contiguous monotonic sequence (e.g. 0,1,2)")
    if 0 not in ranks:
        sys.exit("ERROR: verdicts ladder must include a rank-0 (base hypothesis) verdict")


def has_explicit_ladder(cfg: dict) -> bool:
    return isinstance(cfg.get("verdicts"), list) and bool(cfg.get("verdicts"))


def valid_verdicts(cfg: dict) -> set:
    if has_explicit_ladder(cfg):
        return {v["name"] for v in cfg["verdicts"]}
    return set(DEFAULT_VERDICTS)


def verdict_ranks(cfg: dict) -> dict:
    if has_explicit_ladder(cfg):
        return {v["name"]: v["rank"] for v in cfg["verdicts"]}
    # Legacy flat enum has no ladder; treat all as rank 0 (no promotion concept).
    return {name: 0 for name in DEFAULT_VERDICTS}


def strength_axis(cfg: dict) -> str:
    return cfg.get("strength_axis") or "source_group_convergence"
```

Then wire validation into `load_config()` — add this line immediately before `return cfg`:

```python
    _validate_optional_verdict_config(cfg)
    return cfg
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `C:/dev/llm-kb-template/.venv/Scripts/pytest tests/test_configurable_verdict.py -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Verify golden gate still green**

Run: `C:/dev/llm-kb-template/.venv/Scripts/pytest tests/test_backcompat_golden.py -v`
Expected: PASS (default config path untouched).

- [ ] **Step 6: Commit**

```bash
git -C C:/dev/llm-kb-template add scripts/_kbconfig.py tests/test_configurable_verdict.py
git -C C:/dev/llm-kb-template commit -m "feat: load+validate optional verdicts ladder and strength_axis"
```

---

### Task 3: Config meta-schema + example config

**Files:**
- Modify: `schemas/kb.config.schema.json`
- Modify: `kb.config.example.json`
- Test: `tests/test_configurable_verdict.py` (add schema-shape test)

- [ ] **Step 1: Write failing test for ladder-shape rejection via loader**

The `_kbconfig` validation from Task 2 is the runtime enforcement; here we pin the JSON-Schema mirror. Add to `tests/test_configurable_verdict.py`:

```python
def _make_kb(tmp_path: Path, cfg: dict) -> Path:
    shutil.copytree(SCRIPTS_SRC, tmp_path / "scripts")
    (tmp_path / "wiki").mkdir()
    (tmp_path / "filter-logs").mkdir()
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "pipeline-state.json").write_text("{}", encoding="utf-8")
    (tmp_path / "kb.config.json").write_text(json.dumps(cfg), encoding="utf-8")
    return tmp_path


def _run(kb: Path, script: str, *args):
    return subprocess.run(
        [sys.executable, str(kb / "scripts" / script), *args],
        cwd=kb, capture_output=True, text=True,
    )


def test_non_monotonic_ladder_fails_loud(tmp_path):
    bad = _cfg(verdicts=[
        {"name": "A", "rank": 0},
        {"name": "B", "rank": 2},  # gap -> not contiguous
    ])
    kb = _make_kb(tmp_path, bad)
    (kb / "wiki" / "t.md").write_text(
        "---\ntopic: T\npage_status: stub\npriority: P0\nupdated: 2026-07-03\n---\n",
        encoding="utf-8",
    )
    r = _run(kb, "lint_wiki.py", "wiki/t.md")
    assert r.returncode != 0
    assert "contiguous monotonic" in (r.stdout + r.stderr)


def test_example_config_validates_against_meta_schema():
    import jsonschema  # dev-only
    root = Path(__file__).parent.parent
    schema = json.loads((root / "schemas" / "kb.config.schema.json").read_text(encoding="utf-8"))
    example = json.loads((root / "kb.config.example.json").read_text(encoding="utf-8"))
    jsonschema.validate(example, schema)  # raises on failure
```

- [ ] **Step 2: Run to verify failure**

Run: `C:/dev/llm-kb-template/.venv/Scripts/pytest tests/test_configurable_verdict.py -k "ladder or meta_schema" -v`
Expected: `test_non_monotonic_ladder_fails_loud` PASSES already (loader validation from Task 2 catches it via subprocess). `test_example_config_validates_against_meta_schema` FAILS only if the example later gains a `verdicts`/`strength_axis` key not permitted by the schema. Both are guarded by Step 3.

Note: if `test_non_monotonic_ladder_fails_loud` already passes, that is correct — it proves the runtime loader guards ladder shape. The schema work below adds the declarative mirror + unblocks optional keys under `additionalProperties: false`.

- [ ] **Step 3: Add `verdicts` + `strength_axis` to `schemas/kb.config.schema.json`**

The schema has `"additionalProperties": false`, so any config carrying `verdicts`/`strength_axis` would be rejected until they are declared. Add these two properties inside `"properties"` (after `vote_threshold`):

```json
    "strength_axis": {
      "type": "string",
      "enum": ["source_group_convergence", "domain_recurrence"],
      "description": "Which signal drives verdict strength. Default (absent) = source_group_convergence (legacy). Runtime membership enforced in _kbconfig.py."
    },
    "verdicts": {
      "type": "array",
      "minItems": 1,
      "description": "Optional per-domain verdict ladder. Absent = legacy flat enum {CONFIRMED, LIKELY, HYPOTHESIS}. Ranks must be contiguous from 0 and unique; rank-0 = base hypothesis. Shape only — the contiguous/rank-0 cross-item rules are enforced in _kbconfig.py.",
      "items": {
        "type": "object",
        "required": ["name", "rank"],
        "additionalProperties": true,
        "properties": {
          "name": { "type": "string", "minLength": 1 },
          "rank": { "type": "integer", "minimum": 0 },
          "promote_when": { "type": "string" }
        }
      }
    }
```

- [ ] **Step 4: Update `kb.config.example.json` with the legacy-shaped ladder**

Add the two keys to `kb.config.example.json` so the example documents the surface while staying legacy-compatible in meaning (a 3-step ladder matching the current flat enum, `source_group_convergence` axis):

```json
{
  "kb_name": "My Domain KB",
  "domain": "<short domain name, e.g. TouchDesigner best-practices>",
  "source_types": [
    "official-docs",
    "expert",
    "community",
    "implementation",
    "tutorial"
  ],
  "judges": [
    "Practitioner",
    "Architect",
    "Skeptic"
  ],
  "vote_threshold": null,
  "strength_axis": "source_group_convergence",
  "verdicts": [
    { "name": "HYPOTHESIS", "rank": 0, "promote_when": "start; one source or awaiting council" },
    { "name": "LIKELY", "rank": 1, "promote_when": "partial convergence (>=2 source groups)" },
    { "name": "CONFIRMED", "rank": 2, "promote_when": "full convergence + council PASS" }
  ]
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `C:/dev/llm-kb-template/.venv/Scripts/pytest tests/test_configurable_verdict.py -v`
Expected: PASS (all, including the two new).

- [ ] **Step 6: Verify existing schema tests still pass**

Run: `C:/dev/llm-kb-template/.venv/Scripts/pytest tests/test_schemas.py -v`
Expected: PASS (example config still validates; the example now carries the two optional keys, both declared).

- [ ] **Step 7: Commit**

```bash
git -C C:/dev/llm-kb-template add schemas/kb.config.schema.json kb.config.example.json tests/test_configurable_verdict.py
git -C C:/dev/llm-kb-template commit -m "feat: meta-schema for verdict ladder + strength_axis; example config"
```

---

### Task 4: `wiki-page.schema.json` — verdict as generic string + rewrite drift-guard

**Files:**
- Modify: `schemas/wiki-page.schema.json:48`
- Modify: `tests/test_generic_pipeline.py` (rewrite `test_schema_enums_match_runtime_validators`)

- [ ] **Step 1: Rewrite the drift-guard test to the new invariant**

The old assertion `lint_wiki.VALID_VERDICT == set(ev["verdict"]["enum"])` (line 309) will break once the schema drops the enum AND `VALID_VERDICT` becomes a runtime-populated set. Replace that single line with an assertion mirroring how `source_types` is handled (schema types it as `string`, no enum). In `tests/test_generic_pipeline.py`, replace line 309:

```python
    # verdict is configurable per-domain: the schema types it as a generic string
    # (membership checked at runtime against kb.config.verdicts by lint_wiki),
    # exactly like sources[].type. So the schema must NOT pin a verdict enum.
    assert "enum" not in ev["verdict"], (
        "verdict must be a generic string in the schema (membership is a runtime check)"
    )
    assert ev["verdict"].get("type") == "string"
```

(Leave the other four enum assertions — page_status, priority, convergence, confidence — unchanged; those remain static.)

- [ ] **Step 2: Run to verify it fails**

Run: `C:/dev/llm-kb-template/.venv/Scripts/pytest tests/test_generic_pipeline.py::test_schema_enums_match_runtime_validators -v`
Expected: FAIL — schema still has `verdict.enum`, so `"enum" not in ev["verdict"]` is False.

- [ ] **Step 3: Change the schema — verdict to generic string**

In `schemas/wiki-page.schema.json`, replace line 48:

```json
          "verdict": { "enum": ["CONFIRMED", "LIKELY", "HYPOTHESIS"] },
```

with:

```json
          "verdict": {
            "type": "string",
            "description": "One of kb.config.json verdicts[].name (or the legacy default set when no ladder is configured) — membership is checked at runtime by lint_wiki.py, not here."
          },
```

Leave the `allOf` block (lines 53–65) unchanged: `verdict` is still `required` when confidence is High/Medium; only its value-domain moved to runtime.

- [ ] **Step 4: Run to verify the drift-guard passes**

Run: `C:/dev/llm-kb-template/.venv/Scripts/pytest tests/test_generic_pipeline.py::test_schema_enums_match_runtime_validators -v`
Expected: PASS.

- [ ] **Step 5: Run schema fixture tests**

Run: `C:/dev/llm-kb-template/.venv/Scripts/pytest tests/test_schemas.py -v`
Expected: PASS (generic string is more permissive; existing CONFIRMED/LIKELY fixtures still validate).

- [ ] **Step 6: Commit**

```bash
git -C C:/dev/llm-kb-template add schemas/wiki-page.schema.json tests/test_generic_pipeline.py
git -C C:/dev/llm-kb-template commit -m "refactor: verdict is a generic string in wiki schema; drift-guard mirrors source_types"
```

---

### Task 5: `lint_wiki.py` — config-driven `VALID_VERDICT`

**Files:**
- Modify: `scripts/lint_wiki.py:20`, `scripts/lint_wiki.py:173-175`
- Test: `tests/test_configurable_verdict.py` (add lint membership tests)

- [ ] **Step 1: Write failing tests for config-driven verdict membership**

Add to `tests/test_configurable_verdict.py`:

```python
_LADDER_TOPIC = """---
topic: Subagent Write Sets
page_status: partial
priority: P0
updated: 2026-07-03
see_also: []
tldr: >
  Give each subagent a disjoint write-set.
source_quality:
  convergence: partial
evidence:
  - claim: "disjoint write-sets prevent parallel-agent conflicts"
    sources:
      - type: internal-lineage
        ref: "run:h2t-skills/2026-07-10-practice-harvest"
        replicated: true
    confidence: Medium
    verdict: HYPOTHESIS
---

## Body
x.
"""


def test_lint_accepts_ladder_verdict(tmp_path):
    cfg = _cfg(
        source_types=["internal-lineage"],
        judges=["Realizability", "Generalization", "Falsification"],
        verdicts=_LADDER,
    )
    kb = _make_kb(tmp_path, cfg)
    (kb / "wiki" / "t.md").write_text(_LADDER_TOPIC, encoding="utf-8")
    r = _run(kb, "lint_wiki.py", "wiki/t.md")
    assert r.returncode == 0, r.stdout + r.stderr


def test_lint_rejects_verdict_outside_ladder(tmp_path):
    cfg = _cfg(
        source_types=["internal-lineage"],
        judges=["Realizability", "Generalization", "Falsification"],
        verdicts=_LADDER,
    )
    kb = _make_kb(tmp_path, cfg)
    # CONFIRMED is legacy-only; not in this domain's ladder.
    topic = _LADDER_TOPIC.replace("verdict: HYPOTHESIS", "verdict: CONFIRMED")
    (kb / "wiki" / "t.md").write_text(topic, encoding="utf-8")
    r = _run(kb, "lint_wiki.py", "wiki/t.md")
    assert r.returncode == 1
    assert "verdict must be one of" in r.stdout
```

- [ ] **Step 2: Run to verify failure**

Run: `C:/dev/llm-kb-template/.venv/Scripts/pytest tests/test_configurable_verdict.py -k "ladder_verdict or outside_ladder" -v`
Expected: `test_lint_rejects_verdict_outside_ladder` FAILS (lint currently uses the hardcoded set, which INCLUDES CONFIRMED, so it wrongly passes).

- [ ] **Step 3: Make `VALID_VERDICT` runtime-populated**

In `scripts/lint_wiki.py`, change line 20 from a hardcoded set to a module global default, mirroring `VALID_SOURCE_TYPES`:

```python
VALID_CONFIDENCE = {"High", "Medium", "Low"}
# VALID_VERDICT is loaded per-domain from kb.config.json in main() (mirrors
# VALID_SOURCE_TYPES). Default = legacy flat enum for direct-import callers.
VALID_VERDICT: set = {"CONFIRMED", "LIKELY", "HYPOTHESIS"}
```

Then in `main()` (around lines 173–175), populate it from config alongside `VALID_SOURCE_TYPES`:

```python
    global VALID_SOURCE_TYPES, VALID_VERDICT
    cfg = load_config()
    VALID_SOURCE_TYPES = set(cfg["source_types"])
    VALID_VERDICT = valid_verdicts(cfg)
```

Add the import at the top (line 13 area, next to `from _kbconfig import load_config`):

```python
from _kbconfig import load_config, valid_verdicts
```

- [ ] **Step 4: Run to verify tests pass**

Run: `C:/dev/llm-kb-template/.venv/Scripts/pytest tests/test_configurable_verdict.py -k "ladder_verdict or outside_ladder" -v`
Expected: PASS (both).

- [ ] **Step 5: Verify golden gate + generic pipeline still green**

Run: `C:/dev/llm-kb-template/.venv/Scripts/pytest tests/test_backcompat_golden.py tests/test_generic_pipeline.py -v`
Expected: PASS (legacy default set unchanged; the drift-guard now checks direct-import default `{CONFIRMED, LIKELY, HYPOTHESIS}` matches nothing in schema — but it asserts absence of enum, so fine).

- [ ] **Step 6: Commit**

```bash
git -C C:/dev/llm-kb-template add scripts/lint_wiki.py tests/test_configurable_verdict.py
git -C C:/dev/llm-kb-template commit -m "feat: lint_wiki loads VALID_VERDICT from kb.config verdicts ladder"
```

---

### Task 6: `lint_wiki.py` — council-completeness enforcement (gated on explicit ladder)

Enforces the P1-residual invariant: **when an explicit `verdicts` ladder is configured**, a claim whose `verdict` rank > 0 (promoted above base hypothesis) OR that appears in `tldr`/`decision_triggers` must carry `judge_pass: true`. Gated so legacy configs (no ladder) are unaffected — this preserves the golden gate.

**Files:**
- Modify: `scripts/lint_wiki.py` (`lint_page`, `main`)
- Test: `tests/test_configurable_verdict.py`

- [ ] **Step 1: Write failing tests for council-completeness**

Add to `tests/test_configurable_verdict.py`:

```python
_PROMOTED_TOPIC = """---
topic: Subagent Write Sets
page_status: partial
priority: P0
updated: 2026-07-03
see_also: []
tldr: >
  Give each subagent a disjoint write-set.
source_quality:
  convergence: partial
evidence:
  - claim: "disjoint write-sets prevent parallel-agent conflicts"
    sources:
      - type: internal-lineage
        ref: "run:a"
        replicated: true
      - type: internal-lineage
        ref: "run:b"
        replicated: true
    confidence: High
    verdict: WORKS-IN-PRACTICE
{judge_pass}---

## Body
x.
"""


def _promoted(judge_pass_line: str) -> str:
    return _PROMOTED_TOPIC.format(judge_pass=judge_pass_line)


def _ladder_kb(tmp_path: Path) -> Path:
    cfg = _cfg(
        source_types=["internal-lineage"],
        judges=["Realizability", "Generalization", "Falsification"],
        verdicts=_LADDER,
    )
    return _make_kb(tmp_path, cfg)


def test_promoted_verdict_without_judge_pass_fails(tmp_path):
    kb = _ladder_kb(tmp_path)
    (kb / "wiki" / "t.md").write_text(_promoted(""), encoding="utf-8")
    r = _run(kb, "lint_wiki.py", "wiki/t.md")
    assert r.returncode == 1
    assert "judge_pass" in r.stdout


def test_promoted_verdict_with_judge_pass_passes(tmp_path):
    kb = _ladder_kb(tmp_path)
    (kb / "wiki" / "t.md").write_text(_promoted("    judge_pass: true\n"), encoding="utf-8")
    r = _run(kb, "lint_wiki.py", "wiki/t.md")
    assert r.returncode == 0, r.stdout + r.stderr


def test_rank0_verdict_needs_no_judge_pass(tmp_path):
    # HYPOTHESIS (rank 0) is exempt even under a ladder.
    kb = _ladder_kb(tmp_path)
    (kb / "wiki" / "t.md").write_text(_LADDER_TOPIC, encoding="utf-8")
    r = _run(kb, "lint_wiki.py", "wiki/t.md")
    assert r.returncode == 0, r.stdout + r.stderr


def test_legacy_promoted_verdict_needs_no_judge_pass(tmp_path):
    # No ladder configured -> enforcement OFF, CONFIRMED without judge_pass is fine.
    cfg = _cfg(source_types=["internal-lineage"], judges=["A", "B", "C"])
    kb = _make_kb(tmp_path, cfg)
    topic = _promoted("").replace("verdict: WORKS-IN-PRACTICE", "verdict: CONFIRMED")
    (kb / "wiki" / "t.md").write_text(topic, encoding="utf-8")
    r = _run(kb, "lint_wiki.py", "wiki/t.md")
    assert r.returncode == 0, r.stdout + r.stderr
```

- [ ] **Step 2: Run to verify failure**

Run: `C:/dev/llm-kb-template/.venv/Scripts/pytest tests/test_configurable_verdict.py -k "judge_pass or rank0" -v`
Expected: `test_promoted_verdict_without_judge_pass_fails` FAILS (no enforcement yet — lint passes it).

- [ ] **Step 3: Implement gated council-completeness in `lint_wiki.py`**

`lint_page` needs the verdict ranks and the gating flag. Since `lint_page` currently takes only `path`, thread them via module globals set in `main()` (same pattern as `VALID_SOURCE_TYPES`/`VALID_VERDICT`). Add near the other globals:

```python
VERDICT_RANKS: dict = {}
ENFORCE_COUNCIL_COMPLETENESS: bool = False
```

In the evidence loop of `lint_page`, inside the `else:` branch that already reads `verdict` (currently lines 116–123, the High/Medium branch), after the membership check add the council-completeness check:

```python
        else:
            all_are_single_source = False
            verdict = claim_obj.get("verdict")
            if verdict not in VALID_VERDICT:
                violations.append(
                    f"{label}: verdict must be one of {sorted(VALID_VERDICT)} "
                    f"when confidence is High/Medium, got: {verdict!r}"
                )
            elif ENFORCE_COUNCIL_COMPLETENESS and VERDICT_RANKS.get(verdict, 0) > 0:
                if claim_obj.get("judge_pass") is not True:
                    violations.append(
                        f"{label}: verdict {verdict!r} is above rank-0 but judge_pass is not true "
                        f"— a promoted verdict requires a passed council"
                    )
```

Then in `main()`, populate the two globals from config:

```python
    global VALID_SOURCE_TYPES, VALID_VERDICT, VERDICT_RANKS, ENFORCE_COUNCIL_COMPLETENESS
    cfg = load_config()
    VALID_SOURCE_TYPES = set(cfg["source_types"])
    VALID_VERDICT = valid_verdicts(cfg)
    VERDICT_RANKS = verdict_ranks(cfg)
    ENFORCE_COUNCIL_COMPLETENESS = has_explicit_ladder(cfg)
```

Update the import:

```python
from _kbconfig import load_config, valid_verdicts, verdict_ranks, has_explicit_ladder
```

- [ ] **Step 4: Run to verify council-completeness tests pass**

Run: `C:/dev/llm-kb-template/.venv/Scripts/pytest tests/test_configurable_verdict.py -k "judge_pass or rank0 or legacy_promoted" -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Full suite + golden gate**

Run: `C:/dev/llm-kb-template/.venv/Scripts/pytest tests/ -v`
Expected: PASS (all — golden gate green proves legacy path untouched; enforcement only fires under an explicit ladder).

- [ ] **Step 6: Commit**

```bash
git -C C:/dev/llm-kb-template add scripts/lint_wiki.py tests/test_configurable_verdict.py
git -C C:/dev/llm-kb-template commit -m "feat: enforce council-completeness for promoted verdicts under explicit ladder"
```

---

### Task 7: Docs — `CLAUDE.template.md` + `README.md`

**Files:**
- Modify: `CLAUDE.template.md`
- Modify: `README.md`

- [ ] **Step 1: Document the surface in `CLAUDE.template.md`**

Add a subsection documenting the two optional config keys and the legacy-vs-ladder behavior. Insert after the trust-weights/verdict documentation block:

```markdown
### Verdict ladder & strength axis (optional, per-domain)

By default a KB uses the legacy flat verdict enum `CONFIRMED | LIKELY | HYPOTHESIS`
and `strength_axis: source_group_convergence`. To customize, add to `kb.config.json`:

- `verdicts`: an ordered ladder of `{ name, rank, promote_when }`. Ranks must be
  contiguous from 0 and unique; rank-0 is the base hypothesis (needs no council).
  Any verdict with rank > 0 is "promoted" and **requires `judge_pass: true`** on the
  claim (runtime-enforced by `lint_wiki.py`). Verdict membership is validated at
  runtime against this list — the JSON schema types `verdict` as a generic string.
- `strength_axis`: `source_group_convergence` (default) or `domain_recurrence`.

When `verdicts` is absent, behavior is byte-identical to prior versions
(no council-completeness enforcement, legacy enum). See
`tests/test_backcompat_golden.py`.
```

- [ ] **Step 2: Document in `README.md`**

In the install-protocol / config section of `README.md`, add a bullet noting the two optional keys and pointing to `CLAUDE.template.md` for the ladder rules. One paragraph, consistent with existing README tone.

```markdown
- **Optional verdict customization:** `kb.config.json` accepts a `verdicts` ladder
  and a `strength_axis` (`source_group_convergence` | `domain_recurrence`). Omit both
  for the legacy `CONFIRMED/LIKELY/HYPOTHESIS` enum. Under an explicit ladder,
  promoted verdicts (rank > 0) require a passed council (`judge_pass: true`).
```

- [ ] **Step 3: Full suite (docs don't affect tests, but confirm nothing broke)**

Run: `C:/dev/llm-kb-template/.venv/Scripts/pytest tests/ -v`
Expected: PASS (all).

- [ ] **Step 4: Commit**

```bash
git -C C:/dev/llm-kb-template add CLAUDE.template.md README.md
git -C C:/dev/llm-kb-template commit -m "docs: document optional verdict ladder + strength_axis"
```

---

## Acceptance (maps to spec A1 criteria)

- [x] verdict/strength-axis configurable via path (b): generic string in schema + runtime membership (Tasks 4, 5).
- [x] meta-schema validates ladder shape (rank monotonic+unique, rank-0 present) — declarative in `kb.config.schema.json` + runtime in `_kbconfig.py` (Tasks 2, 3).
- [x] `lint_wiki` enforces verdict-membership + council-completeness (Tasks 5, 6).
- [x] back-compat golden gate PASS — byte-identical legacy output (Task 1, re-verified each task).
- [x] tests green + configurable-verdict test (`tests/test_configurable_verdict.py`).
- [ ] **DEFERRED to #295:** `synthesize_council` derives+writes verdict (documented above — MVP=HYPOTHESIS-only makes derivation a rank-0 no-op until the application-outcome bridge exists).

## Self-review notes

- **Type consistency:** helper names used consistently — `valid_verdicts`, `verdict_ranks`, `has_explicit_ladder`, `strength_axis` (defined in Task 2, imported in Tasks 5–6). Globals `VALID_VERDICT`, `VERDICT_RANKS`, `ENFORCE_COUNCIL_COMPLETENESS` populated in `main()`.
- **Spec coverage gap intentionally left:** synthesize_council verdict derivation (see Deferred). All other A1 acceptance lines have a task.
- **Golden gate is re-run after every code task** (Tasks 2, 5, 6) — the back-compat guarantee is continuously checked, not just once.
- **Risk — direct-import default:** `lint_page` uses module globals; direct-import callers (the drift-guard test) get the legacy defaults set at module load. Subprocess runs (all real tests) go through `main()` which sets them from config. This mirrors the existing `VALID_SOURCE_TYPES` contract.
- **Partial coverage — council-completeness:** the spec phrases the rule as "verdict rank > 0 **OR** claim appears in tldr/decision_triggers". Task 6 enforces the **verdict-rank half** cleanly. The tldr/decision_triggers half is NOT enforced per-claim because the frontmatter has no structural claim↔trigger link (decision_triggers is a free array; tldr is prose). This is acceptable for the MVP: everything is `HYPOTHESIS` (rank 0), so the rule never fires until promotion becomes reachable (#295), which is also where the claim↔trigger linkage should be designed. Flagged so it is a conscious deferral, not an oversight.
