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

Two backends, both commands of the CLI:

- `h2t-setup <sync|update|dev-sync> --json` — installs, repairs and updates the pack: the
  CLI and, in Claude Code, the plugins, to the release `main` points at (spec §7.3).
- `h2t-ops setup <verb> --json` — diagnoses and configures what is installed: `doctor`,
  `setup` (the doctor report plus the machine-name pin), `connectors-check`, `secrets`.

Its other verbs — `install-h2t-ops`, `repair`, `update` — are the 3.x install path: they
install from `main`, not from a release. Do not use them; `h2t-setup` replaces them.

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
2. JSON with `"ok": false` — show the user `error.hint` as it is and stop this skill until
   it is resolved. Do not run anything the hint names unless the user asks you to: on
   `reason: path` it is a command for the user to decide on. `error.details.reason` names the
   case: `not_installed`, `version` or `path`.
3. `command not found` — read `~/.h2t/run/install.env`
   (`grep -E '^(STATE|H2T_HOOK)=' ~/.h2t/run/install.env`). With `STATE=ready` the install
   is fine and PATH does not reach it: show the directory of the `H2T_HOOK=` path, ask the
   user to restart the harness, and offer `uv tool update-shell` for them to run. Without
   it there is no install: give the user `@BOOTSTRAP@ sync`.
4. Anything else (a non-zero exit without JSON, the usage text of an older CLI) — give the
   user `@BOOTSTRAP@ sync`.
<!-- version-check:end -->

In this skill, a user who asked to install, repair or update has asked for the remedy:
on outcomes 2–4 run the bootstrap the outcome names (with `sync`), or `h2t-setup sync`
when that is the hint, yourself, then rerun the version check. `uv tool update-shell`
stays the user's to run — it edits their shell profile. For a diagnosis only, show the
remedy and stop, as the block says.

## Modes

| User intent | Backend command |
| --- | --- |
| diagnose current install | `h2t-ops setup doctor --json` |
| first setup / repair | Step 3 `h2t-setup sync --json`; then Step 3b `h2t-ops setup setup --json`; then Step 4 `connectors-check --json` |
| update | Step 3: give the user `h2t-setup update` for their terminal; or, if they choose, `h2t-setup sync --json`; no Step 4 unless asked |
| the CLI runs editable from a checkout | Step 3: `h2t-setup dev-sync --json`, from inside that checkout |
| check connector readiness | `h2t-ops setup connectors-check --json` |
| run live connector status checks | `h2t-ops setup connectors-check --live --json` |
| include paid Research/Exa preflight | `h2t-ops setup connectors-check --live --include-paid --json` only after explicit user confirmation |

## Procedure

### Step 1: Prerequisites

The version check above is the first gate: a machine without the CLI is handled there —
outcome 3 or 4 hands over the bootstrap, which installs the current release in one
command. Everything below assumes the check passed.

`h2t-setup` drives `uv tool`, so check for `uv` before Step 3:

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
`uv: command not found` from deep inside `h2t-setup` and nothing else.

### Step 2: Doctor

For a diagnosis:

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
and name the remedy: Step 3 installs the plugins in Claude Code; by hand, the user types

```text
/plugin marketplace add lichtpfad/h2t-skills
/plugin install h2t-core@lichtpfad
```

If `entry_points.status` is `partial` or `missing`, the install needs Step 3. If it is
`ready`, skip Step 3 unless the user asked to repair or update.

POS/DOR absence is not an error. Phrase it as:

```text
optional_pos: not_configured
impact: lifecycle and connector provider I/O still work; POS publishing disabled
```

### Step 3: Install, repair or update — `h2t-setup`

**Never clone the repository to install.** `h2t-setup` installs the release's wheel; a
checkout is only ever one the user already develops in (`dev-sync` below).

**Install and repair** — `sync` needs no confirmation, and the user's request is the ask:

```bash
h2t-setup sync --json
```

It brings the machine to the release `main` points at, skipping every step that already
matches, so a second run is the repair. An installed `h2t-setup` hands over to that
release's own isolated bootstrap by itself. To add an extra of the CLI (`drawio`, for
`h2t-drawio generate`), add `--extra <name>`: it is recorded in `install.json` and every
later `sync` keeps it; `dev-sync` takes the same flag. An unknown name is exit 3,
`reason: unknown_extra`, with the known extras in `error.hint`. Read the result:

- exit 0 — report `result.done` and every line of `result.notes` as it is (they include the
  `codex plugin add` lines when Codex is present). When `result.reload_needed` is true,
  tell the user to run `/reload-plugins` or start a new session.
