# h2t-core setup/update delivery + lifecycle context budget design

Date: 2026-05-22
Status: draft
Issue: #160
Owner plugin: h2t-core
Related: #112, #153, docs/reports/2026-05-22-skill-surface-portability-audit.md

## Goal

Make h2t-core usable as the first installed plugin for a new user and prevent
session lifecycle tools from growing context cost over time.

This spec covers two connected areas:

1. `h2t-core:setup` / future update workflow as the install, repair, update, and
   doctor surface for h2t-core and h2t-ops.
2. `h2t-core:session-start` / `h2t-core:handoff` bounded context behavior, with
   optional POS/DOR publishing but no POS/DOR requirement.

## Current Problems

### Setup/update

Current `h2t-core:setup` is a long instruction file with shell snippets. It mixes:

- legacy `~/.h2t/venv` dependency installation;
- h2t-core gather setup;
- h2t-ops `uv tool install` repair guidance;
- local Windows paths;
- old references to legacy `h2t`;
- provider dependency import checks;
- optional personal OS state.

This works for the author but is fragile for another user. It is also hard for an
agent to repair because the real logic is embedded in prose.

### Lifecycle context

Current lifecycle flow:

- `handoff` writes full markdown under `~/.dor/sessions/<machine>/<project>/`.
- `writer.py` stores unbounded `what_done` and `what_remains`.
- `session-start` reads the latest markdown handoff and injects `What Remains`
  or the first 40 lines.
- `briefing.py` shows handoff count but does not provide a bounded handoff hint.

The issue is not markdown itself. The issue is that startup context depends on a
free-form archive artifact. As handoffs become longer, session start becomes more
expensive and less predictable.

## Design Principles

- h2t-core must work before POS/DOR is configured.
- POS/DOR integration is optional publishing/consumption, not a prerequisite.
- Skills should be thin entrypoints; deterministic scripts should own install,
  update, doctor, and lifecycle data shaping.
- `h2t-ops` is delivered as one CLI/API surface; h2t-core setup only installs and
  checks it, not its internal connector logic.
- Bounded startup context must be enforced by code, not by agent discipline.
- Full handoff markdown remains archival and human-readable.
- Machine-readable lifecycle state must be compact and never duplicated into the
  prompt without formatting/truncation.

## Setup/Update Target Shape

### Skill surface

Keep `h2t-core:setup` as the main user-facing skill. Add update semantics either
inside this skill or as a small `h2t-core:update` alias later.

Modes:

- `setup` - first-time install and configuration.
- `doctor` - read-only environment check.
- `repair` - re-run idempotent install/repair steps.
- `update` - refresh plugin/CLI state after marketplace update.
- `connectors-check` - read-only h2t-ops connector auth/status matrix.

The skill should stop being a long shell recipe. It should call a bundled script
and interpret structured output.

### Script backend

Add a deterministic setup backend under h2t-core, for example:

```text
plugins/h2t-core/skills/setup/scripts/setup_h2t.py
```

Suggested commands:

```text
setup_h2t.py doctor --json
setup_h2t.py setup --json
setup_h2t.py repair --json
setup_h2t.py update --json
setup_h2t.py connectors-check --json
setup_h2t.py install-h2t-ops --source <main|git-url|local-path> --json
```

The script should:

- detect platform: Windows, macOS, Linux;
- resolve Python and `uv`;
- find installed plugin cache paths;
- avoid hardcoded `C:/dev/...` paths except when explicitly passed by user;
- check whether `h2t-ops` is installed and runnable;
- install/repair `h2t-ops` through `uv tool install` / `uvx` semantics;
- never modify h2t-ai's root `h2t` binary;
- return structured JSON and human-friendly summaries.

### h2t-ops delivery

Required behavior:

- `uv tool install` from a canonical source works on Windows and macOS.
- If `h2t-ops` is already installed, repair is idempotent.
- If `h2t-ops` is missing from PATH, setup reports the exact binary path and PATH
  fix instead of failing ambiguously.
