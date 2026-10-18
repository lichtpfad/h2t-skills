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

The repository is public. Nothing has to be granted before installing, and nothing has to
be cloned: a checkout is only for developing the pack. This applies to an agent installing
for a person too.

The one prerequisite for the CLI is [uv](https://docs.astral.sh/uv/getting-started/installation/);
it brings its own Python. For the plugin steps, Claude Code and git must already be
installed (`marketplace add` clones over HTTPS); without `claude` on PATH, `sync` skips
them. Then one command, the same for a person and for an agent:

```bash
@BOOTSTRAP@ sync
```

The command is the bootstrap of the current release. `scripts/release.py prepare` writes it
here on every release, so the line above is always the release `main` points at; in a
checkout before a release it holds a placeholder; take the command from `main` or from
the latest Release notes then.

What `sync` does, and each step is skipped when it already matches:

- installs the CLI — one package, `h2t-ops`, with every `h2t-*` command — as a `uv tool`,
  pinned to the release's wheel and constraints, and verifies it by running it;
- when `claude` is on PATH, adds the `lichtpfad` marketplace and installs or updates
  `h2t-core` and `h2t-ops` (`--scope user`) to the same release; keeps the last two versions
  of each plugin in the cache;
- in Codex it installs no plugins and prints the commands for them (see [Codex](#codex));
- reports what it changed, and the command to repeat when something failed — the same
  `sync`. Open Claude Code sessions need `/reload-plugins` or a new session.

Run it again to repair: it compares the machine with the release and redoes only what
differs. Replace `sync` with `update` to see "installed → target" and the CHANGELOG first
and answer yes; `update` asks in a terminal and refuses without one
(`reason: confirmation_required`). Once installed, `h2t-setup sync` and `h2t-setup update`
do the same — they hand over to the bootstrap of the current release themselves. One
exception: on Windows, a repair started from inside the installed tool prints that command
for you to run in a terminal, since the running tool is locked; the bootstrap itself runs
normally there.

Plugins and the CLI are one version. Plugins carry text only (skills, references, the hook
wrapper `hooks/run`); every hook runs as `h2t-hook <name>` from the CLI. When the CLI is
missing or at another version, the first `SessionStart` of a session says so once and names
the bootstrap; every skill starts with `h2t-ops version --expect <its release> --json` and
stops on a mismatch with the same remedy.

**Plugins by hand.** `sync` runs these for you; they are here for a machine where `claude`
was not on PATH when it ran. Typed by a person in Claude Code:

```text
/plugin marketplace add lichtpfad/h2t-skills
/plugin install h2t-core@lichtpfad
/plugin install h2t-ops@lichtpfad
/reload-plugins
```

The same, run by an agent or in any terminal — an agent cannot type slash commands:

```bash
claude plugin marketplace add lichtpfad/h2t-skills --json
claude plugin install h2t-core@lichtpfad --scope user --json
claude plugin install h2t-ops@lichtpfad --scope user --json
```

`marketplace add` reports "cloning via HTTPS": that is Claude Code filling its own plugin
cache, not a checkout you need.

Verify by state, not by what an installer printed:

```bash
uv tool list          # one package `h2t-ops` listing every h2t-* command
h2t-ops version --json
h2t-ops connectors
```

On Windows, hooks need Git Bash; without it skills and the CLI still work and hooks do not
run. For install troubleshooting, use
[H2T Ops External Install + Debug Log](docs/h2t-ops-external-install-debug.md).

### Codex

Skills and the CLI work in Codex; hooks do not, and `sync` does not install Codex plugins.
Install the CLI with the bootstrap above, then the plugins by hand — `sync` prints the same
lines when it finds `codex`:

```bash
codex plugin marketplace add lichtpfad/h2t-skills
codex plugin add h2t-core@lichtpfad
codex plugin add h2t-ops@lichtpfad
codex plugin list | grep lichtpfad      # installed, enabled
```

What a hook does in Claude Code, and what happens in Codex without it (spec §4):

| hook | in Codex |
|---|---|
| gather on the session skills (`<h2t-context>`, the briefing) | the skill runs `h2t-gather` itself when there is no fresh briefing |
| version check on `SessionStart` | the first command of every h2t skill, `h2t-ops version --expect` |
| structure-guard, grade-guard, plain-guard, plan-closer, new-repo-hint | **none** — no fallback |

Measured on Codex 0.159.2, 2026-10-14: Codex reports `plugin_hooks: removed` (#452), and
`h2t-creative` is listed twice, as `deck` and `source-command-deck` (#533).

## Where Your Data Lives (Где хранятся данные)

Everything the pack keeps lives under one root, `~/.h2t` (`H2T_PATH_ROOT` moves it, except
`run/`). Each class has its own directory, so what may be synced and what must not are never
in one folder:

```text
~/.h2t/
├── run/          the install of this machine: install.json, install.env, rollback/ — fixed
├── config/       yours to edit: domains.yaml, repo-mapping.yaml, paths.yaml, user.yaml
├── secrets/
│   ├── shared/   <provider>.env, google.client.json — may live on several machines
│   └── local/    google.token.json, telegram.session — this machine only
├── records/      one machine per file: sessions/<machine>/<project>/<session_id>.md,
│                 activity/<machine>.jsonl, evals/<machine>/, imports/dor-registry.jsonl
├── data/         what the pack made for you: research/, creative/profiles/
├── state/        rebuilt or safe to lose: index.sqlite, cursors/, backups/
├── logs/         hooks.jsonl, writes.jsonl, …
└── layout.json   the layout version
```

| class | sync it? |
|---|---|
| `config/`, `secrets/shared/`, `records/` | yes — the pack does not sync; use your own tool |
| `data/` | if you like |
| `run/`, `secrets/local/`, `state/`, `logs/` | **never** |

Places outside the root are declared in `config/paths.yaml` — `lake` (meetings and
transcripts), `inbox` (single downloaded files), `kb` — and set with
`h2t-ops paths set lake ~/somewhere`. A place not set falls back to `~/.h2t/data/<place>/`,
and the command says where it wrote. The vault is not set there: it is shared with POS and
comes from `H2T_PATH_VAULT` (default `~/.dor/vault`).

`config/user.yaml` is yours; the pack only reads it: `timezone`, `notion.tasks_database_id`,
`domain_patterns`.

Ask the pack instead of spelling a path — the answer stays right when a place moves:

```bash
h2t-ops paths list                       # every place, its path, sync class, and why
h2t-ops paths get secret:notion          # the file a key goes in
h2t-ops paths get records.sessions
```

**From 3.x.** `h2t-setup sync` migrates after installing the CLI; on its own the step is
`h2t-setup layout migrate` (`--machine <name>` when the machine cannot be named). It
**copies**: the old files stay where they were, are read as a fallback through 4.0.x, and
get a `MOVED-TO.txt`. Where sources disagree on a key — two old files, or a new file already
there, which is senior — the senior value wins and the other is kept beside it as
`<file>.from-<source>`; `h2t-ops doctor` lists those
copies. Migrate one machine first, sync `secrets/shared/` and `records/` to the next, then
migrate it.

**Rollback.** Pause the sync of `records/` and `secrets/shared/`, then
`h2t-setup layout rollback --sync-paused`. It removes only the files the migration created and
nobody changed since, restores what it added to, and lists the rest. If the migration's check fails because an old file
changed while it ran, close the program that writes that file, roll back, and migrate again.

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
- Google connectors need two files: the OAuth client (`h2t-ops paths get secret:google.client`,
  a Desktop OAuth client) and this machine's token (`h2t-ops paths get secret:google.token`).
  `h2t-ops google auth` creates the second from the first; see
  [First Google Login](#first-google-login) below.
- Every connector is optional. Setup reports the ones you skip as `missing`; leave their
  `KEY=` lines empty and answer "no" to their auth prompts (#534).
- Notion, MeetGeek, Granola, Exa and Dropbox use API keys from environment variables or from
  one file per provider — `h2t-ops paths get secret:notion` names Notion's.
- Telegram requires `TELEGRAM_API_ID` / `TELEGRAM_API_HASH` in `h2t-ops paths get secret:telegram`,
  then `h2t-ops telegram auth`.

### First Google Login

Two files are involved and they are not alike:

- The OAuth client identifies the **app** — a Desktop OAuth client. Create your own:
  Google Cloud Console → a project with the Gmail, Calendar and Drive APIs enabled → APIs &
  Services → Credentials → Create credentials → OAuth client ID → Desktop app → Download
  JSON, saved as the file `h2t-ops paths get secret:google.client` prints. Add yourself under the
  consent screen's *Test users* while the app is in Testing. Google's documented policy is
  that a Testing app's refresh token expires after 7 days; switching the consent screen to
  *In production* avoids that, and for your own account needs no verification — the
  consent shows an "unverified app" warning you click through. (Policy as documented by
  Google, not measured here.)
- The token (`h2t-ops paths get secret:google.token`) is the **user's** access to their own
  account. It holds the refresh token only; the access token is fetched per command and never
  written. Each machine logs in itself and keeps its own token: do not sync it, and never copy
  it between people — whoever holds it reads that mailbox.

Then one consent covers all three connectors:

```bash
h2t-ops google auth
h2t-ops gmail list --max 1 --json      # a message, not error[config]
```

Rerunning is harmless: a token that already carries every scope is left alone
(`already_authorized`); `--force` asks again.

## Reporting Problems

Something in the pack broken — a skill, a hook, an `h2t-*` command, or docs that contradict
what happens? Report it here, in `lichtpfad/h2t-skills`, rather than patching the installed
copy: the next update overwrites the plugin cache, and the fix reaches nobody else.

Ask your agent to "report an h2t bug". The `h2t-core:report-issue` skill sorts a pack defect
from a setup gap, strips private data, shows you the draft and files it only after your yes.
Without the GitHub CLI, use the [bug form](https://github.com/lichtpfad/h2t-skills/issues/new?template=bug.yml).
The repository is public — no tokens, mail or chat content in a report.

## Configuration

**Nothing here has to be set.** Every variable below has a working default, and the
installer deliberately writes to none of them — putting entries into a stranger's shell
profile is a mutation of their machine that an installer should not make. Set one only to
move a path off its default.

The single exception is `H2T_KB_ROOT`, which has no default: `h2t-ops:kb` refuses to run
without it.

| variable | default | moves |
| --- | --- | --- |
| `H2T_PATH_ROOT` | `~/.h2t` | the whole storage root except `run/` (see [Where Your Data Lives](#where-your-data-lives-где-хранятся-данные)) |
| `H2T_PATH_VAULT` | `~/.dor/vault` | the vault shared with POS; set it in POS's environment too |
| `H2T_MACHINE_NAME` | hostname (`DOR_MACHINE_NAME` is read as a fallback) | the machine segment in session paths |
| `H2T_MACHINE_ID` | `platform.node()`, slugified | the machine key in the MeetGeek uploads journal |
| `H2T_DEV_ROOT` | the checkout's parent, else `~/dev` | where sibling repositories are looked for |
| `H2T_CALENDAR_TZ` | `timezone` in `config/user.yaml`, else the system zone | the timezone calendar commands assume (`--tz` wins over it) |
| `H2T_PYTHON` | resolved: `~/.h2t/venv` → the h2t-ops CLI's own venv → `py -3.11` → `python3` → `uv run` | the interpreter hooks use, tried first |
| `H2T_KB_ROOT` | **none — required by `h2t-ops:kb`** | the knowledge base `llm-kb-engine` opens |

Other places — `lake`, `inbox`, `kb` — are set in `config/paths.yaml`, not by variables.
The 3.x path variables `H2T_CONFIG_ROOT`, `H2T_SESSION_ROOT`, `H2T_ACTIVITY_SPOOL`,
`H2T_SECRETS_FILE`, `H2T_EVALS_ROOT`, `H2T_EVALS_SPOOL` and `H2T_LAKE_ROOT` are no longer read;
`h2t-ops doctor` names any still set and what replaces it (see the 4.0.0 CHANGELOG).

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
Report:    h2t-core:report-issue    (an h2t skill, hook or command is broken → upstream issue, never a local patch)
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

The source is `h2t_ops/hooks/inject_context.py`, and
`tests/core/test_injected_index_matches_tree.py` holds it to the tree: every name it
advertises must have a `SKILL.md`, and it may not name a path the installer never creates.

## Development

Working on the pack itself is [CONTRIBUTING.md](CONTRIBUTING.md) — setup, the checks
CI runs, and the two gates that bite first.

```bash
git clone https://github.com/lichtpfad/h2t-skills.git
cd h2t-skills
uv sync
uv run pytest
uv run h2t-setup dev-sync      # the CLI from this checkout, editable: edits take effect
```

`dev-sync` installs the CLI editable with the checkout's own constraints and your extras,
and records the checkout in `~/.h2t/run/install.env` (`EDITABLE_ROOT`). It does not touch
git or the marketplace plugins. Load the plugins from the checkout instead:

```bash
claude --plugin-dir plugins/h2t-core --plugin-dir plugins/h2t-ops
pwsh scripts/claude-dev.ps1    # every plugin of the pack, the same way
```

On an editable install `h2t-setup sync` and `update` stop with `reason: editable` and
change nothing: update the checkout with git, then run `dev-sync` again.

Useful checks:

```bash
uv run pytest tests/connectors -q
uv run pytest tests/tools/setup/test_setup_h2t.py -q
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
- `uv` (the bootstrap brings Python 3.12; development needs Python 3.11+)
- `gh` CLI for GitHub-backed dev workflows

