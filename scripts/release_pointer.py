"""Read and move the release pointer: marketplace.json plugin sources pinned to one tag."""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

URL = "https://github.com/lichtpfad/h2t-skills.git"
ROOT = Path(__file__).resolve().parents[1]
_SHA = re.compile(r"^[0-9a-f]{40}$")


def set_pointer(marketplace: dict, ref: str, sha: str, versions: dict[str, str] | None = None) -> dict:
    """Pin every entry to `ref`/`sha`; with `versions`, write each entry's label too, so the
    label and the content it names move in one commit (spec §7.1)."""
    if not _SHA.match(sha):
        raise ValueError("sha must be 40 lowercase hex characters")
    for entry in marketplace["plugins"]:
        entry["source"] = {"source": "git-subdir", "url": URL,
                           "path": f"plugins/{entry['name']}", "ref": ref, "sha": sha}
        if versions is not None:
            entry["version"] = versions[entry["name"]]
    return marketplace


def versions_at(sha: str, names: list[str], root: Path) -> dict[str, str]:
    """Each plugin's version from its plugin.json at `sha` (git show), not the working tree."""
    found = {}
    for name in names:
        path = f"plugins/{name}/.claude-plugin/plugin.json"
        done = subprocess.run(["git", "show", f"{sha}:{path}"], cwd=root, capture_output=True,
                              check=False)
        if done.returncode != 0:
            raise ValueError(f"cannot read {path} at {sha}: "
                             f"{done.stderr.decode('utf-8', 'replace').strip()}")
        found[name] = json.loads(done.stdout.decode("utf-8"))["version"]
    return found


def read_pointer(marketplace: dict) -> dict[str, tuple[str, str]]:
    pins = {}
    for entry in marketplace["plugins"]:
        src = entry["source"]
        if not isinstance(src, dict) or src.get("source") != "git-subdir":
            raise ValueError(f"{entry['name']}: source is not a pinned git-subdir")
        pins[entry["name"]] = (src["ref"], src["sha"])
    if len(set(pins.values())) > 1:
        raise ValueError("plugins point at more than one release")
    return pins


def main(argv: list[str]) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    path = ROOT / ".claude-plugin" / "marketplace.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    if argv[:1] == ["set"] and len(argv) == 3:
        versions = versions_at(argv[2], [e["name"] for e in data["plugins"]], ROOT)
        path.write_text(json.dumps(set_pointer(data, argv[1], argv[2], versions), indent=2,
                                   ensure_ascii=False) + "\n", encoding="utf-8")
        return 0
    if argv[:1] == ["check"]:
        print(json.dumps(read_pointer(data)))
        return 0
    print("usage: release_pointer.py set <ref> <sha40> | check", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
