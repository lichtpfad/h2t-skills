#!/usr/bin/env python3
"""Sync canonical labels to GitHub repos via gh CLI."""

import argparse
import json
import subprocess
import sys
from pathlib import Path

_PLUGIN_ROOT = Path(__file__).resolve().parents[3]
for _lib in [_PLUGIN_ROOT / "lib", _PLUGIN_ROOT.parent.parent / "lib"]:
    if _lib.exists():
        sys.path.insert(0, str(_lib))
        break

from docs.common import DEV_ROOT, GH, REPO_MANIFEST, print_header

# Bundled copy takes priority — works on any machine (MacBook, AUTOMATA, CI).
# Canonical source: C:/dev/docs/standards/labels.json (Windows/AUTOMATA only).
_BUNDLED = _PLUGIN_ROOT / "skills" / "docs-sync-labels" / "data" / "labels.json"
_CANONICAL = DEV_ROOT / "docs" / "standards" / "labels.json"
LABELS_FILE = _BUNDLED if _BUNDLED.exists() else _CANONICAL
ORG = "lichtpfad"


def sync_repo(repo_name: str, labels: dict, *, dry_run: bool = True) -> int:
    errors = 0
    for category, label_list in labels.items():
        for label in label_list:
            cmd = [
                GH, "label", "create", label["name"],
                "--color", label["color"],
                "--description", label["description"],
                "--repo", f"{ORG}/{repo_name}",
                "--force",
            ]
            if dry_run:
                print(f"  {label['name']} ({category})")
                continue
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                print(f"  FAIL: {label['name']} -- {result.stderr.strip()}", file=sys.stderr)
                errors += 1
            else:
                print(f"  OK: {label['name']}")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync labels to GitHub repos")
    parser.add_argument("repos", nargs="*", help="Repos (default: all 16)")
    parser.add_argument("--apply", action="store_true", help="Actually sync (default: dry-run)")
    args = parser.parse_args()

    targets = args.repos or REPO_MANIFEST
    mode = "APPLY" if args.apply else "DRY-RUN"
    print_header(f"docs-sync-labels [{mode}]: {len(targets)} repos")

    if not LABELS_FILE.exists():
        print(f"ERROR: labels.json not found at {LABELS_FILE}", file=sys.stderr)
        sys.exit(1)
    labels = json.loads(LABELS_FILE.read_text(encoding="utf-8"))
    labels = {k: v for k, v in labels.items() if not k.startswith("_")}
    if args.apply:
        from pathlib import Path as _Path
        if not _Path(GH).exists():
            print(f"ERROR: gh CLI not found at {GH}", file=sys.stderr)
            sys.exit(1)
    total = sum(len(v) for v in labels.values())
    print(f"  {total} labels from {LABELS_FILE.name}\n")

    total_errors = 0
    for name in targets:
        print(f"--- {name} ---")
        errors = sync_repo(name, labels, dry_run=not args.apply)
        total_errors += errors

    if not args.apply:
        print("\n  Dry-run complete. Run with --apply to sync.")
    elif total_errors:
        print(f"\n  FAILED: {total_errors} label(s) failed")
        sys.exit(1)
    else:
        print("\n  All repos synced.")


if __name__ == "__main__":
    main()
