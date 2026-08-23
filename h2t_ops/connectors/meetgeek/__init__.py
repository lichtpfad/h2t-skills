"""MeetGeek connector — registry entry."""
from h2t_ops.core.registry import ConnectorSpec

from .commands import register

CONNECTOR = ConnectorSpec(
    name="meetgeek",
    help="Work with MeetGeek meetings, transcripts, and summaries",
    client="h2t_ops.connectors.meetgeek.client:MeetGeekClient",
    register=register,
)
