# h2t-core Changelog

## Unreleased

- feat(hooks): a SessionEnd hook reaps the Codex `app-server-broker` this session
  leaked (Windows only). Codex orphans the broker on Windows; measured on AUTOMATA
  2026-09-04, nine had accumulated over eight days, one per session, and the oldest
  pinned a removed git worktree open (`Device or resource busy`) until killed. The
  broker is the only Codex process that records a `--cwd`, so it is both the leak
  and the lock. The hook kills the broker whose `--cwd` is this session's own or no
  longer exists on disk, and leaves a live sibling in another worktree alone — under
  the one-worktree-per-session rule that cwd is unique, so it is exactly this chat's
  Codex. Ancestry cannot scope it (the broker is detached — its parent has exited),
  and only the per-session `cxc-<token>`, which lives in the Codex plugin, could tell
  two chats sharing one tree apart. No-op off Windows, where Codex does not orphan
  this way (#477)

- fix(handoff): the writer's response counted the bounded index, not the record. Eleven
  artifacts in produced `"artifacts": 10` with `"status": "ok"` — and no field told a
  capped index apart from a caller that simply passed ten. Nothing was ever lost: the
  markdown and the activity spool carry every artifact, and `latest.json` already flagged
  itself `truncated`. `artifacts` now counts the distinct artifacts recorded and a new
  `index_truncated` says whether `latest.json` holds all of them; the degraded path
  returns the same shape (#438)

- fix(handlers): three messages told the reader to use `~/.h2t/venv` — the gather failure
  offered "recreate" it as the remedy, `apply_registration` named it as where to pip-install
  ruamel.yaml, and the secrets README template used it to build a rotation test command.
  The guard that caught the injected index read one file; it now reads every shipped file,
  with the four resolver probes allowlisted by name and reason (#443)

- fix(session-context): the index injected into every session no longer names
  `~/.h2t/venv`. That contract was deleted in #449 and nothing in the pack ever created the
  directory, so on any machine but the author's the hook was handing each agent a path to a
  non-existent interpreter. It now names the CLI commands and says the resolver picks the
  interpreter. `h2t-core:setup` was added to the index — the first skill an onboarding user
  needs was the one it did not mention (#443)

- feat(structure-guard): a plan or spec written by hand is blocked when it names no
  issue, or says `none` without a reason. The generator and CI cover two of the three
  entry paths a document can take; this is the third, and without it the other two are a
  habit rather than an invariant (#423)

- fix(scaffold-project): a broken h2t-dev no longer reads as an absent one. `run_docs_init`
  returned `skip` both when the plugin was missing and when the plugin was there without its
  script — so a broken delivery produced a project with no `docs/` and said nothing, which is
  the failure the call exists to prevent. The second case is now an error naming the path and
  what to do. Also follows docs-init to its new home under `scripts/` (#458)

- chore(snap): `compatibility` says what the skill needs before it is run — the h2t-snap
  binary on PATH, prebuilt and free for both platforms, plus Screen Recording and
  Accessibility on macOS, where exit code 5 is a permission refusal and not a missing
  window. Previously the field read "Claude Code", which is true of every skill and
  therefore tells an agent nothing (#464)

- fix(inject-h2t-context): the injected skill index no longer advertises
  `h2t-dev:docs-init`, which has no `SKILL.md` in the tree nor in any of the eleven cached
  versions back to 1.0.20. Not a lost file: `bc335d8` removed `SKILL.md` from four skills
  deliberately ("demote to CLI") and the index was never updated, so every session since
  carried a name the harness cannot reach. Eleven of the twelve names checked out; that one
  did not. `tests/core/test_injected_index_matches_tree.py` is the gate, and it was seen red
  against the restored defect before being trusted (#458)

- chore(agent-profile, autonomous-run): both now declare `compatibility` and `metadata` —
  the only two of the pack's skills that carried neither. The strings say what the skill
  actually needs rather than repeating "Claude Code": agent-profile operates on the
  h2t-skills checkout and refuses to write without it, autonomous-run requires the codex
  CLI because both of its gates call it and both cost money (#464)

- fix(plan-closer): a merged PR closes a plan only if it changed something other than
  documentation. The hook read "the PR listed this document" as "this document is
  finished" — two different claims. Measured on h2t-business 2026-08-27: PRs #58, #59
  and #60, three documentation edits in a row, each stamping `done` on a 2300-line
  decision map with four open questions in one section, and each leaving the working
  tree dirty. The discriminator was on the same `gh pr view` output all along: a PR
  that changed no code implemented nothing. A document with no finished state now says
  so itself with `lifecycle: living` and is never stamped — previously `approved`
  granted permanent immunity while `draft` never could, so the documents still in work
  were exactly the ones being closed. The TUI line states what the hook wrote rather
  than asserting the PR "закрыл" anything (#455)

- fix(hooks): the interpreter chain in `resolve-h2t-python.sh` ends at `uv` instead of
  falling through to a system Python without the package the probe needs. uv is last, so
  a machine that already resolves locally pays nothing — it costs 58 ms warm and an
  unbounded download cold, on a hook that fires every prompt. Requirements travel with
  the probe (`resolve_h2t_python "import yaml" pyyaml`), because uv has no environment
  to inherit. The gather error no longer prescribes `~/.h2t/venv`, a directory the
  installer never creates (#449)

- fix(setup): a preflight names `uv` as the missing prerequisite and exits 3, rather
  than letting the first documented command of a fresh machine die on `command not
  found`. Every invocation in the skill runs through
  `uv run --no-project --python 3.11 python` (#449)

- fix(hooks): the gather envelope can no longer emit a lone surrogate. `sys.stdin.read()`
  re-decodes the briefing through the interpreter's ANSI code page — cp1252 with
  `errors="surrogateescape"` on a pipe, whatever `chcp` says — so byte `0x81` (Cyrillic
  «с») became `U+DC81` and `json.dumps` printed the literal `\udc81`. The API then
  rejected every subsequent request of that session, and the hook reported `rc=0`
  throughout. Measured in vivo on the Windows machine: 17× `\udc81` and 3× `\udc8f` out
  of one real `session-start` briefing — the trigger is the two most common Russian
  letters, not an exotic byte. The envelope now reads `sys.stdin.buffer` and decodes with
  `errors="replace"`, which has no representation for a lone surrogate (#453)

- fix(secrets): read the secrets file from the location every other message names, and
  merge the whole chain instead of the first file found. `H2T_SECRETS_FILE` had also lost
  its `expanduser()`, so a `~`-prefixed path resolved to a literal directory named `~`.
  Both regressions were found by `codex review` inside this same batch of commits and
  confirmed by behaviour, not by reading (#432, #448)

- fix(session-start): the briefing's hints name skills that exist. `/h2t:init-project`
  was hardcoded in `briefing.py` and pinned green by a test — the `h2t` namespace is not
  shipped, so the one actionable line a new machine sees pointed at nothing (#433)

- fix(scaffold-project, setup): derive where sibling repositories live instead of naming
  `C:/dev`. The path was written into other people's repositories verbatim (#434)

- fix(session-start): the briefing warns when a versioned `pre-commit` exists and git
  is not running it. `scripts/hooks/pre-commit` has blocked `marketplace.json` drift
  since #74 and was off on this machine the whole time — `core.hooksPath` unset,
  `.git/hooks` holding only samples. A hook committed but never wired into the clone
  blocks nothing and prints nothing, so nothing distinguishes it from no hook at all.
  Two causes fixed alongside: `install.sh` now sets `core.hooksPath` instead of
  symlinking, and `pre-commit` was committed mode 100644 — non-executable on a fresh
  clone, skipped even with `hooksPath` set. The per-clone step cannot be committed
  away, only made noticeable; a legacy symlink into `.git/hooks` still counts as
  active, so existing clones get no false hint

- feat(hooks): `plan-closer` — a merged PR stamps `status: "done"` and `pr: N` on
  every plan and spec it carried. The repo's first PostToolUse hook. Retrospective
  inference had already been measured and rejected — a plan slug appears in 7 of 60
  merged PR bodies, and commit counts cannot separate "done and never updated" from
  "abandoned" — but at the moment of the merge nothing is inferred: `gh pr view`
  lists the PR's own files. The link was never hard to compute, it was never written
  down while it was still free. Every uncertain case is a no-op: an unmerged PR, a
  file the PR deleted, a document with no frontmatter, one already closed, and
  `gh pr merge` with no explicit number (resolving that after the fact would stamp
  the wrong plan). Always exits 0 — bookkeeping must never look like a failed merge

- feat(session-start): the briefing carries a docs-debt line — `141 из 144
  plan/spec/adr не закрыты · 111 старше 60 дней`. docs-lint measures form and
  never lifecycle, so nothing displayed that number anywhere and it took six
  months to notice. Pure filesystem read, no git/gh, silent when nothing is open
- feat(structure-guard): deny-by-default one level below `docs/`. A NEW
  first-level section and a NEW loose file in the `docs/` root are blocked; a
  directory that already exists is allowed by existing, so no legacy section has
  to be enumerated. The repo root has had an allowlist from the start and holds
  14 deliberate directories; `docs/` had none and grew twelve nobody planned
  (wireframes, library, protocols, visual-regression, agent-instructions,
  architecture, research, and a `docs/plans/` beside `docs/superpowers/plans/`).
  Opt-in: without `allowed_doc_dirs` in structure.yaml the check is off.
  A section is grandfathered by holding a file, not by existing: `mkdir
  docs/kb` would otherwise authorise the very write that follows it, and
  `mkdir -p` before writing is a reflex rather than a decision
- feat(scaffold-project): the generated structure.yaml ships `allowed_doc_dirs`,
  so a new project has the rule on day one rather than after the mess
- fix(structure-guard): block, not warn, on an unlisted root directory and on a
  plan/spec/adr written without frontmatter. A warning in PreToolUse exits 0, so
  the write landed and the message was advice — the same layer as a rules file
- fix(structure-guard): `main()` honours the frontmatter verdict; it used to
  discard the code and keep only the message
- chore(structure.yaml): allowlist had drifted six entries behind the repo
  (.github, evals, tools, hooks, hooks-handlers, .claude-plugin); a test now
  keeps it in sync with `git ls-files`

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
