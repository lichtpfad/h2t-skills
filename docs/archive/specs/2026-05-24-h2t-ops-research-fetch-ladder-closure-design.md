---
title: "h2t-ops Research Fetch Ladder Closure Design"
status: "draft"
owner: "Stanislav Glazov"
date: "2026-05-24"
milestone: ""
---
# h2t-ops Research Fetch Ladder Closure Design

## Goal

Close `#98` by defining the final architecture and closure criteria for
blocked-source URL fetching in `h2t-ops:research`.

The fetch ladder already exists today as
`plugins/h2t-ops/skills/research/scripts/fetch_url.py`. This spec is not about
inventing a new ladder from scratch. It is about making the current fetch
runtime an intentional, documented, shippable part of the research stack with
clear boundaries, honest envelopes, and downstream adapter reuse.

## Why `#98` still exists

The original problem from TD POP research is still valid:

- plain HTTP fetch was not enough for high-value sources such as `alltd.org`;
- JS shell, 403 pages, and gated flows must be classified honestly;
- downstream research workflows need a shared fetch contract rather than ad hoc
  per-site scraping code.

At the same time, the repo has moved forward:

- `fetch_url.py` is already implemented with direct + Jina ladder behavior;
- tests already cover many edge cases;
- `h2t-ops:research` has a broader parity/migration story under `#136`;
- site-specific follow-ups such as `#105` now depend on a stable shared ladder.

So the remaining work in `#98` is not "write the first version". It is:

1. freeze the contract;
2. classify what is in scope for this issue versus follow-up issues;
3. define what counts as done before downstream adapters rely on it.

## Problem statement

Research has two distinct jobs that must not be mixed:

1. **Search/discovery**
   Example: Exa query, author discovery, topic scan.
2. **Fetch/recovery**
   Example: turn a known URL into an honest content envelope.

`#98` is only the second job.

The fetch ladder must solve:

- recover public content when plain direct fetch fails;
- distinguish "blocked but recoverable" from "legitimately gated";
- expose which provider succeeded and which attempts failed;
- avoid silently treating shell/homepage/chrome as article content;
- produce output that downstream site adapters can reuse.

It must not solve:

- bulk crawl strategy;
- author/channel discovery;
- site-specific parsing logic for every source;
- POS knowledge-base promotion.

## Current state

### Existing implementation

Current runtime:

- `plugins/h2t-ops/skills/research/scripts/fetch_url.py`
- `plugins/h2t-ops/skills/research/tests/test_fetch_url.py`

Implemented today:

- provider ladder entrypoint with `fetch` and `preflight`;
- active providers:
  - `direct`
  - `jina`
- stubbed providers:
  - `playwright`
  - `crawl4ai`
  - `firecrawl`
  - `browserless`
- honest envelope fields:
  - `status`
  - `provider_used`
  - `content_type`
  - `content_gate`
  - `telemetry.attempts`
- sidecar writes under `~/.h2t/research/`;
- gating behavior for login/paywall;
- redirect-collapse detection for AllTouchDesigner-style homepage fallback;
- UTF-8-safe CLI output.

### What is not yet fully closed

- the ladder still lives as a skill-local script, not yet as final connector
  runtime under `h2t_ops/connectors/research/`;
- only `direct` and `jina` are real providers today;
- there is no explicit closure note telling downstream work whether stubs are
  acceptable for `#98`;
- site-specific reuse contract for `#105` is implied by code, but not frozen as
  the authoritative design;
- issue text still reads like pre-implementation design, not post-implementation
  closure criteria.

## Design decision

`#98` closes when the fetch ladder contract is considered stable with
`direct + jina` as baseline and the remaining providers explicitly classified as
future, optional escalation paths.

This means:

- `playwright`, `crawl4ai`, `firecrawl`, `browserless` are **not required** for
  `#98` closure;
- they remain part of the ladder namespace and telemetry surface;
- they must stay config-gated and non-default;
- downstream adapters such as `#105` must build on the shared ladder rather than
  duplicating fetch code.

## Scope

### In scope

- shared fetch ladder contract for known URLs;
- baseline providers `direct` and `jina`;
- honest provider telemetry and envelope semantics;
- shell/gated/redirect-collapsed classification;
- sidecar artifact behavior needed by research workflows;
- explicit downstream reuse path for site adapters;
- closure criteria and test expectations.

### Out of scope

- Firecrawl as default or required dependency;
- browser automation implementation as a blocker for closure;
- author resolution helper (`#99`);
- AllTouchDesigner parser logic (`#105`);
- IIHQ or other site-specific parsers;
- POS intake/indexing/promotion;
- replacing Exa discovery workflows.

## Target architecture

The fetch ladder is a reusable provider-I/O component for research.

Target layering:

```text
research workflow
  -> known URL
  -> shared fetch ladder
  -> provider envelope
  -> optional site adapter enrichment
  -> research report / evidence artifact
  -> optional POS registration
```

Ownership split:

| Layer | Owns |
| --- | --- |
| shared fetch ladder | provider attempts, classification, envelope, sidecars |
| site adapter | source-specific listing/article extraction rules |
| research skill | synthesis, traceability, templates, final report |
| POS | indexing, promotion, canonical knowledge |

## Contract

### CLI shape

Target public shape after `#136` remains:

```bash
h2t-ops research fetch --url "https://..." --provider auto --json
```

Current callable reference implementation for `#98` closure is the skill-local
script:

