---
title: "Plugin Versioning Policy"
status: "stable"
owner: "lichtpfad"
updated: "2026-04-19"
---

# Plugin Versioning Policy

Every plugin in this marketplace has **two** places where its version lives:

| File | Role |
|---|---|
| `plugins/<name>/.claude-plugin/plugin.json` | Plugin's own manifest (installed copy reads this) |
| `.claude-plugin/marketplace.json` → `plugins[name=<name>].version` | Marketplace index (clients read this on `/plugin marketplace update`) |

**These two MUST agree.** If they drift, Claude Code silently skips plugin load on fresh installs — observed on macOS 2026-04-19 when `h2t-ops` plugin was at `1.0.2` but the marketplace index still advertised `1.0.0`. See [#74](https://github.com/lichtpfad/h2t-skills/issues/74).

## Bumping a plugin

Use the atomic bump script — it updates both files in one call:

```bash
python scripts/bump_plugin.py <plugin-name> <new-version>
# example:
python scripts/bump_plugin.py h2t-ops 1.0.3
```

Then commit both files:

```bash
git add .claude-plugin/marketplace.json plugins/h2t-ops/.claude-plugin/plugin.json
git commit -m "chore(h2t-ops): bump 1.0.2 → 1.0.3"
```

## Semver discipline (from user-level `CLAUDE.md`)

- **Patch** (`x.x.N`) — iterations and fixes pre-live-confirmation
- **Minor** (`x.N.0`) — only after live-confirmation
- **Major** (`N.0.0`) — breaking changes

Do not bump minor on unverified changes.

## Pre-commit hook (recommended)

Install once per clone to catch drift before push:

```bash
sh scripts/hooks/install.sh
```

This symlinks `scripts/hooks/pre-commit` into `.git/hooks/`. On every commit that touches a `plugin.json` or `marketplace.json`, it runs `scripts/check_marketplace_sync.py` and blocks the commit if drift is detected.

Bypass (only when explicitly fixing the drift in a single commit):

```bash
git commit --no-verify -m "fix(marketplace): sync X from Y to Z"
```

## Manual check anytime

```bash
python scripts/check_marketplace_sync.py
```

Exit 0 with `✓ marketplace synced` = ok.
Exit 1 with per-plugin drift details = fix before push.

## What the check catches

| Drift kind | Example |
|---|---|
| `version` | marketplace says `1.0.0`, plugin.json says `1.0.2` |
| `missing` | marketplace lists a plugin whose `source` path has no `plugin.json` |
| `orphan` | `plugins/foo/` exists on disk but `foo` is not in `marketplace.json` |

## After bump: client-side activation

Bumping + pushing ≠ active. Clients must re-sync:

```
# In Claude Code
/plugin marketplace update lichtpfad
/reload-plugins            # or full CC restart (Mac sometimes requires restart)
```

## Why this matters

Claude Code's installer reads `marketplace.json` and matches against its local cache. A stale marketplace version number means:

1. Client thinks cache is up to date (cache version matches marketplace version).
2. Actual plugin code (with new features/skills) never surfaces — skill not in available list.
3. No error shown — silent skip.

The drift check is a **fail-loud gate** against this specific silent failure.
