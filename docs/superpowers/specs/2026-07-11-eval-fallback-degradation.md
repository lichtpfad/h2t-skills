---
title: "Eval fallback degradation"
status: "draft"
owner: "Stanislav Glazov"
date: "2026-07-11"
milestone: ""
---

# Eval fallback degradation

## Problem

The skillpack's eval subsystem (`SkillEval` in `lib/eval/session.py`) is invoked by
`session-start` (gather), `handoff` (writer), and the `h2t-gather` CLI. When an external
adopter installs the skillpack **without h2t-evals** (no SDK, no token, no activated
access), the skills must degrade cleanly. Today the degradation is *mostly* sound
(local-only by default, `_send_central` guards `ImportError`, all three call sites wrap the
context in `try/except`), but three gaps remain:

1. **No opt-out / no explicit "off".** Local JSON is written unconditionally whenever push
   is not enabled — an external user who wants zero telemetry has no switch.
2. **No discoverability.** Nothing reports whether eval is active, why push is off, or how
   to activate it.
3. **Robustness is per-site, not centralized.** `SkillEval` itself can still do work
   (local write) that may throw; the never-crash guarantee relies on the caller's
   `try/except` rather than on `SkillEval` being intrinsically safe.

## Goals

- **Robustness (never-crash):** skills never fail because eval is absent or misconfigured.
- **Clean optional dependency / opt-out:** eval is fully removable; an external user can run
  with zero telemetry (no local, no push).
- **Discoverability:** a read-only surface reports eval status and how to activate.

Non-goal: **fail-loud on misconfiguration.** The runtime stays silent; surfacing happens
only via the on-demand `status` command.

## Design

### 1. Mode contract (resolution)

A single tri-state env var governs behavior: `H2T_EVALS_MODE ∈ {off, local, push}`
(case-insensitive). Resolution priority:

1. `H2T_EVALS_MODE` set to a valid value → use it.
2. else `H2T_EVALS_ENABLED=1` (legacy) → `push`.
3. else → `off` (new default).

An invalid `H2T_EVALS_MODE` value resolves to `off` (never raises).

### 2. Per-mode behavior (null-object)

| mode  | `_write_local` | `_send_central` |
|-------|:--------------:|:---------------:|
| off   | —              | — (full no-op)  |
| local | ✓              | —               |
| push  | ✓              | ✓ (guarded)     |

`push` + SDK unavailable (e.g. h2t-evals#99 psycopg import, or any `ImportError`) →
**graceful degradation to local** (central becomes a no-op); no exception.

The mode is resolved once in `__init__` and stored. `off` short-circuits every public
method.

### 3. Robustness (centralized)

- Every public method (`__enter__`, `__exit__`, `metric`, `close`) is guaranteed to never
  raise. The existing per-site `try/except` around the context manager remains as
  belt-and-suspenders.
- The top-level `from eval.session import SkillEval` is left as-is (module is bundled and
  imports **stdlib only**). A regression test locks the invariant that `eval.session`
  imports no third-party module at top level (guards against someone adding
  `import h2t_evals` to module scope, which would reintroduce a hard dependency).

### 4. `evals status` (discoverability, read-only)

- Pure logic in `lib/eval/status.py` returning a dict. No config writes, no network by
  default (offline-safe).
- Host command: **`h2t-ops evals status`** (the discoverable operator hub).
- Reports:
  - resolved `mode` + source (`env` / `legacy` / `default`);
  - SDK importable? (`h2t_evals.sdk`) + reason if not (link h2t-evals#99);
  - token present? (masked);
  - `service_url` (configured value only — not probed);
  - local eval dir path + session-file count;
  - activation hint: `to enable: export H2T_EVALS_MODE=local` (or `push`).
- No live service probing in this scope (a `--probe` flag is a possible follow-up).

### 5. Parity & back-compat

- Apply the `session.py` changes to the canonical `lib/eval/session.py` **and** the vendored
  `plugins/h2t-core/lib/eval/session.py` (avoid the known two-copy drift).
- **Behavior change:** the default flips from local-by-default to `off`. Existing users who
  relied on implicit local writes must set `H2T_EVALS_MODE=local` (or `push`). The `status`
  command surfaces the activation hint; note the change in CHANGELOG.

## Testing (TDD)

- Mode matrix: `{off, local, push}` × `{SDK present, SDK absent}` → correct write/no-op
  behavior.
- `off` → full no-op: no local files created, no push.
- `push` + SDK absent → local-only write, no exception raised.
- Legacy `H2T_EVALS_ENABLED=1` (no `H2T_EVALS_MODE`) → resolves to `push`.
- Invalid `H2T_EVALS_MODE` → resolves to `off`.
- Invariant: `eval.session` imports only stdlib at module top.
- `status` returns the correct dict per mode (mode/source/SDK/token/dir/count).

## Out of scope

- Fixing the SDK import coupling (h2t-evals#99) and 4xx silent-loss (h2t-evals#96) — upstream.
- `evals enable|disable` write commands (user chose env + read-only status).
- Live service probing (`--probe` flag) — deferred to a possible follow-up.

