# h2t-arch Changelog

## Unreleased

- chore: `node-researcher` removed. Its description pinned the skill to one project's
  diagram ("crypto-regime-orchestrator", "L5-L10 node") while occupying a slot in every
  user's skill listing, and its nonstandard `trigger:` key was read by nothing — the
  harness takes triggers from `description`. Web research is `h2t-ops:research`; node
  documentation is `h2t-arch:diagram-node`. Removed from README and from both plugin
  descriptions, which had listed it by name (#462)

## 1.0.8

- fix: the skill directory is reached through `bin/h2t-arch` on PATH rather than
  `${CLAUDE_SKILL_DIR}`, which is not exported to skill bash. drawio's four sites resolved
  against an empty prefix (#456)
