# h2t-skills Agent Notes

This repo is a Claude Code plugin pack. It contains:
- `plugins/h2t-*` — plugin source directories (skills, hooks, agents)
- `h2t_ops/` — Python package for operational connectors (Notion, Gmail, Calendar, etc.)
- `lib/` — shared utilities (activity, cli, eval, gather, practice_harvest)
- `scripts/` — bump_plugin.py, claude-dev.ps1, hooks/

The baseline plan for operational connector work is
[docs/h2t-ops-roadmap.md](docs/h2t-ops-roadmap.md).

Use it before creating H2T-OPS specs, plans, PRs, or GitHub issues. It defines the current
`h2t-ops` / `h2t_ops` identity, migration waves, connector inventory, and issue backlog.

## h2t-ops Ownership Boundary

`h2t-ops` owns operational connectors ONLY: Notion, Gmail, Calendar, Drive, MeetGeek, Granola, Telegram, research.
Root `h2t` command and Python package belong to `h2t-ai`. Do not create `h2t` entrypoints here.

## Plugin Development

Dev session (no duplicate skills): `pwsh scripts/claude-dev.ps1`

## Key Commands

This repo is developed on two machines and the paths differ. Run the line for the one you
are on; a command that does not exist is worse than no command.

```bash
# Tests — Windows
C:/dev/h2t-skills/.venv/Scripts/pytest tests/
C:/dev/h2t-skills/.venv/Scripts/pytest tests/connectors/   # connector-only

# Tests — macOS (bare `python` is not on PATH; the venv is uv-built and has no pip)
.venv/bin/pytest tests/
.venv/bin/pytest tests/connectors/

# Lint — Windows has ruff in the venv, macOS does not
C:/dev/h2t-skills/.venv/Scripts/ruff check plugins/ lib/ h2t_ops/
uvx ruff check plugins/ lib/ h2t_ops/

# Git hooks — once per clone. Sets core.hooksPath; git then runs scripts/hooks/pre-commit,
# which blocks a commit that drifts marketplace.json against any plugin.json (#74).
sh scripts/hooks/install.sh

# Version bump — two literal arguments. Updates plugin.json and marketplace.json only;
# the CHANGELOG is written by hand (grep -c CHANGELOG scripts/bump_plugin.py -> 0).
.venv/bin/python scripts/bump_plugin.py <plugin-name> <version>

# Run h2t-ops CLI without install
uv run h2t-ops <connector> <command>
```

Bare `python` is **not** on PATH here — only `python3` and `.venv/bin/python`. The venv is
uv-built, so it ships without `pip`; this one has it because it was installed by hand. Do not
rely on that on a fresh checkout — `uv pip install --python .venv/bin/python <pkg>` works
either way.

## Global CLI tools (uv tool install)

`h2t-skills` exposes **9** global entry points, all from one package:

| command | what it does |
|---|---|
| `h2t-ops` | the connector CLI — Notion, Gmail, Calendar, Drive, MeetGeek, Granola, Telegram, research |
| `h2t-gather` | collects session context and prints the `BRIEFING:` / `GATHER_META:` block |
| `h2t-handoff` | writes the session record — spool first, markdown mirror second |
| `h2t-activity-log` | appends session start/end to the activity spool |
| `h2t-project-register` | applies a project registration to repo-mapping.yaml and domains.yaml |
| `h2t-project-audit-scan` | scans a project tree for the audit |
| `h2t-project-audit-report` | renders that scan |
| `h2t-scaffold-project` | creates and registers a new project |
| `h2t-hook` | runs a plugin hook handler, resolved when the hook fires |

**When to re-run:**
- After `git pull` that adds or renames an entry point in `pyproject.toml`
- After any session where `h2t-handoff` / `h2t-gather` is not found by `command -v`
- Verify with `uv tool list` — all 9 under one package. Judge the listing, not the
  install command's output.

```bash
# Install / update all entry points from source
uv tool install --editable C:/dev/h2t-skills   # Windows
uv tool install --editable .                   # macOS, from the checkout

uv tool list
```

If `uv tool install` conflicts with an existing `h2t-ops` version:
```bash
uv tool uninstall h2t-ops
uv tool install --editable C:/dev/h2t-skills
```

## Connector Standard

New connectors: `ConnectorSpec` + lazy registry in `h2t_ops/connectors/`.
Output: human / `--format md` / `--json` universal envelope.
Exit codes: 0 ok, 1 provider, 2 usage, 3 config, 4 auth, 5 not found, 6 network.
