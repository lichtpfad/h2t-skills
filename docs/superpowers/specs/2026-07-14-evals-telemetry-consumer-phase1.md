---
title: "Evals telemetry consumer phase1"
status: "draft"
owner: "Stanislav Glazov"
date: "2026-07-14"
milestone: ""
---

# Evals telemetry consumer — phase 1 (operational health report)

> Design inputs: `docs/reports/2026-07-12-skill-telemetry-audit.md` (proxy-vs-real
> classification, coverage), `lib/eval/session.py` (local session-JSON schema),
> `lib/eval/status.py` (read-only connector pattern).
> Epic: #289 (skill telemetry ↔ h2t-evals). This closes **gate 4** (a real
> consumer of the telemetry, so data isn't collected-and-ignored).
> Codex design-review folded in (2026-07-14): fallback source, trend/load-range
> split, typed extraction, UTC windows, data-loss surfacing, coverage framing.

## Problem

L1 telemetry writes ~1330 local session JSON files under `~/.h2t/evals/<skill>/
sessions/*.json`, but nothing reads them — the exact "drowns in time" failure
gate 4 exists to prevent. Central push is inactive (`H2T_EVALS_MODE=local`
pins it; see #321), so phase 1 consumes **local data only** and is fully
decoupled from activation.

User goal: *metrics to improve skills*, built incrementally. Phase 1 = a
per-skill operational-health report that points at what to fix first.

## Ground truth (verified against the store, 2026-07-14)

Local store contains **4 skill dirs only**: `session-start` (802), `handoff`
(446), `dev-session-start` (79), `creative-thinking` (5). `research`,
`connectors`, `docs*` = **zero sessions** — those code paths never instantiate
`SkillEval` (heavy prod usage ≠ telemetry emission). This is why the report is
titled **"Instrumented-session health"** and carries a **Coverage-gap** section:
the highest-value improvement lever is surfacing heavily-used-but-blind skills as
an instrumentation queue, not analysing the 4 instrumented ones.

Local record shape (`session.py:_write_local`): `skill, domain, project, status
("success"|"failure"), started_at, ended_at (UTC ISO-8601), metrics[]`. Each
metric: `{key, value_num?|value_bool?|value_text?, level?, unit?}`; any `value_*`
may be absent (caller overrides via `_finalize_metrics`).

### Real vs proxy signals (audit-classified)

| Signal | Source metric | Type | Status |
|---|---|---|---|
| success | top-level `status` (≡ `core.task_success`) | — | **real** (always present) |
| fallback | `core.deflection_rate` | num, **inverted** (`0.0`=degraded, `1.0`=ok) | **real**, always emitted |
| error type | `skills.error_class` | text | **real**, only on failure |
| duration | `skills.duration_ms` | num | real-ish (**script wall-clock**, proxy for latency) |
| op-type correct | `core.op_type_correct_rate` | num | **proxy** — excluded |
| tool-call success | `core.tool_call_success_rate` | num | **proxy** — excluded |
| time-to-first | `core.time_to_first_valid_ms` | num | **proxy** — excluded |

Excluded proxies are listed in a report footnote, never presented as signal.

## Scope

**In (phase 1):** local-only per-skill health report — success rate, fallback
rate, top error type, duration p50/p95; recent-vs-prior **trend/regression**;
**min-N** noise guard; **coverage-gap** section; `h2t-ops evals report` CLI
(human / `--json` / `--md`).

**Out (later phases):** cost (`skills.token_consumption`, `research_cost_usd`) —
phase 2; quality/eval-score trend (needs L3 LLM-judge) — phase 3; central
`/v1/stats` adapter; dev-overview hook + self-surfacing headline; linkage to
`skill_graph` eval-finding lessons. **Adjacent workstream (not this spec):**
instrumenting research/connectors with `SkillEval` (the coverage-gap queue this
report produces).

## Design

### Components (root `lib/eval/`, no plugin copy needed)

`report.py` is imported by the connector only (root `h2t_ops`), so — unlike
`session.py` — it needs **no dual copy** and no parity guard.

**`load_sessions(root, *, load_since=None) -> (list[dict], LoadStats)`**
Reads `<root>/*/sessions/*.json`. Malformed/unreadable files are skipped but
**counted**. `LoadStats = {root_readable: bool, files_seen, loaded,
malformed_skipped, undated_skipped}` — `root_readable=False` distinguishes an
absent/unreadable root (`OSError`) from a genuinely empty store (both currently
collapse to `session_count=0` in `status.py:45-50`; the report must not).
`undated_skipped` counts JSON-valid records dropped for a missing/unparseable
`started_at` (see Error handling). `load_since` bounds the read range; the caller
sets it wide enough for the trend (see below).

**`build_report(sessions, *, now=None, recent_days=7, min_n=5, regress_pp=10.0,
skill_filter=None, project_filter=None) -> dict`** — **pure** (no I/O).
`now` is injected for deterministic tests; **default = `max(started_at)` across
the loaded sessions** (data-anchored), NOT wall-clock. Rationale: with ~1330
historical sessions and sparse recent usage, wall-clock windows would render an
empty report indistinguishable from "nothing happened". Data-anchoring means
"recent" = the last `recent_days` of *actual activity*. When the store is empty,
`now` is undefined and the report is the empty-store form (see Error handling).

### Metric extraction (typed, None-safe)

A helper reads a metric by key and expected slot (`value_bool|value_num|
value_text`), returning `None` when absent — never coercing `None→0`. Sessions
missing a signal are excluded from *that* signal's denominator and counted, so
coverage is honest.

- **success_rate** = share of sessions with top-level `status == "success"`.
  The top-level `status` is the **authoritative** success signal (always
  present); `core.task_success` is derived from it but is caller-overridable
  (`session.py:_finalize_metrics`), so the two **can diverge** — the report does
  not treat them as equivalent and never reads `core.task_success` for this.
- **fallback_rate** = share of *degradation-marked* sessions among those whose
  `core.deflection_rate ∈ {0.0, 1.0}`. `0.0` = degraded (recall the inverted
  scale). Records where a caller overrode `deflection_rate` with any other value
  carry no clean degradation marker → excluded from the denominator and counted
  as `fallback_unknown`. `skills.fallback_used` (optional emit-ahead) is **not
  merged**.
- **top error type** = mode of `skills.error_class` over failing sessions.
  Labeled "top exception type" (only present when `__exit__` saw an exception) —
  a count of exception records, **not** an error rate or a full failure taxonomy.
- **duration** p50/p95 from `skills.duration_ms`, computed by **linear
  interpolation between closest ranks** on the sorted values, shown with `n`;
  p95 suppressed when `n < min_n`. Column labeled "script wall-clock" (proxy for
  latency, not user-perceived).

### Windows & trend

`started_at` parsed as UTC; windows are **half-open** `[t0, t1)` on `started_at`.
With `now` = `max(started_at)` by default (see build_report):
- recent = `[now - recent_days, now]` (closed at `now` so the anchor session is in-window)
- prior  = `[now - 2·recent_days, now - recent_days)`

`load_sessions` must be called with `load_since = now - 2·recent_days` (or wider
for `--since`) — the **load range is separate from the trend window** so the
prior window is never starved. Because `now` is data-anchored, `load_sessions`
first discovers the max `started_at` (a cheap pre-scan) when `--since` is not
given, then bounds the range; the pre-scan and the report share one parse pass.

`regressed = True` iff `success_rate_recent ≤ success_rate_prior -
regress_pp/100` **and both** windows have `≥ min_n` runs (percentage-point drop,
not relative). Trend column: ▼ / ▲ / flat + delta.

### min-N noise guard

A skill with `< min_n` runs in the recent window is **not** rated or trended and
**not** sorted into the main ranking — it is listed in a separate `low-sample`
section with its raw counts. This prevents a 2-run skill from topping "broken".

### Coverage-gap

Enumerate skill ids from the plugin catalog (`plugins/*/skills/*/SKILL.md` →
parent dir name). Subtract skills with ≥1 session. The remainder = **instrumented:
no** → the instrumentation queue, listed in **deterministic (sorted) order**.
Coverage is a **global property of the store**: it is computed over ALL sessions,
**ignoring `--skill`/`--project`** display filters (else a skill instrumented but
idle in the filtered project would look uninstrumented). Known limitation: the
catalog dir name and the `SkillEval(skill=...)` argument can differ (e.g.
`dev-session-start` has no matching SKILL.md dir); unmatched store dirs and
catalog entries are both shown, flagged, not silently dropped.

### CLI

`h2t-ops evals report [--since <dur>] [--skill <name>] [--project <name>]
[--json | --md] [--recent-days N] [--min-n N] [--regress-pp F]`, registered
beside `evals status`. `report` is a **new surface**, not a mirror of `status`:
it gets its own handler and its own format flags (the connector today has only
`status` with `--json`/`as_json`, no `--md` precedent). `--json` and `--md` are
**mutually exclusive**; passing both is a usage error (exit 2). `--since`
overrides the data-anchored load range with an explicit horizon (still ≥
2·recent_days is enforced so the trend never starves); it does **not** change the
trend-window length.

Default = human table, columns: `skill | runs (recent/prior) | success% (Δ) |
fallback% | top-exc | dur p50/p95 (n) | flag`, sorted **regressed → low success
→ high fallback**. Header: window bounds, totals, `loaded/malformed/undated`
(warn if `malformed > 0` or `undated > 0`), and a distinct "telemetry root
unreadable" line when `root_readable=False`. Then `low-sample` section, then
`Coverage-gap` section, then the excluded-proxy footnote. `--json`/`--md` emit
the same aggregate. The **envelope** (human / `--format md` / `--json`) and exit
codes follow the h2t-ops connector standard (`h2t-skills/CLAUDE.md` §Connector
Standard: 0 ok, 2 usage, 3 config, 5 not found) — the report matches whatever
`get_status`/the connector framework already emit; acceptance asserts against
that shared shape, not a bespoke one. `--project`/`--skill` filter the health
rows only (not coverage); without `--project`, each row shows its contributing
`{domain, project}` set so distinct populations aren't merged silently.

## Error handling

Never raises for bad data. Failure modes, each distinct in the output:
- **Root missing/unreadable** (`OSError` on the store dir) → `root_readable=False`,
  reported as "telemetry root unreadable" — NOT the same as an empty store.
- **Empty store** (root readable, zero files) → empty report, `loaded=0`.
- **Malformed/unreadable file** → skipped, `malformed_skipped++`.
- **JSON-valid record with missing/null/non-UTC-parseable `started_at`** →
  cannot be windowed, so skipped for health/trend, `undated_skipped++` (it can
  still count toward coverage, which is date-independent).
- **Missing metric slot** (a `value_*` absent) → degrades that one signal
  (excluded from its denominator), not the whole session.

## Testing (TDD)

- `build_report` on synthetic sessions: success (from top-level `status`) /
  fallback math (inverted `deflection_rate`; `fallback_unknown` when overridden
  off {0,1}), trend delta (regress / improve / flat / insufficient-data when a
  window < min_n), **data-anchored `now`** (recent window non-empty on old data),
  min-N gate + low-sample partitioning, error_class mode, percentiles (linear
  interpolation) + p95 suppression, half-open window boundaries (anchor session
  in recent), mixed project populations, empty input (`now` undefined path).
- `load_sessions` on a tmp store: good + malformed + **undated** + unreadable
  root → `LoadStats` fields (`root_readable/files_seen/loaded/malformed_skipped/
  undated_skipped`) all correct; unreadable root distinct from empty store.
- Coverage-gap: catalog with instrumented + uninstrumented skills → correct,
  **sorted** remainder; unmatched dirs/entries flagged; result **invariant under
  `--skill`/`--project`**.
- Connector: `evals report --json` and `--md` emit the SAME aggregate in the
  connector's standard envelope; `--json --md` together → exit 2 (usage).

## Acceptance

- [ ] `h2t-ops evals report` renders per-skill health over local data, worst-first.
- [ ] success from top-level `status` (not caller-overridable `core.task_success`);
      fallback from inverted `deflection_rate` with `fallback_unknown` for off-scale.
- [ ] Only real signals shown; proxies excluded + footnoted.
- [ ] `now` data-anchored — a store of only old sessions still yields a populated
      report, not an empty one.
- [ ] Trend regression flagged only when both windows ≥ min_n; low-sample
      partitioned out of ranking.
- [ ] Root-unreadable, empty, `malformed>0`, `undated>0` are four distinct,
      surfaced states — none silently dropped.
- [ ] Coverage-gap lists uninstrumented skills (research/connectors/docs),
      sorted, filter-invariant.
- [ ] `--json` / `--md` emit the same aggregate (mutually exclusive); unit tests
      green (TDD).
