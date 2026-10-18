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


def _parse(text: str) -> ast.Module | None:
    try:
        return ast.parse(text)
    except SyntaxError:
        return None


def docstring_lines(text: str, tree: ast.Module | None = None) -> set[int]:
    """Line numbers of module, class and function docstrings; none if the file does not parse."""
    tree = tree or _parse(text)
    if tree is None:
        return set()
    out: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                    and isinstance(body[0].value.value, str):
                out.update(range(body[0].lineno, body[0].end_lineno + 1))
    return out


_SCOPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)


def _own(scope: ast.AST):
    """The nodes of one scope: nested functions, lambdas and classes are not entered."""
    todo = list(ast.iter_child_nodes(scope))
    while todo:
        node = todo.pop()
        yield node
        if not isinstance(node, _SCOPES):
            todo.extend(ast.iter_child_nodes(node))


def _is_door_import(node: ast.AST, alias: ast.alias) -> bool:
    if isinstance(node, ast.ImportFrom):
        return alias.name == "store" and (
            node.module == "h2t_ops.core" or bool(node.level and node.module == "core"))
    return alias.name == "h2t_ops.core.store" and alias.asname is not None


def _repo_call(value: ast.AST, doors: set[str]) -> bool:
    """`<door>.repo(...)`: the call that hands out a RepoWriter."""
    return isinstance(value, ast.Call) and isinstance(value.func, ast.Attribute) \
        and value.func.attr == "repo" and isinstance(value.func.value, ast.Name) \
        and value.func.value.id in doors


def _bindings(scope: ast.AST) -> dict[str, list[ast.AST]]:
    """Every name the scope binds, with what binds it (Python: a name bound anywhere in a
    function is local to all of it)."""
    out: dict[str, list[ast.AST]] = {}
    if isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
        a = scope.args
        for arg in [*a.posonlyargs, *a.args, *a.kwonlyargs, a.vararg, a.kwarg]:
            if arg is not None:
                out.setdefault(arg.arg, []).append(arg)
    for node in _own(scope):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                out.setdefault(alias.asname or alias.name.split(".")[0], []).append(node)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            out.setdefault(node.id, []).append(node)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out.setdefault(node.name, []).append(node)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            out.setdefault(node.name, []).append(node)
        elif isinstance(node, (ast.MatchAs, ast.MatchStar)) and node.name:
            out.setdefault(node.name, []).append(node)
    return out


def door_spans(tree: ast.Module | None) -> dict[int, list[tuple[int, int]]]:
    """Per line, the byte spans of call targets that are the store door: a method on the
    name the core.store import binds, where nothing in the enclosing scopes rebinds it, or
    on a RepoWriter assigned from `<store>.repo(...)` in the same scope. By binding, not by
    spelling: research has a module of its own imported as `store`, and a parameter or an
    attribute called `store` is not the door."""
    spans: dict[int, list[tuple[int, int]]] = {}
    if tree is None:
        return spans

    def visit(scope: ast.AST, doors: set[str], writers: set[str]) -> None:
        if not isinstance(scope, ast.ClassDef):     # a class body does not enclose methods
            binds = _bindings(scope)
            doors = {n for n in doors if n not in binds}
            writers = {n for n in writers if n not in binds}
            for n, how in binds.items():
                if all(isinstance(b, (ast.Import, ast.ImportFrom))
                       and any(_is_door_import(b, a) and (a.asname or a.name) == n for a in b.names)
                       for b in how):
                    doors.add(n)
            assigned = {id(t): node.value for node in _own(scope) if isinstance(node, ast.Assign)
                        for t in node.targets if isinstance(t, ast.Name)}
            for n, how in binds.items():
                if all(isinstance(b, ast.Name) and _repo_call(assigned.get(id(b)), doors)
                       for b in how):
                    writers.add(n)
        for node in _own(scope):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                f, recv = node.func, node.func.value
                if (isinstance(recv, ast.Name) and recv.id in doors | writers) \
                        or _repo_call(recv, doors):
                    if f.lineno == f.end_lineno:
                        spans.setdefault(f.lineno, []).append((f.col_offset, f.end_col_offset))
            if isinstance(node, _SCOPES):
                visit(node, doors, writers)

    visit(tree, set(), set())
    return spans


def _blank(line: str, cols: list[tuple[int, int]]) -> str:
    """ast columns are UTF-8 byte offsets."""
    raw = bytearray(line.encode("utf-8"))
    for a, b in cols:
        raw[a:b] = b" " * (b - a)
    return raw.decode("utf-8", "replace")


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
        tree = _parse(text)
        skip = docstring_lines(text, tree)
        # `writes`: blank the calls through the door, so a raw write beside one still counts.
        doors = door_spans(tree) if name == "writes" else {}
        for n, line in enumerate(text.splitlines(), 1):
            if line.lstrip().startswith("#") or n in skip:
                continue
            if n in doors:
                line = _blank(line, doors[n])
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
