"""The package copies of the plugin tools must not drift from their originals (Task 10).

`h2t_ops/tools/` and `h2t_ops/resources/` are copies: the 3.x skills and the CI paths in
evals.yml still run the plugin originals, and Task 12 deletes those together with this test.
Until then a fix landed in one copy and not the other passes every test that loads the
wrong one. The tests were copied too, pointed at the package, and drift the same way.

What a copy may differ by is data, per pair: `EDITS` are exact replacements that must
match the original exactly once, applied first; `RULES` are regex rewrites of the import
spelling, applied after. Anything else is drift. Resource trees must be byte-identical.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

# --- rewrite rules --------------------------------------------------------------------

_DOCS_LIB = ("agent_instructions|apply_report|common|config|fix_plan|gitignore_hygiene|"
             "index_builder|misplaced_files|naming|new_doc|orphan|project_types|reporter|"
             "retire|root_structure")
# Inside the package: `from docs.<module> import` -> `from .<module> import`. Relative, so
# the lines keep their length and their isort section.
DOCS_SOURCE = [(re.compile(rf"^([ \t]*)from docs\.({_DOCS_LIB}) import", re.M),
                r"\1from .\2 import")]
# In the tests: `docs.<module>` -> `h2t_ops.tools.docs.<module>`, imports and patch targets.
DOCS_LIB = [(re.compile(rf"(?<![\w./-])docs\.({_DOCS_LIB})\b"), r"h2t_ops.tools.docs.\1")]


def _wrap(match: re.Match) -> str:
    indent, module, names = match.group(1), match.group(2), match.group(3).split(", ")
    if len(match.group(0).rstrip("\n")) <= 88:  # ruff's line length, the isort wrap point
        return match.group(0)
    return (f"{indent}from {module} import (\n"
            + "".join(f"{indent}    {name},\n" for name in names) + f"{indent})\n")


def _tidy_imports(text: str) -> str:
    """What removing the path setup leaves behind, put back the way ruff's isort wants it:
    an unused `sys`/`Path`, an `E402` marker with no path insert above it, two blank lines
    where the setup stood, and a longer module name pushing a line past the wrap point."""
    if not re.search(r"\bsys\.", text) and text.count("import sys\n") == 1:
        text = text.replace("import sys\n", "", 1)
    if len(re.findall(r"\bPath\b", text)) == 1:
        text = text.replace("from pathlib import Path\n", "", 1)
    text = re.sub(r"^((?:from|import) [^\n]*?)  # noqa: E402[^\n]*$", r"\1", text, flags=re.M)
    text = re.sub(r"^((?:import|from) [^\n]*\n)\n{2,}(?=(?:import|from) )", r"\1\n", text,
                  flags=re.M)
    return re.sub(r"^([ \t]*)from (\S+) import ([^\n(]+)\n", _wrap, text, flags=re.M)

TEST_SETUP = [
    # Comments that introduced the path setup.
    (re.compile(r"^# (?:Make lint\.py importable|Make docs\.\* importable|"
                r"Allow running from any directory)\n", re.M), ""),
    # A function-local `import sys` that existed only for the path insert below it.
    (re.compile(r'^([ \t]+)import sys\n(?=\1sys\.path\.insert\(0, str\(Path\("plugins/)', re.M),
     ""),
    (re.compile(r'^(_LIB|_LINT_DIR|_INDEX_DIR|_SCRIPT_DIR) = Path\(__file__\)\.parents\[2\] '
                r'/ "plugins/[^"\n]*"\n', re.M), ""),
    (re.compile(r"^[ \t]*sys\.path\.insert\(0, str\((?:_LIB|_LINT_DIR|_INDEX_DIR|_SCRIPT_DIR|"
                r"Path\(__file__\)(?:\.resolve\(\))?\.parent|[^\n]*(?:h2t-dev|h2t-creative)"
                r"[^\n]*)\)\)[^\n]*\n", re.M), ""),
    # tests/<x>/ -> tests/tools/<x>/: one more level to the repository root.
    (re.compile(r"(Path\(__file__\)(?:\.resolve\(\))?\.parents)\[2\]"), r"\1[3]"),
]

DOCS_SCRIPTS = [
    (re.compile(r"^([ \t]*)from (lint|index|closure) import", re.M),
     r"\1from h2t_ops.tools.docs.\2 import"),
    (re.compile(r"^([ \t]*)import (lint|index|closure)\b", re.M),
     r"\1from h2t_ops.tools.docs import \2"),
    (re.compile(r"""patch\((["'])(lint|closure)\."""), r"patch(\1h2t_ops.tools.docs.\2."),
    # Running lint.py by path becomes running the module.
    (re.compile(r"\[(_?sys\.executable|str\(_PYTHON\)), (?:str\(_LINT\)|_LINT_SCRIPT|lint_script)"),
     r'[\1, "-m", "h2t_ops.tools.docs.lint"'),
]
DOCS_TEST = TEST_SETUP + DOCS_SCRIPTS + DOCS_LIB + [_tidy_imports]

