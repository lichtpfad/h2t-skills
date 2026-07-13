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
**counted**. `LoadStats = {files_seen, loaded, malformed_skipped}`. `load_since`
bounds the read range; the caller sets it wide enough for the trend (see below).

**`build_report(sessions, *, now, recent_days=7, min_n=5, regress_pp=10.0,
skill_filter=None, project_filter=None) -> dict`** — **pure** (no I/O).
`now` is injected (default: wall-clock at call site) so tests are deterministic.

### Metric extraction (typed, None-safe)

A helper reads a metric by key and expected slot (`value_bool|value_num|
value_text`), returning `None` when absent — never coercing `None→0`. Sessions
missing a signal are excluded from *that* signal's denominator and counted, so
coverage is honest.

- **success_rate** = share of sessions with top-level `status == "success"`
  (always present; avoids the caller-override ambiguity of `core.task_success`).
- **fallback_rate** = share of sessions with `core.deflection_rate == 0.0`
  (degraded). Derived from `deflection_rate` only — `skills.fallback_used` is
  optional (emit-ahead) and **not merged**.
- **top error type** = mode of `skills.error_class` over failing sessions.
  Labeled "top exception type", not "error rate".
- **duration** p50/p95 from `skills.duration_ms`, shown with `n`; p95 suppressed
  when `n < min_n`. Column labeled "script wall-clock".

### Windows & trend

`started_at` parsed as UTC; windows are **half-open** `[t0, t1)`.
- recent = `[now - recent_days, now)`
- prior  = `[now - 2·recent_days, now - recent_days)`

`load_sessions` must be called with `load_since = now - 2·recent_days` (or wider
for `--since`) — the **load range is separate from the trend window** so the
prior window is never starved.

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
no** → the instrumentation queue. Known limitation: the catalog dir name and the
`SkillEval(skill=...)` argument can differ (e.g. `dev-session-start` has no
matching SKILL.md dir); unmatched store dirs and catalog entries are both shown,
flagged, not silently dropped.

### CLI

`h2t-ops evals report [--since <dur>] [--skill <name>] [--project <name>]
[--json] [--md] [--recent-days N] [--min-n N] [--regress-pp F]`, registered
beside `evals status`. `report` is a **new surface**, not a mirror of `status`:
`--md` gets its own handler (the connector has no `--md` precedent).

Default = human table, columns: `skill | runs (recent/prior) | success% (Δ) |
fallback% | top-exc | dur p50/p95 (n) | flag`, sorted **regressed → low success
→ high fallback**. Header: window bounds, totals, `loaded/malformed` (warn if
`malformed > 0`). Then `low-sample` section, then `Coverage-gap` section, then
the excluded-proxy footnote. `--json`/`--md` emit the same aggregate via the
connector envelope. `--project` filters; without it, each row shows its
contributing `{domain, project}` set so distinct populations aren't merged
silently.

## Error handling

Never raises for bad data: unreadable/malformed files are skipped and counted;
an empty store yields an empty report with `loaded=0` (not an error). Missing
metric slots degrade a single signal, not the whole session.

## Testing (TDD)

- `build_report` on synthetic sessions: success/fallback math (incl. inverted
  `deflection_rate`), trend delta (regress / improve / flat / insufficient-data
  when a window < min_n), min-N gate + low-sample partitioning, error_class
  mode, percentiles + p95 suppression, UTC window boundaries (half-open), mixed
  project populations, empty input.
- `load_sessions` on a tmp store: good + malformed + unreadable files →
  `LoadStats` counts correct, malformed skipped.
- Coverage-gap: catalog with instrumented + uninstrumented skills → correct
  remainder; unmatched dirs/entries flagged.
- Connector smoke: `evals report --json` returns a well-formed envelope.

## Acceptance

- [ ] `h2t-ops evals report` renders per-skill health over local data, worst-first.
- [ ] Only real signals shown; proxies excluded + footnoted.
- [ ] Trend regression flagged only when both windows ≥ min_n; low-sample
      partitioned out of ranking.
- [ ] `malformed > 0` surfaced, not silently dropped.
- [ ] Coverage-gap lists uninstrumented skills (research/connectors/docs).
- [ ] `--json` / `--md` emit the same aggregate; unit tests green (TDD).