- setup can run `h2t-ops doctor` or equivalent without relying on root `h2t`.

Do not require the old `~/.h2t/venv` path for h2t-ops.

### Connector auth/status matrix

`connectors-check` is read-only. It should call provider status/auth checks and
summarize readiness:

| Connector | Required check |
| --- | --- |
| Calendar | OAuth files/token status and minimal readonly calendar call if safe |
| Gmail | OAuth files/token status and readonly profile/labels call if safe |
| Drive | OAuth files/token status and readonly about/list call if safe |
| Notion | token present and readonly user/search/get capability |
| Telegram | `telegram auth status --json` |
| MeetGeek | `meetgeek auth-check` |
| Research | Exa/API key presence and optional dry-run if available |

Connector checks must not write provider data or POS/DOR state.

### Optional POS/DOR integration

Setup should distinguish three layers:

1. Required: h2t-core can run lifecycle skills.
2. Required for h2t-ops: provider credentials and CLI install.
3. Optional: POS/DOR publishing and personal configuration.

If POS/DOR paths are missing, setup should show:

```text
optional_pos: not_configured
impact: lifecycle and connector provider I/O still work; POS publishing disabled
```

This is not an error.

## Lifecycle Context Target Shape

### Session root

h2t-core lifecycle state must not require POS/DOR paths.

New canonical root:

```text
~/.h2t/sessions/<machine>/<project>/
```

Configuration:

- `H2T_SESSION_ROOT` overrides the root.
- `H2T_MACHINE_NAME` is the preferred machine name.
- `DOR_MACHINE_NAME` remains a compatibility fallback.
- Existing `~/.dor/sessions/...` files may be read as legacy prior art during
  transition.
- Writing to `~/.dor/sessions` is optional POS/DOR mirroring, not the default
  h2t-core contract.

### Artifact model

Keep full markdown handoff:

```text
~/.h2t/sessions/<machine>/<project>/<session_id>.md
```

Add compact lifecycle index beside it:

```text
~/.h2t/sessions/<machine>/<project>/latest.json
```

`latest.json` is not prompt content. It is a small index consumed by gather code.
The prompt receives a formatted bounded handoff hint.

Suggested schema:

```json
{
  "version": 1,
  "session_id": "dev-h2t-skills-cleanup-2026-05-22",
  "project": "h2t-skills",
  "domain": "dev",
  "updated_at": "2026-05-22T18:30:00Z",
  "summary_short": "Closed h2t-ops migration and created skill-surface audit.",
  "next_actions": [
    "Implement setup/update backend.",
    "Prototype h2t-ops connector navigator."
  ],
  "blockers": [],
  "artifacts": [
    {"type": "commit", "ref": "8ca9ac4"},
    {"type": "issue", "ref": "160"}
  ],
  "markdown_path": "..."
}
```

Hard limits:

- `summary_short`: max 1200 chars
- `next_actions`: max 5, each max 240 chars
- `blockers`: max 5, each max 240 chars
- `artifacts`: max 10
- total formatted handoff hint in session-start: max 1800 chars

If handoff content exceeds limits, writer truncates with explicit markers.

### Handoff writer changes

`writer.py write` should continue writing markdown and activity stream.

Add:

- structured extraction of bounded summary fields from `what_done`,
  `what_remains`, and `artifacts`;
- `latest.json` write/update;
- atomic writes for `latest.json`;
- optional `--no-index` for debugging only;
- tests for truncation and malformed inputs.

### Gather/session-start changes

Change gather/session-start behavior:

- `find_session_files()` may still find markdown archives.
- new helper reads latest bounded index first.
- `briefing.py` includes a compact previous-session hint when available.
- `session-start` no longer reads markdown handoff by default.
- full markdown read is available only if the user asks for details.

The prompt should look like:

```text
### Previous Session
- Summary: ...
- Next:
  - ...
- Artifacts: commit:..., issue:...
```

Not:

```text
Read full handoff markdown and paste section body.
```

