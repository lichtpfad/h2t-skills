---
name: setup
description: "Install, repair, update, and diagnose h2t-core / h2t-ops delivery. Use for 'h2t setup', 'install h2t-ops', 'repair h2t', 'update h2t', connector auth/status checks, or sharing h2t tools with another machine/user."
compatibility: "Claude Code"
metadata:
  author: lichtpfad
  version: 1.2.1
---

# h2t Setup

Use this skill as the install/update/doctor surface for h2t-core and h2t-ops.

The skill is a thin wrapper around the deterministic backend, a command of the CLI:

```text
h2t-ops setup <verb> --json
```

Do not reimplement setup logic in prose. Run the backend, inspect structured
output, and only then explain the next action.

<!-- version-check:begin -->
## Version check

Run this before any other command of this skill:

```bash
h2t-ops version --expect @VERSION@ --json
```

Act on the result, in this order:

1. JSON with `"ok": true` — continue.
2. JSON with `"ok": false` — show the user `error.hint` and follow it before going on.
   `result.reason` names the case: `not_installed`, `version` or `path`.
3. `command not found` — read `~/.h2t/run/install.env`
   (`grep -E '^(STATE|H2T_HOOK)=' ~/.h2t/run/install.env`). With `STATE=ready` the install
   is fine and PATH does not reach it: show the directory of the `H2T_HOOK=` path, ask the
   user to restart the harness, and offer `uv tool update-shell` for them to run. Without
   it there is no install: give the user `@BOOTSTRAP@ sync`.
4. Anything else (a non-zero exit without JSON, the usage text of an older CLI) — give the
   user `@BOOTSTRAP@ sync`.
<!-- version-check:end -->

## Modes

| User intent | Backend command |
| --- | --- |
| diagnose current install | `doctor --json` |
| first setup / repair | `setup --json` (the doctor report plus the machine-name pin); Step 3 only if `entry_points.status` is `partial` or `missing`; then Step 4 `connectors-check --json` |
| update | `setup --json`, then Step 3 whatever `entry_points` says — the user asked for a newer h2t-ops; no Step 4 unless asked |
| check connector readiness | `connectors-check --json` |
| run live connector status checks | `connectors-check --live --json` |
| include paid Research/Exa preflight | `connectors-check --live --include-paid --json` only after explicit user confirmation |

## Procedure

### Step 1: Prerequisites

The version check above is the first gate: `h2t-ops setup` is part of the CLI it checks, so
a machine without the CLI is handled there — outcome 3 or 4 hands the user the bootstrap,
which installs the current release in one command. Everything below assumes the check
passed.

`install-h2t-ops` drives `uv tool`, so check for `uv` before Step 3:

The snippet below is POSIX shell. On Windows run it from Git Bash, which the audit
confirmed present as `/usr/bin/sh`; native PowerShell or CMD will not parse `if !
command -v` and would fail before printing the message it exists to print. The install
line the message prints for Windows is PowerShell, because that is what installs uv
there — it is what the user runs next, not what runs this snippet.

```bash
if ! command -v uv >/dev/null 2>&1; then
  echo "ERROR: uv is not on PATH, and every remedy this skill offers needs it." >&2
  echo "Install it, then re-run:" >&2
  echo "  macOS/Linux  curl -LsSf https://astral.sh/uv/install.sh | sh" >&2
  echo "  Windows      powershell -c \"irm https://astral.sh/uv/install.ps1 | iex\"" >&2
  exit 3
fi
```

The message names the missing prerequisite and how to install it, and exits 3 — the config
exit code the connector contract already uses. Without it, a machine with no uv would see
`uv: command not found` from deep inside `install-h2t-ops` and nothing else.

### Step 2: Doctor first

For a diagnosis, start with the line below. First setup, repair and update start with Step
2b instead — `setup` returns this same report:

```bash
h2t-ops setup doctor --json
```

Report:

- platform;
- `uv` status and path;
- `h2t-ops` status, path, version;
- `entry_points` status — all four CLIs (`h2t-ops`, `h2t-gather`, `h2t-activity-log`, `h2t-handoff`);
- optional POS/DOR status;
- whether plugin cache is visible.

`plugin_cache.status: missing` means no installed h2t-core was found under Claude Code's or
Codex's plugin cache (`CLAUDE_CONFIG_DIR` / `CODEX_HOME` when set). The skill still runs — it
may be loaded from a checkout — but hooks and skills will not reach other sessions. Report it
and name the remedy, which the user types:

```text
/plugin marketplace add lichtpfad/h2t-skills
/plugin install h2t-core@lichtpfad
```

If `entry_points.status` is `partial` or `missing`, proceed to Step 3 to install or reinstall.
If it is `ready`, skip Step 3 unless the user asked to update — the same rule as the Modes
table.

POS/DOR absence is not an error. Phrase it as:

```text
optional_pos: not_configured
impact: lifecycle and connector provider I/O still work; POS publishing disabled
```

### Step 2b: Pin the machine name

For first setup, repair and update — in place of Step 2's `doctor`, not after it; a plain
diagnosis stays `doctor`:

