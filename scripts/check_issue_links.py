"""CI ratchet: a plan or spec touched by this change must name the work it belongs to.

Deliberately not `docs-lint doctor --fail-on unlinked`. That gates the whole tree, and the
tree carries 74 documents written before the field existed (#421). A gate that is red on
day one for historical reasons gets disabled within a week, which is how the thing it
guards stops being guarded.

So this checks only what the change touched. History stays as it is and is fixed
deliberately; growth is what gets stopped. Same shape as the DESC_DEBT and KNOWN_DEBT
ratchets in tests/.

Usage:  python scripts/check_issue_links.py <base-ref>
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "plugins" / "h2t-dev" / "lib"))

from docs.common import (  # noqa: E402  — path is set on the line above
    LINKED_DOC_DIRS,
    issue_link_problem,
    parse_frontmatter,
)


def changed_files(base: str) -> list[str]:
    r = subprocess.run(
        ["git", "diff", "--name-only", "--diff-filter=ACMR", f"{base}...HEAD"],
        capture_output=True, text=True, cwd=ROOT,
    )
    if r.returncode != 0:
        print(f"ERROR: git diff against {base!r} failed: {r.stderr.strip()}", file=sys.stderr)
        sys.exit(2)
    return [ln.strip() for ln in r.stdout.splitlines() if ln.strip()]


def main() -> int:
    base = sys.argv[1] if len(sys.argv) > 1 else "origin/main"
    targets = [
        f for f in changed_files(base)
        if f.endswith(".md") and any(d in f for d in LINKED_DOC_DIRS)
    ]
    if not targets:
        print("no plan or spec touched — nothing to check")
        return 0

    problems = []
    for rel in targets:
        path = ROOT / rel
        if not path.is_file():          # deleted or renamed away
            continue
        fm = parse_frontmatter(path.read_text(encoding="utf-8", errors="replace"))
        if fm is None:
            problems.append(f"{rel}: no frontmatter at all")
            continue
        problem = issue_link_problem(fm)
        if problem:
            problems.append(f"{rel}: {problem}")

    print(f"checked {len(targets)} touched plan/spec file(s)")
    if problems:
        print("\nA plan or spec must name its work:", file=sys.stderr)
        for p in problems:
            print(f"  {p}", file=sys.stderr)
        print(
            '\nSatisfy it one of three ways:\n'
            '  issue: "123"                     an existing issue\n'
            '  issue: "none" + reason: "..."    an opt-out, argued\n'
            '  docs-lint new plan <slug> --new-issue "..."   creates both and links them',
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
