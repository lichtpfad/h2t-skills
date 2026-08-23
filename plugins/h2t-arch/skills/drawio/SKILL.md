---
name: drawio
description: "Generates, exports, and validates draw.io architecture diagrams. Creates styled .drawio files from graph descriptions using project-specific shape libraries (TOML). Supports PNG/SVG/PDF export via draw.io Desktop CLI. Triggers on: /drawio, 'create diagram', 'architecture diagram', 'draw.io diagram', 'export diagram', 'generate drawio'., 'h2t-arch:drawio'"
compatibility: "Claude Code"
metadata:
  author: lichtpfad
  version: 1.0.1
---

# Draw.io Diagram Skill

Generate production-quality `.drawio` architecture diagrams from structured graph descriptions with project-specific styling.

## Setup

`generate.py` imports `drawpyo` unconditionally, and nothing installs it for you:

```bash
python -c "import drawpyo" 2>/dev/null || {
  echo "ERROR: drawpyo not installed. Run: pip install drawpyo"
  exit 1
}
```

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

1. Describe the graph as a Python dict
2. Run generate.py to create the .drawio file
3. Optionally export to PNG/SVG/PDF
4. Open in draw.io Desktop for review/adjustments

### Project Configuration (optional)

The skill looks for two files in the project root:

- **`.drawio-skill.yaml`** — Theme, layout settings, export config
- **`.drawio-shapes.toml`** — Shape library (colors, shapes, sizes per entity type)

Without these, the skill uses built-in defaults (light theme, generic shapes).

## Creating a Diagram (`/drawio create`)

### Step 1: Define the graph as a Python dict

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
~/.claude/skills/.venv/bin/python -c "
import sys, os
sys.path.insert(0, '${CLAUDE_SKILL_DIR}/scripts')
from generate import generate_diagram

graph = {
    # ... your graph dict here
}

# Without project config (uses defaults):
generate_diagram(graph, 'output.drawio')

# With project config:
generate_diagram(graph, 'docs/diagrams/my_diagram.drawio',
    shapes_path='.drawio-shapes.toml',
    config_path='.drawio-skill.yaml')
"
```

### Step 3: Open in draw.io Desktop

```bash
open <path_to_drawio_file>
```

## Exporting (`/drawio export`)

Export `.drawio` to PNG, SVG, or PDF via draw.io Desktop CLI:

```bash
~/.claude/skills/.venv/bin/python -c "
import sys, os
sys.path.insert(0, '${CLAUDE_SKILL_DIR}/scripts')
from export import export_diagram

# Basic export:
export_diagram('diagram.drawio', fmt='png')

# With project config:
export_diagram('docs/diagrams/arch.drawio', fmt='png',
    config_path='.drawio-skill.yaml')

# Export specific page:
export_diagram('diagram.drawio', fmt='svg', page_index=0)

# Export all pages:
export_diagram('diagram.drawio', fmt='pdf', all_pages=True)
"
```

Output is saved as `<name>.drawio.<fmt>` next to the source file.
With `embed_diagram: true` in config, PNG/SVG contain editable XML inside.

## Graph Description Reference

### Node Types

Check available shape types in the project:
```bash
~/.claude/skills/.venv/bin/python -c "
import os, tomllib
for p in ['.drawio-shapes.toml', '${CLAUDE_SKILL_DIR}/config/shapes/general.toml']:
    if os.path.exists(p):
        with open(p, 'rb') as f:
            shapes = tomllib.load(f)
        for k in sorted(shapes):
            if not k.startswith('_') and k not in ('title', 'version'):
                print(f'  {k}: {shapes[k].get(\"baseStyle\", \"\")}')
        break
"
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
