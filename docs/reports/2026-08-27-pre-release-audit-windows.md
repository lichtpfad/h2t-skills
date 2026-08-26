---
title: "Pre-release audit — Windows half of phase D (clean machine)"
date: "2026-08-27"
status: "complete"
issue: "#431"
runbook: "docs/reports/2026-08-27-pre-release-audit.md"
---

# Pre-release audit — Windows (AUTOMATA)

The macOS report's phase D left one column open: whether the failures classified *quiet* there
are quiet on Windows too, where the console codepage and path separators change what a failure
looks like. This is that column. Machine: AUTOMATA, Windows 11, `git-bash` shell, Python 3.11.9.

**Method.** A synthetic clean `HOME`: `C:/tmp/cleanhome`, with `HOME` **and** `USERPROFILE`
overridden per-invocation (covers both `ntpath.expanduser` and direct `USERPROFILE` reads).
Verified before measuring: `expanduser('~')` → `C:/tmp/cleanhome`, `~/.h2t` does not resolve.
Read-only by instruction — nothing fixed.

**Two honest limits on this measurement, stated up front because they change how to read it:**

1. **The clean `HOME` isolates `~/.h2t`, not the toolchain.** `uv`, and all 9 entry points in
   `C:\Users\stani\.local\bin`, are already installed on this machine and stay on `PATH` under
   the override. A *genuinely* fresh clone has neither. So every "ready" below that concerns the
   toolchain (`uv: ready`, `entry points: ready`) is an artefact of this machine, not a
   measurement of a newcomer's. The `~/.h2t`-dependent findings are sound; the toolchain ones
   are strictly optimistic.
