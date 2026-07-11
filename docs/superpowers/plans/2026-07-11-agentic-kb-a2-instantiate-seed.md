---
title: "Agentic KB — A2: instantiate agentic-kb + seed 40 findings as HYPOTHESIS"
status: "draft"
date: "2026-07-11"
milestone: ""
---

# Agentic KB — A2: instantiate + seed Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax. **This plan is config + data + one throwaway seed script — far lower logic-density than A1. Right-size: fewer tasks, lighter review, no per-task 3-reviewer ceremony.**

**Goal:** Stand up a new standalone `agentic-kb` repo from the A1-upgraded `llm-kb-template`, configured for the agentic-development-methodology domain, and seed the 40 practice-harvest findings as `HYPOTHESIS` atoms — all lint-green.

**Architecture:** Clone the (now A1-upgraded) template, re-init git fresh, write the domain config (with the new `verdicts` ladder + `strength_axis: domain_recurrence`), a 7-topic taxonomy, then a one-shot `seed_from_registry.py` that reads the harvest registry + a finding→topic map and writes 7 topic pages whose `evidence[]` are the 40 findings — every claim `verdict: HYPOTHESIS` (rank-0, so council-completeness does not require `judge_pass`), confidence derived from recurrence. Acceptance = the template's own `pytest` + `lint_wiki` on THIS config, which is also the first real external exercise of A1's ladder + strength_axis + council-completeness.

**Tech Stack:** Python stdlib + PyYAML (runtime), pytest + jsonschema (dev). New repo at `C:/dev/agentic-kb`.

---

## Working repo & preconditions

- **New repo: `C:/dev/agentic-kb`** (does not exist yet — Task 1 creates it). All edits here unless noted.
- Source template: `C:/dev/llm-kb-template` — local `main` must contain A1 (merge `5f0702b`). Verify: `git -C C:/dev/llm-kb-template log --oneline -1`. (Already merged + pulled this session.)
- Seed source: `C:/dev/h2t-skills/docs/reports/2026-07-10-practice-harvest-registry.json` (40 findings).
- Bash tool = git-bash; ONE command per call, NO `&&`/`;`. Python via the new repo's venv: `C:/dev/agentic-kb/.venv/Scripts/python`.

## Scope note (MVP = HYPOTHESIS-only)

