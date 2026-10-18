"""Measure the paths and writes that bypass core/paths, core/store, core/secrets (#548 §7.3).

Partial by design: it matches known spellings, it does not prove there is no bypass —
the sandbox test in tests/governance does that. Counts are lines of tracked
h2t_ops/**/*.py, comment-only lines and docstrings skipped (plan R21): neither runs, so
the numbers move with the code and nothing else.
"""
from __future__ import annotations

import ast
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PATTERNS: dict[str, str] = {
    "home": r"Path\.home\(\)|expanduser\(|[\"']~/|os\.environ\[.HOME.\]|os\.environ\.get\(.HOME|USERPROFILE",
    # Not after a word character or a dot: "secrets.dor" is a LEGACY key, ".dor" and
    # "~/.dor/x" are paths (plan R21).
    "legacy_roots": r"(?<![\w.])\.dor\b|(?<![\w.])\.config/|[\"']\.config[\"']",
    # H2T_DEV_ROOT is where sibling repositories live, not a storage place (plan R16).
    "path_env": r"H2T_(?!DEV_ROOT\b)[A-Z_]*(ROOT|SPOOL|FILE|DIR)\b|H2T_PATH_|H2T_CONFIG_SECRETS",
    "dotenv": r"load_dotenv\(",
    # A line that reads a secret file rarely names it (`path.read_text()`), so a spelling
    # pattern measures nothing. These are the 3.x readers by name; each task that moves one
    # to core.secrets takes its name off the tree.
    "secret_readers": (r"\b_read_env_file\b|\bPROVIDER_ENV_FILE\b|\b_DEFAULT_SECRETS\b"
                       r"|\b_candidate_paths\b|\b_candidate_secret_files\b|\b_resolve_secret_value\b"),
    # File handles opened for writing are caught at the open(); json.dump and fh.write are not
    # writes of their own. tempfile.gettempdir() only names a directory.
    "writes": (r"write_text\(|write_bytes\(|os\.replace\(|os\.rename\(|\b(tmp|src)\w*\.(replace|rename)\("
               r"|shutil\.(copy|copy2|copyfile|copytree|move|rmtree)\b|\.unlink\(|os\.remove\(|rmdir\("
               r"|tempfile\.(mkstemp|mkdtemp|NamedTemporaryFile|TemporaryDirectory|SpooledTemporaryFile)\b"
               r"|FileHandler|\.mkdir\(|os\.fdopen\(|\.touch\(|tree\.write\("
               r"|\.open\([\"'](w|a|x)|(?:^|[^_.\w])open\([^)]*,\s*[\"'](w|a|x)[bt+]*[\"']"),
    "sqlite": r"sqlite3\.connect\(",
}
ALLOWED: dict[str, set[str]] = {
    "home": {"h2t_ops/core/paths.py"},
    "legacy_roots": {"h2t_ops/core/paths.py"},
    "path_env": {"h2t_ops/core/paths.py"},
    "dotenv": set(),
    "secret_readers": {"h2t_ops/core/secrets.py"},
    "writes": {"h2t_ops/core/store.py"},
    "sqlite": {"h2t_ops/core/store.py"},
}


def _tracked(root: Path) -> list[str]:
    # --others: a new module that is not staged yet must count too, or the ratchet stays
    # green until the commit.
    out = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard", "h2t_ops/"],
                         cwd=root, capture_output=True, text=True, check=True).stdout
    return sorted({p for p in out.splitlines() if p.endswith(".py")})


def docstring_lines(text: str) -> set[int]:
    """Line numbers of module, class and function docstrings; none if the file does not parse."""
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return set()
    out: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                    and isinstance(body[0].value.value, str):
                out.update(range(body[0].lineno, body[0].end_lineno + 1))
    return out


def hits(root: Path, name: str) -> list[str]:
    rx = re.compile(PATTERNS[name])
    found = []
    for rel in _tracked(root):
        if rel in ALLOWED[name]:
            continue
        try:
            text = (root / rel).read_text(encoding="utf-8-sig")
        except (UnicodeDecodeError, FileNotFoundError):
            continue
        skip = docstring_lines(text)
        for n, line in enumerate(text.splitlines(), 1):
            if line.lstrip().startswith("#") or n in skip:
                continue
            if rx.search(line):
                found.append(f"{rel}:{n}")
    return found


def files(root: Path, name: str) -> list[str]:
    return sorted({h.rsplit(":", 1)[0].removeprefix("h2t_ops/") for h in hits(root, name)})


def main(argv: list[str]) -> int:
    root = Path(argv[argv.index("--root") + 1]) if "--root" in argv else ROOT
    if "--files" in argv:
        print("\n".join(files(root, argv[argv.index("--files") + 1])))
        return 0
    counts = {name: len(hits(root, name)) for name in PATTERNS}
    for name, count in counts.items():
        print(f"{name} {count}")
    if "--check" in argv:
        sys.path.insert(0, str(ROOT / "tests" / "governance"))
        from test_storage_ratchets import CEILINGS  # noqa: E402
        drift = {k: (CEILINGS[k], v) for k, v in counts.items() if CEILINGS.get(k) != v}
        for k, (was, now) in drift.items():
            print(f"ceiling {k}: {was} -> {now}")
        return 1 if drift else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
