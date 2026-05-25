---
title: "h2t-ops Visual OCR Fallback for Research Fetch Failures"
status: "draft"
owner: "Stanislav Glazov"
date: "2026-05-25"
milestone: ""
---
# h2t-ops Visual OCR Fallback for Research Fetch Failures

## Goal

Define a lightweight fallback path for `h2t-ops:research` when normal text
fetch fails or degrades:

- `direct`
- `jina`
- then optional **visual/OCR fallback**

This is not a replacement for structured fetch. It is a cheap rescue layer for
recovering visible text from hard pages without adopting a heavy browser/crawler
stack as baseline.

## Why this exists

The `#105` generic recovery spike showed:

- `direct -> jina` is already sufficient for many public articles;
- a heavy next rung such as `Playwright` or `Crawl4AI` is not yet justified by
  the current failing corpus;
- screenshot-only rescue is too weak because it helps triage but does not
  recover usable text.

There is a middle path:

> capture the visible rendered page and run OCR/text recovery on that visual
> surface.

This does not solve DOM extraction, but it can still recover:

- page title
- visible headings
- dates
- bylines
- visible article paragraphs
- visible paywall/login/anti-bot states

## Problem statement

Current failure handling has a gap between:

1. honest structured fetch failure/degradation; and
2. manual human inspection in a browser.

For some sources, that gap is too wide:

- the page is visible in a browser but not retrievable cleanly via current
  fetchers;
- the page is visually readable enough that OCR could recover the core text;
- we do not want to pay the operational cost of a heavy generic rung just to
  get that text.

This fallback exists to narrow that gap.

## Target shape

The visual fallback should be:

- **optional**
- **cheap**
- **clearly marked as non-canonical**
- **usable only after ordinary fetch fails or degrades**

It should not silently pretend to be equivalent to structured extraction.

## Scope

### In scope

- capture one or more page screenshots or rendered page images;
- run OCR / visible-text recovery on those images;
- emit a machine-readable fallback artifact;
- record that the result came from visual recovery, not normal fetch;
- support triage and rough text capture for difficult public pages.

### Out of scope

- replacing `direct` or `jina`;
- full browser automation;
- DOM extraction;
- hidden text recovery;
- reliable extraction of structured links/tables/metadata;
- bypassing login/paywall/private content;
- claiming OCR output is quote-safe by default.

## Pipeline position

The intended order is:

1. `direct`
2. `jina`
3. if still insufficient, optional `visual_ocr` rescue
4. if still poor, manual review or stop

This fallback is **not** a normal provider rung inside `fetch_url.py`.

It should be treated as a **separate post-fetch rescue step** that consumes a
failed/degraded fetch result and optionally adds a weaker visual artifact.

This fallback should only run when all of the following are true:

- the structured ladder is insufficient; and
- the page appears likely to be visually readable.
- the result is not explicitly access-gated.

V1 trigger gate:

- allowed after `FAILED`; or
- allowed after specific degraded reasons such as:
  - `redirect_collapsed_to_homepage`
  - `all_providers_degraded_js_shell`
  - `all_providers_degraded_short_body`
- not allowed after:
  - `content_gate=login_required`
  - `content_gate=paid`
- not allowed after a merely imperfect but still substantially readable
  structured result.

## Input / output contract

### Input

Minimum inputs:

- source URL
- one or more page images or screenshots
- basic provenance:
  - capture timestamp
  - capture tool/provider
  - viewport or page section marker if available

### Output

Target envelope shape should include fields like:

```json
{
  "status": "OK | DEGRADED | FAILED",
  "provider_used": "visual_ocr",
  "text_source": "visual_ocr",
  "url": "https://example.com/x",
  "body_text_visual_ocr": "...",
  "visible_headings": ["..."],
  "ocr_confidence": "high | medium | low | unknown",
  "quote_safe": false,
  "needs_review": true,
  "review_status": "unreviewed",
  "limitations": [
    "visual_only",
    "not_quote_safe",
    "links_not_reliable"
  ],
  "provenance": {
    "capture_method": "screenshot | page_render",
    "capture_tool": "...",
    "captured_at": "..."
  }
}
```

Exact field names can change, but the contract must preserve:

- explicit provider attribution;
- explicit distinction from normal fetch text;
- explicit review requirement;
- explicit limitations.

## Quality boundary

This fallback must be honest about what it is.

### Allowed uses

- source identification
- rough human-readable recovery
- deciding whether a source is worth deeper follow-up
- producing a weak text artifact for later review

### Not allowed by default

- strong quotes without review
- “canonical article text” claims
- exact link extraction claims
- precise structural interpretation of complex layouts

If OCR output is used in a final research artifact, it should be marked as:

- reviewed by human/agent;
- visually recovered;
- lower confidence than structured fetch.

## Failure classes it can help with

The visual OCR fallback may help when:

- structured fetch returns shell pages;
- the browser-rendered page is readable but fetch is blocked;
- the source is visible enough for OCR even if markup is hostile;
- the page is dominated by visible text rather than interactive widgets.

It is weak when:

- text is tiny or multi-column;
- the page is heavily interactive;
- text is hidden behind tabs/modals/scroll states;
- the source relies on embedded video/canvas rather than text;
- the page is truly access-gated.

## Design options

This spec intentionally keeps later alternatives open, but v1 must stay narrow.

Possible families are:

1. browser/page capture + OCR
2. screenshot tool + OCR
3. model vision readback from page images

The architecture should keep these split:

- **capture**
- **OCR/text recovery**
- **artifact packaging**

That keeps the fallback modular and prevents it from being confused with a
normal fetch provider.

### Forced v1 slice

V1 must choose exactly:

- one capture path;
- one OCR path;
- one artifact packaging path.

Everything else is deferred.

Recommended v1 constraint:

- single captured page image only;
- no multi-screenshot stitching;
- no scroll reconstruction;
- no overlap/dedup merge logic.

If full-page render is available from the chosen capture path, that is preferred
over assembling multiple viewport screenshots in v1.

## Strong constraints

The fallback must:

- remain optional;
- avoid requiring paid hosted scraping as baseline;
- avoid becoming a silent replacement for structured fetch;
- emit lower-confidence output with `needs_review=true` by default;
- preserve provenance of how the text was obtained.

## Relationship to #105

This should be treated as a **narrower and lighter follow-up** than the heavy
generic recovery rung considered in `#105`.

Current interpretation:

- `#105` heavy generic rung: deferred
- visual/OCR fallback: plausible next small task

That means:

- do not reopen the heavy `Playwright/Crawl4AI/Firecrawl` decision from this
  spec;
- instead, evaluate whether a low-cost visual fallback is enough to improve the
  remaining difficult cases.

Implementation boundary:

- `#105` heavy-rung question stays deferred;
- this task, if accepted, should produce a small separate rescue utility or
  workflow step;
- it should not mutate the current provider ladder into pretending OCR is just
  another ordinary fetch provider.

## Acceptance

This spec is ready for planning when:

- the boundary between structured fetch and visual OCR is explicit;
- the trigger gate is narrow and excludes gated content;
- the output is clearly marked non-canonical and review-required;
- the fallback is positioned after `direct+jina` as a rescue step, not as a
  baseline provider;
- provenance and limitations are part of the contract;
- the task is small enough to implement without dragging in a heavy new generic
  rung.

## Recommended next step

If accepted, the next artifact should be a short implementation plan for:

- one capture path
- one OCR path
- one envelope/output shape
- one or two real validation targets

Start small and prove value before generalizing.