```bash
h2t-ops setup setup --json
```

It is `doctor` plus one write: `env.H2T_MACHINE_NAME` in `~/.claude/settings.json`, so
session records stop following a macOS hostname (ADR 0003). Report the doctor part as
Step 2 says, including the `plugin_cache` remedy and the rule for Step 3. Then read
`machine_name.status`:

- `unchanged` / `written` — report the value.
- `needs_choice` — nothing was written: today's name (`today`) has no folder in the
  session root, while other folders (`candidates`) do. One of them may be this machine
  under an older hostname; another may belong to a different machine. Show both and ask
  which name this machine's history lives under, then pin the answer:

  ```bash
  h2t-ops setup setup --machine-name <answer> --json
  ```

  If the user says the machine is new, pin the value of the `today` field
  (`--machine-name <today>`). `today` is `H2T_MACHINE_NAME`, else `DOR_MACHINE_NAME`, else
  the hostname lowercased up to the first dot.
- `error` — report it; the settings file was left untouched.

### Step 3: Install or repair h2t-ops

Pick the source from `h2t_ops.version` in the report — `doctor` or `setup`, the payload is
the same:

- it reads `(editable <path>)` — h2t-ops runs from a checkout. Keep it that way:
  `--source <path>`, which installs editable again. `--source main` would replace the
  checkout with the GitHub version, and edits in the checkout would stop taking effect.
- anything else, or h2t-ops is missing — `--source main`.

**Never clone the repository to install.** `--source main` is
`git+https://github.com/lichtpfad/h2t-skills.git`: uv fetches it into its own cache, and
that is the whole install. A `<path>` source is only ever a checkout that is *already* the
editable install the report shows — never one you create. The same holds for plugins: a
person types `/plugin …`, an agent runs `claude plugin marketplace add lichtpfad/h2t-skills`
and `claude plugin install h2t-core@lichtpfad` (README, Channel 1). Neither needs a clone.

First run a dry-run:

```bash
h2t-ops setup install-h2t-ops --source <source> --dry-run --json
```

Show the command to the user. Ask before running the real install because it
modifies the user's `uv tool` environment.

Real install:

```bash
h2t-ops setup install-h2t-ops --source <source> --json
```

### Step 4: Connector readiness

Default connector check is credential-only and read-only:

```bash
h2t-ops setup connectors-check --json
```

This must not write provider data, POS/DOR state, Notion pages, Drive files, or
calendar events.

Live checks require explicit user intent:

```bash
h2t-ops setup connectors-check --live --json
```

Research/Exa preflight can use a paid provider request. Only run it if the user
explicitly asks:

```bash
h2t-ops setup connectors-check --live --include-paid --json
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
h2t-ops setup secrets skeleton --json
```

From the result, show the user:
- `path` — the file the placeholders went into
- For each key in `added`: its description and URL from `known_secrets.yaml`

`skipped` holds keys that are already set — in that file, in the environment, or in any
other secrets file the connectors read, `~/.h2t/config/secrets/*.env` included. Do not ask
for them.

### Step 2 — Fill API Keys

If `added` is empty, skip to Step 3. Otherwise tell the user to open `path` and paste a
value after each `KEY=` from `added` — one message together with Step 1, the list shown
once. Do not list keys from memory: the registry is the list, and a list copied here falls
behind it.

Open the file in an editor — the same line on macOS, Linux and Git Bash on Windows, with
`path` from Step 1 quoted as is. If `code` is not on PATH, give the user `path` to open in
any editor instead:

```bash
code "<path>"
```

Wait for user to say "done" or "готово" before proceeding.

### Step 3 — Google OAuth

First, check which Google connectors are actually missing:

```bash
h2t-ops setup connectors-check --json
```

Calendar, Gmail and Drive share one token, so this is one question and one command, not
three. If none of the three is `missing`, skip this step. Otherwise ask: "Gmail, Calendar
and Drive need one Google sign-in in the browser. Proceed? (yes/no)" — a user who wants
none of them answers no, and that is a finished setup, not a failure.

Only after an explicit yes:

```bash
h2t-ops google auth --json
```

- exit 0, `status: authorized` or `already_authorized` — done; report `token_path`.
- exit 3 — `credentials.json` is missing. That file is the user's own Google Cloud OAuth
  client, and nothing here can create it. Show the error's `hint` (the Console steps) and
  the path, wait for "done", rerun. Never offer someone else's file.
- exit 4 — consent was refused or failed; report and offer to rerun.

`--no-browser` prints the consent URL instead of opening it. Google still redirects to
`localhost` on the machine running the command, so over SSH the printed port must be
forwarded (`ssh -L <port>:localhost:<port>`) for the consent to complete.

Verify by state, not by the exit code alone:

```bash
h2t-ops gmail list --max 1 --json
```

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
h2t-ops setup secrets preflight --json
```

If user asks for a live check (costs Exa tokens — confirm first):

```bash
h2t-ops setup secrets preflight --live --json
```

Show a summary table: key → found/valid/connector.
Flag any `found: false` or `valid: false` with the URL from the registry.
