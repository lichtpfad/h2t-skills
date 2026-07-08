## skills-release milestone (29 issues)

Deploy connector, session-start/handoff stability, gather/writer packaging, research ergonomics, Drive connector format aliases, stdlib HTML→MD fallback.

## Lifecycle OS (#196, #197)

- `scaffold-project` installs Stop + PostToolUse git-commit hooks in nested Claude Code hook shape
- `post-git-commit-docs-lint` hook: runs docs-lint doctor after commits touching `docs/*.md`, writes JSON report to `.h2t/lifecycle/`
- `gh-memory` deprecated as compatibility shim — use `h2t-core:session-start` / `h2t-core:handoff`

## Versions

- h2t-core 3.2.6
- h2t-dev 1.0.13
