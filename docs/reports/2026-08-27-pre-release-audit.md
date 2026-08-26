---
title: "Pre-release audit — the tree against a machine that is not the author's"
date: "2026-08-27"
status: "complete"
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

## Phase G — duplicate and stray functionality

35 skills across 6 plugins. No two do the same job, but three things are worth acting on.

### G1. A deprecated skill ships

`plugins/h2t-dev/skills/gh-memory/SKILL.md` carries `status: deprecated` in its own
frontmatter and describes itself as a *"Deprecated compatibility shim for old
GitHub-Issues-as-memory workflows"*. It is in the marketplace, so its description is loaded
into the skill list of every session, where it spends attention telling the model to prefer
two other skills. Publishing a pack whose inventory includes a tombstone is a choice; making
it deliberately is the point.

### G2. A skill that needs a local LLM server, silently

`plugins/h2t-edu/skills/process-transcripts/scripts/process_transcripts.py:74-75`

```python
OLLAMA_URL   = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3.2:latest"
```

Neither is configurable and neither is mentioned in the skill's dependency notes. A user
without Ollama running, or with a different model pulled, gets a connection error from a skill
whose description says only *"LLM-enrichment of MeetGeek meeting transcripts"*. It does **not**
violate the connector-ownership rule — it parses local Markdown and never calls the MeetGeek
API — but it is the clearest case in the tree of an undeclared external dependency.

### G3. Boundaries that hold

`init-project` (register an existing repo) against `scaffold-project` (create a new one),
`deck` against `landing` (same assembler, different output), `style-create` against
`style-validate`, `research` against `kb`. Each pair has a stated boundary and the code
respects it. Recorded because "no duplicates found" is only meaningful if the near-misses are
named.

## Phase H — connectors against the provider APIs

Surface as shipped:

```
calendar   calendars list search get create update rsvp move delete create-calendar instances freebusy
gmail      list read threads thread attachment search send draft reply forward label-* trash untrash delete
drive      list search folders create-folder rename copy move get-file trash delete docs docs-tab
           sheets download export upload upload-folder share
notion     get blocks search get-database search-workspace graph find-* create update comments sync
           create-db-item update-db-item create-database patch-db-schema views archive append-blocks
telegram   auth dialogs folders messages send saved-messages mentions bootstrap search send-file
           download-media forward-message delete-message
meetgeek   auth-check teams list get transcript summary highlights insights download-url submit-url
granola    list transcript auth-check get summary folders webhooks sync
research   preflight providers route search crawl fetch visual-ocr similar answer research agent …
```

This is a wide surface and most of it is well covered. Two gaps are worth naming, and they
share a shape.

### H1. Neither Google connector can answer "who can see this?"

`calendar` has **zero** references to `acl` anywhere in `h2t_ops/connectors/calendar/`. The
Google Calendar API exposes `acl.list` / `acl.get`; the connector exposes none of it. There is
no way to ask whether a calendar is public.

`drive share --get-link` does call `permissions().list(fields="permissions(type,role)")` at
`h2t_ops/connectors/drive/client.py:1466` — and then discards everything except one boolean:

```python
has_anyone = any(p.get("type") == "anyone" for p in permissions)
```

So it can say *"not link-shared"* and cannot say *who does* have access, or with what role. The
data is fetched and thrown away.

**This gap was hit by this very audit.** Checking whether the Google objects named in
`docs/reports/2026-05-25-*` are publicly exposed is a precondition for publishing the
repository. Drive answered — five objects, none link-shared. Calendar could not be asked at
all, and that question is still open, on the operator's side, in a settings page.

A connector suite built for *doing* things has no surface for *auditing* them. That is a
coherent design until the day the audit is the task.

### H2. Deliberate omissions, recorded as such

`gmail` has no settings/filters/watch surface; `meetgeek` has no delete; `granola` has no
write path. None of these has ever been needed by a workflow in this repo, and adding them
speculatively would widen the auth scopes a user must grant. Listed so a later reader does not
mistake a decision for an oversight.

## Phase K — codex cross-compatibility

`codex` is installed here (`/opt/homebrew/bin/codex`) and there is a global
`~/.codex/AGENTS.md`, so the operator already works across both harnesses.

### K1. The repository has no `AGENTS.md`

