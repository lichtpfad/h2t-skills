#!/usr/bin/env python3
"""Test for export.py."""
import sys, os, tempfile
sys.path.insert(0, os.path.expanduser("~/.claude/skills/drawio-skill/scripts"))
from generate import generate_diagram
from export import export_diagram

graph = {
    "nodes": [
        {"id": "a", "label": "Test Node", "type": "rounded_rect"},
    ],
    "edges": [],
}

with tempfile.TemporaryDirectory() as tmpdir:
    drawio_path = os.path.join(tmpdir, "test.drawio")
    generate_diagram(graph, drawio_path)

    png_path = export_diagram(drawio_path, fmt="png")
    assert os.path.exists(png_path), f"PNG not created at {png_path}"
    assert os.path.getsize(png_path) > 100, "PNG too small"
    print(f"OK — exported PNG: {os.path.getsize(png_path)} bytes at {png_path}")
