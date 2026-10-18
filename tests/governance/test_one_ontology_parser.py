"""One ontology parser (#548 §5, Task 15): domains.yaml and repo-mapping.yaml are parsed by
the index builder, and every reader asks index.ontology().

Two allowed files: lifecycle/index/build.py parses, lifecycle/apply_registration.py writes
through ruamel (it loads to keep the comments). The pairing is looked for across the whole
file, not one line: in tools/docs/common.py the file name and the safe_load sat on lines 88
and 94.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ALLOWED = {"lifecycle/index/build.py", "lifecycle/apply_registration.py"}
_PARSE = re.compile(r"yaml\.safe_load|YAML\(\)")
_NAMES = re.compile(r"domains\.yaml|repo-mapping\.yaml")


def parsers(package: Path) -> list[str]:
    """Modules under `package` that both parse YAML and name an ontology file."""
    out = []
    for f in sorted(package.rglob("*.py")):
        text = f.read_text(encoding="utf-8", errors="replace")
        if _PARSE.search(text) and _NAMES.search(text):
            out.append(f.relative_to(package).as_posix())
    return out


def test_only_the_index_builder_parses_the_ontology():
    extra = sorted(set(parsers(ROOT / "h2t_ops")) - ALLOWED)
    assert extra == [], f"parse the ontology through h2t_ops.lifecycle.index.ontology(): {extra}"


def test_the_scan_sees_a_pairing_split_across_lines(tmp_path):
    """Control: the shape common.py had — the name on one line, safe_load on another."""
    (tmp_path / "x.py").write_text('p = home / "repo-mapping.yaml"\n\n'
                                   "data = yaml.safe_load(p.read_text())\n", encoding="utf-8")
    (tmp_path / "y.py").write_text("data = yaml.safe_load(other)\n", encoding="utf-8")
    assert parsers(tmp_path) == ["x.py"]
