---
title: "h2t-core:agent-profile design"
status: "draft"
owner: "Stanislav Glazov"
date: "2026-05-21"
milestone: ""
---
# h2t-core:agent-profile design

Date: 2026-05-21
Status: concept captured; implementation not started
Owner plugin: h2t-core

## Goal

Create `h2t-core:agent-profile`: a project-level Claude runtime profile manager.

The skill should make Claude Code load the right skill/plugin set for the current kind of work without forcing one global "everything enabled" setup. It should support stable repo defaults, temporary task overlays, and cross-machine sync.

## Problem

The current global Claude setup loads too many skills in every repository. After removing duplicate command/skill registration in #151-#153, the remaining context pressure comes mostly from intentionally enabled global skill packs:

- legacy `h2t`;
- user/global skills;
- broad plugin packs that are only useful in some contexts;
- project-specific work modes that change during the day.

Manual `/plugin disable` and `/plugin install` workflows are too slow and stateful. They also do not explain why a repo has a given plugin set.

## Core Model

Use two composable layers:

```text
base profile      = what kind of repository this is
session overlays  = what kind of work is happening right now
effective profile = base + overlays + local machine availability
```

Examples:

```text
POS repo:
  base = pos
  overlays = []

POS repo while writing a landing page:
  base = pos
  overlays = ["creative", "marketing"]

h2t-skills repo while editing plugins:
  base = dev
  overlays = ["plugin-dev"]
```

## Three Storage Layers

### 1. Profile Catalog

Versioned source of truth shipped with `h2t-core`.

Proposed path:

```text
plugins/h2t-core/references/agent-profiles.json
```

Contains:

- base profiles;
- task overlays;
- plugin ids per profile;
- default disabled plugin ids;
- human-readable descriptions;
- compatibility notes.

### 2. Project Binding

Committed repo-local profile selection.

Proposed path:

```text
.claude/agent-profile.json
```

Example:

```json
{
  "base": "pos",
  "overlays": [],
  "requiredPlugins": ["h2t-core", "h2t-ops", "h2t-dev"],
  "updatedAt": "2026-05-21"
}
```

This file is portable between machines. It should not contain secrets, permissions, absolute user paths, or MCP credentials.

### 3. Machine State

Machine-local state, never committed.

Proposed path:

```text
~/.claude/h2t-agent-profile.local.json
```

Contains:

- installed marketplace ids;
- plugin ids unavailable on this machine;
- local opt-outs;
- last sync result;
- optional machine-specific aliases.

## Generated Settings

The skill writes only the `enabledPlugins` part of project `.claude/settings.json`.

It must preserve unrelated settings:

- permissions;
- MCP config;
- hooks;
- local tool rules;
- project-specific non-profile settings.

Example generated block:

```json
{
  "enabledPlugins": {
    "h2t-core@lichtpfad": true,
    "h2t-ops@lichtpfad": true,
    "h2t-creative@lichtpfad": false,
    "marketing-playbook@marketing-playbook-plugins": false
  }
}
```

Current observed behavior: per-project `enabledPlugins` can disable globally enabled plugins. This was verified with `marketing-playbook@marketing-playbook-plugins: false` in `C:/dev/h2t-skills`.

## Base Profiles

Initial catalog should include these base profiles as draft defaults. Exact plugin membership is intentionally reviewable before implementation.

### dev

For codebase and plugin development.

Likely includes:

- h2t-core;
- h2t-dev;
- superpowers;
- plugin-dev;
- codex;
- GitHub-related tooling.

### pos

For Personal OS repository work.

Likely includes:

- h2t-core;
- h2t-ops;
- h2t-dev;
- superpowers.

Usually excludes by default:

- h2t-creative;
- h2t-dcc;
- marketing/product packs.

### ops

For personal operations and provider adapters.

Likely includes:

- h2t-core;
- h2t-ops;
- h2t-dev;
- lead-search when relevant.

### creative

For landing pages, decks, design systems, and visual QA.

Likely includes:

- h2t-core;
- h2t-creative;
- h2t-arch;
- frontend-design.

### dcc

For TouchDesigner / Houdini work.

Likely includes:

- h2t-core;
- h2t-dcc.

### product

For product strategy, roadmap, discovery, and positioning.

Likely includes:

- h2t-core;
- creative-thinking;
- selected PM/product plugins;
- h2t-arch when diagrams are expected.

### marketing

For go-to-market, copy, lead-gen, and landing strategy.

Likely includes:

- h2t-core;
- marketing-playbook;
- h2t-creative;
- lead-search;
- selected PM/positioning plugins.

### mixed

Fallback for repos where no strong profile exists.

Should be conservative. It should not re-create the global everything-enabled setup.

## Task Overlays

Overlays are temporary additions or subtractions on top of the base profile.

Initial overlays:

- `plugin-dev` — plugin/skill/hook/MCP development;
- `creative` — visual/design work in a non-creative repo;
- `marketing` — marketing/copy/lead-gen work;
- `product` — product strategy and PM work;
- `research` — web/research-heavy sessions;
- `dcc` — TouchDesigner/Houdini work in another repo;
- `github-heavy` — PR/issue/CI workflows;
- `minimal` — reduce to only core/session tools.

Overlays should be easy to add and remove without changing the repo's base identity.

## Skill Commands

The skill body should expose these user-facing workflows:

```text
h2t-core:agent-profile status
h2t-core:agent-profile recommend
h2t-core:agent-profile apply <base>
h2t-core:agent-profile add <overlay>
h2t-core:agent-profile remove <overlay>
h2t-core:agent-profile reset
h2t-core:agent-profile diff [profile-or-overlay]
h2t-core:agent-profile sync
h2t-core:agent-profile doctor
```

Behavior:

- `status` shows project binding, active overlays, generated settings, and missing plugins.
- `recommend` inspects repository signals and proposes a base profile.
- `apply <base>` writes `.claude/agent-profile.json` and updates `.claude/settings.json`.
- `add <overlay>` adds a temporary or persisted overlay, depending on command flags.
- `remove <overlay>` removes an overlay.
- `reset` returns `.claude/settings.json` to base profile.
- `diff` shows changes before writing.
- `sync` applies the committed project binding on the current machine.
- `doctor` checks installed plugins, marketplace availability, duplicate plugin roots, and stale cache versions.

## Sync Between Computers

Target workflow on a second machine:

```text
git pull
h2t-core:agent-profile sync
/reload-plugins
/context
```

`sync` should:

1. Read `.claude/agent-profile.json`.
2. Load the versioned catalog from `h2t-core`.
3. Check whether required plugins are installed.
4. Print missing `/plugin install ...` commands rather than silently installing.
5. Generate or update `.claude/settings.json`.
6. Preserve machine-local settings.
7. Ask the user to run `/reload-plugins`.

The skill should not sync secrets, permissions, tokens, or user-home paths.

## Recommended Implementation Shape

```text
plugins/h2t-core/skills/agent-profile/SKILL.md
plugins/h2t-core/skills/agent-profile/scripts/apply_agent_profile.py
plugins/h2t-core/skills/agent-profile/references/agent-profiles.json
```

Possible support files:

```text
plugins/h2t-core/skills/agent-profile/references/plugin-ids.md
plugins/h2t-core/skills/agent-profile/references/profile-schema.md
```

Keep `SKILL.md` small. Put catalog/schema details in references and deterministic JSON editing in the script.

## Safety Rules

- Never overwrite the full `.claude/settings.json`.
- Only manage `enabledPlugins` and the profile marker block.
- Preserve unknown keys.
- Before writing, show a diff.
- Keep global `~/.claude/settings.json` read-only unless the user explicitly asks for global profile changes.
- Do not edit permissions allowlists as part of profile switching.
- Do not install/uninstall plugins automatically in MVP; print exact commands.
- Do not touch MCP secrets or OAuth state.
- Avoid destructive cache cleanup except under explicit `doctor --fix-cache`-style approval.

## Relationship To Existing Skills

`h2t-core:init-project`

- Registers or initializes project context.
- Should not silently apply profiles in MVP.
- May suggest running `h2t-core:agent-profile recommend`.

`h2t-core:session-start`

- Can report the active profile in the briefing.
- May warn when no project profile exists.
- Should not mutate settings during normal session start.

`h2t-core:scaffold-project`

- May create `.claude/agent-profile.json` for newly scaffolded repos.

## Non-Goals

- Replace Claude Code's plugin manager.
- Solve global user skill bloat.
- Remove legacy `h2t` automatically.
- Install plugins without user approval.
- Sync secrets, tokens, permissions, or MCP credentials.
- Make one universal profile that fits all repos.
- Require changing a repo's base profile just to do one temporary task.

## MVP Definition Of Done

- `h2t-core:agent-profile` skill exists.
- Catalog includes at least `dev`, `pos`, `creative`, `dcc`, `ops`, `product`, `marketing`.
- Supports `status`, `recommend`, `apply`, `add`, `remove`, `reset`, `sync`, `doctor`.
- Writes `.claude/agent-profile.json`.
- Updates only `enabledPlugins` in `.claude/settings.json`.
- Preserves unrelated `.claude/settings.json` keys.
- Demonstrated in `C:/dev/h2t-skills` with one base profile and one overlay.
- `/reload-plugins` + `/context` confirms expected plugin visibility.

## Open Decisions

1. Exact plugin ids for each base profile.
2. Whether overlays are session-only by default or persisted in `.claude/agent-profile.json`.
3. Whether a machine-local overlay file is needed for temporary overlays.
4. Whether legacy `h2t` retirement is a profile concern or a separate migration issue.
5. Whether to expose a slash command wrapper or rely only on the skill entry.

