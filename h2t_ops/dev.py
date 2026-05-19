"""h2t-ops dev — repo-local execution wrapper for agents/plans/tests.

Resolves the running interpreter (uv-managed under `uv run`) so plans never
hardcode a python path or shell idiom.
  dev python <args...>   -> [py, <args...>]
  dev pip <args...>      -> [py, -m pip, <args...>]   (NOT for installing this project)
  dev pytest <args...>   -> [py, -m pytest, <args...>]
  dev check <name>       -> named verification (no shell, cross-platform)
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

_RUNTIME = Path(__file__).resolve().parent.parent / ".h2t" / "agent-runtime.json"
_SYSPATH_PAT = re.compile(r"sys\.path\.insert\s*\(")


def _repo_root() -> Path:
    base = _RUNTIME.parent.parent
    try:
        cfg = json.loads(_RUNTIME.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        cfg = {}
    repo = cfg.get("repo", ".")
    return base.resolve() if repo == "." else Path(repo).resolve()


def _run(cmd: list[str]) -> int:
    try:
        return subprocess.run(cmd, cwd=_repo_root()).returncode
    except FileNotFoundError as e:
        print(f"h2t-ops dev: cannot run {cmd[0]}: {e}", file=sys.stderr)
        return 127


def _check(name: str) -> int:
    root = _repo_root()
    if name == "no-syspath":
        hits = [str(p) for p in (root / "h2t_ops").rglob("*.py")
                if _SYSPATH_PAT.search(p.read_text(encoding="utf-8"))]
        if hits:
            print("FAIL no-syspath: " + ", ".join(hits), file=sys.stderr)
            return 1
        print("OK no-syspath")
        return 0
    if name == "lazy-registry":
        import builtins
        real = builtins.__import__

        def guard(n, *a, **k):
            if n in ("notion_client", "httpx"):
                raise AssertionError(f"registry imported {n}")
            return real(n, *a, **k)

        builtins.__import__ = guard
        try:
            from h2t_ops.core.registry import discover
            names = {s.name for s in discover()}
        except ImportError as e:
            print(f"FAIL lazy-registry (not yet installed: {e})", file=sys.stderr)
            return 1
        finally:
            builtins.__import__ = real
        ok = "notion" in names
        print(("OK" if ok else "FAIL") + " lazy-registry")
        return 0 if ok else 1
    if name == "gather-smoke":
        code = subprocess.run(
            [sys.executable, "-m", "h2t_ops.cli", "gather", "session-start", "--cwd", str(root)],
            cwd=root, stdout=subprocess.DEVNULL).returncode
        print(("OK" if code == 0 else "FAIL") + f" gather-smoke (exit={code})")
        return 0 if code == 0 else 1
    if name == "skill-md-notion":
        f = root / "plugins" / "h2t-ops" / "skills" / "notion" / "SKILL.md"
        t = f.read_text(encoding="utf-8")
        ok = t.startswith("---") and "h2t-ops notion get" in t
        print(("OK" if ok else "FAIL") + " skill-md-notion")
        return 0 if ok else 1
    print(f"unknown check: {name}", file=sys.stderr)
    return 2


def main(argv: list[str]) -> int:
    if not argv:
        print("usage: h2t-ops dev {python|pip|pytest|check} ...", file=sys.stderr)
        return 2
    tool, rest, py = argv[0], argv[1:], sys.executable
    if tool == "python":
        return _run([py, *rest])
    if tool == "pip":
        return _run([py, "-m", "pip", *rest])
    if tool == "pytest":
        return _run([py, "-m", "pytest", *rest])
    if tool == "check":
        if not rest:
            print("usage: h2t-ops dev check <name>", file=sys.stderr)
            return 2
        return _check(rest[0])
    print(f"unknown dev tool: {tool}", file=sys.stderr)
    return 2
