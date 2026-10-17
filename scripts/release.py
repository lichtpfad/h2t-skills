#!/usr/bin/env python3
"""Prepare a release commit: one version everywhere, one bootstrap literal (spec §7.1, §7.2).

    python scripts/release.py prepare <X.Y.Z>

Writes `<ver>` into pyproject.toml, h2t_ops/__init__.py, uv.lock (the project's own row),
every plugin.json, every `version` of marketplace.json and every plugins/*/release.env;
stamps the `--expect` and bootstrap literals into the SKILL.md / reference copies and
plugins/*/hooks/run; regenerates h2t_ops/setup/_release.py; exports constraints.txt; writes
release.json at the repo root.

Substitution is by slot pattern, not by placeholder, so the next release rewrites what this
one wrote. `@VERSION@` and `@BOOTSTRAP@` are accepted as the initial values. Every slot has
an exact expected count per file; any other count is an error and nothing is written.

The root CHANGELOG.md must already carry a `## <ver>` heading: the notes are written by
hand, this script only refuses to cut a release without them.
"""
from __future__ import annotations

import importlib.util
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON = "3.12.11"
REPO = "lichtpfad/h2t-skills"
_VER = re.compile(r"^\d+\.\d+\.\d+$")
# One shell word that needs no quoting in bash, PowerShell and cmd alike.
_PLAIN = re.compile(r"^[A-Za-z0-9_.=+-]+$")
_UNSAFE = set("'\"\\$`\n\r")

# Slot patterns: each matches the initial placeholder and every value a release writes.
# The public ones are also what tests/skills and tests/hooks read the shipped text with.
_VERSION_SLOT = r"(?:@VERSION@|\d+\.\d+\.\d+)"
VERSION_CHECK = re.compile(rf"h2t-ops version --expect {_VERSION_SLOT} --json")
_MD_VERSION = re.compile(rf"(?<=h2t-ops version --expect ){_VERSION_SLOT}(?= --json)")
BOOTSTRAP_SLOT = re.compile(
    r'@BOOTSTRAP@|uvx --isolated --python [0-9.]+ --managed-python -c "[^"\n]*" '
    r'--from "[^"\n]*" h2t-setup')
RUN_BOOTSTRAP = re.compile(r"^BOOTSTRAP='[^'\n]*'", re.M)
_ENV_VERSION = re.compile(r"^VERSION=.*$", re.M)
_TOML_VERSION = re.compile(r'^version = "[^"\n]*"$', re.M)
_INIT_VERSION = re.compile(r'^__version__ = "[^"\n]*"$', re.M)
_JSON_VERSION = re.compile(r'"version": "[^"\n]*"')
# A file carrying the version-check block has one --expect and two bootstraps in it.
_BLOCK = (1, 2)

RELEASE_PY = '''"""The bootstrap of this release (spec §7.2). Written by scripts/release.py prepare; do not edit."""

BOOTSTRAP: list[str] = {argv}
BOOTSTRAP_COMMAND = {command}
'''


class ReleaseError(Exception):
    pass


def bootstrap_argv(ver: str, wheel_url: str, constraints_url: str, python: str) -> list[str]:
    """The one source of the bootstrap literal; the caller appends the mode (sync/update)."""
    return ["uvx", "--isolated", "--python", python, "--managed-python", "-c", constraints_url,
            "--from", f"h2t-ops @ {wheel_url}", "h2t-setup"]


def asset_urls(ver: str) -> tuple[str, str]:
    base = f"https://github.com/{REPO}/releases/download/v{ver}"
    return f"{base}/h2t_ops-{ver}-py3-none-any.whl", f"{base}/constraints.txt"


def render(argv: list[str]) -> str:
    """The argv as one command line, double-quoting words that need it.

    The result is written inside bash single quotes (hooks/run) and into JSON by the
    wrapper's escaper, so no word may carry a quote, a backslash or an expansion."""
    for word in argv:
        if _UNSAFE & set(word):
            raise ReleaseError(f"bootstrap word cannot be quoted safely: {word!r}")
    return " ".join(w if _PLAIN.match(w) else f'"{w}"' for w in argv)


def _sub(path: Path, text: str, pattern: re.Pattern, value: str, expected: int) -> tuple[str, int]:
    text, n = pattern.subn(lambda _m: value, text)
    if n != expected:
        raise ReleaseError(f"{path}: slot {pattern.pattern!r} matched {n} times, expected {expected}")
    return text, n


def _plan(root: Path, ver: str) -> dict[Path, tuple[str, int]]:
    """Every file's new text and its slot count, or ReleaseError before anything is written."""
    wheel, constraints = asset_urls(ver)
    argv = bootstrap_argv(ver, wheel, constraints, PYTHON)
    command = render(argv)
    plan: dict[Path, tuple[str, int]] = {}

    def edit(path: Path, *slots: tuple[re.Pattern, str, int]) -> None:
        text, total = path.read_text(encoding="utf-8"), 0
        for pattern, value, expected in slots:
            text, n = _sub(path.relative_to(root), text, pattern, value, expected)
            total += n
        plan[path] = (text, total)

    edit(root / "pyproject.toml", (_TOML_VERSION, f'version = "{ver}"', 1))
    edit(root / "h2t_ops" / "__init__.py", (_INIT_VERSION, f'__version__ = "{ver}"', 1))
    market = root / ".claude-plugin" / "marketplace.json"
    plugins = json.loads(market.read_text(encoding="utf-8"))["plugins"]
    edit(market, (_JSON_VERSION, f'"version": "{ver}"', len(plugins)))
    for pj in sorted(root.glob("plugins/*/.claude-plugin/plugin.json")):
        edit(pj, (_JSON_VERSION, f'"version": "{ver}"', 1))
    for env in sorted(root.glob("plugins/*/release.env")):
        edit(env, (_ENV_VERSION, f"VERSION={ver}", 1))
    for run in sorted(root.glob("plugins/*/hooks/run")):
        edit(run, (RUN_BOOTSTRAP, f"BOOTSTRAP='{command}'", 1))
    for md in sorted(root.glob("plugins/**/*.md")):
        text = md.read_text(encoding="utf-8")
        found = (len(_MD_VERSION.findall(text)), len(BOOTSTRAP_SLOT.findall(text)))
        if found == (0, 0):
            continue
        if found != _BLOCK:
            raise ReleaseError(f"{md.relative_to(root)}: {found[0]} --expect and {found[1]} bootstrap "
                               f"slots, expected {_BLOCK[0]} and {_BLOCK[1]} (the version-check block)")
        edit(md, (_MD_VERSION, ver, 1), (BOOTSTRAP_SLOT, command, 2))
    data = root / "h2t_ops" / "setup" / "_release.py"
    plan[data] = (RELEASE_PY.format(argv=json.dumps(argv), command=json.dumps(command)), 1)
    return plan


