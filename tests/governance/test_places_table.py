"""The `yaml places` block of the spec and paths.PLACES agree both ways (§3, §7.6)."""
import re
from pathlib import Path

import yaml

from h2t_ops.core import paths

SPEC = Path(__file__).resolve().parents[2] / "docs/superpowers/specs/2026-10-17-storage-and-governance.md"


def _spec_places():
    text = SPEC.read_text(encoding="utf-8")
    block = re.search(r"```yaml places\n(.*?)```", text, re.S).group(1)
    return [{"id": r["id"], "kind": r["kind"], "class": r["class"], "sync": r["sync"]}
            for r in yaml.safe_load(block)]


def test_places_table_matches_spec_both_ways():
    code = [{"id": p.id, "kind": p.kind, "class": p.cls, "sync": p.sync} for p in paths.PLACES]
    assert code == _spec_places()
