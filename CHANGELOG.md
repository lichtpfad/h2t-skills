# Changelog

One CHANGELOG for the whole pack from 4.0.0 on. The per-plugin files
(`plugins/*/CHANGELOG.md`) are the history up to 3.x; their `Unreleased` entries ship in
4.0.0.

## 4.0.0

The pack is rebuilt around one package (#541), and its data moves to one root, `~/.h2t`
(#548): see "One storage root" below.

### One version, one install

- **One version for the whole pack.** The CLI (the distribution `h2t-ops`, package
  `h2t_ops`) and all five plugins carry the same version, 4.0.0. A plugin and the CLI it calls can no longer drift apart unnoticed.
- **The install is one command:** `uvx --isolated --python 3.12.11 --managed-python -c
  "<constraints>" --from "h2t-ops @ <wheel>" h2t-setup sync`, with the release's own wheel
  and constraints. The exact line for this release is in the README and in the Release
  notes. It needs only uv, and no clone.
- **`h2t-setup sync`** brings a machine to the release `main` points at: the CLI as a
  `uv tool` (verified by running it), and in Claude Code the `lichtpfad` marketplace with
  `h2t-core` and `h2t-ops` at the same version. Each step is skipped when it already
  matches, so running it again is the repair. It keeps the last two versions of each plugin
  in the cache and snapshots what it changes under `~/.h2t/run/rollback/`.
- **`h2t-setup update`** is `sync` that first shows "installed → target" and this
  CHANGELOG and asks. It asks only in a terminal; without one it refuses with
  `reason: confirmation_required`, and `sync` is the form for an agent.
- **`h2t-setup dev-sync`** installs the CLI editable from a checkout. On an editable install
  `sync` and `update` stop with `reason: editable` and change nothing.
- **A marketplace pinned to a ref** is not re-pinned by `sync`: re-pinning means
  `marketplace remove`, which uninstalls the plugins. `sync` shows the commands; `update`
  asks and runs them, restoring scope and the disabled state.
- **Codex:** skills and the CLI are supported; `sync` installs no Codex plugins and prints
  the `codex plugin add` commands instead.
- **From 3.x:** run the bootstrap once. `/plugin marketplace update` alone brings the
  plugins and leaves the CLI behind; the first session after it says so and names the
  bootstrap.

### Plugins carry text only

- Every Python script left the plugins. Skills, references, agents and `hooks/hooks.json`
  stay; the code lives in the `h2t_ops` package and is reached through `h2t-*` commands
  (19 of them, among them `h2t-setup`, `h2t-hook`, `h2t-docs-lint`, `h2t-drawio`,
  `h2t-creative`, `h2t-runbook`).
- Every h2t skill starts with `h2t-ops version --expect 4.0.0 --json` and stops with the
  remedy when the CLI is missing, at another version, or not on PATH.

### Hooks

- **The hook wrapper.** Every hook runs through the plugin's `hooks/run`, a bash wrapper
  that compares two version strings and calls `h2t-hook <name>` from the installed CLI.
  When the CLI is missing or at another version, hooks stay quiet and the first
  `SessionStart` of a session says so once, naming the bootstrap. On Windows the hooks need
  Git Bash.
- **post-git-commit-docs-lint now really runs docs-lint** after a commit that touches docs
  in a project made by `scaffold-project`, for up to 8 s (`H2T_LINT_HOOK_TIMEOUT`). In 3.x
  it could not find its script on a user's machine and was effectively a no-op, so expect
  its findings where there were none before.
- **grade-guard and plain-guard are silent on `Stop`.** They print nothing and log every
  verdict to `~/.h2t/logs/grade-guard.jsonl` and `~/.h2t/logs/plain-guard.jsonl`.
- **Failing hooks are logged.** Every failing hook, including one whose JSON input does not
  parse, is logged to `~/.h2t/logs/hooks.jsonl` instead of vanishing. Only a failure during
  `SessionStart` is also reported in the session; on every other event h2t hooks print
  nothing.

### Creative profiles

- Profiles you create with `style-create` now live in `~/.h2t/data/creative/profiles/`
  (`h2t-creative profiles-dir`), outside every install, so an update cannot wipe them.
  `assemble` looks there first, then among the shipped profiles.
- Profiles created under 3.x sit inside the plugin cache and are **not moved**; the cache
  cleanup of a later `sync` deletes old versions. Copy them before that:

  ```bash
  ls ~/.claude/plugins/cache/lichtpfad/h2t-creative/*/profiles/
  mkdir -p "$(h2t-creative profiles-dir)"
  cp -R ~/.claude/plugins/cache/lichtpfad/h2t-creative/<3.x version>/profiles/<your profile> "$(h2t-creative profiles-dir)"/
  ```

  The shipped profiles (`h2t-default`, `h2t-editorial`, `h2t-graphs`, `h2t-mono`,
  `h2t-pfad`, `h2t-terminal`) need no copy.

### One storage root (#548)

- **Everything lives under `~/.h2t`**, one directory per class: `config/`, `secrets/shared/`,
  `secrets/local/`, `records/`, `data/`, `state/`, `logs/`, plus `run/` and `layout.json`.
  The README section "Where Your Data Lives" has the tree and says which classes may be
  synced. Places outside the root — `lake`, `inbox`, `kb` — are declared in
  `config/paths.yaml` (`h2t-ops paths set <place> <path>`); the vault comes from
  `H2T_PATH_VAULT`. Skills ask `h2t-ops paths get <id>` instead of spelling a path, and
  `h2t-ops paths list` shows every place and why it is where it is.
- **Migration: `h2t-setup layout migrate`**, run by `h2t-setup sync` after the CLI is
  installed. It copies the 3.x secrets, sessions, activity, evals, cursors, the registry,
  research and creative profiles into the new layout and checks every copy by hash. The
  old files stay, are read as a fallback through 4.0.x and get a `MOVED-TO.txt`. Where
  sources disagree on a key, the senior value wins — a file already at the new address
  first; for `H2T_EVALS_*` too, ahead of `~/.dor/secrets.env` — and the other is kept as
  `<file>.from-<source>` (`<file>-2.from-<source>` on a repeat); `h2t-ops doctor` lists
  them. `paths.yaml` is written only when there is a place to declare. When the machine
  cannot be named, the migration stops and asks for `--machine <name>`.
- **Rollback: `h2t-setup layout rollback --sync-paused`**, after pausing the sync of
  `records/` and `secrets/shared/`. It removes only the files the migration created and
  nobody changed since, restores what it added to, and lists the rest. If the migration's
  check fails because an old file changed while it ran, roll back and migrate again.
- **Downloads with no path go to the `inbox` place** (or `~/.h2t/data/inbox` while it is not
  set) under a free name, and say where they went. `drive download` without `--dest` no
  longer writes into the current directory.
- **`latest.json` is no longer written.** A session record is
  `records/sessions/<machine>/<project>/<session_id>.md` with frontmatter, and "the last
  session of this project" is a query to `state/index.sqlite`, across every machine.
- **Google:** the access token is no longer written to disk; each command gets one from the
  refresh token in memory. The token is per machine, in `secrets/local/google.token.json`
  (`h2t-ops paths get secret:google.token`): each machine logs in itself, and the file is
  not synced. A token without a `refresh_token` never wins a migration. The file is written
  only at login and when Google issues a new refresh token; through 4.0.x each such write is
  mirrored into this machine's 3.x `tokens.json` while that file exists, for readers such as
  POS, whose `token` and `expiry` there go stale after an hour.
- **`config/user.yaml`** is yours; the package only reads it: `timezone`,
  `notion.tasks_database_id`, `domain_patterns`. The calendar zone is `--tz`, then
  `H2T_CALENDAR_TZ`, then `timezone`, then the system zone (UTC on Windows). `notion search`
  and `find-project-tasks` without a database id use `notion.tasks_database_id`, and exit 2
  when it is not set.
- **A Granola manifest under a `--to` other than `<lake>/granola` is not moved.** The next
  `granola sync` without `--to` starts a new manifest in `<lake>/granola`; pass the old `--to`
  to keep using the old one.

**The 3.x path variables are no longer read.** `h2t-ops doctor` names any still set.

| variable | what to do |
|---|---|
| `H2T_LAKE_ROOT` | nothing: the migration writes its value into `paths.yaml` as `lake`; then remove it |
| `H2T_SECRETS_FILE` | nothing: the migration reads its file once as one more secrets source; then remove it |
| `H2T_EVALS_SPOOL` | nothing: the migration copies that spool into `state/evals-spool.sqlite`; then remove it |
| `H2T_CONFIG_ROOT`, `H2T_SESSION_ROOT`, `H2T_ACTIVITY_SPOOL`, `H2T_EVALS_ROOT` | remove it; to move the whole root, use `H2T_PATH_ROOT` |

Two path variables replace them: `H2T_PATH_ROOT` moves the whole `~/.h2t` except `run/`;
`H2T_PATH_VAULT` (default `~/.dor/vault`) is the vault's address, shared with POS — set it
in POS's environment too if the vault moves. `H2T_KB_ROOT` stays: `llm-kb-engine` reads it.
