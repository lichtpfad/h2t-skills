# Session pulse

Every live Claude and Codex session leaves one record, keyed by the program's own session
UUID. `h2t-ops sessions` lists the records by domain, project, repo and branch, with the PR
status and a resume command for each.

## Commands

| command | does |
|---|---|
| `h2t-ops sessions list` | the list; also the default with no subcommand |
| `h2t-ops sessions list --since today` | `--since` takes `YYYY-MM-DD` or `today` |
| `h2t-ops sessions list --status "<text>"` | other filters: `--domain` `--project` `--repo` `--pr` `--tool` |
| `h2t-ops sessions list --all --json` | `--all` adds unknown-origin and empty sessions |
| `h2t-ops sessions status` | refresh PR and issue status of every branch (gh, network) |
| `h2t-ops sessions backfill` | write records for sessions the hook missed |
| `h2t-ops sessions daily` | run the daily pass by hand |
| `h2t-ops sessions page` | build `state/sessions.html` and open it; `--no-open` builds only, `--out <file>` writes elsewhere |

`--json` works on every subcommand.

## What becomes a record

- A session becomes a record only after its first user message. Until then it is a local
  draft in `state/pulse/open/`. An empty session leaves nothing in the synced records.
- Headless `claude -p` runs carry the entrypoint `sdk-cli` and are never listed.
- Subagent transcripts and `codex exec` runs are never listed.

## Resume commands

The list and the page print one line per session:

```
cd <cwd>; claude --resume <session-id>
codex resume <session-id> -C <cwd>
```

The `<cwd>` is quoted for the shell of the machine that renders the line: `shlex.quote` on
POSIX (a plain path stays bare), PowerShell single quotes on Windows (`'C:\a b'`, a quote is
doubled). Paste the line as shown.

## Claude

The plugin's `hooks/hooks.json` runs `session-pulse` on `SessionStart` and `SessionEnd`.
Nothing to install.

## Codex

Codex hooks are stable from Codex 0.153. This pack does not install the entry; add it by
hand to `~/.codex/hooks.json`. The file's exact shape is in Codex's hooks documentation
(not verified here: it does not exist on the machine this page was written on). The entry
needs:

| field | value |
|---|---|
| events | `SessionStart` and `SessionEnd` |
| command | `h2t-hook session-pulse` |
| timeout | `10` |

Then trust the entry once in `/hooks` inside Codex. Trust it again after every change to the
file.

Until a Codex session-id environment variable is known (`CODEX_ID_VARS` in
`h2t_ops/lifecycle/pulse/record.py`, empty today), a Codex handoff writes its own record
instead of joining the session's.

## Daily pass

The first `SessionStart` of the day starts the pass detached. It runs backfill, branch
status, summaries and the audit map. `h2t-ops sessions daily` runs it by hand.

`sessions.audit_map` in `config/user.yaml` is an argv list: the command the pass runs to
report work outside sessions. Unset, the view says so.