Codex reads `AGENTS.md` for project instructions. This tree ships `CLAUDE.md` (109 lines) and
`.claude/rules/*.md` (10 files, 388 lines) and nothing a Codex session will look at. Every rule
this repository has learned the hard way — the connector boundary, the pinned ruff set, the
verification discipline, the gate invariant — is invisible to half the toolchain the operator
actually uses.

### K2. What is portable and what is not

Portable as-is: the nine CLI entry points, `h2t_ops/`, `lib/`, every `scripts/*.py` under a
skill. They are plain Python with argparse and no harness dependency.

Not portable: the skills themselves (`SKILL.md` is a Claude Code construct), the hooks
(`hooks/hooks.json` + `hooks-handlers/`, driven by Claude Code events), and `plugin.json` /
`marketplace.json`.

That split is not a defect — it is the actual product boundary, and it is worth stating in the
README, because a Codex user can have the connectors and cannot have the skills.

### K3. The hook fallback branch is the codex-shaped hole

`plugins/h2t-core/hooks-handlers/inject-h2t-context` branches three ways on
`CURSOR_PLUGIN_ROOT` / `CLAUDE_PLUGIN_ROOT`, and its `else` branch emits a top-level
`{"additionalContext": …}` that no documented harness consumes. That branch exists precisely
for "some other harness", which today means Codex — and what it emits there is not a contract
anyone honours. A silent hook is a failure, not a steady state (`.claude/rules/hooks.md`).

## Phase E — cross-test: does every script run?

75 Python files under `plugins/`, of which **29 have an entry point**. Each was invoked with
`--help` under the synthetic HOME.

```
22  print a usage line               ok
 3  exit 0 with empty output         the hook handlers — they read stdin, not argv
 1  exit 4 with a hint               exa_search.py
 3  raise a traceback                below
```

### E1. Three scripts treat `--help` as a filename

```
plugins/h2t-core/skills/autonomous-run/scripts/runbook_state.py
plugins/h2t-core/skills/autonomous-run/scripts/validate_runbook.py
   FileNotFoundError: [Errno 2] No such file or directory: '--help'
```

Plus the `h2t-hook --help` case from phase D — the same defect at the entry-point level. Four
places take `sys.argv[1]` as a path without checking it. The cost is small and the shape is
worth naming: the failure blames the *file* for not existing rather than the *invocation* for
being wrong, so the reader looks in the wrong place.

### E2. A missing dependency crashes raw

```
plugins/h2t-edu/skills/convert-meeting-transcript/scripts/convert_docx_to_md.py
   ModuleNotFoundError: No module named 'docx'
```

`python-docx` is declared nowhere. Note the contrast with #429: `apply_registration.py` at
least prints a JSON error object before dying; this one just raises. The tree has **two**
different behaviours for the same situation and neither is the right one — one kills the
importer, the other kills the reader's patience.

### E3. The one that gets it right, and its rough edge

```
plugins/h2t-ops/skills/research/scripts/exa_search.py
   rc=4  EXA_ERROR:ENV h2t_secrets module not found. Tried: []. Set H2T_P…
```

Exit 4 is the auth code from the CLAUDE.md contract, the message names the cause and the fix.
This is the standard the other 28 should be measured against. The rough edge: `Tried: []` — on
a machine with no config the list of attempted paths is *empty*, so the diagnostic that exists
to show where it looked shows nothing exactly when a new user needs it most.

### E4. Hook handlers exit 0 on a malformed invocation

`plan_closer.py`, `post_git_commit_docs_lint.py` and `structure_guard.py` all return 0 with no
output when handed `--help`. For a hook that is defensible — the harness always feeds them
stdin. It is recorded because `.claude/rules/hooks.md` says a silent hook is a failure, not a
steady state, and these three are silent by construction when invoked any other way.

## Phase F — are the instructions legible to an agent with no context?

Judged per SKILL.md against one question: can an agent that has never seen this repository
follow it? Four classes of blocker, all already quantified above, are what an outsider hits:

| class | count | effect on a first run |
|---|---|---|
| points at `/h2t:*`, a plugin that is not shipped | 9 refs | instruction cannot be followed |
| assumes `C:/dev/…` | 28 files | wrong path, sometimes another repo entirely |
| assumes `~/.dor/…` | 27 files (live) | writes and reads a vault the user does not have |
| undeclared runtime dependency | Ollama, `python-docx` | failure with no stated cause |

