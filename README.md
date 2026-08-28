# H2T Skills

Claude Code plugin suite for H2T workflows: lifecycle context, provider connectors, docs/dev automation, architecture diagrams, and creative assets.

## Plugins

| Plugin | Main skills | Purpose |
| --- | --- | --- |
| `h2t-core` | `h2t-core:setup`, `session-start`, `handoff`, `init-project`, `scaffold-project`, `agent-profile` | Session lifecycle, setup, project registration, local context continuity |
| `h2t-ops` | `h2t-ops:connectors`, `h2t-ops:research`, `h2t-ops:daily-brief` | Provider I/O through `h2t-ops`: Drive, Gmail, Calendar, Notion, Telegram, MeetGeek, Granola, research |
| `h2t-dev` | `docs-lint`, `pre-merge-check`, `milestone-closure`, `github-issues` | Development and documentation lifecycle automation |
| `h2t-arch` | `drawio`, `diagram-node` | Architecture and diagram workflows |
| `h2t-creative` | `deck`, `landing`, `design`, `style-create`, `style-validate` | Landing pages, decks, and visual asset generation |

## Install For A User

The repository is public. Nothing has to be granted before installing.

Installation has **two channels, and the first does not move the second.** The marketplace
delivers skills, hooks and agents into the plugin cache; `uv tool install` puts nine CLI
commands on PATH. Skills call those commands. Stop after the first channel and the skills
load, then die on their first command.

**Channel 1 — plugins.** In Claude Code:

```text
/plugin marketplace add lichtpfad/h2t-skills
/plugin install h2t-core@lichtpfad
/plugin install h2t-ops@lichtpfad
/reload-plugins
```

**Channel 2 — the CLI.** `/h2t-core:setup install-h2t-ops` runs it for you:

```text
/h2t-core:setup doctor
/h2t-core:setup install-h2t-ops
/h2t-core:setup connectors-check
```

Verify **channel 2 by its own state**, not by what the marketplace printed — a plugin
update never touches the entry points:

```bash
uv tool list          # expect one package `h2t-ops` listing nine commands
h2t-ops --version
h2t-ops connectors
```

```text
h2t-ops v0.2.1
- h2t-activity-log      - h2t-hook                   - h2t-project-register
- h2t-gather            - h2t-ops                    - h2t-scaffold-project
- h2t-handoff           - h2t-project-audit-report   - h2t-project-audit-scan
```

Fewer than nine, or no `h2t-ops` package at all, means channel 2 did not land. Rerun it
from a checkout with `uv tool install --editable .`, or from the remote:

```bash
uv tool install --reinstall git+https://github.com/lichtpfad/h2t-skills.git
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
- POS/DOR configuration is optional for connector I/O.
- Google connectors require a local OAuth token store.
- Notion, MeetGeek, Granola, and Exa use API keys in `~/.dor/secrets/secrets.env` or environment variables.
- Telegram requires `~/.config/telegram/config.json` with `api_id` / `api_hash`, then `h2t-ops telegram auth`.

## Configuration

**Nothing here has to be set.** Every variable below has a working default, and the
installer deliberately writes to none of them — putting entries into a stranger's shell
profile is a mutation of their machine that an installer should not make. Set one only to
move a path off its default.

The single exception is `H2T_KB_ROOT`, which has no default: `h2t-ops:kb` refuses to run
without it.

| variable | default | moves |
| --- | --- | --- |
| `H2T_CONFIG_ROOT` | `~/.h2t/config` | `domains.yaml`, `repo-mapping.yaml`, `secrets/` |
| `H2T_SESSION_ROOT` | `~/.h2t/sessions` | where handoff records are written and read |
| `H2T_ACTIVITY_SPOOL` | `~/.h2t/activity/spool.jsonl` | the session activity spool |
| `H2T_MACHINE_NAME` | hostname (`DOR_MACHINE_NAME` is read as a fallback) | the machine segment in session paths |
| `H2T_MACHINE_ID` | `platform.node()`, slugified | the machine key in the MeetGeek uploads journal |
| `H2T_DEV_ROOT` | the checkout's parent, else `~/dev` | where sibling repositories are looked for |
| `H2T_SECRETS_FILE` | first hit of `~/.h2t/config/secrets/secrets.env`, `~/.dor/secrets/secrets.env`, `~/.dor/secrets.env` | the secrets file, searched first |
| `H2T_CALENDAR_TZ` | `Asia/Jerusalem` | the timezone calendar commands assume |
| `H2T_EVALS_ROOT` | `~/.h2t/evals` | the eval telemetry tree |
| `H2T_LAKE_ROOT` | `~/.dor/lake` | the MeetGeek media lake |
| `H2T_PYTHON` | resolved: `~/.h2t/venv` → `py -3.11` → `python3` → `uv run` | the interpreter hooks use, tried first |
| `H2T_KB_ROOT` | **none — required by `h2t-ops:kb`** | the knowledge base `llm-kb-engine` opens |

`H2T_OPS`, `H2T_PLUGIN_ROOT`, `H2T_DOCS_LINT_SCRIPT`, `H2T_LINT_HOOK_TIMEOUT` and the
`H2T_DEPLOY_*` family are set by hooks and by the deploy executor for the process they
spawn. They are internal plumbing; setting them by hand is not part of any install.

## What Your Agent Is Told

A `SessionStart` hook injects a short skill index into every session, so an agent in your
repository knows this pack exists without being told. It is printed here for the case where
it does not fire — a harness that does not run Claude Code hooks, or a failed hook. Paste it
into your project's `CLAUDE.md` and nothing is lost.

```text
H2T SKILLS — invoke with the Skill tool when relevant:

