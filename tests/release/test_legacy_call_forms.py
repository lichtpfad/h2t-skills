import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FORMS = json.loads((ROOT / "tests/release/legacy_call_forms.json").read_text(encoding="utf-8"))


def test_inventory_covers_scaffolded_project_hooks():
    names = {tuple(f["argv"][:2]) for f in FORMS}
    for hook in ("layout-precommit", "bulk-precommit", "secrets-precommit"):
        assert ("h2t-hook", hook) in names


def test_inventory_covers_core_cli_forms():
    heads = {f["argv"][0] for f in FORMS}
    for cmd in ("h2t-gather", "h2t-handoff", "h2t-activity-log", "h2t-ops", "h2t-project-register",
                "h2t-scaffold-project", "h2t-project-audit-scan", "h2t-project-audit-report"):
        assert cmd in heads
    gather = [f["argv"] for f in FORMS if f["argv"][0] == "h2t-gather"]
    assert ["h2t-gather", "--cwd", "<dir>", "--briefing-only"] in gather
    assert any(f["argv"][:2] == ["h2t-handoff", "write"] for f in FORMS)


def test_every_entry_has_argv_and_source():
    for f in FORMS:
        assert f["argv"] and f["source"].count(":") >= 1, f
