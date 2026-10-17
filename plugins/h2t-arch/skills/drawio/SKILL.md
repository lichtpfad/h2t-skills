---
name: drawio
description: "Generates, exports, and validates draw.io architecture diagrams. Creates styled .drawio files from graph descriptions using project-specific shape libraries (TOML). Supports PNG/SVG/PDF export via draw.io Desktop CLI. Triggers on: /drawio, 'create diagram', 'architecture diagram', 'draw.io diagram', 'export diagram', 'generate drawio'., 'h2t-arch:drawio'"
compatibility: "Requires the h2t-ops CLI with its drawio extra (h2t-drawio generate needs
  drawpyo), the draw.io desktop app for export, and Node for the validators."
metadata:
  author: lichtpfad
  version: 1.0.1
---

# Draw.io Diagram Skill

Generate production-quality `.drawio` architecture diagrams from structured graph descriptions with project-specific styling.

<!-- version-check:begin -->
## Version check

Run this before any other command of this skill:

```bash
h2t-ops version --expect @VERSION@ --json
```

Act on the result, in this order:

1. JSON with `"ok": true` — continue.
2. JSON with `"ok": false` — show the user `error.hint` as it is and stop this skill until
   it is resolved. Do not run anything the hint names unless the user asks you to: on
   `reason: path` it is a command for the user to decide on. `error.details.reason` names the
   case: `not_installed`, `version` or `path`.
3. `command not found` — read `~/.h2t/run/install.env`
   (`grep -E '^(STATE|H2T_HOOK)=' ~/.h2t/run/install.env`). With `STATE=ready` the install
   is fine and PATH does not reach it: show the directory of the `H2T_HOOK=` path, ask the
   user to restart the harness, and offer `uv tool update-shell` for them to run. Without
   it there is no install: give the user `@BOOTSTRAP@ sync`.
4. Anything else (a non-zero exit without JSON, the usage text of an older CLI) — give the
   user `@BOOTSTRAP@ sync`.
<!-- version-check:end -->

## Setup

Everything runs through one command, `h2t-drawio`, with three subcommands: `generate`,
`export` and `shapes`. Only `generate` needs `drawpyo`, which is the CLI's `drawio` extra
(`uv tool install 'h2t-ops[drawio]'`). Without it, `generate` exits 3 and prints that remedy
rather than an ImportError; `export` and `shapes` work on a base install.

Export additionally needs the draw.io Desktop CLI at
`/Applications/draw.io.app/Contents/MacOS/draw.io`, overridable through
`.drawio-skill.yaml` (`export.drawio_path`).

## Commands

| Command | Description | Status |
|---------|-------------|--------|
| `/drawio create <path>` | Create new diagram from graph description | Available |
| `/drawio export <path> [--format png\|svg\|pdf]` | Export to raster/vector | Available |
| `/drawio validate <path>` | Check diagram quality | Planned (Iter 4) |
| `/drawio update <path>` | Modify existing diagram | Planned (Iter 3) |
| `/drawio convert <mermaid> --output <drawio>` | Convert Mermaid to styled .drawio | Planned (Iter 3) |

## Quick Start

### Creating a diagram

1. Describe the graph in a YAML or JSON file
2. Run `h2t-drawio generate` to create the .drawio file
3. Optionally export to PNG/SVG/PDF
4. Open in draw.io Desktop for review/adjustments

### Project Configuration (optional)

The skill looks for two files in the project root:

- **`.drawio-skill.yaml`** — Theme, layout settings, export config
- **`.drawio-shapes.toml`** — Shape library (colors, shapes, sizes per entity type)

Without these, the skill uses built-in defaults (light theme, generic shapes).

## Creating a Diagram (`/drawio create`)

### Step 1: Write the graph to a YAML or JSON file

The keys, shown as a Python dict for the comments. In YAML `None` is `null` and `False` is
`false`; in JSON drop the comments.

