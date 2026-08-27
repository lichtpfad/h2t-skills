"""The standards ship inside the pack (#439).

`lint.py` looked for them under `DEV_ROOT/docs/standards`, which resolves to
`~/Projects/docs/standards` on the author's Mac and `C:/dev/docs/standards` on the author's
Windows box. The first does not exist, so `lint.py h2t-skills` printed eight
`FAIL: missing ...` lines while all eight files sat in a sibling repository. On a stranger's
machine the whole constellation is absent, and the skill reports their tree as violating
standards they cannot read.

Bundling follows the precedent already in this plugin: docs-sync-labels shipped
`labels.json` beside its script and reached for `DEV_ROOT` only as a fallback.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).parents[2]
LIB = REPO / "plugins" / "h2t-dev" / "lib"
if str(LIB) not in sys.path:
    sys.path.insert(0, str(LIB))

from docs.common import STANDARDS_FILES, standards_dir  # noqa: E402

# Paths that exist on exactly one machine in the world. A shipped standard naming one is
# the #434 defect wearing a documentation hat.
PRIVATE_PATH = re.compile(r"C:/dev|C:\\\\dev|/Users/[a-z_]+/|h2t-infra", re.IGNORECASE)


def test_all_eight_standards_ship_with_the_plugin():
    bundled = REPO / "plugins" / "h2t-dev" / "references" / "standards"
    missing = [name for name in STANDARDS_FILES if not (bundled / name).is_file()]
    assert not missing, f"not bundled: {missing}"


def test_standards_resolve_without_any_sibling_repository(monkeypatch):
    """The check must pass in a checkout that has no neighbours — a stranger's machine."""
    monkeypatch.delenv("H2T_DEV_ROOT", raising=False)
    resolved = standards_dir()
    missing = [name for name in STANDARDS_FILES if not (resolved / name).is_file()]
    assert not missing, f"missing under {resolved}: {missing}"


def test_dev_root_override_still_wins(monkeypatch, tmp_path):
    """An operator with their own standards keeps pointing at them."""
    own = tmp_path / "docs" / "standards"
    own.mkdir(parents=True)
    for name in STANDARDS_FILES:
        (own / name).write_text("{}" if name.endswith(".json") else "# own\n", encoding="utf-8")
    monkeypatch.setenv("H2T_DEV_ROOT", str(tmp_path))
    assert standards_dir() == own


def test_no_shipped_standard_names_a_private_path():
    bundled = REPO / "plugins" / "h2t-dev" / "references" / "standards"
    offenders = []
    for path in sorted(bundled.glob("*")):
        if not path.is_file():
            continue
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if PRIVATE_PATH.search(line):
                offenders.append(f"{path.name}:{lineno}: {line.strip()[:70]}")
    assert not offenders, "private paths in shipped standards:\n" + "\n".join(offenders)