### Retention/archive policy

First implementation may avoid physically moving files. It must still define the
hot/cold split:

- hot: latest bounded index;
- warm: most recent markdown handoffs;
- cold: older markdown archive, readable on request;
- optional later: distilled project memory consumed by POS or graph.

Retention should be a follow-up command, not implicit deletion.

## File Map

Expected files for implementation:

```text
plugins/h2t-core/skills/setup/SKILL.md
plugins/h2t-core/skills/setup/scripts/setup_h2t.py          # new
plugins/h2t-core/skills/setup/scripts/test_setup_h2t.py     # new
plugins/h2t-core/skills/handoff/SKILL.md
plugins/h2t-core/skills/handoff/scripts/writer.py
plugins/h2t-core/skills/handoff/scripts/test_writer.py      # new or extended
plugins/h2t-core/skills/session-start/SKILL.md
plugins/h2t-core/lib/gather/sessions.py
plugins/h2t-core/lib/gather/briefing.py
plugins/h2t-core/lib/gather/test_sessions.py                # new or extended
plugins/h2t-core/lib/gather/test_briefing.py                # new or extended
docs/reports/2026-05-22-skill-surface-portability-audit.md
```

Avoid editing unrelated connector internals unless a setup check exposes a real
CLI contract bug.

## Tests

### Unit tests

- setup detects platform and resolves paths without private `C:/dev` assumptions.
- setup reports missing `uv` clearly.
- setup never targets root `h2t`.
- setup parses h2t-ops doctor/check output.
- connector matrix can represent ready/missing/auth-error states.
- handoff writer creates markdown plus compact `latest.json`.
- long `what_done` / `what_remains` are truncated deterministically.
- briefing formats previous-session hint under the character budget.
- session discovery works when POS/DOR directories are absent.
- writer defaults to `~/.h2t/sessions`, not `~/.dor/sessions`.
- legacy `~/.dor/sessions` can be read when present without making it required.

### Smoke tests

Read-only:

```text
h2t-core setup doctor
h2t-core setup connectors-check
h2t-ops doctor
h2t-ops <connector> auth/status read-only checks where credentials exist
```

Lifecycle:

```text
writer.py write --session-id test-... --what-done ... --what-remains ...
gather.py --cwd <repo> --format-briefing
```

Acceptance requires that the briefing does not include full handoff markdown.

## Migration Plan

1. Add tests for current lifecycle budget failure.
2. Implement bounded handoff index in writer.
3. Update gather/briefing/session-start to use bounded hint.
4. Add setup backend with `doctor` and read-only checks first.
5. Move existing setup prose into thin skill instructions around the backend.
6. Add h2t-ops install/repair/update modes.
7. Add connector read-only auth/status matrix.
8. Run Windows smoke and define macOS smoke commands for later validation.

## Non-Goals

- Do not redesign `h2t-core:agent-profile` in this issue.
- Do not implement `h2t-ops:connectors`; tracked separately by #161.
- Do not change provider connector behavior except for doctor/status bugs.
- Do not require POS/DOR for setup, session-start, or handoff.
- Do not write POS journal, vault, lake, or graph state from lifecycle skills by
  default.
- Do not make `~/.dor/sessions` the canonical lifecycle store.
- Do not delete old handoff markdown automatically.
- Do not fix h2t-ai root `h2t` binary.
- Do not migrate all legacy `plugins/h2t/` content here.

## Acceptance Gates

- A new user can run h2t-core setup/doctor without private author paths.
- `h2t-ops` can be installed/repaired through documented `uv` flow.
- Connector auth/status matrix is read-only and clearly reports missing
  credentials.
- `session-start` has a hard context budget for previous-session data.
- Full handoff markdown remains available but is not injected by default.
- POS/DOR integration is optional and explicitly reported as optional.
- Default lifecycle files are written under `~/.h2t/sessions` or
  `H2T_SESSION_ROOT`.
- Tests cover setup backend, handoff index, and briefing budget.
