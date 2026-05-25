import json
from types import MappingProxyType

from h2t_ops.core.errors import ConfigError
from h2t_ops.deploy.commands import dispatch
from h2t_ops.deploy.models import DeployServiceSpec, DeployTargetBinding


def test_deploy_list_json_success_with_monkeypatched_registries(monkeypatch, capsys):
    monkeypatch.setattr("h2t_ops.deploy.commands.load_profile_registry", lambda: {"bundle": object()})
    monkeypatch.setattr(
        "h2t_ops.deploy.commands.load_service_registry",
        lambda *, profiles: MappingProxyType(
            {
                "h2t-graphs": DeployServiceSpec(
                    name="h2t-graphs",
                    service_type="static-site",
                    help="",
                    default_target="prod",
                    targets=MappingProxyType(
                        {
                            "prod": DeployTargetBinding(
                                name="prod",
                                profile="bundle",
                                config=MappingProxyType({}),
                            )
                        }
                    ),
                )
            }
        ),
    )

    code = dispatch(["list", "--json"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert code == 0
    assert payload == {
        "ok": True,
        "provider": "deploy",
        "result": [
            {
                "service": "h2t-graphs",
                "service_type": "static-site",
                "target": "prod",
                "profile": "bundle",
                "is_default": True,
            }
        ],
    }


def test_deploy_service_dispatches_to_executor(monkeypatch, capsys):
    calls = []

    def fake_execute(service, *, action, target, dry_run):
        calls.append((service, action, target, dry_run))
        return {
            "ok": True,
            "provider": "deploy",
            "result": {"service": service, "status": "deployed"},
        }

    monkeypatch.setattr("h2t_ops.deploy.commands.execute_deploy_action", fake_execute)

    code = dispatch(["h2t-graphs", "--target", "prod", "--dry-run", "--json"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert code == 0
    assert calls == [("h2t-graphs", "deploy", "prod", True)]
    assert payload == {
        "ok": True,
        "provider": "deploy",
        "result": {"service": "h2t-graphs", "status": "deployed"},
    }


def test_deploy_status_dispatches_to_executor(monkeypatch, capsys):
    calls = []

    def fake_execute(service, *, action, target, dry_run):
        calls.append((service, action, target, dry_run))
        return {
            "ok": True,
            "provider": "deploy",
            "result": {"service": service, "status": "unsupported"},
        }

    monkeypatch.setattr("h2t_ops.deploy.commands.execute_deploy_action", fake_execute)

    code = dispatch(["status", "h2t-graphs", "--target", "prod", "--json"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert code == 0
    assert calls == [("h2t-graphs", "status", "prod", False)]
    assert payload["result"]["status"] == "unsupported"


def test_deploy_list_invalid_registry_fails_as_a_whole(monkeypatch, capsys):
    monkeypatch.setattr(
        "h2t_ops.deploy.commands.load_profile_registry",
        lambda: (_ for _ in ()).throw(ConfigError("bad profiles")),
    )

    code = dispatch(["list", "--json"])

    captured = capsys.readouterr()
    payload = json.loads(captured.err)
    assert code == 3
    assert payload["error"]["type"] == "config"
    assert payload["error"]["message"] == "bad profiles"


def test_deploy_missing_args_returns_usage_code(capsys):
    code = dispatch([])

    captured = capsys.readouterr()
    assert code == 2
    assert "deploy requires a subcommand or service name" in captured.err


def test_deploy_invalid_subcommand_returns_usage_code(capsys):
    code = dispatch(["status"])

    captured = capsys.readouterr()
    assert code == 2
    assert "deploy status requires a service name" in captured.err


def test_deploy_parse_failure_honors_json_output(capsys):
    code = dispatch(["status", "--json"])

    captured = capsys.readouterr()
    payload = json.loads(captured.err)
    assert code == 2
    assert payload["ok"] is False
    assert payload["provider"] == "deploy"
    assert payload["error"]["type"] == "usage"
    assert "deploy status requires a service name" in payload["error"]["message"]
