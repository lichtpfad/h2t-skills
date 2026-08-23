#!/usr/bin/env python3
"""Core diagram generator for drawio-skill.

Takes a graph dict + TOML shape library + YAML config and produces a .drawio
file via drawpyo.

Usage:
    from generate import generate_diagram
    path = generate_diagram(graph, "output.drawio")
"""

from __future__ import annotations

import copy
import os
import re
import tomllib
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import drawpyo
import yaml
from drawpyo.diagram.edges import Edge
from drawpyo.diagram.objects import Object

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SKILL_DIR = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = SKILL_DIR / "config" / "defaults.yaml"
DEFAULT_SHAPES = SKILL_DIR / "config" / "shapes" / "general.toml"

# Map node type -> edge color convention key
TYPE_TO_CONVENTION: dict[str, str] = {
    "s3_minio": "storage_s3",
    "timescaledb": "storage_tsdb",
    "clickhouse": "storage_click",
    "redis": "storage_redis",
    "external_source": "external",
    "logical_view": "logical",
}

# Edge style -> drawpyo pattern name
STYLE_TO_PATTERN: dict[str, str] = {
    "solid": "solid",
    "dashed": "dashed_medium",
    "dotted": "dotted_medium",
}

# Routing name -> drawpyo waypoints name
ROUTING_TO_WAYPOINTS: dict[str, str] = {
    "orthogonal": "orthogonal",
    "straight": "straight",
    "curved": "curved",
    "entity_relation": "entity_relation",
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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
    # 20+ alphanum chars = draw.io Desktop generated.
    # Anchored at start only (no $): draw.io IDs may contain hyphens after the
    # long prefix (e.g. "6MHS348oe3dsvKXpeqjV-42"), so we match on prefix length.
    if re.match(r'^[A-Za-z0-9]{20,}', cell_id):
        return False
    return True


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
            # Note: mxCell children of UserObject have no id attribute (id was moved
            # to UserObject by _post_process_xml). The empty-id guard below skips them.
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
            # User-only node — deepcopy so caller can safely insert into a new tree
            # without mutating the parsed source tree or risking re-use issues.
            if elem.tag == "UserObject":
                user_nodes.append(copy.deepcopy(elem))
            else:
                user_nodes.append(copy.deepcopy(mxcell))

    return {"managed": managed, "user_nodes": user_nodes}


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge *override* into a copy of *base*."""
    result = copy.deepcopy(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def _load_yaml(path: str | Path) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    with open(p) as f:
        return yaml.safe_load(f) or {}


def _load_toml(path: str | Path) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    with open(p, "rb") as f:
        return tomllib.load(f)


def _load_config(config_path: str | Path | None) -> dict:
    """Load defaults.yaml, then merge project config on top."""
    base = _load_yaml(DEFAULT_CONFIG)
    if config_path:
        project = _load_yaml(config_path)
        base = _deep_merge(base, project)
    return base


def _load_shapes(shapes_path: str | Path | None) -> dict:
    """Load general.toml, then merge project shapes on top."""
    base = _load_toml(DEFAULT_SHAPES)
    if shapes_path:
        project = _load_toml(shapes_path)
        base = _deep_merge(base, project)
    return base


# Style attributes that drawpyo Object supports as properties
_OBJ_STYLE_PROPS = {
    "fillColor", "strokeColor", "dashed", "rounded",
    "shadow", "opacity", "glass", "comic", "sketch",
}


def _apply_shape_to_object(obj: Object, shape_def: dict, extra_base: str = "") -> None:
    """Apply TOML shape definition to a drawpyo Object by setting properties.

    This avoids apply_style_string which can fail on read-only properties
    like 'container'.
    """
    base = shape_def.get("baseStyle", "")
    if extra_base:
        base = extra_base + base
    # Ensure whiteSpace=wrap and html=1 are always present in the style
    if "whiteSpace=wrap" not in base:
        base = base.rstrip(";") + ";whiteSpace=wrap;html=1" if base else "whiteSpace=wrap;html=1"
    obj.baseStyle = base

    for key in _OBJ_STYLE_PROPS:
        if key in shape_def:
            setattr(obj, key, shape_def[key])

    # fontColor lives on TextFormat, not Object
    if "fontColor" in shape_def:
        obj.text_format.fontColor = shape_def["fontColor"]


def _resolve_edge_color(
    edge_def: dict,
    target_type: str | None,
    shapes: dict,
) -> str | None:
    """Resolve edge color: explicit > auto from target type > default."""
    explicit = edge_def.get("color")
    if explicit:
        return explicit

    edge_colors = shapes.get("_edges", {})
    if not edge_colors or not target_type:
        return edge_colors.get("process_internal")

    convention = TYPE_TO_CONVENTION.get(target_type)
    if convention and convention in edge_colors:
        return edge_colors[convention]

    return edge_colors.get("process_internal")


# ---------------------------------------------------------------------------
# Post-processing: inject IDs, restore user edits, append user-only nodes
# ---------------------------------------------------------------------------


def _post_process_xml(
    xml_path: str,
    obj_id_map: dict[str, str],
    existing: dict,
    link_map: dict[str, dict],
) -> None:
    """Post-process drawpyo XML: inject user IDs, restore positions/styles, append user nodes.

    Args:
        xml_path:    Path to the .drawio file written by drawpyo.
        obj_id_map:  {drawpyo_python_id_str: user_string_id} for all managed nodes.
        existing:    Output of _read_existing() — prior user state to restore.
        link_map:    {drawpyo_python_id_str: {"link": ..., "tooltip": ...}} for nodes with links.
    """
    # Skip parse-write cycle entirely when there is nothing to inject or append.
    # Note: obj_id_map empty but user_nodes non-empty still needs the append pass.
    if not obj_id_map and not existing["user_nodes"]:
        return

    try:
        tree = ET.parse(xml_path)
    except ET.ParseError:
        return  # leave file as-is; better than crashing after file.write()
    root = tree.getroot()

    managed_state = existing["managed"]

    # Pass 1: collect cells to process (avoids mutation during iter())
    # Only process mxCell/UserObject — skip <diagram>, <mxGraphModel> etc.
    # whose numeric ids could accidentally match obj_id_map entries.
    to_process: list[tuple] = []  # (parent_elem, child, drawpyo_id)
    for parent_elem in root.iter():
        for child in list(parent_elem):
            if child.tag not in ("mxCell", "UserObject"):
                continue
            drawpyo_id = child.get("id", "")
            if not drawpyo_id or drawpyo_id in ("0", "1"):
                continue
            if drawpyo_id in obj_id_map:
                to_process.append((parent_elem, child, drawpyo_id))

    # Pass 2: mutate — inject IDs, restore positions/styles, handle link wrapping
    for parent_elem, child, drawpyo_id in to_process:
        user_id = obj_id_map[drawpyo_id]
        link_attrs = link_map.get(drawpyo_id, {})
        link = link_attrs.get("link")
        tooltip = link_attrs.get("tooltip")

        mxcell: ET.Element | None = None

        if child.tag == "UserObject":
            child.set("id", user_id)
            if link:
                child.set("link", link)
            mxcell = child.find("mxCell")
        elif child.tag == "mxCell" and child.get("vertex") == "1":
            if link:
                idx = list(parent_elem).index(child)
                parent_elem.remove(child)
                user_obj = ET.Element("UserObject")
                user_obj.set("label", child.get("value", ""))
                user_obj.set("link", link)
                user_obj.set("id", user_id)
                if tooltip:
                    user_obj.set("tooltip", tooltip)
                child.attrib.pop("id", None)
                child.attrib.pop("value", None)
                user_obj.append(child)
                parent_elem.insert(idx, user_obj)
                mxcell = child
            else:
                child.set("id", user_id)
                mxcell = child
        else:
            continue

        # Restore geometry and style from user's saved state
        if user_id in managed_state and mxcell is not None:
            saved = managed_state[user_id]
            geo = mxcell.find("mxGeometry")
            if geo is not None:
                geo.set("x", str(saved["x"]))
                geo.set("y", str(saved["y"]))
                geo.set("width", str(saved["w"]))
                geo.set("height", str(saved["h"]))
            if saved.get("style"):
                mxcell.set("style", saved["style"])

        # Update all references from drawpyo_id → user_id:
        # - parent= (container membership / swimlane children)
        # - source= / target= (edge endpoints)
        for elem in root.iter("mxCell"):
            if elem.get("parent") == drawpyo_id:
                elem.set("parent", user_id)
            if elem.get("source") == drawpyo_id:
                elem.set("source", user_id)
            if elem.get("target") == drawpyo_id:
                elem.set("target", user_id)

    # Append user-only nodes verbatim
    root_elem = root.find(".//root")
    if root_elem is not None:
        for user_node in existing["user_nodes"]:
            root_elem.append(user_node)

    tree.write(xml_path, xml_declaration=True, encoding="UTF-8")


# ---------------------------------------------------------------------------
# Main generator
# ---------------------------------------------------------------------------


def generate_diagram(
    graph: dict[str, Any],
    output_path: str | os.PathLike,
    preserve_user_edits: bool = True,
    shapes_path: str | Path | None = None,
    config_path: str | Path | None = None,
) -> str:
    """Generate a .drawio file from a graph description.

    Args:
        graph: Dict with "nodes", "edges", and optionally "containers".
        output_path: Where to write the .drawio file.
        preserve_user_edits: If True (default), read existing file and restore
            user-moved positions, custom styles, and user-added nodes.
            Set to False to perform a full overwrite (reset layout).
        shapes_path: Optional path to project .drawio-shapes.toml override.
        config_path: Optional path to project .drawio-skill.yaml override.

    Returns:
        Absolute path to the generated .drawio file.
    """
    output_path = Path(output_path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Read existing user state before drawpyo overwrites the file
    existing = _read_existing(output_path) if preserve_user_edits else {"managed": {}, "user_nodes": []}

    config = _load_config(config_path)
    shapes = _load_shapes(shapes_path)

    layout = config.get("layout", {})
    node_spacing = layout.get("node_spacing", 200)
    level_spacing = layout.get("level_spacing", 120)
    max_cols = 4

    # -- Create file and page ------------------------------------------------
    file = drawpyo.File()
    file.file_path = str(output_path.parent)
    file.file_name = output_path.name
    page = drawpyo.Page(file=file, name="Page-1")

    # -- Auto-grid state -----------------------------------------------------
    grid_x, grid_y = 100, 100
    grid_col = 0

    def _next_grid_pos() -> tuple[int, int]:
        nonlocal grid_x, grid_y, grid_col
        pos = (grid_x, grid_y)
        grid_col += 1
        if grid_col >= max_cols:
            grid_col = 0
            grid_x = 100
            grid_y += level_spacing
        else:
            grid_x += node_spacing
        return pos

    # -- Build containers first ----------------------------------------------
    obj_map: dict[str, Object] = {}  # id -> drawpyo Object
    node_type_map: dict[str, str] = {}  # id -> type string
    child_to_container: dict[str, str] = {}  # node_id -> container_id

    containers = graph.get("containers", [])
    for cdef in containers:
        cid = cdef["id"]
        ctype = cdef.get("type", "swimlane")
        shape_def = shapes.get(ctype, shapes.get("swimlane", {}))

        cx = cdef.get("x", 0)
        cy = cdef.get("y", 0)
        cw = cdef.get("width", 400)
        ch = cdef.get("height", 300)

        container_obj = Object(
            page=page,
            value=cdef.get("label", cid),
            position=(cx, cy),
            width=cw,
            height=ch,
        )
        _apply_shape_to_object(
            container_obj, shape_def,
            extra_base="container=1;collapsible=0;",
        )
        obj_map[cid] = container_obj

        for child_id in cdef.get("children", []):
            child_to_container[child_id] = cid

    # -- Build link map for post-processing ----------------------------------
    link_map: dict[str, dict] = {}

    # -- Build nodes ---------------------------------------------------------
    nodes = graph.get("nodes", [])
    for ndef in nodes:
        nid = ndef["id"]
        ntype = ndef.get("type", "rectangle")
        node_type_map[nid] = ntype

        shape_def = shapes.get(ntype, shapes.get("rectangle", {}))

        # Determine position
        x = ndef.get("x")
        y = ndef.get("y")
        if x is None or y is None:
            x, y = _next_grid_pos()

        w = ndef.get("width", shape_def.get("width", 120))
        h = ndef.get("height", shape_def.get("height", 60))

        # If inside a container, position is relative to parent
        parent_container = None
        if nid in child_to_container:
            parent_container = obj_map.get(child_to_container[nid])

        tooltip = ndef.get("tooltip")
        link = ndef.get("link")

        obj = Object(
            page=page,
            value=ndef.get("label", nid),
            position=(x, y),
            width=w,
            height=h,
            tooltip=tooltip,
        )
        _apply_shape_to_object(obj, shape_def)

        # Set parent for container membership
        if parent_container is not None:
            obj.parent = parent_container

        obj_map[nid] = obj

        # Track links for post-processing
        if link:
            link_map[str(obj.id)] = {"link": link, "tooltip": tooltip}

    # -- Build edges ---------------------------------------------------------
    edge_defaults = shapes.get("_edge_defaults", {})
    edges = graph.get("edges", [])

    for edef in edges:
        src_id = edef["from"]
        tgt_id = edef["to"]

        src_obj = obj_map.get(src_id)
        tgt_obj = obj_map.get(tgt_id)
        if src_obj is None or tgt_obj is None:
            continue  # skip broken refs

        # Resolve color
        target_type = node_type_map.get(tgt_id)
        color = _resolve_edge_color(edef, target_type, shapes)

        # Pattern
        style_name = edef.get("style", "solid")
        pattern = STYLE_TO_PATTERN.get(style_name, "solid")

        # Waypoints / routing
        routing = edef.get("routing", edge_defaults.get("routing", "orthogonal"))
        waypoints = ROUTING_TO_WAYPOINTS.get(routing, "orthogonal")

        # Arrow
        arrow = edef.get("arrow", edge_defaults.get("arrow", "classic"))

        # Build edge
        label = edef.get("label", "")
        bidirectional = edef.get("bidirectional", False)

        edge_kwargs: dict[str, Any] = {
            "page": page,
            "source": src_obj,
            "target": tgt_obj,
            "label": label,
            "waypoints": waypoints,
            "pattern": pattern,
            "line_end_target": arrow,
        }

        if bidirectional:
            edge_kwargs["line_end_source"] = arrow

        edge_obj = Edge(**edge_kwargs)

        # Set strokeColor/strokeWidth after construction — drawpyo Edge
        # ignores these in kwargs but accepts them as property assignments.
        if color:
            edge_obj.strokeColor = color

        stroke_w = edge_defaults.get("strokeWidth")
        if stroke_w is not None:
            edge_obj.strokeWidth = stroke_w

        # Edge tooltip via post-processing isn't needed often, but note it
        # drawpyo Edge also supports tooltip natively
        edge_tooltip = edef.get("tooltip")
        if edge_tooltip:
            edge_obj.tooltip = edge_tooltip

    # -- Write file ----------------------------------------------------------
    file.write()

    # -- Post-process: inject IDs, restore user edits, append user-only nodes --
    drawpyo_to_user: dict[str, str] = {str(obj.id): nid for nid, obj in obj_map.items()}
    _post_process_xml(str(output_path), drawpyo_to_user, existing, link_map)

    return str(output_path)
