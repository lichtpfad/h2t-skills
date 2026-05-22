# Agent Permissions Policy

Tracked repository config must not grant personal or destructive agent
permissions.

## Tracked Policy

- Keep `.claude/settings.json` narrow and repo-scoped.
- Do not allow broad user-home reads such as `Read(//c/Users/<user>/**)`.
- Do not allow bare shell entrypoints such as `PowerShell`, `Bash(bash *)`, or
  arbitrary language runtimes.
- Do not allow destructive Git/shell operations such as `rm`, `git rm`,
  `git reset`, `git restore`, or `git checkout`.
- Keep outward-facing operations such as `git push` approval-gated unless a
  narrow workflow-specific rule is explicitly reviewed.

## Local Speed Policy

Machine-specific allowlists belong in untracked local config:

- `.claude/settings.local.json`
- user-level Claude/Codex settings outside this repository

This lets a developer keep fast local loops without shipping broad permissions
as project policy.

## Context Packers

Repo tools must not execute unpinned package code while staging private context.
If a context packer needs `repomix`, install a reviewed version on `PATH`.
Scripts must not fall back to an unpinned `npx` package invocation.
