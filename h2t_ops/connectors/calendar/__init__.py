"""Calendar connector — registry entry."""
from h2t_ops.core.registry import ConnectorSpec

from .commands import register  # safe: commands.py has no heavy module-level imports

CONNECTOR = ConnectorSpec(
    name="calendar",
    help="Work with Google Calendar events",
    client="h2t_ops.connectors.calendar.client:CalendarClient",  # lazy ref (spec §4.1)
    register=register,
)
