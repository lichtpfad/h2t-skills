#!/usr/bin/env python3
"""Test for export.py.

Converted from a smoke script (#396). It needs the draw.io Desktop CLI, which no CI
runner has, so it skips there — but it says so out loud. A test that skips quietly is
the same zero as a directory pytest never collected.
"""
import os
import tempfile
from pathlib import Path

import pytest

from conftest import REAL_HOME
from h2t_ops.tools.drawio.export import export_diagram
from h2t_ops.tools.drawio.generate import generate_diagram

# export.py:104 — the default, overridable through .drawio-skill.yaml
# The literal is what the control greps for; Path() would render it "\\Applications\\..."
# on Windows and the control would fail on the separator rather than on a stale path.
DRAWIO_CLI_LITERAL = "/Applications/draw.io.app/Contents/MacOS/draw.io"
DRAWIO_CLI = Path(DRAWIO_CLI_LITERAL)


def test_the_cli_path_this_test_probes_is_the_one_export_uses():
    """The control. If export.py's default moves, the skip below would silently become
    permanent and this file would report success by never running."""
    source = (Path(__file__).resolve().parents[3] / "h2t_ops" / "tools" / "drawio"
              / "export.py").read_text(encoding="utf-8")
    assert DRAWIO_CLI_LITERAL in source, (
        f"{DRAWIO_CLI_LITERAL} no longer appears in export.py — the skip condition is stale"
    )


@pytest.mark.skipif(not DRAWIO_CLI.exists(), reason=f"draw.io CLI absent at {DRAWIO_CLI}")
def test_export_produces_a_png(monkeypatch, tmp_path):
    # Electron hangs without its real profile under ~/Library, and no variable narrower
    # than HOME moves that profile, so this test alone gets the real HOME back (#548 R5).
    monkeypatch.setenv("HOME", str(REAL_HOME))
    # The package code must not follow it: drawio writes through store, which journals into
    # logs/ — with the real HOME that was the real ~/.h2t/logs/writes.jsonl (Task 18).
    monkeypatch.setenv("H2T_PATH_ROOT", str(tmp_path / "h2t"))
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