- **Every seeded claim is `HYPOTHESIS`.** `WORKS-IN-PRACTICE` is unreachable until the application-outcome bridge (#295) — by design, not a gap.
- **Judges are config-only.** No council runs in the MVP (promotion unreachable), so write the 3 judge definitions but do NOT invest in elaborate prose or run `synthesize_council`.
- **Seed pages are `page_status: stub`** — stub does NOT require `tldr`/`source_quality`; write NO `decision_triggers` and NO asserting `tldr`. Keeps the un-councilled seed epistemology-clean (no claim surfaces as fact) and lint-clean.
- **finding→topic mapping is a judgment first-cut** (several findings straddle topics). Living taxonomy — do not claim precision.

## Confidence + verdict derivation (mechanical, from the registry)

| field | rule |
|---|---|
| `claim` | the finding's `practice` string |
| `sources[]` | one `{type: internal-lineage, ref: "lineage:<repo>", replicated: false}` per entry in `lineage_sources` |
| `confidence` | `Low` if `recurrence == 1` else `Medium` (all sources same-type internal, none replicated → `High` unreachable — honest to MVP) |
| `single_source_warning` | `true` **iff** `confidence == Low` (lint requires it for Low) |
| `verdict` | `HYPOTHESIS` on every claim (rank-0; required for Medium, harmless-but-consistent for Low) |

## finding→topic map (index → taxonomy slug — the one judgment input)

```
verification-gates:      0, 4, 13, 29, 30, 32, 33, 34, 39
extraction-pipelines:    14, 15, 20, 21, 22, 28, 31, 35, 37
environment-portability: 3, 5, 7, 8, 9, 18, 19, 26
evidence-synthesis:      10, 11, 12, 17, 23, 24
autonomous-run:          1, 2, 36, 38
subagent-orchestration:  6, 25
session-continuity:      16, 27
```
(Indices are positions in `registry.json.findings`. Covers all 40; uneven distribution reflects the corpus.)

## File Structure (in `C:/dev/agentic-kb`)

- `kb.config.json` — domain config (Task 2).
- `CLAUDE.md` — from `CLAUDE.template.md` (Task 3).
- `taxonomy.md` — 7 topics (Task 4).
- `data/seed-registry.json` — copy of the harvest registry (Task 5).
- `scripts/seed_from_registry.py` — one-shot seeder (Task 6).
- `wiki/<slug>.md` × 7 — generated topic pages with evidence[] (Task 7 output).
- `index.md` — from `update_index.py` (Task 7).

---

### Task 1: Instantiate the repo (clone A1-upgraded template → fresh git)

- [ ] **Step 1: Verify template main has A1**

Run: `git -C C:/dev/llm-kb-template log --oneline -3`
Expected: shows the A1 merge (`5f0702b`) / configurable-verdict commits.

- [ ] **Step 2: Clone the template locally**

Run: `git clone C:/dev/llm-kb-template C:/dev/agentic-kb`
Expected: `Cloning into 'C:/dev/agentic-kb'... done.`

- [ ] **Step 3: Drop inherited history, re-init fresh**

agentic-kb is its own project (template-upgrade reconciliation is a Project B / #297 concern).

Run: `rm -rf C:/dev/agentic-kb/.git`
Then run: `git -C C:/dev/agentic-kb init`
Expected: `Initialized empty Git repository`.

- [ ] **Step 4: Create venv + install deps**

Run: `python -m venv C:/dev/agentic-kb/.venv`
Then run: `C:/dev/agentic-kb/.venv/Scripts/pip install -r C:/dev/agentic-kb/requirements-dev.txt`
Expected: installs pyyaml + pytest + jsonschema.

- [ ] **Step 5: Baseline — template tests green on the clean clone**

Run: `C:/dev/agentic-kb/.venv/Scripts/pytest C:/dev/agentic-kb/tests/ -q`
Expected: all pass (35) — confirms the A1-upgraded template is intact.

- [ ] **Step 6: Initial commit**

```bash
git -C C:/dev/agentic-kb add -A
git -C C:/dev/agentic-kb commit -m "chore: instantiate agentic-kb from llm-kb-template (A1-upgraded)"
```

---

### Task 2: Domain config (`kb.config.json`) — exercises A1

**Files:** Create `C:/dev/agentic-kb/kb.config.json`.

- [ ] **Step 1: Write the config**

```json
{
  "kb_name": "Agentic KB",
  "domain": "agentic-development-methodology",
  "source_types": [
    "internal-lineage",
    "external-practitioner",
    "external-academic"
  ],
  "judges": [
    "Realizability",
    "Generalization",
    "Falsification"
  ],
  "vote_threshold": null,
  "strength_axis": "domain_recurrence",
  "verdicts": [
    { "name": "HYPOTHESIS", "rank": 0, "promote_when": "start; recurrence signal only, or awaiting council" },
    { "name": "WORKS-IN-PRACTICE", "rank": 1, "promote_when": "council PASS + application-outcome in >=2 independent domains (needs #295 outcome bridge)" }
  ]
}
```

- [ ] **Step 2: Verify A1 accepts it (fail-loud path)**

Run: `C:/dev/agentic-kb/.venv/Scripts/python C:/dev/agentic-kb/scripts/lint_wiki.py C:/dev/agentic-kb/wiki/_template.md`
Expected: config loads with no fail-loud exit. `_template.md` itself may FAIL on its placeholder date — that is fine; it proves A1's loader accepted the `verdicts` ladder + `strength_axis: domain_recurrence`. If it exits with a `strength_axis`/`verdicts` ERROR, the config is malformed — fix before proceeding.

- [ ] **Step 3: Commit**

```bash
git -C C:/dev/agentic-kb add kb.config.json
git -C C:/dev/agentic-kb commit -m "feat: agentic-development-methodology config (verdicts ladder + domain_recurrence)"
```

---

### Task 3: `CLAUDE.md` from template

**Files:** Create `C:/dev/agentic-kb/CLAUDE.md` (from `CLAUDE.template.md`); delete leading HTML comment.

- [ ] **Step 1: Author CLAUDE.md**

Copy `CLAUDE.template.md` → `CLAUDE.md`, fill placeholders:
- `{KB_NAME}` = Agentic KB; `{DOMAIN}` = agentic-development-methodology.
- source groups: **INTERNAL** (`internal-lineage`), **EXTERNAL** (`external-practitioner`, `external-academic`).
- judges (concise — config-only in MVP):
  - **Realizability** — does the practice actually work when applied? PASS: applied in a real run with observed effect. FAIL: aspirational / never exercised.
  - **Generalization** — domain-agnostic mechanism? PASS: works from a general property AND application-outcomes in ≥2 independent domains (distinct repo/task-type/mechanism). FAIL: all one task-type/habit, or domain-specific.
  - **Falsification** — is there a counter-lineage/run where it failed? PASS: survives a genuine attempt to find a counter-case. FAIL: no falsification attempted.
- Keep the A1 "Verdict ladder & strength axis" section; note `strength_axis: domain_recurrence` and that promotion needs the #295 outcome bridge.

- [ ] **Step 2: Commit**

```bash
git -C C:/dev/agentic-kb add CLAUDE.md
git -C C:/dev/agentic-kb commit -m "docs: agentic-kb operating manual (judges, source groups, ladder)"
```

---

### Task 4: Taxonomy (7 topics)

**Files:** Create `C:/dev/agentic-kb/taxonomy.md`.

- [ ] **Step 1: Write taxonomy.md**

```markdown
# Agentic Development Methodology — Taxonomy

## TIER 0 — Orchestration & Execution
| slug | priority |
|------|----------|
| subagent-orchestration | P0 |
| autonomous-run | P0 |

## TIER 1 — Gates & Evidence
| slug | priority |
|------|----------|
| verification-gates | P0 |
| evidence-synthesis | P1 |

## TIER 2 — Pipelines & Continuity
| slug | priority |
|------|----------|
| extraction-pipelines | P1 |
| session-continuity | P1 |
| environment-portability | P2 |
```

- [ ] **Step 2: Commit**

```bash
git -C C:/dev/agentic-kb add taxonomy.md
git -C C:/dev/agentic-kb commit -m "docs: 7-topic taxonomy for agentic-development-methodology"
```

---

### Task 5: Seed data (copy registry into the repo)

**Files:** Create `C:/dev/agentic-kb/data/seed-registry.json`.

- [ ] **Step 1: Copy the registry (self-contained seed)**

Run: `cp C:/dev/h2t-skills/docs/reports/2026-07-10-practice-harvest-registry.json C:/dev/agentic-kb/data/seed-registry.json`
Expected: file present.

- [ ] **Step 2: Commit**

```bash
git -C C:/dev/agentic-kb add data/seed-registry.json
git -C C:/dev/agentic-kb commit -m "data: vendor practice-harvest registry as seed source"
```

---

### Task 6: One-shot seeder `scripts/seed_from_registry.py`

Throwaway migration script — acceptance is "lint green + 40 claims present + spot-check," NOT heavy TDD.

- [ ] **Step 1: Write the seeder**

```python
#!/usr/bin/env python3
"""One-shot seeder: registry findings -> wiki/<topic>.md pages, all HYPOTHESIS.

Reads data/seed-registry.json + the embedded finding->topic map, groups the 40
findings by topic, writes one wiki page per topic. Every claim is verdict
HYPOTHESIS (rank-0 -> council-completeness does not require judge_pass). Confidence
from recurrence (1 lineage -> Low + single_source_warning; else Medium).
Idempotent: overwrites the 7 topic pages from the registry each run.
"""
import json
from pathlib import Path

REPO = Path(__file__).parent.parent
REGISTRY = REPO / "data" / "seed-registry.json"
WIKI = REPO / "wiki"

# index (position in registry.findings) -> taxonomy slug. Judgment first-cut.
TOPIC_MAP = {
    "verification-gates":      [0, 4, 13, 29, 30, 32, 33, 34, 39],
    "extraction-pipelines":    [14, 15, 20, 21, 22, 28, 31, 35, 37],
    "environment-portability": [3, 5, 7, 8, 9, 18, 19, 26],
    "evidence-synthesis":      [10, 11, 12, 17, 23, 24],
    "autonomous-run":          [1, 2, 36, 38],
    "subagent-orchestration":  [6, 25],
    "session-continuity":      [16, 27],
}
PRIORITY = {
    "subagent-orchestration": "P0", "autonomous-run": "P0",
    "verification-gates": "P0", "evidence-synthesis": "P1",
    "extraction-pipelines": "P1", "session-continuity": "P1",
    "environment-portability": "P2",
}
UPDATED = "2026-07-11"


def _title(slug: str) -> str:
    return slug.replace("-", " ").title()


def _yaml_str(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _claim_block(finding: dict) -> list:
    low = finding["recurrence"] == 1
    lines = [f"  - claim: {_yaml_str(finding['practice'])}", "    sources:"]
    for repo in finding["lineage_sources"]:
        lines += [
            "      - type: internal-lineage",
            f"        ref: {_yaml_str('lineage:' + repo)}",
            "        replicated: false",
        ]
    lines.append(f"    confidence: {'Low' if low else 'Medium'}")
    if low:
        lines.append("    single_source_warning: true")
    lines.append("    verdict: HYPOTHESIS")
    return lines


def build_page(slug: str, findings: list) -> str:
    title = _title(slug)
    fm = ["---", f"topic: {title}", "page_status: stub",
          f"priority: {PRIORITY[slug]}", f"updated: {UPDATED}", "evidence:"]
    for f in findings:
        fm += _claim_block(f)
    fm.append("---")
    body = (
        f"\n## {title}\n\n"
        "Harvested practice-hypotheses for this topic. Every claim is `HYPOTHESIS` "
        "(rank-0) — none has passed council. Promotion to `WORKS-IN-PRACTICE` needs "
        "council PASS + application-outcome in >=2 independent domains (see #295).\n"
    )
    return "\n".join(fm) + "\n" + body


def main() -> None:
    findings = json.loads(REGISTRY.read_text(encoding="utf-8"))["findings"]
    WIKI.mkdir(exist_ok=True)
    total = 0
    for slug, idxs in TOPIC_MAP.items():
        page_findings = [findings[i] for i in idxs]
        (WIKI / f"{slug}.md").write_text(build_page(slug, page_findings), encoding="utf-8")
        total += len(page_findings)
        print(f"wrote wiki/{slug}.md ({len(page_findings)} claims)")
    covered = sorted(i for idxs in TOPIC_MAP.values() for i in idxs)
    assert covered == list(range(len(findings))), (
        f"map covers {len(covered)}/{len(findings)} findings — each must map to exactly one topic"
    )
    print(f"seeded {total} claims across {len(TOPIC_MAP)} topics")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run it**

Run: `C:/dev/agentic-kb/.venv/Scripts/python C:/dev/agentic-kb/scripts/seed_from_registry.py`
Expected: 7 `wrote wiki/<slug>.md` lines + `seeded 40 claims across 7 topics`. The coverage assert catches any map gap/overlap.

- [ ] **Step 3: Hold commit until Task 7 (include the index).**

---

### Task 7: Build index + commit

- [ ] **Step 1: Build the index**

Run: `C:/dev/agentic-kb/.venv/Scripts/python C:/dev/agentic-kb/scripts/update_index.py`
Expected: writes `index.md` listing the 7 topics sorted by priority.

- [ ] **Step 2: Commit seeder + generated content**

```bash
git -C C:/dev/agentic-kb add scripts/seed_from_registry.py wiki/ index.md
git -C C:/dev/agentic-kb commit -m "feat: seed 40 practice-harvest findings as HYPOTHESIS atoms across 7 topics"
```

---

### Task 8: Acceptance gate (A1↔A2 integration) — the real done-gate

First exercise of A1's ladder + strength_axis + council-completeness outside A1's own tests. A composition gap surfaces here. **NB (codex review):** the template `pytest` suite builds throwaway fixture configs in `tmp_path` — it does NOT load the repo-root `kb.config.json`. So the actual A1↔A2 integration is exercised ONLY by `lint_wiki.py wiki/` (Step 2), which calls `load_config()` on the real root config. Step 1 confirms the template code is intact; Step 2 is the config-exercising gate.

- [ ] **Step 1: Template code intact (fixture-level, does NOT exercise root config)**

Run: `C:/dev/agentic-kb/.venv/Scripts/pytest C:/dev/agentic-kb/tests/ -q`
Expected: all pass (35). This proves the A1-upgraded template code is intact in the clone; it uses fixture configs, not agentic-kb's root config (that's Step 2).

- [ ] **Step 2: Lint the seeded wiki — the real A1↔A2 integration gate (loads root config)**

Run: `C:/dev/agentic-kb/.venv/Scripts/python C:/dev/agentic-kb/scripts/lint_wiki.py C:/dev/agentic-kb/wiki/`
Expected: `OK:` for all 7 topic pages. If `wiki/_template.md` is still present it will FAIL on its placeholder date — if so, remove it (`git -C C:/dev/agentic-kb rm wiki/_template.md`) and re-lint.
**Key assertion:** every seeded page lints OK under the explicit `verdicts` ladder — proving (a) `HYPOTHESIS` accepted as a ladder member, (b) rank-0 claims need no `judge_pass` (council-completeness exempts them), (c) `strength_axis: domain_recurrence` + ladder loaded without fail-loud.

- [ ] **Step 3: Verify all 40 claims present (no silent drop)**

Run: `C:/dev/agentic-kb/.venv/Scripts/python -c "import glob,yaml; n=sum(len(yaml.safe_load(open(p,encoding='utf-8').read().split('---')[1]).get('evidence',[])) for p in glob.glob('C:/dev/agentic-kb/wiki/*.md') if not p.endswith('_template.md')); print('claims:',n); assert n==40, n"`
Expected: `claims: 40`.

- [ ] **Step 4: Spot-check 2-3 pages**

Read `wiki/subagent-orchestration.md` (2 claims), `wiki/verification-gates.md` (9), and one recurrence-1 (`Low`) claim in `environment-portability` — confirm: `verdict: HYPOTHESIS` everywhere; `single_source_warning: true` exactly on `Low` claims; `internal-lineage` sources match the finding lineages; no `tldr`/`decision_triggers`.

- [ ] **Step 5: Commit any lint fix**

```bash
git -C C:/dev/agentic-kb add -A
git -C C:/dev/agentic-kb commit -m "chore: lint-clean seeded wiki"
```

---

### Task 9: Publish + register (operator-gated)

**Outward-facing — confirm with operator before pushing (new repo). For an autonomous run this is a HARD-STOP: execute Tasks 1-8 autonomously, then STOP here and hand off for operator sign-off on repo creation + push (creating a public/remote repo is not auto-resolvable).**

- [ ] **Step 1: Create the GitHub repo** (operator-gated; choose `--private`/`--public` with operator)

Run: `gh repo create lichtpfad/agentic-kb --private --source C:/dev/agentic-kb --remote origin --push`

- [ ] **Step 2: Register in the h2t ecosystem**

Invoke `h2t-core:init-project` from `C:/dev/agentic-kb` so it surfaces in dev-overview / gather; add domain/id to `~/.h2t/config` registries as prompted.

- [ ] **Step 3: Hand back** the install report: source_types, 3 judges, 7-topic taxonomy, 40 HYPOTHESIS atoms, and the ingest command for the first council run (phase-2 / #295 — not this plan).

---

## Acceptance (maps to spec A2 criteria)

- [x] `agentic-kb` stood up on the A1-upgraded template: config + taxonomy + 3 judges + seed 40 findings **as HYPOTHESIS** (Tasks 1-7).
- [x] `pytest` + `lint_wiki` green on this config (Task 8) — `WORKS-IN-PRACTICE` unreached by design (#295).
- [x] A1↔A2 integration verified: ladder membership + rank-0 council-exemption + `domain_recurrence` axis exercised (Task 8 Step 2).
- [ ] Retrieval MVP + consumer-mapping = **A3** (separate plan).
- [~] One council-run over a P0 topic → **advisory verdicts** (spec A criterion). **Correction (finish-gate):** a council RUN (`parse_claims` → 3 judge sections → `synthesize_council` majority vote → `pipeline-state.json`) is **reachable NOW** — it produces advisory verdicts and needs NOTHING from #295. Only *promotion* to `WORKS-IN-PRACTICE` needs the #295 outcome bridge. The council **write-path was smoke-tested green** in A2's finish-gate (parse_claims on `subagent-orchestration` + synthesize_council under the 3-judge / `vote_threshold: null` config → correct 2-of-3 majority; smoke artifacts reverted, KB stays HYPOTHESIS-only). A full *live* advisory-council pass over P0 topics is deferred to **A3** as low-value-until-#295 (the Generalization judge lacks application-outcome inputs to PASS anything meaningfully), NOT because it is unreachable.

## Self-review notes

- **Epistemology-clean seed:** stub pages, no asserting `tldr`, no `decision_triggers`, all `HYPOTHESIS` — nothing surfaces as fact pre-council.
- **Confidence derivation is honest:** `High` is unreachable (same-type internal sources, no replicated outcome) — the seed cannot overstate strength.
- **finding→topic is a living first-cut** — uneven distribution (gates/pipelines heavy) reflects the corpus, not a modelling error.
- **Seed script is one-shot** — the coverage `assert` (Task 6) + Task 8 acceptance are its verification; no separate test file.