Two further observations that are about legibility rather than correctness:

**`$H2T_PYTHON` is used without ever being explained.** Three `h2t-edu` skills gate on it —
`[ -z "$H2T_PYTHON" ] && echo "ERROR: h2t venv not found. Run /h2t:setup"` — and the remedy they
name does not exist. A reader is left with a variable, no definition, and a dead command.

**The largest skills carry their references inline.** `design` (1361 lines), `project-audit`
(472), `setup` (262) have no `references/` directory, so an agent invoking them pays for the
entire body to answer any question about them. The pattern the repo already uses elsewhere —
`autonomous-run/references/gates.md`, `docs-lint/references/`, `research/references/` — is the
fix, and it is a local one.

## Phase J — the rest of the pre-publication list

### J1. Nothing that makes a repository public is present

```
LICENSE              absent   → GitHub renders "all rights reserved"; nobody may legally reuse it
CONTRIBUTING.md      absent
SECURITY.md          absent   → no channel to report a vulnerability privately
CODE_OF_CONDUCT.md   absent
README.md            present, 127 lines, written for the author
```

The LICENSE is the one that changes what the repository *is*. Without it the pack is readable
and not usable, which defeats the purpose of publishing it.

### J2. `.gitignore` does not cover credentials

Checked with `git check-ignore`, not by matching strings — the authoritative answer:

```
x/__pycache__/y.pyc   ignored
.env                  NOT ignored
secrets.env           NOT ignored
foo.pem               NOT ignored
bar.key               NOT ignored
credentials.json      NOT ignored
token.json            NOT ignored
```

44 lines of `.gitignore` covering build artifacts, editor state and lint output — and no
credential pattern in any of them. No such file is in the tree today, so this is not a leak;
it is the absence of the guard that would stop the next one. The repository is about to acquire
contributors who do not know where secrets are supposed to live — and phase C shows the tree
gives three different answers to that question.

### J3. The working tree still carries the tokens

`gitleaks --no-git` over the current tree: **2 findings, both in
`docs/archive/plans/2026-04-07-skill-graph-foundation.md`.** Unchanged since the security review
of 2026-08-26. Nothing new has appeared, and nothing has been cleaned.

Under the curated-snapshot manifest this file is not published, which resolves it without any
history surgery — but only if the manifest is actually applied. Right now the exposure is
exactly where the review left it.

### J4. Packaging

`pyproject.toml` declares `requires-python = ">=3.11"`, `name = "h2t-ops"`, `version = "0.2.1"`.
The version has not moved while the plugins have (h2t-ops the *plugin* is at 1.6.8 — see the
name-collision note in `CLAUDE.md`), which is the drift #363 introduced `build_id()` to make
visible. Nothing to fix for publication; recorded because a reader of the public repo will see
`0.2.1` and draw conclusions.

## State of the two machines

### This Mac

```
repo        main @ 87c3148, clean; audit branch audit/pre-release-clean-machine
CI          green on both platforms; the windows-latest leg now gates
entry pts   9/9 installed, editable from this checkout
config      ~/.h2t present, ~/.dor present — which is why the phase C defects were invisible here
merged tonight   #427 (windows leg + 6 fixes), #430 (plugins/h2t deleted), 311975f (CLAUDE.md note)
open issues from tonight   #428 (14 emitters), #429 (4 import-time exits), #431 (this audit)
```

### AUTOMATA (Windows)

State as of its last report, 22:39:

```
repo        was at 1c6d7ee; has NOT yet pulled 87c3148 (the plugins/h2t deletion)
entry pts   9/9 after `uv tool install --editable` — was 4/9
git hook    core.hooksPath = scripts/hooks; drift guard verified by positive control
test venv   still without pip / ruamel / drawpyo — the divergence-from-CI baseline is intact
tree        clean
```

**Its half of phase D is not done.** The clean-HOME measurement on Windows was sent at 23:12
and is unanswered. The operator reports that murmur does not actually wake the agent — the
message was picked up only after a manual nudge — so this is `BLOCKED-DEFERRED (needs an
operator nudge)`, not a failure of the task. When it lands it should answer one question this
audit could not: whether the failures classified as *quiet* on macOS are quiet on Windows too,
where the console codepage and path separators change what a failure looks like.

