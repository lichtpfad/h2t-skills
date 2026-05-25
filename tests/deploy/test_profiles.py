from pathlib import Path
from types import MappingProxyType

import pytest

from h2t_ops.core.errors import ConfigError
from h2t_ops.deploy import load_profile_registry


def test_load_profile_registry_reads_valid_profile(tmp_path):
    path = tmp_path / "profiles.yaml"
    path.write_text(
        """
profiles:
  github-actions-dispatch:
    contract_version: 1
    kind: script-bundle
    inputs:
      - repo
      - workflow
    deploy:
      run: scripts/deploy/github-actions-dispatch/deploy.ps1
    status:
      run: scripts/deploy/github-actions-dispatch/status.ps1
""".strip(),
        encoding="utf-8",
    )

    profiles = load_profile_registry(path)

    spec = profiles["github-actions-dispatch"]
    assert spec.name == "github-actions-dispatch"
    assert spec.contract_version == 1
    assert spec.kind == "script-bundle"
    assert spec.inputs == ("repo", "workflow")
    assert spec.deploy.run.endswith("deploy.ps1")
    assert spec.status.run.endswith("status.ps1")
    assert isinstance(profiles, MappingProxyType)


def test_load_profile_registry_returns_immutable_specs(tmp_path):
    path = tmp_path / "profiles.yaml"
    path.write_text(
        """
profiles:
  github-actions-dispatch:
    contract_version: 1
    kind: script-bundle
    inputs:
      - repo
    deploy:
      run: scripts/deploy/github-actions-dispatch/deploy.ps1
    status:
      run: scripts/deploy/github-actions-dispatch/status.ps1
""".strip(),
        encoding="utf-8",
    )

    profiles = load_profile_registry(path)

    with pytest.raises(TypeError):
        profiles["ssh-shell"] = profiles["github-actions-dispatch"]

    with pytest.raises(AttributeError):
        profiles["github-actions-dispatch"].inputs.append("workflow")


def test_load_profile_registry_uses_home_at_call_time(monkeypatch, tmp_path):
    home = tmp_path / "home"
    deploy_dir = home / ".h2t" / "config" / "deploy"
    deploy_dir.mkdir(parents=True)
    (deploy_dir / "profiles.yaml").write_text(
        """
profiles:
  ssh-shell:
    contract_version: 1
    kind: script-bundle
    inputs: []
    deploy:
      run: scripts/deploy/ssh-shell/deploy.ps1
    status:
      run: scripts/deploy/ssh-shell/status.ps1
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setattr(Path, "home", lambda: home)

    profiles = load_profile_registry()

    assert list(profiles) == ["ssh-shell"]


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ("{}", "missing required top-level key: profiles"),
        (
            """
profiles:
  bad:
    contract_version: 2
    kind: script-bundle
    inputs: []
    deploy: {run: scripts/deploy/bad/deploy.ps1}
    status: {run: scripts/deploy/bad/status.ps1}
""".strip(),
            "contract_version to 1",
        ),
        (
            """
profiles:
  bad:
    contract_version: 1
    kind: custom
    inputs: []
    deploy: {run: scripts/deploy/bad/deploy.ps1}
    status: {run: scripts/deploy/bad/status.ps1}
""".strip(),
            "kind to 'script-bundle'",
        ),
        (
            """
profiles:
  bad:
    contract_version: 1
    kind: script-bundle
    inputs: [repo]
    deploy: {}
    status: {run: scripts/deploy/bad/status.ps1}
""".strip(),
            "deploy.run",
        ),
    ],
)
def test_load_profile_registry_rejects_malformed_configs(tmp_path, body, message):
    path = tmp_path / "profiles.yaml"
    path.write_text(body, encoding="utf-8")

    with pytest.raises(ConfigError, match=message):
        load_profile_registry(path)