def stamp(root: Path, ver: str) -> dict[str, int]:
    """Write `ver` and its bootstrap into every slot; returns the slot count per file."""
    _check_version(ver)
    plan = _plan(root, ver)
    for path, (text, _n) in plan.items():
        path.write_text(text, encoding="utf-8", newline="")
    return {path.relative_to(root).as_posix(): n for path, (_t, n) in plan.items()}


def _check_version(ver: str) -> None:
    if not _VER.match(ver):
        raise ReleaseError(f"version must be X.Y.Z, got {ver!r}")


def previous(root: Path) -> str:
    """The release the pointer names now, without its `v`."""
    spec = importlib.util.spec_from_file_location("release_pointer", root / "scripts" / "release_pointer.py")
    assert spec and spec.loader
    pointer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pointer)
    market = json.loads((root / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
    try:
        refs = {ref for ref, _sha in pointer.read_pointer(market).values()}
    except (ValueError, KeyError) as exc:
        raise ReleaseError(
            f"marketplace.json is not pinned to a release ({exc}); freeze the pointer first: "
            "python scripts/release_pointer.py set v<current> <sha40>") from exc
    ref = refs.pop()
    if not ref.startswith("v"):
        raise ReleaseError(f"pointer ref {ref!r} is not a v<X.Y.Z> tag")
    return ref[1:]


def manifest(root: Path, ver: str) -> dict:
    wheel, constraints = asset_urls(ver)
    return {"format": 1, "version": ver, "previous": previous(root), "python": PYTHON,
            "wheel": wheel, "constraints": constraints,
            "bootstrap": bootstrap_argv(ver, wheel, constraints, PYTHON)}


def write_manifest(root: Path, ver: str) -> dict:
    data = manifest(root, ver)
    (root / "release.json").write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return data


def _check_changelog(root: Path, ver: str) -> None:
    changelog = root / "CHANGELOG.md"
    text = changelog.read_text(encoding="utf-8") if changelog.is_file() else ""
    if not re.search(rf"^## {re.escape(ver)}(\s|$)", text, re.M):
        raise ReleaseError(f"CHANGELOG.md has no '## {ver}' heading; write the release notes first")


def _uv(root: Path, *args: str) -> None:
    uv = shutil.which("uv")
    if uv is None:
        raise ReleaseError("uv is not on PATH; prepare locks and exports through it")
    result = subprocess.run([uv, *args], cwd=root, capture_output=True, text=True, encoding="utf-8")
    if result.returncode != 0:
        raise ReleaseError(f"uv {' '.join(args)} failed:\n{result.stderr}")


def export_constraints(root: Path) -> None:
    # The lock's own row of h2t-ops carries the version; --offline changes nothing else.
    _uv(root, "lock", "--offline")
    _uv(root, "export", "--frozen", "--no-dev", "--all-extras", "--no-emit-project", "--no-hashes",
        "-o", "constraints.txt")
    leaked = [line for line in (root / "constraints.txt").read_text(encoding="utf-8").splitlines()
              if re.match(r"h2t[-_]ops", line, re.I)]
    if leaked:
        raise ReleaseError(f"constraints.txt pins the project itself: {leaked}")


def prepare(root: Path, ver: str) -> dict[str, int]:
    _check_version(ver)
    prev = previous(root)
    if prev == ver:
        raise ReleaseError(f"{ver} is the release the pointer already names")
    _check_changelog(root, ver)
    # uv lock reads the stamped pyproject, so the uv steps cannot run first. Every file
    # prepare may touch is snapshotted as bytes and put back on any failure after stamp.
    touched = [*_plan(root, ver), *(root / name for name in ("uv.lock", "constraints.txt", "release.json"))]
    before = {path: path.read_bytes() if path.is_file() else None for path in touched}
    try:
        counts = stamp(root, ver)
        export_constraints(root)
        write_manifest(root, ver)
    except Exception as exc:
        for path, data in before.items():
            if data is None:
                path.unlink(missing_ok=True)
            else:
                path.write_bytes(data)
        raise ReleaseError(f"{exc}\nthe tree was restored: {len(before)} files back to their state "
                           "before prepare") from exc
    return counts


def main(argv: list[str]) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    if len(argv) != 2 or argv[0] != "prepare":
        print("usage: release.py prepare <X.Y.Z>", file=sys.stderr)
        return 2
    try:
        counts = prepare(ROOT, argv[1])
    except ReleaseError as exc:
        print(f"release: {exc}", file=sys.stderr)
        return 1
    for path, n in counts.items():
        print(f"{n:3d}  {path}")
    print(f"release {argv[1]}: {len(counts)} files, constraints.txt, release.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
