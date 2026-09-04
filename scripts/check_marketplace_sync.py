#!/usr/bin/env python3
"""Check that .claude-plugin/marketplace.json agrees with each plugin's
own .claude-plugin/plugin.json. Exits 1 on drift with actionable message.

Runs via pre-commit hook (see scripts/hooks/pre-commit) or manually:
    python scripts/check_marketplace_sync.py

Motivation: see lichtpfad/h2t-skills#74. A marketplace entry frozen at
an older version than the plugin's own manifest causes Claude Code to
silently skip plugin load on fresh installs.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    # The success and drift lines carry ✓/❌; a Windows console encodes stdout as
    # cp1252 whatever the source encoding, so printing them raised UnicodeEncodeError
    # and failed the pre-commit hook on the very bump it guards. Same trap the hook
    # handlers already reconfigure around.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")

    market_path = ROOT / ".claude-plugin" / "marketplace.json"
    if not market_path.is_file():
        print(f"error: {market_path} not found", file=sys.stderr)
        return 2
    market = _load(market_path)

    drifts: list[tuple[str, str, str]] = []
    market_names: set[str] = set()

    for entry in market["plugins"]:
        name = entry["name"]
        market_names.add(name)
        source = entry["source"].lstrip("./")
        plugin_path = ROOT / source / ".claude-plugin" / "plugin.json"
        if not plugin_path.is_file():
            drifts.append((name, "missing", f"source path {source} has no plugin.json"))
            continue
        actual = _load(plugin_path)
        if actual["version"] != entry["version"]:
            drifts.append((
                name, "version",
                f"marketplace={entry['version']} plugin.json={actual['version']}",
            ))

    # Orphan check: plugins present on disk but absent from marketplace.json.
    plugins_root = ROOT / "plugins"
    if plugins_root.is_dir():
        for plugin_dir in sorted(plugins_root.iterdir()):
            if not (plugin_dir / ".claude-plugin" / "plugin.json").is_file():
                continue
            if plugin_dir.name not in market_names:
                drifts.append((
                    plugin_dir.name, "orphan",
                    f"plugins/{plugin_dir.name}/ exists but not in marketplace.json",
                ))

    if drifts:
        print("❌ marketplace drift detected:", file=sys.stderr)
        for name, kind, detail in drifts:
            print(f"  [{kind}] {name}: {detail}", file=sys.stderr)
        print("", file=sys.stderr)
        print(
            "Fix options:\n"
            "  - python scripts/bump_plugin.py <name> <version>   (atomic bump)\n"
            "  - or edit both files manually and keep them in sync",
            file=sys.stderr,
        )
        return 1

    print(f"✓ marketplace synced ({len(market['plugins'])} plugins)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
