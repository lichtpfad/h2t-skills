import json
import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
FORMS = json.loads((ROOT / "tests/release/legacy_call_forms.json").read_text(encoding="utf-8"))


def test_inventory_covers_scaffolded_project_hooks():
    names = {tuple(f["argv"][:2]) for f in FORMS}
    for hook in ("layout-precommit", "bulk-precommit", "secrets-precommit", "on-stop",
                 "post-git-commit-docs-lint"):
        assert ("h2t-hook", hook) in names


HOOK_FORMS = sorted({f["argv"][1] for f in FORMS if f["argv"][0] == "h2t-hook"})


@pytest.mark.parametrize("name", HOOK_FORMS)
def test_every_h2t_hook_form_runs_against_the_current_hook_entry(name, tmp_path):
    """Each 3.x `h2t-hook <name>` resolves in HANDLERS and runs to exit 0 on a quiet input:
    nothing staged for a git hook, an event that asks for nothing for a Claude hook."""
    from h2t_ops import hooks
    from tests.hooks.test_command_hooks import GIT, h2t_hook

    if GIT is None:
        pytest.skip("git is not on PATH")
    assert name in hooks.HANDLERS
    repo, home = tmp_path / "repo", tmp_path / "home"
    repo.mkdir()
    home.mkdir()
    env = {**os.environ, "HOME": str(home), "USERPROFILE": str(home)}
    for args in (["init", "-q"], ["-c", "user.email=t@example.invalid", "-c", "user.name=t",
                                    "commit", "-q", "--allow-empty", "-m", "init"]):
        subprocess.run([GIT, *args], cwd=repo, env=env, check=True, capture_output=True)
    stdin = b"" if isinstance(hooks.HANDLERS[name], hooks.Command) else json.dumps(
        {"hook_event_name": "Probe", "cwd": str(repo), "session_id": "s1"}).encode()
    done = subprocess.run([*h2t_hook(), name], cwd=repo, env=env, input=stdin,
                          capture_output=True, timeout=60, check=False)
    assert done.returncode == 0, done.stderr.decode("utf-8", "replace")


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
