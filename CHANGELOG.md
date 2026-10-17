# Changelog

One CHANGELOG for the whole pack from 4.0.0 on. The per-plugin files
(`plugins/*/CHANGELOG.md`) are the history up to 3.x; their `Unreleased` entries ship in
4.0.0.

## 4.0.0

The pack is rebuilt around one package (#541). Nothing here moves your data; see
"Известные ограничения" below.

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
- **An invalid hook event is logged.** A hook whose JSON input does not parse appends its
  traceback to `~/.h2t/logs/hooks.jsonl` instead of vanishing, and the next
  `SessionStart` names the repair.

### Creative profiles

- Profiles you create with `style-create` now live in `~/.h2t/creative/profiles/`
  (`h2t-creative profiles-dir`), outside every install, so an update cannot wipe them.
  `assemble` looks there first, then among the shipped profiles.
- Profiles created under 3.x sit inside the plugin cache and are **not moved**; the cache
  cleanup of a later `sync` deletes old versions. Copy them before that:

  ```bash
  ls ~/.claude/plugins/cache/lichtpfad/h2t-creative/*/profiles/
  mkdir -p ~/.h2t/creative/profiles
  cp -R ~/.claude/plugins/cache/lichtpfad/h2t-creative/<3.x version>/profiles/<your profile> ~/.h2t/creative/profiles/
  ```

  The shipped profiles (`h2t-default`, `h2t-editorial`, `h2t-graphs`, `h2t-mono`,
  `h2t-pfad`, `h2t-terminal`) need no copy.

### Известные ограничения

- 4.0.0 moves code, not data. The storage roots (`~/.h2t`, `~/.dor`, `~/.config`), the
  order in which secrets are looked up and the author's literals in defaults are unchanged
  in 4.0.0; there is no single paths file yet. That is the next subsystem:
  [#548](https://github.com/lichtpfad/h2t-skills/issues/548).
