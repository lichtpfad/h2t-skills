# agent-profiles.json schema

## Draft status

Catalog plugin membership is **draft data**, not product strategy. Profiles reflect best-guess
defaults at the time of writing. Review and adjust for each repository.

## Top-level fields

| Field | Type | Description |
|-------|------|-------------|
| `version` | int | Schema version. Increment on breaking changes. |
| `pluginIds` | object | Map from short alias → full marketplace plugin id. |
| `baseProfiles` | object | Named base profiles. |
| `overlays` | object | Named task overlays. |

## pluginIds

Each alias must be a lowercase kebab-case string. The value is the full marketplace id
(`name@author`). All aliases used in `baseProfiles` and `overlays` must appear here.

## baseProfiles and overlays entries

| Field | Type | Description |
|-------|------|-------------|
| `description` | string | Human-readable purpose. |
| `enable` | string[] | Plugin aliases to enable. |
| `disable` | string[] | Plugin aliases to disable. |

## Conflict resolution (merge semantics)

1. Start with base profile's `enable` and `disable` sets.
2. Apply overlays in listed order.
3. Later overlays win on direct conflicts.
4. `enable` removes an alias from the disabled set.
5. `disable` removes an alias from the enabled set.
6. Unknown alias → `UNKNOWN_PLUGIN_ALIAS` error.
7. Unknown profile/overlay → `UNKNOWN_PROFILE` or `UNKNOWN_OVERLAY` error.

## Safety rules

- Catalog is not a permissions model. Profile switching never touches `permissions` blocks.
- Profile switching never installs or uninstalls plugins automatically.
- Only `enabledPlugins` and `h2tAgentProfile` are written to `.claude/settings.json`.
- Unknown settings keys are preserved on every write.
- Global `~/.claude/settings.json` is never touched by profile commands.
