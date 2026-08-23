"""Evals connector - registry entry (read-only status)."""
from h2t_ops.core.registry import ConnectorSpec

from .commands import register

CONNECTOR = ConnectorSpec(
    name="evals",
    help="Eval telemetry mode/status (read-only)",
    client="lib.eval.status:get_status",
    register=register,
)
