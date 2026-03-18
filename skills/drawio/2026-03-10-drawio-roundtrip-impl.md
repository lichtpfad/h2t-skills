# draw.io Round-Trip Preservation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Preserve user-edited positions, sizes, styles, and manually-added nodes in draw.io when `generate_diagram()` regenerates a file.

**Architecture:** Before generation, read existing `.drawio` to extract user state. After drawpyo writes, post-process XML to restore user's positions/styles for managed nodes and re-append user-only nodes verbatim. User string IDs (injected by the skill) are the merge key.

**Tech Stack:** Python 3.11+, `xml.etree.ElementTree`, drawpyo, existing `_post_process_xml` pattern in `generate.py`.

---

## Context

**Skill directory:** `~/.claude/skills/drawio-skill/`
**Venv:** `~/.claude/skills/.venv/bin/python`
**Generator:** `scripts/generate.py`
**Tests:** `scripts/test_generate.py` — script-style (print + assert, no pytest)

**Run all tests:**
```bash
cd ~/.claude/skills/drawio-skill && ~/.claude/skills/.venv/bin/python scripts/test_generate.py
```

**Design doc:** `docs/plans/2026-03-10-drawio-roundtrip-design.md`

**Key distinction:**
- **Managed nodes**: short user string IDs like `"ccxt"`, `"L1_SPX"` — injected by skill on previous run
- **User-only nodes**: draw.io Desktop IDs like `"6MHS348oe3dsvKXpeqjV-..."` — 20+ alphanum chars → preserve verbatim

---

## Task 1: `_is_user_managed` helper

**Files:**
- Modify: `~/.claude/skills/drawio-skill/scripts/generate.py` (add helper after `ROUTING_TO_WAYPOINTS`)
- Modify: `~/.claude/skills/drawio-skill/scripts/test_generate.py` (add Test 9)

**Step 1: Add Test 9 to test_generate.py** — append after the last test, before `print("\nAll tests passed.")`

```python
# ---------------------------------------------------------------------------
# Test 9: _is_user_managed ID classification
# ---------------------------------------------------------------------------
print("Test 9: _is_user_managed helper ... ", end="")
from generate import _is_user_managed

# Managed: short readable IDs injected by skill
assert _is_user_managed("ccxt") is True
assert _is_user_managed("L1_SPX") is True
assert _is_user_managed("kill") is True
assert _is_user_managed("s3") is True
# Not managed: draw.io Desktop auto-generated IDs (20+ alphanum chars)
assert _is_user_managed("6MHS348oe3dsvKXpeqjV-4319183397") is False
assert _is_user_managed("AbCdEfGhIjKlMnOpQrSt") is False
# Not managed: numeric-only (drawpyo Python id())
assert _is_user_managed("4314286992") is False
print("OK")
```

**Step 2: Run test — expect FAIL** (ImportError: cannot import `_is_user_managed`)

```bash
cd ~/.claude/skills/drawio-skill && ~/.claude/skills/.venv/bin/python scripts/test_generate.py 2>&1 | tail -5
```

Expected: `ImportError: cannot import name '_is_user_managed'`

**Step 3: Add `_is_user_managed` to generate.py** — insert after `ROUTING_TO_WAYPOINTS` dict (line ~59)

```python
def _is_user_managed(cell_id: str) -> bool:
    """Return True if cell_id was injected by the skill (short readable string).

    draw.io Desktop generates long alphanumeric IDs (20+ chars).
    drawpyo generates numeric Python id() addresses.
    We inject short user-provided strings like 'ccxt', 'L1_SPX'.
    """
    if not cell_id or cell_id in ("0", "1"):
        return False
    # Numeric only = drawpyo Python id()
    if cell_id.isdigit():
        return False
    # 20+ alphanum chars = draw.io Desktop generated
    if re.match(r'^[A-Za-z0-9]{20,}', cell_id):
        return False
    return True
```

**Step 4: Run tests — expect all pass**

```bash
cd ~/.claude/skills/drawio-skill && ~/.claude/skills/.venv/bin/python scripts/test_generate.py
```

Expected: `Test 9: _is_user_managed helper ... OK` + `All tests passed.`

**Step 5: Commit**

