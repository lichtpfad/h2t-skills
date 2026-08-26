---
title: "h2t-ops Connector Development Runbook — Implementation Plan"
status: "draft"
date: "2026-05-19"
milestone: ""
---
# h2t-ops Connector Development Runbook — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce `plugins/h2t-ops/references/h2t-connector-runbook.md` — a procedural-index runbook that an agent follows to add or migrate a connector to the h2t-ops standard, referencing (never duplicating) the TZ-0 spec, the API coverage audit, and the POS boundary.

**Architecture:** Docs-only. One Markdown deliverable built incrementally over 6 tasks that mirror the approved design (`docs/superpowers/specs/2026-05-19-h2t-ops-connector-runbook-design.md`). The runbook uses **stable file-path references by default** and **`file:line` anchors only for 6 load-bearing patterns**. No connector code, no test code, no new skill is created.

**Tech Stack:** Markdown only. Verification is `grep`/`git status` (no pytest — the deliverable is documentation; the "test" of each task is that every cited path resolves, each load-bearing anchor still points at the right symbol, and zero connector/test code changed).

---

## Authoritative inputs (do not duplicate their content into the runbook)

| Input | Path |
|---|---|
| Design (this plan's spec) | `docs/superpowers/specs/2026-05-19-h2t-ops-connector-runbook-design.md` |
| TZ-0 connector architecture spec | `docs/superpowers/specs/2026-05-18-h2t-connector-architecture-design.md` |
| API coverage audit (9-item checklist source) | `docs/reports/2026-05-19-h2t-ops-api-coverage-audit.md` |
| Roadmap (#138 section; 9-item checklist verbatim) | `docs/h2t-ops-roadmap.md` |
| POS operational boundary | `plugins/h2t-ops/references/pos-operational-boundary.md` |
| Testing plan (G-gates, evidence format) | `docs/h2t-ops-testing-plan.md` |

## The 6 load-bearing `file:line` anchors (verified 2026-05-19, HEAD `bc44056`)

These are the ONLY places the runbook may use `file:line`. Everything else is path-only.

| # | Pattern | Anchor | Expected symbol on that line |
|---|---|---|---|
| 1 | ConnectorSpec definition | `h2t_ops/core/registry.py:14` | `class ConnectorSpec:` |
| 1b | ConnectorSpec usage (canon) | `h2t_ops/connectors/notion/__init__.py:5` | `CONNECTOR = ConnectorSpec(` |
| 2 | Lazy client string | `h2t_ops/connectors/notion/__init__.py:8` | `client="h2t_ops.connectors.notion.client:NotionClient"` |
| 3 | cli `_MIGRATED` set | `h2t_ops/cli.py:18` | `_MIGRATED = {"notion", "gmail"}` |
| 3b | cli ingest shim | `h2t_ops/cli.py:107` | `# ingest notion shim → new connector (spec §10)` |
| 4 | Error map (HTTP→typed) | `h2t_ops/connectors/gmail/client.py:137` | `def _map_http_error(e: Exception, *, op: str):` |
| 4b | Exit-code table | `h2t_ops/core/errors.py:39` | `EXIT_CODES: dict[str, int] = {` |
| 5 | `emit()` call site | `h2t_ops/core/output.py:61` | `def emit(provider: str, *, result: Any = None, exc: ...` |
| 5b | Envelope builders | `h2t_ops/core/envelope.py:9` | `def success_envelope(provider: str, result: Any)` |
| 6 | POS boundary rule | `plugins/h2t-ops/references/pos-operational-boundary.md:28` | `- Skills must not write directly to \`~/.dor/pos.db\`.` |
| 6b | Proposed-capture contract | `plugins/h2t-ops/references/pos-operational-boundary.md:39` | `## Structured Proposed Capture` |

Stable **path-only** references (routine — never line-anchored):
`h2t_ops/connectors/notion/{__init__,client,commands}.py`,
`h2t_ops/connectors/gmail/{__init__,client,commands}.py`,
`h2t_ops/core/{registry,errors,output,envelope,secrets}.py`, `h2t_ops/cli.py`,
`tests/connectors/{notion,gmail}/test_{client,commands}.py`.

## Per-task verification (run at the end of EVERY task)

> **Shell:** these verification commands are written for Git Bash / Claude Bash
> on Windows. If executing from PowerShell, use `Select-String` (and `Test-Path`)
> equivalents — do **not** skip the checks.

```bash
cd C:/dev/h2t-skills
# A. zero connector/test/skill code touched (docs-only gate)
git status --porcelain -- h2t_ops/ tests/ plugins/h2t-ops/skills/ | grep . \
  && echo "VIOLATION: non-docs file changed" || echo "OK: docs-only"
# B. only the runbook (and in Task 6 also the roadmap) is modified
git status --porcelain -- plugins/h2t-ops/references/h2t-connector-runbook.md
# C. every load-bearing anchor still resolves to its symbol
grep -n 'class ConnectorSpec:' h2t_ops/core/registry.py            # expect :14
grep -n 'CONNECTOR = ConnectorSpec(' h2t_ops/connectors/notion/__init__.py  # expect :5
grep -n 'client="h2t_ops.connectors.notion.client:NotionClient"' h2t_ops/connectors/notion/__init__.py  # expect :8
grep -n '_MIGRATED = {"notion", "gmail"}' h2t_ops/cli.py            # expect :18
grep -n 'ingest notion shim' h2t_ops/cli.py                        # expect :107
grep -n 'def _map_http_error' h2t_ops/connectors/gmail/client.py    # expect :137
grep -n 'EXIT_CODES: dict\[str, int\] = {' h2t_ops/core/errors.py   # expect :39
grep -n 'def emit(provider: str' h2t_ops/core/output.py             # expect :61
grep -n 'def success_envelope' h2t_ops/core/envelope.py             # expect :9
grep -n 'must not write directly to' plugins/h2t-ops/references/pos-operational-boundary.md  # expect :28
```

If any anchor line number drifted, update the runbook to the new line in the SAME task before committing (anchors must be correct at every commit).

---

### Task 1: Create runbook file — front-matter + Reference Map (design task 1)

**Files:**
- Create: `plugins/h2t-ops/references/h2t-connector-runbook.md`

- [ ] **Step 1: Create the file with front-matter and the verified Reference Map**

Write exactly this content:

````markdown
# h2t-ops Connector Development Runbook

**Status:** Active procedure
**Model:** procedural index — this runbook tells you WHAT to do and WHERE the
canonical pattern lives. It does not restate architecture. When this runbook and
an authority document disagree, the authority wins.

## Authority order

1. TZ-0 connector architecture spec —
   `docs/superpowers/specs/2026-05-18-h2t-connector-architecture-design.md`
2. API coverage audit (2026-05-19) —
   `docs/reports/2026-05-19-h2t-ops-api-coverage-audit.md`
3. POS operational boundary —
   `plugins/h2t-ops/references/pos-operational-boundary.md`
4. Testing plan — `docs/h2t-ops-testing-plan.md`
5. Notion / Gmail connector code — the pattern to copy.

## Reference map

Default to **stable file paths**. `file:line` is used ONLY for the load-bearing
patterns below; line numbers are verified and updated whenever this runbook is
edited (routine code is path-only because line anchors drift).

| Pattern | Anchor |
|---|---|
| ConnectorSpec class | `h2t_ops/core/registry.py:14` |
| ConnectorSpec usage (canon) | `h2t_ops/connectors/notion/__init__.py:5` |
| Lazy client string | `h2t_ops/connectors/notion/__init__.py:8` |
| cli `_MIGRATED` set | `h2t_ops/cli.py:18` |
| cli ingest shim | `h2t_ops/cli.py:107` |
| Error map (HTTP→typed) | `h2t_ops/connectors/gmail/client.py:137` |
| Exit-code table | `h2t_ops/core/errors.py:39` |
| `emit()` call site | `h2t_ops/core/output.py:61` |
| Envelope builders | `h2t_ops/core/envelope.py:9` |
| POS "no `~/.dor` write" rule | `plugins/h2t-ops/references/pos-operational-boundary.md:28` |
| Proposed-capture contract | `plugins/h2t-ops/references/pos-operational-boundary.md:39` |

Path-only reference implementations:
`h2t_ops/connectors/notion/` (read-centric) and `h2t_ops/connectors/gmail/`
(read + write + OAuth); core: `h2t_ops/core/`; tests:
`tests/connectors/{notion,gmail}/`.
````

- [ ] **Step 2: Verify anchors + docs-only gate**

Run the **Per-task verification** block above. Expected: `OK: docs-only`, runbook file shows as the only `??`/` M` entry, and every `grep -n` prints the expected line number. Fix any drifted anchor in the file before committing.

- [ ] **Step 3: Commit**

```bash
git add plugins/h2t-ops/references/h2t-connector-runbook.md
git commit -m "docs(h2t-ops): connector runbook — front-matter + reference map (#138)"
```

---

### Task 2: Runbook skeleton — 8 section headings + anchoring-policy note (design task 2)

**Files:**
- Modify: `plugins/h2t-ops/references/h2t-connector-runbook.md`

- [ ] **Step 1: Append the 8 empty section headings and the anchoring-policy note**

Append exactly:

````markdown
## Reference anchoring policy

Stable file paths by default. `file:line` ONLY for: ConnectorSpec, lazy client
string, cli `_MIGRATED`/shim, error map, `emit()`/envelope, POS boundary rule.
Routine code is path-only — line anchors there drift and make this runbook
brittle. When you edit this runbook, re-verify the anchors in the Reference map.

## 1. When to use / scope

## 2. Reference implementations

## 3. Step-by-step procedure

## 4. API coverage checklist (review gate)

## 5. Error and exit-code map

## 6. Output contract

## 7. POS boundary and distribution-without-POS gate

## 8. Definition of Done / PR gate
````

- [ ] **Step 2: Verify**

Run the **Per-task verification** block. Expected: `OK: docs-only`; only the runbook modified; all anchors resolve.

- [ ] **Step 3: Commit**

```bash
git add plugins/h2t-ops/references/h2t-connector-runbook.md
git commit -m "docs(h2t-ops): connector runbook — section skeleton + anchoring policy (#138)"
```

---

### Task 3: Fill sections 1–3 — scope, reference implementations, step-by-step (design task 3)

**Files:**
- Modify: `plugins/h2t-ops/references/h2t-connector-runbook.md`

- [ ] **Step 1: Replace the three empty headings with this content**

Replace `## 1. When to use / scope`, `## 2. Reference implementations`, and `## 3. Step-by-step procedure` (and nothing else) with:

````markdown
## 1. When to use / scope

Use this runbook to add or migrate a **connector**: a stateless client over an
external provider API exposed as `h2t-ops <name> ...`.

A connector is in scope only if it is pure provider I/O. The following are NOT
connector work — they belong to a coordinator/POS layer, never inside the
connector (authority: `plugins/h2t-ops/references/pos-operational-boundary.md`):

- writing `~/.dor/**` (lake, context, journal), `pos.db`, `dor.db`, vault;
- interpretation/summarisation that turns provider data into POS memory;
- multi-step sync/cron/webhook workflows.

If a legacy script mixes reads with the above, migrate ONLY the pure-API reads
and record the excluded side-effecting subcommands explicitly (see the audit
"inventory gate" connectors: Drive/MeetGeek/Telegram).

## 2. Reference implementations

Copy the pattern from the connector closest to your case:

- **Notion** — `h2t_ops/connectors/notion/` — read-centric: token auth, no OAuth
  browser flow, block/markdown normalisation.
- **Gmail** — `h2t_ops/connectors/gmail/` — the fuller case: OAuth token reuse
  (no interactive browser), read + write ops, HTTP→typed error mapping.

Each connector is exactly three files plus tests:

| File | Responsibility | Canon |
|---|---|---|
| `__init__.py` | `CONNECTOR = ConnectorSpec(...)` only | `h2t_ops/connectors/notion/__init__.py:5` |
| `client.py` | provider API logic, typed errors, lazy SDK import | `h2t_ops/connectors/notion/client.py` |
| `commands.py` | argparse subcommands → client calls; no provider logic | `h2t_ops/connectors/notion/commands.py` |
| `tests/connectors/<name>/test_{client,commands}.py` | API + CLI contract | `tests/connectors/notion/` |

## 3. Step-by-step procedure

1. **Create the package.** `h2t_ops/connectors/<name>/{__init__,client,commands}.py`.
   Mirror the layout of `h2t_ops/connectors/notion/`.

2. **Write `client.py`.** Re-wrap the legacy logic (do not rewrite behaviour).
   - Lazy-import the heavy SDK INSIDE the method/`__init__`, never at module
     scope (keeps `h2t-ops --help`/`connectors` cheap).
   - Map provider/HTTP failures to the typed hierarchy; copy the shape of
     `_map_http_error` at `h2t_ops/connectors/gmail/client.py:137`.
   - Missing creds/SDK → `ConfigError`; refused/expired auth → `AuthError`;
     never launch an interactive browser flow.

3. **Write `commands.py`.** One argparse subparser per verb; each handler calls
   the client and returns a result object — it must NOT build envelopes or print.
   Mirror `h2t_ops/connectors/notion/commands.py`.

4. **Write `__init__.py`.** Exactly one `CONNECTOR = ConnectorSpec(...)`. The
   `client=` value is the **lazy string** `"h2t_ops.connectors.<name>.client:<Class>"`
   — see `h2t_ops/connectors/notion/__init__.py:8`. `ConnectorSpec` is defined at
   `h2t_ops/core/registry.py:14`; it is discovered automatically — never import
   the client at registration.

5. **Wire the CLI.** Add `"<name>"` to `_MIGRATED` at `h2t_ops/cli.py:18`. If a
   legacy `h2t ingest <name>` path exists, add a deprecation shim mirroring the
   ingest shim at `h2t_ops/cli.py:107` (warns on human output, silent under
   `--json`).

6. **Tests.** API happy path + typed-error mapping + CLI contract
   (`--json`, human, `--help`, shim) + the lazy-registry guard. Migrate any
   legacy normalise tests. Pattern: `tests/connectors/gmail/`.

7. **Live smoke.** Read-only live E2E through the installed CLI; record evidence
   in the issue per `docs/h2t-ops-testing-plan.md`.

Common pitfalls: module-scope SDK import (breaks `--help`); building the
envelope inside `commands.py` (envelope is `emit()`'s job); interactive OAuth in
`client.py` (forbidden — must raise `ConfigError`); silently dropping a legacy
subcommand instead of documenting the exclusion.
````

- [ ] **Step 2: Verify**

Run the **Per-task verification** block. Expected: `OK: docs-only`; only the runbook modified; all anchors resolve (especially `:137`, `:18`, `:107`, `:5`, `:8`, `:14`).

- [ ] **Step 3: Commit**

```bash
git add plugins/h2t-ops/references/h2t-connector-runbook.md
git commit -m "docs(h2t-ops): connector runbook — scope, references, procedure (#138)"
```

---

### Task 4: Fill sections 4–8 — checklist, error/output, POS gate, DoD (design task 4)

**Files:**
- Modify: `plugins/h2t-ops/references/h2t-connector-runbook.md`

- [ ] **Step 1: Replace the five remaining empty headings with this content**

Replace `## 4. ...` through `## 8. ...` (and nothing else) with:

````markdown
## 4. API coverage checklist (review gate)

Every connector PR must pass the **9-item API coverage checklist**. It is
maintained verbatim in the roadmap — do not copy it here (single source of
truth): see `docs/h2t-ops-roadmap.md`, section
`skills: [M3] Add connector development skill runbook — #138` →
"API coverage checklist (required gate for every connector PR)".

The nine gates, by name (full text in the roadmap): 1 legacy parity ·
2 provider API gaps · 3 auth/secrets · 4 lazy imports · 5 tests · 6 live smoke ·
7 POS boundary · 8 distribution-without-POS · 9 write side effects.

A reviewer who cannot point each gate at concrete evidence must block the PR.

## 5. Error and exit-code map

Raise the typed hierarchy in `h2t_ops/core/errors.py`; never `sys.exit` or print
from a client. The exit-code table is `EXIT_CODES` at
`h2t_ops/core/errors.py:39` (resolved by `exit_code_for`). Map provider/HTTP
failures with the same shape as `_map_http_error`
(`h2t_ops/connectors/gmail/client.py:137`):

- bad arguments → `UsageError` (2)
- missing/!resolvable creds or SDK → `ConfigError` (3)
- refused/expired auth → `AuthError` (4)
- provider 4xx/5xx → `ProviderError` (1)
- missing resource → `NotFoundError` (5)
- transport/timeout → `NetworkError` (6)

## 6. Output contract

`commands.py` returns a result object; it never prints. `emit()`
(`h2t_ops/core/output.py:61`) renders it through the universal envelope
(`success_envelope`/`error_envelope` at `h2t_ops/core/envelope.py:9`) honoring
`--json` / `--format md` / human. Do not hand-build envelopes in a connector.

## 7. POS boundary and distribution-without-POS gate

Authority: `plugins/h2t-ops/references/pos-operational-boundary.md`.

- A connector imports no `pos`/`dor.db`/`vault`/`lake` and must run with POS
  absent. It must not write `~/.dor/**` — see the rule at
  `plugins/h2t-ops/references/pos-operational-boundary.md:28`.
- Default any output path to stdout, not `~/.dor/`.

Provider write commands are allowed only as explicit CLI verbs with clear user
intent (e.g. `send`, `label`, `create`, `delete`). They must be classified in
the API coverage checklist as write side effects and covered by tests.

A synthesis/coordinator workflow must not auto-execute provider writes. If an
agent discovery implies a task/decision/action and POS journal/action commands
are unavailable, emit a structured `proposed_capture`
(`plugins/h2t-ops/references/pos-operational-boundary.md:39`) instead of
mutating POS/vault/lake or silently performing workflow writes.

## 8. Definition of Done / PR gate

A connector is done only when (authority: `docs/h2t-ops-testing-plan.md`):

- the 9-item checklist (§4) passes with evidence;
- CI + mocked API/CLI tests green; lazy-registry guard covers the new SDK;
- read-only live E2E through the **installed** CLI passed, evidence in the issue
  in the testing-plan format;
- legacy entrypoint preserved until its users migrate;
- no connector code outside the new package changed; POS boundary held.
````

- [ ] **Step 2: Verify**

Run the **Per-task verification** block. Expected: `OK: docs-only`; only the runbook modified; anchors `:39`, `:137`, `:61`, `:9`, `:28`, `:39`(boundary) resolve.

- [ ] **Step 3: Commit**

```bash
git add plugins/h2t-ops/references/h2t-connector-runbook.md
git commit -m "docs(h2t-ops): connector runbook — checklist, errors, output, POS gate, DoD (#138)"
```

---

### Task 5: Self-review against the 9-item checklist + dead-reference sweep (design task 5)

**Files:**
- Modify: `plugins/h2t-ops/references/h2t-connector-runbook.md` (only if the sweep finds a fix)

- [ ] **Step 1: Dead-reference sweep — every cited path resolves**

```bash
cd C:/dev/h2t-skills
# Extract every backticked path/anchor from the runbook and assert it exists.
grep -oE '`[a-zA-Z0-9_./-]+\.(py|md)(:[0-9]+)?`' \
  plugins/h2t-ops/references/h2t-connector-runbook.md \
  | tr -d '`' | sed 's/:.*//' | sort -u | while read p; do
    test -e "$p" && echo "OK   $p" || echo "DEAD $p"
  done
```
Expected: every line `OK`. Any `DEAD` → fix the reference in the runbook in this task.

- [ ] **Step 2: Re-verify all 11 load-bearing anchors point at the right symbol**

Run section C of the **Per-task verification** block. Each `grep -n` must print the line recorded in the Reference map table. If a line drifted, update both the Reference map and the in-prose anchor in the runbook.

- [ ] **Step 3: Self-review against the 9-item audit checklist**

Open `docs/h2t-ops-roadmap.md` (#138 section) and confirm the runbook’s §3–§8 give an agent a concrete way to satisfy each of the 9 gates. For each gate, confirm the runbook names the file/section that proves it. Record the result as a checklist comment block at the end of the runbook:

````markdown
<!-- self-review 2026-05-19: 9-item gate coverage
1 parity §3.2 · 2 provider-gap §4 · 3 auth/secrets §3.2,§5 · 4 lazy §3.2,§3.4
5 tests §3.6 · 6 live smoke §3.7,§8 · 7 POS §7 · 8 dist-no-POS §7 · 9 writes §7
all gates have a concrete runbook locus -->
````

- [ ] **Step 4: Verify + commit (only if a fix or the self-review block was written)**

Run the **Per-task verification** block. Then:

```bash
git add plugins/h2t-ops/references/h2t-connector-runbook.md
git commit -m "docs(h2t-ops): connector runbook — self-review + dead-reference sweep (#138)"
```

If the sweep found nothing to change and you still added the self-review comment block, the commit above still applies (the comment block is a change). If literally nothing changed, skip the commit and note "no fixes needed" in the task report.

---

### Task 6: Reconcile roadmap #138 wording + add roadmap → runbook link (design task 6)

**Files:**
- Modify: `docs/h2t-ops-roadmap.md`

- [ ] **Step 1: Point the #138 roadmap section at the delivered runbook**

In `docs/h2t-ops-roadmap.md`, in the section
`### skills: [M3] Add connector development skill runbook — #138`, locate the
Definition of Done bullet:

```
- `references/h2t-connector-runbook.md` exists.
```

Replace it with:

```
- `plugins/h2t-ops/references/h2t-connector-runbook.md` exists (plugin-level
  references, beside `pos-operational-boundary.md` — no separate skill is
  scaffolded; this satisfies the original "references/h2t-connector-runbook.md"
  intent).
```

And in the same section's **What** list, replace:

```
- Put the long runbook under that skill's `references/` directory.
```

with:

```
- Put the long runbook at `plugins/h2t-ops/references/h2t-connector-runbook.md`
  (plugin-level references; no new skill scaffold).
```

- [ ] **Step 2: Add a Source Documents row for the runbook**

In `docs/h2t-ops-roadmap.md`, in the `## Source Documents` table, after the
API coverage audit row, add:

```
| [Connector development runbook](../plugins/h2t-ops/references/h2t-connector-runbook.md) | Procedural-index recipe for adding/migrating a connector to the h2t-ops standard |
```

- [ ] **Step 3: Verify (docs-only; roadmap + runbook only)**

```bash
cd C:/dev/h2t-skills
git status --porcelain -- h2t_ops/ tests/ plugins/h2t-ops/skills/ | grep . \
  && echo "VIOLATION" || echo "OK: docs-only"
git status --porcelain -- docs/h2t-ops-roadmap.md plugins/h2t-ops/references/h2t-connector-runbook.md
# confirm no OTHER tracked file got staged later
git diff --cached --name-only
```
Expected: `OK: docs-only`; only `docs/h2t-ops-roadmap.md` shows modified this task.

- [ ] **Step 4: Commit**

```bash
git add docs/h2t-ops-roadmap.md
git commit -m "docs(h2t-ops): reconcile #138 runbook wording + link runbook (#138)"
```

---

## Self-Review (run by the plan author after writing — completed)

**1. Spec coverage:** design §Goal→Goal; §Authority order→Task 1 content; §Scope/non-goals→Task 3 §1; §Location→Task 1 + Task 6 reconcile; §Runbook structure (8 sections)→Tasks 2–4; §Anchoring policy→Task 2 + the 6/11 anchor table; §Implementation plan outline (6 tasks)→Tasks 1–6 1:1; §Review gates→Task 5 + this self-review + execution handoff. No gap.

**2. Placeholder scan:** No "TBD/TODO/handle edge cases". Every task ships the literal Markdown to write and concrete `grep` verification with expected output. The 9-item checklist is intentionally referenced (not pasted) — that is the design's DRY decision, not a placeholder.

**3. Consistency:** Anchor line numbers (`registry.py:14`, `notion/__init__.py:5/8`, `cli.py:18/107`, `gmail/client.py:137`, `errors.py:39`, `output.py:61`, `envelope.py:9`, `pos-operational-boundary.md:28/39`) are identical in the Reference Map (Task 1), the per-task verification block, and the in-prose uses (Tasks 3–4). Section numbering 1–8 is consistent between Task 2 skeleton and Tasks 3–4 fills. Deliverable path is identical everywhere. Docs-only gate is enforced in every task.

No issues found.

---

## Constraints (carried from the approved design — every task obeys)

- Docs-only. Zero changes to `h2t_ops/`, `tests/`, or `plugins/h2t-ops/skills/`.
- Deliverable: `plugins/h2t-ops/references/h2t-connector-runbook.md`.
- No new skill scaffold.
- Procedural-index model: reference authority, never duplicate the TZ-0 spec,
  the audit, or the POS ADR.
- Preserve the repo's 25 unrelated dirty files; stage only the files named in
  each task's commit step.
- Each task ends with the per-task verification (paths resolve, anchors correct,
  docs-only gate green) before its commit.
