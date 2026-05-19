"""Gmail connector — registry entry."""
from h2t_ops.core.registry import ConnectorSpec
from .commands import register  # safe: commands.py has no heavy module-level imports

CONNECTOR = ConnectorSpec(
    name="gmail",
    help="Work with Gmail messages and labels",
    client="h2t_ops.connectors.gmail.client:GmailClient",  # lazy ref (spec §4.1)
    register=register,
)
