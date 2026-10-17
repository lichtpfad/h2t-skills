---
name: report-issue
description: "Report a defect in the h2t plugin pack (h2t-core, h2t-ops, h2t-dev, h2t-arch, h2t-creative, or an h2t-* CLI command) to its upstream repo, lichtpfad/h2t-skills. Use when an h2t skill, hook or command fails, misbehaves, or its docs are wrong — not for the user's own project. Triggers: 'report an h2t bug', 'h2t is broken', 'file an issue upstream', 'сообщить об ошибке h2t', 'завести баг в h2t'."
compatibility: "Files through the GitHub CLI (gh), authenticated with any GitHub account. Without
  gh it hands the user the finished draft and the new-issue URL instead."
metadata:
  author: lichtpfad
  version: 0.1.0
---

# Report an h2t issue upstream

The pack is maintained in one place: **`lichtpfad/h2t-skills`**. A defect found on any
machine that installed it belongs there — not in the user's repository, and not fixed in
place.

Do not patch the pack's files in the plugin cache (`~/.claude/plugins/cache/…`,
`~/.codex/plugins/cache/…`) or in the installed `h2t-ops` tool. The next update overwrites
them, the fix reaches nobody else, and the defect stays unreported. A local workaround for
the user's current task is fine; say that it is one, and report the defect anyway.

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

Here a failed check does not stop the skill: the report may be about the install itself.
Keep the JSON (or the error text) as evidence for Step 2, show the user its hint, and go on.

## Step 1 — Is it the pack?

| what you see | what it is | action |
|---|---|---|
| `error[config]` naming a missing key, token or file | the user's setup is incomplete | `h2t-core:setup`, not an issue |
| exit 4 with a provider 401/403 | the user's credential is wrong or expired | fix the credential, not an issue |
| provider 5xx, timeouts, rate limits | the provider | retry later, not an issue |
| a traceback, a wrong result, a crash, a command a skill tells you to run that does not exist, a hint pointing at something that is not there, docs that contradict behaviour | **the pack** | continue |
| a capability the pack lacks | the pack, as a request | continue; title it `feature:` |

Reproduce once before reporting. One run can be a fluke; two identical runs are a defect.

## Step 2 — Collect evidence

```bash
h2t-ops --version
uv tool list | grep -A1 '^h2t-ops'
```

Also: the plugin and its version (`/plugin` in Claude Code, `codex plugin list` in Codex),
the harness and its version, the OS, the exact command or skill invoked, the exit code,
the error class and its message.

## Step 3 — Remove everything private

The repository is **public**. Never include:

- secrets, tokens, API keys, OAuth codes, cookies, session files;
- email bodies, transcripts, calendar descriptions, chat text, document contents;
- full provider JSON payloads;
- personal emails, phone numbers, names of clients or people;
- local paths that name a private project or person — write `~/<project>` instead.

Truncate ids to a few characters. Prefer the shape of a payload to its content.

## Step 4 — Draft, show, ask

Check for an existing report first:

```bash
gh issue list --repo lichtpfad/h2t-skills --state all --search "<two or three keywords>"
```

If one matches, the new evidence becomes a comment on it, not a new issue.

Otherwise write the body to a file in the session's scratch or temp directory, with exactly
these headings — they are the bug form's, and the repository's triage workflow recognises a
report by them:

```md
### What happened

### Steps to reproduce

### Expected

### Environment

### Error output
```

Show the user the title and the whole body, and say that it will be public. **Create the
issue only after an explicit yes.** A user who declines keeps the draft.

## Step 5 — File it

```bash
gh issue create --repo lichtpfad/h2t-skills \
  --title "bug: <component>: <symptom in a few words>" \
  --body-file <draft file>
```

- `--repo` always. Without it gh files into whatever repository the shell is in — the
  user's own.
- No `--label`. A reporter cannot set labels on someone else's repository; the triage
  workflow adds `type:bug` and `status:triage` from the headings.
- Report the URL gh prints.

Without gh, or when it is not authenticated, give the user the draft and this link, which
opens the same form in the browser:

```text
https://github.com/lichtpfad/h2t-skills/issues/new?template=bug.yml
```
