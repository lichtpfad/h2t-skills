# h2t-core Changelog

## 3.2.21 — 2026-08-22

- session-start finds the handoff the previous session wrote. The writer keys the session
  directory by `project.id`, the reader keyed it by the tail of the github remote — and for
  20 of the 38 entries in `repo-mapping.yaml` those differ, so every handoff landed in a
  directory session-start never looked in. Silently: `latest.json` still existed under the
  repo name, so the briefing was not empty, merely days old.
- `project.id` is the primary key, not an alternative. Several repositories map onto one
  project on purpose (DocGraph and SpecDesigner onto docgraph); only `project.id` keeps
  their history together. `find_session_files` and `find_latest_session_index` now take
  several identity keys and read the repo name too, so handoffs written before a project
  was mapped stay visible and no migration is needed.
- Round-trip test: `h2t-handoff write --project agent-skills` must be found by a reader
  that knows the repo as `h2t-skills`. Neither side's own tests could catch this.

## 3.2.20 — 2026-08-22

- The slash form of a session skill gathers again. `/h2t-core:session-start` is expanded
  into the prompt by the harness and never calls the Skill tool, so the `PreToolUse: Skill`
  matcher could not fire — the accurate user was the only one whose briefing silently went
  missing. A `UserPromptSubmit` hook now covers that path and hands over to the same
  `gather-on-skill`, whose per-directory lock keeps a double entry from gathering twice.
  Plain-text requests ("сделай handoff") already called the Skill tool and are unchanged.
- The match is anchored to a leading slash command: `UserPromptSubmit` also fires for
  harness messages such as `<task-notification>`, whose file paths contain these words.
- Briefings reach the model on the slash path via `hookSpecificOutput.additionalContext`;
  `systemMessage` is the user-visible TUI channel and stays in use for the Skill path.
- The resolver-failure exit honours the same channel. On a machine with no PyYAML
  interpreter the hook returns before `emit()` exists, and its hand-written envelope
  still said `systemMessage` — so a slash user got no error the model could act on.

## 3.2.19 — 2026-08-22

- session-start/handoff context injection works again. The hook ran `-m lib.cli.main`
  and cd'd into the plugin root, whose vendored `lib/` has no `cli` package and shadows
  an installed one — so it returned GATHER_ERROR on every interpreter, in every layout,
  since 2026-04-25. It now runs the plugin's own `gather.py --briefing-only`.
- init-project receives the `INIT_DATA` its SKILL.md documents; nothing produced it before.
- The hook keeps stdout, stderr and exit code apart, so a crashed script can no longer
  pass a half-written payload off as a briefing, and its dedup lock is per directory and
  records a success rather than an attempt.
- `detect_project.py` and `apply_registration.py` both honour `--config-root` and
  `H2T_CONFIG_ROOT`; registration takes `--description` and fills a blank field only.
- `lib/gather` is identical to the root copy again, guarded by a parity test.

## 3.2.13 — 2026-07-11

- eval fallback: `H2T_EVALS_MODE` (auto/off/local/push, default auto); off-by-default
  for adopters without h2t-evals; `h2t-ops evals status`. BREAKING: default is no longer
  implicit local-write — set `H2T_EVALS_MODE=local` to keep local-only telemetry.
