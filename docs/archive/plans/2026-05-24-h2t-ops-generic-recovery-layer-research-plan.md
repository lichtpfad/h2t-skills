---
title: "h2t-ops Generic Recovery Layer Research Plan"
status: "draft"
date: "2026-05-24"
milestone: ""
---
# h2t-ops Generic Recovery Layer Research Plan

## Objective

Execute a bounded research spike that determines whether `h2t-ops:research`
should add a next generic recovery layer after `direct -> jina`, and if so,
which one.

This is not an implementation plan. It is a decision-making plan.

## Fixed scope

Compare exactly:

1. `Playwright`
2. `Crawl4AI`
3. one hosted/reference comparator:
   - `Firecrawl`
4. implicit baseline:
   - keep `direct -> jina` only

The spike must not expand beyond these unless a comparison becomes impossible
without clarifying a missing category.

## Deliverables

By the end of the spike, we need:

- a capability matrix;
- side-by-side validation notes for at least two failing source cases;
- one explicit decision record;
- a rewrite proposal for `#105`;
- a follow-up split: generic provider work vs site-adapter work.

## Work plan

### T0. Baseline framing

Goal:
freeze the exact baseline we are comparing against.

Actions:

- restate the current `#98` baseline:
  - `direct`
  - `jina`
  - honest `OK / DEGRADED / FAILED`
  - no paywall/login bypass
- list the known failure classes still motivating this spike:
  - JS shell
  - redirect collapse
  - anti-bot / 403 public pages
  - pages requiring browser-rendered DOM to become useful
- confirm validation targets:
  - AllTouchDesigner
  - IIHQ / interactiveimmersive

Deliverable:

- one short baseline section at the top of research notes/report.

No commit required by itself.

### T1. Primary-source comparison

Goal:
build a clean source-grounded comparison of the three candidate classes.

Actions:

- read official docs for:
  - Playwright
  - Crawl4AI
  - Firecrawl or Browserless
- extract only the repo-relevant properties:
  - self-hosting / local-first story
  - JS-render capability
  - anti-bot / browser realism
  - install/runtime weight
  - pricing / free tier / hosted dependency
  - integration shape for a provider rung
  - whether the tool itself uses or depends on LLM/model calls
  - whether total cost includes hidden model-inference cost, not only scraping/runtime cost
  - whether a lighter screenshot-first fallback could cover part of the same problem space

Deliverable:

- capability matrix draft.

Guardrail:

- avoid blogspam and secondary hype unless needed to confirm pricing/setup.

### T2. Minimal practical experiments

Goal:
collect enough real evidence to distinguish theoretical fit from actual value.

Allowed experiment surface:

- one-off local commands;
- disposable test snippets if needed;
- no committed provider implementation.

Actions:

- select at least two concrete failing cases:
  - one AllTD case
  - one IIHQ / interactiveimmersive case
- record baseline `direct -> jina` outcomes
- if practical and lightweight, try candidate-level validation outside repo
  runtime:
  - Playwright one-off fetch/render extraction
  - Crawl4AI one-off fetch/render extraction
  - hosted/reference class only if docs/runtime access is enough to compare
  - screenshot-first fallback using existing site screenshot tooling plus model interpretation
    (`Claude` / `Codex`) to test whether visual capture can serve as a lighter rescue path

Screenshot-first fallback is evaluated only as:

- triage / source identification
- rough human-readable recovery
- a cheap rescue path for “see what is there”

It is **not** to be treated as a substitute for structured DOM/text extraction
when judging whether a new ladder rung should exist.

Deliverable:

- side-by-side table:
  - baseline
  - candidate
  - quality delta
  - interpretation
  - cost delta:
    - scraping/runtime cost
    - model/LLM cost if applicable
    - setup/operator cost

Guardrail:

- if a candidate is too heavy to validate practically in this spike, that is
  itself evidence and must be recorded as such.
- if a candidate requires more than one short setup attempt, account creation,
  or meaningful environment wrestling, stop practical validation for that
  candidate and record “too heavy for bounded spike” as an explicit outcome.

### T3. Decision record

Goal:
end the spike with a forced decision.

Allowed outcomes:

1. adopt `Crawl4AI` as next optional ladder rung
2. adopt `Playwright` as next optional ladder rung
3. defer both; current value does not justify the operational weight
4. conclude that a generic layer is still insufficient and a site adapter is
   justified

The decision record must include:

- chosen outcome
- why alternatives lost
- evidence threshold used
- what follow-up issue(s) should exist
- explicit cost conclusion:
  - Firecrawl out-of-box cost vs local/self-hosted path
  - Crawl4AI runtime cost vs any model-cost component
  - whether screenshot-first fallback is cheap enough to keep as a separate rescue mode

Deliverable:

- final recommendation section in the report/spec follow-up.

### T4. Follow-up split and issue rewrite

Goal:
turn research into clean next actions instead of ambiguity.

Actions:

- decide what belongs to:
  - generic provider implementation
  - site-adapter work
  - connector migration (`#136`)
  - discovery/resolution (`#99`)
- draft rewritten wording for `#105`

Deliverable:

- issue comment or rewrite draft:
  - either replace `#105`
  - or close/supersede it in favor of a better-framed issue

## Acceptance

- exactly three candidate classes are compared;
- comparison is grounded in official/primary sources;
- at least two failing cases are shown baseline-vs-candidate side by side;
- one explicit decision record is produced;
- cost comparison includes both scraping/runtime cost and any model-inference cost;
- screenshot-first fallback is explicitly evaluated as a lighter alternative, not ignored;
- the result is actionable enough to reframe `#105`;
- no production implementation work is mixed into the spike.
