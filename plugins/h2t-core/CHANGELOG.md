# h2t-core Changelog

## 3.2.24 — 2026-08-23

- Hooks written into other projects resolve when they fire. `scaffold-project` used to put
  `~/.claude/plugins/cache/lichtpfad/h2t-core/latest/hooks-handlers/on-stop` into a project's
  `.claude/settings.json` — a path under one machine's home directory, in a file that is
  normally committed. The `latest` junction it named was refreshed only by
  `install-h2t-ops`, never by `/plugin marketplace update`, so it sat at 3.2.18 while the
  cache held 3.2.22. The new `h2t-hook <name>` resolves the handler through the same ladder
  the entry points use and runs it under the interpreter its shebang names. Nothing had been
  wired to the old path yet, so no scaffolded project needs repair.
- `create_latest_link` and the symlink are gone: deleting the artifact alone would have left
  the generator to recreate it.
- `.claude/project-id` is read at last. `init-project` wrote it and promised the next
  session-start would recognise the project; no reader existed, so identity came from the git
  remote plus a central `repo-mapping.yaml` and a clone without that mapping resolved to
  `unknown`. It is now the first rung, found by walking up from the working directory and
  stopping at the repository root. The writer emits `domain/project`; bare-id files still
  resolve through `domains.yaml`.
- The handoff writer no longer dies after the record is written. `log_session_end` writes the
  spool before the markdown mirror, so an unusable `--markdown-dir` raised out of `main()`
  over a session that was already saved. Every mirror failure now returns `degraded` with the
  spool path, and exit codes follow the connector taxonomy: 2 usage, 3 config.
- `scaffold-project`: the dead `$H2T_PYTHON` block is gone (its only use sat inside
  `open(... if False else ...)` under prose saying to skip it), and the skill gates on
  `h2t-hook`, which it now writes into other projects' settings.
- Packaging: the wheel shipped `eval/session.py`, `eval/skill_class.py` and
  `activity/writer.py` twice and claimed the top-level name `lib` in `site-packages`. One
  copy each now, under `h2t_ops/_plugin_payload`, reached through
  `ensure_plugin_lib_on_path`. Hook handlers ship in the payload too, so `h2t-hook` works on
  a host that never installed the plugin.

## 3.2.23 — 2026-08-23

- One gather implementation. `h2t-ops gather` reached a second copy in `lib/cli/main.py` that
  never gained `find_latest_session_index`, so it silently dropped the `### Previous Session`
  block; `h2t-ops gather session-start --briefing-only | grep -c "Previous Session"` returned
  0 where `h2t-gather` returned 1. Both paths now run the plugin script.
- `h2t-gather --cwd` on a path that is not a directory exits 3 instead of printing a complete
  looking briefing for project `unknown`.
- The `gather-on-skill` hook calls `h2t-gather` when it is on PATH, so it resolves through the
  same ladder as everything else rather than reaching for the plugin script directly.
- `handoff` no longer asks for a session name before writing (#391): the question stood
  between a finished summary and the only place it could survive. Identity is derived from
  the working directory through the same `identify_project()` the reader uses.

## 3.2.22 — 2026-08-22

- gather reports a dead GitHub source instead of an empty backlog. `_run_one` collapsed
  every failure — timeout, non-zero exit, missing binary — into `""`, `_parse_json("")`
  turned that into `[]`, and the briefing printed "Нет открытых issues" as a fact about the
  repository. Two consecutive runs disagreed: the first at `gather_ms: 15110` (the 15s cap)
  showed no tasks and no PRs, the second at 1544 ms showed 20 issues and 3 PRs. Both said
  `sources_failed: []`.
- `None` now means "the command did not run"; `""` means "it ran and printed nothing".
  `gather_github` returns `failed`, the names of the calls that did not answer, and the
  session-start script puts `"github"` into `sources_failed`. The hint names the failed
  calls instead of asserting an empty backlog.
- `identify_project` survives that same `None`. `git remote get-url origin` exits non-zero
  outside a repo, and stripping it blindly raised `AttributeError` before the cwd patterns
  or the default could run — caught by codex review as [P1] in both copies.

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