Session:   h2t-core:session-start | h2t-core:handoff | h2t-core:init-project | h2t-core:scaffold-project
Setup:     h2t-core:setup           (install, repair, doctor, connector readiness)
Research:  h2t-ops:research        (Exa semantic search — use for any web/news/paper lookup)
Connectors: h2t-ops:connectors     (Google, Notion, Telegram, MeetGeek command map and safety)
Daily:     h2t-ops:daily-brief     (daily ops brief from connected sources)
Docs:      h2t-dev:docs-lint | h2t-dev:docs-sync-labels
Diagrams:  h2t-arch:drawio | h2t-arch:diagram-node

Commands:  h2t-ops | h2t-gather | h2t-handoff | h2t-activity-log  (on PATH after 'uv tool install')
Python:    skills resolve their own interpreter — never build a path to one
Config:    ~/.h2t/config/  (domains.yaml, repo-mapping.yaml, secrets/)
Standards: bundled in h2t-dev skill references — load via Read when needed
```

The source is `plugins/h2t-core/hooks-handlers/inject-h2t-context`, and
`tests/core/test_injected_index_matches_tree.py` holds it to the tree: every name it
advertises must have a `SKILL.md`, and it may not name a path the installer never creates.

## Development

Working on the pack itself is [CONTRIBUTING.md](CONTRIBUTING.md) — setup, the checks
CI runs, and the two gates that bite first.

```bash
uv sync
uv run pytest
uv run h2t-ops --help
```

Useful checks:

```bash
uv run pytest tests/connectors -q
uv run pytest plugins/h2t-core/skills/setup/scripts/test_setup_h2t.py -q
uv run python scripts/check_marketplace_sync.py
```

## Public Landing

The page explaining the pack lives in a different repository; only its source is here.

| what | where |
|---|---|
| source recipe | `docs/landing/recipe.yaml` |
| built page | `skills/index.html` in `lichtpfad/h2t-landings` |
| public URL | https://lichtpfad.github.io/h2t-landings/skills/ |

Rebuild and deploy steps: [docs/landing/README.md](docs/landing/README.md). The built HTML
is deliberately not committed here — one artifact in two repositories drifts silently.

## Structure

```text
.claude-plugin/marketplace.json
plugins/
  h2t-core/
  h2t-ops/
  h2t-dev/
  h2t-arch/
  h2t-creative/
h2t_ops/
  cli.py
  connectors/
docs/
  h2t-ops-external-install-debug.md
  h2t-ops-testing-plan.md
  landing/          # recipe for the public landing (built into h2t-landings)
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