DRAWIO_TEST = TEST_SETUP + [_tidy_imports] + [
    (re.compile(r"^([ \t]*)from (generate|export) import", re.M),
     r"\1from h2t_ops.tools.drawio.\2 import"),
]
CREATIVE_TEST = TEST_SETUP + [_tidy_imports] + [
    (re.compile(r"^import assembler\b", re.M), "from h2t_ops.tools.creative import assembler"),
]
AGENT_TEST = TEST_SETUP + [_tidy_imports] + [
    (re.compile(r"^import apply_agent_profile\b", re.M),
     "from h2t_ops.tools.agent_profile import apply_agent_profile"),
]

# --- enumerated edits -----------------------------------------------------------------

_BOOTSTRAP = '''_PLUGIN_ROOT = Path(__file__).resolve().parents[3]
for _lib in [_PLUGIN_ROOT / "lib", _PLUGIN_ROOT.parent.parent / "lib"]:
    if _lib.exists():
        sys.path.insert(0, str(_lib))
        break

'''
_RESOURCE_IMPORT_AFTER_PATH = ("from pathlib import Path\n",
                               "from pathlib import Path\n\n"
                               "from h2t_ops.resources import resource_dir\n")

_COMMON = [
    ("    The default was `C:/dev`, which is right on exactly one machine and wrong everywhere\n",
     "    The default was a drive-letter dev root, right on exactly one machine and wrong everywhere\n"),
    ("""    2. Derived: if this file sits inside a checkout (a `pyproject.toml` four levels up),
       sibling repositories are that checkout's parent. Correct on both machines with no
       configuration — `C:/dev/h2t-skills` gives `C:/dev`, `~/Projects/h2t-skills` gives
       `~/Projects`.
""", """    2. Derived: if this file sits inside a checkout (a `pyproject.toml` three levels up),
       sibling repositories are that checkout's parent. Correct on both machines with no
       configuration — `~/Projects/h2t-skills` gives `~/Projects`.
"""),
    ("    checkout = Path(__file__).resolve().parents[4]\n",
     "    checkout = Path(__file__).resolve().parents[3]\n"),
    ("# The plugin root: this file is plugins/h2t-dev/lib/docs/common.py.\n"
     "PLUGIN_ROOT = Path(__file__).resolve().parents[2]\n", ""),
    ('    return PLUGIN_ROOT / "references" / "standards"\n',
     '    return resource_dir("docs") / "standards"\n'),
    _RESOURCE_IMPORT_AFTER_PATH,
]

_INDEX_BUILDER = [
    ('''    import sys
    _index_dir = Path(__file__).parents[3] / "skills" / "docs-index" / "scripts"
    if str(_index_dir) not in sys.path:
        sys.path.insert(0, str(_index_dir))
    from index import build_navigation_index
''', "    from .index import build_navigation_index\n"),
]

