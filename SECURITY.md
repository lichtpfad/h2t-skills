# Security

## Reporting

Report a vulnerability by opening a [GitHub security advisory][advisory] on this
repository. That keeps the report private until a fix is out. If you cannot use
advisories, open an issue that describes the *class* of problem and asks for a
private channel — do not put a working exploit or a live credential in a public
issue.

[advisory]: https://github.com/lichtpfad/h2t-skills/security/advisories/new

## What this pack can reach

These plugins run inside Claude Code with the permissions of the person running
them. Installing them grants:

- **Shell execution.** Skills are markdown whose bash blocks an agent runs.
- **Hooks that fire on their own.** Seven wirings in
  `plugins/h2t-core/hooks/hooks.json`, and reading that file is the way to know
  what runs, not this list:

  | event | matcher | handler |
  |---|---|---|
  | `SessionStart` | — | `inject-h2t-context` |
  | `UserPromptSubmit` | — | `gather-on-prompt` |
  | `PreToolUse` | `Skill` | `gather-on-skill` |
  | `PreToolUse` | `Write` / `Edit` / `MultiEdit` | `structure-guard` — can block the write |
  | `PostToolUse` | `Bash` | `plan-closer` — writes to your working tree after `gh pr merge` |

  `plan-closer` is the only one that modifies files you did not ask it to touch:
  it stamps `status: done` on plans a merged pull request implemented, and says
  so on both channels. A document that never finishes can opt out with
  `lifecycle: living` in its frontmatter.
- **Provider credentials**, when you configure connectors: Google (Drive, Gmail,
  Calendar), Notion, Telegram, MeetGeek, Granola, and Exa-backed research.
- **Network access** to those providers and to `uv`'s package index.

## Where credentials live, and where they must not

Secrets are runtime machine state, never repository state. The loader reads, in
order: `$H2T_SECRETS_FILE`, `~/.h2t/config/secrets/secrets.env`, then
`~/.dor/secrets/secrets.env` and its legacy sibling. Nothing in this repository
should ever contain a real credential value.

`.gitignore` covers the credential patterns, and a pre-commit hook checks
`marketplace.json` against every `plugin.json`. Neither is a substitute for not
pasting a key into a file.

## If a credential does reach the history

Rotate first. A secret committed to a repository that has ever had a pull
request cannot be fully removed by rewriting history: GitHub keeps
`refs/pull/*/head` server-side and a force-push does not touch them. Measured
here on 2026-08-27, after `git filter-repo` and a force-push of every branch and
tag, 147 of 148 pull-request refs still carried the original commit. Rewriting
history is worth doing for tidiness; rotation is the control that works.

A scan is only as wide as you make it. `gitleaks detect` walks what a clone
reaches; `gitleaks detect --log-opts="--all"` after fetching `refs/pull/*` walks
what is actually there, and the two gave different answers on the same day.

## Supported versions

The published plugin versions are whatever `.claude-plugin/marketplace.json`
names on `main`. Older cached versions are not maintained — the plugin cache is
addressed by version, so an update leaves the old directory in place next to the
new one. Remove stale directories under `~/.claude/plugins/cache/` yourself.
