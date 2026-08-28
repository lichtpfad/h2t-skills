# Contributing

## Setup

```bash
git clone https://github.com/lichtpfad/h2t-skills.git
cd h2t-skills
uv sync
sh scripts/hooks/install.sh     # once per clone — see "Two files move together" below
```

`uv` is the one hard prerequisite: it supplies every interpreter this repo uses. There is
no supported path that assumes a `python` on PATH, because on macOS there usually is not
one. Where a command needs an interpreter, it is `uv run python`.

## Checks

Run the same paths CI runs, or a clean local check will still fail on the runner:

```bash
uv run pytest tests/ -q
uvx ruff check plugins/ lib/ h2t_ops/ tests/ scripts/
uv run python scripts/check_marketplace_sync.py
```

The repository is at **zero ruff findings** under the rule set pinned in `pyproject.toml`
(`select = ["E4", "E7", "E9", "F", "I", "UP"]`, no `ignore`). A red line is therefore
yours. CI pins the ruff version too; if a finding appears locally and not in CI, compare
`ruff --version` before assuming it is real.

## Two files move together

A plugin is addressed by its version. Editing `plugins/<name>/` without bumping it means
the fix reaches nobody: the plugin cache keeps serving the old version, and both the
change and its test look fine locally.

```bash
uv run python scripts/bump_plugin.py <plugin-name> <version>
```

That writes `plugin.json` and `.claude-plugin/marketplace.json`. The CHANGELOG is written
by hand. The pre-commit hook installed above blocks a commit where the two JSON files
disagree — that is what `sh scripts/hooks/install.sh` buys you.

## Documents name their work

Every plan and spec under `docs/superpowers/` must name the issue it belongs to. Generate
the file rather than hand-writing frontmatter:

```bash
uv run python plugins/h2t-dev/skills/docs-lint/scripts/lint.py new plan <slug> --issue 123
uv run python plugins/h2t-dev/skills/docs-lint/scripts/lint.py new spec <slug> --issue 123
uv run python plugins/h2t-dev/skills/docs-lint/scripts/lint.py new adr  <slug>
```

`--new-issue "title"` files one first; `--no-issue "reason"` records why there is none. A
`PreToolUse` hook rejects a plan written any other way, and CI re-checks changed files.

## Conventions

`.claude/rules/` is the source, not this file. Each rule there records what was measured
and what it cost — read the one that covers what you are touching before you touch it.

| file | covers |
| --- | --- |
| `verification.md` | how a check is allowed to be believed |
| `linting.md` | the pinned rule set, and why suppression has three scopes |
| `git.md` | merge detection, branch deletion, recovering a deleted local branch |
| `plugin-deploy.md` | why `update-plugin.sh` is never the final deploy |
| `documentation.md` | issue titles, commit format, where documents live |
| `secrets.md` | rotation first, and never printing a secret to verify its removal |
| `connectors.md` | provider I/O goes through `h2t-ops` and nothing else |

Commits are `<type>: <description>` (`feat`, `fix`, `docs`, `refactor`, `test`, `chore`,
`perf`) and close their issue with `fixes #N` in the body. Issue titles are
`{repo-short}: [MN] verb noun` — for this repository, `skills: ...`.
