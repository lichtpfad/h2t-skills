# h2t-skills Agent Notes

This repo is a Claude Code plugin pack. It contains:
- `plugins/h2t-*` — plugin source directories (skills, hooks, agents)
- `h2t_ops/` — Python package for operational connectors (Notion, Gmail, Calendar, etc.)
- `lib/` — shared utilities (activity, gather, skill_graph, clients)
- `scripts/` — bump_plugin.py, claude-dev.ps1, hooks/

The baseline plan for operational connector work is
[docs/h2t-ops-roadmap.md](docs/h2t-ops-roadmap.md).

Use it before creating H2T-OPS specs, plans, PRs, or GitHub issues. It defines the current
`h2t-ops` / `h2t_ops` identity, migration waves, connector inventory, and issue backlog.

## h2t-ops Ownership Boundary

`h2t-ops` owns operational connectors ONLY: Notion, Gmail, Calendar, Drive, MeetGeek, Telegram, research.
Root `h2t` command and Python package belong to `h2t-ai`. Do not create `h2t` entrypoints here.

## Plugin Development

Dev session (no duplicate skills): `pwsh scripts/claude-dev.ps1`

## Key Commands

```bash
# Tests (no venv activation — use direct paths)
C:/dev/h2t-skills/.venv/Scripts/pytest tests/
C:/dev/h2t-skills/.venv/Scripts/pytest tests/connectors/   # connector-only

# Version bump (updates plugin.json + CHANGELOG)
python scripts/bump_plugin.py <plugin-name> <version>

# Run h2t-ops CLI without install
uv run h2t-ops <connector> <command>
```

## Global CLI tools (uv tool install)

`h2t-skills` exposes 4 global entry points: `h2t-ops`, `h2t-handoff`, `h2t-gather`, `h2t-activity-log`.

**When to re-run:**
- After `git pull` that adds or renames an entry point in `pyproject.toml`
- After any session where `h2t-handoff` / `h2t-gather` is not found by `command -v`
- Verify: `uv tool list` — all 4 should appear under one package

```bash
# Install / update all entry points from source
uv tool install --editable C:/dev/h2t-skills

# Verify
uv tool list   # should show h2t-ops, h2t-handoff, h2t-gather, h2t-activity-log
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
