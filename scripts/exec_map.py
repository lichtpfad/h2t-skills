"""Map every executable file the pack ships and count what must reach zero."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ALLOWLIST = {"hooks/run"}
_TEST_PARTS = ("/tests/", "/test_", "conftest.py")


def _tracked(root: Path, prefix: str) -> list[str]:
    cmd = ["git", "ls-files", prefix]
    return subprocess.run(cmd, cwd=root, check=True, capture_output=True, text=True).stdout.splitlines()


def _is_test(path: str) -> bool:
    return any(t in "/" + path for t in _TEST_PARTS)


def shipped_runtime_python(root: Path) -> list[str]:
    """Every tracked .py under plugins/, tests included: tests no longer live there (#541),
    and excusing them let a `plugins/x/tests/helper.py` ship unseen."""
    return sorted(p for p in _tracked(root, "plugins/") if p.endswith(".py"))


def _allowlisted(path: str) -> bool:
    """`plugins/<name>/hooks/run` matches `hooks/run`: the allowlist names the in-plugin path."""
    return "/".join(path.split("/")[2:]) in ALLOWLIST


def shipped_executables(root: Path) -> list[str]:
    """Shipped files that can run as programs: the exec bit in git, or a `#!` first line.

    Python is one way to ship code; a shell script is another. The runtime-.py ratchet sees
    only the first, so this one counts the rest, the allowlist excepted.
    """
    staged = subprocess.run(["git", "ls-files", "-s", "plugins/"], cwd=root, check=True,
                            capture_output=True, text=True).stdout.splitlines()
    found = set()
    for line in staged:
        mode, _, _, path = line.split(maxsplit=3)
        if _allowlisted(path):
            continue
        if mode == "100755":
            found.add(path)
            continue
        try:
            with open(root / path, "rb") as fh:
                if fh.read(2) == b"#!":
                    found.add(path)
        except FileNotFoundError:
            continue
    return sorted(found)


def literal_hits(root: Path, literals: list[str]) -> list[str]:
    hits = []
    for path in _tracked(root, "plugins/") + _tracked(root, "h2t_ops/"):
        if _is_test(path):
            continue
        try:
            text = (root / path).read_text(encoding="utf-8")
        except (UnicodeDecodeError, FileNotFoundError):
            continue
        hits += [f"{path}: {lit}" for lit in literals if lit in text]
    return hits


def _destination(path: str) -> str:
    """Spec section 5: where the file's behaviour lives after the move."""
    parts = path.split("/")
    name = Path(path).name
    if "hooks-handlers" in parts:
        return "h2t_ops/hooks/"
    if "connectors" in parts or parts[0] == "h2t_ops":
        return "h2t_ops/connectors/"
    if "docs-lint" in parts or "drawio" in parts or "assembler.py" == name:
        return "h2t_ops/tools/"
    if "lib" in parts:
        return "h2t_ops/lifecycle/ или core/"
    if "setup" in parts or name.startswith("setup"):
        return "h2t_ops/setup/"
    if "scripts" in parts:
        return "h2t_ops/lifecycle/ или tools/"
    return "h2t_ops/ (определить при переносе)"


def _consumers(root: Path, path: str) -> int:
    stem = Path(path).stem
    out = subprocess.run(["git", "grep", "-l", "-F", stem, "--", "plugins/", "tests/", "scripts/"],
                         cwd=root, capture_output=True, text=True).stdout.splitlines()
    return len([p for p in out if p != path])


def build_table(root: Path) -> str:
    rows = shipped_runtime_python(root)
    lines = ["| файл | потребители (файлов с именем) | назначение по спеке §5 |", "|---|---|---|"]
    for p in rows:
        lines.append(f"| `{p}` | {_consumers(root, p)} | {_destination(p)} |")
    return "\n".join(lines)


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    py = shipped_runtime_python(root)
    print("# Карта исполняемых файлов\n")
    print(f"Исполняемого Python в `plugins/` вне тестов: **{len(py)}**. "
          f"Допустимые исключения (ALLOWLIST): {sorted(ALLOWLIST)}.\n")
    print(build_table(root))
    return 0


if __name__ == "__main__":
    sys.exit(main())
