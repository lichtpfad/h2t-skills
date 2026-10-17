#!/usr/bin/env python3
"""Check that .claude-plugin/marketplace.json agrees with each plugin's
own .claude-plugin/plugin.json. Exits 1 on drift with actionable message.

Runs via pre-commit hook (see scripts/hooks/pre-commit) or manually:
    python scripts/check_marketplace_sync.py

Motivation: see lichtpfad/h2t-skills#74. A marketplace entry frozen at
an older version than the plugin's own manifest causes Claude Code to
silently skip plugin load on fresh installs.

A relative-source entry is compared with plugin.json in the working tree. A pinned
`git-subdir` entry is what Claude Code installs from its commit, so it is compared with
plugin.json AT THAT COMMIT (`git show <sha>:<path>/.claude-plugin/plugin.json`): between a
release commit, which stamps plugin.json, and the pointer move, which stamps the labels,
main is consistent and must stay green (spec §7.1).
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_at(commit: str, path: str) -> dict[str, Any] | None:
    """plugin.json as committed at `commit`, or None when git cannot show it."""
    try:
        done = subprocess.run(["git", "show", f"{commit}:{path}"], cwd=ROOT, capture_output=True,
                              timeout=30, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    if done.returncode != 0:
        return None
    try:
        return json.loads(done.stdout.decode("utf-8"))
    except ValueError:
        return None


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
        src = entry["source"]
        pinned = isinstance(src, dict) and src.get("source") == "git-subdir"
        source = src["path"] if isinstance(src, dict) else src.lstrip("./")
        if pinned:
            commit = src.get("sha") or src.get("ref") or ""
            actual = _load_at(commit, f"{source}/.claude-plugin/plugin.json")
            if actual is None:
                drifts.append((name, "missing",
                               f"cannot read {source}/.claude-plugin/plugin.json at the pinned "
                               f"commit {commit} ({src.get('ref')}); fetch it: git fetch --tags"))
                continue
            where = f"plugin.json@{src.get('ref') or commit}"
        else:
            plugin_path = ROOT / source / ".claude-plugin" / "plugin.json"
            if not plugin_path.is_file():
                drifts.append((name, "missing", f"source path {source} has no plugin.json"))
                continue
            actual = _load(plugin_path)
            where = "plugin.json"
        if actual["version"] != entry["version"]:
            drifts.append((
                name, "version",
                f"marketplace={entry['version']} {where}={actual['version']}",
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
            "  - a pinned entry: python scripts/release_pointer.py set <ref> <sha40>\n"
            "    (writes each label from plugin.json at that commit)\n"
            "  - or edit both files manually and keep them in sync",
            file=sys.stderr,
        )
        return 1

    print(f"✓ marketplace synced ({len(market['plugins'])} plugins)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
