#!/usr/bin/env python3
"""Tests for generate.py.

Converted from a smoke script (#396). The 16 blocks below ran top-level under
`python test_generate.py` and passed, but defined no test function, so pytest
collected nothing and exited 5 — the directory looked covered and was not.
"""
import os
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from generate import (
    _is_user_managed,
    _post_process_xml,
    _read_existing,
    generate_diagram,
)


def test_1_basic_nodes_edges():
    """Test 1: Basic nodes + edges."""
    graph = {
        "nodes": [
            {"id": "a", "label": "Service A", "type": "rounded_rect"},
            {"id": "b", "label": "Database", "type": "cylinder"},
            {"id": "c", "label": "Gateway", "type": "diamond"},
        ],
        "edges": [
            {"from": "a", "to": "b", "label": "writes"},
            {"from": "c", "to": "a", "label": "routes", "style": "dashed"},
        ],
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        output = os.path.join(tmpdir, "test.drawio")
        generate_diagram(graph, output)
        assert os.path.exists(output), "File not created"
        content = open(output).read()
        assert "<mxGraphModel" in content, "Not valid drawio XML"
        assert "Service A" in content, "Node label 'Service A' missing"
        assert "Database" in content, "Node label 'Database' missing"
        assert "writes" in content, "Edge label 'writes' missing"


def test_2_links_and_tooltips():
    """Test 2: Links and tooltips."""
    graph2 = {
        "nodes": [
            {
                "id": "x",
                "label": "Node X",
                "type": "rectangle",
                "link": "docs/test.md",
                "tooltip": "Test tooltip",
            },
            {
                "id": "y",
                "label": "Node Y",
                "type": "ellipse",
                "tooltip": "Only tooltip",
            },
        ],
        "edges": [],
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        output = os.path.join(tmpdir, "test_links.drawio")
        generate_diagram(graph2, output)
        content = open(output).read()
        assert "docs/test.md" in content, "Link not found in XML"
        assert "Test tooltip" in content, "Tooltip not found in XML"
        assert "Only tooltip" in content, "Tooltip-only node missing"


def test_3_containers():
    """Test 3: Containers."""
    graph3 = {
        "containers": [
            {
                "id": "group1",
                "label": "Backend Services",
                "type": "swimlane",
                "children": ["svc1", "svc2"],
                "x": 50,
                "y": 50,
                "width": 500,
                "height": 300,
            },
        ],
        "nodes": [
            {"id": "svc1", "label": "API", "type": "rounded_rect", "x": 30, "y": 60},
            {"id": "svc2", "label": "Worker", "type": "rounded_rect", "x": 200, "y": 60},
            {"id": "db", "label": "DB", "type": "cylinder", "x": 250, "y": 400},
        ],
        "edges": [
            {"from": "svc1", "to": "db", "label": "query"},
        ],
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        output = os.path.join(tmpdir, "test_containers.drawio")
        generate_diagram(graph3, output)
        content = open(output).read()
        assert "Backend Services" in content, "Container label missing"
        assert "API" in content, "Child node missing"
        assert "container=1" in content, "Container style missing"


def test_4_explicit_positions_vs_auto_grid():
    """Test 4: Explicit positions vs auto-grid."""
    graph4 = {
        "nodes": [
            {"id": f"n{i}", "label": f"Node {i}", "type": "rectangle"}
            for i in range(6)
        ],
        "edges": [],
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        output = os.path.join(tmpdir, "test_grid.drawio")
        generate_diagram(graph4, output)
        assert os.path.exists(output), "File not created"


def test_5_edge_with_bidirectional_tooltip():
    """Test 5: Edge with bidirectional + tooltip."""
    graph5 = {
        "nodes": [
            {"id": "p", "label": "Producer", "type": "rectangle"},
            {"id": "q", "label": "Queue", "type": "hexagon"},
        ],
        "edges": [
            {
                "from": "p",
                "to": "q",
                "label": "pub/sub",
                "bidirectional": True,
                "style": "dotted",
                "tooltip": "Async messaging",
            },
        ],
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        output = os.path.join(tmpdir, "test_bidir.drawio")
        generate_diagram(graph5, output)
        content = open(output).read()
        assert "pub/sub" in content, "Edge label missing"


def test_6_whitespace_wrap_and_html_1_in_node_styles():
    """Test 6: whiteSpace=wrap and html=1 in node styles."""
    graph6 = {
        "nodes": [
            {"id": "w1", "label": "Wrap Test", "type": "rectangle"},
            {"id": "w2", "label": "Wrap Test 2", "type": "rounded_rect"},
        ],
        "edges": [],
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        output = os.path.join(tmpdir, "test_whitespace.drawio")
        generate_diagram(graph6, output)
        content = open(output).read()
        assert "whiteSpace=wrap" in content, "whiteSpace=wrap missing from node styles"
        assert "html=1" in content, "html=1 missing from node styles"


def test_7_auto_grid_positions_are_correct():
    """Test 7: Auto-grid positions are correct."""
    graph7 = {
        "nodes": [
            {"id": f"g{i}", "label": f"Grid {i}", "type": "rectangle"}
            for i in range(6)
        ],
        "edges": [],
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        output = os.path.join(tmpdir, "test_grid_coords.drawio")
        generate_diagram(graph7, output)
        tree = ET.parse(output)
        root = tree.getroot()

        # Expected positions: 4 cols max, 200px h-step, 120px v-step, start (100,100)
        expected = [
            (100, 100), (300, 100), (500, 100), (700, 100),  # row 0
            (100, 220), (300, 220),                            # row 1
        ]

        # Collect mxGeometry x/y for cells that have our labels
        positions = []
        for cell in root.iter("mxCell"):
            val = cell.get("value", "")
            if val.startswith("Grid "):
                geom = cell.find("mxGeometry")
                if geom is None:
                    # Check parent UserObject
                    continue
                positions.append((int(float(geom.get("x", "0"))), int(float(geom.get("y", "0")))))

        # Also check inside UserObject wrappers
        for uo in root.iter("UserObject"):
            val = uo.get("label", "")
            if val.startswith("Grid "):
                cell = uo.find("mxCell")
                if cell is not None:
                    geom = cell.find("mxGeometry")
                    if geom is not None:
                        positions.append((int(float(geom.get("x", "0"))), int(float(geom.get("y", "0")))))

        assert len(positions) == 6, f"Expected 6 node positions, got {len(positions)}"
        for i, (ex, ey) in enumerate(expected):
            ax, ay = positions[i]
            assert (ax, ay) == (ex, ey), f"Node g{i}: expected ({ex},{ey}), got ({ax},{ay})"


def test_8_edge_color_auto_resolution_from_edges_table():
    """Test 8: Edge color auto-resolution from _edges table."""
    graph8 = {
        "nodes": [
            {"id": "src", "label": "Source", "type": "rectangle"},
            {"id": "ext", "label": "External", "type": "external_source"},
        ],
        "edges": [
            {"from": "src", "to": "ext", "label": "calls"},
        ],
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        output = os.path.join(tmpdir, "test_edge_color.drawio")
        generate_diagram(graph8, output)
        content = open(output).read()
        # external_source maps to "external" convention -> #999999 in general.toml
        assert "#999999" in content, "Auto-resolved edge color #999999 not found in XML"


def test_9_is_user_managed_id_classification():
    """Test 9: _is_user_managed ID classification."""
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
    # Boundary: 19-char alphanum → managed (threshold is 20+)
    assert _is_user_managed("AbCdEfGhIjKlMnOpQrS") is True


def test_10_read_existing_parse_positions_styles_and_user_only_nodes():
    """Test 10: _read_existing — parse positions, styles, and user-only nodes."""
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


def test_10b_read_existing_userobject_wrapped_managed_node_post_generation_shape():
    """Test 10b: _read_existing — UserObject-wrapped managed node (post-generation shape)."""
    # After _post_process_xml runs, skill nodes with links become UserObject wrappers.
    # _read_existing must correctly extract position from these.
    fixture_uo_xml = '''<?xml version="1.0" encoding="UTF-8"?>
    <mxGraphModel>
      <root>
        <mxCell id="0"/>
        <mxCell id="1" parent="0"/>
        <UserObject id="kill" label="KillSwitch" link="docs/adr/008.md" tooltip="NORMAL/DEGRADED/HALT">
          <mxCell style="rhombus;fillColor=#b85450;" vertex="1" parent="1">
            <mxGeometry x="800" y="150" width="120" height="80" as="geometry"/>
          </mxCell>
        </UserObject>
      </root>
    </mxGraphModel>'''

    with tempfile.TemporaryDirectory() as tmpdir:
        uo_path = os.path.join(tmpdir, "existing_uo.drawio")
        with open(uo_path, "w") as f:
            f.write(fixture_uo_xml)

        result = _read_existing(uo_path)

        assert "kill" in result["managed"], "UserObject-wrapped node 'kill' not found in managed"
        assert result["managed"]["kill"]["x"] == 800
        assert result["managed"]["kill"]["y"] == 150
        assert result["managed"]["kill"]["w"] == 120
        assert result["managed"]["kill"]["h"] == 80
        assert "rhombus" in result["managed"]["kill"]["style"]
        assert len(result["user_nodes"]) == 0, "kill should be managed, not user_nodes"


def test_11_post_process_xml_id_injection_position_restore_user_nodes():
    """Test 11: _post_process_xml — ID injection + position restore + user_nodes."""
    import xml.etree.ElementTree as ET_t11

    # Minimal drawpyo-style XML: numeric ID, drawpyo-generated position
    fixture_xml_11 = '''<?xml version="1.0" encoding="UTF-8"?>
    <mxGraphModel>
      <root>
        <mxCell id="0"/>
        <mxCell id="1" parent="0"/>
        <mxCell id="4399820496" value="CCXT" style="rounded=1;" vertex="1" parent="1">
          <mxGeometry x="100" y="100" width="120" height="60" as="geometry"/>
        </mxCell>
      </root>
    </mxGraphModel>'''

    with tempfile.TemporaryDirectory() as tmpdir:
        path_11 = os.path.join(tmpdir, "test_post.drawio")
        with open(path_11, "w") as f:
            f.write(fixture_xml_11)

        # obj_id_map: drawpyo numeric id → user string id
        obj_id_map = {"4399820496": "ccxt"}
        # existing: user moved ccxt to (500, 300), changed style
        existing = {
            "managed": {"ccxt": {"x": 500, "y": 300, "w": 140, "h": 70, "style": "ellipse;"}},
            "user_nodes": [],
        }

        _post_process_xml(path_11, obj_id_map, existing, link_map={})

        tree_11 = ET_t11.parse(path_11)
        root_11 = tree_11.getroot()

        # ID should be replaced: find cell with id="ccxt"
        # Could be plain mxCell or wrapped in UserObject
        cell_11 = root_11.find('.//*[@id="ccxt"]')
        assert cell_11 is not None, "User ID 'ccxt' not injected"

        # Find mxGeometry — may be direct child or inside UserObject
        geo_11 = cell_11.find(".//mxGeometry") or cell_11.find("mxGeometry")
        if geo_11 is None and cell_11.tag == "mxCell":
            geo_11 = cell_11.find("mxGeometry")
        assert geo_11 is not None, "mxGeometry not found"

        assert int(float(geo_11.get("x"))) == 500, f"x not restored: {geo_11.get('x')}"
        assert int(float(geo_11.get("y"))) == 300, f"y not restored: {geo_11.get('y')}"
        assert int(float(geo_11.get("width"))) == 140
        assert int(float(geo_11.get("height"))) == 70

        # Style should be from user (ellipse) not drawpyo (rounded=1)
        mxcell_11 = cell_11 if cell_11.tag == "mxCell" else cell_11.find("mxCell")
        assert mxcell_11 is not None
        assert "ellipse" in mxcell_11.get("style", ""), f"User style not restored: {mxcell_11.get('style')}"


def test_12_round_trip_user_positions_survive_regeneration():
    """Test 12: Round-trip — user positions survive regeneration."""
    graph_rt = {
        "nodes": [
            {"id": "ccxt", "label": "CCXT", "type": "process_periodic", "x": 100, "y": 100},
            {"id": "s3",   "label": "S3",   "type": "s3_minio",          "x": 350, "y": 100},
        ],
        "edges": [{"from": "ccxt", "to": "s3", "label": "raw"}],
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "rt.drawio")

        # First generation — creates the file
        generate_diagram(graph_rt, path)

        # Simulate user moves s3 to (700, 400) in draw.io Desktop
        tree = ET.parse(path)
        for cell in tree.findall('.//*[@id="s3"]'):
            geo = cell.find("mxGeometry")
            if geo is not None:
                geo.set("x", "700"); geo.set("y", "400")
        tree.write(path, xml_declaration=True, encoding="UTF-8")

        # Regenerate — preserve_user_edits=True (default)
        generate_diagram(graph_rt, path)

        # Verify s3 position preserved
        tree2 = ET.parse(path)
        s3_cell = tree2.find('.//*[@id="s3"]')
        assert s3_cell is not None, "s3 not found after regen"
        geo = s3_cell.find("mxGeometry")
        if geo is None:
            geo = s3_cell.find(".//mxGeometry")
        assert geo is not None, "mxGeometry not found for s3"
        assert int(float(geo.get("x"))) == 700, f"x not preserved: {geo.get('x')}"
        assert int(float(geo.get("y"))) == 400, f"y not preserved: {geo.get('y')}"


def test_13_user_only_node_draw_io_desktop_id_survives_regeneration():
    """Test 13: User-only node (draw.io Desktop ID) survives regeneration."""
    graph_uo = {
        "nodes": [{"id": "svc", "label": "Service", "type": "rectangle"}],
        "edges": [],
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "uo.drawio")
        generate_diagram(graph_uo, path)

        # Inject a user-only node (draw.io Desktop style ID — 20+ alphanum chars)
        tree = ET.parse(path)
        root_el = tree.find(".//root")
        user_cell = ET.SubElement(root_el, "mxCell")
        user_cell.set("id", "6MHS348oe3dsvKXpeqjV-9999")
        user_cell.set("value", "My Annotation")
        user_cell.set("style", "text;html=1;")
        user_cell.set("vertex", "1")
        user_cell.set("parent", "1")
        geo = ET.SubElement(user_cell, "mxGeometry")
        geo.set("x", "900"); geo.set("y", "50")
        geo.set("width", "150"); geo.set("height", "40")
        geo.set("as", "geometry")
        tree.write(path, xml_declaration=True, encoding="UTF-8")

        # Regenerate — user-only node should survive
        generate_diagram(graph_uo, path)

        content = open(path).read()
        assert "My Annotation" in content, "User-only node not preserved after regen"
        assert "6MHS348oe3dsvKXpeqjV-9999" in content, "User-only node ID not preserved"
        assert 'x="900"' in content, "User-only node geometry not preserved"


def test_14_preserve_user_edits_false_resets_to_graph_dict_positions():
    """Test 14: preserve_user_edits=False resets to graph dict positions."""
    graph_reset = {
        "nodes": [
            {"id": "node_a", "label": "A", "type": "rectangle", "x": 100, "y": 100},
        ],
        "edges": [],
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "reset.drawio")
        generate_diagram(graph_reset, path)

        # Simulate user moves node_a far away
        tree = ET.parse(path)
        for cell in tree.findall('.//*[@id="node_a"]'):
            geo = cell.find("mxGeometry")
            if geo is not None:
                geo.set("x", "999"); geo.set("y", "999")
        tree.write(path, xml_declaration=True, encoding="UTF-8")

        # Regenerate with preserve_user_edits=False — should reset
        generate_diagram(graph_reset, path, preserve_user_edits=False)

        tree2 = ET.parse(path)
        # Find node_a — could be mxCell or inside UserObject
        cell = tree2.find('.//*[@id="node_a"]')
        assert cell is not None, "node_a not found"
        geo = cell.find("mxGeometry") or cell.find(".//mxGeometry")
        assert geo is not None, "mxGeometry not found"
        assert int(float(geo.get("x"))) == 100, f"x should be reset to 100, got {geo.get('x')}"
        assert int(float(geo.get("y"))) == 100, f"y should be reset to 100, got {geo.get('y')}"


def test_15_edge_source_target_references_updated_after_id_injection_bug_3():
    """Test 15: Edge source/target references updated after ID injection (Bug 3)."""
    graph_edges = {
        "nodes": [
            {"id": "src_node", "label": "Source",  "type": "rectangle", "x": 100, "y": 100},
            {"id": "tgt_node", "label": "Target",  "type": "rectangle", "x": 300, "y": 100},
            {"id": "mid_node", "label": "Middle",  "type": "rectangle", "x": 200, "y": 200},
        ],
        "edges": [
            {"from": "src_node", "to": "tgt_node", "label": "direct"},
            {"from": "src_node", "to": "mid_node", "label": "branch"},
            {"from": "mid_node", "to": "tgt_node", "label": "merge"},
        ],
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "edges.drawio")
        generate_diagram(graph_edges, path)

        tree = ET.parse(path)
        edges = [c for c in tree.findall('.//*[@edge="1"]')]
        assert len(edges) == 3, f"Expected 3 edges, got {len(edges)}"

        for edge in edges:
            src = edge.get("source", "")
            tgt = edge.get("target", "")
            # Neither endpoint should be a raw numeric drawpyo id
            assert not src.isdigit(), f"Edge source still numeric: {src}"
            assert not tgt.isdigit(), f"Edge target still numeric: {tgt}"
            # Both endpoints must resolve to known user IDs
            assert src in ("src_node", "tgt_node", "mid_node"), f"Unexpected source: {src}"
            assert tgt in ("src_node", "tgt_node", "mid_node"), f"Unexpected target: {tgt}"

        # Verify specific routing
        direct = next(e for e in edges if e.get("value") == "direct")
        assert direct.get("source") == "src_node", "direct edge source wrong"
        assert direct.get("target") == "tgt_node", "direct edge target wrong"

    print("\nAll tests passed.")