_LINT = [
    (_BOOTSTRAP, ""),
    ('''_SYNC_LABELS_SCRIPT = Path(__file__).parents[2] / "docs-sync-labels" / "scripts" / "sync_labels.py"
_H2T_PYTHON = (
    Path.home() / ".h2t" / "venv" / "Scripts" / "python.exe"
    if sys.platform == "win32"
    else Path.home() / ".h2t" / "venv" / "bin" / "python"
)


def fix_labels(rp: Path, repo_name: str) -> str:
    python = str(_H2T_PYTHON) if _H2T_PYTHON.exists() else sys.executable
    result = subprocess.run(
        [python, str(_SYNC_LABELS_SCRIPT), repo_name, "--apply"],
''', '''def fix_labels(rp: Path, repo_name: str) -> str:
    result = subprocess.run(
        [sys.executable, "-m", "h2t_ops.tools.docs.sync_labels", repo_name, "--apply"],
'''),
    ('''    """Generate index content, falling back gracefully if docs-index script is unavailable."""
    # Try the canonical docs-index script first
    _index_dir = Path(__file__).resolve().parents[3] / "skills" / "docs-index" / "scripts"
    if _index_dir.exists():
        _orig_path = list(sys.path)
        try:
            if str(_index_dir) not in sys.path:
                sys.path.insert(0, str(_index_dir))
            from index import build_navigation_index  # noqa: PLC0415
            cfg = load_config(repo_root)
            return build_navigation_index(
                repo_root, repo_name, exclude_dirs=cfg.get("exclude_dirs")
            )
        except ImportError:
            # Only "the generator is not shipped here" falls back. Any other
            # error is a real defect, and swallowing it would replace a live
            # index with the two-line stub below on --apply.
            sys.path[:] = _orig_path
    # Fallback: minimal stub index
    return f"# {repo_name} Documentation Index\\n\\n> Auto-generated by docs-lint fix-index\\n"
''', '''    """Generate index content. The generator ships in this package, so there is no fallback."""
    from .index import build_navigation_index

    cfg = load_config(repo_root)
    return build_navigation_index(repo_root, repo_name, exclude_dirs=cfg.get("exclude_dirs"))
'''),
]

_INDEX = [
    ('''if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

''' + _BOOTSTRAP, ""),
    ("    repo_path,\n)\n",
     '    repo_path,\n)\n\nif hasattr(sys.stdout, "reconfigure"):\n'
     '    sys.stdout.reconfigure(encoding="utf-8", errors="replace")\n'),
]

_CLOSURE = [
    ('''    lint = Path(__file__).resolve().parents[2] / "docs-lint" / "scripts" / "lint.py"
    r = _run([python, str(lint), "plan", "--root", str(repo_root)])
''', '''    r = _run([python, "-m", "h2t_ops.tools.docs.lint", "plan", "--root", str(repo_root)])
'''),
]

_MIGRATE = [
    # sys and Path were there only for the path insert.
    ('import subprocess\nimport sys\nfrom pathlib import Path\n\n'
     'sys.path.insert(0, str(Path(__file__).parents[3] / "lib"))  # plugins/h2t-dev/lib\n'
     "from docs.common import GH, REPO_MANIFEST  # noqa: E402\n",
     "import subprocess\n\nfrom docs.common import GH, REPO_MANIFEST\n"),
]

_SYNC_LABELS = [
    # The function-local `from pathlib import Path as _Path` below is the original's own;
    # the module-level import was there only for the path insert.
    ("import sys\nfrom pathlib import Path\n\n" + _BOOTSTRAP, "import sys\n\n"),
]

_DRAWIO_RESOURCES = ('''SKILL_DIR = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = SKILL_DIR / "config" / "defaults.yaml"
''', '''RESOURCE_DIR = resource_dir("drawio")
DEFAULT_CONFIG = RESOURCE_DIR / "defaults.yaml"
''')

