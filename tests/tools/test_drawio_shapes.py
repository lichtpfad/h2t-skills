"""`h2t-drawio shapes`: the node types, without a `python -c` over the plugin config (Task 12)."""
from __future__ import annotations

import json

from h2t_ops.tools.drawio import cli


def test_shipped_library_is_listed(capsys):
    assert cli.main(["shapes", "--json"]) == 0
    types = json.loads(capsys.readouterr().out)
    assert "cylinder" in types
    assert not any(name.startswith("_") for name in types)


def test_a_project_override_is_merged_on_top(tmp_path, capsys):
    override = tmp_path / ".drawio-shapes.toml"
    override.write_text('[my_queue]\nbaseStyle = "shape=mxgraph.queue"\n', encoding="utf-8")
    assert cli.main(["shapes", "--shapes", str(override), "--json"]) == 0
    types = json.loads(capsys.readouterr().out)
    assert types["my_queue"] == "shape=mxgraph.queue"
    assert "cylinder" in types
