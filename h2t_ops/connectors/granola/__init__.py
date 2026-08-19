"""Granola connector — registry entry."""
from h2t_ops.core.registry import ConnectorSpec
from .commands import register

CONNECTOR = ConnectorSpec(
    name="granola",
    help="Work with Granola notes, summaries, and transcripts",
    client="h2t_ops.connectors.granola.client:GranolaClient",
    register=register,
)
