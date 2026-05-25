from pathlib import Path
from types import MappingProxyType

import pytest

from h2t_ops.core.errors import ConfigError
from h2t_ops.deploy import load_profile_registry, load_service_registry


def test_load_service_registry_reads_valid_service(tmp_path):
    profiles_path = tmp_path / "profiles.yaml"
    profiles_path.write_text(
        """
profiles:
  arvixe-upload:
    contract_version: 1
    kind: script-bundle
    inputs:
      - host
      - user
    deploy:
      run: scripts/deploy/arvixe-upload/deploy.ps1
    status:
      run: scripts/deploy/arvixe-upload/status.ps1
""".strip(),
        encoding="utf-8",
    )
    services_path = tmp_path / "services.yaml"
    services_path.write_text(
        """
services:
  h2t-graphs:
    service_type: static-site
    help: h2t-graphs landing
    default_target: arvixe-prod
    targets:
      arvixe-prod:
        profile: arvixe-upload
        config:
          host: example.host
          user: deploy
""".strip(),
        encoding="utf-8",
    )

    profiles = load_profile_registry(profiles_path)
    services = load_service_registry(services_path, profiles=profiles)

    spec = services["h2t-graphs"]
    assert spec.name == "h2t-graphs"
    assert spec.service_type == "static-site"
    assert spec.default_target == "arvixe-prod"
    assert spec.targets["arvixe-prod"].profile == "arvixe-upload"
    assert spec.targets["arvixe-prod"].config["host"] == "example.host"
    assert isinstance(services, MappingProxyType)
    assert isinstance(spec.targets, MappingProxyType)
    assert isinstance(spec.targets["arvixe-prod"].config, MappingProxyType)


def test_load_service_registry_returns_immutable_target_mappings(tmp_path):
    profiles = load_profile_registry(
        _write_profiles_fixture(
            tmp_path / "profiles.yaml",
            profile_name="arvixe-upload",
            inputs=["host"],
        )
    )
    services_path = tmp_path / "services.yaml"
    services_path.write_text(
        """
services:
  h2t-graphs:
    service_type: static-site
    help: h2t-graphs landing
    default_target: arvixe-prod
    targets:
      arvixe-prod:
        profile: arvixe-upload
        config:
          host: example.host
""".strip(),
        encoding="utf-8",
    )

    services = load_service_registry(services_path, profiles=profiles)
    spec = services["h2t-graphs"]

    with pytest.raises(TypeError):
        services["another"] = spec

    with pytest.raises(TypeError):
        spec.targets["other"] = spec.targets["arvixe-prod"]

    with pytest.raises(TypeError):
        spec.targets["arvixe-prod"].config["host"] = "changed.host"


def test_load_service_registry_uses_home_and_loads_profiles_by_default(monkeypatch, tmp_path):
    home = tmp_path / "home"
    deploy_dir = home / ".h2t" / "config" / "deploy"
    deploy_dir.mkdir(parents=True)
    (deploy_dir / "profiles.yaml").write_text(
        """
profiles:
  github-actions-dispatch:
    contract_version: 1
    kind: script-bundle
    inputs: []
    deploy:
      run: scripts/deploy/github-actions-dispatch/deploy.ps1
    status:
      run: scripts/deploy/github-actions-dispatch/status.ps1
""".strip(),
        encoding="utf-8",
    )
    (deploy_dir / "services.yaml").write_text(
        """
services:
  h2t-evals:
    service_type: worker
    help: eval worker
    default_target: github-preview
    targets:
      github-preview:
        profile: github-actions-dispatch
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setattr(Path, "home", lambda: home)

    services = load_service_registry()

    assert list(services) == ["h2t-evals"]
    assert services["h2t-evals"].targets["github-preview"].profile == "github-actions-dispatch"


@pytest.mark.parametrize(
    ("body", "message", "profile_inputs"),
    [
        ("{}", "missing required top-level key: services", ["host", "user"]),
        (
            """
services:
  h2t-graphs:
    service_type: static-site
    targets:
      arvixe-prod:
        profile: arvixe-upload
""".strip(),
            "default_target",
            ["host", "user"],
        ),
        (
            """
services:
  h2t-graphs:
    service_type: static-site
    default_target: missing
    targets:
      arvixe-prod:
        profile: arvixe-upload
""".strip(),
            "default_target 'missing' does not match any target",
            [],
        ),
        (
            """
services:
  h2t-graphs:
    service_type: static-site
    default_target: arvixe-prod
    targets:
      arvixe-prod:
        profile: missing-profile
""".strip(),
            "unknown profile",
            ["host", "user"],
        ),
        (
            """
services:
  h2t-graphs:
    service_type: static-site
    default_target: arvixe-prod
    targets:
      arvixe-prod:
        config: {}
""".strip(),
            "missing required field: profile",
            ["host", "user"],
        ),
        (
            """
services:
  h2t-graphs:
    service_type: static-site
    default_target: arvixe-prod
    targets:
      arvixe-prod:
        profile: arvixe-upload
        config:
          host: example.host
""".strip(),
            "missing required config keys",
            ["host", "user"],
        ),
        (
            """
services:
  h2t-graphs:
    service_type: static-site
    default_target: arvixe-prod
    targets:
      arvixe-prod:
        profile: arvixe-upload
        config:
          host: example.host
          user: deploy
          extra: nope
""".strip(),
            "unknown config keys",
            ["host", "user"],
        ),
    ],
)
def test_load_service_registry_rejects_malformed_configs(tmp_path, body, message, profile_inputs):
    services_path = tmp_path / "services.yaml"
    services_path.write_text(body, encoding="utf-8")
    profiles = {
        "arvixe-upload": load_profile_registry(
            _write_profiles_fixture(
                tmp_path / "profiles.yaml",
                profile_name="arvixe-upload",
                inputs=profile_inputs,
            )
        )["arvixe-upload"]
    }

    with pytest.raises(ConfigError, match=message):
        load_service_registry(services_path, profiles=profiles)


def _write_profiles_fixture(path: Path, *, profile_name: str, inputs: list[str] | None = None) -> Path:
    rendered_inputs = "\n".join(f"      - {item}" for item in (inputs or []))
    path.write_text(
        f"""
profiles:
  {profile_name}:
    contract_version: 1
    kind: script-bundle
    inputs:
{rendered_inputs if rendered_inputs else "      []"}
    deploy:
      run: scripts/deploy/{profile_name}/deploy.ps1
    status:
      run: scripts/deploy/{profile_name}/status.ps1
""".strip(),
        encoding="utf-8",
    )
    return path