2. **stdout/stderr were captured to files, not a TTY.** That means the cp1252 console-encoding
   path (#428) was *not* exercised — a Russian-language print that crashes in a real terminal
   would look clean here. `h2t-gather` emitted Cyrillic without error into a pipe; that does not
   clear it for an interactive console. #428 stays open; this run does not touch it.

## ШАГ 0 — sync

`git pull` fast-forwarded `1c6d7ee → 87c3148`. Tree clean.

**No ghost directories.** The macOS side warned that `__pycache__` might leave empty dirs under
`plugins/h2t/` after the `#430` deletion. On AUTOMATA it did **not**: `plugins/h2t` does not
exist on disk at all, `git status` clean. The expected ghost is absent here — worth recording
as a divergence, not a defect.

## Entry points under clean HOME (phase D core)

| # | command | rc | first line | category |
|---|---------|----|-----------|----------|
| 1 | `h2t-ops --help` | 0 | `usage: h2t-ops ...` | ok |
| 2 | `h2t-ops doctor` | 0 | version + `secrets: NOTION_API_TOKEN=MISSING` / `gmail credentials=MISSING` | **QUIET** |
| 3 | `h2t-ops connectors` | 0 | connector list | ok |
| 4 | `h2t-gather --briefing-only` | 0 | `BRIEFING:` … Hint `/h2t:init-project` | **MISLEADING** |
| 5 | `h2t-handoff --help` | 0 | `usage: h2t-handoff` | ok |
| 6 | `h2t-activity-log --help` | 0 | `usage: writer.py ...` | **MISLEADING (minor)** |
| 7 | `h2t-project-register --help` | 0 | usage | ok |
| 8 | `h2t-project-audit-scan --help` | 0 | usage | ok |
| 9 | `h2t-project-audit-report --help` | 0 | usage | ok |
| 10 | `h2t-scaffold-project --help` | 0 | usage | ok |
| 11 | `h2t-hook --help` | 5 | `Plugin entrypoint script not found: hooks-handlers/--help` | LOUD |

All 9 entry points **start** under a clean HOME — none crash on a missing `~/.h2t`. The
interesting rows are the two quiet ones and the one loud one, which confirm macOS:

- **#2 `h2t-ops doctor` — QUIET.** It *does* report `NOTION_API_TOKEN=MISSING` and
  `gmail credentials=MISSING` (loud text), but **exits 0**, and never mentions that `~/.h2t`
  is absent at all. It also checks secrets for only 2 of 9 connectors. Anything gating on the
  exit code reads success. This is exactly the macOS finding (morning item 17), reproduced on
  Windows: the *text* is loud, the *contract* is silent.
- **#4 `h2t-gather` — MISLEADING.** rc 0, `sources_failed: []`, does not invent — it sets
  `project: unknown` and prints a real Hint: *"Repo не зарегистрирован. Запусти
  `/h2t:init-project`."* But the `h2t` plugin namespace is not shipped (renamed to `h2t-core`),
  so a newcomer who follows the hint gets *Unknown command*. Confirmed as issue **#433 / D3**;
  and `lib/gather/briefing.py:289` hardcodes it while `lib/gather/test_briefing.py:139` pins it
  green. Same defect, live on Windows.
- **#6 `h2t-activity-log --help` — MISLEADING (minor).** Usage line prints `usage: writer.py`,
  the internal filename, not the entry-point name. Cosmetic, but a newcomer copy-pasting help
  learns a name that does not exist on `PATH`. Not in the macOS table — possibly new.
- **#11 `h2t-hook --help` — LOUD.** Treats `--help` as a hook name, looks for
  `hooks-handlers/--help`, rc 5 (`not found`) with a clear message and an override hint. This is
  the "`--help` as a filename" class (morning item 16); loud and correctly coded here.

## ШАГ 3 — setup_h2t.py, read as a newcomer

`setup_h2t.py doctor` (rc 0): `platform: windows`, `uv: ready`, `h2t-ops: ready`,
`entry points: ready`, `optional POS/DOR: not_configured`. Reads reassuring — but per limit (1)
above, `uv`/`entry points` "ready" is this machine, not a fresh clone. It says nothing about the
empty `~/.h2t` and gives **no next step**. `--help` (rc 0) lists 7 subcommands
`{doctor,setup,repair,update,connectors-check,install-h2t-ops,secrets}` with **no descriptions**
and no hint that `setup` is where a newcomer starts. Judgement: it runs and is readable, but on
a truly clean machine it would neither detect the gap nor point at the fix.

## ШАГ 4 — connectors with no keys (contract 0-6)

| command | rc | stderr | verdict |
|---------|----|--------|---------|
| `h2t-ops calendar list` | 3 | `error[config]: Google OAuth token not found` + hint | LOUD, correct |
| `h2t-ops drive list` | 3 | `error[config]: Google OAuth token not found` + hint | LOUD, correct |
| `h2t-ops notion search test` | 3 | `error[config]: Notion API token not found` + hint (real path) | LOUD, correct |
| `h2t-ops gmail --help` | 0 | — | ok |
| `h2t-ops notion --help` | 0 | — | ok |

**Not "1 for everything."** Missing keys map uniformly to **rc 3 (config)**, loud, with an
actionable hint pointing at the real loader path (`~/.dor/secrets.env`). One nuance vs the
stated expectation "4 = auth": the implementation treats *no token at all* as config (3), not
auth (4) — defensible (not-configured ≠ invalid-credential), and worth pinning in the contract
rather than calling a defect.

## ШАГ 5 — restore

`HOME`/`USERPROFILE` were never overridden globally (per-invocation only), so nothing needed
un-setting. Confirmed: without override, `h2t-ops doctor` reports `NOTION_API_TOKEN=present`,
`gmail credentials=present`; `expanduser('~')` → `C:\Users\stani`; `~/.h2t exists: True`.
RESTORED: yes.

## The quiet column, summarised

The macOS report asked which macOS-quiet failures stay quiet on Windows. Answer: **the two that
matter reproduce identically.** `h2t-ops doctor` is quiet-by-exit-code on both. `h2t-gather`'s
dead-namespace hint is misleading on both. Windows adds one minor misleading case
(`activity-log` prog name) and — importantly — does **not** add a louder failure mode: the
codepage-crash risk (#428) is real but was not reachable through these entry-point paths with
output redirected, so it is neither confirmed nor cleared here.