_GENERATE = [
    ("from typing import Any\n", "from typing import TYPE_CHECKING, Any\n"),
    ('''import drawpyo
import yaml
from drawpyo.diagram.edges import Edge
from drawpyo.diagram.objects import Object
''', '''import yaml

from h2t_ops.resources import resource_dir

# drawpyo is the `drawio` extra: imported where a diagram is built, so that the rest of the
# tool — and `h2t-drawio --help` — works on a base install.
if TYPE_CHECKING:
    from drawpyo.diagram.objects import Object
'''),
    (_DRAWIO_RESOURCES[0] + 'DEFAULT_SHAPES = SKILL_DIR / "config" / "shapes" / "general.toml"\n',
     _DRAWIO_RESOURCES[1] + 'DEFAULT_SHAPES = RESOURCE_DIR / "shapes" / "general.toml"\n'),
    ('''    Returns:
        Absolute path to the generated .drawio file.
    """
''', '''    Returns:
        Absolute path to the generated .drawio file.
    """
    import drawpyo
    from drawpyo.diagram.edges import Edge
    from drawpyo.diagram.objects import Object

'''),
]

_EXPORT = [
    ("import yaml\n", "import yaml\n\nfrom h2t_ops.resources import resource_dir\n"),
    _DRAWIO_RESOURCES,
]

_ASSEMBLER = [
    ("import yaml\n", "import yaml\n\nfrom h2t_ops.resources import resource_dir\n"),
    ("PLUGIN_ROOT = Path(__file__).parent\n", 'PLUGIN_ROOT = resource_dir("creative")\n'),
]

_AGENT_PROFILE = [
    _RESOURCE_IMPORT_AFTER_PATH,
    ("# Default catalog lives next to this script's parent references/\n"
     '_DEFAULT_CATALOG = Path(__file__).parent.parent / "references" / "agent-profiles.json"\n',
     "# Default catalog ships as package data: h2t_ops/resources/agent_profile/\n"
     '_DEFAULT_CATALOG = resource_dir("agent_profile") / "agent-profiles.json"\n'),
]

_DEV = "plugins/h2t-dev"
_LIB = f"{_DEV}/lib/docs"
_DOCS = "h2t_ops/tools/docs"
_DRAWIO_SRC = "plugins/h2t-arch/skills/drawio/scripts"

# copy -> (original, rules, edits)
SOURCE_PAIRS = {
    f"{_DOCS}/__init__.py": (f"{_LIB}/__init__.py", [], [
        ("# plugins/h2t-dev/lib/docs/__init__.py\n",
         "# h2t_ops/tools/docs — docs-lint and its siblings, copied from plugins/h2t-dev\n")]),
    **{f"{_DOCS}/{m}.py": (f"{_LIB}/{m}.py", DOCS_SOURCE, []) for m in _DOCS_LIB.split("|")},
    f"{_DOCS}/common.py": (f"{_LIB}/common.py", DOCS_SOURCE, _COMMON),
    f"{_DOCS}/index_builder.py": (f"{_LIB}/index_builder.py", DOCS_SOURCE, _INDEX_BUILDER),
    f"{_DOCS}/lint.py": (f"{_DEV}/skills/docs-lint/scripts/lint.py", DOCS_SOURCE, _LINT),
    f"{_DOCS}/index.py": (f"{_DEV}/skills/docs-index/scripts/index.py", DOCS_SOURCE, _INDEX),
    f"{_DOCS}/sync_labels.py": (f"{_DEV}/skills/docs-sync-labels/scripts/sync_labels.py",
                                DOCS_SOURCE, _SYNC_LABELS),
    f"{_DOCS}/migrate_legacy_labels.py": (
        f"{_DEV}/skills/docs-sync-labels/scripts/migrate_legacy_labels.py", DOCS_SOURCE, _MIGRATE),
    f"{_DOCS}/closure.py": (f"{_DEV}/skills/milestone-closure/scripts/closure.py", [], _CLOSURE),
    "h2t_ops/tools/drawio/generate.py": (f"{_DRAWIO_SRC}/generate.py", [], _GENERATE),
    "h2t_ops/tools/drawio/export.py": (f"{_DRAWIO_SRC}/export.py", [], _EXPORT),
    "h2t_ops/tools/creative/assembler.py": ("plugins/h2t-creative/assembler.py", [], _ASSEMBLER),
}

# Package modules written for the package, not copied: nothing to compare them against.
AUTHORED = {
    "h2t_ops/tools/__init__.py",
    "h2t_ops/tools/drawio/__init__.py",
    "h2t_ops/tools/drawio/cli.py",
    "h2t_ops/tools/creative/__init__.py",
    "h2t_ops/tools/creative/cli.py",
}