Note for the morning: after AUTOMATA pulls `87c3148`, empty directories may remain under
`plugins/h2t/` from `__pycache__`, exactly as they did here. That is expected, not a new defect.

## Morning plan

Ordered by what blocks what, not by severity. Nothing below was done tonight — the run was
read-only by instruction.

### Before the repository becomes public

| # | what | who | why it is first |
|---|---|---|---|
| 1 | **Pick a licence and add `LICENSE`** | operator | without it the pack is readable and not usable; five minutes, but it is a decision only you can make |
| 2 | **Decide the manifest** (ship `plugins/ h2t_ops/ lib/ tests/ scripts/ .github/ docs/adr/`; drop `docs/superpowers docs/archive docs/reports TODOS.md`) | operator | it is the cheapest fix in the whole audit: both known leak sites are in directories the manifest excludes, so no history surgery is needed |
| 3 | **Check whether the calendar `omue9d…slg` is public** — Google Calendar settings → "Make available to public" | operator | the one exposure this audit could not measure; `h2t-ops calendar` has no ACL surface (H1) |
| 4 | **Re-provision the VPS with new tokens, not from a backup** | operator | free rotation; makes the leaked pair inert and removes the plan file from any history decision |

### Before strangers arrive (they can clone within the hour)

| # | what | effort | finding |
|---|---|---|---|
| 5 | Settle **where secrets live** — one answer, in code and in every message | ~1h | C1: `secrets.py` says `~/.dor/secrets/`, the context banner says `~/.h2t/config/secrets/`, MeetGeek says a third thing |
| 6 | Remove the **9 `/h2t:*` references** — and the test at `lib/gather/test_briefing.py:139` that pins the broken string | ~30m | D3 |
| 7 | Replace **`C:/dev` hardcode** in `scaffold-project` (default project dir), `project-audit` (points at another repo), `session-start`, `handoff`, `setup` | ~1h | C2 |
| 8 | Add credential patterns to **`.gitignore`** | 5m | J2 |
| 9 | Declare the **undeclared dependencies** — Ollama for `process-transcripts`, `python-docx` for `convert-meeting-transcript` | ~30m | G2, E2 |

### After, in priority order

10. **English-only skills** — 24 SKILL.md, 17 of them with Cyrillic in the dispatch
    `description`; plus 18 files printing Russian to the user. Target state per the operator:
    skills in English, response language from the user's settings.
11. **#429** — 4 remaining import-time `sys.exit` sites (was 10 before `plugins/h2t` went).
12. **#428** — 14 remaining unguarded JSON emitters; confirmed live on Windows (cp1252).
13. **Split `design/SKILL.md`** (1361 lines) into `references/`; then `project-audit` (472)
    and `setup` (262).
14. **`AGENTS.md`** — Codex currently reads nothing in this repo (K1).
15. **Retire or keep `gh-memory`** — it ships with `status: deprecated` in its own frontmatter.
16. **`--help` as a filename** — 4 places (`h2t-hook`, `runbook_state.py`,
    `validate_runbook.py`, plus the entry point).
17. **`h2t-ops doctor` exit code** — it prints MISSING and exits 0, so nothing can gate on it.

### Waiting on AUTOMATA

The Windows half of phase D. Needs an operator nudge to be picked up. Its value is specifically
in the *quiet* column: a failure that is loud on macOS can be silent on Windows, and the whole
day has been examples of exactly that.

## What this run did and did not change

Changed: this report, the runbook, and three commits of documentation. Merged, under prior
authorization: PR #430. Nothing else.

Not changed: every finding above. They are findings, not fixes, by instruction — "важно ничего
не поломать". The suite is green, `main` is green on both platforms, and both machines are in a
known state.

## Manifest decision, taken during the run

**Operator, 2026-08-27:** of `h2t-edu`, only `youtube-transcript` ships. `process-transcripts`,
`convert-meeting-transcript` and `lesson-parser` are superseded and move to POS.

That decision retires several findings above outright rather than scheduling them. Recomputed:

| finding | before | after the cut |
|---|---|---|
| `/h2t:*` dead references | 9 | **7** (3 of them in `youtube-transcript`) |
| Cyrillic lines in agent-facing text | 701 | **495** — 206 leave with the three skills |
| Ollama at a hardcoded `localhost:11434` (G2) | open | **gone** — only in `process-transcripts` |
| raw `ModuleNotFoundError: docx` (E2) | open | **gone** — only in `convert-meeting-transcript` |
| files writing into `~/.dor` under `h2t-edu` | 4 | **1** (`youtube_transcript_cli.py`) |

Both undeclared-dependency findings disappear with the cut, which leaves that class empty in
the shipped tree.

`lesson-parser` also carried the only real question in `h2t-edu` that was not technical — it
encodes a method for turning tutorial transcripts into topology, and whether to hand that to
strangers was a business call rather than an audit finding. The cut settles it.

What `youtube-transcript` still brings into the manifest, and what therefore still needs
fixing before publication:

```
plugins/h2t-edu/skills/youtube-transcript/SKILL.md:21,98,99   → /h2t:setup   (dead namespace)
plugins/h2t-edu/skills/youtube-transcript/scripts/…:18,22     → ~/.dor       (personal vault)
33 lines of Cyrillic
```

## Why `.dor` is everywhere — measured, not guessed

Asked during the run: how many config directories are synced. The Syncthing config
(`~/Library/Application Support/Syncthing/config.xml`) has exactly **one folder**:

```
DOR Registry    /Users/stanislav_glazov/.dor
   type=sendreceive   devices=MacBook-Pro-3.local, AUTOMATA
```

`~/.h2t` is **not** synced.

This reframes finding C1. `.dor` is not a personal path that leaked into the code by accident —
it is the only directory guaranteed identical on both machines, which is exactly why the
secrets loader treats it as canonical. A key written on the Mac is on AUTOMATA immediately.

`~/.h2t` is machine-local, and the whole day demonstrated what that means: 9 entry points on one
machine and 4 on the other, different `core.hooksPath`, different venv contents.

So the architecture is coherent: **`.dor` is shared state, `~/.h2t` is local state.** The
three-way contradiction about where secrets live is not carelessness; it is the trace of an
unfinished migration between those two models — `meetgeek/client.py:50` and the SessionStart
banner already point at the local one while the loader still reads the shared one.

For an external user the whole model collapses: no Syncthing, no second machine, no `.dor`. The
fork that is meaningful here becomes three wrong addresses there. That does not make #432
smaller — it makes it a design decision rather than a cleanup, and the decision is *which of the
two models a single-machine user gets*.

One consequence worth stating on its own: **`~/.dor/secrets/secrets.env` travels over
Syncthing.** That is deliberate — the keys are needed on both boxes — but it means credentials
live inside a synchronised folder, and any third device added to that share receives them
without a further step.

## Correction to C2: the code is parameterised, the instructions are not

Measured after the first pass. The tree already has a path-parameterisation mechanism and uses
it widely — at least twelve environment variables:

```
H2T_CONFIG_ROOT  H2T_SESSION_ROOT  H2T_SECRETS_FILE  H2T_LAKE_ROOT
H2T_ACTIVITY_SPOOL  H2T_MACHINE_NAME  H2T_DEV_ROOT  H2T_PLUGIN_ROOT
H2T_EVALS_MODE  H2T_EVALS_TOKEN  H2T_PYTHON  H2T_LINT_ENTRIES
```

`H2T_DEV_ROOT` is one of them:

```python
plugins/h2t-core/skills/scaffold-project/scripts/scaffold_project.py:411
plugins/h2t-dev/lib/docs/common.py:9
    DEV_ROOT = Path(os.environ.get("H2T_DEV_ROOT", "C:/dev"))
```

So the *scripts* are not hardcoded — their **default** is wrong. The actual defect sits one
layer up: `H2T_DEV_ROOT` is mentioned **zero times** in either SKILL.md that writes `C:/dev`
into its prose (`scaffold-project/SKILL.md:61,64,67`, `project-audit/SKILL.md:22,23,33,40,41`).

An agent following the skill offers `C:/dev/{id}` as the default project location, while the
script underneath would have honoured the environment. Code and its own documentation disagree,
and only the documentation is read by the thing making the decision.

This makes #434 smaller and sharper than filed. Three pieces:

1. a portable default instead of `C:/dev` (the value, not the mechanism),
2. a root key in `repo-mapping.yaml` — which today holds only `mappings`, `cwd_patterns` and
   `default`, while `H2T_CONFIG_ROOT` already exists to find that file,
3. the two SKILL.md files told about the variable they are overriding by accident.

## On having two config directories

`.dor` synced, `~/.h2t` local — the split is a reasonable architecture and phase C mistook it
for carelessness. What is genuinely wrong is the **naming**: `.dor` is a project name and
`.h2t` is the ecosystem name, and neither says anything about the role it plays. Establishing
that one is shared and the other is not required reading the Syncthing config.

For a single-machine user the split has no purpose at all — there is nothing to sync with, both
directories are local, and the distinction degrades into two places where the same thing might
be. That is the form in which an outsider meets it, and it is the reason #432 is a design
decision rather than a rename.

## Open manifest question: `h2t-creative`

Raised by the operator during the run — "not sure, they are raw". Measured, the plugin is three
layers in very different states, and only one of them is raw.

```
engine    assembler.py + 968 tests in 14 files — the best-tested code in the repository
          (legacy fidelity 128, field mapper 59, asset validator 46, skin loader 31,
           semantic parser 29, editorial landing primitives 35 …)
skills    7 skills, 94–1361 lines; none has scripts/, six have no references/
profiles  6 profiles, 295 files of design assets; 2 files carry personal data
```

The tests cover the **engine**, not the skills. So the most verified code in the tree is wrapped
in its thinnest instruction layer: seven prose skills, no scripts, and `design` as a 1361-line
monolith (the same file phase I flagged for loading cost).

"Raw" is accurate for the wrapper and wrong for the engine. Dropping the plugin wholesale would
discard 968 tests of working code because of the prose around it.

**The profiles are a different question again.** `h2t-pfad`, `h2t-graphs`, `h2t-editorial` are
the operator's own brands; `h2t-default`, `h2t-mono`, `h2t-terminal` read as generic. Whether to
publish them is not a readiness judgment but an identity one — the same shape as `lesson-parser`
in `h2t-edu`, which the operator resolved by keeping it back.

Default recommendation if the decision is not made before publication: **leave `h2t-creative`
out of the snapshot.** Not because the engine is weak — it is the strongest part — but because
publishing it usefully means publishing the profiles with it, and that is a decision about
identity rather than about code. A plugin can be added later; it cannot be withdrawn once
cloned.

### `h2t-creative` — the rework stopped, and the tracker says so

The operator recalled a global rework that "drowned", with crooked output. That is not a
recollection to check against taste — it is filed.

```
commits on plugins/h2t-creative:  22 in 2026-04, 42 in 2026-05, 4 in 2026-08
```

The four August commits are repo-wide chores — a lint-debt sweep, a rule-set pin, a namespace
fix, a version bump. Real work on the plugin stopped at the end of May: three months.

Open issues name the gap precisely:

```
#83  creative: [recovery] restore rich component library — fidelity gap vs legacy skills
#88  skills: [R2b] Recover h2t-editorial landing legacy fidelity
#90  skills: [R3a] Add h2t-graphs deck form
#91  skills: [R3b] Add h2t-mono deck form
```

And the test distribution matches: of the 968 tests, **208 are fidelity-recovery tests** —
`test_r2b_legacy_fidelity_deck.py` (128) and `test_r2_legacy_fidelity.py` (80). The measuring
apparatus for the migration was built, works, and is green. The migration itself is unfinished.

**This is the third instance of one shape in a single day.** `plugins/h2t/` was the rollback
archive of the connector migration, outliving it by three months (#430). `.dor` against
`~/.h2t` is an unfinished move between shared and local state (#432). And here: migration tests
green, migration incomplete.

What they share is that **a green state is reached before the work is done**, and nothing
afterwards says otherwise. A rollback archive that nobody rolls back to looks identical to one
that is still needed; a fidelity test suite that passes on the subset already recovered looks
identical to one that passes on all of it.

This settles the manifest question rather than deferring it. Publishing `h2t-creative` would
ship a fidelity gap its own tracker documents, together with six profiles of the operator's
identity. **Leave it out**, and let #83/#88/#90/#91 close on their own schedule.
