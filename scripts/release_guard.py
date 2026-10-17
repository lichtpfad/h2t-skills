#!/usr/bin/env python3
"""May tag v<ver> move the release pointer? (spec §7.1)

    python scripts/release_guard.py v<ver> [--allow-done]

Run from a full clone with origin/main fetched. Prints `move` (exit 0) when the tag commit is
reachable from origin/main and the pointer on origin/main names release.json's `previous`
(read at the tag, without its `v`). With --allow-done it prints `done` (exit 0) when the
pointer already names v<ver> at the tag's own commit, so a re-run pointer job is a no-op.
Anything else exits 1 with the reason on stderr.

release.yml calls it twice: in `build`, before anything is published, and in `pointer`,
because main can move between the two.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], capture_output=True, text=True, encoding="utf-8")


def _read_pointer(marketplace: dict) -> dict[str, tuple[str, str]]:
    spec = importlib.util.spec_from_file_location("release_pointer", ROOT / "release_pointer.py")
    assert spec and spec.loader
    pointer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pointer)
    return pointer.read_pointer(marketplace)


def decide(tag: str, allow_done: bool) -> str:
    """'move' or 'done'; raises SystemExit(reason) when the pointer must not move."""
    sha = _git("rev-parse", f"refs/tags/{tag}^{{commit}}")
    if sha.returncode != 0:
        raise SystemExit(f"no tag {tag}: {sha.stderr.strip()}")
    sha = sha.stdout.strip()
    # A release comes from main only: a tag on an unmerged branch never moves the pointer.
    if _git("merge-base", "--is-ancestor", sha, "origin/main").returncode != 0:
        raise SystemExit(f"{tag} ({sha}) is not reachable from origin/main")
    manifest = _git("show", f"{sha}:release.json")
    if manifest.returncode != 0:
        raise SystemExit(f"{tag} has no release.json: prepare was not run on it")
    previous = json.loads(manifest.stdout)["previous"]
    market = _git("show", "origin/main:.claude-plugin/marketplace.json")
    if market.returncode != 0:
        raise SystemExit(f"origin/main has no marketplace.json: {market.stderr.strip()}")
    try:
        pins = set(_read_pointer(json.loads(market.stdout)).values())
    except (ValueError, KeyError) as exc:
        raise SystemExit(f"the pointer on origin/main is not pinned: {exc}") from exc
    (current, current_sha), = pins
    if allow_done and (current, current_sha) == (tag, sha):
        print(f"the pointer is already at {tag} ({sha})", file=sys.stderr)
        return "done"
    # The pointer moves only from `previous`, so it never goes back. The first release,
    # 4.0.0, follows the freeze at v3.3.0.
    if current.removeprefix("v") != previous:
        raise SystemExit(f"the pointer is at {current} ({current_sha}); release.json at {tag} "
                         f"says previous = {previous}. Not moving.")
    return "move"


def main(argv: list[str]) -> int:
    if len(argv) not in (1, 2) or (len(argv) == 2 and argv[1] != "--allow-done"):
        print("usage: release_guard.py v<ver> [--allow-done]", file=sys.stderr)
        return 2
    try:
        print(decide(argv[0], allow_done=len(argv) == 2))
    except SystemExit as exc:
        print(f"::error::{exc.code}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
