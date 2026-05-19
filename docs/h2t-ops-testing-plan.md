# H2T-OPS Testing Plan

**Status:** Active gate
**Date:** 2026-05-19
**Related:** #139, #131

This plan defines how `h2t-ops` connector work is accepted. CI and mocked tests are required,
but they are not enough. A connector is accepted only after the installed local CLI works and
the live read-only smoke passes.

## Scope

Current scope:

- runtime setup and repair path for `h2t-ops`
- Notion live read-only E2E
- Gmail live read-only E2E
- regression suite for core, Notion, Gmail
- shared output/encoding behavior on Windows

Out of scope:

- write E2E against personal data unless explicitly approved
- bulk sync or destructive connector operations
- h2t-ai umbrella bridge
- future connectors after Gmail

## Acceptance Gates

| Gate | Purpose | Required For |
| --- | --- | --- |
| G0 Runtime | Prove local CLI installation works | #139, every connector PR |
| G1 Automated | Prove unit/API/CLI contract tests are green | every PR |
| G2 CLI Contract | Prove help, doctor, registry, JSON envelope | every connector PR |
| G3 Notion Live | Prove reference connector works against real Notion | #139, before accepting Gmail |
| G4 Gmail Live | Prove Gmail connector works against real Gmail | #131 |
| G5 Encoding | Prove stdout/stderr handle UTF-8 on Windows | core fix before broad rollout |
| G6 PR Gate | Prove issue/PR evidence is complete | merge |

## G0 Runtime Gate

Goal: prove the user can run `h2t-ops` as an installed local tool, not only in CI.

Commands:

```powershell
uv --version
h2t-ops --version
h2t-ops doctor
h2t-ops connectors
```

Pass criteria:

- command exists and exits 0
- `doctor` reports version, install path, connectors, and secrets presence
- `connectors` lists at least `notion` and `gmail` after #131
- no `uv trampoline failed to canonicalize script path`
- no broken `.venv` Python path

If `uv` is intentionally not the supported installer, replace the first command with the chosen
setup/repair command and update #139 with the decision.

## G1 Automated Gate

Goal: prove the code contract still holds.

Commands:

```powershell
h2t-ops dev pytest tests/core tests/connectors -v
h2t-ops dev check no-syspath
h2t-ops dev check lazy-registry
```

Pass criteria:

- all core, Notion, and Gmail tests pass
- registry/help does not import heavy SDKs
- legacy `lib/` behavior is not changed unless the PR explicitly owns that migration
- `uv.lock` is consistent with `pyproject.toml`

For #131, the known expected suite is 93 tests: core 29, Gmail 30, Notion 34.

## G2 CLI Contract Gate

Goal: prove the installed CLI surfaces behave consistently.

Commands:

```powershell
h2t-ops --version
h2t-ops doctor
h2t-ops notion --help
h2t-ops gmail --help
h2t-ops ingest notion --help
h2t-ops ingest gmail --help
```

Pass criteria:

- help exits 0
- deprecation shims warn on human output and stay silent under `--json`
- unknown/bad args map to exit 2
- missing config maps to exit 3
- auth failures map to exit 4
- `--json` writes machine-readable envelopes and uses the correct non-zero exit on errors

## G3 Notion Live Read-Only E2E

Goal: prove the reference connector works through `h2t-ops`, not direct REST.

Stable read-only fixture:

- Art Projects page id: `10adbc1e61d04d13aa6f17210b77e0d3`

Commands:

```powershell
h2t-ops notion get 10adbc1e61d04d13aa6f17210b77e0d3 --json
h2t-ops notion blocks 10adbc1e61d04d13aa6f17210b77e0d3 --limit 3 --json
```

Pass criteria:

- both commands exit 0
- JSON parses successfully
- result is non-empty
- output does not print the Notion token
- no writes are performed

Optional read-only exploration:

```powershell
h2t-ops notion find-databases 10adbc1e61d04d13aa6f17210b77e0d3 --json
```

## G4 Gmail Live Read-Only E2E

Goal: prove the Gmail connector works through `h2t-ops` on the real account.

Use only read-only commands from the final #131 CLI surface. The exact command names come from
the PR, but the smoke must cover:

- auth/config resolution
- list/search messages
- fetch one message or thread
- JSON output
- human output with realistic UTF-8 subject/sender text

Candidate commands, to adjust to the final #131 CLI:

```powershell
h2t-ops gmail --help
h2t-ops gmail list --limit 3 --json
h2t-ops gmail search "newer_than:30d" --limit 3 --json
h2t-ops gmail get <message-id> --json
```

Pass criteria:

- all read-only commands exit 0
- JSON parses successfully
- result count is plausible and non-empty for list/search
- no message body is posted into public PR text unless intentionally redacted
- no send/archive/delete/mark-read command is used in smoke

Evidence to record in #131:

- command list
- exit codes
- redacted result shape
- any skipped command and why

## G5 UTF-8 Output Gate

Goal: prevent Windows `cp1252` stdout/stderr failures and machine-consumer false success.

Known issue:

- `h2t_ops/core/output.py` can raise `UnicodeEncodeError` on Cyrillic/emoji output on Windows.
- A secondary symptom can be `--json` returning exit 0 with `{"ok": false}`.

Required tests for the core fix:

```powershell
h2t-ops dev pytest tests/core/test_output.py -v
h2t-ops dev python -c "from h2t_ops.core.output import emit; raise SystemExit(emit('gmail', result={'subject':'Привет ✨'}, fmt='json'))"
```

Pass criteria:

- UTF-8 text prints without crashing
- JSON error envelopes exit non-zero
- JSON success envelopes exit 0
- behavior is the same for Notion and Gmail providers

This gate should become its own core issue if it is not fixed before #131 merge.

## G6 PR Merge Gate

A connector PR is mergeable only when the PR body or issue comments contain:

- automated test command and result
- runtime command and result
- live read-only E2E command list and result
- known skipped checks with reason
- confirmation that no secrets or private message bodies were pasted
- link to the blocker issue if any gate is still open

For #131 specifically:

- #139 must pass before the PR is accepted as done
- Gmail work may continue while #139 is open
- merge should wait for Notion and Gmail live smoke through installed `h2t-ops`

## Evidence Format

Use this template in issue comments:

```md
## Live Smoke Evidence

Date:
Machine:
Branch/commit:

### Runtime
- `h2t-ops --version`: exit
- `h2t-ops doctor`: exit

### Notion
- command:
- exit:
- result shape:

### Gmail
- command:
- exit:
- result shape:

### Notes
- redactions:
- skipped:
- follow-ups:
```

## Operating Rule

Do not call a connector «done» because mocked tests are green. For `h2t-ops`, «done» means:

1. tested in CI;
2. tested as an installed local CLI;
3. tested against the real provider in read-only mode;
4. evidence recorded in GitHub.
