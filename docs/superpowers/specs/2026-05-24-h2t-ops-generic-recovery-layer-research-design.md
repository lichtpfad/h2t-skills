---
title: "h2t-ops Generic Recovery Layer Research Spike"
status: "draft"
owner: "Stanislav Glazov"
date: "2026-05-24"
milestone: ""
---
# h2t-ops Generic Recovery Layer Research Spike

## Goal

Reframe `#105` from "build an AllTouchDesigner-specific adapter" into a
research spike that determines the next **generic** recovery layer for difficult
public web sources after the current `direct -> jina` baseline.

AllTouchDesigner remains a primary validation target, but not the product
boundary.

The output of this task is not a production site adapter. The output is a
decision:

- what recovery layer should be added next, if any;
- how it should sit in the ladder;
- what evidence proves it is worth adopting;
- which work belongs to generic recovery vs site-specific parsing.

## Why the old framing is weak

The original `#105` issue assumes that the right answer is an `alltd.py`
adapter. That is too narrow.

What actually failed in research was not "one site needs custom business
logic", but a broader class of source failures:

- JavaScript-rendered shells;
- anti-bot / 403 / redirect-collapse behavior;
- public pages that require a browser context to become readable;
- sources where direct HTML or Jina are not enough.

If we solve this only for `alltd.org`, we will repeat the same work for IIHQ and
the next difficult source. The better question is:

> What is the next generic recovery layer that improves difficult-but-public
> research sources without turning the stack into vendor lock-in or brittle
> one-off adapters?

## Problem statement

The current fetch ladder baseline is closed under `#98`:

- `direct`
- `jina`
- honest `OK / DEGRADED / FAILED`
- no paywall/login bypass

That baseline is intentionally limited. It does not yet answer:

- should the next step be browser automation or crawler middleware?
- should the next step be local-first, hosted-first, or optional-by-config?
- how much operational weight is acceptable inside `h2t-ops:research`?
- when is a generic rendered-page layer enough, and when is a site adapter still
  needed?

This spike exists to answer those questions with evidence.

## Scope

### In scope

- research free or self-hostable recovery tools for difficult public sites;
- compare generic candidates for rendered / protected / anti-bot pages;
- validate candidates on real known-problem URLs;
- define decision criteria for adoption into the fetch ladder;
- separate generic recovery from site-specific adapter work.

### Out of scope

- building a production AllTouchDesigner parser;
- bypassing login/paywall or protected private content;
- committing to a paid provider as default;
- full connector migration of research runtime;
- author resolution / discovery work from `#99`.

Scope cap:

- this spike compares exactly three classes:
  - `Playwright`
  - `Crawl4AI`
  - one hosted/reference class: `Firecrawl` or `Browserless`
- all other tool categories are out of scope unless one of these comparisons
  exposes a missing class we cannot evaluate honestly without adding it.

## Primary question

Which next-step recovery layer gives the best value after `direct -> jina` for
public but difficult sources?

Candidate classes:

1. `Playwright`
2. `Crawl4AI`
3. one hosted/reference comparator: `Browserless` or `Firecrawl`
4. "do nothing generic; keep site adapters only"

The spike should not assume that "more browser" automatically means "better".

## Decision criteria

The comparison must judge candidates on the criteria that matter for this repo.

### 1. Recovery capability

Can it help on:

- JS-rendered pages
- redirect-collapse cases
- anti-bot / 403 public pages
- shell pages with meaningful client-rendered content

### 2. Honesty of failure

Can it preserve:

- explicit provider attribution
- clean telemetry
- honest `DEGRADED` / `FAILED`
- no silent fake success

### 3. Local reproducibility

Can a repo user run it locally without heroic setup?

Questions:

- install weight
- browser/runtime dependencies
- Windows/macOS viability
- deterministic CLI integration

### 4. Operational cost

We prefer free or self-hosted baseline.

Questions:

- does it require paid infrastructure?
- is it viable without usage billing?
- what is the real hidden maintenance cost?

### 5. Integration complexity

Questions:

- can it be slotted into `fetch_url.py` as one more provider rung?
- can it emit the same envelope shape?
- can it reuse current telemetry and sidecar patterns?
- does it force a redesign of the research runtime?

### 6. Agent ergonomics

Questions:

- does it give deterministic output usable by `ResearchSkillA`?
- does it reduce the need for site-specific rescue steps?
- can failures be explained in a clean issue/report artifact?

### 7. Security / policy fit

Questions:

- does it avoid stealthy auth/paywall bypass?
- does it avoid turning `h2t-ops` into a black-box hosted scraping service?
- does it keep secrets/config manageable?

## Validation targets

This spike should use concrete targets, but only as validation fixtures.

### Primary validation target

`alltd.org`

Why:

- historically failed in TD POP runs;
- redirect-collapse and anti-bot behavior already observed;
- directly relevant to TouchDesigner source recovery.

### Secondary validation target

`interactiveimmersive.io` / `iihq.tv`

Why:

- historically produced JS shell / truncated content cases;
- different failure shape from AllTD;
- useful to test whether a candidate helps rendered content, not just one site's
  anti-bot behavior.

### Optional neutral public target

One safe public JS-rendered page may be used as a control if needed, but the
core evaluation should stay grounded in the known failing research sources.

## Expected outputs

This spike should produce four artifacts.

### 1. Capability matrix

For each candidate:

- recovery strengths
- failure modes
- install/runtime weight
- local vs hosted mode
- cost profile
- telemetry friendliness
- integration complexity

### 2. Validation notes

For each target URL class:

- current `direct -> jina` outcome
- candidate outcome
- whether the candidate improves quality meaningfully
- whether the improvement is generic or site-specific

At least two concrete failing cases must be shown side by side:

- baseline `direct -> jina` result
- candidate result
- delta in usefulness
- whether the delta is strong enough to justify adoption

### 3. Recommendation

A crisp recommendation in one of these forms:

- adopt `Crawl4AI` as next optional ladder rung
- adopt `Playwright` as next optional ladder rung
- keep both deferred; current value does not justify the weight
- generic layer still insufficient; a site adapter is justified

This must end as an explicit decision record, not just a descriptive memo.

The decision record must include:

- chosen outcome
- why the alternatives lost
- what follow-up issue should be created or updated
- what evidence threshold justified the decision

### 4. Follow-up split

Explicitly state what becomes:

- follow-up generic provider implementation
- follow-up site adapter work
- follow-up issue rewording or issue creation

## Strong default hypothesis

The spike should challenge this, not blindly accept it:

- `Crawl4AI` is the likely best next generic candidate
- `Playwright` is the likely lower-level fallback/base primitive
- `Browserless` and `Firecrawl` should remain non-default / optional / later

Why this hypothesis exists:

- it keeps the stack local-first;
- it avoids vendor lock-in as a default;
- it aims at rendered-page extraction rather than one site;
- it seems aligned with the repo's preference for honest provider layering.

But the spike must be allowed to reject that hypothesis if evidence is weak.

## Allowed experiment surface

This spike may include practical experiments, but only at research depth.

Allowed:

- reading primary-source docs and official feature/pricing/self-hosting docs;
- one-off local experiments outside committed repo code;
- disposable commands or throwaway scripts used only to test whether a candidate
  can recover a target page;
- recording outcomes in notes/spec/report artifacts.

Not allowed:

- committing provider code into `fetch_url.py`;
- adding runtime dependencies to the repo as part of this spike;
- creating production scripts or adapters;
- changing ladder order or connector surfaces.

## Non-goals

This spike must not quietly turn into implementation work.

Not part of this task:

- adding `crawl4ai` code to the ladder
- adding `playwright` code to the ladder
- writing `alltd.py`
- changing issue `#99`
- migrating `fetch_url.py` into `h2t_ops/connectors/research`

If implementation starts, it should happen in a separate plan after the
recommendation is accepted.

## Acceptance

This spike is done when:

- at least three candidate approaches are compared seriously;
- the comparison is grounded in real repo needs, not generic web-scraping hype;
- AllTD and IIHQ are used as validation targets, not product boundaries;
- the result clearly distinguishes generic recovery from site-specific parsing;
- one recommended next step is chosen, or a justified "defer" decision is made;
- at least two side-by-side baseline-vs-candidate validation cases are recorded;
- the spike ends in an explicit decision record, not just a descriptive memo;
- the output is actionable enough to rewrite or replace `#105`.

## Recommended issue rewrite

If this spike lands cleanly, `#105` should no longer describe itself as
"AllTouchDesigner auth-aware adapter".

It should become something closer to:

`research: generic rendered/blocked source recovery layer after direct+jina`

And then:

- keep AllTD as validation target
- keep IIHQ as secondary validation target
- move site-specific parsing to a later issue only if still needed

## Definition of done

This task is done when the team can answer:

- what next generic recovery layer, if any, should be added after `direct -> jina`;
- why that choice beats the alternatives for this repo;
- whether `alltd.org` still needs a dedicated adapter after that layer exists.
