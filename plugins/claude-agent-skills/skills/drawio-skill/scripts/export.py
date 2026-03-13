#!/usr/bin/env python3
"""Export draw.io diagrams to PNG/SVG/PDF via draw.io Desktop CLI.

Usage:
    from export import export_diagram
    path = export_diagram("input.drawio", fmt="png")
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

import yaml

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SKILL_DIR = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = SKILL_DIR / "config" / "defaults.yaml"

SUPPORTED_FORMATS = {"png", "svg", "pdf"}


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------


def _load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    with open(path, "r") as f:
        return yaml.safe_load(f) or {}


def _load_config(config_path: str | Path | None) -> dict:
    """Load defaults.yaml, then merge project config on top."""
    base = _load_yaml(DEFAULT_CONFIG)
    if config_path:
        project = _load_yaml(Path(config_path))
        for key, value in project.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                base[key].update(value)
            else:
                base[key] = value
    return base


# ---------------------------------------------------------------------------
# Main export function
# ---------------------------------------------------------------------------


def export_diagram(
    drawio_path: str | os.PathLike,
    fmt: str = "png",
    output_path: str | os.PathLike | None = None,
    config_path: str | Path | None = None,
    page_index: int | None = None,
    all_pages: bool = False,
) -> str:
    """Export a .drawio file to PNG, SVG, or PDF using draw.io Desktop CLI.

    Args:
        drawio_path: Path to the source .drawio file.
        fmt: Output format — "png", "svg", or "pdf".
        output_path: Explicit output file path. If None, auto-generates
            as ``{name}.drawio.{fmt}`` next to the source file.
        config_path: Optional project config (.drawio-skill.yaml) override.
        page_index: Export a specific page (0-based). Mutually exclusive
            with all_pages.
        all_pages: Export all pages. Mutually exclusive with page_index.

    Returns:
        Absolute path to the exported file.

    Raises:
        FileNotFoundError: If source file or draw.io CLI not found.
        ValueError: If format is unsupported or args conflict.
        RuntimeError: If export process fails or output not created.
    """
    # -- Validate format -----------------------------------------------------
    fmt = fmt.lower()
    if fmt not in SUPPORTED_FORMATS:
        raise ValueError(
            f"Unsupported format '{fmt}'. Must be one of: {', '.join(sorted(SUPPORTED_FORMATS))}"
        )

    if page_index is not None and all_pages:
        raise ValueError("Cannot specify both page_index and all_pages")

    # -- Resolve paths -------------------------------------------------------
    source = Path(drawio_path).resolve()
    if not source.exists():
        raise FileNotFoundError(f"Source file not found: {source}")

    config = _load_config(config_path)
    export_config = config.get("export", {})

    cli_path = Path(export_config.get("drawio_path", "/Applications/draw.io.app/Contents/MacOS/draw.io"))
    if not cli_path.exists():
        raise FileNotFoundError(f"draw.io CLI not found at: {cli_path}")

    # -- Determine output path -----------------------------------------------
    if output_path is not None:
        out = Path(output_path).resolve()
    else:
        # {name}.drawio.{fmt} next to the source
        stem = source.stem  # e.g. "test" from "test.drawio"
        out = source.parent / f"{stem}.drawio.{fmt}"

    out.parent.mkdir(parents=True, exist_ok=True)

    # -- Build CLI command ---------------------------------------------------
    cmd: list[str] = [
        str(cli_path),
        "--export",
        "--format", fmt,
        "--output", str(out),
    ]

    border = export_config.get("border", 10)
    cmd.extend(["--border", str(border)])

    scale = export_config.get("scale", 1)
    if scale != 1:
        cmd.extend(["--scale", str(scale)])

    transparent = export_config.get("transparent", False)
    if transparent and fmt == "png":
        cmd.append("--transparent")

    embed_diagram = config.get("embed_diagram", True)
    if embed_diagram and fmt in ("png", "svg"):
        cmd.append("--embed-diagram")

    if all_pages:
        cmd.append("--all-pages")
    elif page_index is not None:
        cmd.extend(["--page-index", str(page_index)])

    # Source file goes last
    cmd.append(str(source))

    # -- Run -----------------------------------------------------------------
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(
            f"draw.io export timed out after 30s. Command: {' '.join(cmd)}"
        )

    if result.returncode != 0:
        stderr = result.stderr.strip() if result.stderr else "(no stderr)"
        raise RuntimeError(
            f"draw.io export failed (rc={result.returncode}): {stderr}"
        )

    # -- Verify output -------------------------------------------------------
    if not out.exists():
        raise RuntimeError(
            f"Export completed but output file not found: {out}"
        )

    return str(out)
