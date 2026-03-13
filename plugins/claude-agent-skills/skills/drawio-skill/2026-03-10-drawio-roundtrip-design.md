# Design: draw.io Round-Trip Position & Style Preservation

**Date:** 2026-03-10
**Scope:** `~/.claude/skills/drawio-skill/scripts/generate.py`
**Status:** Approved, ready for implementation

---

## Problem

`generate_diagram()` always writes from scratch via drawpyo. User edits (positions, styles, manually added nodes) are lost on every regeneration. Round-trip test confirmed: 2/3 nodes lost their positions after regeneration.

---

## Design

### Principle: User Always Has Last Word

- **Managed nodes** (in `graph dict`): Claude controls existence, label, edges. User controls position, size, style.
- **User-only nodes** (in draw.io, not in `graph dict`): preserved verbatim.
- **Removed from graph dict** (by user instruction to Claude): disappear from draw.io.

### New Function: `_read_existing(path)`

Reads existing `.drawio` file before generation. Returns:

```python
{
    "managed": {
        "ccxt": {"x": 500, "y": 300, "w": 120, "h": 60, "style": "rounded=1;..."},
        ...
    },
    "user_nodes": [<ET.Element>, ...]  # cells with draw.io-generated IDs
}
```

**How to distinguish managed vs user-only nodes:**
- Managed: short readable string ID (`"ccxt"`, `"L1_SPX"`) — injected by skill on previous run
- User-only: draw.io Desktop ID pattern (`"6MHS348oe3dsvKXpeqjV-..."`) — 20+ alphanum chars

```python
def _is_user_managed(cell_id: str) -> bool:
    return not re.match(r'^[A-Za-z0-9]{20,}', cell_id)
```

### Refactor: `_inject_links` → `_post_process_xml`

Extends existing post-processing (single XML pass) to:

1. **Inject user string IDs**: replace Python `id()` addresses with user-provided IDs
2. **Restore positions/sizes**: if node existed in previous file, apply saved `x/y/w/h`
3. **Restore styles**: if node existed in previous file, replace drawpyo-generated style with user's style
4. **Append user-only nodes**: copy verbatim into `<root>` of new file

New nodes (first time in graph dict, not in existing file) get TOML default style as before.

### API Change

Single new parameter with safe default:

```python
def generate_diagram(
    graph: dict,
    output_path: str | os.PathLike,
    preserve_user_edits: bool = True,   # NEW
    shapes_path: str | Path | None = None,
    config_path: str | Path | None = None,
) -> str:
```

`preserve_user_edits=False` → full overwrite (reset layout to graph dict positions + TOML styles).

---

## Data Flow

```
existing .drawio (optional)
         ↓
    _read_existing()
         ↓
   existing_data = {managed: {...}, user_nodes: [...]}
         ↓
drawpyo generates new file (from scratch, graph dict positions + TOML styles)
         ↓
    _post_process_xml(existing_data)
         ├── inject user IDs
         ├── restore positions/styles for managed nodes
         └── append user-only nodes verbatim
         ↓
   final .drawio (merge result)
```

---

## Edge Cases

| Case | Behaviour |
|------|-----------|
| File doesn't exist yet | Generate as before (no merge) |
| Node new in graph dict | TOML default style, graph dict position |
| Node in both graph dict and draw.io | User's position/style wins |
| Node removed from graph dict | Disappears (user asked Claude to remove) |
| User-only node (draw.io ID) | Preserved verbatim |
| `preserve_user_edits=False` | Full overwrite, TOML styles, graph dict positions |

---

## Testing Plan

1. **Unit: `_read_existing`** — parses fixture XML, returns correct managed/user_nodes split
2. **Unit: `_is_user_managed`** — correctly classifies IDs
3. **Integration: round-trip test** — generate → simulate user edits → regenerate → assert positions preserved
4. **Integration: user-only node test** — inject draw.io-style cell → regenerate → assert it survives
5. **Integration: new node test** — add node not in previous file → assert TOML style applied
6. **Integration: `preserve_user_edits=False`** — assert positions reset to graph dict values