```bash
cd ~/.claude/skills/drawio-skill && git add scripts/generate.py scripts/test_generate.py && git commit -m "feat: add _is_user_managed helper for round-trip ID classification"
```

---

## Task 2: `_read_existing` function

**Files:**
- Modify: `~/.claude/skills/drawio-skill/scripts/generate.py` (add function after `_is_user_managed`)
- Modify: `~/.claude/skills/drawio-skill/scripts/test_generate.py` (add Test 10)

**Step 1: Add Test 10 to test_generate.py** — append before `print("\nAll tests passed.")`

```python
# ---------------------------------------------------------------------------
# Test 10: _read_existing — parse positions, styles, and user-only nodes
# ---------------------------------------------------------------------------
print("Test 10: _read_existing ... ", end="")
from generate import _read_existing

# Build a minimal .drawio XML fixture with:
# - one managed node (id="ccxt", known position)
# - one user-only node (draw.io Desktop ID)
fixture_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<mxGraphModel>
  <root>
    <mxCell id="0"/>
    <mxCell id="1" parent="0"/>
    <mxCell id="ccxt" value="CCXT" style="rounded=1;fillColor=#1e3a5f;" vertex="1" parent="1">
      <mxGeometry x="500" y="300" width="140" height="70" as="geometry"/>
    </mxCell>
    <mxCell id="6MHS348oe3dsvKXpeqjV-42" value="User Node" style="ellipse;" vertex="1" parent="1">
      <mxGeometry x="900" y="100" width="100" height="60" as="geometry"/>
    </mxCell>
  </root>
</mxGraphModel>'''

with tempfile.TemporaryDirectory() as tmpdir:
    fixture_path = os.path.join(tmpdir, "existing.drawio")
    with open(fixture_path, "w") as f:
        f.write(fixture_xml)

    result = _read_existing(fixture_path)

    # Managed node
    assert "ccxt" in result["managed"], "ccxt not found in managed"
    assert result["managed"]["ccxt"]["x"] == 500
    assert result["managed"]["ccxt"]["y"] == 300
    assert result["managed"]["ccxt"]["w"] == 140
    assert result["managed"]["ccxt"]["h"] == 70
    assert "rounded=1" in result["managed"]["ccxt"]["style"]

    # User-only node preserved as ET element
    assert len(result["user_nodes"]) == 1
    assert result["user_nodes"][0].get("value") == "User Node"

    # Non-existent file returns empty structure
    empty = _read_existing("/tmp/does_not_exist_xyz.drawio")
    assert empty == {"managed": {}, "user_nodes": []}

print("OK")
```

**Step 2: Run test — expect FAIL**

```bash
cd ~/.claude/skills/drawio-skill && ~/.claude/skills/.venv/bin/python scripts/test_generate.py 2>&1 | tail -5
```

Expected: `ImportError: cannot import name '_read_existing'`

**Step 3: Add `_read_existing` to generate.py** — insert after `_is_user_managed`

```python
def _read_existing(path: str | Path) -> dict:
    """Read existing .drawio file and extract managed node state + user-only nodes.

    Returns:
        {
            "managed": {user_id: {"x": int, "y": int, "w": int, "h": int, "style": str}},
            "user_nodes": [ET.Element, ...]  # cells with draw.io-generated IDs
        }
    """
    empty: dict = {"managed": {}, "user_nodes": []}
    p = Path(path)
    if not p.exists():
        return empty

    try:
        tree = ET.parse(p)
    except ET.ParseError:
        return empty

    root = tree.getroot()

    managed: dict[str, dict] = {}
    user_nodes: list = []

    for elem in root.iter():
        # Handle both plain mxCell and UserObject-wrapped cells
        if elem.tag == "UserObject":
            cell_id = elem.get("id", "")
            mxcell = elem.find("mxCell")
        elif elem.tag == "mxCell":
            cell_id = elem.get("id", "")
            mxcell = elem
        else:
            continue

        if not cell_id or cell_id in ("0", "1"):
            continue
        if mxcell is None or mxcell.get("vertex") != "1":
            continue

        geo = mxcell.find("mxGeometry")
        if geo is None:
            continue

        if _is_user_managed(cell_id):
            managed[cell_id] = {
                "x": int(float(geo.get("x", "0"))),
                "y": int(float(geo.get("y", "0"))),
                "w": int(float(geo.get("width", "120"))),
                "h": int(float(geo.get("height", "60"))),
                "style": mxcell.get("style", ""),
            }
        else:
            # User-only node — preserve the outermost element verbatim
            if elem.tag == "UserObject":
                user_nodes.append(elem)
            else:
                user_nodes.append(mxcell)

    return {"managed": managed, "user_nodes": user_nodes}
```

