# H2T Ops Recent Closure Validation Gate

**Date:** 2026-05-25  
**Scope:** recent provider closures after the connector-closure milestone  
**Status:** required before continuing broad P2 backlog closure

## Why This Gate Exists

The recent P1/provider follow-up issues were closed with good unit and CLI
coverage, but not all of them received the same level of live validation.

That is acceptable for narrow, deterministic read-path changes. It is not a
good default for provider writes or provider-shaped behavior that mocks can miss.

This gate standardizes the closure rule for the latest provider work so we stop
closing issues on mixed evidence standards.

## Validation Standard

| Change class | Minimum gate |
| --- | --- |
| Read-only, deterministic, narrow surface | Focused unit tests + CLI parser/help |
| Provider read with provider-shaped output risk | Focused unit tests + CLI parser/help + one safe live smoke when feasible |
| Reversible provider write | Focused unit tests + CLI parser/help + one safe live smoke |
| Destructive provider write | Guarded design + focused unit tests + CLI parser/help + explicit live smoke on prepared test object |

`h2t-ops` should not treat unit coverage as a universal substitute for live
provider validation.

## Current Matrix

| Issue | Surface | Risk class | Unit / CLI | Live smoke | Gate state |
| --- | --- | --- | --- | --- | --- |
| #169 | Drive `create-folder` | Reversible provider write | PASS | Pending | Not fully validated |
| #172 | Gmail `threads`, `thread`, send thread flags | Mixed: mostly read, partial write surface exposure | PASS | Pending | Not fully validated |
| #173 | Gmail attachment download | Provider read with provider-shaped payload | PASS | Pending | Not fully validated |
| #181 | Telegram `send` | Reversible provider write | PASS | PASS (`me` self-target) | Fully validated |
| #176 | Calendar `rsvp`, `move` | Reversible provider write | PASS | Pending | Do not close before live smoke |

## Immediate Sweep

Before continuing broad P2 backlog work, run a focused validation sweep for:

1. `#169` — safe create-folder smoke in a designated test parent.
2. `#172` — safe Gmail thread list/detail smoke; reply-in-thread only on a prepared test message.
3. `#173` — download a small known attachment to a temp path and verify bytes written.
4. `#176` — RSVP on a prepared test event; move only if a safe source/destination pair exists.

`#181` does not block this sweep because it already has a safe live pass.

## Closure Policy Going Forward

For post-closure maintenance issues:

1. Do not close provider-write issues on unit tests alone.
2. Record the exact live smoke command or explicitly state why live smoke was deferred.
3. If live smoke is unsafe or environment-dependent, narrow the issue first and
   close only the validated slice.
4. Destructive operations should default to a separate guarded design task, not
   be bundled into parity cleanup.

## Practical Next Step

Run the validation sweep above and either:

- keep the existing closed status with added evidence comments; or
- reopen / relabel any issue whose live behavior does not match the closed claim.