_T = "tests/tools"
_DOCS_TESTS = [
    "test_agent_instructions", "test_bundled_standards", "test_config", "test_docs_new",
    "test_execution_tracking", "test_fix_index", "test_fix_plan", "test_gitignore_hygiene",
    "test_index_navigation", "test_issue_link_binding", "test_lint_checks", "test_lint_v2",
    "test_misplaced_files", "test_naming_extended", "test_orphan", "test_project_types",
    "test_reporter", "test_retire", "test_root_structure",
]
DOCS_TEST_EDITS: dict[str, list] = {
    "test_execution_tracking": [
        ('_LINT = Path(__file__).parents[2] / "plugins/h2t-dev/skills/docs-lint/scripts/lint.py"\n',
         "")],
    "test_issue_link_binding": [
        ('_LINT = ROOT / "plugins" / "h2t-dev" / "skills" / "docs-lint" / "scripts" / "lint.py"'
         "\n\n\n", "\n")],
    "test_lint_checks": [
        # Path was used only by the two path constants; one test imports its own.
        ('"""Unit tests for docs-lint check functions."""\nimport sys\nfrom pathlib import Path\n',
         '"""Unit tests for docs-lint check functions."""\nimport sys\n'),
        ('_LINT_SCRIPT = str(\n    Path(__file__).parents[2]\n'
         '    / "plugins/h2t-dev/skills/docs-lint/scripts/lint.py"\n)\n\n', ""),
        # fix_labels runs the module, not a script file.
        ('    assert "sync_labels.py" in " ".join(str(c) for c in cmd)\n',
         '    assert "h2t_ops.tools.docs.sync_labels" in cmd\n')],
    "test_bundled_standards": [
        ('LIB = REPO / "plugins" / "h2t-dev" / "lib"\nif str(LIB) not in sys.path:\n'
         "    sys.path.insert(0, str(LIB))\n", "")],
}
# test name -> extra rules, after DOCS_TEST
DOCS_TEST_RULES = {
    "test_bundled_standards": [
        (re.compile(r'REPO / "plugins" / "h2t-dev" / "references" / "standards"'),
         'REPO / "h2t_ops" / "resources" / "docs" / "standards"')],
}
_PYTEST_FIRST = {  # `import assembler` sorted after pytest once it is first-party
    "test_assembler": ("import assembler\nimport pytest\n", "import pytest\n\nimport assembler\n"),
    "test_smoke": ("import assembler as asm\nimport pytest\n",
                   "import pytest\n\nimport assembler as asm\n"),
}

TEST_PAIRS = {
    **{f"{_T}/docs/{t}.py": (f"tests/docs/{t}.py", DOCS_TEST + DOCS_TEST_RULES.get(t, []),
                             DOCS_TEST_EDITS.get(t, []))
       for t in _DOCS_TESTS},
    f"{_T}/docs/test_closure.py": ("tests/milestone/test_closure.py", DOCS_TEST, [
        ('    assert "docs-lint" in " ".join(cmd)\n',
         '    assert "h2t_ops.tools.docs.lint" in cmd\n')]),
    f"{_T}/drawio/test_generate.py": (f"{_DRAWIO_SRC}/test_generate.py", DRAWIO_TEST, []),
    f"{_T}/drawio/test_export.py": (f"{_DRAWIO_SRC}/test_export.py", DRAWIO_TEST, [
        ('    source = (Path(__file__).resolve().parent / "export.py").read_text(encoding="utf-8")\n',
         '    source = (Path(__file__).resolve().parents[3] / "h2t_ops" / "tools" / "drawio"\n'
         '              / "export.py").read_text(encoding="utf-8")\n')]),
    f"{_T}/creative/test_assembler.py": ("tests/h2t_creative/test_assembler.py",
                                         CREATIVE_TEST, [_PYTEST_FIRST["test_assembler"]]),
    f"{_T}/creative/test_smoke.py": ("plugins/h2t-creative/tests/test_smoke.py",
                                     CREATIVE_TEST, [_PYTEST_FIRST["test_smoke"]]),
}

