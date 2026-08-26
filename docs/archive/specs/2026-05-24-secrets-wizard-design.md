---
title: "Design: h2t-core:setup Secrets Wizard (#112)"
status: "draft"
owner: "Stanislav Glazov"
date: "2026-05-24"
milestone: ""
---
# Design: h2t-core:setup Secrets Wizard (#112)

**Date:** 2026-05-24
**Issue:** [#112](https://github.com/lichtpfad/h2t-skills/issues/112)
**Approach:** C — Hybrid (thin backend + skill orchestration)

## Problem

New users cloning h2t-skills on a fresh machine have no `~/.dor/secrets/secrets.env`.
The connector loader fails-loud immediately. There is no guided path to populate credentials.

## Solution Overview

A wizard flow triggered via `h2t-core:setup --secrets`. The skill orchestrates a 5-step
sequence; the backend (`setup_h2t.py`) handles only two atomic file operations.

## Architecture

```
User intent: "setup secrets" / "h2t-core:setup --secrets"
        │
        ▼
  SKILL.md wizard (5 steps)
  ├── Step 1: setup_h2t.py secrets skeleton --json
  ├── Step 2: open editor (agent instructs, user fills keys)
  ├── Step 3: h2t-ops google auth drive/gmail/calendar
  ├── Step 4: h2t-ops telegram auth
  └── Step 5: setup_h2t.py secrets preflight --json
```

The backend is stateless and deterministic. The skill owns sequencing and UX.

## Known Secrets Registry

New file: `plugins/h2t-core/skills/setup/known_secrets.yaml`

```yaml
EXA_API_KEY:
  description: "Exa semantic search API key"
  url: "https://dashboard.exa.ai/api-keys"
  validator: uuid
  connector: research

NOTION_API_TOKEN:
  description: "Notion integration token"
  url: "https://www.notion.so/profile/integrations"
  validator: starts_with:secret_
  connector: notion

MEETGEEK_API_KEY:
  description: "MeetGeek API key"
  url: "https://app.meetgeek.ai/settings/api"
  validator: nonempty
  connector: meetgeek
```

Google (Drive, Gmail, Calendar) and Telegram use OAuth/session flows — not `.env` keys.
They are handled in Steps 3–4, not via the registry.

## Backend Additions (`setup_h2t.py`)

### `secrets skeleton`

- Reads `known_secrets.yaml` from same directory as script
- Creates `~/.dor/secrets/` if absent
- If `secrets.env` already exists: appends only missing keys (never overwrites existing values)
- Returns:

```json
{
  "kind": "h2t_secrets_skeleton/v1",
  "path": "~/.dor/secrets/secrets.env",
  "added": ["EXA_API_KEY", "MEETGEEK_API_KEY"],
  "skipped": ["NOTION_API_TOKEN"]
}
```

### `secrets preflight`

- Reads `known_secrets.yaml`
- For each key: checks presence and non-empty in `secrets.env`
- Applies format validator (uuid, starts_with:, nonempty)
- Does NOT return key values — only status
- With `--live`: runs connector smoke test (e.g. `h2t-ops research preflight --json`)
- Returns:

```json
{
  "kind": "h2t_secrets_preflight/v1",
  "results": [
    {"key": "EXA_API_KEY", "found": true, "valid": true, "connector": "research"},
    {"key": "NOTION_API_TOKEN", "found": true, "valid": true, "connector": "notion"},
    {"key": "MEETGEEK_API_KEY", "found": false, "valid": false, "connector": "meetgeek"}
  ]
}
```

**Security invariant:** key values never appear in JSON output or agent context.

## Skill Wizard Flow (SKILL.md additions)

Triggered by: `h2t-core:setup --secrets` or agent detecting missing credentials.

### Step 1 — Skeleton

```bash
python setup_h2t.py secrets skeleton --json
```

Show user: which keys were added, path to file, and the URL for each key.

### Step 2 — Editor

Instruct user:
> "Open `~/.dor/secrets/secrets.env` and paste your API keys.
> Here is where to get each one: [list from known_secrets.yaml with URLs]"

Open editor:
- macOS/Linux: `code ~/.dor/secrets/secrets.env` (or `nano` if VS Code unavailable)
- Windows: `code $env:USERPROFILE\.dor\secrets\secrets.env`

Wait for user: "Say 'done' when you've filled in the keys."

### Step 3 — Google OAuth

Google OAuth is triggered lazily on first use. The wizard forces it by running a
lightweight read command for each connector. Do NOT use `connectors-check` to decide
whether to skip — it only checks file presence, not scope validity or token freshness.
Always attempt the trigger; if already authenticated, the command completes silently.

```bash
h2t-ops calendar list --max 1 --json    # triggers calendar OAuth if needed
h2t-ops gmail list --max 1 --json       # triggers gmail OAuth if needed
h2t-ops drive folders --max 1 --json    # triggers drive OAuth if needed
```

Each opens a browser OAuth flow and waits for callback. If the token is already valid,
no browser opens. Exit code 0 in both cases — only exit 4 (AuthError) means auth failed.

### Step 4 — Telegram Auth

Telegram auth is a three-phase flow:

```bash
# Phase 1 — check current state
h2t-ops telegram auth status

# Phase 2 — request login code (only if status is not authenticated)
h2t-ops telegram auth request-code --phone <phone>

# Phase 3 — complete login
h2t-ops telegram auth complete --code <code>
# If 2FA is enabled, also: --password <password>
```

The wizard drives each phase explicitly, waits for user input between phases, and
re-checks `auth status` after `complete` to confirm success.

### Step 5 — Preflight

Default (format-only, free):
```bash
python setup_h2t.py secrets preflight --json
```

Optional live check (costs Exa tokens — ask user first):
```bash
python setup_h2t.py secrets preflight --live --json
```

Show final status table. Flag any `found: false` or `valid: false` with remediation hint.

## Error Handling

| Situation | Behavior |
|-----------|----------|
| `known_secrets.yaml` missing | exit 3, ConfigError |
| `secrets.env` not found at preflight | exit 5, NotFoundError |
| User interrupts at Step 2 | skeleton preserved; next run adds only missing keys |
| Google token already exists | Step 3 skipped for that connector |
| Telegram session already exists | Step 4 skipped |
| Exa live check requested | agent asks confirmation before running |

## Testing

- Unit tests for `secrets skeleton`: creates correct `KEY=` lines, skips existing keys, no values in output
- Unit tests for `secrets preflight`: format validators, JSON output contains no key values
- Fixture: mock `secrets.env` with known keys — no real credentials in repo
- Test file: `tests/test_setup_secrets.py`

## Out of Scope

- OS keyring backend
- Encrypted-at-rest storage
- Multi-machine sync
- Gemini API key (not yet wired to a connector)

## Files Changed

| File | Change |
|------|--------|
| `plugins/h2t-core/skills/setup/known_secrets.yaml` | new |
| `plugins/h2t-core/skills/setup/scripts/setup_h2t.py` | add `secrets skeleton` and `secrets preflight` subcommands |
| `plugins/h2t-core/skills/setup/SKILL.md` | add wizard section with 5-step flow |
| `tests/test_setup_secrets.py` | new |