```bash
python plugins/h2t-ops/skills/research/scripts/fetch_url.py fetch --url "https://..." --json
```

Closure rule:

- `#98` does **not** require the public `h2t-ops research fetch` command to be
  migrated yet;
- `#98` does require the current script-level contract to be stable enough for
  downstream adapter reuse;
- exposing the same contract through the public connector CLI belongs to `#136`.

### Provider order

Default auto order:

1. `direct`
2. `jina`
3. `playwright`
4. `crawl4ai`
5. `firecrawl`
6. `browserless`

Closure rule for `#98`:

- only `direct` and `jina` must be real and tested;
- all later providers may remain stubs;
- stubs must be skipped honestly in telemetry;
- no hidden network call to stubbed providers is allowed.

### Status semantics

Required statuses:

- `OK`
  Content is substantive enough for research use.
- `DEGRADED`
  Best effort recovered something diagnostic, but not safe to treat as a real
  article body.
- `FAILED`
  No acceptable content was recovered, or the source is legitimately gated.

Required gates:

- `content_gate=login_required`
- `content_gate=paid`

Required degraded classes:

- `js_shell`
- `short_body`
- `redirect_collapsed`
- `unknown`

### Honest failure rule

The ladder must never:

- convert a paywall/login page into fake article success;
- treat homepage chrome as a recovered article;
- hide provider failures behind an empty but "successful" body;
- claim fallback success without showing `provider_used` and attempts.

## Downstream reuse rule

`#98` is the shared fetch substrate for downstream source adapters.

This is the key boundary:

- `#98` owns generic URL recovery and classification;
- `#105` owns AllTouchDesigner tag/article parsing on top of `#98`;
- `#99` owns author/channel resolution before URL fetch even starts.

Practical implication:

- no duplicate `urllib`/Jina/browser fallback logic should be added in `alltd.py`
  or future site adapters;
- adapters may enrich metadata and parse raw HTML/markdown output from the shared
  ladder, but not reimplement the ladder itself.

Raw HTML contract:

- the Python-level ladder API may provide in-memory `raw_html` on provider
  results during the same call;
- persisted raw HTML is **not guaranteed by default**;
- adapter implementations that need disk-backed raw HTML must explicitly enable
  `keep_raw=True` and consume `metadata.raw_html_path`;
- adapter implementations must not assume `metadata.raw_html_path` exists when
  `keep_raw` was not requested.

## Testing contract

`#98` should be considered closed only if these test classes are green and kept
as part of the stable contract:

1. direct provider success/failure behavior;
2. Jina fallback after direct failure;
3. hard gate detection for login/paywall;
4. degraded classification for shell/short body;
5. redirect-collapse detection;
6. JSON envelope output for OK/DEGRADED/FAILED;
7. sidecar writes;
8. UTF-8-safe output;
9. stub-provider non-execution.

Operational guarantees that remain part of the contract:

- `--json` prints a machine-readable envelope for `OK`, `DEGRADED`, and
  `FAILED`;
- `FAILED` still preserves provider telemetry in the JSON envelope;
- sidecar behavior remains stable enough for research workflows:
  `.sources.json` is always written, `.partial.md` only for non-failed runs,
  raw HTML only when explicitly requested;
- CLI exit behavior remains class-stable:
  success/degraded exit `0`, args/env failures are distinct from provider/gated
  failures.

Live smoke for closure should be modest:

- at least one blocked-source URL recovered honestly as `OK` or `DEGRADED`;
- at least one legitimately gated/broken case classified honestly;
- no requirement that all historical TD POP URLs become `OK`.

The goal is reliability of classification, not magical recovery rate.

## Closure criteria for `#98`

`#98` can be closed when all of the following are true:

- a current design spec exists and reflects the implemented ladder;
- `fetch_url.py` contract is accepted as the shared fetch substrate;
- `direct + jina` baseline is documented as sufficient for closure;
- stub providers are explicitly deferred and not treated as missing work;
- tests cover the honest-classification cases above;
- script-level JSON/sidecar/exit behavior is explicitly preserved as the
  current callable contract;
- downstream work (`#105`, `#99`) is clearly unblocked by the shared contract;
- issue or PR evidence records at least one real blocked-source smoke outcome.

## Non-goals for closure

The following must **not** block `#98` closure:

- implementing Playwright;
- implementing Crawl4AI;
- implementing Firecrawl;
- adding paid providers;
- building AllTouchDesigner-specific listing parser;
- solving author resolution;
- migrating the whole research stack into connector runtime if the fetch
  contract itself is already stable.

Those belong to:

- `#136` for connector migration/runtime parity;
- `#105` for AllTouchDesigner adapter;
- `#99` for author/channel resolution.

## Recommended next sequence

After this spec:

1. treat `#98` as a contract-freeze + closure issue;
2. use `#105` as the next concrete source-recovery implementation target;
3. use `#99` for better discovery seeding once fetch substrate is frozen;
4. keep full runtime migration under `#136`.

## Definition of done

This spec defines `#98` as done when the repo recognizes:

- the fetch ladder is already implemented enough to be the shared baseline;
- the authoritative baseline is `direct + jina`;
- the envelope and telemetry semantics are frozen;
- the current script-level runtime contract is frozen pending `#136` public CLI
  migration;
- downstream adapters must reuse this substrate;
- remaining provider implementations are future enhancements, not blockers.