```python
graph = {
    "nodes": [
        {
            "id": "unique_id",           # Required — unique identifier
            "label": "Display\\nName",    # Required — use \\n for line breaks
            "type": "shape_type",        # From TOML shape library
            "x": 100, "y": 200,         # Optional — explicit position (pixels)
            "width": 140, "height": 60,  # Optional — override TOML defaults
            "link": "docs/adr/008.md",   # Optional — clickable link in draw.io
            "tooltip": "Description",    # Optional — hover tooltip
        },
    ],
    "edges": [
        {
            "from": "source_id",         # Required
            "to": "target_id",           # Required
            "label": "relationship",     # Optional — edge label
            "tooltip": "details",        # Optional — hover tooltip
            "style": "solid",            # solid | dashed | dotted
            "arrow": "classic",          # classic | block | open | diamond
            "color": None,               # None = auto from target type, or "#hex"
            "routing": "orthogonal",     # orthogonal | straight | curved
            "bidirectional": False,      # Arrows on both ends
        },
    ],
    "containers": [
        {
            "id": "group_id",            # Required
            "label": "Group Name",       # Required
            "type": "layer_boundary",    # From TOML shape library
            "children": ["node_id"],     # Node IDs inside this container
            "x": 0, "y": 0,             # Position
            "width": 400, "height": 300, # Size
        },
    ],
}
```

### Step 2: Generate the .drawio file

```bash
# Without project config (uses defaults):
h2t-drawio generate graph.yaml output.drawio

# With project config:
h2t-drawio generate graph.yaml docs/diagrams/my_diagram.drawio \
  --shapes .drawio-shapes.toml --config .drawio-skill.yaml
```

Regenerating keeps the positions and nodes a user moved or added in draw.io; `--reset`
overwrites them instead. The command prints the path it wrote.

### Step 3: Open in draw.io Desktop

```bash
open <path_to_drawio_file>
```

## Exporting (`/drawio export`)

Export `.drawio` to PNG, SVG, or PDF via draw.io Desktop CLI:

```bash
# Basic export:
h2t-drawio export diagram.drawio --format png

# With project config:
h2t-drawio export docs/diagrams/arch.drawio --format png --config .drawio-skill.yaml

# Export specific page:
h2t-drawio export diagram.drawio --format svg --page 0

# Export all pages:
h2t-drawio export diagram.drawio --format pdf --all-pages
```

Output is saved as `<name>.drawio.<fmt>` next to the source file.
With `embed_diagram: true` in config, PNG/SVG contain editable XML inside.

## Graph Description Reference

### Node Types

Check available shape types — the shipped library, with the project's file merged on top
the way `generate` merges it:
```bash
h2t-drawio shapes --shapes .drawio-shapes.toml --json
```

### Edge Color Convention

When edge `color` is `None`, color is automatically resolved from the **target** node type using the `[_edges]` section in the TOML. This ensures visual consistency:
- Edges to S3 storage → orange
- Edges to TimescaleDB → green
- Edges to ClickHouse → teal
- Internal process edges → blue

Override with explicit `"color": "#hex"` when needed.

### Node Links

Nodes with `link` become clickable in draw.io Desktop:
- `"link": "docs/adr/008-killswitch-policy.md"` — opens file
- `"link": "src/execution/order_manager.py"` — opens source

### Auto-Grid Positioning

When nodes don't have explicit `x`/`y`, they are placed in an auto-grid:
- Starts at (100, 100)
- Steps horizontally by `node_spacing` (default 200px)
- Max 4 columns, then wraps to next row
- Row spacing: `level_spacing` (default 120px)

For precise layouts, always specify `x`/`y` explicitly.

### Containers

Containers group nodes visually. Children are positioned relative to the container.
Common container types: `layer_boundary` (labeled swimlane), `external_layer` (dashed border).

## Tips

- Always specify `x`/`y` for production diagrams — auto-grid is for quick drafts
- Use `\\n` in labels for multi-line text
- After generating, fine-tune positions in draw.io Desktop
- Export with `embed_diagram: true` so PNG/SVG remain editable
- Edge routing `orthogonal` (right angles) looks best for architecture diagrams
