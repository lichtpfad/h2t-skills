#!/usr/bin/env python3
"""Atomically bump a plugin's version in BOTH marketplace.json and the
plugin's own plugin.json. Prevents drift (see lichtpfad/h2t-skills#74).

Usage:
    python scripts/bump_plugin.py <plugin_name> <new_version>
    python scripts/bump_plugin.py h2t-ops 1.0.3

Exits 0 on success and prints the recommended commit command.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
_SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+([-+].+)?$")


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _dump(path: Path, data: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: bump_plugin.py <plugin_name> <new_version>", file=sys.stderr)
        print("example: bump_plugin.py h2t-ops 1.0.3", file=sys.stderr)
        return 1
    _, name, new_ver = argv

    if not _SEMVER_RE.match(new_ver):
        print(f"error: {new_ver!r} is not a valid semver (x.y.z)", file=sys.stderr)
        return 2

    market_path = ROOT / ".claude-plugin" / "marketplace.json"
    market = _load(market_path)
    entry = next((p for p in market["plugins"] if p["name"] == name), None)
    if entry is None:
        print(f"error: plugin {name!r} not in marketplace.json", file=sys.stderr)
        print(
            f"  known plugins: {', '.join(p['name'] for p in market['plugins'])}",
            file=sys.stderr,
        )
        return 2

    plugin_path = ROOT / entry["source"].lstrip("./") / ".claude-plugin" / "plugin.json"
    plugin = _load(plugin_path)
    old_ver = plugin["version"]

    if old_ver == new_ver:
        print(f"error: version already {new_ver}", file=sys.stderr)
        return 2

    # Atomic-ish: compute both dicts, then write both.
    plugin["version"] = new_ver
    entry["version"] = new_ver

    _dump(plugin_path, plugin)
    _dump(market_path, market)

    rel_plugin = plugin_path.relative_to(ROOT).as_posix()
    rel_market = market_path.relative_to(ROOT).as_posix()

    print(f"✓ {name}: {old_ver} → {new_ver}")
    print(f"  updated: {rel_plugin}")
    print(f"  updated: {rel_market}")
    print()
    print("next:")
    print(f"  git add {rel_market} {rel_plugin}")
    print(f"  git commit -m 'chore({name}): bump {old_ver} → {new_ver}'")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
