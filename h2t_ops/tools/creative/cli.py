"""`h2t-creative`: profiles and the assembler, from the package.

`root` prints the shipped resources (`profiles/`, `base/`, `shared/`). `profiles-dir` prints
where profiles the user creates live: `~/.h2t/data/creative/profiles/`, outside every
install, so an update cannot wipe them — the plugin bin this replaces answered with its own
directory, and style-create wrote new profiles into the plugin cache. `assemble` looks a
profile up there first, then in the 3.x directory `~/.h2t/creative/profiles/` (read only,
until the migration moves it), then among the shipped ones. `verify` checks a built deck
against the approved text its markdown names (`h2t_ops.tools.creative.fidelity`).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from h2t_ops.core import paths
from h2t_ops.resources import resource_dir

USAGE = "usage: h2t-creative {root,profiles-dir,assemble,verify} [args]"


def user_profiles_dir() -> Path:
    """data/creative/profiles under the one root, `~/.h2t` (#548 option A, §3)."""
    return paths.data_dir() / "creative" / "profiles"


def _profiles_dir_with(name: str) -> Path | None:
    """The user directory that holds this profile: 4.0's, else the 3.x one (4.0.x fallback)."""
    for d in (user_profiles_dir(), paths.legacy("creative")):
        if (d / name).is_dir():
            return d
    return None


def _profile_name(args: list[str]) -> str | None:
    for i, arg in enumerate(args):
        if arg == "--profile" and i + 1 < len(args):
            return args[i + 1]
        if arg.startswith("--profile="):
            return arg.split("=", 1)[1]
    return None


def _resolve(path: str, deck: Path) -> Path:
    """A source path as written in the deck: relative to the working directory, else to the deck."""
    p = Path(path)
    return p if p.is_absolute() or p.exists() else deck.parent / p


def verify(args: list[str]) -> int:
    from h2t_ops.tools.creative import fidelity

    ap = argparse.ArgumentParser(prog="h2t-creative verify",
                                 description="Check a built deck against the approved text its markdown names.")
    ap.add_argument("--deck", required=True, help="deck markdown with `verbatim_source` in its frontmatter")
    ap.add_argument("--page", required=True, help="built page, e.g. dist/index.html")
    ap.add_argument("--source", help="approved markdown; overrides `verbatim_source`")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(args)
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")  # the report quotes the source (#428)
    deck = Path(a.deck)
    deck_md = deck.read_text(encoding="utf-8")
    source = a.source or fidelity.frontmatter(deck_md).get("verbatim_source")
    source_md = _resolve(source, deck).read_text(encoding="utf-8") if source else None
    report = fidelity.verify(deck_md, source_md, Path(a.page).read_text(encoding="utf-8"))
    report["source"] = source
    if a.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["ok"] else 1
    if source is None:
        print("no verbatim_source: only slide placement checked")
    for o in report["omitted"]:
        text, why = (o.get("text", ""), o.get("why", "")) if isinstance(o, dict) else (o, "")
        print(f"  not shown by decision: {text[:80]} — {why}")
    for old, new in report["renamed"].items():
        print(f"  renamed: «{old}» → «{new}»")
    for key, title in (("stale_omit", "omit entries not found in the source"),
                       ("misplaced", "blocks not on their slide"),
                       ("missing", f"fragments of {source} not in the deck word for word")):
        if report[key]:
            print(f"FAIL: {len(report[key])} {title}:", file=sys.stderr)
            for item in report[key]:
                print(f"  - {item[:140]}", file=sys.stderr)
    if report["ok"]:
        print("PASS: deck fidelity" + (f" against {source}" if source else ""))
    return 0 if report["ok"] else 1


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else list(argv)
    command = args[0] if args else ""
    if command == "root":
        print(resource_dir("creative"))
        return 0
    if command == "profiles-dir":
        print(user_profiles_dir())
        return 0
    if command == "assemble":
        from h2t_ops.tools.creative import assembler

        name = _profile_name(args[1:])
        found = _profiles_dir_with(name) if name else None
        if found is not None:
            # The assembler copy reads PROFILES_DIR once per run; base/ and shared/ stay
            # the shipped ones. A user profile shadows a shipped one of the same name.
            assembler.PROFILES_DIR = found
        # assembler.main parses sys.argv itself, exactly as the plugin script runs it.
        sys.argv = ["h2t-creative assemble", *args[1:]]
        assembler.main()
        return 0
    if command == "verify":
        return verify(args[1:])
    if command in {"-h", "--help"}:
        print(__doc__.splitlines()[0])
        print(USAGE)
        return 0
    print(USAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
