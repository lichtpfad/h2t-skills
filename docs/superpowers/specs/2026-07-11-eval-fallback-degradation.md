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

A single env var governs behavior: `H2T_EVALS_MODE ∈ {auto, off, local, push}`
(case-insensitive). Resolution priority:

1. `H2T_EVALS_MODE` set to a valid value → use it.
2. else `H2T_EVALS_ENABLED=1` (legacy) → `push`.
3. else → `auto` (default).

An invalid `H2T_EVALS_MODE` value resolves to `auto` (never raises).

**`auto` resolution** — cheap, per-run, **no network**:

- → `push` if `h2t_evals.sdk` is importable **and** `H2T_EVALS_TOKEN` is set.
- → `off` otherwise.

Rationale: an external user without the SDK/token gets `off` (zero writes — same
cleanliness as explicit off); an internal user with SDK + token auto-activates `push` with
no flag. Self-healing: once the SDK is installed and a token is set, the next run activates
on its own. The network is never probed at resolution time (a transient outage must not flip
the mode — `push` already spools and, per h2t-evals#96, fails loud only on permanent 4xx).

### 2. Per-mode behavior (null-object)

`auto` first resolves to a terminal mode (`push` or `off`, per §1); the table below is the
terminal behavior:

| mode  | `_write_local` | `_send_central` |
|-------|:--------------:|:---------------:|
| off   | —              | — (full no-op)  |
| local | ✓              | —               |
| push  | ✓              | ✓ (guarded)     |

`push` + SDK unavailable (e.g. h2t-evals#99 psycopg import, or any `ImportError`) →
**graceful degradation to local** (central becomes a no-op); no exception. (Note: under
`auto`, a missing SDK resolves to `off` before this branch is reached; the degradation
matters for *explicit* `H2T_EVALS_MODE=push` on a machine where the SDK later breaks.)

The mode is resolved once in `__init__` and stored. `off` short-circuits the **eval writes**
(`_write_local` + `_send_central`).

**Scope of "mode":** the mode governs eval telemetry writes only (local JSON + central
push). The `skill_graph` lesson hook in `__exit__`/`close` is a *separate* subsystem
(knowledge graph, not h2t-evals) and remains gated solely by whether a `skill_graph` was
passed in — it is **not** disabled by `off`. This preserves existing `skill_graph` behavior
and its tests.

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
  - activation hint tuned to the resolved state: if `auto` resolved to `off`, name the
    missing signal (SDK not importable and/or `H2T_EVALS_TOKEN` unset) and note that
    supplying both auto-activates `push`, or `export H2T_EVALS_MODE=local` to force
    local-only.
- No live service probing in this scope (a `--probe` flag is a possible follow-up).

### 5. Parity & back-compat

- **Runtime copy (verified):** `h2t-gather` (`h2t_ops.gather_entry:main`) and `h2t-handoff`
  run the *plugin* scripts via `run_plugin_main`, whose sys.path bootstrap inserts
  `plugins/h2t-core/lib` first — so the **vendored** `plugins/h2t-core/lib/eval/session.py`
  is the live copy at runtime. Root `lib/eval/session.py` is the canonical source (and what
  `test_session.py` imports); `lib/cli/main.py` is legacy and not wired to `h2t-gather`.
- Apply the `session.py` change to the canonical root, then **sync the vendored copy
  byte-identical** to it. The two currently drift (vendored is stale — it lacks the
  `skill_graph`/`close()` block); syncing both fixes the fallback *and* that pre-existing
  drift. The added `skill_graph` code is dormant in the hook path (`gather.py` does not pass
  `skill_graph`), so the sync is behavior-safe there.
- **Behavior change:** the default flips from local-by-default to `auto`. Under `auto`, a
  machine with the SDK + a token auto-activates `push` (previously it only wrote local); a
  machine without them resolves to `off` (previously it wrote local). So the old implicit
  local-only behavior is gone — `local` is now explicit-only (`H2T_EVALS_MODE=local`). The
  `status` command surfaces the resolved mode and its source; note the change in CHANGELOG.

## Testing (TDD)

- Mode matrix: `{off, local, push}` × `{SDK present, SDK absent}` → correct write/no-op
  behavior.
- `off` → full no-op: no local files created, no push.
- `push` + SDK absent → local-only write, no exception raised.
- `auto` resolution:
  - SDK importable **and** token set → resolves to `push`;
  - SDK absent → resolves to `off`;
  - token unset → resolves to `off`.
- Legacy `H2T_EVALS_ENABLED=1` (no `H2T_EVALS_MODE`) → resolves to `push`.
- Explicit `H2T_EVALS_MODE` overrides legacy and auto.
- Invalid `H2T_EVALS_MODE` → resolves to `auto` (never raises).
- Invariant: `eval.session` imports only stdlib at module top.
- `status` returns the correct dict per mode (mode/source/SDK/token/dir/count).
- **Existing-test migration:** the current local-write tests in `lib/eval/test_session.py`
  (`test_skill_eval_local_write_on_success`, `..._on_failure`, `..._metrics_recorded`) rely
  on implicit local write with no env set. Under the new `auto` default they must set
  `H2T_EVALS_MODE=local` explicitly (they test local-write behavior). The `skill_graph`
  lesson tests are unaffected (mode-independent, see §2/§3).
- **Parity:** a test asserts `lib/eval/session.py` and
  `plugins/h2t-core/lib/eval/session.py` stay byte-identical (guards the two-copy drift,
  since `check_marketplace_sync.py` does not cover source parity).

## Out of scope

- Fixing the SDK import coupling (h2t-evals#99) and 4xx silent-loss (h2t-evals#96) — upstream.
- `evals enable|disable` write commands (user chose env + read-only status).
- Live service probing (`--probe` flag) — deferred to a possible follow-up.

