# Connector Issue Policy

Use this policy when an h2t-ops connector command is missing, returns the wrong shape, fails with a provider bug, or forces an agent toward raw provider API code.

## Bug vs Feature

- Bug: a documented `h2t-ops CONNECTOR VERB` command exists but fails, returns the wrong output shape, leaks raw errors, or violates the connector boundary.
- Feature: a useful provider operation is not exposed by `h2t-ops`.

## Never Include

- secrets, tokens, OAuth codes, cookies, session files;
- raw email bodies, transcripts, calendar descriptions, chat text;
- private Notion page bodies or private Drive document bodies;
- full provider JSON payloads containing personal data;
- personal emails, phone numbers, client names, or private file paths unless the user explicitly approves and the data is already public.

## Allowed Evidence

- connector name;
- command name;
- installed/local CLI source;
- operating system class;
- exit code;
- typed error class;
- sanitized error message;
- redacted JSON envelope shape;
- synthetic examples;
- artifact refs without raw content.

## Issue Template

```md
## Context

- Connector:
- Command:
- Environment: Windows/macOS/Linux
- CLI source: installed/local/dev
- Read or write path:

## Expected

Behavior without private payloads.

## Actual

- Exit code:
- Error class:
- Sanitized message:

## Repro

`h2t-ops CONNECTOR VERB --json`

## Evidence

- CLI version:
- Connector:
- Redacted envelope:
- Artifact refs only, no raw content:

## Privacy Review

- [ ] No tokens/API keys/cookies/session files
- [ ] No raw email bodies, transcripts, calendar descriptions, chat text
- [ ] No personal emails/phone numbers/client names unless already public
- [ ] IDs are truncated or generalized where possible
- [ ] Local paths contain no private project/person names, or are generalized

## Classification

type:bug|feature
priority:p?
domain:skills
phase:triage
```

## Command

Use GitHub CLI only after the issue body passes the privacy review:

```bash
gh issue create --repo lichtpfad/h2t-skills --title "h2t-ops CONNECTOR: short issue title" --body-file issue-body.md --label domain:skills --label phase:triage
```

If unsure whether evidence is private, do not create the issue automatically. Show the sanitized issue draft to the user first.
