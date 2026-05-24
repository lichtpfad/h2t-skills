---
name: h2t-core:setup
description: "Install, repair, update, and diagnose h2t-core / h2t-ops delivery. Use for 'h2t setup', 'install h2t-ops', 'repair h2t', 'update h2t', connector auth/status checks, or sharing h2t tools with another machine/user."
compatibility: "Claude Code"
metadata:
  author: lichtpfad
  version: 1.2.1
---

# h2t Setup

Use this skill as the install/update/doctor surface for h2t-core and h2t-ops.

The skill is a thin wrapper around the deterministic backend:

```text
scripts/setup_h2t.py
```

Do not reimplement setup logic in prose. Run the backend, inspect structured
output, and only then explain the next action.

## Modes

| User intent | Backend command |
| --- | --- |
| diagnose current install | `doctor --json` |
| first setup / repair / update | `doctor --json`, then `install-h2t-ops --source main --dry-run --json`, then ask before real install |
| check connector readiness | `connectors-check --json` |
| run live connector status checks | `connectors-check --live --json` |
| include paid Research/Exa preflight | `connectors-check --live --include-paid --json` only after explicit user confirmation |

## Procedure

### Step 1: Resolve script path

Use the `scripts/setup_h2t.py` file bundled next to this `SKILL.md`.

Run it with any available Python 3.11+:

```bash
python scripts/setup_h2t.py doctor --json
```

On Windows, `py -3` or an existing project/uv Python is also acceptable:

```powershell
py -3 .\scripts\setup_h2t.py doctor --json
```

If running from a repo checkout instead of plugin cache, use the repo-relative
path:

```powershell
uv.exe run python plugins\h2t-core\skills\setup\scripts\setup_h2t.py doctor --json
```

### Step 2: Doctor first

Always start with:

```bash
python scripts/setup_h2t.py doctor --json
```

Report:

- platform;
- `uv` status and path;
- `h2t-ops` status, path, version;
- optional POS/DOR status;
- whether plugin cache is visible.

POS/DOR absence is not an error. Phrase it as:

```text
optional_pos: not_configured
impact: lifecycle and connector provider I/O still work; POS publishing disabled
```

### Step 3: Install or repair h2t-ops

First run a dry-run:

```bash
python scripts/setup_h2t.py install-h2t-ops --source main --dry-run --json
```

Show the command to the user. Ask before running the real install because it
modifies the user's `uv tool` environment.

Real install:

```bash
python scripts/setup_h2t.py install-h2t-ops --source main --json
```

If installing from a local checkout:

```bash
python scripts/setup_h2t.py install-h2t-ops --source C:/dev/h2t-skills --json
```

### Step 4: Connector readiness

Default connector check is credential-only and read-only:

```bash
python scripts/setup_h2t.py connectors-check --json
```

This must not write provider data, POS/DOR state, Notion pages, Drive files, or
calendar events.

Live checks require explicit user intent:

```bash
python scripts/setup_h2t.py connectors-check --live --json
```

Research/Exa preflight can use a paid provider request. Only run it if the user
explicitly asks:

```bash
python scripts/setup_h2t.py connectors-check --live --include-paid --json
```

### Step 5: Boundaries

- Never install, repair, shadow, or modify root `h2t`.
- Never run `uv tool install h2t`.
- h2t-ops is installed as `h2t-ops`, from `h2t-skills` source.
- h2t-core setup can work before POS/DOR exists.
- Missing POS/DOR disables publishing only; it does not block lifecycle or
  provider I/O.

## Expected Outputs

Doctor returns `h2t_setup_doctor/v1`.

Connector readiness returns `h2t_connectors_check/v1`.

Install returns `h2t_ops_install/v1`.

If the backend returns `missing_uv`, do not guess shell paths manually. Report
the hint and ask whether to install/fix `uv`.

If a connector returns `missing`, report the exact credential/config file or env
var from the backend output.

## Secrets Wizard

Triggered by user intent: "setup secrets", "configure credentials", "h2t-core:setup --secrets",
or when `connectors-check` reports any connector as `missing`.

### Step 1 — Skeleton

```bash
python setup_h2t.py secrets skeleton --json
```

From the result, show the user:
- Path to `secrets.env`
- For each key in `added`: its description and URL from `known_secrets.yaml`

### Step 2 — Fill API Keys

Tell the user:

> "Open `~/.dor/secrets/secrets.env` and paste your API keys. Here is where to get each one:
> - **EXA_API_KEY** — https://dashboard.exa.ai/api-keys
> - **NOTION_API_TOKEN** — https://www.notion.so/profile/integrations
> - **MEETGEEK_API_KEY** — https://app.meetgeek.ai/settings/api"

Open the file in an editor:

```bash
# macOS / Linux
code ~/.dor/secrets/secrets.env

# Windows
code $env:USERPROFILE\.dor\secrets\secrets.env
```

Wait for user to say "done" or "готово" before proceeding.

### Step 3 — Google OAuth

First, check which Google connectors are actually missing:

```bash
python setup_h2t.py connectors-check --json
```

For each connector in `["calendar", "gmail", "drive"]` where status is `missing`:
- Tell the user: "Connector **<name>** needs Google OAuth. This will open a browser window. Proceed? (yes/no)"
- Only after explicit confirmation, run the trigger command for that specific connector:

```bash
# calendar missing → ask → if yes:
h2t-ops calendar list --max 1 --json

# gmail missing → ask → if yes:
h2t-ops gmail list --max 1 --json

# drive missing → ask → if yes:
h2t-ops drive folders --json
```

Exit code 0 means authenticated. Exit code 4 (AuthError) means OAuth failed — report and
ask user to retry. Skip any connector that is already `ready`.

### Step 4 — Telegram Auth

Phase 1 — check status:

```bash
h2t-ops telegram auth status
```

If already authenticated: skip to Step 5.

Otherwise, ask user: "Telegram needs authentication. This will send a code to your phone. Proceed? (yes/no)"

Phase 2 — request code (ask user for phone number first):

```bash
h2t-ops telegram auth request-code --phone <phone>
```

Phase 3 — complete login (ask user for the code from Telegram):

```bash
h2t-ops telegram auth complete --phone <phone> --code <code>
```

If 2FA is enabled, also ask for password:

```bash
h2t-ops telegram auth complete --phone <phone> --code <code> --password <password>
```

Confirm success by re-running `auth status`.

### Step 5 — Preflight

Default (format-only, free):

```bash
python setup_h2t.py secrets preflight --json
```

If user asks for a live check (costs Exa tokens — confirm first):

```bash
python setup_h2t.py secrets preflight --live --json
```

Show a summary table: key → found/valid/connector.
Flag any `found: false` or `valid: false` with the URL from the registry.
