"""Regression test for #143 — bump_plugin must not crash on Windows cp1252.

The success path of ``scripts/bump_plugin.py`` prints unicode glyphs (``✓``,
``→``). On Windows the default console codepage is often cp1252, which cannot
encode those characters, so ``print`` raised ``UnicodeEncodeError`` *after*
the file writes had already succeeded — producing a misleading exit 1.

This test reproduces a cp1252 stdout and asserts the script reports success
without raising. It is intentionally focused on the encoding behaviour and
does not exercise unrelated semver / marketplace logic.
"""

from __future__ import annotations

import importlib.util
import io
import json
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPT = _REPO_ROOT / "scripts" / "bump_plugin.py"


def _load_bump_plugin():
    """Load scripts/bump_plugin.py as a module (scripts/ is not a package)."""
    spec = importlib.util.spec_from_file_location("bump_plugin_under_test", _SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _seed_fake_repo(root: Path, plugin_name: str, old_ver: str) -> None:
    """Create a minimal marketplace + plugin layout for the bumper to target."""
    market_dir = root / ".claude-plugin"
    market_dir.mkdir(parents=True)
    plugin_dir = root / "plugins" / plugin_name / ".claude-plugin"
    plugin_dir.mkdir(parents=True)

    market = {
        "plugins": [
            {"name": plugin_name, "source": f"./plugins/{plugin_name}", "version": old_ver}
        ]
    }
    plugin = {"name": plugin_name, "version": old_ver}

    (market_dir / "marketplace.json").write_text(
        json.dumps(market, indent=2) + "\n", encoding="utf-8"
    )
    (plugin_dir / "plugin.json").write_text(
        json.dumps(plugin, indent=2) + "\n", encoding="utf-8"
    )


def test_success_output_survives_cp1252_stdout(tmp_path, monkeypatch):
    """Success path must print ``✓`` / ``→`` without UnicodeEncodeError.

    Mimics the real Windows console: ``sys.stdout`` is a cp1252-backed
    TextIOWrapper *before* the script runs, and the script's startup guard
    must reconfigure it to utf-8.
    """
    # cp1252 cannot encode ✓ or →; errors="strict" would make a regression loud.
    cp1252_buf = io.BytesIO()
    cp1252_stdout = io.TextIOWrapper(
        cp1252_buf, encoding="cp1252", errors="strict", newline="", write_through=True
    )
    cp1252_err_buf = io.BytesIO()
    cp1252_stderr = io.TextIOWrapper(
        cp1252_err_buf, encoding="cp1252", errors="strict", newline="", write_through=True
    )

    # Stdout/stderr must be cp1252 BEFORE the module loads, so its top-level
    # ``sys.stdout.reconfigure`` guard runs against the cp1252 stream.
    monkeypatch.setattr(sys, "stdout", cp1252_stdout)
    monkeypatch.setattr(sys, "stderr", cp1252_stderr)

    bump_plugin = _load_bump_plugin()

    # Sanity: the guard re-encoded the live stream to utf-8.
    assert cp1252_stdout.encoding.lower() == "utf-8", (
        f"startup guard did not reconfigure stdout (still {cp1252_stdout.encoding})"
    )

    _seed_fake_repo(tmp_path, plugin_name="fake-plugin", old_ver="0.0.1")
    monkeypatch.setattr(bump_plugin, "ROOT", tmp_path)

    try:
        rc = bump_plugin.main(["bump_plugin.py", "fake-plugin", "0.0.2"])
    except UnicodeEncodeError as exc:  # pragma: no cover — failure mode of #143
        pytest.fail(f"bump_plugin.main raised UnicodeEncodeError on cp1252 stdout: {exc}")
    finally:
        cp1252_stdout.flush()

    assert rc == 0, "bump should succeed on a fresh fake repo"

    # Bytes on the wire must round-trip as utf-8 (since the wrapper is now utf-8).
    output = cp1252_buf.getvalue().decode("utf-8")
    assert "✓ fake-plugin: 0.0.1" in output
    assert "→ 0.0.2" in output

    # Sanity: file writes happened.
    updated_market = json.loads(
        (tmp_path / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8")
    )
    assert updated_market["plugins"][0]["version"] == "0.0.2"
