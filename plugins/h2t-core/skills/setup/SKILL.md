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
