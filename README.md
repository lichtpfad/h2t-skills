# H2T Skills

Claude Code plugin suite for H2T workflows: lifecycle context, provider connectors, docs/dev automation, architecture diagrams, creative assets, and education tooling.

## Plugins

| Plugin | Main skills | Purpose |
| --- | --- | --- |
| `h2t-core` | `h2t-core:setup`, `session-start`, `handoff`, `init-project`, `scaffold-project`, `agent-profile` | Session lifecycle, setup, project registration, local context continuity |
| `h2t-ops` | `h2t-ops:connectors`, `h2t-ops:research`, `h2t-ops:daily-brief` | Provider I/O through `h2t-ops`: Drive, Gmail, Calendar, Notion, Telegram, MeetGeek, Granola, research |
| `h2t-dev` | `docs-lint`, `pre-merge-check`, `milestone-closure`, `github-issues` | Development and documentation lifecycle automation |
| `h2t-arch` | `drawio`, `diagram-node`, `node-researcher` | Architecture and diagram workflows |
| `h2t-creative` | `deck`, `landing`, `design`, `style-create`, `style-validate` | Landing pages, decks, and visual asset generation |
| `h2t-edu` | education/transcript skills | Education content and transcript workflows |

## Install For A User

The repository is currently private. External users need GitHub read access to `lichtpfad/h2t-skills` before installing.

In Claude Code:

```text
/plugin marketplace add lichtpfad/h2t-skills
/plugin install h2t-core@lichtpfad
/plugin install h2t-ops@lichtpfad
/reload-plugins
```

Then run setup:

```text
/h2t-core:setup doctor
/h2t-core:setup install h2t-ops
/h2t-core:setup connectors-check
```

CLI smoke:

```bash
h2t-ops --version
h2t-ops connectors
h2t-ops drive --help
```

For external install troubleshooting, use [H2T Ops External Install + Debug Log](docs/h2t-ops-external-install-debug.md).

## h2t-ops Connectors

`h2t-ops:connectors` is the provider I/O hub. It should be loaded for provider-owned URLs and provider tasks:

- Google Drive / Docs / Sheets / Slides links;
- Google Calendar and Meet links;
- Gmail / mail.google.com links;
- Notion links;
- Telegram links;
- MeetGeek meetings, transcripts, summaries, recordings;
- Granola notes, AI summaries, verbatim transcripts, folders.

Agents should use the `h2t-ops` CLI instead of raw provider APIs when a connector command exists.

Examples:

```bash
h2t-ops drive export DOC_ID --format text --dest ./doc.txt --json
h2t-ops gmail search "from:person@example.com" --max 10 --json
h2t-ops calendar list --max 10 --json
h2t-ops notion get PAGE_ID --format md
h2t-ops telegram auth status
h2t-ops meetgeek transcript MEETING_ID --format md
h2t-ops granola list --limit 10 --format md
```

## Setup Notes

- `h2t-core:setup` owns install, repair, doctor, and connector readiness checks.
- `h2t-ops` is installed as a Python CLI via `uv tool install --reinstall git+https://github.com/lichtpfad/h2t-skills.git`.
- POS/DOR configuration is optional for connector I/O.
- Google connectors require a local OAuth token store.
- Notion, MeetGeek, Granola, and Exa use API keys in `~/.dor/secrets/secrets.env` or environment variables.
- Telegram requires `~/.config/telegram/config.json` with `api_id` / `api_hash`, then `h2t-ops telegram auth`.

## Development

```bash
uv sync
uv run pytest
uv run h2t-ops --help
```

Useful checks:

```bash
uv run pytest tests/connectors -q
uv run pytest plugins/h2t-core/skills/setup/scripts/test_setup_h2t.py -q
python scripts/check_marketplace_sync.py
```

## Structure

```text
.claude-plugin/marketplace.json
plugins/
  h2t-core/
  h2t-ops/
  h2t-dev/
  h2t-arch/
  h2t-creative/
  h2t-edu/
h2t_ops/
  cli.py
  connectors/
docs/
  h2t-ops-external-install-debug.md
  h2t-ops-testing-plan.md
  reports/
  superpowers/
```

## Requirements

- Claude Code
- GitHub access to `lichtpfad/h2t-skills`
- `git`
- `uv`
- Python 3.11+
- `gh` CLI for GitHub-backed dev workflows

