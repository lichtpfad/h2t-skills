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


_SKILL_ROOT = re.compile(r"--config-root|H2T_CONFIG_ROOT")


def skill_root_overrides(plugins: Path) -> list[str]:
    """Shipped skill text that names a config root itself. Registration with --config-root
    writes with dest=True into a directory the index never reads, and H2T_CONFIG_ROOT is
    retired (R5); without the flag the CLI uses paths.config_dir(). CHANGELOG.md records
    history and is skipped."""
    out = []
    for f in sorted(plugins.rglob("*.md")):
        if f.name == "CHANGELOG.md":
            continue
        for n, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if _SKILL_ROOT.search(line):
                out.append(f"{f.relative_to(plugins).as_posix()}:{n}")
    return out


def test_no_shipped_skill_names_a_config_root():
    assert skill_root_overrides(ROOT / "plugins") == []


def test_the_skill_scan_sees_both_spellings(tmp_path):
    """Control: the two forms init-project and scaffold-project shipped until Task 15."""
    d = tmp_path / "p" / "skills" / "s"
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text('a\n  --cwd x --config-root "$CONFIG_ROOT"\n'
                                'b "${H2T_CONFIG_ROOT:-x}"\n', encoding="utf-8")
    (tmp_path / "p" / "CHANGELOG.md").write_text("--config-root\n", encoding="utf-8")
    assert skill_root_overrides(tmp_path) == ["p/skills/s/SKILL.md:2", "p/skills/s/SKILL.md:3"]