**Step 4: Run tests — expect all pass**

```bash
cd ~/.claude/skills/drawio-skill && ~/.claude/skills/.venv/bin/python scripts/test_generate.py
```

Expected: `Test 10: _read_existing ... OK` + `All tests passed.`

**Step 5: Commit**

```bash
cd ~/.claude/skills/drawio-skill && git add scripts/generate.py scripts/test_generate.py && git commit -m "feat: add _read_existing for round-trip state extraction"
```

---

## Task 3: Refactor `_inject_links` → `_post_process_xml`

This is the core merge step. The existing `_inject_links` already does one post-processing pass. We generalise it.

**Files:**
- Modify: `~/.claude/skills/drawio-skill/scripts/generate.py`
  - Rename `_inject_links` → `_post_process_xml`
  - Extend with: ID injection for ALL managed nodes, position/style restore, user_nodes append

**Step 1: Add Test 11 to test_generate.py** — append before `print("\nAll tests passed.")`

```python
# ---------------------------------------------------------------------------
# Test 11: _post_process_xml — ID injection + position restore + user_nodes
# ---------------------------------------------------------------------------
print("Test 11: _post_process_xml ... ", end="")
from generate import _post_process_xml

# Minimal drawpyo-style XML: numeric ID, drawpyo-generated position
fixture_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<mxGraphModel>
  <root>
    <mxCell id="0"/>
    <mxCell id="1" parent="0"/>
    <mxCell id="4399820496" value="CCXT" style="rounded=1;" vertex="1" parent="1">
      <mxGeometry x="100" y="100" width="120" height="60" as="geometry"/>
    </mxCell>
  </root>
</mxGraphModel>'''

import xml.etree.ElementTree as ET_test

with tempfile.TemporaryDirectory() as tmpdir:
    path = os.path.join(tmpdir, "test_post.drawio")
    with open(path, "w") as f:
        f.write(fixture_xml)

    # Simulate: obj_id_map maps numeric drawpyo ID → user string ID
    obj_id_map = {"4399820496": "ccxt"}
    # Saved state: user moved ccxt to (500, 300)
    existing = {"managed": {"ccxt": {"x": 500, "y": 300, "w": 140, "h": 70, "style": "ellipse;"}},
                "user_nodes": []}

    _post_process_xml(path, obj_id_map, existing)

    tree = ET_test.parse(path)
    root = tree.getroot()

    # ID should be replaced
    cell = root.find('.//mxCell[@id="ccxt"]')
    assert cell is not None, "User ID 'ccxt' not injected"

    # Position should be restored to user's 500,300
    geo = cell.find("mxGeometry")
    assert int(float(geo.get("x"))) == 500, f"x not restored: {geo.get('x')}"
    assert int(float(geo.get("y"))) == 300, f"y not restored: {geo.get('y')}"
    assert int(float(geo.get("width"))) == 140
    assert int(float(geo.get("height"))) == 70

    # Style should be from user (ellipse;) not TOML (rounded=1;)
    assert "ellipse" in cell.get("style", ""), "User style not restored"

print("OK")
```

**Step 2: Run test — expect FAIL**

```bash
cd ~/.claude/skills/drawio-skill && ~/.claude/skills/.venv/bin/python scripts/test_generate.py 2>&1 | tail -5
```

Expected: `ImportError: cannot import name '_post_process_xml'`

**Step 3: In generate.py, replace `_inject_links` with `_post_process_xml`**

Remove the old `_inject_links` function entirely and replace with:

```python
def _post_process_xml(
    xml_path: str,
    obj_id_map: dict[str, str],
    existing: dict,
) -> None:
    """Post-process drawpyo XML: inject user IDs, restore positions/styles, append user nodes.

    Args:
        xml_path:    Path to the .drawio file written by drawpyo.
        obj_id_map:  {drawpyo_python_id_str: user_string_id} for all managed nodes.
        existing:    Output of _read_existing() — prior user state.
    """
    if not obj_id_map and not existing["user_nodes"]:
        return

    tree = ET.parse(xml_path)
    root = tree.getroot()

    managed_state = existing["managed"]

    # -- Pass 1: inject user IDs, restore positions/styles, handle links ------
    for elem in list(root.iter()):
        for child in list(elem):
            drawpyo_id = child.get("id", "")
            user_id = obj_id_map.get(drawpyo_id)
            if user_id is None:
                continue

            link_attrs = {}  # collect link/tooltip if set on existing UserObject

            if child.tag == "UserObject":
                # drawpyo already wrapped it (tooltip was set)
                child.set("id", user_id)
                mxcell = child.find("mxCell")
            elif child.tag == "mxCell" and child.get("vertex") == "1":
                # Wrap in UserObject only if we have a link to inject
                # (tooltip-only nodes: drawpyo handles via UserObject already)
                link = None
                for _id, attrs in _post_process_xml._link_registry.items():
                    if _id == drawpyo_id:
                        link = attrs.get("link")
                        link_attrs = attrs
                        break

                if link:
                    idx = list(elem).index(child)
                    elem.remove(child)
                    user_obj = ET.Element("UserObject")
                    user_obj.set("label", child.get("value", ""))
                    user_obj.set("link", link)
                    user_obj.set("id", user_id)
                    if link_attrs.get("tooltip"):
                        user_obj.set("tooltip", link_attrs["tooltip"])
                    if "id" in child.attrib:
                        del child.attrib["id"]
                    if "value" in child.attrib:
                        del child.attrib["value"]
                    user_obj.append(child)
                    elem.insert(idx, user_obj)
                    child = user_obj
                    mxcell = child.find("mxCell")
                else:
                    child.set("id", user_id)
                    mxcell = child
            else:
                continue

            # Restore geometry from user's saved state
            if user_id in managed_state and mxcell is not None:
                saved = managed_state[user_id]
                geo = mxcell.find("mxGeometry")
                if geo is not None:
                    geo.set("x", str(saved["x"]))
                    geo.set("y", str(saved["y"]))
                    geo.set("width", str(saved["w"]))
                    geo.set("height", str(saved["h"]))
                # Restore style
                if saved.get("style") and mxcell is not None:
                    mxcell.set("style", saved["style"])

    # -- Pass 2: append user-only nodes verbatim ------------------------------
    root_elem = root.find(".//root")
    if root_elem is not None:
        for user_node in existing["user_nodes"]:
            root_elem.append(user_node)

    tree.write(xml_path, xml_declaration=True, encoding="UTF-8")


# Registry for link data — populated by generate_diagram before calling post-process
_post_process_xml._link_registry: dict[str, dict] = {}
```

**Step 4: Update `generate_diagram` to use new function name**

Find the call to `_inject_links` near the end of `generate_diagram` and replace:

Old:
```python
    if link_map:
        _inject_links(str(output_path), link_map)
```

New (temporary — will be replaced in Task 4):
```python
    if link_map:
        _post_process_xml._link_registry = link_map
        _post_process_xml(str(output_path), {str(obj.id): nid for nid, obj in obj_map.items()}, {"managed": {}, "user_nodes": []})
```

Note: `obj_map` maps `user_id → drawpyo_object`, so we invert it to `{str(drawpyo_obj.id): user_id}`.

**Step 5: Run tests — expect all pass**

```bash
cd ~/.claude/skills/drawio-skill && ~/.claude/skills/.venv/bin/python scripts/test_generate.py
```

Expected: Tests 1-11 pass. All tests passed.

**Step 6: Commit**

```bash
cd ~/.claude/skills/drawio-skill && git add scripts/generate.py scripts/test_generate.py && git commit -m "feat: refactor _inject_links → _post_process_xml with ID injection and position restore"
```

---

## Task 4: Wire `preserve_user_edits` into `generate_diagram`

