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

(Implementation as shown in design doc)

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

(Implementation details in design doc)

---

## Task 4: Wire `preserve_user_edits` into `generate_diagram`

**Files:**
- Modify: `~/.claude/skills/drawio-skill/scripts/generate.py` — `generate_diagram` signature and body

(Implementation details in design doc)

---

## Task 5: Integration tests (round-trip)

**Files:**
- Modify: `~/.claude/skills/drawio-skill/scripts/test_generate.py` (add Tests 12-14)

(Test implementations in design doc)

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
