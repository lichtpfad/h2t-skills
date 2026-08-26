---
title: "Pre-release audit — the tree against a machine that is not the author's"
date: "2026-08-27"
status: "in-progress"
issue: "#431"
runbook: "docs/superpowers/plans/2026-08-27-pre-release-clean-machine-audit-runbook.md"
---

# Pre-release audit

Measurement pass before publication (#419). Nothing here is fixed by this run; every finding
becomes an issue. Written incrementally so it survives a context compaction — a section with
no numbers in it has not been measured yet.

## Phase B — language

Agent-facing text was checked for Cyrillic across `plugins/`, `lib/`, `h2t_ops/`, `scripts/`,
`tools/`, `tests/` and `.claude/`. **45 files, 701 lines.** Not all of it costs the same, so
the classification is the finding rather than the total.

### B1. Skill descriptions — 24 SKILL.md, 17 of them in the frontmatter

The frontmatter `description` is what Claude Code reads to decide whether a skill applies. Of
24 SKILL.md files carrying Cyrillic, **17 carry it inside the frontmatter itself**:

| lines | frontmatter | file |
|---|---|---|
| 88 | yes | `plugins/h2t-ops/skills/daily-brief/SKILL.md` |
| 78 | no | `plugins/h2t-edu/skills/lesson-parser/SKILL.md` |
| 51 | yes | `plugins/h2t-edu/skills/process-transcripts/SKILL.md` |
| 51 | yes | `plugins/h2t-creative/skills/voice-eval/SKILL.md` |
| 35 | yes | `plugins/h2t-core/skills/scaffold-project/SKILL.md` |
| 33 | yes | `plugins/h2t-edu/skills/youtube-transcript/SKILL.md` |
| 20 | yes | `plugins/h2t-core/skills/handoff/SKILL.md` |
| 12 | no | `plugins/h2t-dev/skills/gh-memory/SKILL.md` |
| 10 | no | `plugins/h2t-dev/skills/docs-lint/SKILL.md` |
| 9 | yes | `plugins/h2t-core/skills/session-start/SKILL.md` |

…and 14 more with 1–6 lines each.

The shape is consistently a bilingual trigger list — `Triggers: 'daily brief', 'briefing',
'утренний брифинг', 'что сегодня'`. Whether that helps or hurts dispatch is a question for the
architecture review (phase I), not something this phase can settle by counting.

### B2. Runtime strings the user reads — 18 files

These are not documentation. They are what a person sees when something goes wrong:

```
44  plugins/h2t-ops/skills/drive/scripts/drive_cli.py
44  plugins/h2t-edu/skills/process-transcripts/scripts/process_transcripts.py
21  plugins/h2t-core/lib/gather/briefing.py
21  lib/gather/briefing.py
19  plugins/h2t-dev/skills/docs-lint/scripts/lint.py
16  plugins/h2t-core/skills/init-project/scripts/detect_project.py
14  plugins/h2t-core/hooks-handlers/structure_guard.py
 5  plugins/h2t-core/hooks-handlers/plan_closer.py
```

Sample — `drive_cli.py:88`:

```
Папка '{folder_name}' не найдена. Запустите: drive list
```

A `structure_guard` hook that blocks a commit does it with `BLOCKED: запрещённый паттерн
имени`. For an external user this is an error message in a language they may not read, from a
hook they did not install deliberately.

### B3. Harmless

22 test files (fixture strings and assertion text) and 8 content/config files (creative
profiles, CHANGELOGs, a handoff example). These carry no cost for an external reader.

## Phase K — codex cross-compatibility (partial)

**There is no `AGENTS.md` in this repository.** `codex` is installed on this machine
(`/opt/homebrew/bin/codex`) and reads `AGENTS.md` for project instructions; this tree has
`CLAUDE.md` only. A Codex session in this repo therefore starts with none of the project
rules — not the connector boundary, not the linting rule set, not the verification discipline.

Remaining sub-questions for this phase are unmeasured at time of writing.

## Phase C — hardcode

Scanned by publication zone, because a path in `docs/` that will not ship costs nothing and a
path in `plugins/` costs a stranger their first hour.

| zone | occurrences | note |
|---|---|---|
| **ships** (`plugins/ h2t_ops/ lib/ scripts/ tools/ tests/`) | **183** | the whole problem |
| `.claude/` (undecided) | 9 | all in `rules/documentation.md` |
| `docs/` (not shipping) | 1874 | disappears with the directory |

The 1874 in `docs/` are the reason the curated-snapshot manifest matters more than any
cleanup pass: they are already solved by not publishing them.

### C1. `~/.dor` — 114 occurrences, 46 files, and it is not a comment

`.dor` is the operator's personal vault. An AST pass separating real string literals from
docstrings finds it **live in 27 shipped files**, and `h2t_ops/core/secrets.py:10` makes it
canonical, not a fallback:

```python
DEFAULT_SECRETS = Path.home() / ".dor" / "secrets" / "secrets.env"
LEGACY_SECRETS  = Path.home() / ".dor" / "secrets.env"
```

The docstring is explicit: *"Canonical runtime secrets live at `~/.dor/secrets/secrets.env`."*

**And the tree contradicts itself about where secrets go.** Three answers are shipped at once:

| source | says |
|---|---|
| `h2t_ops/core/secrets.py:10` | `~/.dor/secrets/secrets.env` — what the code actually reads |
| `plugins/h2t-core/skills/setup/SKILL.md:172,181` | `~/.dor/secrets/secrets.env` — agrees |
| `h2t_ops/connectors/meetgeek/client.py:50` | `~/.h2t/config/secrets/meetgeek.md` |
| the SessionStart context banner | `Config: ~/.h2t/config/ (…, secrets/)` |

A new user following the banner puts keys in `~/.h2t/config/secrets/` and the loader never
looks there. For the author both directories already exist, so the contradiction has never
had a chance to show itself.

`.dor` also appears as a default *output* location — `meetgeek_cli.py:949` defaults to
`~/.dor/lake/meetgeek/uploads-staging/`, `process_transcripts.py`, `youtube_transcript_cli.py`
and `convert_docx_to_md.py` write there too. On a machine without that vault these are writes
into a directory the user never made and cannot interpret.

### C2. `C:/dev` — 48 occurrences, 28 files

Not only in error text. Two skills hardcode it as **behaviour**:

```
plugins/h2t-core/skills/scaffold-project/SKILL.md:61
   Ask: "Где создать/дополнить директорию? (по умолчанию: C:/dev/{id})"
plugins/h2t-core/skills/project-audit/SKILL.md:22
   TEMPLATES_DIR="C:/dev/h2t-landings/templates"
```

The first offers a Windows path as the default project location to every user on every
platform — and asks in Russian. The second points at **a different repository entirely**
(`h2t-landings`), which an external user does not have and cannot obtain.

The error-message class is the smaller half: `session-start/SKILL.md:18,22` and
`handoff/SKILL.md:16` tell a failing user to run
`uv tool install --editable C:/dev/h2t-skills`. `CLAUDE.md:94` documents
`uv tool install --editable .` for exactly this case, so the tree already knows the right
answer and does not use it.

### C3. Machine names and other machines' disks

14 occurrences in 8 files name a specific machine; 4 more reference `E:/DROPBOX` (a drive
letter on the author's Windows box), including two live test fixtures in
`plugins/h2t-core/skills/init-project/scripts/test_detect.py:32,90`.

## Phase I — architecture review (`claude-code-guide`)

Run as an agent, at the operator's explicit request. Its findings, and what verification
changed:

| finding | agent's severity | verified |
|---|---|---|
| hardcoded `C:/dev` in skills | Critical, 3 files | **understated** — 28 files, and two of them hardcode behaviour, not just error text |
| `design/SKILL.md` 1361 lines with no `references/` | Medium | confirmed; `project-audit` (472) and `setup` (262) are the next two |
| `inject-h2t-context` three-way output branch | High | confirmed present; see below |
| `Triggers:` phrases inside `description` frontmatter | Low | confirmed, ~18 skills |
| plugin.json / marketplace.json compliance | none | confirmed clean — required fields present, sources relative |
| hook events, matchers, output channels | correct | confirmed |
| `plugins/*/agents/` | none found | confirmed — 0 directories, since #430 removed the only one |
| dependencies | stdlib only in hooks | confirmed |

The agent **missed `~/.dor` entirely**, which is the larger of the two hardcode classes. Worth
recording as a property of the method rather than of the agent: it was asked about architecture
and conformance to documented Claude Code behaviour, and `.dor` violates neither — it is a
perfectly well-formed path to somewhere only one person has.

On `inject-h2t-context`, the agent's concern is the fallback branch emitting a top-level
`{"additionalContext": …}` rather than the documented
`{"hookSpecificOutput": {"hookEventName": …, "additionalContext": …}}`. That branch fires when
`CLAUDE_PLUGIN_ROOT` is unset — which is precisely a non-Claude-Code harness, so it connects
directly to phase K.

## Phase D — a clean machine (macOS half)

Method: a fresh `HOME` in `/tmp`, with a control both ways — `~/.h2t` must not resolve under
the synthetic HOME **and** must resolve under the real one. Without the second half, a
"nothing found" result cannot be told apart from a probe that never ran.

```
synthetic:  ls: /tmp/cleanhome.SuecEp/.h2t: No such file or directory
real:       /Users/stanislav_glazov/.h2t
```

### D1. All nine entry points start; two misbehave

```
rc=0  h2t-ops --help / doctor / connectors
rc=0  h2t-handoff, h2t-activity-log, h2t-project-register,
      h2t-project-audit-scan, h2t-project-audit-report, h2t-scaffold-project
rc=5  h2t-hook --help    Plugin entrypoint script not found: hooks-handlers/--help
```

`h2t-hook` treats `--help` as a handler name, so the one command whose behaviour is least
guessable is also the one with no help. **Loud, but useless** — the message names an internal
path rather than saying the command takes a handler name.

`h2t-activity-log --help` prints `usage: writer.py`. The program name leaks the internal
script, so a user who copies the usage line types a command that does not exist. **Misleading.**

### D2. `h2t-ops doctor` exits 0 on a machine it has just diagnosed as unconfigured

```
secrets: NOTION_API_TOKEN=MISSING
secrets: gmail credentials=MISSING
rc=0
```

It says MISSING in prose and 0 in the exit code, so nothing can gate on it. It also never
mentions that `~/.h2t` and `~/.dor` are absent — the two directories everything else assumes.
**Quiet** by the classification that matters: a caller branching on the exit code is told the
machine is fine.

### D3. `h2t-gather` degrades well, then gives a broken instruction

The briefing renders on a machine with no config at all — project id falls back to `unknown`,
milestones and issues still resolve through `gh`. That part is genuinely graceful.

Then it ends with:

```
### Hints
- Repo не зарегистрирован. Запусти `/h2t:init-project` для регистрации.
```

`/h2t:init-project` does not exist. The `h2t` plugin was never in `marketplace.json` and was
deleted in #430; the skill lives at `h2t-core:init-project`. This is the **misleading** class:
the user is told exactly what to do, does it, and nothing happens.

**Nine such references ship**, all naming the dead namespace:

```
plugins/h2t-edu/skills/process-transcripts/SKILL.md:27        → /h2t:setup
plugins/h2t-edu/skills/convert-meeting-transcript/SKILL.md:23 → /h2t:setup
plugins/h2t-edu/skills/youtube-transcript/SKILL.md:21,98,99   → /h2t:setup
plugins/h2t-core/lib/gather/briefing.py:289                   → /h2t:init-project
lib/gather/briefing.py:289                                    → /h2t:init-project
plugins/h2t-core/skills/init-project/scripts/apply_registration.py:158 → /h2t:scaffold-project
lib/gather/test_briefing.py:139                               → asserts the broken string
```

The last line is the one to read twice. A test pins `/h2t:init-project` as expected output, so
the suite is green **because** the instruction is wrong. Fixing the hint fails a test; that is
the shape of a defect that survives a rewrite.

Note these were already broken before #430: `h2t` was never shipped by the marketplace, so
`/h2t:setup` has never resolved for anyone who installed the pack normally. The deletion did
not create this — it removed the last excuse for not noticing.
