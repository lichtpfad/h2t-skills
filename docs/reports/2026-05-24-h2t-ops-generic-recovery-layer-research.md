# h2t-ops Generic Recovery Layer Research Spike

**Date:** 2026-05-24
**Issue:** `#105`
**Spec:** `docs/superpowers/specs/2026-05-24-h2t-ops-generic-recovery-layer-research-design.md`
**Plan:** `docs/superpowers/plans/2026-05-24-h2t-ops-generic-recovery-layer-research-plan.md`

## Purpose

Determine whether `h2t-ops:research` should add a next generic recovery layer
after the current `direct -> jina` baseline, and whether `#105` should stay a
site-specific adapter issue.

This is a bounded research spike, not implementation work.

## Baseline

Current closed baseline from `#98`:

- `direct`
- `jina`
- honest `OK / DEGRADED / FAILED`
- no login/paywall bypass

Known failure classes still relevant to this spike:

- redirect collapse to homepage
- anti-bot / source instability
- JS shell / browser-rendered content

Validation targets used here:

- AllTouchDesigner
- IIHQ / Interactive & Immersive

## Candidate comparison

| Candidate | Recovery shape | Cost shape | Traceability | Integration weight | Decision note |
| --- | --- | --- | --- | --- | --- |
| `Playwright` | Strong browser realism and render control | no vendor metering, but local browser/runtime cost | strongest local traces: screenshots, network, DOM, traces | high | technically strongest, but heavy for one remaining failing class |
| `Crawl4AI` | good generic rendered-page recovery with crawler ergonomics | self-host/local-first; optional LLM cost if LLM extraction is enabled | good observability and request logs | medium | best generic candidate on paper, but not justified by current evidence set |
| `Firecrawl` | strong hosted dynamic-page recovery | explicit credit billing; agent/browser paths increase cost | vendor-side observability, but hosted control plane | low/medium | useful reference comparator, not a baseline fit |
| `direct -> jina` only | already handles ordinary public articles and some redirects | lowest cost and setup | modest but sufficient current envelope telemetry | low | remains the baseline |

Primary-source comparison summary:

- `Playwright` wins on control and traceability.
- `Crawl4AI` is the most credible local-first generic rung.
- `Firecrawl` is the fastest hosted path, but changes the contract toward
  credits, hosted APIs, and optional model spend.
- none of the heavier options is justified by the current repo-specific failing
  corpus.

## Validation evidence

### Case 1: AllTouchDesigner remains a real failing class

Command:

```powershell
uv.exe run --python 3.11 -- python plugins/h2t-ops/skills/research/scripts/fetch_url.py fetch --url "https://alltd.org/glsl-for-pops-lesson-0/" --provider auto --json --output-dir C:\tmp\h2t-generic-recovery --project generic-recovery
```

Observed:

- `status`: `DEGRADED`
- `provider_used`: `direct`
- `final_url`: `https://www.alltd.org/`
- `content_type`: `redirect_collapsed`
- `reason_for_degraded`: `redirect_collapsed_to_homepage`

Interpretation:

- this is a real unresolved failure class;
- current ladder avoids false `OK`, but does not recover the requested article;
- the source looks more like redirect-collapse / auth-shaped behavior than a
  plain JS-rendered page problem.

### Case 2: old IIHQ shortlink no longer proves the generic-layer need

Command:

```powershell
uv.exe run --python 3.11 -- python plugins/h2t-ops/skills/research/scripts/fetch_url.py fetch --url "https://iihq.tv/4nFDCKc" --provider auto --json --output-dir C:\tmp\h2t-generic-recovery --project generic-recovery
```

Observed:

- `status`: `OK`
- `provider_used`: `direct`
- `final_url`: `https://interactiveimmersive.io/blog/touchdesigner-resources/whats-new-in-the-2025-touchdesigner-release/?utm_source=twitter&utm_medium=organic`
- `content_type`: `article`

Interpretation:

- this historical IIHQ fixture no longer demonstrates a missing generic rung;
- current ladder already recovers the content via ordinary direct fetch and
  redirect handling.

### Case 3: Interactive & Immersive article is already ordinary baseline success

Command:

```powershell
uv.exe run --python 3.11 -- python plugins/h2t-ops/skills/research/scripts/fetch_url.py fetch --url "https://interactiveimmersive.io/blog/touchdesigner-3d/pops-in-touchdesigner-faq/" --provider auto --json --output-dir C:\tmp\h2t-generic-recovery --project generic-recovery
```

Observed:

- `status`: `OK`
- `provider_used`: `direct`
- `content_type`: `article`

Interpretation:

- this class is already handled by the current baseline;
- it does not justify a new browser/crawler rung.

## Screenshot-first fallback

Verdict:

- keep it only as a **manual rescue / triage path**;
- do not treat it as a normal ladder rung.

What it is good for:

- source identification
- spotting paywall/login/anti-bot states
- rough human-readable visual recovery

What it is not good for:

- structured extraction
- reliable citations and quotes
- canonical research artifacts

Reason:

the research skill requires grounded output with `URL + quote + confidence`.
A screenshot-only path does not meet that contract.

## Decision record

### Chosen outcome

**Defer both generic heavy rungs for now; current evidence does not justify the
operational weight.**

### Why the alternatives lost

`Playwright` lost because:

- it is the heaviest integration option;
- the current failing corpus does not show enough multi-site benefit to justify
  adding a browser automation rung now.

`Crawl4AI` lost because:

- it is the best generic local-first candidate on paper;
- but the live validation corpus collapsed to essentially one real unresolved
  class: AllTD.
- one remaining class is not enough to justify new runtime weight.

`Firecrawl` lost because:

- it pushes the stack toward hosted credits and optional model spend;
- it solves the wrong problem too expensively for current repo needs.

### Evidence threshold used

To justify a new rung, this spike needed at least two real current failing
classes where the baseline was insufficient and the candidate class plausibly
improved repo-specific value.

That threshold was not met:

- AllTD remains unresolved.
- IIHQ / Interactive & Immersive no longer demonstrates the same gap.

### Cost conclusion

- `Firecrawl` has the clearest explicit paid surface and the highest risk of
  turning this into a hosted default.
- `Crawl4AI` is cheaper structurally, but can still accumulate hidden model cost
  if LLM extraction is used.
- `Playwright` avoids vendor metering, but shifts cost into engineering and
  maintenance.
- screenshot-first is cheap, but only as manual rescue.

## Follow-up split

### Generic provider implementation

No new generic provider implementation should start from this spike.

### Site-specific work

If AllTD still matters as a source, the next useful work is narrower:

- improve classification/reporting for redirect-collapsed sources; or
- validate whether AllTD has any truly public article path that a browser-based
  rung would recover honestly without crossing into auth bypass.

That is a source-specific investigation, not a generic ladder expansion.

### `#105` rewrite proposal

`#105` should not remain "AllTouchDesigner adapter".

Recommended rewrite:

`research: evaluate next generic rendered/blocked recovery layer after direct+jina`

Recommended resolution after this spike:

- attach this report to `#105`;
- mark the research spike complete;
- record the decision as **defer generic rung for now**;
- only open a new implementation issue if a larger failing source corpus
  emerges, or if AllTD proves to have a recoverable public path that warrants
  narrower work.

## Conclusion

This spike does **not** support adding `Playwright`, `Crawl4AI`, or
`Firecrawl` to the fetch ladder right now.

It does support a cleaner framing:

- `#98` already closed the honest shared baseline;
- `#105` should stop pretending the answer is an AllTD adapter;
- the next implementation should happen only if the failing corpus grows beyond
  one stubborn source class.
