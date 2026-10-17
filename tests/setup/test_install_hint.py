"""The hint for a missing CLI must not need the CLI (Task 12c fix round 1).

It used to say `h2t-ops setup install-h2t-ops ... --dry-run`: a subcommand of the tool
that is missing, and a dry run that installs nothing.
"""
from h2t_ops.setup import _release, legacy


def _missing(tmp_path):
    return legacy.resolve_h2t_ops(which=lambda name: None, home=tmp_path)


def test_a_release_points_at_its_bootstrap(tmp_path, monkeypatch):
    monkeypatch.setattr(_release, "BOOTSTRAP_COMMAND", "uvx --isolated --from W h2t-setup")
    result = _missing(tmp_path)
    assert result["status"] == "missing"
    assert result["hint"] == "Run: uvx --isolated --from W h2t-setup sync"


def test_a_checkout_points_at_setup_or_an_editable_install(tmp_path, monkeypatch):
    monkeypatch.setattr(_release, "BOOTSTRAP_COMMAND", "")
    hint = _missing(tmp_path)["hint"]
    assert "/h2t-core:setup" in hint and "uv tool install --editable ." in hint


def test_neither_hint_needs_the_missing_cli(tmp_path, monkeypatch):
    for command in ("", "uvx --isolated --from W h2t-setup"):
        monkeypatch.setattr(_release, "BOOTSTRAP_COMMAND", command)
        for hint in (_missing(tmp_path)["hint"],
                     legacy.resolve_entry_points(which=lambda n: None, home=tmp_path)["hint"]):
            assert "h2t-ops setup" not in hint and "--dry-run" not in hint, hint
