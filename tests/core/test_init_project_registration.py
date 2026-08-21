"""Registration must be able to fill `description` (#378).

`domains.yaml` descriptions feed LLM task classification; every hand-written project has
one. `apply_registration.py` always wrote `"description": ""` and offered no way to supply
it, so every project registered through the skill started blind.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
APPLY = REPO_ROOT / "plugins" / "h2t-core" / "skills" / "init-project" / "scripts" / "apply_registration.py"


def _interpreter():
    for candidate in (Path(sys.executable), REPO_ROOT / ".venv" / "bin" / "python"):
        if candidate.is_file() and subprocess.run(
            [str(candidate), "-c", "import ruamel.yaml, yaml"], capture_output=True
        ).returncode == 0:
            return str(candidate)
    pytest.skip("no interpreter with ruamel.yaml available")


@pytest.fixture
def config_root(tmp_path):
    root = tmp_path / "config"
    root.mkdir()
    (root / "repo-mapping.yaml").write_text("mappings: {}\n", encoding="utf-8")
    (root / "domains.yaml").write_text(
        "domains:\n"
        "  fixture-domain:\n"
        "    label: Fixture\n"
        "    projects:\n"
        "    - id: existing-repo\n"
        "      label: Existing\n"
        "      description: \"already written by hand\"\n",
        encoding="utf-8",
    )
    return root


def _register(config_root, project_id, *args):
    result = subprocess.run(
        [
            _interpreter(), str(APPLY),
            "--id", project_id, "--domain", "fixture-domain",
            "--type", "git", "--label", "Fixture Label",
            "--config-root", str(config_root), *args,
        ],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def _project(config_root, project_id):
    import yaml as pyyaml

    data = pyyaml.safe_load((config_root / "domains.yaml").read_text(encoding="utf-8"))
    entries = data["domains"]["fixture-domain"]["projects"]
    return next(entry for entry in entries if entry["id"] == project_id)


def test_description_is_written_when_supplied(config_root):
    _register(config_root, "new-repo", "--description", "Course revenue and data model")

    assert _project(config_root, "new-repo")["description"] == "Course revenue and data model"


def test_updating_a_project_keeps_its_existing_description(config_root):
    """Re-registering must not blank a description someone wrote by hand."""
    _register(config_root, "existing-repo")

    assert _project(config_root, "existing-repo")["description"] == "already written by hand"


def test_config_root_env_is_honoured_without_the_flag(config_root, monkeypatch):
    """detect_project.py reads H2T_CONFIG_ROOT; apply must resolve the same root.

    Otherwise detection runs against one config and the documented apply command writes
    another — silently, whenever the config is relocated.
    """
    env = dict(os.environ, H2T_CONFIG_ROOT=str(config_root))
    result = subprocess.run(
        [
            _interpreter(), str(APPLY),
            "--id", "env-repo", "--domain", "fixture-domain",
            "--type", "git", "--label", "Env Repo",
        ],
        capture_output=True, text=True, env=env,
    )

    assert result.returncode == 0, result.stderr
    assert _project(config_root, "env-repo")["label"] == "Env Repo"