- exit 1, `error.type: provider` — something did not reach the target.
  `error.details.failed` lists `[subject, remedy]` pairs; show each, and `error.hint` (the
  first remedy) as it is. A **pinned marketplace** lands here: `sync` changed nothing in
  Claude Code, and the remedy lists `marketplace remove` / `add` / `install` lines.
  `remove` uninstalls the user's lichtpfad plugins — do not run those lines. Offer
  `h2t-setup update` (below), which asks and runs them with a restore on failure.
- exit 3 — read `error.details.reason`:
  - `editable` — the CLI is installed editable from the checkout in
    `error.details.checkout`. `sync` and `update` do not touch it. Tell the user to update
    the checkout with git; then `dev-sync` below.
  - `relaunch_required` — Windows, run from the installed tool, which the update replaces
    and Windows keeps locked. Show `error.hint`: it is the exact command for the user to run
    in a terminal.
  - no `reason` — e.g. `main` has no released pointer yet, or the release manifest is
    unreadable. Report `error.message` and `error.hint`.
- exit 6 — the network failed before anything was touched. Run the same command again
  when it is back.

**Update** — `h2t-setup update` is `sync` that first shows "installed → target" and the
CHANGELOG and asks. It asks only at a terminal: run from here it refuses with exit 3,
`reason: confirmation_required`, and changes nothing. So do not run it; give the user the
line for their terminal:

```text
h2t-setup update
```

If the user would rather not review the changes, `h2t-setup sync --json` above brings the
install to the same target without asking — run it on their word.

**Editable install** — from inside the checkout the CLI is installed from:

```bash
cd "<checkout>"
h2t-setup dev-sync --json
```

It installs the CLI editable with the checkout's constraints and the user's extras; it does
not touch git or the marketplace plugins (its note says to load them with
`claude --plugin-dir`). Exit 3 with `reason: not_a_checkout` means the directory is not an
h2t-skills checkout.

Verify by state, not by the output: rerun the version check at the top of this skill. It
must answer `"ok": true`.

### Step 3b: Pin the machine name

For first setup and repair, after Step 3:

```bash
h2t-ops setup setup --json
```

It is `doctor` plus one write: `env.H2T_MACHINE_NAME` in `~/.claude/settings.json`, so
session records stop following a macOS hostname (ADR 0003). Report the doctor part as
Step 2 says, including the `plugin_cache` remedy. Then read `machine_name.status`:

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
- h2t-ops is installed as `h2t-ops` by `h2t-setup`, from the release wheel; never from a
  clone.
- h2t-core setup can work before POS/DOR exists.
- Missing POS/DOR disables publishing only; it does not block lifecycle or
  provider I/O.

## Expected Outputs

Doctor returns `h2t_setup_doctor/v1`.

Connector readiness returns `h2t_connectors_check/v1`.

`h2t-setup` returns the standard envelope with `provider: setup`; on success `result`
carries `done`, `failed`, `reload_needed` and `notes`.

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
- `files` — one file per provider the placeholders went into (`<provider>.env` under `path`, the
  secrets directory), each with its own `added` keys
- For each key in `added`: its description and URL from `known_secrets.yaml`

`skipped` holds keys that are already set — in those files, in the environment, or in any
other secrets file the connectors read, `~/.h2t/config/secrets/*.env` included. Do not ask
for them.

### Step 2 — Fill API Keys

If `added` is empty, skip to Step 3. Otherwise tell the user to open each `files[...].path` and
paste a value after each `KEY=` from its `added` — one message together with Step 1, the list shown
once. Do not list keys from memory: the registry is the list, and a list copied here falls
behind it.

Open the file in an editor — the same line on macOS, Linux and Git Bash on Windows, with
each file's `path` from Step 1 quoted as is. If `code` is not on PATH, give the user those paths to open in
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
h2t-ops telegram auth status --json
```

If already authenticated: skip to Step 5.

Otherwise, ask user: "Telegram needs authentication. This will send a code to your phone. Proceed? (yes/no)"

Phase 2 — request code (ask user for phone number first):

```bash
h2t-ops telegram auth request-code --phone <phone> --json
```

Phase 3 — complete login (ask user for the code from Telegram):

```bash
h2t-ops telegram auth complete --phone <phone> --code <code> --json
```

If 2FA is enabled, also ask for password:

```bash
h2t-ops telegram auth complete --phone <phone> --code <code> --password <password> --json
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