**Files:**
- Modify: `~/.claude/skills/drawio-skill/scripts/generate.py` — `generate_diagram` signature and body

**Step 1: Update `generate_diagram` signature**

Find:
```python
def generate_diagram(
    graph: dict[str, Any],
    output_path: str | os.PathLike,
    shapes_path: str | Path | None = None,
    config_path: str | Path | None = None,
) -> str:
```

Replace with:
```python
def generate_diagram(
    graph: dict[str, Any],
    output_path: str | os.PathLike,
    preserve_user_edits: bool = True,
    shapes_path: str | Path | None = None,
    config_path: str | Path | None = None,
) -> str:
```

**Step 2: Add `_read_existing` call at the top of the function body**

After `output_path = Path(output_path).resolve()` and before `config = _load_config(config_path)`, add:

```python
    # Read existing user state for round-trip preservation
    existing = _read_existing(output_path) if preserve_user_edits else {"managed": {}, "user_nodes": []}
```

**Step 3: Replace the temporary post-process call at the bottom**

Remove:
```python
    if link_map:
        _post_process_xml._link_registry = link_map
        _post_process_xml(str(output_path), {str(obj.id): nid for nid, obj in obj_map.items()}, {"managed": {}, "user_nodes": []})
```

Replace with:
```python
    # Build inverted map: drawpyo numeric id → user string id
    drawpyo_to_user: dict[str, str] = {str(obj.id): nid for nid, obj in obj_map.items()}

    _post_process_xml._link_registry = link_map
    _post_process_xml(str(output_path), drawpyo_to_user, existing)
```

**Step 4: Run all existing tests — expect pass**

```bash
cd ~/.claude/skills/drawio-skill && ~/.claude/skills/.venv/bin/python scripts/test_generate.py
```

Expected: All tests pass.

**Step 5: Commit**

```bash
cd ~/.claude/skills/drawio-skill && git add scripts/generate.py && git commit -m "feat: wire preserve_user_edits into generate_diagram"
```

---

## Task 5: Integration tests (round-trip)

**Files:**
- Modify: `~/.claude/skills/drawio-skill/scripts/test_generate.py` (add Tests 12-14)

**Step 1: Add Test 12 — position round-trip**

```python
# ---------------------------------------------------------------------------
# Test 12: Round-trip — user positions survive regeneration
# ---------------------------------------------------------------------------
print("Test 12: Round-trip position preservation ... ", end="")

graph_rt = {
    "nodes": [
        {"id": "ccxt", "label": "CCXT", "type": "process_periodic", "x": 100, "y": 100},
        {"id": "s3",   "label": "S3",   "type": "s3_minio",          "x": 350, "y": 100},
    ],
    "edges": [{"from": "ccxt", "to": "s3", "label": "raw"}],
}

with tempfile.TemporaryDirectory() as tmpdir:
    path = os.path.join(tmpdir, "rt.drawio")

    # First generation
    generate_diagram(graph_rt, path)

    # Simulate user moves s3 to (700, 400)
    tree = ET.parse(path)
    for cell in tree.findall('.//*[@id="s3"]'):
        geo = cell.find("mxGeometry")
        if geo is not None:
            geo.set("x", "700"); geo.set("y", "400")
    tree.write(path, xml_declaration=True, encoding="UTF-8")

    # Regenerate — preserve_user_edits=True (default)
    generate_diagram(graph_rt, path)

    tree2 = ET.parse(path)
    s3_cell = tree2.find('.//*[@id="s3"]')
    assert s3_cell is not None, "s3 not found after regen"
    geo = s3_cell.find("mxGeometry")
    if geo is None:
        # Check inside UserObject
        for uo in tree2.findall('.//UserObject[@id="s3"]'):
            geo = uo.find('.//mxGeometry')
    assert geo is not None, "mxGeometry not found for s3"
    assert int(float(geo.get("x"))) == 700, f"x not preserved: {geo.get('x')}"
    assert int(float(geo.get("y"))) == 400, f"y not preserved: {geo.get('y')}"

print("OK")
```

**Step 2: Add Test 13 — user-only node survival**

