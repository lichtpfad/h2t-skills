#!/usr/bin/env python3
"""Does the installed h2t-ops behave for someone who has nothing configured? (#583)

    python3 scripts/release_empty_home.py <path to the installed h2t-ops>

Runs the command with a new, empty HOME and an environment that carries nothing but PATH,
HOME, USERPROFILE and LANG (plus SYSTEMROOT on Windows), so no H2T_ variable, secret or
config of the machine can answer for the user. Checks:

- `--version` exits 0 and names h2t-ops;
- `setup doctor` exits with one of the documented codes;
- `version --json` (no tool install in this HOME) exits 3, the config code, with a hint;
- no output of any of them contains a Python traceback.

Prints one line per check and exits 1 if any failed.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

TRACEBACK = "Traceback (most recent call last)"
EXIT_CODES = range(0, 7)  # 0 ok, 1 provider, 2 usage, 3 config, 4 auth, 5 not found, 6 network


def run(cli: str, args: list[str], home: Path) -> tuple[int, str, str]:
    env = {"PATH": os.pathsep.join([str(Path(cli).parent), "/usr/bin", "/bin"]),
           "HOME": str(home), "USERPROFILE": str(home), "LANG": "C.UTF-8"}
    if "SYSTEMROOT" in os.environ:  # Windows: Python cannot start without it; it holds no config
        env["SYSTEMROOT"] = os.environ["SYSTEMROOT"]
    out = subprocess.run([cli, *args], env=env, cwd=home, capture_output=True, text=True,
                         encoding="utf-8", errors="replace", timeout=120)
    return out.returncode, out.stdout, out.stderr


def check(results: dict[str, tuple[int, str, str]]) -> list[str]:
    """The failures, given each command's (exit, stdout, stderr)."""
    errors = []
    for name, (_, out, err) in results.items():
        if TRACEBACK in out or TRACEBACK in err:
            errors.append(f"{name}: traceback")
    rc, out, _ = results["--version"]
    if rc != 0 or not out.startswith("h2t-ops "):
        errors.append(f"--version: exit {rc}, output {out[:80]!r}")
    rc, _, _ = results["setup doctor"]
    if rc not in EXIT_CODES:
        errors.append(f"setup doctor: exit {rc} is not a documented code")
    rc, out, _ = results["version --json"]
    try:
        hint = json.loads(out)["error"]["hint"]
    except (ValueError, KeyError, TypeError):
        hint = None
    if rc != 3 or not hint:
        errors.append(f"version --json: exit {rc}, hint {hint!r}; a missing install must be exit 3 with a hint")
    return errors


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print(__doc__, file=sys.stderr)
        return 2
    # Absolute: the commands run with the empty HOME as cwd, where a relative path names nothing.
    cli = str(Path(args[0]).resolve())
    with tempfile.TemporaryDirectory(prefix="h2t-empty-home-") as tmp:
        home = Path(tmp)
        results = {name: run(cli, name.split(), home)
                   for name in ("--version", "setup doctor", "version --json")}
        left = sorted(p.name for p in home.iterdir())
    for name, (rc, _, _) in results.items():
        print(f"h2t-ops {name}: exit {rc}")
    print(f"written into the empty HOME: {left or 'nothing'}")
    errors = check(results)
    for e in errors:
        print(f"FAIL {e}", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
