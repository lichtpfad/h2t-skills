---
title: "Pin the machine name in Claude Code settings"
status: "accepted"
date: "2026-10-10"
---

# Pin the machine name in Claude Code settings

## Context

Session records live under `~/.h2t/sessions/<machine>/<project>/`. The machine segment came
from `platform.node()`, and on macOS that is set by the network: one MacBook reported
`MacBook-Pro-3` in the morning and `Mac` in the evening (2026-09-19). Its history split into
`macbook-pro-3/` (46 records) and `mac/` (5 records), and session-start no longer found the
previous handoff.

The rule was also written three times — the session reader (`lib/gather/sessions.py`), the
handoff writer, and the activity spool — and the spool's copy kept the hostname's case, so the
same machine wrote `Mac` to the spool and `mac/` to the path. `H2T_MACHINE_NAME` already
overrode the hostname, but nothing set it, and `DOR_MACHINE_NAME` in `~/.zshrc` did not reach
Claude Code, which runs commands in bash.

## Decision

Option B, chosen by the owner on 2026-09-19 (#491):

- One function, `gather.sessions.get_machine_name()`, is the rule:
  `H2T_MACHINE_NAME` → `DOR_MACHINE_NAME` → `platform.node()` lowercased, first label.
  The handoff writer and the activity spool call it.
- `h2t-core:setup` (`setup_h2t.py setup`) writes `env.H2T_MACHINE_NAME` into
  `~/.claude/settings.json` once, with today's value of that rule, so existing directories
  keep their name. Claude Code passes `env` to every process it starts, hooks included,
  independent of the shell. An existing value is never changed; an unreadable settings file
  is left untouched and reported.

## Rejected

Option A: on macOS, default to `scutil --get LocalHostName`. It needs no setup, but it would
move the directory once on some machines and works on macOS only.

## Consequences

- After `setup`, the session directory no longer depends on the hostname.
- Machines that never run `setup` behave as before.
- Directories already split are not merged; on the MacBook that was done by hand on
  2026-09-19.