```python
# ---------------------------------------------------------------------------
# Test 13: User-only node (draw.io Desktop ID) survives regeneration
# ---------------------------------------------------------------------------
print("Test 13: User-only node preserved ... ", end="")

graph_uo = {
    "nodes": [{"id": "svc", "label": "Service", "type": "rectangle"}],
    "edges": [],
}

with tempfile.TemporaryDirectory() as tmpdir:
    path = os.path.join(tmpdir, "uo.drawio")
    generate_diagram(graph_uo, path)

    # Inject a user-only node (draw.io Desktop style ID)
    tree = ET.parse(path)
    root_el = tree.find(".//root")
    user_cell = ET.SubElement(root_el, "mxCell")
    user_cell.set("id", "6MHS348oe3dsvKXpeqjV-9999")
    user_cell.set("value", "My Annotation")
    user_cell.set("style", "text;html=1;")
    user_cell.set("vertex", "1")
    user_cell.set("parent", "1")
    geo = ET.SubElement(user_cell, "mxGeometry")
    geo.set("x", "900"); geo.set("y", "50"); geo.set("width", "150"); geo.set("height", "40")
    geo.set("as", "geometry")
    tree.write(path, xml_declaration=True, encoding="UTF-8")

    # Regenerate
    generate_diagram(graph_uo, path)

    content = open(path).read()
    assert "My Annotation" in content, "User-only node not preserved after regen"

print("OK")
```

**Step 3: Add Test 14 — `preserve_user_edits=False` resets positions**

```python
# ---------------------------------------------------------------------------
# Test 14: preserve_user_edits=False resets to graph dict positions
# ---------------------------------------------------------------------------
print("Test 14: preserve_user_edits=False resets layout ... ", end="")

graph_reset = {
    "nodes": [
        {"id": "node_a", "label": "A", "type": "rectangle", "x": 100, "y": 100},
    ],
    "edges": [],
}

with tempfile.TemporaryDirectory() as tmpdir:
    path = os.path.join(tmpdir, "reset.drawio")
    generate_diagram(graph_reset, path)

    # Simulate user moves node_a
    tree = ET.parse(path)
    for cell in tree.findall('.//*[@id="node_a"]'):
        geo = cell.find("mxGeometry")
        if geo is not None:
            geo.set("x", "999"); geo.set("y", "999")
    tree.write(path, xml_declaration=True, encoding="UTF-8")

    # Regenerate with preserve_user_edits=False
    generate_diagram(graph_reset, path, preserve_user_edits=False)

    tree2 = ET.parse(path)
    cell = tree2.find('.//*[@id="node_a"]')
    if cell is None:
        for uo in tree2.findall('.//UserObject[@id="node_a"]'):
            cell = uo.find('.//mxCell')
            break
    assert cell is not None
    geo = cell.find("mxGeometry") if cell.tag == "mxCell" else cell.find('.//mxGeometry')
    assert int(float(geo.get("x"))) == 100, f"x should be reset to 100, got {geo.get('x')}"
    assert int(float(geo.get("y"))) == 100, f"y should be reset to 100, got {geo.get('y')}"

print("OK")
```

**Step 4: Run all tests — expect pass**

```bash
cd ~/.claude/skills/drawio-skill && ~/.claude/skills/.venv/bin/python scripts/test_generate.py
```

Expected: Tests 1-14 all pass.

**Step 5: Commit**

```bash
cd ~/.claude/skills/drawio-skill && git add scripts/test_generate.py && git commit -m "test: add round-trip integration tests (T12-T14)"
```

---

## Final Verification

```bash
# All 14 tests pass
cd ~/.claude/skills/drawio-skill && ~/.claude/skills/.venv/bin/python scripts/test_generate.py

# Manual integration test: regenerate the existing CRO diagram
# (if architecture_overview.drawio is open in draw.io Desktop, check it loads correctly after)
~/.claude/skills/.venv/bin/python -c "
import sys, os
sys.path.insert(0, os.path.expanduser('~/.claude/skills/drawio-skill/scripts'))
from generate import generate_diagram
print('generate_diagram imported OK, preserve_user_edits param present')
import inspect
sig = inspect.signature(generate_diagram)
assert 'preserve_user_edits' in sig.parameters
print('preserve_user_edits parameter: OK')
"
```
