"""Granola must be discoverable by the registry and routed by the CLI."""
from __future__ import annotations

from h2t_ops.core.registry import ConnectorSpec, discover, resolve_client


def _spec() -> ConnectorSpec:
    specs = {s.name: s for s in discover()}
    assert "granola" in specs, f"granola not discovered; found {sorted(specs)}"
    return specs["granola"]


def test_registry_discovers_granola_connector():
    spec = _spec()
    assert spec.help
    assert spec.client == "h2t_ops.connectors.granola.client:GranolaClient"


def test_registry_can_resolve_client_class():
    assert resolve_client(_spec()).__name__ == "GranolaClient"


def test_cli_routes_granola_to_the_connector_dispatcher():
    from h2t_ops.cli import _MIGRATED
    assert "granola" in _MIGRATED


def test_cli_parser_accepts_granola_subcommand():
    from h2t_ops.cli import build_parser
    ns = build_parser().parse_args(["granola", "list", "--limit", "2"])
    assert ns.granola_cmd == "list"
