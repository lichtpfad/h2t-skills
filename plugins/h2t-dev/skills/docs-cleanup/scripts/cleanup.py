#!/usr/bin/env python3
"""Find and archive stale documentation."""

import argparse
import re
import shutil
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

_PLUGIN_ROOT = Path(__file__).resolve().parents[3]
for _lib in [_PLUGIN_ROOT / "lib", _PLUGIN_ROOT.parent.parent / "lib"]:
    if _lib.exists():
        sys.path.insert(0, str(_lib))
        break

from docs.common import parse_frontmatter, print_header, repo_path


def _current_repo_name() -> str | None:
    """Detect repo name from cwd via git remote."""
    result = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        capture_output=True, text=True, cwd=str(Path.cwd()),
    )
    if result.returncode == 0:
        return result.stdout.strip().rstrip("/").split("/")[-1].removesuffix(".git")
    return None


def find_stale_plans(rp: Path, max_age_days: int = 30) -> list[Path]:
    stale = []
    plans_dir = rp / "docs" / "superpowers" / "plans"
    if not plans_dir.exists():
        return stale
    cutoff = datetime.now() - timedelta(days=max_age_days)
    for f in plans_dir.glob("*.md"):
        m = re.match(r"(\d{4}-\d{2}-\d{2})", f.name)
        if m:
            try:
                if datetime.strptime(m.group(1), "%Y-%m-%d") < cutoff:
                    stale.append(f)
            except ValueError:
                pass
    return sorted(stale)


def find_implemented_specs(rp: Path) -> list[Path]:
    specs_dir = rp / "docs" / "superpowers" / "specs"
    if not specs_dir.exists():
        return []
    implemented = []
    for f in specs_dir.glob("*.md"):
        text = f.read_text(encoding="utf-8", errors="replace")
        fm = parse_frontmatter(text)
        if fm and fm.get("status") in ("implemented", "done", "completed"):
            implemented.append(f)
    return sorted(implemented)


def artifacts_size(rp: Path) -> int:
    art = rp / "docs" / ".artifacts"
    if not art.exists():
        return 0
    return sum(f.stat().st_size for f in art.rglob("*") if f.is_file())


def update_readme(rp: Path, archived: list[tuple[Path, Path]], milestone: str) -> None:
    """Append archive section to docs/README.md if it exists."""
    readme = rp / "docs" / "README.md"
    if not readme.exists():
        return
    note = f"\n\n## Archived (M{milestone})\n\n"
    for src, dest in archived:
        note += f"- {src.name} -> {dest.relative_to(rp)}\n"
    with open(readme, "a", encoding="utf-8") as f:
        f.write(note)


def main() -> None:
    parser = argparse.ArgumentParser(description="Archive stale docs")
    parser.add_argument("repo", nargs="?", help="Repo name (default: current repo)")
    parser.add_argument("--apply", action="store_true", help="Execute git mv + commit")
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--milestone", default="N", help="Milestone label for commit message")
    parser.add_argument("--clean-artifacts", action="store_true",
                        help="Delete docs/.artifacts/ contents (requires --apply)")
    args = parser.parse_args()

    name = args.repo or _current_repo_name()
    if not name:
        print("ERROR: cannot determine repo name. Pass repo as argument.")
        sys.exit(1)

    rp = repo_path(name)
    if not rp.exists():
        print(f"ERROR: {rp} not found")
        sys.exit(1)

    mode = "APPLY" if args.apply else "DRY-RUN"
    print_header(f"docs-cleanup [{mode}]: {name}")

    archive_dir = rp / "docs" / "archive"
    candidates: list[tuple[Path, Path]] = []

    stale = find_stale_plans(rp, args.days)
    if stale:
        print(f"\n  Stale plans (>{args.days} days): {len(stale)}")
        for f in stale:
            rel = f.relative_to(rp)
            dest = archive_dir / rel.relative_to("docs")
            candidates.append((f, dest))
            print(f"    {rel}")

    implemented = find_implemented_specs(rp)
    if implemented:
        print(f"\n  Implemented specs: {len(implemented)}")
        for f in implemented:
            rel = f.relative_to(rp)
            dest = archive_dir / rel.relative_to("docs")
            candidates.append((f, dest))
            print(f"    {rel}")

    art_bytes = artifacts_size(rp)
    if art_bytes > 0:
        print(f"\n  docs/.artifacts/: {art_bytes / 1024:.1f} KB")
        if args.clean_artifacts and not args.apply:
            print("  (use --clean-artifacts --apply to delete)")

    if not candidates and not (args.clean_artifacts and art_bytes > 0):
        print("\n  Nothing to do.")
        return

    if not args.apply:
        if candidates:
            print(f"\n  {len(candidates)} files to archive. Run with --apply to execute.")
        return

    # Execute moves
    if candidates:
        archive_dir.mkdir(parents=True, exist_ok=True)
        for src, dest in candidates:
            dest.parent.mkdir(parents=True, exist_ok=True)
            rel_src = src.relative_to(rp)
            rel_dest = dest.relative_to(rp)
            subprocess.run(["git", "-C", str(rp), "mv", str(rel_src), str(rel_dest)], check=True)
            print(f"    moved: {rel_src} -> {rel_dest}")

        update_readme(rp, candidates, args.milestone)

        # Stage README changes from update_readme()
        subprocess.run(["git", "-C", str(rp), "add", "docs/README.md"], check=False)

        subprocess.run(
            ["git", "-C", str(rp), "commit", "-m",
             f"docs: archive M{args.milestone} documents"],
            check=True,
        )
        print(f"\n  Archived {len(candidates)} files.")

    # Clean artifacts
    if args.clean_artifacts and art_bytes > 0:
        art_dir = rp / "docs" / ".artifacts"
        shutil.rmtree(art_dir)
        art_dir.mkdir()
        (art_dir / ".gitkeep").touch()
        print(f"  Cleared docs/.artifacts/ ({art_bytes / 1024:.1f} KB freed)")
        print("  NOTE: .artifacts/ cleanup not auto-committed (usually gitignored)")


if __name__ == "__main__":
    main()
