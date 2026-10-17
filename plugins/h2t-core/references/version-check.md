# Version check

Every h2t skill starts with one command, `h2t-ops version --expect <ver> --json`, where
`<ver>` is the release the skill was shipped with (spec §6.3). It answers two questions at
once: is the installed CLI the release this skill was written against, and does the
harness's PATH reach every one of its commands. A skill that skipped it would fail on its
first real command, with an error that names the symptom instead of the remedy.

## The block every SKILL.md carries

The text between the markers below is copied, byte for byte, into each SKILL.md that runs
an h2t command. `tests/skills/test_skill_commands_exist.py` holds the copies equal to this
one and checks that the command is each skill's first.

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

## Why each outcome reads the way it does

**1 and 2 come from the command itself.** On `ok: false` the envelope carries a `hint`
with the exact next command, at `error.hint`; `error.details.reason` is the machine-readable
case. The skill shows the hint rather than composing its own advice, so the advice changes
with the CLI, not with every copy of this text. It shows it and stops — it does not act on
it: the `path` hint ends in `uv tool update-shell`, which edits the user's shell profile,
and the hint itself says the user runs it (spec §6.3).

**3 is the only outcome the CLI cannot report**, because it did not run. Two very different
machines look the same here: one with no install, and one whose install is complete but
whose harness PATH does not see it — on Windows PATH is read once, when the window opens,
so a fresh install is invisible until the harness restarts. `install.env` tells them apart:
`h2t-setup` writes it last, with `STATE=ready`, only after the install was verified by
running it (spec §6.4). `sync` never edits the shell profile, so `uv tool update-shell` is
offered for the user to decide on, not run on their behalf.

**4 covers an install too old to know the command.** A 3.x CLI answers `version --expect`
with a usage error, or with a version line and no JSON. Any of those means the CLI predates
this skill, and the bootstrap brings the machine to the current release whatever state it
is in (spec §7.2).

The version after `--expect` and the bootstrap command are slots. `scripts/release.py
prepare` rewrites both in every file of the release, by pattern, so the next release
rewrites them again; in a checkout they hold placeholders until a release is cut, and the
check reports `reason: version` there.

## Why a copy in every skill, not a link to this file

A skill in another plugin cannot reach this file. The plugin cache keeps each plugin under
its own version directory (`cache/lichtpfad/h2t-core/<ver>/`), so a relative path from
`h2t-ops` or `h2t-dev` to `h2t-core` names a version that changes with every release.
`${CLAUDE_PLUGIN_ROOT}` is not exported to the bash a skill runs (#456), and it is per
plugin anyway. A plugin `bin/` is on PATH in Claude Code but not in Codex, which installs
skills without plugins (spec §4). And the CLI cannot print the text: outcome 3 is exactly
the case where the CLI is not there. The one form that works in the cache, in a checkout
and in Codex is the text inside the SKILL.md itself — so it is copied, and the test keeps
the copies from drifting.

## Codex

Codex runs no hooks (spec §4), so this check is also the only version check a Codex session
gets: in Claude Code the `SessionStart` hook reports a mismatch once per session, in Codex
nothing does. The outcomes above are the same in both.
