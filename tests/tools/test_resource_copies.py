"""The package's resource trees must not drift from the plugin text they were copied from.

`h2t_ops/resources/` holds the data the tools read (Task 10). The plugins still ship the
same files as text: the standards and the runbook template are references a skill reads,
and the drawio, creative, agent-profile and known_secrets trees sit where the 3.x scripts
looked for them. Task 12 deleted the scripts and the source copy checks
(test_tool_copy_parity); these trees still exist twice, so a change landed in one copy and
not the other would pass every test that reads the wrong one.
"""
from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
_DEV = "plugins/h2t-dev"

# copy -> original; every file under each must be byte-identical, and the sets equal.
RESOURCE_TREES = {
    "h2t_ops/resources/docs/standards": f"{_DEV}/references/standards",
    "h2t_ops/resources/drawio/defaults.yaml": "plugins/h2t-arch/skills/drawio/config/defaults.yaml",
    "h2t_ops/resources/drawio/shapes": "plugins/h2t-arch/skills/drawio/config/shapes",
    "h2t_ops/resources/creative/base": "plugins/h2t-creative/base",
    "h2t_ops/resources/creative/profiles": "plugins/h2t-creative/profiles",
    "h2t_ops/resources/creative/shared": "plugins/h2t-creative/shared",
    "h2t_ops/resources/agent_profile/agent-profiles.json":
        "plugins/h2t-core/skills/agent-profile/references/agent-profiles.json",
    "h2t_ops/resources/known_secrets.yaml": "plugins/h2t-core/skills/setup/known_secrets.yaml",
    "h2t_ops/resources/runbook/runbook-template.md":
        "plugins/h2t-core/skills/autonomous-run/references/runbook-template.md",
}


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


def test_every_resource_file_is_covered():
    """Only the package markers sit outside a compared tree."""
    resources = ROOT / "h2t_ops" / "resources"
    covered = [ROOT / c for c in RESOURCE_TREES]
    loose = sorted(p.relative_to(ROOT).as_posix() for p in resources.rglob("*")
                   if p.is_file() and "__pycache__" not in p.parts and p.name != "__init__.py"
                   and not any(p == c or c in p.parents for c in covered))
    assert loose == []