PAIRS = {**SOURCE_PAIRS, **TEST_PAIRS}

# copy -> original; every file under each must be byte-identical, and the sets equal.
RESOURCE_TREES = {
    "h2t_ops/resources/docs/standards": f"{_DEV}/references/standards",
    "h2t_ops/resources/drawio/defaults.yaml": "plugins/h2t-arch/skills/drawio/config/defaults.yaml",
    "h2t_ops/resources/drawio/shapes": "plugins/h2t-arch/skills/drawio/config/shapes",
    "h2t_ops/resources/creative/base": "plugins/h2t-creative/base",
    "h2t_ops/resources/creative/profiles": "plugins/h2t-creative/profiles",
    "h2t_ops/resources/creative/shared": "plugins/h2t-creative/shared",
}


def expected_copy(original: str, rules, edits) -> str:
    for old, new in edits:
        assert original.count(old) == 1, (
            f"an enumerated edit no longer matches the original exactly once "
            f"({original.count(old)} matches): {old.splitlines()[0]!r}")
        original = original.replace(old, new)
    for rule in rules:
        original = rule(original) if callable(rule) else rule[0].sub(rule[1], original)
    return original


def first_difference(expected: str, actual: str) -> str:
    exp, act = expected.splitlines(), actual.splitlines()
    for number, (e, a) in enumerate(zip(exp, act), 1):
        if e != a:
            return f"line {number}: expected {e!r}, copy has {a!r}"
    return f"length differs: expected {len(exp)} lines, copy has {len(act)}"


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


@pytest.mark.parametrize("copy", sorted(PAIRS))
def test_copy_matches_original_up_to_enumerated_edits(copy):
    original, rules, edits = PAIRS[copy]
    expected = expected_copy(_read(original), rules, edits)
    actual = _read(copy)
    assert actual == expected, (
        f"{copy} drifted from {original} beyond the edits enumerated in this test — "
        f"{first_difference(expected, actual)}. Apply the change to both copies. "
        "Task 12 deletes the originals together with this test."
    )


def _files(path: Path) -> dict[str, bytes]:
    if path.is_file():
        return {"": path.read_bytes()}
    return {p.relative_to(path).as_posix(): p.read_bytes() for p in sorted(path.rglob("*"))
            if p.is_file() and "__pycache__" not in p.parts}


@pytest.mark.parametrize("copy", sorted(RESOURCE_TREES))
def test_resource_copy_is_identical(copy):
    want, have = _files(ROOT / RESOURCE_TREES[copy]), _files(ROOT / copy)
    assert want, f"{RESOURCE_TREES[copy]} is empty or missing"
    assert sorted(have) == sorted(want), f"{copy}: file sets differ"
    changed = sorted(name for name in want if want[name] != have[name])
    assert not changed, f"{copy}: differs from {RESOURCE_TREES[copy]} in {changed}"


def test_every_tool_module_is_paired_or_authored():
    """A new module under h2t_ops/tools/ must be classified here, or it escapes the check."""
    modules = {p.relative_to(ROOT).as_posix() for p in (ROOT / "h2t_ops" / "tools").rglob("*.py")}
    assert modules == set(SOURCE_PAIRS) | AUTHORED


def test_every_copied_test_is_paired():
    copies = {p.relative_to(ROOT).as_posix() for p in (ROOT / _T).glob("*/test_*.py")}
    assert copies == set(TEST_PAIRS)


def test_every_resource_file_is_covered():
    """Only the package markers sit outside a compared tree."""
    resources = ROOT / "h2t_ops" / "resources"
    covered = [ROOT / c for c in RESOURCE_TREES]
    loose = sorted(p.relative_to(ROOT).as_posix() for p in resources.rglob("*")
                   if p.is_file() and "__pycache__" not in p.parts and p.name != "__init__.py"
                   and not any(p == c or c in p.parents for c in covered))
    assert loose == []


def test_first_difference_names_the_line():
    """Control for the message: it must point at the line, not just say 'differs'."""
    assert first_difference("a\nb\n", "a\nc\n") == "line 2: expected 'b', copy has 'c'"
